#!/usr/bin/env python3
"""One-shot: merge duplicate lottery_matches rows that share an oddsfe_event_id.

Background
----------
After the sporttery WAF ban (2026-07-04), some matches existed in both:
- sporttery-era rows (created 7/3-7/6, match_num=1093/1094/1201/2095/2096/7092)
  with WRONG beijing_time (sporttery used CN local that drifted)
- oddsfe-era rows (created 7/5 03:17, match_num=3726/3727/7405/7617/8290/8893/8993)
  with CORRECT beijing_time (from oddsfe event_start_at UTC+8)

oddsfe_eid_backfill.py paired the sporttery-era row with the oddsfe eid but
didn't update beijing_time, so both rows persisted with the same eid.

This script merges each duplicate pair:
- canonical = the row whose beijing_time matches oddsfe event_start_at (UTC+8)
- dupe = the other row
- migrate child rows from dupe -> canonical (or delete if canonical already has data)
- delete dupe

Run once after deploying the eid_backfill beijing_time fix.
"""
import logging
import sqlite3
import sys
from typing import List, Tuple

ROOT = "/opt/football_tools"
DB_PATH = f"{ROOT}/data/football_v2.db"

sys.path.insert(0, ROOT)
sys.path.insert(0, f"{ROOT}/scripts")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


CHILD_TABLES = [
    "lottery_odds",
    "lottery_results",
    "lottery_predictions",
    "lottery_analysis_reports",
    "lottery_validation",
    "bet_records",
    "lottery_revalidation_queue",
    "prediction_reanalysis_changes",
    "lottery_market_field_repairs",
    "lottery_team_id_repairs",
    "lottery_match_time_corrections",
    "lottery_result_corrections",
]


def _find_dupes(conn: sqlite3.Connection) -> List[Tuple[str, str, str]]:
    """Return [(canonical_id, dupe_id, eid)] for each duplicate pair."""
    rows = conn.execute(
        "SELECT lottery_match_id, oddsfe_event_id, beijing_time, created_at "
        "FROM lottery_matches "
        "WHERE oddsfe_event_id IN (SELECT oddsfe_event_id FROM lottery_matches "
        "WHERE oddsfe_event_id IS NOT NULL GROUP BY oddsfe_event_id HAVING COUNT(*) > 1) "
        "ORDER BY oddsfe_event_id, created_at"
    ).fetchall()
    by_eid = {}
    for lm_id, eid, bj, created in rows:
        by_eid.setdefault(eid, []).append((lm_id, bj, created))
    pairs = []
    for eid, items in by_eid.items():
        if len(items) != 2:
            logger.warning("eid %s has %d rows, expected 2 — skipping", eid, len(items))
            continue
        # canonical = row with non-null beijing_time that looks like full datetime
        # (oddsfe-era has "YYYY-MM-DD HH:MM:SS"; sporttery-era often has "YYYY-MM-DD HH:MM" or wrong date)
        # Prefer the earlier-created row (7/5 03:17 = oddsfe-era canonical)
        items_sorted = sorted(items, key=lambda x: x[2] or "")
        # Heuristic: canonical has beijing_time with seconds (length 19), dupe often has length 16
        a, b = items_sorted[0], items_sorted[1]
        a_len = len(a[1] or "")
        b_len = len(b[1] or "")
        if a_len == 19 and b_len == 19:
            # Both full — pick earlier created (oddsfe-era wins)
            canonical, dupe = a, b
        elif a_len == 19:
            canonical, dupe = a, b
        elif b_len == 19:
            canonical, dupe = b, a
        else:
            canonical, dupe = a, b
        pairs.append((canonical[0], dupe[0], eid))
    return pairs


def _migrate_children(conn: sqlite3.Connection, canonical: str, dupe: str) -> int:
    """Move child rows from dupe to canonical. Delete dupes that conflict."""
    migrated = 0
    for table in CHILD_TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if "lottery_match_id" not in cols:
            continue
        pk_cols = [r[1] for r in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall() if r[5] == 1]
        if not pk_cols:
            # No PK — just rebind
            cur = conn.execute(
                f"UPDATE {table} SET lottery_match_id=? WHERE lottery_match_id=?",
                (canonical, dupe)
            )
            migrated += cur.rowcount
            continue
        # Has PK — try UPDATE OR REPLACE for each row (handles unique constraints)
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE lottery_match_id=?",
            (dupe,)
        ).fetchall()
        for row in rows:
            col_names = [r[1] for r in conn.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()]
            row_dict = dict(zip(col_names, row))
            row_dict["lottery_match_id"] = canonical
            # Check if canonical already has a row with same PK (excluding lottery_match_id)
            where_pk = " AND ".join(f"{c}=?" for c in pk_cols if c != "lottery_match_id")
            pk_vals = tuple(row_dict[c] for c in pk_cols if c != "lottery_match_id")
            if where_pk:
                existing = conn.execute(
                    f"SELECT 1 FROM {table} WHERE {where_pk} AND lottery_match_id=?",
                    pk_vals + (canonical,)
                ).fetchone()
                if existing:
                    # Conflict — drop the dupe row, canonical already has data
                    continue
            placeholders = ",".join("?" for _ in col_names)
            conn.execute(
                f"DELETE FROM {table} WHERE {','.join(pk_cols)}=?",
                tuple(row_dict[c] for c in pk_cols)
            )
            conn.execute(
                f"INSERT OR REPLACE INTO {table} ({','.join(col_names)}) VALUES ({placeholders})",
                tuple(row_dict[c] for c in col_names)
            )
            migrated += 1
    return migrated


def main() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("BEGIN")
    pairs = _find_dupes(conn)
    logger.info("found %d duplicate pairs", len(pairs))
    total_migrated = 0
    total_deleted = 0
    for canonical, dupe, eid in pairs:
        migrated = _migrate_children(conn, canonical, dupe)
        conn.execute("DELETE FROM lottery_matches WHERE lottery_match_id=?", (dupe,))
        total_migrated += migrated
        total_deleted += 1
        logger.info("merged %s -> %s (eid=%s, %d child rows migrated)",
                    dupe, canonical, eid, migrated)
    conn.commit()
    conn.close()
    print(f"dedup done: pairs={len(pairs)} migrated={total_migrated} deleted={total_deleted}")


if __name__ == "__main__":
    main()
