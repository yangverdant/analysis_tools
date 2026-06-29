import sqlite3
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = str(_PROJECT_ROOT / "data" / "football_v2.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS intelligence_jobs (
            job_id TEXT PRIMARY KEY,
            match_id INTEGER,
            lottery_match_id TEXT,
            home_team_id INTEGER,
            away_team_id INTEGER,
            match_date TEXT,
            match_time TEXT,
            league_name TEXT,
            home_team TEXT,
            away_team TEXT,
            competition_type TEXT NOT NULL DEFAULT 'unknown',
            analysis_view TEXT NOT NULL DEFAULT 'generic',
            status TEXT NOT NULL DEFAULT 'pending',
            priority INTEGER NOT NULL DEFAULT 5,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_intelligence_jobs_date
            ON intelligence_jobs(match_date);
        CREATE INDEX IF NOT EXISTS idx_intelligence_jobs_status
            ON intelligence_jobs(status);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_intelligence_jobs_lottery
            ON intelligence_jobs(lottery_match_id)
            WHERE lottery_match_id IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_intelligence_jobs_match
            ON intelligence_jobs(match_id)
            WHERE match_id IS NOT NULL;

        CREATE TABLE IF NOT EXISTS intelligence_requirements (
            requirement_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            key TEXT NOT NULL,
            category TEXT NOT NULL,
            required INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'missing',
            preferred_sources TEXT NOT NULL DEFAULT '[]',
            fallback_policy TEXT NOT NULL DEFAULT 'mark_missing',
            description TEXT,
            artifact_id TEXT,
            confidence REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(job_id, key),
            FOREIGN KEY(job_id) REFERENCES intelligence_jobs(job_id)
        );

        CREATE INDEX IF NOT EXISTS idx_intelligence_requirements_job
            ON intelligence_requirements(job_id);
        CREATE INDEX IF NOT EXISTS idx_intelligence_requirements_status
            ON intelligence_requirements(status);

        CREATE TABLE IF NOT EXISTS intelligence_artifacts (
            artifact_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            requirement_key TEXT NOT NULL,
            source TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES intelligence_jobs(job_id)
        );

        CREATE INDEX IF NOT EXISTS idx_intelligence_artifacts_job
            ON intelligence_artifacts(job_id);

        CREATE TABLE IF NOT EXISTS intelligence_packages (
            package_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL UNIQUE,
            package_json TEXT NOT NULL,
            completeness REAL NOT NULL DEFAULT 0,
            missing_required_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES intelligence_jobs(job_id)
        );

        CREATE TABLE IF NOT EXISTS intelligence_reviews (
            review_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            lottery_match_id TEXT,
            play_type TEXT,
            predicted_result TEXT,
            actual_result TEXT,
            is_correct INTEGER,
            attribution TEXT,
            confidence REAL,
            source TEXT NOT NULL DEFAULT 'manual',
            result_json TEXT NOT NULL DEFAULT '{}',
            attribution_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES intelligence_jobs(job_id)
        );

        CREATE TABLE IF NOT EXISTS intelligence_runs (
            run_id TEXT PRIMARY KEY,
            run_date TEXT,
            trigger_source TEXT NOT NULL DEFAULT 'manual',
            include_external INTEGER NOT NULL DEFAULT 0,
            collectors_json TEXT NOT NULL DEFAULT '[]',
            network INTEGER NOT NULL DEFAULT 1,
            force INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'running',
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            summary_json TEXT NOT NULL DEFAULT '{}',
            error TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_intelligence_runs_date
            ON intelligence_runs(run_date);
        CREATE INDEX IF NOT EXISTS idx_intelligence_runs_status
            ON intelligence_runs(status);
        """
    )
    _ensure_column(conn, "intelligence_jobs", "home_team_id", "INTEGER")
    _ensure_column(conn, "intelligence_jobs", "away_team_id", "INTEGER")
    _ensure_column(conn, "intelligence_reviews", "lottery_match_id", "TEXT")
    _ensure_column(conn, "intelligence_reviews", "play_type", "TEXT")
    _ensure_column(conn, "intelligence_reviews", "predicted_result", "TEXT")
    _ensure_column(conn, "intelligence_reviews", "actual_result", "TEXT")
    _ensure_column(conn, "intelligence_reviews", "is_correct", "INTEGER")
    _ensure_column(conn, "intelligence_reviews", "attribution", "TEXT")
    _ensure_column(conn, "intelligence_reviews", "confidence", "REAL")
    _ensure_column(conn, "intelligence_reviews", "source", "TEXT NOT NULL DEFAULT 'manual'")
    _ensure_column(conn, "intelligence_reviews", "updated_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_intelligence_reviews_job ON intelligence_reviews(job_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_intelligence_reviews_lottery ON intelligence_reviews(lottery_match_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_intelligence_reviews_correct ON intelligence_reviews(is_correct)"
    )
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
