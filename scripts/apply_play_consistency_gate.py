"""Apply hard consistency gates across SPF/RQSPF/BQC predictions.

Dry-run by default. This post-processor only fixes mathematically incompatible
play recommendations, such as a trusted SPF home-win axis paired with a BQC
full-time away-win leg, or an RQSPF result that is impossible under the trusted
full-time direction. It does not use final scores to choose a new prediction;
final scores are used only to measure whether scored changes got better/worse.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"
BACKUP_DIR = Path(os.environ.get("FOOTBALL_BACKUP_DIR", ROOT.parent / "football_backups")) / "play_consistency_gate"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.validate import _validate_predictions  # noqa: E402


SPF_CN = {"3": "主胜", "1": "平局", "0": "客胜"}
RQSPF_CN = {"3": "让胜", "1": "让平", "0": "让负"}
BQC_LATIN_TO_CODE = {
    "hh": "33", "hd": "31", "ha": "30",
    "dh": "13", "dd": "11", "da": "10",
    "ah": "03", "ad": "01", "aa": "00",
}
BQC_CODE_TO_LATIN = {value: key for key, value in BQC_LATIN_TO_CODE.items()}
BQC_CN_TO_CODE = {
    "胜胜": "33", "胜平": "31", "胜负": "30",
    "平胜": "13", "平平": "11", "平负": "10",
    "负胜": "03", "负平": "01", "负负": "00",
}
BQC_CODE_TO_CN = {value: key for key, value in BQC_CN_TO_CODE.items()}
FULL_LEG_TO_LATIN = {"3": "h", "1": "d", "0": "a"}


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def placeholders(values: Sequence[Any]) -> str:
    return ",".join(["?"] * len(values))


def loads_json(value: Any, default: Any = None) -> Any:
    if default is None:
        default = {}
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return default
    try:
        return json.loads(str(value))
    except Exception:
        return default


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def direction(value: Any) -> str:
    text = str(value or "").strip()
    aliases = {
        "home_win": "3",
        "draw": "1",
        "away_win": "0",
        "主胜": "3",
        "胜": "3",
        "平局": "1",
        "平": "1",
        "客胜": "0",
        "负": "0",
        "让胜": "3",
        "让平": "1",
        "让负": "0",
    }
    return aliases.get(text, text)


def normalize_bqc(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if lowered in BQC_LATIN_TO_CODE:
        return BQC_LATIN_TO_CODE[lowered]
    if text in BQC_CN_TO_CODE:
        return BQC_CN_TO_CODE[text]
    if len(text) == 2 and set(text) <= {"3", "1", "0"}:
        return text
    return text


def bqc_full_code(value: Any) -> str:
    code = normalize_bqc(value)
    if len(code) == 2 and code[1] in {"3", "1", "0"}:
        return code[1]
    return ""


def axis_context_trusted(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return bool(value.get("usable_for_derived") or value.get("trusted"))


def normalize_probs(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: Dict[str, float] = {}
    for key, raw in value.items():
        code = direction(key)
        if code in {"3", "1", "0"}:
            prob = to_float(raw)
            if prob is not None:
                result[code] = prob
    return result


def rqspf_code_for_margin(goal_diff: int, handicap: float) -> str:
    adjusted = goal_diff - handicap
    if adjusted > 0:
        return "3"
    if adjusted == 0:
        return "1"
    return "0"


def rqspf_margin_requirement(handicap: float, value: str) -> str:
    try:
        h = float(handicap or 0.0)
    except (TypeError, ValueError):
        h = 0.0

    def num(raw: float) -> str:
        return str(int(raw)) if float(raw).is_integer() else f"{raw:g}"

    code = direction(value)
    if abs(h) < 1e-9:
        return {"3": "主队胜出", "1": "双方打平", "0": "客队胜出"}.get(code, "")

    if h > 0:
        line = num(h)
        cover = num(h + 1) if float(h).is_integer() else f"超过{line}"
        if code == "3":
            return f"主队至少赢{cover}球才是让胜"
        if code == "1":
            return f"主队正好赢{line}球才是让平"
        if code == "0":
            return f"主队净胜不足{line}球或不胜才是让负"
    else:
        line_value = abs(h)
        line = num(line_value)
        cover_limit = line_value - 1 if float(line_value).is_integer() else None
        miss = num(line_value + 1) if float(line_value).is_integer() else f"超过{line}"
        if code == "3":
            if cover_limit is not None and cover_limit <= 0:
                return "主队不败才是让胜"
            if cover_limit is not None:
                return f"主队不败或最多输{num(cover_limit)}球才是让胜"
            return f"主队受让{line}球后仍领先才是让胜"
        if code == "1":
            return f"客队正好赢{line}球才是让平"
        if code == "0":
            return f"客队至少赢{miss}球才是让负"
    return ""


def possible_rqspf_codes_under_spf(handicap: float, spf_dir: str) -> set[str]:
    possible: set[str] = set()
    for diff in range(-15, 16):
        if spf_dir == "3" and diff <= 0:
            continue
        if spf_dir == "1" and diff != 0:
            continue
        if spf_dir == "0" and diff >= 0:
            continue
        possible.add(rqspf_code_for_margin(diff, handicap))
    return possible


def choose_rqspf_under_spf(rqspf: Dict[str, Any], handicap: float, spf_dir: str) -> Optional[Tuple[str, float]]:
    possible = possible_rqspf_codes_under_spf(handicap, spf_dir)
    if not possible:
        return None
    probs = normalize_probs(rqspf.get("probabilities")) or normalize_probs(rqspf.get("market_probabilities"))
    if probs:
        selected = max(possible, key=lambda code: probs.get(code, -1.0))
        return selected, probs.get(selected, 0.5)
    # Deterministic fallback: pick the least assertive compatible option when
    # no probability payload exists.
    for code in ("1", "3", "0"):
        if code in possible:
            return code, 0.5
    return None


def bqc_probabilities(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: Dict[str, float] = {}
    for key, raw in value.items():
        code = normalize_bqc(key)
        if len(code) == 2 and set(code) <= {"3", "1", "0"}:
            prob = to_float(raw)
            if prob is not None:
                result[code] = prob
    return result


def choose_bqc_with_full_leg(bqc: Dict[str, Any], full_code: str) -> Optional[Tuple[str, str, float]]:
    probs = bqc_probabilities(bqc.get("probabilities"))
    candidates = {code: prob for code, prob in probs.items() if code.endswith(full_code)}
    if candidates:
        code = max(candidates, key=candidates.get)
        return BQC_CODE_TO_LATIN.get(code, code), BQC_CODE_TO_CN.get(code, code), candidates[code]

    half_probs = normalize_probs(bqc.get("half_time"))
    half_code = max(half_probs, key=half_probs.get) if half_probs else "1"
    code = f"{half_code}{full_code}"
    return BQC_CODE_TO_LATIN.get(code, code), BQC_CODE_TO_CN.get(code, code), half_probs.get(half_code, 0.5)


def actual_for_play(row: sqlite3.Row, play_type: str) -> str:
    if play_type == "bqc":
        return normalize_bqc(row["bqc_result"])
    if play_type == "rqspf":
        return direction(row["rqspf_result"])
    return ""


def fetch_latest_reports(
    conn: sqlite3.Connection,
    date_from: Optional[str],
    date_to: Optional[str],
    league: str,
    report_type: str,
) -> List[sqlite3.Row]:
    report_cols = table_columns(conn, "lottery_analysis_reports")
    stale_filter = "AND COALESCE(ar.is_stale, 0) = 0" if "is_stale" in report_cols else ""
    where = ["ar.report_type = ?"]
    params: List[Any] = [report_type]
    if date_from:
        where.append("substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) >= ?")
        params.append(date_from)
    if date_to:
        where.append("substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) <= ?")
        params.append(date_to)
    if league:
        where.append("lm.league_name_cn = ?")
        params.append(league)

    return conn.execute(
        f"""
        SELECT ar.report_id, ar.report_data, ar.report_type, ar.created_at AS report_created_at,
               lm.lottery_match_id, lm.match_id, lm.match_num, lm.home_team_cn, lm.away_team_cn,
               lm.league_name_cn, lm.match_date, lm.beijing_time, lm.handicap_line,
               lr.spf_result, lr.bqc_result, lr.rqspf_result
        FROM lottery_analysis_reports ar
        JOIN lottery_matches lm ON lm.lottery_match_id = ar.lottery_match_id
        LEFT JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
        WHERE {" AND ".join(where)}
          {stale_filter}
          AND ar.report_id = (
              SELECT ar2.report_id
              FROM lottery_analysis_reports ar2
              WHERE ar2.lottery_match_id = ar.lottery_match_id
                AND ar2.report_type = ar.report_type
                {stale_filter.replace("ar.", "ar2.")}
              ORDER BY datetime(ar2.created_at) DESC, ar2.report_id DESC
              LIMIT 1
          )
        ORDER BY substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10), lm.lottery_match_id
        """,
        params,
    ).fetchall()


def build_changes_for_report(row: sqlite3.Row, report: Dict[str, Any]) -> List[Dict[str, Any]]:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    final = report.get("final_prediction") if isinstance(report.get("final_prediction"), dict) else {}
    spf = plays.get("spf") if isinstance(plays.get("spf"), dict) else {}
    rqspf = plays.get("rqspf") if isinstance(plays.get("rqspf"), dict) else {}
    bqc = plays.get("bqc") if isinstance(plays.get("bqc"), dict) else {}

    spf_dir = direction(spf.get("direction") or spf.get("recommendation") or final.get("predicted_result"))
    spf_trusted = spf_dir in {"3", "1", "0"} and axis_context_trusted(spf.get("axis_context"))

    changes: List[Dict[str, Any]] = []
    bqc_rec = bqc.get("recommendation") or bqc.get("recommendation_cn")
    bqc_full = bqc_full_code(bqc_rec)
    if spf_trusted and bqc and bqc_full and bqc_full != spf_dir:
        selected = choose_bqc_with_full_leg(bqc, spf_dir)
        if selected:
            rec, rec_cn, conf = selected
            before_code = normalize_bqc(bqc_rec)
            after_code = normalize_bqc(rec)
            if before_code != after_code:
                changes.append(make_change(row, "bqc", before_code, after_code, bqc_rec, rec, rec_cn, conf, "bqc_full_time_conflicts_with_trusted_spf"))

    handicap = to_float(rqspf.get("handicap"), None)
    if handicap is None:
        handicap = to_float(row["handicap_line"], 0.0) or 0.0
    rqspf_dir = direction(rqspf.get("direction") or rqspf.get("recommendation"))
    if rqspf and rqspf_dir in {"3", "1", "0"}:
        rqspf_change_added = False
        possible = possible_rqspf_codes_under_spf(handicap, spf_dir) if spf_trusted else set()
        if spf_trusted and possible and rqspf_dir not in possible:
            selected = choose_rqspf_under_spf(rqspf, handicap, spf_dir)
            if selected:
                after_code, conf = selected
                if after_code != rqspf_dir:
                    changes.append(make_change(row, "rqspf", rqspf_dir, after_code, rqspf.get("recommendation_cn") or rqspf_dir, after_code, RQSPF_CN[after_code], conf, "rqspf_impossible_under_trusted_spf"))
                    rqspf_change_added = True

        bqc_axis_dir = {"3": "3", "1": "1", "0": "0"}.get(bqc_full)
        if bqc_axis_dir and not rqspf_change_added:
            possible_under_bqc = possible_rqspf_codes_under_spf(handicap, bqc_axis_dir)
            if possible_under_bqc and rqspf_dir not in possible_under_bqc:
                selected = choose_rqspf_under_spf(rqspf, handicap, bqc_axis_dir)
                if selected:
                    after_code, conf = selected
                    if after_code != rqspf_dir:
                        changes.append(make_change(row, "rqspf", rqspf_dir, after_code, rqspf.get("recommendation_cn") or rqspf_dir, after_code, RQSPF_CN[after_code], conf, "rqspf_impossible_under_bqc_axis"))

    return changes


def make_change(
    row: sqlite3.Row,
    play_type: str,
    before_code: str,
    after_code: str,
    before_display: Any,
    after_raw: Any,
    after_display: str,
    confidence: float,
    reason: str,
) -> Dict[str, Any]:
    actual = actual_for_play(row, play_type)
    before_correct = before_code == actual if actual else None
    after_correct = after_code == actual if actual else None
    return {
        "lottery_match_id": str(row["lottery_match_id"]),
        "report_id": int(row["report_id"]),
        "match_num": row["match_num"],
        "date": str(row["beijing_time"] or row["match_date"])[:10],
        "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
        "play_type": play_type,
        "before_code": before_code,
        "after_code": after_code,
        "before": str(before_display),
        "after": str(after_display),
        "after_raw": str(after_raw),
        "actual": actual,
        "before_correct": before_correct,
        "after_correct": after_correct,
        "direction": (
            "improved" if before_correct is False and after_correct is True
            else "regressed" if before_correct is True and after_correct is False
            else "changed"
        ),
        "confidence": round(float(confidence or 0.5), 4),
        "reason": reason,
    }


def apply_to_report(report: Dict[str, Any], changes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    updated = json.loads(json.dumps(report, ensure_ascii=False, default=str))
    plays = updated.setdefault("play_predictions", {})
    analyses = updated.get("analyses") if isinstance(updated.get("analyses"), dict) else {}
    for change in changes:
        play_type = change["play_type"]
        if play_type == "bqc":
            bqc = plays.setdefault("bqc", {})
            previous = bqc.get("recommendation")
            bqc.setdefault("model_recommendation", previous)
            bqc["pre_consistency_recommendation"] = previous
            bqc["recommendation"] = BQC_CODE_TO_LATIN.get(change["after_code"], change["after_raw"])
            bqc["recommendation_cn"] = BQC_CODE_TO_CN.get(change["after_code"], change["after"])
            bqc["confidence"] = max(float(bqc.get("confidence") or 0), float(change["confidence"]))
            bqc["confidence_level"] = "medium" if bqc["confidence"] < 0.58 else "high"
            bqc["consistency_gate_adjustment"] = {
                "from": change["before"],
                "to": bqc["recommendation_cn"],
                "reason": change["reason"],
                "source": "play_consistency_gate",
            }
            if isinstance(analyses.get("bqc"), dict):
                analyses["bqc"].update(bqc)
        elif play_type == "rqspf":
            rqspf = plays.setdefault("rqspf", {})
            previous = rqspf.get("direction")
            target = change["after_code"]
            handicap = to_float(rqspf.get("handicap"), 0.0) or 0.0
            probabilities = normalize_probs(rqspf.get("probabilities")) or normalize_probs(rqspf.get("adjusted_probs"))
            rqspf.setdefault("model_direction", previous)
            rqspf["pre_consistency_direction"] = previous
            rqspf["direction"] = target
            rqspf["recommendation"] = target
            rqspf["direction_cn"] = SPF_CN.get(target, target)
            rqspf["recommendation_cn"] = RQSPF_CN.get(target, change["after"])
            rqspf["margin_requirement"] = rqspf_margin_requirement(handicap, target)
            rqspf["confidence"] = max(float(rqspf.get("confidence") or 0), float(change["confidence"]))
            rqspf["confidence_level"] = "medium" if rqspf["confidence"] < 0.58 else "high"
            rqspf["display_source"] = "play_consistency_gate"
            if isinstance(rqspf.get("boundary_profile"), dict):
                rqspf["boundary_profile"]["consistency_gate_override_direction"] = target
                rqspf["boundary_profile"]["consistency_gate_override_cn"] = rqspf["recommendation_cn"]
                rqspf["boundary_profile"]["consistency_gate_override_probability"] = round(float(probabilities.get(target) or 0.0), 4)
            rqspf["consistency_gate_adjustment"] = {
                "from": change["before"],
                "to": rqspf["recommendation_cn"],
                "reason": change["reason"],
                "source": "play_consistency_gate",
                "margin_requirement": rqspf["margin_requirement"],
                "selected_probability": round(float(probabilities.get(target) or 0.0), 4),
            }
            if isinstance(analyses.get("rqspf"), dict):
                analyses["rqspf"].update(rqspf)
    return updated


def make_backup(conn: sqlite3.Connection, changes: Sequence[Dict[str, Any]]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / f"play_consistency_gate_rows_{stamp}.json"
    report_ids = sorted({int(item["report_id"]) for item in changes})
    match_ids = sorted({str(item["lottery_match_id"]) for item in changes})
    backup: Dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "report_ids": report_ids,
        "match_ids": match_ids,
        "tables": {},
    }
    if report_ids:
        backup["tables"]["lottery_analysis_reports"] = [
            dict(row) for row in conn.execute(
                f"SELECT * FROM lottery_analysis_reports WHERE report_id IN ({placeholders(report_ids)})",
                report_ids,
            ).fetchall()
        ]
    if match_ids and table_exists(conn, "lottery_predictions"):
        backup["tables"]["lottery_predictions"] = [
            dict(row) for row in conn.execute(
                f"SELECT * FROM lottery_predictions WHERE lottery_match_id IN ({placeholders(match_ids)})",
                match_ids,
            ).fetchall()
        ]
    path.write_text(dumps_json(backup), encoding="utf-8")
    return path


def update_prediction_rows(conn: sqlite3.Connection, match_id: str, play_type: str, play_payload: Dict[str, Any]) -> int:
    if not table_exists(conn, "lottery_predictions"):
        return 0
    rows = conn.execute(
        """
        SELECT prediction_id, predictions
        FROM lottery_predictions
        WHERE lottery_match_id = ? AND play_type = ?
        """,
        (match_id, play_type),
    ).fetchall()
    updated = 0
    for row in rows:
        pred = loads_json(row["predictions"], {})
        pred = {**pred, **play_payload} if isinstance(pred, dict) else play_payload
        recommendation = play_payload.get("recommendation") or play_payload.get("recommendation_cn") or play_payload.get("direction")
        conn.execute(
            """
            UPDATE lottery_predictions
            SET predictions = ?, recommendation = ?, confidence = ?, confidence_level = ?
            WHERE prediction_id = ?
            """,
            (
                dumps_json(pred),
                recommendation,
                to_float(play_payload.get("confidence"), None),
                play_payload.get("confidence_level"),
                row["prediction_id"],
            ),
        )
        updated += 1
    return updated


def delete_validation_rows_for_match_ids(conn: sqlite3.Connection, match_ids: Sequence[str]) -> Dict[str, int]:
    deleted = {"lottery_validation": 0, "post_match_reviews": 0}
    if not match_ids:
        return deleted
    if table_exists(conn, "lottery_validation"):
        deleted["lottery_validation"] = conn.execute(
            f"SELECT COUNT(*) FROM lottery_validation WHERE lottery_match_id IN ({placeholders(match_ids)})",
            list(match_ids),
        ).fetchone()[0]
        conn.execute(
            f"DELETE FROM lottery_validation WHERE lottery_match_id IN ({placeholders(match_ids)})",
            list(match_ids),
        )
    if table_exists(conn, "post_match_reviews"):
        deleted["post_match_reviews"] = conn.execute(
            f"SELECT COUNT(*) FROM post_match_reviews WHERE match_key IN ({placeholders(match_ids)})",
            list(match_ids),
        ).fetchone()[0]
        conn.execute(
            f"DELETE FROM post_match_reviews WHERE match_key IN ({placeholders(match_ids)})",
            list(match_ids),
        )
    return deleted


def apply_changes(conn: sqlite3.Connection, rows_by_report: Dict[int, sqlite3.Row], changes: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    grouped: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for change in changes:
        grouped[int(change["report_id"])].append(change)

    counters = {"reports": 0, "prediction_rows": 0}
    for report_id, report_changes in grouped.items():
        row = rows_by_report[report_id]
        report = loads_json(row["report_data"], {})
        updated = apply_to_report(report, report_changes)
        conn.execute(
            "UPDATE lottery_analysis_reports SET report_data = ? WHERE report_id = ?",
            (dumps_json(updated), report_id),
        )
        counters["reports"] += 1
        plays = updated.get("play_predictions") if isinstance(updated.get("play_predictions"), dict) else {}
        for play_type in sorted({item["play_type"] for item in report_changes}):
            payload = plays.get(play_type) if isinstance(plays.get(play_type), dict) else {}
            counters["prediction_rows"] += update_prediction_rows(conn, str(row["lottery_match_id"]), play_type, payload)
    return counters


def summarize_changes(changes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    by_play: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    counts = defaultdict(int)
    before_correct = 0
    after_correct = 0
    scored = 0
    for item in changes:
        play_type = item["play_type"]
        counts[item["direction"]] += 1
        by_play[play_type]["changes"] += 1
        by_play[play_type][item["direction"]] += 1
        if item.get("before_correct") is not None and item.get("after_correct") is not None:
            scored += 1
            before_correct += int(bool(item["before_correct"]))
            after_correct += int(bool(item["after_correct"]))
            by_play[play_type]["scored"] += 1
            by_play[play_type]["before_correct"] += int(bool(item["before_correct"]))
            by_play[play_type]["after_correct"] += int(bool(item["after_correct"]))
    return {
        "changes": len(changes),
        "reports": len({item["report_id"] for item in changes}),
        "improved": counts["improved"],
        "regressed": counts["regressed"],
        "changed_only": counts["changed"],
        "scored": scored,
        "before_correct": before_correct,
        "after_correct": after_correct,
        "delta_correct": after_correct - before_correct,
        "by_play_type": {key: dict(value) for key, value in sorted(by_play.items())},
    }


def build_plan(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    with connect(db_path) as conn:
        rows = fetch_latest_reports(conn, args.date_from, args.date_to, args.league, args.report_type)
        rows_by_report = {int(row["report_id"]): row for row in rows}
        changes: List[Dict[str, Any]] = []
        skipped = defaultdict(int)
        for row in rows:
            report = loads_json(row["report_data"], {})
            row_changes = build_changes_for_report(row, report)
            if row_changes:
                changes.extend(row_changes)
            else:
                skipped["no_hard_conflict"] += 1
    return {
        "mode": "apply" if args.apply else "dry_run",
        "db": str(db_path),
        "settings": {
            "date_from": args.date_from,
            "date_to": args.date_to,
            "league": args.league,
            "report_type": args.report_type,
        },
        "reports_checked": len(rows_by_report),
        "changed_dates": sorted({item["date"] for item in changes}),
        "summary": summarize_changes(changes),
        "skipped": dict(sorted(skipped.items())),
        "changes": changes,
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    plan = build_plan(args)
    if not args.apply:
        return plan

    summary = plan["summary"]
    if args.rollback_on_worse and int(summary.get("delta_correct") or 0) < 0:
        plan["accepted"] = False
        plan["abort_reason"] = "candidate_play_consistency_delta_worse"
        return plan
    if not plan["changes"]:
        plan["accepted"] = True
        plan["apply_result"] = {"reports": 0, "prediction_rows": 0}
        return plan

    db_path = Path(args.db)
    with connect(db_path) as conn:
        report_ids = sorted({int(item["report_id"]) for item in plan["changes"]})
        rows_by_report = {
            int(row["report_id"]): row
            for row in conn.execute(
                f"SELECT * FROM lottery_analysis_reports WHERE report_id IN ({placeholders(report_ids)})",
                report_ids,
            ).fetchall()
        }
        backup_path = make_backup(conn, plan["changes"])
        apply_result = apply_changes(conn, rows_by_report, plan["changes"])
        deleted = {"lottery_validation": 0, "post_match_reviews": 0}
        if args.rebuild_validation:
            match_ids = sorted({str(item["lottery_match_id"]) for item in plan["changes"]})
            deleted = delete_validation_rows_for_match_ids(conn, match_ids)
        conn.commit()

    validation_result = None
    if args.rebuild_validation and plan["changed_dates"]:
        validation_result = _validate_predictions(str(db_path), plan["changed_dates"])

    plan["accepted"] = True
    plan["backup_path"] = str(backup_path)
    plan["apply_result"] = apply_result
    plan["deleted_for_validation_rebuild"] = deleted
    plan["validation_result"] = validation_result
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply SPF/RQSPF/BQC hard consistency gates")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--date-from", dest="date_from", default=None)
    parser.add_argument("--date-to", dest="date_to", default=None)
    parser.add_argument("--league", default="世界杯")
    parser.add_argument("--report-type", default="prediction")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback-on-worse", action="store_true")
    parser.add_argument("--rebuild-validation", action="store_true")
    parser.add_argument("--examples-limit", type=int, default=30)
    args = parser.parse_args()

    result = run(args)
    if args.examples_limit >= 0 and len(result.get("changes") or []) > args.examples_limit:
        result["changes"] = result["changes"][: args.examples_limit]
        result["changes_truncated"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
