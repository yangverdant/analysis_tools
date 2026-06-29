"""Mark older lottery analysis reports as stale without deleting history.

The active report for each match is the newest prediction/full row by
created_at, then report_id. Older rows remain in the database with is_stale=1
so audit trails, snapshots, reviews, and learning references can still resolve
their original source.
"""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "football_v2.db"


def table_columns(conn: sqlite3.Connection, table: str) -> Set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def load_reports(conn: sqlite3.Connection, include_full: bool) -> Dict[str, List[Dict[str, Any]]]:
    report_types = ("prediction", "full") if include_full else ("prediction",)
    placeholders = ",".join("?" for _ in report_types)
    rows = conn.execute(
        f"""
        SELECT report_id, lottery_match_id, report_type, created_at, COALESCE(is_stale, 0) AS is_stale
        FROM lottery_analysis_reports
        WHERE report_type IN ({placeholders})
          AND lottery_match_id IS NOT NULL
        ORDER BY lottery_match_id, datetime(created_at) DESC, report_id DESC
        """,
        report_types,
    ).fetchall()
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["lottery_match_id"])].append(dict(row))
    return grouped


def plan_marks(grouped: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    keep_ids: List[int] = []
    stale_ids: List[int] = []
    active_duplicate_matches: List[Dict[str, Any]] = []

    for match_key, rows in grouped.items():
        if not rows:
            continue
        keep = rows[0]
        keep_ids.append(int(keep["report_id"]))
        older = rows[1:]
        stale_ids.extend(int(row["report_id"]) for row in older if int(row.get("is_stale") or 0) == 0)
        active_count = sum(1 for row in rows if int(row.get("is_stale") or 0) == 0)
        if active_count > 1:
            active_duplicate_matches.append({
                "lottery_match_id": match_key,
                "active_count": active_count,
                "keep_report_id": keep["report_id"],
                "latest_created_at": keep["created_at"],
            })

    return {
        "matches": len(grouped),
        "keep_ids": keep_ids,
        "stale_ids": stale_ids,
        "active_duplicate_matches": active_duplicate_matches,
    }


def apply_marks(conn: sqlite3.Connection, keep_ids: List[int], stale_ids: List[int]) -> Dict[str, int]:
    stale_updated = 0
    keep_updated = 0
    if stale_ids:
        placeholders = ",".join("?" for _ in stale_ids)
        cur = conn.execute(
            f"UPDATE lottery_analysis_reports SET is_stale = 1 WHERE report_id IN ({placeholders})",
            stale_ids,
        )
        stale_updated = cur.rowcount
    if keep_ids:
        placeholders = ",".join("?" for _ in keep_ids)
        cur = conn.execute(
            f"UPDATE lottery_analysis_reports SET is_stale = 0 WHERE report_id IN ({placeholders})",
            keep_ids,
        )
        keep_updated = cur.rowcount
    conn.commit()
    return {"stale_updated": stale_updated, "keep_updated": keep_updated}


def mark_duplicate_reports_stale(db_path: Path, include_full: bool = True, apply: bool = False) -> Dict[str, Any]:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    try:
        cols = table_columns(conn, "lottery_analysis_reports")
        if "is_stale" not in cols:
            return {
                "success": True,
                "skipped": True,
                "reason": "lottery_analysis_reports.is_stale is not available",
            }

        grouped = load_reports(conn, include_full=include_full)
        plan = plan_marks(grouped)
        result: Dict[str, Any] = {
            "success": True,
            "apply": bool(apply),
            "include_full": bool(include_full),
            "matches_scanned": plan["matches"],
            "reports_kept_active": len(plan["keep_ids"]),
            "older_active_reports_to_mark_stale": len(plan["stale_ids"]),
            "matches_with_active_duplicates": len(plan["active_duplicate_matches"]),
            "active_duplicate_examples": plan["active_duplicate_matches"][:12],
        }
        if apply:
            result.update(apply_marks(conn, plan["keep_ids"], plan["stale_ids"]))
        return result
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run/apply stale marking for duplicate reports")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to football_v2.db")
    parser.add_argument("--apply", action="store_true", help="Apply updates. Default is dry-run only.")
    parser.add_argument("--prediction-only", action="store_true", help="Only consider prediction reports")
    args = parser.parse_args()

    result = mark_duplicate_reports_stale(
        Path(args.db),
        include_full=not args.prediction_only,
        apply=args.apply,
    )
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] database: {args.db}")
    if result.get("skipped"):
        print(f"skipped: {result.get('reason')}")
        return 0
    print(f"matches scanned: {result['matches_scanned']}")
    print(f"reports kept active: {result['reports_kept_active']}")
    print(f"older active reports to mark stale: {result['older_active_reports_to_mark_stale']}")
    print(f"matches with active duplicates: {result['matches_with_active_duplicates']}")
    for row in result["active_duplicate_examples"]:
        print(
            f"- {row['lottery_match_id']}: active={row['active_count']} "
            f"keep={row['keep_report_id']} latest={row['latest_created_at']}"
        )

    if args.apply:
        print(f"stale_updated: {result.get('stale_updated', 0)}")
        print(f"keep_updated: {result.get('keep_updated', 0)}")
    else:
        print("Dry-run only. Re-run with --apply to mark older reports stale.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
