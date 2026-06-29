"""Mark stale collection_runs rows that were left in running state.

Default mode is dry-run. Use --apply to update rows. This never deletes run
history; it only closes clearly stale runs so dashboards and operators do not
mistake old crashed jobs for active collection.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "football_v2.db"


def parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("T", " ").split(".")[0]
    for fmt, width in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16)):
        try:
            return datetime.strptime(text[:width], fmt)
        except ValueError:
            continue
    return None


def load_running(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT run_id, trigger_source, run_type, match_date, status,
               started_at, finished_at, summary_json, error
        FROM collection_runs
        WHERE status = 'running'
        ORDER BY started_at
        """
    ).fetchall()
    return [dict(row) for row in rows]


def stale_rows(
    conn: sqlite3.Connection,
    *,
    older_than_hours: Optional[int] = None,
    older_than_minutes: Optional[int] = None,
    run_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    # collection_runs timestamps come from SQLite CURRENT_TIMESTAMP (UTC).
    now = datetime.utcnow()
    if older_than_minutes is not None:
        cutoff = now - timedelta(minutes=older_than_minutes)
        age_label = f"{older_than_minutes} minutes"
    else:
        older_than_hours = 6 if older_than_hours is None else older_than_hours
        cutoff = now - timedelta(hours=older_than_hours)
        age_label = f"{older_than_hours} hours"
    wanted_types = {item.strip() for item in (run_types or []) if item.strip()}
    stale: List[Dict[str, Any]] = []
    for row in load_running(conn):
        if wanted_types and str(row.get("run_type") or "") not in wanted_types:
            continue
        started_at = parse_dt(row.get("started_at"))
        if started_at and started_at <= cutoff:
            row["age_hours"] = round((now - started_at).total_seconds() / 3600, 2)
            row["stale_age_label"] = age_label
            stale.append(row)
    return stale


def mark_stale(conn: sqlite3.Connection, rows: List[Dict[str, Any]], age_label: str) -> int:
    updated = 0
    for row in rows:
        try:
            summary = json.loads(row.get("summary_json") or "{}")
            if not isinstance(summary, dict):
                summary = {"previous_summary": summary}
        except json.JSONDecodeError:
            summary = {"previous_summary_json": row.get("summary_json")}
        summary["stale_marked_at"] = datetime.now().isoformat(timespec="seconds")
        summary["stale_reason"] = f"running longer than {age_label}"

        cur = conn.execute(
            """
            UPDATE collection_runs
            SET status = 'stale_failed',
                finished_at = CURRENT_TIMESTAMP,
                summary_json = ?,
                error = ?
            WHERE run_id = ?
              AND status = 'running'
            """,
            (
                json.dumps(summary, ensure_ascii=False, sort_keys=True),
                f"Marked stale locally after running longer than {age_label}",
                row["run_id"],
            ),
        )
        updated += cur.rowcount
    conn.commit()
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run/apply stale collection run cleanup")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to football_v2.db")
    parser.add_argument("--older-than-hours", type=int, default=6, help="Only close runs older than this many hours")
    parser.add_argument("--older-than-minutes", type=int, help="Only close runs older than this many minutes")
    parser.add_argument("--run-type", action="append", default=[], help="Restrict to a run_type. Can be repeated.")
    parser.add_argument("--apply", action="store_true", help="Apply updates. Default is dry-run only.")
    args = parser.parse_args()

    db_path = Path(args.db)
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.execute("PRAGMA busy_timeout=120000")
    try:
        rows = stale_rows(
            conn,
            older_than_hours=args.older_than_hours,
            older_than_minutes=args.older_than_minutes,
            run_types=args.run_type,
        )
        age_label = rows[0].get("stale_age_label") if rows else (
            f"{args.older_than_minutes} minutes" if args.older_than_minutes is not None else f"{args.older_than_hours} hours"
        )
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"[{mode}] database: {db_path}")
        if args.run_type:
            print(f"run_type filter: {', '.join(args.run_type)}")
        print(f"stale running rows: {len(rows)}")
        for row in rows:
            print(f"- {row['run_id']} {row['run_type']} {row['match_date']} age={row['age_hours']}h")

        if args.apply and rows:
            updated = mark_stale(conn, rows, str(age_label))
            print(f"updated: {updated}")
        elif not args.apply:
            print("Dry-run only. Re-run with --apply to mark stale_failed.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
