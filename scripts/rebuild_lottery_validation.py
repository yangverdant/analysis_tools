"""Rebuild lottery validation records with the current validation rules.

Dry-run by default. Use --apply to delete target validation/review rows and
recreate them from the latest lottery analysis reports plus settled results.
This script does not fetch network data.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"
BACKUP_DIR = Path(os.environ.get("FOOTBALL_BACKUP_DIR", ROOT.parent / "football_backups")) / "validation_rebuilds"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.validate import (  # noqa: E402
    _is_valid_validation_text,
    _normalize_bqc_value,
    _normalize_rqspf_value,
    _validate_predictions,
)
from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner  # noqa: E402


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone() is not None


def placeholders(values: Sequence[Any]) -> str:
    return ",".join(["?"] * len(values))


def backup_db(db_path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{db_path.stem}_before_validation_rebuild_{stamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def target_dates(conn: sqlite3.Connection, date_from: Optional[str], date_to: Optional[str]) -> List[str]:
    clauses = [
        "lr.lottery_match_id IS NOT NULL",
        """
        EXISTS (
            SELECT 1
            FROM lottery_analysis_reports ar
            WHERE ar.lottery_match_id = lm.lottery_match_id
              AND ar.report_type IN ('prediction', 'full')
        )
        """,
    ]
    params: List[Any] = []
    if date_from:
        clauses.append("substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) <= ?")
        params.append(date_to)

    rows = conn.execute(
        f"""
        SELECT DISTINCT substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) AS d
        FROM lottery_matches lm
        JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
        WHERE {" AND ".join(clauses)}
        ORDER BY d
        """,
        params,
    ).fetchall()
    return [row["d"] for row in rows if row["d"]]


def target_match_ids(conn: sqlite3.Connection, dates: Sequence[str]) -> List[str]:
    if not dates:
        return []
    rows = conn.execute(
        f"""
        SELECT lm.lottery_match_id
        FROM lottery_matches lm
        JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
        WHERE substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) IN ({placeholders(dates)})
          AND EXISTS (
              SELECT 1
              FROM lottery_analysis_reports ar
              WHERE ar.lottery_match_id = lm.lottery_match_id
                AND ar.report_type IN ('prediction', 'full')
          )
        ORDER BY substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10), lm.lottery_match_id
        """,
        list(dates),
    ).fetchall()
    return [str(row["lottery_match_id"]) for row in rows]


def load_validations(conn: sqlite3.Connection, match_ids: Sequence[str]) -> List[sqlite3.Row]:
    if not match_ids or not table_exists(conn, "lottery_validation"):
        return []
    return conn.execute(
        f"""
        SELECT lottery_match_id, play_type, predicted_result, actual_result, is_correct
        FROM lottery_validation
        WHERE lottery_match_id IN ({placeholders(match_ids)})
        """,
        list(match_ids),
    ).fetchall()


def normalized_pair(play_type: str, predicted: Any, actual: Any) -> Tuple[str, str]:
    pred = "" if predicted is None else str(predicted).strip()
    act = "" if actual is None else str(actual).strip()
    if play_type == "bqc":
        return _normalize_bqc_value(pred), _normalize_bqc_value(act)
    if play_type == "rqspf":
        return _normalize_rqspf_value(pred), _normalize_rqspf_value(act)
    return pred, act


def validation_stats(rows: Iterable[sqlite3.Row]) -> Dict[str, Any]:
    raw: Dict[str, Dict[str, int]] = {}
    normalized: Dict[str, Dict[str, int]] = {}
    invalid: Dict[str, int] = {}
    changed = 0

    for row in rows:
        play_type = str(row["play_type"] or "unknown")
        raw.setdefault(play_type, {"total": 0, "correct": 0})
        raw[play_type]["total"] += 1
        raw[play_type]["correct"] += int(row["is_correct"] or 0)

        pred, act = normalized_pair(play_type, row["predicted_result"], row["actual_result"])
        if pred != ("" if row["predicted_result"] is None else str(row["predicted_result"]).strip()) or act != (
            "" if row["actual_result"] is None else str(row["actual_result"]).strip()
        ):
            changed += 1
        if not _is_valid_validation_text(pred) or not _is_valid_validation_text(act):
            invalid[play_type] = invalid.get(play_type, 0) + 1
            continue
        normalized.setdefault(play_type, {"total": 0, "correct": 0})
        normalized[play_type]["total"] += 1
        normalized[play_type]["correct"] += int(pred == act)

    def finish(bucket: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, Any]]:
        result = {}
        for play_type, values in sorted(bucket.items()):
            total = values["total"]
            correct = values["correct"]
            result[play_type] = {
                "total": total,
                "correct": correct,
                "accuracy": round(correct * 100 / total, 1) if total else 0,
            }
        return result

    return {
        "raw": finish(raw),
        "normalized_existing": finish(normalized),
        "invalid_by_play_type": dict(sorted(invalid.items())),
        "normalization_changes": changed,
    }


def delete_target_validations(conn: sqlite3.Connection, match_ids: Sequence[str]) -> Dict[str, int]:
    if not match_ids:
        return {"lottery_validation": 0, "post_match_reviews": 0}
    ids_sql = placeholders(match_ids)
    validation_count = 0
    review_count = 0
    if table_exists(conn, "lottery_validation"):
        validation_count = conn.execute(
            f"SELECT COUNT(*) FROM lottery_validation WHERE lottery_match_id IN ({ids_sql})",
            list(match_ids),
        ).fetchone()[0]
        conn.execute(
            f"DELETE FROM lottery_validation WHERE lottery_match_id IN ({ids_sql})",
            list(match_ids),
        )
    if table_exists(conn, "post_match_reviews"):
        review_count = conn.execute(
            f"SELECT COUNT(*) FROM post_match_reviews WHERE match_key IN ({ids_sql})",
            list(match_ids),
        ).fetchone()[0]
        conn.execute(
            f"DELETE FROM post_match_reviews WHERE match_key IN ({ids_sql})",
            list(match_ids),
        )
    return {"lottery_validation": int(validation_count), "post_match_reviews": int(review_count)}


def build_summary(db_path: Path, date_from: Optional[str], date_to: Optional[str], apply: bool, backup: bool) -> Dict[str, Any]:
    with connect(db_path) as conn:
        dates = target_dates(conn, date_from, date_to)
        match_ids = target_match_ids(conn, dates)
        before_rows = load_validations(conn, match_ids)
        before_stats = validation_stats(before_rows)
        before_counts = {
            "target_dates": len(dates),
            "target_matches": len(match_ids),
            "existing_validations": len(before_rows),
            "existing_reviews": 0,
        }
        if match_ids and table_exists(conn, "post_match_reviews"):
            before_counts["existing_reviews"] = conn.execute(
                f"SELECT COUNT(*) FROM post_match_reviews WHERE match_key IN ({placeholders(match_ids)})",
                list(match_ids),
            ).fetchone()[0]

    summary: Dict[str, Any] = {
        "mode": "apply" if apply else "dry_run",
        "database": str(db_path),
        "date_range": {"from": date_from, "to": date_to},
        "dates": dates,
        "counts_before": before_counts,
        "stats_before": before_stats,
    }

    if not apply:
        summary["would_delete"] = {
            "lottery_validation": before_counts["existing_validations"],
            "post_match_reviews": before_counts["existing_reviews"],
        }
        summary["would_revalidate_dates"] = dates
        return summary

    backup_path = backup_db(db_path) if backup else None
    with connect(db_path) as conn:
        deleted = delete_target_validations(conn, match_ids)
        conn.commit()

    validation_result = _validate_predictions(str(db_path), dates)
    settle_result = LotteryAutoGapRunner(str(db_path), str(db_path.parent / "oddsfe_merged.db")).settle_reanalysis_changes(
        date_from if date_from else (dates[0] if dates else None),
        date_to if date_to else (dates[-1] if dates else None),
    )

    with connect(db_path) as conn:
        after_rows = load_validations(conn, match_ids)
        after_stats = validation_stats(after_rows)
        after_reviews = 0
        if match_ids and table_exists(conn, "post_match_reviews"):
            after_reviews = conn.execute(
                f"SELECT COUNT(*) FROM post_match_reviews WHERE match_key IN ({placeholders(match_ids)})",
                list(match_ids),
            ).fetchone()[0]

    summary.update(
        {
            "backup_path": str(backup_path) if backup_path else None,
            "deleted": deleted,
            "validation_result": validation_result,
            "reanalysis_change_settlement": settle_result,
            "counts_after": {
                "validations": len(after_rows),
                "reviews": after_reviews,
            },
            "stats_after": after_stats,
        }
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run/apply lottery validation rebuild")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to football_v2.db")
    parser.add_argument("--from", dest="date_from", default=None, help="Start Beijing date YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", default=None, help="End Beijing date YYYY-MM-DD")
    parser.add_argument("--apply", action="store_true", help="Delete and rebuild target validations")
    parser.add_argument("--backup", action="store_true", help="Copy the DB before --apply")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"database not found: {db_path}")
    summary = build_summary(db_path, args.date_from, args.date_to, args.apply, args.backup)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
