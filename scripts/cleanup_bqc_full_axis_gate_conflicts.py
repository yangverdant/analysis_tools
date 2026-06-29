"""Revert BQC full-axis gate adjustments that create hard RQSPF conflicts."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.apply_bqc_full_axis_gate import (
    BACKUP_DIR,
    BQC_CODE_TO_CN,
    BQC_CODE_TO_LATIN,
    connect,
    delete_validation_rows_for_match_ids,
    dumps_json,
    normalize_bqc,
    placeholders,
    rqspf_conflicts_with_full_axis,
    table_columns,
    table_exists,
    update_prediction_rows,
)
from backend.app.core.validate import _validate_predictions


DEFAULT_DB = ROOT / "data" / "football_v2.db"


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


def fetch_reports(conn: sqlite3.Connection, args: argparse.Namespace) -> List[sqlite3.Row]:
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
        SELECT ar.report_id, ar.report_data, lm.lottery_match_id, lm.match_num,
               lm.home_team_cn, lm.away_team_cn, lm.match_date, lm.beijing_time,
               lm.handicap_line, lr.bqc_result
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


def evaluate_revert(row: sqlite3.Row, report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    bqc = plays.get("bqc") if isinstance(plays.get("bqc"), dict) else {}
    adjustment = bqc.get("full_axis_gate_adjustment") if isinstance(bqc.get("full_axis_gate_adjustment"), dict) else {}
    if adjustment.get("source") != "bqc_full_axis_gate" or adjustment.get("reverted"):
        return None
    current = normalize_bqc(bqc.get("recommendation") or bqc.get("recommendation_cn"))
    if len(current) != 2:
        return None
    conflict = rqspf_conflicts_with_full_axis(row, report, current[1])
    if not conflict:
        return None
    previous = normalize_bqc(adjustment.get("from"))
    if len(previous) != 2 or previous == current:
        return None
    actual = normalize_bqc(row["bqc_result"])
    return {
        "lottery_match_id": str(row["lottery_match_id"]),
        "report_id": int(row["report_id"]),
        "match_num": row["match_num"],
        "date": str(row["beijing_time"] or row["match_date"])[:10],
        "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
        "before_code": current,
        "after_code": previous,
        "before": BQC_CODE_TO_CN.get(current, current),
        "after": BQC_CODE_TO_CN.get(previous, previous),
        "actual": actual,
        "before_correct": current == actual if actual else None,
        "after_correct": previous == actual if actual else None,
        "conflict": conflict,
    }


def make_backup(conn: sqlite3.Connection, changes: Sequence[Dict[str, Any]]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    path = BACKUP_DIR / f"bqc_full_axis_gate_conflict_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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


def apply_revert(report: Dict[str, Any], change: Dict[str, Any]) -> Dict[str, Any]:
    updated = loads_json(dumps_json(report), {})
    bqc = updated.setdefault("play_predictions", {}).setdefault("bqc", {})
    bqc["recommendation"] = BQC_CODE_TO_LATIN.get(change["after_code"], change["after_code"])
    bqc["recommendation_cn"] = BQC_CODE_TO_CN.get(change["after_code"], change["after_code"])
    adjustment = bqc.get("full_axis_gate_adjustment") if isinstance(bqc.get("full_axis_gate_adjustment"), dict) else {}
    adjustment["reverted"] = True
    adjustment["reverted_at"] = datetime.now().isoformat(timespec="seconds")
    adjustment["revert_reason"] = "rqspf_impossible_under_bqc_axis"
    adjustment["conflict"] = change["conflict"]
    bqc["full_axis_gate_adjustment"] = adjustment
    bqc["full_axis_gate_reverted"] = {
        "from": change["before"],
        "to": change["after"],
        "reason": "rqspf_impossible_under_bqc_axis",
    }
    analyses = updated.get("analyses")
    if isinstance(analyses, dict) and isinstance(analyses.get("bqc"), dict):
        analyses["bqc"].update(bqc)
    return updated


def summarize(changes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    scored = [item for item in changes if item.get("before_correct") is not None]
    return {
        "changes": len(changes),
        "reports": len({item["report_id"] for item in changes}),
        "scored": len(scored),
        "before_correct": sum(1 for item in scored if item.get("before_correct") is True),
        "after_correct": sum(1 for item in scored if item.get("after_correct") is True),
        "delta_correct": (
            sum(1 for item in scored if item.get("after_correct") is True)
            - sum(1 for item in scored if item.get("before_correct") is True)
        ),
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    with connect(db_path) as conn:
        rows = fetch_reports(conn, args)
        changes = []
        rows_by_report = {int(row["report_id"]): row for row in rows}
        for row in rows:
            change = evaluate_revert(row, loads_json(row["report_data"], {}))
            if change:
                changes.append(change)
        result: Dict[str, Any] = {
            "mode": "apply" if args.apply else "dry_run",
            "reports_checked": len(rows),
            "summary": summarize(changes),
            "changed_dates": sorted({item["date"] for item in changes}),
            "changes": changes,
        }
        if not args.apply or not changes:
            return result
        backup_path = make_backup(conn, changes)
        prediction_rows = 0
        for change in changes:
            row = rows_by_report[int(change["report_id"])]
            updated = apply_revert(loads_json(row["report_data"], {}), change)
            conn.execute(
                "UPDATE lottery_analysis_reports SET report_data = ? WHERE report_id = ?",
                (dumps_json(updated), change["report_id"]),
            )
            bqc = ((updated.get("play_predictions") or {}).get("bqc") or {})
            prediction_rows += update_prediction_rows(conn, change, bqc)
        deleted = {"lottery_validation": 0, "post_match_reviews": 0}
        if args.rebuild_validation:
            deleted = delete_validation_rows_for_match_ids(conn, sorted({item["lottery_match_id"] for item in changes}))
        conn.commit()
    validation_result = None
    if args.rebuild_validation and result["changed_dates"]:
        validation_result = _validate_predictions(str(db_path), result["changed_dates"])
    result["backup_path"] = str(backup_path)
    result["prediction_rows"] = prediction_rows
    result["deleted_for_validation_rebuild"] = deleted
    result["validation_result"] = validation_result
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--date-from", dest="date_from", default=None)
    parser.add_argument("--date-to", dest="date_to", default=None)
    parser.add_argument("--league", default="世界杯")
    parser.add_argument("--report-type", default="prediction")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rebuild-validation", action="store_true")
    parser.add_argument("--examples-limit", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(args)
    if args.examples_limit >= 0 and len(result.get("changes") or []) > args.examples_limit:
        result["changes"] = result["changes"][: args.examples_limit]
        result["changes_truncated"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
