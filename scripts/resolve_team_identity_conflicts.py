"""Resolve duplicate team identity rows without deleting old team records.

The script merges references from duplicate team ids into a chosen canonical id,
updates source_entity_mappings to the canonical id, and copies missing external
ids from duplicates onto the canonical row. Duplicate rows are retained. When
requested, duplicate source ids that now match the canonical row are retired so
future source lookups do not return multiple teams.

Dry-run by default.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "data" / "football_v2.db"

SOURCE_ID_COLUMNS = [
    "sm_team_id",
    "fd_team_id",
    "tsdb_team_id",
    "sb_team_id",
    "sporttery_team_id",
    "oddsfe_team_id",
    "apifootball_team_id",
    "sporttery_name_cn",
    "sporttery_name_en",
    "oddsfe_name_cn",
    "oddsfe_name_en",
    "apifootball_name_cn",
    "apifootball_name_en",
    "name_cn_aliases",
    "country",
    "country_cn",
    "fifa_code",
    "logo_url",
]

SOURCE_IDENTITY_COLUMNS = [
    "sm_team_id",
    "fd_team_id",
    "tsdb_team_id",
    "sb_team_id",
    "sporttery_team_id",
    "oddsfe_team_id",
    "apifootball_team_id",
]

REFERENCE_COLUMNS = {
    "team_id",
    "home_team_id",
    "away_team_id",
    "opponent_team_id",
    "winner_team_id",
    "from_team_id",
    "to_team_id",
}

REFERENCE_TABLE_EXCLUDES = {
    "teams",
    "lottery_team_id_repairs",
}


def norm_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def clean(value: Any) -> str:
    return str(value or "").strip()


def is_empty(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def same_value(left: Any, right: Any) -> bool:
    if is_empty(left) or is_empty(right):
        return False
    return str(left).strip() == str(right).strip()


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    return [str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")]


def reference_targets(conn: sqlite3.Connection) -> List[Tuple[str, str]]:
    targets: List[Tuple[str, str]] = []
    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        table = str(row["name"])
        if table in REFERENCE_TABLE_EXCLUDES:
            continue
        for column in table_columns(conn, table):
            if column in REFERENCE_COLUMNS:
                targets.append((table, column))
    return targets


def usage_count(conn: sqlite3.Connection, team_id: int, table: str, column: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (team_id,)).fetchone()[0])
    except Exception:
        return 0


def team_usage(conn: sqlite3.Connection, team_id: int) -> Dict[str, int]:
    return {
        "lottery": usage_count(conn, team_id, "lottery_matches", "home_team_id")
        + usage_count(conn, team_id, "lottery_matches", "away_team_id"),
        "matches": usage_count(conn, team_id, "matches", "home_team_id")
        + usage_count(conn, team_id, "matches", "away_team_id"),
        "facts": usage_count(conn, team_id, "team_match_facts", "team_id")
        + usage_count(conn, team_id, "team_match_facts", "opponent_team_id"),
    }


def canonical_score(conn: sqlite3.Connection, row: sqlite3.Row) -> float:
    score = 0.0
    if clean(row["team_type"]).lower() == "national":
        score += 50
    if clean(row["country"]) and clean(row["country"]).lower() != "international":
        score += 20
    if clean(row["apifootball_team_id"]):
        score += 100
    if clean(row["fd_team_id"]):
        score += 12
    if clean(row["oddsfe_team_id"]):
        score += 8
    if clean(row["name_cn"]):
        score += 4
    uses = team_usage(conn, int(row["team_id"]))
    score += min(uses["lottery"], 5) * 3
    score += min(uses["matches"], 25) * 0.1
    score += min(uses["facts"], 50) * 0.02
    # Prefer rows that are already semantically clean over importer-created
    # "International club" placeholders.
    if clean(row["team_type"]).lower() == "club" and clean(row["country"]).lower() == "international":
        score -= 30
    return round(score, 3)


def same_cn_with_shared_source_id(team_rows: List[sqlite3.Row]) -> bool:
    cn_names = {clean(row["name_cn"]) for row in team_rows if clean(row["name_cn"])}
    if len(cn_names) != 1:
        return False
    for column in SOURCE_IDENTITY_COLUMNS:
        values: Dict[str, int] = {}
        for row in team_rows:
            value = clean(row[column]) if column in row.keys() else ""
            if value:
                values[value] = values.get(value, 0) + 1
        if any(count > 1 for count in values.values()):
            return True
    return False


def duplicate_fd_groups(conn: sqlite3.Connection, only_fd_ids: Optional[set[str]] = None) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    params: List[Any] = []
    where = "fd_team_id IS NOT NULL AND fd_team_id != ''"
    if only_fd_ids:
        where += f" AND CAST(fd_team_id AS TEXT) IN ({','.join('?' for _ in only_fd_ids)})"
        params.extend(sorted(only_fd_ids))
    rows = conn.execute(
        f"""
        SELECT CAST(fd_team_id AS TEXT) AS fd_team_id, COUNT(*) AS c
        FROM teams
        WHERE {where}
        GROUP BY CAST(fd_team_id AS TEXT)
        HAVING COUNT(*) > 1
        ORDER BY CAST(fd_team_id AS INTEGER)
        """,
        params,
    ).fetchall()
    for group_row in rows:
        team_rows = conn.execute(
            """
            SELECT *
            FROM teams
            WHERE CAST(fd_team_id AS TEXT) = ?
            ORDER BY team_id
            """,
            (str(group_row["fd_team_id"]),),
        ).fetchall()
        names = {norm_name(row["name_en"]) for row in team_rows if clean(row["name_en"])}
        name_compatibility = "same_normalized_name"
        # Stay conservative: allow normalized name differences only when the
        # local Chinese name and at least one source identity also agree.
        if len(names) > 1:
            if same_cn_with_shared_source_id(team_rows):
                name_compatibility = "same_cn_and_shared_source_id"
            else:
                groups.append(
                    {
                        "fd_team_id": str(group_row["fd_team_id"]),
                        "skipped": True,
                        "reason": "different_normalized_names",
                        "names": sorted(names),
                        "teams": [dict(row) for row in team_rows],
                    }
                )
                continue
        scored = [(canonical_score(conn, row), int(row["team_id"]), row) for row in team_rows]
        scored.sort(key=lambda item: (-item[0], item[1]))
        canonical = scored[0][2]
        duplicates = [row for _, _, row in scored[1:]]
        groups.append(
            {
                "fd_team_id": str(group_row["fd_team_id"]),
                "canonical_id": int(canonical["team_id"]),
                "canonical_score": scored[0][0],
                "duplicate_ids": [int(row["team_id"]) for row in duplicates],
                "name_compatibility": name_compatibility,
                "teams": [
                    {
                        "team_id": int(row["team_id"]),
                        "name_en": row["name_en"],
                        "name_cn": row["name_cn"],
                        "team_type": row["team_type"],
                        "country": row["country"],
                        "apifootball_team_id": row["apifootball_team_id"],
                        "oddsfe_team_id": row["oddsfe_team_id"],
                        "score": score,
                        "usage": team_usage(conn, int(row["team_id"])),
                    }
                    for score, _, row in scored
                ],
            }
        )
    return groups


def planned_reference_updates(
    conn: sqlite3.Connection,
    canonical_id: int,
    duplicate_ids: Iterable[int],
) -> List[Dict[str, Any]]:
    targets = reference_targets(conn)
    updates: List[Dict[str, Any]] = []
    for duplicate_id in duplicate_ids:
        for table, column in targets:
            count = usage_count(conn, duplicate_id, table, column)
            if count:
                updates.append(
                    {
                        "table": table,
                        "column": column,
                        "from_team_id": duplicate_id,
                        "to_team_id": canonical_id,
                        "rows": count,
                    }
                )
    return updates


def merge_missing_team_columns(
    conn: sqlite3.Connection,
    canonical_id: int,
    duplicate_ids: Iterable[int],
    apply: bool,
) -> List[Dict[str, Any]]:
    canonical = conn.execute("SELECT * FROM teams WHERE team_id = ?", (canonical_id,)).fetchone()
    if not canonical:
        return []
    updates: Dict[str, Any] = {}
    available = set(table_columns(conn, "teams"))
    for duplicate_id in duplicate_ids:
        duplicate = conn.execute("SELECT * FROM teams WHERE team_id = ?", (duplicate_id,)).fetchone()
        if not duplicate:
            continue
        for column in SOURCE_ID_COLUMNS:
            if column not in available:
                continue
            if is_empty(canonical[column]) and not is_empty(duplicate[column]):
                updates[column] = duplicate[column]
    changes = [{"column": column, "value": value} for column, value in sorted(updates.items())]
    if apply and updates:
        assignments = ", ".join(f"{column} = ?" for column in updates)
        params = list(updates.values()) + [canonical_id]
        conn.execute(f"UPDATE teams SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE team_id = ?", params)
    return changes


def retire_duplicate_source_ids(
    conn: sqlite3.Connection,
    canonical_id: int,
    duplicate_ids: Iterable[int],
    apply: bool,
) -> List[Dict[str, Any]]:
    available = set(table_columns(conn, "teams"))
    columns = [column for column in SOURCE_IDENTITY_COLUMNS if column in available]
    canonical = conn.execute("SELECT * FROM teams WHERE team_id = ?", (canonical_id,)).fetchone()
    if not canonical:
        return []
    changes: List[Dict[str, Any]] = []
    for duplicate_id in duplicate_ids:
        duplicate = conn.execute("SELECT * FROM teams WHERE team_id = ?", (duplicate_id,)).fetchone()
        if not duplicate:
            continue
        retire_columns = [
            column
            for column in columns
            if same_value(duplicate[column], canonical[column])
        ]
        if not retire_columns:
            continue
        for column in retire_columns:
            changes.append(
                {
                    "team_id": duplicate_id,
                    "column": column,
                    "retired_value": duplicate[column],
                }
            )
        if apply:
            assignments = ", ".join(f"{column} = NULL" for column in retire_columns)
            conn.execute(
                f"UPDATE teams SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE team_id = ?",
                (duplicate_id,),
            )
    return changes


def apply_reference_updates(
    conn: sqlite3.Connection,
    updates: Iterable[Dict[str, Any]],
    apply: bool,
) -> List[Dict[str, Any]]:
    applied: List[Dict[str, Any]] = []
    for item in updates:
        if apply:
            conn.execute(
                f"UPDATE OR IGNORE {item['table']} SET {item['column']} = ? WHERE {item['column']} = ?",
                (item["to_team_id"], item["from_team_id"]),
            )
        applied.append(dict(item))
    return applied


def apply_mapping_updates(
    conn: sqlite3.Connection,
    canonical_id: int,
    duplicate_ids: Iterable[int],
    apply: bool,
) -> List[Dict[str, Any]]:
    if "source_entity_mappings" not in {
        row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }:
        return []
    duplicate_text = [str(item) for item in duplicate_ids]
    if not duplicate_text:
        return []
    rows = conn.execute(
        f"""
        SELECT mapping_id, entity_type, source_name, source_entity_id, canonical_id
        FROM source_entity_mappings
        WHERE CAST(canonical_id AS TEXT) IN ({','.join('?' for _ in duplicate_text)})
        ORDER BY source_name, entity_type, source_entity_id
        """,
        duplicate_text,
    ).fetchall()
    changes = [dict(row) | {"new_canonical_id": str(canonical_id)} for row in rows]
    if apply and rows:
        conn.execute(
            f"""
            UPDATE source_entity_mappings
            SET canonical_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE CAST(canonical_id AS TEXT) IN ({','.join('?' for _ in duplicate_text)})
            """,
            [str(canonical_id), *duplicate_text],
        )
    return changes


def run(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    only = {item.strip() for item in (args.fd_team_ids or "").split(",") if item.strip()} or None
    summary: Dict[str, Any] = {
        "success": True,
        "dry_run": not args.apply,
        "db": str(db_path),
        "groups": [],
        "groups_considered": 0,
        "groups_planned": 0,
        "reference_rows_planned": 0,
        "mapping_rows_planned": 0,
        "team_column_updates_planned": 0,
        "duplicate_source_ids_retired_planned": 0,
    }
    with connect(db_path) as conn:
        groups = duplicate_fd_groups(conn, only_fd_ids=only)
        summary["groups_considered"] = len(groups)
        for group in groups:
            if group.get("skipped"):
                summary["groups"].append(group)
                continue
            canonical_id = int(group["canonical_id"])
            duplicate_ids = [int(item) for item in group["duplicate_ids"]]
            ref_updates = planned_reference_updates(conn, canonical_id, duplicate_ids)
            mapping_updates = apply_mapping_updates(conn, canonical_id, duplicate_ids, apply=args.apply)
            team_column_updates = merge_missing_team_columns(conn, canonical_id, duplicate_ids, apply=args.apply)
            retired_source_ids = retire_duplicate_source_ids(
                conn,
                canonical_id,
                duplicate_ids,
                apply=args.apply and args.retire_duplicate_source_ids,
            )
            applied_refs = apply_reference_updates(conn, ref_updates, apply=args.apply)
            planned = {
                **group,
                "reference_updates": applied_refs,
                "mapping_updates": mapping_updates,
                "team_column_updates": team_column_updates,
                "retired_source_ids": retired_source_ids,
            }
            summary["groups"].append(planned)
            summary["groups_planned"] += 1
            summary["reference_rows_planned"] += sum(int(item["rows"]) for item in applied_refs)
            summary["mapping_rows_planned"] += len(mapping_updates)
            summary["team_column_updates_planned"] += len(team_column_updates)
            summary["duplicate_source_ids_retired_planned"] += len(retired_source_ids)
        if args.apply:
            conn.commit()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--fd-team-ids", default="", help="Comma-separated football-data team ids. Default: all duplicate fd_team_id groups.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--retire-duplicate-source-ids",
        action="store_true",
        help="Clear duplicate rows' source id columns when the canonical row has the same value.",
    )
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
