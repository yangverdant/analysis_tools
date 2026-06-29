"""Safely merge a local data delta SQLite database into football_v2.db.

This is intentionally conservative:
- never drops cloud rows;
- never overwrites match results with local values unless the cloud field is NULL;
- inserts local analysis reports only when the cloud has no active report or the
  local active report is newer;
- marks older active reports stale after import;
- creates a compact backup of affected cloud tables before applying changes.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


AFFECTED_TABLES = [
    "lottery_matches",
    "lottery_odds",
    "lottery_results",
    "lottery_analysis_reports",
    "lottery_validation",
    "intelligence_jobs",
    "intelligence_packages",
    "match_context_snapshots",
    "match_feature_snapshots",
    "post_match_reviews",
]

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def default_backup_dir() -> Path:
    backup_root = Path(os.environ.get("FOOTBALL_BACKUP_DIR", PROJECT_ROOT.parent / "football_backups"))
    return backup_root / "data_delta_imports"


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> List[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def table_sql(conn: sqlite3.Connection, table: str) -> Optional[str]:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row[0] if row and row[0] else None


def rows(conn: sqlite3.Connection, table: str) -> Iterable[sqlite3.Row]:
    return conn.execute(f"SELECT * FROM {table}")


def insert_row(
    conn: sqlite3.Connection,
    table: str,
    row: sqlite3.Row,
    cols: Sequence[str],
    omit: Sequence[str] = (),
) -> int:
    usable = [col for col in cols if col not in omit]
    placeholders = ",".join("?" for _ in usable)
    values = [row[col] for col in usable]
    cur = conn.execute(
        f"INSERT OR IGNORE INTO {table} ({','.join(usable)}) VALUES ({placeholders})",
        values,
    )
    return int(cur.rowcount or 0)


def update_row(
    conn: sqlite3.Connection,
    table: str,
    row: sqlite3.Row,
    cols: Sequence[str],
    key_col: str,
    omit: Sequence[str] = (),
) -> int:
    usable = [col for col in cols if col != key_col and col not in omit]
    if not usable:
        return 0
    assignments = ",".join(f"{col}=?" for col in usable)
    values = [row[col] for col in usable] + [row[key_col]]
    cur = conn.execute(
        f"UPDATE {table} SET {assignments} WHERE {key_col}=?",
        values,
    )
    return int(cur.rowcount or 0)


def newer(left: Any, right: Any) -> bool:
    if not left:
        return False
    if not right:
        return True
    return str(left) > str(right)


def make_backup(target: sqlite3.Connection, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"data_delta_before_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup = sqlite3.connect(str(backup_path))
    try:
        for table in AFFECTED_TABLES:
            if not table_exists(target, table):
                continue
            sql = table_sql(target, table)
            if not sql:
                continue
            backup.execute(sql)
            cols = columns(target, table)
            placeholders = ",".join("?" for _ in cols)
            data = [tuple(row[col] for col in cols) for row in rows(target, table)]
            if data:
                backup.executemany(
                    f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
                    data,
                )
        backup.commit()
    finally:
        backup.close()
    return backup_path


def merge_lottery_matches(target: sqlite3.Connection, delta: sqlite3.Connection) -> Dict[str, int]:
    table = "lottery_matches"
    if not table_exists(delta, table) or not table_exists(target, table):
        return {"inserted": 0, "updated": 0}
    cols = [col for col in columns(delta, table) if col in columns(target, table)]
    inserted = updated = 0
    for row in rows(delta, table):
        current = target.execute(
            "SELECT updated_at FROM lottery_matches WHERE lottery_match_id=?",
            (row["lottery_match_id"],),
        ).fetchone()
        if not current:
            inserted += insert_row(target, table, row, cols)
        elif newer(row["updated_at"] if "updated_at" in row.keys() else None, current["updated_at"]):
            updated += update_row(target, table, row, cols, "lottery_match_id")
    return {"inserted": inserted, "updated": updated}


def merge_lottery_odds(target: sqlite3.Connection, delta: sqlite3.Connection) -> Dict[str, int]:
    table = "lottery_odds"
    if not table_exists(delta, table) or not table_exists(target, table):
        return {"inserted": 0, "updated": 0}
    cols = [col for col in columns(delta, table) if col in columns(target, table)]
    inserted = updated = 0
    for row in rows(delta, table):
        key = (row["lottery_match_id"], row["play_type"], row["snapshot_type"])
        current = target.execute(
            """
            SELECT odds_id, update_time FROM lottery_odds
            WHERE lottery_match_id=? AND play_type=? AND snapshot_type=?
            """,
            key,
        ).fetchone()
        if not current:
            inserted += insert_row(target, table, row, cols, omit=("odds_id",))
        elif newer(row["update_time"] if "update_time" in row.keys() else None, current["update_time"]):
            usable = [col for col in cols if col not in {"odds_id", "lottery_match_id", "play_type", "snapshot_type"}]
            if usable:
                assignments = ",".join(f"{col}=?" for col in usable)
                values = [row[col] for col in usable] + list(key)
                cur = target.execute(
                    f"""
                    UPDATE lottery_odds
                    SET {assignments}
                    WHERE lottery_match_id=? AND play_type=? AND snapshot_type=?
                    """,
                    values,
                )
                updated += int(cur.rowcount or 0)
    return {"inserted": inserted, "updated": updated}


def merge_lottery_results(target: sqlite3.Connection, delta: sqlite3.Connection) -> Dict[str, int]:
    table = "lottery_results"
    if not table_exists(delta, table) or not table_exists(target, table):
        return {"inserted": 0, "updated": 0}
    cols = [col for col in columns(delta, table) if col in columns(target, table)]
    inserted = updated = 0
    fill_cols = [
        col for col in cols
        if col not in {"result_id", "lottery_match_id", "match_id", "created_at"}
    ]
    for row in rows(delta, table):
        current = target.execute(
            "SELECT * FROM lottery_results WHERE lottery_match_id=?",
            (row["lottery_match_id"],),
        ).fetchone()
        if not current:
            inserted += insert_row(target, table, row, cols, omit=("result_id",))
            continue
        assignments: List[str] = []
        values: List[Any] = []
        for col in fill_cols:
            if current[col] is None and row[col] is not None:
                assignments.append(f"{col}=?")
                values.append(row[col])
        if assignments:
            values.append(row["lottery_match_id"])
            cur = target.execute(
                f"UPDATE lottery_results SET {','.join(assignments)} WHERE lottery_match_id=?",
                values,
            )
            updated += int(cur.rowcount or 0)
    return {"inserted": inserted, "updated": updated}


def mark_duplicate_reports_stale(target: sqlite3.Connection) -> int:
    if not table_exists(target, "lottery_analysis_reports"):
        return 0
    report_cols = columns(target, "lottery_analysis_reports")
    if "is_stale" not in report_cols:
        return 0
    rows_ = target.execute(
        """
        SELECT report_id, lottery_match_id
        FROM lottery_analysis_reports
        WHERE report_type IN ('prediction', 'full')
        ORDER BY lottery_match_id, datetime(created_at) DESC, report_id DESC
        """
    ).fetchall()
    seen = set()
    stale_ids: List[int] = []
    keep_ids: List[int] = []
    for row in rows_:
        match_key = row["lottery_match_id"]
        if match_key in seen:
            stale_ids.append(int(row["report_id"]))
        else:
            seen.add(match_key)
            keep_ids.append(int(row["report_id"]))
    updated = 0
    if stale_ids:
        placeholders = ",".join("?" for _ in stale_ids)
        updated += int(target.execute(
            f"UPDATE lottery_analysis_reports SET is_stale=1 WHERE report_id IN ({placeholders})",
            stale_ids,
        ).rowcount or 0)
    if keep_ids:
        placeholders = ",".join("?" for _ in keep_ids)
        target.execute(
            f"UPDATE lottery_analysis_reports SET is_stale=0 WHERE report_id IN ({placeholders})",
            keep_ids,
        )
    return updated


def merge_analysis_reports(target: sqlite3.Connection, delta: sqlite3.Connection) -> Dict[str, int]:
    table = "lottery_analysis_reports"
    if not table_exists(delta, table) or not table_exists(target, table):
        return {"inserted": 0, "stale_marked": 0}
    cols = [col for col in columns(delta, table) if col in columns(target, table)]
    inserted = 0
    for row in rows(delta, table):
        current = target.execute(
            """
            SELECT MAX(created_at) AS latest
            FROM lottery_analysis_reports
            WHERE lottery_match_id=? AND report_type=? AND COALESCE(is_stale,0)=0
            """,
            (row["lottery_match_id"], row["report_type"]),
        ).fetchone()
        if current and current["latest"] and not newer(row["created_at"], current["latest"]):
            continue
        inserted += insert_row(target, table, row, cols, omit=("report_id",))
    stale_marked = mark_duplicate_reports_stale(target)
    return {"inserted": inserted, "stale_marked": stale_marked}


def merge_validation(target: sqlite3.Connection, delta: sqlite3.Connection) -> Dict[str, int]:
    table = "lottery_validation"
    if not table_exists(delta, table) or not table_exists(target, table):
        return {"inserted": 0}
    cols = [col for col in columns(delta, table) if col in columns(target, table)]
    inserted = 0
    for row in rows(delta, table):
        exists = target.execute(
            """
            SELECT 1 FROM lottery_validation
            WHERE lottery_match_id=? AND play_type=?
            LIMIT 1
            """,
            (row["lottery_match_id"], row["play_type"]),
        ).fetchone()
        if not exists:
            inserted += insert_row(target, table, row, cols, omit=("validation_id",))
    return {"inserted": inserted}


def merge_intelligence(target: sqlite3.Connection, delta: sqlite3.Connection) -> Dict[str, int]:
    jobs_inserted = packages_inserted = 0
    if table_exists(delta, "intelligence_jobs") and table_exists(target, "intelligence_jobs"):
        cols = [col for col in columns(delta, "intelligence_jobs") if col in columns(target, "intelligence_jobs")]
        for row in rows(delta, "intelligence_jobs"):
            exists = target.execute(
                """
                SELECT 1 FROM intelligence_jobs
                WHERE job_id=?
                   OR (lottery_match_id IS NOT NULL AND lottery_match_id=?)
                LIMIT 1
                """,
                (row["job_id"], row["lottery_match_id"]),
            ).fetchone()
            if not exists:
                jobs_inserted += insert_row(target, "intelligence_jobs", row, cols)
    if table_exists(delta, "intelligence_packages") and table_exists(target, "intelligence_packages"):
        cols = [col for col in columns(delta, "intelligence_packages") if col in columns(target, "intelligence_packages")]
        for row in rows(delta, "intelligence_packages"):
            job_exists = target.execute("SELECT 1 FROM intelligence_jobs WHERE job_id=?", (row["job_id"],)).fetchone()
            package_exists = target.execute("SELECT 1 FROM intelligence_packages WHERE job_id=?", (row["job_id"],)).fetchone()
            if job_exists and not package_exists:
                packages_inserted += insert_row(target, "intelligence_packages", row, cols)
    return {"jobs_inserted": jobs_inserted, "packages_inserted": packages_inserted}


def merge_by_primary_key(target: sqlite3.Connection, delta: sqlite3.Connection, table: str, pk: str) -> int:
    if not table_exists(delta, table) or not table_exists(target, table):
        return 0
    cols = [col for col in columns(delta, table) if col in columns(target, table)]
    inserted = 0
    for row in rows(delta, table):
        exists = target.execute(f"SELECT 1 FROM {table} WHERE {pk}=?", (row[pk],)).fetchone()
        if not exists:
            inserted += insert_row(target, table, row, cols)
    return inserted


def merge_reviews(target: sqlite3.Connection, delta: sqlite3.Connection) -> Dict[str, int]:
    table = "post_match_reviews"
    if not table_exists(delta, table) or not table_exists(target, table):
        return {"inserted": 0}
    cols = [col for col in columns(delta, table) if col in columns(target, table)]
    inserted = 0
    for row in rows(delta, table):
        exists = target.execute(
            "SELECT 1 FROM post_match_reviews WHERE match_key=? AND play_type=? LIMIT 1",
            (row["match_key"], row["play_type"]),
        ).fetchone()
        if not exists:
            inserted += insert_row(target, table, row, cols)
    return {"inserted": inserted}


def run_import(db_path: Path, delta_path: Path, backup_dir: Path, apply: bool) -> Dict[str, Any]:
    target = connect(db_path)
    delta = connect(delta_path)
    try:
        result: Dict[str, Any] = {"apply": apply, "backup": None, "steps": {}}
        if apply:
            result["backup"] = str(make_backup(target, backup_dir))

        if apply:
            result["steps"]["lottery_matches"] = merge_lottery_matches(target, delta)
            result["steps"]["lottery_odds"] = merge_lottery_odds(target, delta)
            result["steps"]["lottery_results"] = merge_lottery_results(target, delta)
            result["steps"]["analysis_reports"] = merge_analysis_reports(target, delta)
            result["steps"]["validation"] = merge_validation(target, delta)
            result["steps"]["intelligence"] = merge_intelligence(target, delta)
            result["steps"]["context_snapshots"] = {
                "inserted": merge_by_primary_key(target, delta, "match_context_snapshots", "snapshot_id")
            }
            result["steps"]["feature_snapshots"] = {
                "inserted": merge_by_primary_key(target, delta, "match_feature_snapshots", "snapshot_id")
            }
            result["steps"]["post_match_reviews"] = merge_reviews(target, delta)
            target.commit()
        else:
            for table in AFFECTED_TABLES:
                result["steps"][table] = {
                    "delta_rows": delta.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    if table_exists(delta, table)
                    else 0,
                    "target_rows": target.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    if table_exists(target, table)
                    else 0,
                }
        return result
    finally:
        delta.close()
        target.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely import local data delta into cloud DB")
    parser.add_argument("--db", required=True, help="Target football_v2.db")
    parser.add_argument("--delta", required=True, help="Delta SQLite DB exported from local")
    parser.add_argument("--backup-dir", default=str(default_backup_dir()), help="Backup directory")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")
    args = parser.parse_args()
    result = run_import(Path(args.db), Path(args.delta), Path(args.backup_dir), args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
