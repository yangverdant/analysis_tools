"""Idempotent migration helper for the long-term data foundation.

Default mode is dry-run. It prints the missing tables and SQL that would be
applied. Use --apply only after backing up the target database.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audit_data_foundation import DEFAULT_DB, EXPECTED_TABLES, audit, create_sql


INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_collection_runs_date ON collection_runs(match_date);",
    "CREATE INDEX IF NOT EXISTS idx_collection_runs_status ON collection_runs(status);",
    "CREATE INDEX IF NOT EXISTS idx_source_artifacts_entity ON source_artifacts(entity_type, entity_id);",
    "CREATE INDEX IF NOT EXISTS idx_source_artifacts_source ON source_artifacts(source_name, captured_at);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_source_entity_mapping_unique ON source_entity_mappings(entity_type, source_name, source_entity_id);",
    "CREATE INDEX IF NOT EXISTS idx_context_snapshots_match ON match_context_snapshots(match_key, snapshot_time);",
    "CREATE INDEX IF NOT EXISTS idx_feature_snapshots_match ON match_feature_snapshots(match_key, snapshot_time);",
    "CREATE INDEX IF NOT EXISTS idx_post_match_reviews_match ON post_match_reviews(match_key, play_type);",
    "CREATE INDEX IF NOT EXISTS idx_similar_match_cases_match ON similar_match_cases(match_key, similarity_score);",
    "CREATE INDEX IF NOT EXISTS idx_similar_match_cases_play ON similar_match_cases(play_type, match_key, similarity_score);",
    "CREATE INDEX IF NOT EXISTS idx_prediction_reanalysis_changes_run ON prediction_reanalysis_changes(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_prediction_reanalysis_changes_match ON prediction_reanalysis_changes(lottery_match_id, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_prediction_reanalysis_changes_changed ON prediction_reanalysis_changes(prediction_changed, created_at);",
]

ADDITIONAL_COLUMNS = {
    "lottery_results": [
        ("ou_result", "TEXT"),
    ],
    "lottery_validation": [
        ("confidence", "REAL"),
    ],
    "similar_match_cases": [
        ("play_type", "TEXT"),
    ],
}


def table_sql(table: str) -> str:
    cols = EXPECTED_TABLES[table]
    col_sql = ",\n    ".join(f"{name} {definition}" for name, definition in cols)
    return f"CREATE TABLE IF NOT EXISTS {table} (\n    {col_sql}\n);"


def existing_columns(db_path: Path, table: str) -> set:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.execute("PRAGMA busy_timeout=120000")
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
            (table,),
        ).fetchone()
        if not table_exists:
            return set()
        return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}
    finally:
        conn.close()


def additional_column_sql(db_path: Path) -> List[str]:
    statements = []
    for table, columns in ADDITIONAL_COLUMNS.items():
        current = existing_columns(db_path, table)
        if not current:
            continue
        for column, definition in columns:
            if column not in current:
                statements.append(f'ALTER TABLE "{table}" ADD COLUMN {column} {definition};')
    return statements


def planned_sql(db_path: Path) -> List[str]:
    result = audit(db_path)
    statements = [table_sql(table) for table in result["missing_foundation_tables"]]
    statements.extend(additional_column_sql(db_path))
    if statements:
        statements.extend(INDEX_SQL)
    return statements


def apply_sql(db_path: Path, statements: List[str]) -> None:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.execute("PRAGMA busy_timeout=120000")
    try:
        for statement in statements:
            conn.execute(statement)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run/apply data foundation schema migration")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to football_v2.db")
    parser.add_argument("--apply", action="store_true", help="Apply migration. Default is dry-run only.")
    parser.add_argument("--print-all", action="store_true", help="Print all proposed foundation SQL, not only missing tables.")
    args = parser.parse_args()

    db_path = Path(args.db)
    statements = create_sql().split("\n\n") + INDEX_SQL if args.print_all else planned_sql(db_path)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] database: {db_path}")
    if not statements:
        print("No missing foundation tables detected.")
        return

    print(f"Statements: {len(statements)}")
    print("")
    for statement in statements:
        print(statement)
        print("")

    if args.apply:
        apply_sql(db_path, statements)
        print("Migration applied.")
    else:
        print("Dry-run only. Re-run with --apply after backing up the database.")


if __name__ == "__main__":
    main()
