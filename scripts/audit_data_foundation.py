"""Read-only audit for the football data foundation.

This script does not mutate the database. It checks whether the current
SQLite database has the minimum tables/columns needed for durable collection,
pre-match snapshots, post-match review, and similar-match learning.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import quote


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "football_v2.db"


EXPECTED_TABLES: Dict[str, List[Tuple[str, str]]] = {
    "collection_runs": [
        ("run_id", "TEXT PRIMARY KEY"),
        ("trigger_source", "TEXT NOT NULL DEFAULT 'manual'"),
        ("run_type", "TEXT NOT NULL"),
        ("match_date", "TEXT"),
        ("status", "TEXT NOT NULL DEFAULT 'running'"),
        ("started_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("finished_at", "TEXT"),
        ("summary_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("error", "TEXT"),
    ],
    "source_artifacts": [
        ("artifact_id", "TEXT PRIMARY KEY"),
        ("run_id", "TEXT"),
        ("source_name", "TEXT NOT NULL"),
        ("source_type", "TEXT"),
        ("entity_type", "TEXT"),
        ("entity_id", "TEXT"),
        ("payload_json", "TEXT NOT NULL"),
        ("payload_hash", "TEXT"),
        ("confidence", "REAL DEFAULT 0.5"),
        ("captured_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ],
    "source_entity_mappings": [
        ("mapping_id", "TEXT PRIMARY KEY"),
        ("entity_type", "TEXT NOT NULL"),
        ("canonical_id", "TEXT"),
        ("source_name", "TEXT NOT NULL"),
        ("source_entity_id", "TEXT"),
        ("source_entity_name", "TEXT"),
        ("confidence", "REAL DEFAULT 0.5"),
        ("status", "TEXT NOT NULL DEFAULT 'active'"),
        ("updated_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ],
    "match_context_snapshots": [
        ("snapshot_id", "TEXT PRIMARY KEY"),
        ("match_key", "TEXT NOT NULL"),
        ("snapshot_time", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("competition_context_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("odds_context_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("intel_context_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("data_quality_json", "TEXT NOT NULL DEFAULT '{}'"),
    ],
    "match_feature_snapshots": [
        ("snapshot_id", "TEXT PRIMARY KEY"),
        ("match_key", "TEXT NOT NULL"),
        ("snapshot_time", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("feature_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("model_version", "TEXT"),
        ("source_report_id", "TEXT"),
    ],
    "post_match_reviews": [
        ("review_id", "TEXT PRIMARY KEY"),
        ("match_key", "TEXT NOT NULL"),
        ("play_type", "TEXT"),
        ("predicted_result", "TEXT"),
        ("actual_result", "TEXT"),
        ("is_correct", "INTEGER"),
        ("attribution", "TEXT"),
        ("review_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("created_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ],
    "similar_match_cases": [
        ("case_id", "TEXT PRIMARY KEY"),
        ("match_key", "TEXT NOT NULL"),
        ("play_type", "TEXT"),
        ("similar_match_key", "TEXT NOT NULL"),
        ("similarity_score", "REAL NOT NULL"),
        ("similarity_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("outcome_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("created_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ],
    "prediction_reanalysis_changes": [
        ("change_id", "TEXT PRIMARY KEY"),
        ("run_id", "TEXT"),
        ("trigger_source", "TEXT"),
        ("lottery_match_id", "TEXT NOT NULL"),
        ("match_date", "TEXT"),
        ("match_num", "TEXT"),
        ("league_name_cn", "TEXT"),
        ("home_team_cn", "TEXT"),
        ("away_team_cn", "TEXT"),
        ("before_report_id", "TEXT"),
        ("after_report_id", "TEXT"),
        ("prediction_changed", "INTEGER NOT NULL DEFAULT 0"),
        ("change_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("created_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("settled_at", "TEXT"),
        ("validation_json", "TEXT"),
    ],
}


CORE_TABLES = [
    "matches",
    "teams",
    "players",
    "lottery_matches",
    "lottery_odds",
    "lottery_results",
    "lottery_validation",
    "lottery_analysis_reports",
    "intelligence_jobs",
    "intelligence_artifacts",
    "intelligence_packages",
    "data_source_health",
    "oddsfe_matches",
    "match_odds",
    "match_lineups",
    "fifa_rankings",
    "elo_ratings",
    "elo_history",
]


KEY_COLUMN_CHECKS: Dict[str, List[str]] = {
    "lottery_matches": ["lottery_match_id", "match_date", "beijing_time", "oddsfe_event_id", "handicap_line"],
    "lottery_odds": ["lottery_match_id", "play_type", "odds_data", "opening_odds", "latest_odds", "odds_movement", "snapshot_type"],
    "lottery_results": ["lottery_match_id", "home_goals_ft", "away_goals_ft", "spf_result", "bf_result", "bqc_result", "rqspf_result", "ou_result"],
    "lottery_validation": ["lottery_match_id", "play_type", "predicted_result", "actual_result", "is_correct", "attribution", "scenario_type", "confidence"],
    "data_source_health": ["source_name", "source_category", "status", "last_success", "last_failure", "success_rate"],
}


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    resolved = db_path.resolve()
    uri = "file:" + quote(str(resolved).replace("\\", "/"), safe="/:") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    return conn


def table_names(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row["name"] for row in rows]


def columns(conn: sqlite3.Connection, table: str) -> List[str]:
    try:
        return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
    except sqlite3.Error:
        return []


def indexes(conn: sqlite3.Connection, table: str) -> List[sqlite3.Row]:
    try:
        return conn.execute(f'PRAGMA index_list("{table}")').fetchall()
    except sqlite3.Error:
        return []


def count_rows(conn: sqlite3.Connection, table: str) -> Any:
    try:
        return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    except sqlite3.Error as exc:
        return f"ERR: {exc}"


def fetch_all(conn: sqlite3.Connection, query: str) -> List[Dict[str, Any]]:
    try:
        return [dict(row) for row in conn.execute(query).fetchall()]
    except sqlite3.Error as exc:
        return [{"error": str(exc)}]


def audit(db_path: Path) -> Dict[str, Any]:
    conn = connect_readonly(db_path)
    try:
        existing = set(table_names(conn))
        core_counts = {table: count_rows(conn, table) for table in CORE_TABLES if table in existing}

        missing_foundation = []
        present_foundation = {}
        for table, expected_cols in EXPECTED_TABLES.items():
            if table not in existing:
                missing_foundation.append(table)
                continue
            current_cols = set(columns(conn, table))
            present_foundation[table] = {
                "missing_columns": [name for name, _ in expected_cols if name not in current_cols],
                "row_count": count_rows(conn, table),
            }

        key_columns = {}
        for table, required in KEY_COLUMN_CHECKS.items():
            current = set(columns(conn, table)) if table in existing else set()
            key_columns[table] = {
                "exists": table in existing,
                "missing_columns": [col for col in required if col not in current],
            }

        unique_lottery_results = False
        if "lottery_results" in existing:
            for idx in indexes(conn, "lottery_results"):
                if idx["unique"]:
                    idx_name = idx["name"]
                    idx_cols = [row[2] for row in conn.execute(f'PRAGMA index_info("{idx_name}")').fetchall()]
                    if idx_cols == ["lottery_match_id"]:
                        unique_lottery_results = True
                        break

        metrics = {
            "source_health": fetch_all(
                conn,
                """
                SELECT source_name, source_category, status, last_success, last_failure,
                       failure_count, ROUND(success_rate, 4) AS success_rate
                FROM data_source_health
                ORDER BY source_name
                """,
            ),
            "odds_snapshots": fetch_all(
                conn,
                """
                SELECT COALESCE(snapshot_type, 'null') AS snapshot_type, play_type,
                       COUNT(*) AS count, MAX(update_time) AS latest_update
                FROM lottery_odds
                GROUP BY COALESCE(snapshot_type, 'null'), play_type
                ORDER BY count DESC
                """,
            ),
            "validation_by_play": fetch_all(
                conn,
                """
                SELECT play_type, COALESCE(scenario_type, 'unknown') AS scenario_type,
                       COUNT(*) AS count, SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct
                FROM lottery_validation
                GROUP BY play_type, COALESCE(scenario_type, 'unknown')
                ORDER BY count DESC
                """,
            ),
            "lottery_result_missing_ft": fetch_all(
                conn,
                """
                SELECT COUNT(*) AS missing_count
                FROM lottery_results
                WHERE home_goals_ft IS NULL OR away_goals_ft IS NULL
                """,
            ),
        }

        return {
            "db_path": str(db_path),
            "table_count": len(existing),
            "core_counts": core_counts,
            "missing_foundation_tables": missing_foundation,
            "present_foundation_tables": present_foundation,
            "key_column_checks": key_columns,
            "unique_lottery_results": unique_lottery_results,
            "metrics": metrics,
        }
    finally:
        conn.close()


def create_sql() -> str:
    statements = []
    for table, cols in EXPECTED_TABLES.items():
        col_sql = ",\n    ".join(f"{name} {definition}" for name, definition in cols)
        statements.append(f"CREATE TABLE IF NOT EXISTS {table} (\n    {col_sql}\n);")
    return "\n\n".join(statements)


def markdown_report(result: Dict[str, Any], include_sql: bool = False) -> str:
    lines: List[str] = []
    lines.append("# Data Foundation Audit")
    lines.append("")
    lines.append(f"- Database: `{result['db_path']}`")
    lines.append(f"- Tables: `{result['table_count']}`")
    lines.append(f"- `lottery_results` unique by `lottery_match_id`: `{result['unique_lottery_results']}`")
    lines.append("")

    lines.append("## Core Table Counts")
    lines.append("")
    lines.append("| Table | Rows |")
    lines.append("|---|---:|")
    for table, count in result["core_counts"].items():
        lines.append(f"| `{table}` | {count} |")
    lines.append("")

    lines.append("## Missing Foundation Tables")
    lines.append("")
    if result["missing_foundation_tables"]:
        for table in result["missing_foundation_tables"]:
            lines.append(f"- `{table}`")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## Key Column Checks")
    lines.append("")
    lines.append("| Table | Exists | Missing Columns |")
    lines.append("|---|---|---|")
    for table, check in result["key_column_checks"].items():
        missing = ", ".join(f"`{col}`" for col in check["missing_columns"]) or "-"
        lines.append(f"| `{table}` | `{check['exists']}` | {missing} |")
    lines.append("")

    lines.append("## Odds Snapshot Distribution")
    lines.append("")
    lines.append("| Snapshot | Play Type | Count | Latest Update |")
    lines.append("|---|---|---:|---|")
    for row in result["metrics"]["odds_snapshots"]:
        if "error" in row:
            lines.append(f"| error | | | {row['error']} |")
        else:
            lines.append(
                f"| `{row['snapshot_type']}` | `{row['play_type']}` | {row['count']} | {row['latest_update']} |"
            )
    lines.append("")

    lines.append("## Validation Distribution")
    lines.append("")
    lines.append("| Play Type | Scenario | Count | Correct |")
    lines.append("|---|---|---:|---:|")
    for row in result["metrics"]["validation_by_play"]:
        if "error" in row:
            lines.append(f"| error | | | {row['error']} |")
        else:
            lines.append(f"| `{row['play_type']}` | `{row['scenario_type']}` | {row['count']} | {row['correct']} |")
    lines.append("")

    lines.append("## Source Health")
    lines.append("")
    lines.append("| Source | Category | Status | Last Success | Last Failure | Success Rate |")
    lines.append("|---|---|---|---|---|---:|")
    for row in result["metrics"]["source_health"]:
        if "error" in row:
            lines.append(f"| error | | | | | {row['error']} |")
        else:
            lines.append(
                f"| `{row['source_name']}` | `{row['source_category']}` | `{row['status']}` | "
                f"{row['last_success']} | {row['last_failure']} | {row['success_rate']} |"
            )
    lines.append("")

    missing_ft = result["metrics"]["lottery_result_missing_ft"]
    if missing_ft and "missing_count" in missing_ft[0]:
        lines.append(f"- Lottery results missing FT score: `{missing_ft[0]['missing_count']}`")
    lines.append("")

    if include_sql:
        lines.append("## Proposed SQL")
        lines.append("")
        lines.append("```sql")
        lines.append(create_sql())
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only data foundation audit")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to football_v2.db")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")
    parser.add_argument("--emit-sql", action="store_true", help="Include proposed CREATE TABLE SQL in Markdown output")
    args = parser.parse_args()

    db_path = Path(args.db)
    result = audit(db_path)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(markdown_report(result, include_sql=args.emit_sql))


if __name__ == "__main__":
    main()
