"""Clean stale duplicate analysis reports and their linked snapshots.

This is intentionally conservative:
- active reports (is_stale=0) are never deleted
- classification/intel reports are ignored by default
- each match/report_type keeps the latest N stale versions plus the first stale
  version as a light audit trail
- linked foundation snapshots for deleted report_ids are removed together

Default mode is dry-run. Use --apply to delete and --backup to create a SQLite
backup outside the project directory.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "football_v2.db"


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def table_columns(conn: sqlite3.Connection, table_name: str) -> Set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def loads_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def db_stats(conn: sqlite3.Connection) -> Dict[str, int]:
    page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
    page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
    free_count = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
    return {
        "page_size": page_size,
        "page_count": page_count,
        "freelist_count": free_count,
        "file_bytes": page_size * page_count,
        "free_bytes": page_size * free_count,
    }


def backup_database(db_path: Path) -> Path:
    backup_root = Path(os.environ.get("FOOTBALL_BACKUP_DIR", PROJECT_ROOT.parent / "football_backups"))
    backup_dir = backup_root / "stale_report_cleanups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_before_stale_report_cleanup_{stamp}{db_path.suffix}"
    with sqlite3.connect(str(db_path), timeout=30) as source:
        with sqlite3.connect(str(backup_path), timeout=30) as target:
            source.backup(target)
    return backup_path


def parse_report_types(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_stale_reports(conn: sqlite3.Connection, report_types: Sequence[str]) -> List[sqlite3.Row]:
    placeholders = ",".join("?" for _ in report_types)
    return conn.execute(
        f"""
        SELECT report_id, lottery_match_id, match_id, report_type, created_at,
               COALESCE(is_stale, 0) AS is_stale
        FROM lottery_analysis_reports
        WHERE COALESCE(is_stale, 0) = 1
          AND report_type IN ({placeholders})
          AND COALESCE(lottery_match_id, match_id, '') <> ''
        ORDER BY COALESCE(lottery_match_id, match_id), report_type,
                 datetime(created_at) ASC, report_id ASC
        """,
        list(report_types),
    ).fetchall()


def select_delete_report_ids(rows: Sequence[sqlite3.Row], keep_stale_per_match: int) -> Set[int]:
    grouped: Dict[tuple[str, str], List[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        match_key = str(row["lottery_match_id"] or row["match_id"])
        grouped[(match_key, str(row["report_type"]))].append(row)

    keep: Set[int] = set()
    all_ids: Set[int] = set()
    for group_rows in grouped.values():
        ordered = sorted(group_rows, key=lambda row: (str(row["created_at"] or ""), int(row["report_id"])))
        all_ids.update(int(row["report_id"]) for row in ordered)
        if ordered:
            keep.add(int(ordered[0]["report_id"]))  # first stale audit point
        if keep_stale_per_match > 0:
            keep.update(int(row["report_id"]) for row in ordered[-keep_stale_per_match:])
    return all_ids - keep


def chunked(values: Sequence[int], size: int = 500) -> Iterable[Sequence[int]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def count_feature_snapshots(conn: sqlite3.Connection, report_ids: Set[int]) -> int:
    if not report_ids or not table_exists(conn, "match_feature_snapshots"):
        return 0
    total = 0
    for chunk in chunked(sorted(report_ids)):
        placeholders = ",".join("?" for _ in chunk)
        row = conn.execute(
            f"SELECT COUNT(*) FROM match_feature_snapshots WHERE source_report_id IN ({placeholders})",
            [str(item) for item in chunk],
        ).fetchone()
        total += int(row[0] or 0)
    return total


def context_snapshot_rowids(conn: sqlite3.Connection, report_ids: Set[int]) -> Set[int]:
    if not report_ids or not table_exists(conn, "match_context_snapshots"):
        return set()
    report_text = {str(item) for item in report_ids}
    rowids: Set[int] = set()
    for row in conn.execute("SELECT rowid, data_quality_json FROM match_context_snapshots"):
        quality = loads_json(row["data_quality_json"])
        if str(quality.get("source_report_id") or "") in report_text:
            rowids.add(int(row["rowid"]))
    return rowids


def delete_reports(conn: sqlite3.Connection, report_ids: Set[int]) -> int:
    deleted = 0
    for chunk in chunked(sorted(report_ids)):
        placeholders = ",".join("?" for _ in chunk)
        cursor = conn.execute(
            f"DELETE FROM lottery_analysis_reports WHERE report_id IN ({placeholders})",
            list(chunk),
        )
        deleted += cursor.rowcount if cursor.rowcount is not None else 0
    return deleted


def delete_feature_snapshots(conn: sqlite3.Connection, report_ids: Set[int]) -> int:
    deleted = 0
    for chunk in chunked(sorted(report_ids)):
        placeholders = ",".join("?" for _ in chunk)
        cursor = conn.execute(
            f"DELETE FROM match_feature_snapshots WHERE source_report_id IN ({placeholders})",
            [str(item) for item in chunk],
        )
        deleted += cursor.rowcount if cursor.rowcount is not None else 0
    return deleted


def delete_context_snapshots(conn: sqlite3.Connection, rowids: Set[int]) -> int:
    deleted = 0
    for chunk in chunked(sorted(rowids)):
        placeholders = ",".join("?" for _ in chunk)
        cursor = conn.execute(
            f"DELETE FROM match_context_snapshots WHERE rowid IN ({placeholders})",
            list(chunk),
        )
        deleted += cursor.rowcount if cursor.rowcount is not None else 0
    return deleted


def summarize_by_match(rows: Sequence[sqlite3.Row], delete_ids: Set[int], limit: int = 12) -> List[Dict[str, Any]]:
    counter: Counter = Counter()
    for row in rows:
        if int(row["report_id"]) in delete_ids:
            counter[str(row["lottery_match_id"] or row["match_id"])] += 1
    return [{"match_key": key, "delete_reports": int(count)} for key, count in counter.most_common(limit)]


def cleanup(
    db_path: Path,
    report_types: Sequence[str],
    keep_stale_per_match: int,
    apply: bool,
    backup: bool,
    vacuum: bool,
) -> Dict[str, Any]:
    with connect(db_path) as conn:
        required = ["lottery_analysis_reports"]
        missing = [table for table in required if not table_exists(conn, table)]
        if missing:
            raise RuntimeError(f"Missing tables: {', '.join(missing)}")
        cols = table_columns(conn, "lottery_analysis_reports")
        if "is_stale" not in cols:
            raise RuntimeError("lottery_analysis_reports.is_stale is required")

        before_db = db_stats(conn)
        rows = load_stale_reports(conn, report_types)
        delete_ids = select_delete_report_ids(rows, keep_stale_per_match)
        feature_count = count_feature_snapshots(conn, delete_ids)
        context_rowids = context_snapshot_rowids(conn, delete_ids)

    summary: Dict[str, Any] = {
        "db": str(db_path),
        "mode": "apply" if apply else "dry_run",
        "report_types": list(report_types),
        "keep_stale_per_match": keep_stale_per_match,
        "stale_reports_seen": len(rows),
        "delete_report_candidates": len(delete_ids),
        "delete_feature_snapshot_candidates": feature_count,
        "delete_context_snapshot_candidates": len(context_rowids),
        "top_matches": summarize_by_match(rows, delete_ids),
        "db_before": before_db,
    }

    if not apply:
        return summary

    if backup:
        summary["backup"] = str(backup_database(db_path))

    with connect(db_path) as conn:
        conn.execute("BEGIN")
        try:
            deleted_context = delete_context_snapshots(conn, context_rowids)
            deleted_feature = delete_feature_snapshots(conn, delete_ids)
            deleted_reports = delete_reports(conn, delete_ids)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        if vacuum:
            conn.execute("VACUUM")
        summary["deleted_context_snapshots"] = deleted_context
        summary["deleted_feature_snapshots"] = deleted_feature
        summary["deleted_reports"] = deleted_reports
        summary["db_after"] = db_stats(conn)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--report-types", default="prediction,full")
    parser.add_argument("--keep-stale-per-match", type=int, default=3)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--vacuum", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    result = cleanup(
        db_path=db_path,
        report_types=parse_report_types(args.report_types),
        keep_stale_per_match=max(args.keep_stale_per_match, 0),
        apply=args.apply,
        backup=args.backup,
        vacuum=args.vacuum,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
