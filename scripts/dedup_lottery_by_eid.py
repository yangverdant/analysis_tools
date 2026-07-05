#!/usr/bin/env python3
"""One-shot cleanup: deduplicate lottery_matches rows that share the same
oddsfe_event_id. Keeps the row whose home_team_cn has CJK chars (CN name);
deletes the other. Migrates child rows (predictions, results, bets,
analyses) to the kept id before deleting.
"""
import sqlite3

DB = "/opt/football_tools/data/football_v2.db"


def _migrate_table(conn, table, id_col, keep_id, del_id, other_cols):
    """INSERT OR IGNORE rows from del_id into keep_id, then DELETE del_id rows."""
    if not other_cols:
        conn.execute(f"DELETE FROM {table} WHERE {id_col}=?", (del_id,))
        return
    cols_str = ",".join(other_cols)
    conn.execute(
        f"INSERT OR IGNORE INTO {table} ({id_col}, {cols_str}) "
        f"SELECT ?, {cols_str} FROM {table} WHERE {id_col}=?",
        (keep_id, del_id)
    )
    conn.execute(f"DELETE FROM {table} WHERE {id_col}=?", (del_id,))


def main():
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")

    # Discover child tables and their non-id columns
    child_tables = []
    for t in ("lottery_predictions", "lottery_results", "bet_records", "match_analyses"):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
        if "lottery_match_id" in cols:
            other = [c for c in cols if c != "lottery_match_id"]
            child_tables.append((t, "lottery_match_id", other))

    dups = conn.execute("""
        SELECT oddsfe_event_id,
               GROUP_CONCAT(lottery_match_id) as ids,
               GROUP_CONCAT(home_team_cn) as homes,
               COUNT(*) as n
        FROM lottery_matches
        WHERE oddsfe_event_id IS NOT NULL
        GROUP BY oddsfe_event_id
        HAVING n > 1
    """).fetchall()
    print(f"Duplicate groups: {len(dups)}")

    total_deleted = 0
    for eid, ids, homes, n in dups:
        id_list = ids.split(",")
        home_list = (homes or "").split(",")
        keep_idx = None
        for i, h in enumerate(home_list):
            if h and any("一" <= c <= "鿿" for c in h):
                keep_idx = i
                break
        if keep_idx is None:
            keep_idx = 0
        keep_id = id_list[keep_idx]
        delete_ids = [x for i, x in enumerate(id_list) if i != keep_idx]
        for did in delete_ids:
            for table, id_col, other_cols in child_tables:
                try:
                    _migrate_table(conn, table, id_col, keep_id, did, other_cols)
                except Exception as exc:
                    print(f"  warn: migrate {table} failed: {exc}")
                    conn.execute(f"DELETE FROM {table} WHERE {id_col}=?", (did,))
            conn.execute("DELETE FROM lottery_matches WHERE lottery_match_id=?", (did,))
            total_deleted += 1
            other_idx = 0 if keep_idx == 1 else 1
            print(f"  eid={eid}: keep={keep_id}({home_list[keep_idx]!r}), delete={did}({home_list[other_idx]!r})")
    conn.commit()
    print(f"Deleted {total_deleted} duplicate rows")
    conn.close()


if __name__ == "__main__":
    main()
