"""Retire duplicate source ids that conflict with active lottery teams.

This script does not merge teams. It keeps the active lottery team's source id
as canonical for the current window and clears the same source id from other
team rows. It is useful when youth/club/import placeholder rows accidentally
carry a senior national team's oddsfe id.

Dry-run by default.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_DB = ROOT / "data" / "football_v2.db"
DEFAULT_SOURCE_COLUMNS = ("oddsfe_team_id",)


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}


def active_lottery_team_ids(
    conn: sqlite3.Connection,
    *,
    date_from: str,
    date_to: str,
    league: str,
) -> set[int]:
    rows = conn.execute(
        """
        SELECT home_team_id, away_team_id
        FROM lottery_matches
        WHERE substr(COALESCE(beijing_time, match_date), 1, 10) BETWEEN ? AND ?
          AND COALESCE(league_name_cn, '') = ?
        """,
        (date_from, date_to, league),
    ).fetchall()
    values: set[int] = set()
    for row in rows:
        for column in ("home_team_id", "away_team_id"):
            value = row[column]
            if value is not None:
                values.add(int(value))
    return values


def row_label(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "team_id": row["team_id"],
        "name_cn": row["name_cn"],
        "name_en": row["name_en"],
        "team_type": row["team_type"],
        "country": row["country"],
    }


def plan_column(
    conn: sqlite3.Connection,
    *,
    source_column: str,
    active_ids: set[int],
) -> List[Dict[str, Any]]:
    if not active_ids:
        return []
    placeholders = ",".join("?" for _ in active_ids)
    active_rows = conn.execute(
        f"""
        SELECT team_id, name_cn, name_en, team_type, country, {source_column} AS source_id
        FROM teams
        WHERE team_id IN ({placeholders})
          AND {source_column} IS NOT NULL
          AND {source_column} != ''
        ORDER BY team_id
        """,
        sorted(active_ids),
    ).fetchall()

    by_source: Dict[str, List[sqlite3.Row]] = {}
    for row in active_rows:
        by_source.setdefault(str(row["source_id"]).strip(), []).append(row)

    plans: List[Dict[str, Any]] = []
    for source_id, owners in sorted(by_source.items()):
        owner_ids = {int(row["team_id"]) for row in owners}
        if len(owner_ids) != 1:
            plans.append(
                {
                    "source_column": source_column,
                    "source_id": source_id,
                    "skipped": True,
                    "reason": "multiple_active_owners",
                    "active_owners": [row_label(row) for row in owners],
                }
            )
            continue

        all_rows = conn.execute(
            f"""
            SELECT team_id, name_cn, name_en, team_type, country, {source_column} AS source_id
            FROM teams
            WHERE CAST({source_column} AS TEXT) = ?
            ORDER BY team_id
            """,
            (source_id,),
        ).fetchall()
        duplicate_rows = [row for row in all_rows if int(row["team_id"]) not in owner_ids]
        if not duplicate_rows:
            continue
        plans.append(
            {
                "source_column": source_column,
                "source_id": source_id,
                "active_owner": row_label(owners[0]),
                "retire_rows": [row_label(row) for row in duplicate_rows],
                "retire_count": len(duplicate_rows),
            }
        )
    return plans


def apply_plans(conn: sqlite3.Connection, plans: Iterable[Dict[str, Any]]) -> int:
    changed = 0
    for plan in plans:
        if plan.get("skipped"):
            continue
        source_column = str(plan["source_column"])
        for row in plan.get("retire_rows") or []:
            cur = conn.execute(
                f"UPDATE teams SET {source_column} = NULL, updated_at = CURRENT_TIMESTAMP WHERE team_id = ?",
                (row["team_id"],),
            )
            changed += cur.rowcount
    return changed


def run(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    source_columns = tuple(
        item.strip()
        for item in str(args.source_columns or "").split(",")
        if item.strip()
    ) or DEFAULT_SOURCE_COLUMNS
    league = args.league.encode("utf-8").decode("unicode_escape") if "\\u" in args.league else args.league

    summary: Dict[str, Any] = {
        "success": True,
        "dry_run": not args.apply,
        "db": str(db_path),
        "date_from": args.date_from,
        "date_to": args.date_to,
        "league": league,
        "source_columns": list(source_columns),
        "active_team_count": 0,
        "plans": [],
        "retire_rows_planned": 0,
        "rows_changed": 0,
    }

    with connect(db_path) as conn:
        available = table_columns(conn, "teams")
        invalid = [column for column in source_columns if column not in available]
        if invalid:
            summary["success"] = False
            summary["error"] = f"Unknown teams columns: {', '.join(invalid)}"
            return summary

        active_ids = active_lottery_team_ids(
            conn,
            date_from=args.date_from,
            date_to=args.date_to,
            league=league,
        )
        summary["active_team_count"] = len(active_ids)
        plans: List[Dict[str, Any]] = []
        for column in source_columns:
            plans.extend(plan_column(conn, source_column=column, active_ids=active_ids))
        summary["plans"] = plans
        summary["retire_rows_planned"] = sum(int(plan.get("retire_count") or 0) for plan in plans)
        if args.apply:
            summary["rows_changed"] = apply_plans(conn, plans)
            conn.commit()
    return summary


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--league", default="\\u4e16\\u754c\\u676f")
    parser.add_argument("--source-columns", default=",".join(DEFAULT_SOURCE_COLUMNS))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
