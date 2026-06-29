"""Clean duplicated data-foundation snapshot rows.

The snapshot tables are consumed as "latest state" by the lottery cockpit and
similar-case builder. This script keeps the latest snapshot per
match/source_report_id pair, plus the latest snapshot per match, and removes
older rows created by repeated backfills or repeated analysis runs.

Default mode is dry-run. Use --apply to delete rows and --backup to create a
SQLite backup first.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "football_v2.db"
NO_REPORT = "__no_report__"


SnapshotRow = Dict[str, Any]


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def clean_report_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "undefined", "nan"}:
        return None
    return text


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


def report_id_from_quality(value: Any) -> Optional[str]:
    quality = loads_json(value)
    return clean_report_id(quality.get("source_report_id"))


def row_sort_key(row: SnapshotRow) -> Tuple[str, int]:
    return (str(row.get("snapshot_time") or ""), int(row.get("rowid") or 0))


def is_newer(candidate: SnapshotRow, current: Optional[SnapshotRow]) -> bool:
    return current is None or row_sort_key(candidate) > row_sort_key(current)


def load_context_rows(conn: sqlite3.Connection) -> List[SnapshotRow]:
    rows = conn.execute(
        """
        SELECT rowid, snapshot_id, match_key, snapshot_time, data_quality_json
        FROM match_context_snapshots
        """
    ).fetchall()
    result: List[SnapshotRow] = []
    for row in rows:
        item = dict(row)
        item["source_report_id"] = report_id_from_quality(item.get("data_quality_json"))
        result.append(item)
    return result


def load_feature_rows(conn: sqlite3.Connection) -> List[SnapshotRow]:
    rows = conn.execute(
        """
        SELECT rowid, snapshot_id, match_key, snapshot_time, source_report_id
        FROM match_feature_snapshots
        """
    ).fetchall()
    result: List[SnapshotRow] = []
    for row in rows:
        item = dict(row)
        item["source_report_id"] = clean_report_id(item.get("source_report_id"))
        result.append(item)
    return result


def latest_by_key(rows: Sequence[SnapshotRow], key_fields: Sequence[str]) -> Dict[Tuple[Any, ...], SnapshotRow]:
    latest: Dict[Tuple[Any, ...], SnapshotRow] = {}
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        if is_newer(row, latest.get(key)):
            latest[key] = row
    return latest


def select_keep_rowids(rows: Sequence[SnapshotRow], max_per_match: int = 0) -> Set[int]:
    keep: Set[int] = set()
    latest_per_match = latest_by_key(rows, ["match_key"])
    latest_per_report = latest_by_key(rows, ["match_key", "source_report_id"])

    for row in latest_per_match.values():
        keep.add(int(row["rowid"]))
    for row in latest_per_report.values():
        keep.add(int(row["rowid"]))

    if max_per_match and max_per_match > 0:
        by_match: Dict[str, List[SnapshotRow]] = {}
        rows_by_id = {int(row["rowid"]): row for row in rows}
        for rowid in keep:
            row = rows_by_id[rowid]
            by_match.setdefault(str(row.get("match_key")), []).append(row)

        capped_keep: Set[int] = set()
        for match_key, match_rows in by_match.items():
            ordered = sorted(match_rows, key=row_sort_key, reverse=True)
            capped_keep.update(int(row["rowid"]) for row in ordered[:max_per_match])
            latest = latest_per_match.get((match_key,))
            if latest:
                capped_keep.add(int(latest["rowid"]))
        keep = capped_keep

    return keep


def count_by_match(rows: Iterable[SnapshotRow], rowids: Optional[Set[int]] = None) -> Counter:
    counter: Counter = Counter()
    for row in rows:
        if rowids is not None and int(row["rowid"]) not in rowids:
            continue
        counter[str(row.get("match_key"))] += 1
    return counter


def top_counts(counter: Counter, limit: int = 8) -> List[Tuple[str, int]]:
    return [(str(match_key), int(count)) for match_key, count in counter.most_common(limit)]


def analyze_table(rows: Sequence[SnapshotRow], max_per_match: int) -> Dict[str, Any]:
    keep = select_keep_rowids(rows, max_per_match=max_per_match)
    all_rowids = {int(row["rowid"]) for row in rows}
    delete = all_rowids - keep
    report_rows = [row for row in rows if row.get("source_report_id")]
    no_report_rows = [row for row in rows if not row.get("source_report_id")]
    return {
        "rows": len(rows),
        "matches": len({row.get("match_key") for row in rows}),
        "report_rows": len(report_rows),
        "no_report_rows": len(no_report_rows),
        "report_groups": len({(row.get("match_key"), row.get("source_report_id") or NO_REPORT) for row in rows}),
        "keep_rowids": keep,
        "delete_rowids": delete,
        "delete_count": len(delete),
        "keep_count": len(keep),
        "top_before": top_counts(count_by_match(rows)),
        "top_after": top_counts(count_by_match(rows, keep)),
    }


def print_table_report(table_name: str, stats: Dict[str, Any]) -> None:
    print(f"\n[{table_name}]")
    print(f"rows_before       : {stats['rows']}")
    print(f"matches           : {stats['matches']}")
    print(f"source_report_rows: {stats['report_rows']}")
    print(f"no_report_rows    : {stats['no_report_rows']}")
    print(f"report_groups     : {stats['report_groups']}")
    print(f"keep_rows         : {stats['keep_count']}")
    print(f"delete_candidates : {stats['delete_count']}")
    print("top_before        : " + ", ".join(f"{k}={v}" for k, v in stats["top_before"]))
    print("top_after         : " + ", ".join(f"{k}={v}" for k, v in stats["top_after"]))


def chunked(values: Sequence[int], size: int = 500) -> Iterable[Sequence[int]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def delete_rowids(conn: sqlite3.Connection, table_name: str, rowids: Set[int]) -> int:
    ordered = sorted(rowids)
    deleted = 0
    for chunk in chunked(ordered):
        placeholders = ",".join("?" for _ in chunk)
        cursor = conn.execute(f"DELETE FROM {table_name} WHERE rowid IN ({placeholders})", list(chunk))
        deleted += cursor.rowcount if cursor.rowcount is not None else 0
    return deleted


def db_stats(conn: sqlite3.Connection) -> Dict[str, int]:
    page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
    page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
    freelist_count = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
    return {
        "page_size": page_size,
        "page_count": page_count,
        "freelist_count": freelist_count,
        "file_bytes": page_size * page_count,
        "free_bytes": page_size * freelist_count,
    }


def backup_database(db_path: Path) -> Path:
    backup_root = Path(os.environ.get("FOOTBALL_BACKUP_DIR", PROJECT_ROOT.parent / "football_backups"))
    backup_dir = backup_root / "snapshot_cleanups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_before_snapshot_cleanup_{stamp}{db_path.suffix}"
    with sqlite3.connect(str(db_path), timeout=30) as source:
        with sqlite3.connect(str(backup_path), timeout=30) as target:
            source.backup(target)
    return backup_path


def compact_table_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "rows_before": stats["rows"],
        "matches": stats["matches"],
        "source_report_rows": stats["report_rows"],
        "no_report_rows": stats["no_report_rows"],
        "report_groups": stats["report_groups"],
        "keep_rows": stats["keep_count"],
        "delete_candidates": stats["delete_count"],
        "top_before": stats["top_before"],
        "top_after": stats["top_after"],
    }


def cleanup_snapshots(
    db_path: Path,
    max_per_match: int = 0,
    apply: bool = False,
    backup: bool = False,
    vacuum: bool = False,
) -> Dict[str, Any]:
    db_path = Path(db_path).resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    with connect(db_path) as conn:
        missing = [
            table_name
            for table_name in ("match_context_snapshots", "match_feature_snapshots")
            if not table_exists(conn, table_name)
        ]
        if missing:
            raise RuntimeError(f"Missing tables: {', '.join(missing)}")

        before_db = db_stats(conn)
        table_rows = {
            "match_context_snapshots": load_context_rows(conn),
            "match_feature_snapshots": load_feature_rows(conn),
        }
        analyses = {
            table_name: analyze_table(rows, max_per_match=max_per_match)
            for table_name, rows in table_rows.items()
        }

    summary: Dict[str, Any] = {
        "db": str(db_path),
        "apply": bool(apply),
        "max_per_match": max_per_match,
        "db_before": before_db,
        "tables": {table_name: compact_table_stats(stats) for table_name, stats in analyses.items()},
        "total_delete_candidates": sum(stats["delete_count"] for stats in analyses.values()),
    }

    if not apply:
        return summary

    if backup:
        summary["backup"] = str(backup_database(db_path))

    with connect(db_path) as conn:
        conn.execute("BEGIN")
        try:
            deleted_total = 0
            deleted_by_table = {}
            for table_name, stats in analyses.items():
                deleted = delete_rowids(conn, table_name, stats["delete_rowids"])
                deleted_by_table[table_name] = deleted
                deleted_total += deleted
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        if vacuum:
            conn.execute("VACUUM")

        summary["deleted_total"] = deleted_total
        summary["deleted_by_table"] = deleted_by_table
        summary["db_after"] = db_stats(conn)
    return summary


def run(args: argparse.Namespace) -> int:
    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 2

    print(f"Database: {db_path}")
    print(f"Mode    : {'APPLY' if args.apply else 'DRY-RUN'}")
    if args.max_per_match:
        print(f"Cap     : keep latest {args.max_per_match} rows per match after report grouping")

    with connect(db_path) as conn:
        missing = [
            table_name
            for table_name in ("match_context_snapshots", "match_feature_snapshots")
            if not table_exists(conn, table_name)
        ]
        if missing:
            print(f"Missing tables: {', '.join(missing)}", file=sys.stderr)
            return 2

        before_db = db_stats(conn)
        print(
            "DB pages: "
            f"{before_db['page_count']} total, {before_db['freelist_count']} free "
            f"({before_db['free_bytes'] / 1024 / 1024:.1f} MB reusable)"
        )

        table_rows = {
            "match_context_snapshots": load_context_rows(conn),
            "match_feature_snapshots": load_feature_rows(conn),
        }
        analyses = {
            table_name: analyze_table(rows, max_per_match=args.max_per_match)
            for table_name, rows in table_rows.items()
        }

        for table_name, stats in analyses.items():
            print_table_report(table_name, stats)

        total_delete = sum(stats["delete_count"] for stats in analyses.values())
        print(f"\nTotal delete candidates: {total_delete}")

    if not args.apply:
        print("Dry-run only. Re-run with --apply to delete candidates.")
        return 0

    backup_path: Optional[Path] = None
    if args.backup:
        print("Creating SQLite backup before cleanup...")
        backup_path = backup_database(db_path)
        print(f"Backup: {backup_path}")

    with connect(db_path) as conn:
        conn.execute("BEGIN")
        try:
            deleted_total = 0
            for table_name, stats in analyses.items():
                deleted = delete_rowids(conn, table_name, stats["delete_rowids"])
                deleted_total += deleted
                print(f"Deleted from {table_name}: {deleted}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        if args.vacuum:
            print("Running VACUUM. This can take a while and needs free disk space.")
            conn.execute("VACUUM")

        after_db = db_stats(conn)
        print(
            "DB pages after: "
            f"{after_db['page_count']} total, {after_db['freelist_count']} free "
            f"({after_db['free_bytes'] / 1024 / 1024:.1f} MB reusable)"
        )

    print("Cleanup complete.")
    if backup_path:
        print(f"Backup kept at: {backup_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    parser.add_argument("--apply", action="store_true", help="Delete duplicate snapshot rows")
    parser.add_argument("--backup", action="store_true", help="Create a SQLite backup before --apply")
    parser.add_argument("--vacuum", action="store_true", help="Run VACUUM after delete")
    parser.add_argument(
        "--max-per-match",
        type=int,
        default=0,
        help="Optional aggressive cap after per-report dedupe; 0 keeps all report groups",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
