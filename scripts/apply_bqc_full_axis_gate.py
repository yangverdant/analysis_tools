"""Apply a narrow BQC full-time-axis arbitration gate.

Dry-run by default. The gate only adjusts the full-time leg of BQC when the
current BQC path is detached from the SPF/score axis. Final scores are used only
for backtest measurement, never for choosing the candidate.
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
BACKUP_DIR = Path(os.environ.get("FOOTBALL_BACKUP_DIR", ROOT.parent / "football_backups")) / "bqc_full_axis_gate"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.validate import _validate_predictions  # noqa: E402


RESULT_CN = {"3": "主胜", "1": "平局", "0": "客胜"}
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


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
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


def normalize_result(value: Any) -> str:
    text = str(value or "").strip()
    return {
        "home_win": "3", "draw": "1", "away_win": "0",
        "主胜": "3", "胜": "3",
        "平局": "1", "平": "1",
        "客胜": "0", "负": "0",
    }.get(text, text)


def normalize_bqc(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if lowered in BQC_LATIN_TO_CODE:
        return BQC_LATIN_TO_CODE[lowered]
    if text in BQC_CN_TO_CODE:
        return BQC_CN_TO_CODE[text]
    if len(text) == 2 and set(text) <= {"3", "1", "0"}:
        return text
    return ""


def actual_bqc(row: sqlite3.Row) -> str:
    return normalize_bqc(row["bqc_result"])


def score_direction(value: Any) -> str:
    match = re.search(r"(\d+)\s*[-:]\s*(\d+)", str(value or ""))
    if not match:
        return ""
    home, away = int(match.group(1)), int(match.group(2))
    if home > away:
        return "3"
    if home == away:
        return "1"
    return "0"


def probability_of(item: Any) -> float:
    if not isinstance(item, dict):
        return 0.0
    for key in ("adjusted_probability", "probability", "prob"):
        value = to_float(item.get(key), 0.0) or 0.0
        if value:
            return value / 100.0 if value > 1.0001 else value
    return 0.0


def normalize_probabilities(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: Dict[str, float] = {}
    for key, raw in value.items():
        code = normalize_result(key)
        if code in {"3", "1", "0"}:
            prob = to_float(raw, 0.0) or 0.0
            result[code] = prob / 100.0 if prob > 1.0001 else prob
    return result


def bqc_probabilities(bqc: Dict[str, Any]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for key, raw in (bqc.get("probabilities") or {}).items():
        code = normalize_bqc(key)
        if len(code) == 2:
            prob = to_float(raw, 0.0) or 0.0
            result[code] = prob / 100.0 if prob > 1.0001 else prob
    return result


def rqspf_code_for_margin(goal_diff: int, handicap: float) -> str:
    adjusted = goal_diff - handicap
    if adjusted > 0:
        return "3"
    if adjusted == 0:
        return "1"
    return "0"


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


def rqspf_conflicts_with_full_axis(row: sqlite3.Row, report: Dict[str, Any], full_axis: str) -> Optional[Dict[str, Any]]:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    rqspf = plays.get("rqspf") if isinstance(plays.get("rqspf"), dict) else {}
    rqspf_dir = normalize_result(rqspf.get("direction") or rqspf.get("recommendation") or rqspf.get("recommendation_cn"))
    if rqspf_dir not in {"3", "1", "0"} or full_axis not in {"3", "1", "0"}:
        return None
    handicap = to_float(rqspf.get("handicap"), None)
    if handicap is None:
        handicap = to_float(row["handicap_line"], 0.0) or 0.0
    possible = possible_rqspf_codes_under_spf(float(handicap), full_axis)
    if possible and rqspf_dir not in possible:
        return {
            "rqspf_direction": rqspf_dir,
            "rqspf_direction_cn": {"3": "让胜", "1": "让平", "0": "让负"}.get(rqspf_dir, rqspf_dir),
            "handicap": float(handicap),
            "possible_under_full_axis": sorted(possible),
        }
    return None


def score_axes(report: Dict[str, Any]) -> Dict[str, Any]:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    final = report.get("final_prediction") if isinstance(report.get("final_prediction"), dict) else {}
    scores = plays.get("top3_scores") or final.get("most_likely_scores") or []
    weighted = {"3": 0.0, "1": 0.0, "0": 0.0}
    items = []
    for raw in scores[:5]:
        score = raw.get("score") if isinstance(raw, dict) else raw
        direction = score_direction(score)
        weight = probability_of(raw)
        if direction in weighted:
            weighted[direction] += weight
        items.append({"score": str(score or ""), "direction": direction, "weight": round(weight, 4)})
    top_axis = items[0]["direction"] if items else ""
    weighted_axis = max(weighted, key=weighted.get) if any(weighted.values()) else top_axis
    return {"top_axis": top_axis, "weighted_axis": weighted_axis, "weighted": weighted, "scores": items}


def choose_bqc_with_full_leg(bqc: Dict[str, Any], full_code: str) -> Optional[Tuple[str, float]]:
    current = normalize_bqc(bqc.get("recommendation") or bqc.get("recommendation_cn"))
    half_code = current[0] if len(current) == 2 else "1"
    candidates = {code: prob for code, prob in bqc_probabilities(bqc).items() if code.endswith(full_code)}
    if candidates:
        code = max(candidates, key=candidates.get)
        return code, candidates[code]
    return f"{half_code}{full_code}", 0.5


def fetch_latest_reports(conn: sqlite3.Connection, args: argparse.Namespace) -> List[sqlite3.Row]:
    report_cols = table_columns(conn, "lottery_analysis_reports")
    stale_filter = "AND COALESCE(ar.is_stale, 0) = 0" if "is_stale" in report_cols else ""
    where = ["ar.report_type = ?"]
    params: List[Any] = [args.report_type]
    if args.date_from:
        where.append("substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) >= ?")
        params.append(args.date_from)
    if args.date_to:
        where.append("substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) <= ?")
        params.append(args.date_to)
    if args.league:
        where.append("COALESCE(lm.league_name_cn, '') = ?")
        params.append(args.league)
    return conn.execute(
        f"""
        SELECT ar.report_id, ar.report_data, ar.report_type, ar.created_at AS report_created_at,
               lm.lottery_match_id, lm.match_num, lm.home_team_cn, lm.away_team_cn,
               lm.league_name_cn, lm.match_date, lm.beijing_time, lm.handicap_line,
               lr.bqc_result
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
        ORDER BY substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10), lm.match_num
        """,
        params,
    ).fetchall()


def evaluate_change(row: sqlite3.Row, report: Dict[str, Any], args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    final = report.get("final_prediction") if isinstance(report.get("final_prediction"), dict) else {}
    spf = plays.get("spf") if isinstance(plays.get("spf"), dict) else {}
    bqc = plays.get("bqc") if isinstance(plays.get("bqc"), dict) else {}
    current = normalize_bqc(bqc.get("recommendation") or bqc.get("recommendation_cn"))
    if len(current) != 2:
        return None
    current_full = current[1]
    probs = normalize_probabilities(spf.get("probabilities") or final.get("probabilities"))
    spf_axis = normalize_result(spf.get("direction") or spf.get("recommendation") or final.get("predicted_result"))
    if not spf_axis and probs:
        spf_axis = max(probs, key=probs.get)
    if spf_axis not in {"3", "1", "0"} or current_full == spf_axis:
        return None

    ordered = sorted(probs.items(), key=lambda item: item[1], reverse=True)
    top_probability = ordered[0][1] if ordered else 0.0
    gap = ordered[0][1] - ordered[1][1] if len(ordered) > 1 else 1.0
    draw_probability = probs.get("1", 0.0)
    scores = score_axes(report)
    expected = final.get("expected_score") if isinstance(final.get("expected_score"), dict) else {}
    expected_margin = (to_float(expected.get("home"), 0.0) or 0.0) - (to_float(expected.get("away"), 0.0) or 0.0)

    reason = ""
    if current_full != "1" and (scores["top_axis"] == spf_axis or scores["weighted_axis"] == spf_axis):
        reason = "non_draw_bqc_detached_from_score_supported_spf"
    elif (
        current_full == "1"
        and spf_axis in {"3", "0"}
        and scores["top_axis"] == spf_axis
        and scores["weighted_axis"] == spf_axis
        and draw_probability < args.max_draw_probability
        and (gap >= args.min_spf_gap or abs(expected_margin) >= args.min_expected_margin)
    ):
        reason = "draw_bqc_overridden_by_consensus_full_axis"
    if not reason:
        return None

    rqspf_conflict = rqspf_conflicts_with_full_axis(row, report, spf_axis)
    if rqspf_conflict:
        return None

    selected = choose_bqc_with_full_leg(bqc, spf_axis)
    if not selected:
        return None
    after_code, selected_confidence = selected
    if after_code == current:
        return None
    actual = actual_bqc(row)
    before_full_correct = current[1] == actual[1] if len(actual) == 2 else None
    after_full_correct = after_code[1] == actual[1] if len(actual) == 2 else None
    before_correct = current == actual if actual else None
    after_correct = after_code == actual if actual else None
    return {
        "lottery_match_id": str(row["lottery_match_id"]),
        "report_id": int(row["report_id"]),
        "match_num": row["match_num"],
        "date": str(row["beijing_time"] or row["match_date"])[:10],
        "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
        "before_code": current,
        "after_code": after_code,
        "before": BQC_CODE_TO_CN.get(current, current),
        "after": BQC_CODE_TO_CN.get(after_code, after_code),
        "actual": actual,
        "actual_display": BQC_CODE_TO_CN.get(actual, actual),
        "before_correct": before_correct,
        "after_correct": after_correct,
        "before_full_correct": before_full_correct,
        "after_full_correct": after_full_correct,
        "direction": (
            "improved" if before_correct is False and after_correct is True
            else "regressed" if before_correct is True and after_correct is False
            else "changed"
        ),
        "full_direction": (
            "improved" if before_full_correct is False and after_full_correct is True
            else "regressed" if before_full_correct is True and after_full_correct is False
            else "changed"
        ),
        "confidence": round(max(0.50, min(float(selected_confidence or 0.5), 0.62)), 4),
        "reason": reason,
        "axis": {
            "spf_axis": spf_axis,
            "spf_axis_cn": RESULT_CN.get(spf_axis, spf_axis),
            "top_probability": round(top_probability, 4),
            "spf_gap": round(gap, 4),
            "draw_probability": round(draw_probability, 4),
            "score_top_axis": scores["top_axis"],
            "score_weighted_axis": scores["weighted_axis"],
            "expected_margin": round(expected_margin, 4),
            "score_candidates": scores["scores"],
        },
    }


def apply_to_report(report: Dict[str, Any], change: Dict[str, Any]) -> Dict[str, Any]:
    updated = loads_json(dumps_json(report), {})
    plays = updated.setdefault("play_predictions", {})
    bqc = plays.setdefault("bqc", {})
    previous = bqc.get("recommendation") or bqc.get("recommendation_cn")
    bqc.setdefault("model_recommendation", previous)
    bqc["pre_full_axis_gate_recommendation"] = previous
    bqc["recommendation"] = BQC_CODE_TO_LATIN.get(change["after_code"], change["after_code"])
    bqc["recommendation_cn"] = BQC_CODE_TO_CN.get(change["after_code"], change["after_code"])
    bqc["confidence"] = max(float(bqc.get("confidence") or 0.0), float(change["confidence"]))
    bqc["confidence"] = min(float(bqc["confidence"]), 0.62)
    bqc["confidence_level"] = "medium" if float(bqc["confidence"]) < 0.62 else "high"
    bqc["full_axis_gate_adjustment"] = {
        "from": change["before"],
        "to": bqc["recommendation_cn"],
        "reason": change["reason"],
        "axis": change["axis"],
        "source": "bqc_full_axis_gate",
    }
    bqc.setdefault("risk_profile", {})
    if isinstance(bqc["risk_profile"], dict):
        bqc["risk_profile"]["risk_note"] = "BQC全场腿已按胜平负/比分轴仲裁，仍需结合半场节奏谨慎使用。"
        bqc["risk_profile"]["recommended_usage"] = "guarded"
    analyses = updated.get("analyses")
    if isinstance(analyses, dict) and isinstance(analyses.get("bqc"), dict):
        analyses["bqc"].update(bqc)
    return updated


def make_backup(conn: sqlite3.Connection, changes: Sequence[Dict[str, Any]]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    path = BACKUP_DIR / f"bqc_full_axis_gate_rows_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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


def update_prediction_rows(conn: sqlite3.Connection, change: Dict[str, Any], bqc: Dict[str, Any]) -> int:
    if not table_exists(conn, "lottery_predictions"):
        return 0
    rows = conn.execute(
        "SELECT prediction_id, predictions FROM lottery_predictions WHERE lottery_match_id = ? AND play_type = 'bqc'",
        (change["lottery_match_id"],),
    ).fetchall()
    updated = 0
    for row in rows:
        pred = loads_json(row["predictions"], {})
        pred = {**pred, **bqc} if isinstance(pred, dict) else bqc
        conn.execute(
            """
            UPDATE lottery_predictions
            SET predictions = ?, recommendation = ?, confidence = ?, confidence_level = ?
            WHERE prediction_id = ?
            """,
            (
                dumps_json(pred),
                bqc.get("recommendation_cn") or bqc.get("recommendation"),
                to_float(bqc.get("confidence"), None),
                bqc.get("confidence_level"),
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
        conn.execute(f"DELETE FROM lottery_validation WHERE lottery_match_id IN ({placeholders(match_ids)})", list(match_ids))
    if table_exists(conn, "post_match_reviews"):
        deleted["post_match_reviews"] = conn.execute(
            f"SELECT COUNT(*) FROM post_match_reviews WHERE match_key IN ({placeholders(match_ids)})",
            list(match_ids),
        ).fetchone()[0]
        conn.execute(f"DELETE FROM post_match_reviews WHERE match_key IN ({placeholders(match_ids)})", list(match_ids))
    return deleted


def summarize_changes(changes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    counts = defaultdict(int)
    full_counts = defaultdict(int)
    before_correct = after_correct = before_full = after_full = scored = full_scored = 0
    by_reason: Dict[str, int] = defaultdict(int)
    for item in changes:
        counts[item["direction"]] += 1
        full_counts[item["full_direction"]] += 1
        by_reason[item["reason"]] += 1
        if item.get("before_correct") is not None and item.get("after_correct") is not None:
            scored += 1
            before_correct += int(bool(item["before_correct"]))
            after_correct += int(bool(item["after_correct"]))
        if item.get("before_full_correct") is not None and item.get("after_full_correct") is not None:
            full_scored += 1
            before_full += int(bool(item["before_full_correct"]))
            after_full += int(bool(item["after_full_correct"]))
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
        "full_improved": full_counts["improved"],
        "full_regressed": full_counts["regressed"],
        "full_changed_only": full_counts["changed"],
        "full_scored": full_scored,
        "before_full_correct": before_full,
        "after_full_correct": after_full,
        "full_delta_correct": after_full - before_full,
        "by_reason": sorted(by_reason.items(), key=lambda item: (-item[1], item[0])),
    }


def build_plan(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    with connect(db_path) as conn:
        rows = fetch_latest_reports(conn, args)
        rows_by_report = {int(row["report_id"]): row for row in rows}
        changes = []
        skipped = defaultdict(int)
        for row in rows:
            report = loads_json(row["report_data"], {})
            change = evaluate_change(row, report, args)
            if change:
                changes.append(change)
            else:
                skipped["no_full_axis_gate_signal"] += 1
    return {
        "mode": "apply" if args.apply else "dry_run",
        "db": str(db_path),
        "settings": {
            "date_from": args.date_from,
            "date_to": args.date_to,
            "league": args.league,
            "report_type": args.report_type,
            "min_spf_gap": args.min_spf_gap,
            "min_expected_margin": args.min_expected_margin,
            "max_draw_probability": args.max_draw_probability,
        },
        "reports_checked": len(rows_by_report),
        "changed_dates": sorted({item["date"] for item in changes}),
        "summary": summarize_changes(changes),
        "skipped": dict(sorted(skipped.items())),
        "changes": changes,
    }


def apply_changes(conn: sqlite3.Connection, rows_by_report: Dict[int, sqlite3.Row], changes: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counters = {"reports": 0, "prediction_rows": 0}
    for change in changes:
        row = rows_by_report[int(change["report_id"])]
        report = loads_json(row["report_data"], {})
        updated = apply_to_report(report, change)
        conn.execute("UPDATE lottery_analysis_reports SET report_data = ? WHERE report_id = ?", (dumps_json(updated), change["report_id"]))
        counters["reports"] += 1
        bqc = ((updated.get("play_predictions") or {}).get("bqc") or {})
        counters["prediction_rows"] += update_prediction_rows(conn, change, bqc)
    return counters


def run(args: argparse.Namespace) -> Dict[str, Any]:
    plan = build_plan(args)
    if not args.apply:
        return plan
    summary = plan["summary"]
    if args.rollback_on_worse and (
        int(summary.get("delta_correct") or 0) < 0
        or int(summary.get("full_delta_correct") or 0) < 0
    ):
        plan["accepted"] = False
        plan["abort_reason"] = "candidate_bqc_full_axis_delta_worse"
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


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--date-from", dest="date_from", default=None)
    parser.add_argument("--date-to", dest="date_to", default=None)
    parser.add_argument("--league", default="世界杯")
    parser.add_argument("--report-type", default="prediction")
    parser.add_argument("--min-spf-gap", type=float, default=0.18)
    parser.add_argument("--min-expected-margin", type=float, default=0.50)
    parser.add_argument("--max-draw-probability", type=float, default=0.305)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback-on-worse", action="store_true")
    parser.add_argument("--rebuild-validation", action="store_true")
    parser.add_argument("--examples-limit", type=int, default=30)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    result = run(args)
    if args.examples_limit >= 0 and len(result.get("changes") or []) > args.examples_limit:
        result["changes"] = result["changes"][: args.examples_limit]
        result["changes_truncated"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("accepted", True) is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
