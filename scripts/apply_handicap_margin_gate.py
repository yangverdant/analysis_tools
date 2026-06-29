"""Apply a narrow handicap-margin calibration gate.

This post-processor uses only pre-match signals already present in the report:
current RQSPF pick, handicap line, margin distribution, score candidates, and
market probabilities. Settled scores are used only to score the proposed
changes and to decide whether the batch is safe to apply.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"
BACKUP_DIR = Path(os.environ.get("FOOTBALL_BACKUP_DIR", ROOT.parent / "football_backups")) / "handicap_margin_gate"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.validate import _validate_predictions  # noqa: E402
from scripts.apply_handicap_margin_axis import (  # noqa: E402
    CODE_TO_RQSPF_CN,
    audit_row,
    connect,
    dumps_json,
    fetch_latest_reports,
    loads_json,
    normalize_code,
    placeholders,
    table_exists,
    to_float,
)


SPF_CN = {"3": "\u4e3b\u80dc", "1": "\u5e73\u5c40", "0": "\u5ba2\u80dc"}


def rqspf_code_for_margin(goal_diff: int, handicap: float) -> str:
    adjusted = goal_diff - handicap
    if adjusted > 0:
        return "3"
    if adjusted == 0:
        return "1"
    return "0"


def rqspf_margin_requirement(handicap: float, direction: str) -> str:
    try:
        h = float(handicap or 0.0)
    except (TypeError, ValueError):
        h = 0.0

    def num(value: float) -> str:
        return str(int(value)) if float(value).is_integer() else f"{value:g}"

    direction = normalize_code(direction)
    if abs(h) < 1e-9:
        return {"3": "主队胜出", "1": "双方打平", "0": "客队胜出"}.get(direction, "")

    if h > 0:
        line = num(h)
        cover = num(h + 1) if float(h).is_integer() else f"超过{line}"
        if direction == "3":
            return f"主队至少赢{cover}球才是让胜"
        if direction == "1":
            return f"主队正好赢{line}球才是让平"
        if direction == "0":
            return f"主队净胜不足{line}球或不胜才是让负"
    else:
        line_value = abs(h)
        line = num(line_value)
        cover_limit = line_value - 1 if float(line_value).is_integer() else None
        miss = num(line_value + 1) if float(line_value).is_integer() else f"超过{line}"
        if direction == "3":
            if cover_limit is not None and cover_limit <= 0:
                return "主队不败才是让胜"
            if cover_limit is not None:
                return f"主队不败或最多输{num(cover_limit)}球才是让胜"
            return f"主队受让{line}球后仍领先才是让胜"
        if direction == "1":
            return f"客队正好赢{line}球才是让平"
        if direction == "0":
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


def bqc_full_code(value: Any) -> str:
    text = str(value or "").strip().lower()
    mapping = {
        "hh": "3", "dh": "3", "ah": "3",
        "hd": "1", "dd": "1", "ad": "1",
        "ha": "0", "da": "0", "aa": "0",
        "\u80dc\u80dc": "3", "\u5e73\u80dc": "3", "\u8d1f\u80dc": "3",
        "\u80dc\u5e73": "1", "\u5e73\u5e73": "1", "\u8d1f\u5e73": "1",
        "\u80dc\u8d1f": "0", "\u5e73\u8d1f": "0", "\u8d1f\u8d1f": "0",
    }
    if text in mapping:
        return mapping[text]
    raw = str(value or "").strip()
    if len(raw) == 2 and raw[1] in {"3", "1", "0"}:
        return raw[1]
    return ""


def axis_context_trusted(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("trusted") or value.get("usable_for_derived"))


def hard_conflict(report: Dict[str, Any], handicap: float, target: str) -> Optional[str]:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    final = report.get("final_prediction") if isinstance(report.get("final_prediction"), dict) else {}
    spf = plays.get("spf") if isinstance(plays.get("spf"), dict) else {}
    bqc = plays.get("bqc") if isinstance(plays.get("bqc"), dict) else {}
    spf_dir = normalize_code(spf.get("direction") or spf.get("recommendation") or final.get("predicted_result"))
    if spf_dir in {"3", "1", "0"} and axis_context_trusted(spf.get("axis_context")):
        if target not in possible_rqspf_codes_under_spf(handicap, spf_dir):
            return "target_impossible_under_trusted_spf"
    bqc_dir = bqc_full_code(bqc.get("recommendation") or bqc.get("recommendation_cn"))
    if bqc_dir in {"3", "1", "0"}:
        if target not in possible_rqspf_codes_under_spf(handicap, bqc_dir):
            return "target_impossible_under_bqc_full_axis"
    return None


def pick_signal(signals: Dict[str, Any], name: str) -> Dict[str, Any]:
    value = signals.get(name)
    return value if isinstance(value, dict) else {}


def build_candidate(
    audit: Dict[str, Any],
    report: Dict[str, Any],
    *,
    min_home_tail_gap: float,
    min_market_gap: float,
) -> Optional[Dict[str, Any]]:
    signals = audit.get("signals") if isinstance(audit.get("signals"), dict) else {}
    current = audit.get("predicted")
    if current not in {"3", "1", "0"}:
        return None
    handicap = float(audit.get("handicap") or 0.0)
    margin = pick_signal(signals, "margin_distribution")
    score = pick_signal(signals, "score_axis")
    conditional = pick_signal(signals, "conditional_axis")
    market = pick_signal(signals, "market_axis")

    home_win_by_1 = float(margin.get("home_win_by_1") or 0.0)
    home_win_by_2_plus = float(margin.get("home_win_by_2_plus") or 0.0)
    market_top = normalize_code(market.get("top"))
    market_gap = float(market.get("gap") or 0.0)
    conditional_top = normalize_code(conditional.get("top"))
    expected_adjusted_margin = float(signals.get("expected_adjusted_margin") or 0.0)

    # Rule 1: home gives one or more goals, display says exact one-goal cover,
    # but the 2+ margin tail is already slightly stronger. This is the specific
    # boundary pattern seen in the World Cup backtest.
    if (
        current == "1"
        and handicap > 0
        and home_win_by_2_plus - home_win_by_1 >= min_home_tail_gap
        and normalize_code(score.get("top")) == "1"
        and normalize_code(conditional.get("top")) == "1"
    ):
        target = "3"
        conflict = hard_conflict(report, handicap, target)
        if not conflict:
            return {
                "after_code": target,
                "reason": "home_gives_draw_to_cover_tail",
                "confidence": round(min(0.68, 0.54 + (home_win_by_2_plus - home_win_by_1)), 4),
                "evidence": {
                    "home_win_by_1": home_win_by_1,
                    "home_win_by_2_plus": home_win_by_2_plus,
                    "tail_gap": round(home_win_by_2_plus - home_win_by_1, 6),
                    "score_axis": score,
                    "conditional_axis": conditional,
                },
            }

    # Rule 2: strong handicap market disagreement. Backtest showed weak market
    # gaps are noisy, so this only fires on a large enough gap and still passes
    # the hard SPF/BQC compatibility guard above.
    if market_top in {"3", "1", "0"} and market_top != current and market_gap >= min_market_gap:
        if (
            handicap >= 2
            and current == "0"
            and market_top == "3"
            and conditional_top == current
            and expected_adjusted_margin <= -0.35
        ):
            return None
        conflict = hard_conflict(report, handicap, market_top)
        if not conflict:
            return {
                "after_code": market_top,
                "reason": "strong_handicap_market_reversal",
                "confidence": round(min(0.7, 0.50 + market_gap), 4),
                "evidence": {
                    "market_axis": market,
                    "conditional_axis": conditional,
                    "expected_adjusted_margin": expected_adjusted_margin,
                    "current": current,
                },
            }

    return None


def make_change(row: sqlite3.Row, audit: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    before = audit.get("predicted")
    after = candidate["after_code"]
    actual = audit.get("actual")
    before_correct = before == actual if actual in {"3", "1", "0"} else None
    after_correct = after == actual if actual in {"3", "1", "0"} else None
    return {
        "lottery_match_id": str(row["lottery_match_id"]),
        "report_id": int(row["report_id"]),
        "match_num": row["match_num"],
        "date": str(row["beijing_time"] or row["match_date"])[:10],
        "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
        "play_type": "rqspf",
        "before_code": before,
        "after_code": after,
        "before": CODE_TO_RQSPF_CN.get(before, before),
        "after": CODE_TO_RQSPF_CN.get(after, after),
        "actual": actual,
        "before_correct": before_correct,
        "after_correct": after_correct,
        "direction": (
            "improved" if before_correct is False and after_correct is True
            else "regressed" if before_correct is True and after_correct is False
            else "changed"
        ),
        "confidence": candidate["confidence"],
        "reason": candidate["reason"],
        "evidence": candidate.get("evidence") or {},
    }


def build_changes_for_row(
    row: sqlite3.Row,
    report: Dict[str, Any],
    *,
    min_home_tail_gap: float,
    min_market_gap: float,
) -> List[Dict[str, Any]]:
    audit = audit_row(row, report, expected_edge=0.18, score_limit=5)
    candidate = build_candidate(
        audit,
        report,
        min_home_tail_gap=min_home_tail_gap,
        min_market_gap=min_market_gap,
    )
    return [make_change(row, audit, candidate)] if candidate else []


def summarize_changes(changes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = defaultdict(int)
    by_reason: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    before_correct = 0
    after_correct = 0
    scored = 0
    for item in changes:
        counts[item["direction"]] += 1
        by_reason[item["reason"]]["changes"] += 1
        by_reason[item["reason"]][item["direction"]] += 1
        if item.get("before_correct") is not None and item.get("after_correct") is not None:
            scored += 1
            before_correct += int(bool(item["before_correct"]))
            after_correct += int(bool(item["after_correct"]))
            by_reason[item["reason"]]["scored"] += 1
            by_reason[item["reason"]]["before_correct"] += int(bool(item["before_correct"]))
            by_reason[item["reason"]]["after_correct"] += int(bool(item["after_correct"]))
    return {
        "changes": len(changes),
        "changed_reports": len({item["report_id"] for item in changes}),
        "improved": counts["improved"],
        "regressed": counts["regressed"],
        "changed_only": counts["changed"],
        "scored": scored,
        "before_correct": before_correct,
        "after_correct": after_correct,
        "delta_correct": after_correct - before_correct,
        "by_reason": {key: dict(value) for key, value in sorted(by_reason.items())},
    }


def apply_to_report(report: Dict[str, Any], change: Dict[str, Any]) -> Dict[str, Any]:
    updated = json.loads(json.dumps(report, ensure_ascii=False, default=str))
    plays = updated.setdefault("play_predictions", {})
    analyses = updated.get("analyses") if isinstance(updated.get("analyses"), dict) else {}
    rqspf = plays.setdefault("rqspf", {})
    previous = rqspf.get("direction")
    target = change["after_code"]
    handicap = to_float(rqspf.get("handicap"), 0.0) or 0.0
    probabilities = rqspf.get("probabilities") if isinstance(rqspf.get("probabilities"), dict) else {}
    rqspf.setdefault("model_direction", previous)
    rqspf["pre_handicap_margin_gate_direction"] = previous
    rqspf["direction"] = target
    rqspf["recommendation"] = target
    rqspf["direction_cn"] = SPF_CN.get(target, target)
    rqspf["recommendation_cn"] = CODE_TO_RQSPF_CN.get(target, change["after"])
    rqspf["margin_requirement"] = rqspf_margin_requirement(handicap, target)
    rqspf["confidence"] = max(float(rqspf.get("confidence") or 0), float(change["confidence"]))
    rqspf["confidence_level"] = "medium" if rqspf["confidence"] < 0.58 else "high"
    rqspf["display_source"] = "handicap_margin_gate"
    if isinstance(rqspf.get("boundary_profile"), dict):
        rqspf["boundary_profile"]["gate_override_direction"] = target
        rqspf["boundary_profile"]["gate_override_cn"] = rqspf["recommendation_cn"]
        rqspf["boundary_profile"]["gate_override_probability"] = round(float(probabilities.get(target) or 0.0), 4)
    rqspf["handicap_margin_gate_adjustment"] = {
        "from": change["before"],
        "to": rqspf["recommendation_cn"],
        "reason": change["reason"],
        "evidence": change.get("evidence") or {},
        "source": "handicap_margin_gate",
        "margin_requirement": rqspf["margin_requirement"],
        "selected_probability": round(float(probabilities.get(target) or 0.0), 4),
    }
    if isinstance(analyses.get("rqspf"), dict):
        analyses["rqspf"].update(rqspf)
    return updated


def make_backup(conn: sqlite3.Connection, changes: Sequence[Dict[str, Any]]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / f"handicap_margin_gate_rows_{stamp}.json"
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


def update_prediction_rows(conn: sqlite3.Connection, match_id: str, play_payload: Dict[str, Any]) -> int:
    if not table_exists(conn, "lottery_predictions"):
        return 0
    rows = conn.execute(
        """
        SELECT prediction_id, predictions
        FROM lottery_predictions
        WHERE lottery_match_id = ? AND play_type = 'rqspf'
        """,
        (match_id,),
    ).fetchall()
    updated = 0
    for row in rows:
        pred = loads_json(row["predictions"], {})
        pred = {**pred, **play_payload} if isinstance(pred, dict) else play_payload
        recommendation = play_payload.get("recommendation_cn") or play_payload.get("direction")
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


def delete_validation_rows(conn: sqlite3.Connection, match_ids: Sequence[str]) -> Dict[str, int]:
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
    counters = {"reports": 0, "prediction_rows": 0}
    for change in changes:
        row = rows_by_report[int(change["report_id"])]
        report = loads_json(row["report_data"], {})
        updated = apply_to_report(report, change)
        conn.execute(
            "UPDATE lottery_analysis_reports SET report_data = ? WHERE report_id = ?",
            (dumps_json(updated), int(change["report_id"])),
        )
        counters["reports"] += 1
        plays = updated.get("play_predictions") if isinstance(updated.get("play_predictions"), dict) else {}
        payload = plays.get("rqspf") if isinstance(plays.get("rqspf"), dict) else {}
        counters["prediction_rows"] += update_prediction_rows(conn, str(row["lottery_match_id"]), payload)
    return counters


def build_plan(args: argparse.Namespace) -> Dict[str, Any]:
    with connect(Path(args.db)) as conn:
        rows = fetch_latest_reports(
            conn,
            args.date_from,
            args.date_to,
            args.league,
            args.report_type,
            args.match_nums,
            args.limit,
        )
        rows_by_report = {int(row["report_id"]): row for row in rows}
        changes: List[Dict[str, Any]] = []
        skipped: Dict[str, int] = defaultdict(int)
        for row in rows:
            if args.finished_only and row["rqspf_result"] in (None, ""):
                skipped["unfinished_or_missing_actual"] += 1
                continue
            report = loads_json(row["report_data"], {})
            row_changes = build_changes_for_row(
                row,
                report,
                min_home_tail_gap=args.min_home_tail_gap,
                min_market_gap=args.min_market_gap,
            )
            if row_changes:
                changes.extend(row_changes)
            else:
                skipped["no_gate_signal"] += 1
    return {
        "success": True,
        "mode": "apply" if args.apply else "dry_run",
        "settings": {
            "date_from": args.date_from,
            "date_to": args.date_to,
            "league": args.league,
            "finished_only": args.finished_only,
            "min_home_tail_gap": args.min_home_tail_gap,
            "min_market_gap": args.min_market_gap,
        },
        "reports_checked": len(rows_by_report),
        "changed_dates": sorted({item["date"] for item in changes}),
        "summary": summarize_changes(changes),
        "skipped": dict(sorted(skipped.items())),
        "changes": changes,
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    plan = build_plan(args)
    summary = plan["summary"]
    if not args.apply:
        return plan
    if args.rollback_on_worse and int(summary.get("delta_correct") or 0) < 0:
        plan["accepted"] = False
        plan["abort_reason"] = "candidate_handicap_margin_delta_worse"
        return plan
    if args.require_no_regression and int(summary.get("regressed") or 0) > 0:
        plan["accepted"] = False
        plan["abort_reason"] = "candidate_handicap_margin_has_regression"
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
            deleted = delete_validation_rows(conn, match_ids)
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--date-from", dest="date_from", default=None)
    parser.add_argument("--date-to", dest="date_to", default=None)
    parser.add_argument("--league", default="\u4e16\u754c\u676f")
    parser.add_argument("--match-nums", default="")
    parser.add_argument("--report-type", default="prediction")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-home-tail-gap", type=float, default=0.02)
    parser.add_argument("--min-market-gap", type=float, default=0.18)
    parser.add_argument("--include-unfinished", dest="finished_only", action="store_false", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback-on-worse", action="store_true")
    parser.add_argument("--require-no-regression", action="store_true", default=True)
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
