"""Read-only audit for automated lottery collection/analysis loops.

This focuses on operational drift: repeated analysis reports, stale/running
jobs, snapshot bloat, and current-window data gaps. It does not mutate data.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "football_v2.db"


def utc_now_naive() -> datetime:
    """Return UTC now as a naive datetime for existing SQLite UTC strings."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("T", " ").replace("Z", "").split(".")[0]
    for width, fmt in ((19, "%Y-%m-%d %H:%M:%S"), (16, "%Y-%m-%d %H:%M")):
        try:
            return datetime.strptime(text[:width], fmt)
        except ValueError:
            continue
    return None


def iso_date(value: datetime) -> str:
    return value.date().isoformat()


def default_window(days: int = 21) -> Tuple[str, str]:
    today = datetime.now()
    return iso_date(today - timedelta(days=days - 1)), iso_date(today)


def parse_match_time(item: Dict[str, Any]) -> Optional[datetime]:
    text = str(item.get("beijing_time") or "").strip()
    if not text:
        date_text = str(item.get("match_date") or item.get("d") or "").strip()
        time_text = str(item.get("match_time") or "").strip()[:5]
        text = f"{date_text} {time_text}" if date_text and time_text else ""
    if not text:
        return None
    for width, fmt in ((19, "%Y-%m-%d %H:%M:%S"), (16, "%Y-%m-%d %H:%M")):
        try:
            return datetime.strptime(text[:width], fmt)
        except ValueError:
            continue
    return None


def estimated_runtime_minutes(item: Dict[str, Any]) -> int:
    text = " ".join(str(item.get(key) or "") for key in ("league_name_cn", "stage", "round_stage")).lower()
    match_date = str(item.get("match_date") or item.get("d") or str(item.get("beijing_time") or "")[:10] or "")
    if ("world cup" in text or "世界杯" in text) and match_date >= "2026-06-28":
        return 185
    return 130


def is_result_due(item: Dict[str, Any]) -> bool:
    status = str(item.get("sell_status") or "").lower()
    if status in {"finished", "finished_pending"}:
        return True
    kickoff = parse_match_time(item)
    if not kickoff:
        return False
    return (datetime.now() - kickoff).total_seconds() / 60 > estimated_runtime_minutes(item)


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def columns(conn: sqlite3.Connection, table_name: str) -> set:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    except sqlite3.Error:
        return set()


def loads_json(value: Any) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def db_size_stats(conn: sqlite3.Connection, db_path: Path) -> Dict[str, Any]:
    page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
    page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
    free_count = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
    file_bytes = db_path.stat().st_size if db_path.exists() else page_size * page_count
    return {
        "file_mb": round(file_bytes / 1024 / 1024, 1),
        "page_count": page_count,
        "free_pages": free_count,
        "free_mb": round(free_count * page_size / 1024 / 1024, 1),
        "reusable_ratio": round(free_count / page_count, 4) if page_count else 0,
    }


def collection_run_audit(
    conn: sqlite3.Connection,
    recent_hours: int,
    stale_running_hours: int,
) -> Dict[str, Any]:
    if not table_exists(conn, "collection_runs"):
        return {"exists": False}

    # collection_runs.created_at/started_at are written by SQLite CURRENT_TIMESTAMP,
    # which is UTC. Compare with UTC to avoid marking fresh Beijing-time jobs stale.
    cutoff = utc_now_naive() - timedelta(hours=recent_hours)
    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT run_id, trigger_source, run_type, match_date, status,
                   started_at, finished_at, summary_json, error
            FROM collection_runs
            WHERE started_at >= ?
            ORDER BY started_at DESC
            """,
            (cutoff.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()
    ]
    by_type_status: Dict[str, Dict[str, int]] = {}
    durations: Dict[str, List[float]] = {}
    recent_failures: List[Dict[str, Any]] = []
    resolved_recent_failures: List[Dict[str, Any]] = []
    service_restart_interruptions: List[Dict[str, Any]] = []
    active_running: List[Dict[str, Any]] = []
    stale_running: List[Dict[str, Any]] = []
    newer_success_by_type: set[str] = set()
    now = utc_now_naive()

    for row in rows:
        run_type = str(row.get("run_type") or "unknown")
        status = str(row.get("status") or "unknown")
        by_type_status.setdefault(run_type, {})
        by_type_status[run_type][status] = by_type_status[run_type].get(status, 0) + 1

        started = parse_dt(row.get("started_at"))
        finished = parse_dt(row.get("finished_at"))
        if started and finished:
            durations.setdefault(run_type, []).append((finished - started).total_seconds())
        if status in {"success", "completed"}:
            newer_success_by_type.add(run_type)
        elif status != "running":
            failure_item = {
                "run_id": row.get("run_id"),
                "run_type": run_type,
                "status": status,
                "started_at": row.get("started_at"),
                "error": row.get("error"),
            }
            error_text = str(row.get("error") or "")
            if status == "interrupted" and "Marked interrupted during service startup" in error_text:
                service_restart_interruptions.append(failure_item)
            elif run_type in newer_success_by_type:
                resolved_recent_failures.append(failure_item)
            else:
                recent_failures.append(failure_item)
        if status == "running":
            age_hours = round((now - started).total_seconds() / 3600, 2) if started else None
            item = {
                "run_id": row.get("run_id"),
                "run_type": run_type,
                "trigger_source": row.get("trigger_source"),
                "started_at": row.get("started_at"),
                "age_hours": age_hours,
            }
            active_running.append(item)
            if age_hours is not None and age_hours >= stale_running_hours:
                stale_running.append(item)

    avg_durations = {
        run_type: {
            "count": len(values),
            "avg_seconds": round(sum(values) / len(values), 1) if values else 0,
            "max_seconds": round(max(values), 1) if values else 0,
        }
        for run_type, values in durations.items()
    }

    latest = [
        {
            "run_id": row.get("run_id"),
            "run_type": row.get("run_type"),
            "status": row.get("status"),
            "started_at": row.get("started_at"),
            "finished_at": row.get("finished_at"),
            "trigger_source": row.get("trigger_source"),
        }
        for row in rows[:12]
    ]
    return {
        "exists": True,
        "recent_hours": recent_hours,
        "total_recent": len(rows),
        "by_type_status": by_type_status,
        "duration_by_type": avg_durations,
        "active_running": active_running,
        "stale_running": stale_running,
        "recent_failures": recent_failures[:20],
        "resolved_recent_failures": resolved_recent_failures[:20],
        "service_restart_interruptions": service_restart_interruptions[:20],
        "latest": latest,
    }


def analysis_report_audit(
    conn: sqlite3.Connection,
    recent_hours: int,
    duplicate_threshold: int,
) -> Dict[str, Any]:
    if not table_exists(conn, "lottery_analysis_reports"):
        return {"exists": False}

    report_cols = columns(conn, "lottery_analysis_reports")
    has_stale = "is_stale" in report_cols
    stale_expr = "SUM(COALESCE(is_stale, 0))" if "is_stale" in report_cols else "0"
    active_filter = "AND COALESCE(is_stale, 0) = 0" if has_stale else ""
    total = conn.execute("SELECT COUNT(*) FROM lottery_analysis_reports WHERE report_type = 'prediction'").fetchone()[0]
    stale_total = (
        conn.execute(
            "SELECT COUNT(*) FROM lottery_analysis_reports WHERE report_type = 'prediction' AND COALESCE(is_stale, 0) = 1"
        ).fetchone()[0]
        if has_stale
        else 0
    )
    distinct_matches = conn.execute(
        "SELECT COUNT(DISTINCT lottery_match_id) FROM lottery_analysis_reports WHERE report_type = 'prediction'"
    ).fetchone()[0]
    duplicate_rows = max(0, int(total or 0) - int(distinct_matches or 0))
    active_total = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM lottery_analysis_reports
        WHERE report_type = 'prediction'
          {active_filter}
        """
    ).fetchone()[0]
    active_distinct = conn.execute(
        f"""
        SELECT COUNT(DISTINCT lottery_match_id)
        FROM lottery_analysis_reports
        WHERE report_type = 'prediction'
          {active_filter}
        """
    ).fetchone()[0]
    active_duplicate_rows = max(0, int(active_total or 0) - int(active_distinct or 0))
    top_duplicates = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT lottery_match_id, COUNT(*) AS report_count,
                   {stale_expr} AS stale_count,
                   MIN(created_at) AS first_report_at,
                   MAX(created_at) AS latest_report_at
            FROM lottery_analysis_reports
            WHERE report_type = 'prediction'
            GROUP BY lottery_match_id
            HAVING COUNT(*) > ?
            ORDER BY report_count DESC
            LIMIT 20
            """,
            (duplicate_threshold,),
        ).fetchall()
    ]
    top_active_duplicates = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT lottery_match_id, COUNT(*) AS report_count,
                   MIN(created_at) AS first_report_at,
                   MAX(created_at) AS latest_report_at
            FROM lottery_analysis_reports
            WHERE report_type = 'prediction'
              {active_filter}
            GROUP BY lottery_match_id
            HAVING COUNT(*) > 1
            ORDER BY report_count DESC
            LIMIT 20
            """,
        ).fetchall()
    ]

    # lottery_analysis_reports.created_at is also stored with SQLite timestamps.
    cutoff = utc_now_naive() - timedelta(hours=recent_hours)
    recent_rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT lottery_match_id, COUNT(*) AS report_count,
                   MIN(created_at) AS first_report_at,
                   MAX(created_at) AS latest_report_at
            FROM lottery_analysis_reports
            WHERE report_type = 'prediction'
              AND created_at >= ?
            GROUP BY lottery_match_id
            HAVING COUNT(*) > 1
            ORDER BY report_count DESC
            LIMIT 20
            """,
            (cutoff.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()
    ]
    recent_total = conn.execute(
        """
        SELECT COUNT(*)
        FROM lottery_analysis_reports
        WHERE report_type = 'prediction'
          AND created_at >= ?
        """,
        (cutoff.strftime("%Y-%m-%d %H:%M:%S"),),
    ).fetchone()[0]
    recent_distinct = conn.execute(
        """
        SELECT COUNT(DISTINCT lottery_match_id)
        FROM lottery_analysis_reports
        WHERE report_type = 'prediction'
          AND created_at >= ?
        """,
        (cutoff.strftime("%Y-%m-%d %H:%M:%S"),),
    ).fetchone()[0]
    recent_active_total = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM lottery_analysis_reports
        WHERE report_type = 'prediction'
          AND created_at >= ?
          {active_filter}
        """,
        (cutoff.strftime("%Y-%m-%d %H:%M:%S"),),
    ).fetchone()[0]
    recent_active_distinct = conn.execute(
        f"""
        SELECT COUNT(DISTINCT lottery_match_id)
        FROM lottery_analysis_reports
        WHERE report_type = 'prediction'
          AND created_at >= ?
          {active_filter}
        """,
        (cutoff.strftime("%Y-%m-%d %H:%M:%S"),),
    ).fetchone()[0]
    recent_active_rows = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT lottery_match_id, COUNT(*) AS report_count,
                   MIN(created_at) AS first_report_at,
                   MAX(created_at) AS latest_report_at
            FROM lottery_analysis_reports
            WHERE report_type = 'prediction'
              AND created_at >= ?
              {active_filter}
            GROUP BY lottery_match_id
            HAVING COUNT(*) > 1
            ORDER BY report_count DESC
            LIMIT 20
            """,
            (cutoff.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()
    ]

    return {
        "exists": True,
        "prediction_reports": int(total or 0),
        "prediction_matches": int(distinct_matches or 0),
        "stale_prediction_reports": int(stale_total or 0),
        "duplicate_report_rows": duplicate_rows,
        "duplicate_ratio": round(duplicate_rows / total, 4) if total else 0,
        "active_prediction_reports": int(active_total or 0),
        "active_prediction_matches": int(active_distinct or 0),
        "active_duplicate_report_rows": active_duplicate_rows,
        "active_duplicate_ratio": round(active_duplicate_rows / active_total, 4) if active_total else 0,
        "matches_over_threshold": len(top_duplicates),
        "active_matches_with_duplicates": len(top_active_duplicates),
        "top_duplicates": top_duplicates,
        "top_active_duplicates": top_active_duplicates,
        "recent_hours": recent_hours,
        "recent_reports": int(recent_total or 0),
        "recent_distinct_matches": int(recent_distinct or 0),
        "recent_duplicate_rows": max(0, int(recent_total or 0) - int(recent_distinct or 0)),
        "recent_active_reports": int(recent_active_total or 0),
        "recent_active_distinct_matches": int(recent_active_distinct or 0),
        "recent_active_duplicate_rows": max(0, int(recent_active_total or 0) - int(recent_active_distinct or 0)),
        "recent_top_duplicates": recent_rows,
        "recent_top_active_duplicates": recent_active_rows,
    }


def snapshot_audit(conn: sqlite3.Connection) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for table in ("match_context_snapshots", "match_feature_snapshots"):
        if not table_exists(conn, table):
            result[table] = {"exists": False}
            continue
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        distinct_matches = conn.execute(f"SELECT COUNT(DISTINCT match_key) FROM {table}").fetchone()[0]
        top = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT match_key, COUNT(*) AS snapshot_count,
                       MIN(snapshot_time) AS first_snapshot_at,
                       MAX(snapshot_time) AS latest_snapshot_at
                FROM {table}
                GROUP BY match_key
                ORDER BY snapshot_count DESC
                LIMIT 12
                """
            ).fetchall()
        ]
        result[table] = {
            "exists": True,
            "rows": int(total or 0),
            "matches": int(distinct_matches or 0),
            "avg_per_match": round(total / distinct_matches, 2) if distinct_matches else 0,
            "top_matches": top,
        }
    return result


def completeness_audit(conn: sqlite3.Connection, date_from: str, date_to: str, league: str = "") -> Dict[str, Any]:
    required_tables = ["lottery_matches", "lottery_odds", "lottery_results", "lottery_analysis_reports"]
    if any(not table_exists(conn, table) for table in required_tables):
        return {"exists": False, "missing_tables": [table for table in required_tables if not table_exists(conn, table)]}

    has_intel = table_exists(conn, "intelligence_packages") and table_exists(conn, "intelligence_jobs")
    has_validation = table_exists(conn, "lottery_validation")
    has_review = table_exists(conn, "post_match_reviews")
    has_oddsfe_matches = table_exists(conn, "oddsfe_matches")
    report_cols = columns(conn, "lottery_analysis_reports")
    active_report_filter = "AND COALESCE(is_stale, 0) = 0" if "is_stale" in report_cols else ""

    rows = conn.execute(
        f"""
        WITH match_base AS (
            SELECT lm.lottery_match_id, lm.match_num, lm.home_team_cn, lm.away_team_cn,
                   lm.league_name_cn, lm.sell_status, lm.oddsfe_event_id,
                   lm.match_date, lm.match_time, lm.beijing_time,
                   substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) AS d
            FROM lottery_matches lm
            WHERE substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?
              AND (? = '' OR lm.league_name_cn = ? OR lm.league_name_cn LIKE '%' || ? || '%')
        ),
        odds AS (
            SELECT lottery_match_id, COUNT(*) AS c
            FROM lottery_odds
            GROUP BY lottery_match_id
        ),
        results AS (
            SELECT lottery_match_id,
                   MAX(CASE WHEN home_goals_ft IS NOT NULL AND away_goals_ft IS NOT NULL THEN 1 ELSE 0 END) AS has_score,
                   MAX(CASE WHEN home_goals_ht IS NOT NULL AND away_goals_ht IS NOT NULL THEN 1 ELSE 0 END) AS has_half
            FROM lottery_results
            GROUP BY lottery_match_id
        ),
        reports AS (
            SELECT lottery_match_id, COUNT(*) AS c
            FROM lottery_analysis_reports
            WHERE report_type = 'prediction'
              {active_report_filter}
            GROUP BY lottery_match_id
        ),
        validations AS (
            SELECT lottery_match_id, COUNT(*) AS c
            FROM lottery_validation
            GROUP BY lottery_match_id
        ),
        reviews AS (
            SELECT match_key AS lottery_match_id, COUNT(*) AS c
            FROM post_match_reviews
            GROUP BY match_key
        ),
        intel AS (
            SELECT ij.lottery_match_id, COUNT(*) AS c
            FROM intelligence_jobs ij
            JOIN intelligence_packages ip ON ip.job_id = ij.job_id
            GROUP BY ij.lottery_match_id
        ),
        ou AS (
            SELECT event_id, COUNT(*) AS c
            FROM oddsfe_matches
            WHERE ou_pinnacle_line IS NOT NULL
            GROUP BY event_id
        )
        SELECT mb.*,
               COALESCE(odds.c, 0) AS odds_count,
               COALESCE(results.has_score, 0) AS has_score,
               COALESCE(results.has_half, 0) AS has_half,
               COALESCE(reports.c, 0) AS report_count,
               COALESCE(validations.c, 0) AS validation_count,
               COALESCE(reviews.c, 0) AS review_count,
               COALESCE(intel.c, 0) AS intel_count,
               COALESCE(ou.c, 0) AS ou_count
        FROM match_base mb
        LEFT JOIN odds ON odds.lottery_match_id = mb.lottery_match_id
        LEFT JOIN results ON results.lottery_match_id = mb.lottery_match_id
        LEFT JOIN reports ON reports.lottery_match_id = mb.lottery_match_id
        LEFT JOIN validations ON validations.lottery_match_id = mb.lottery_match_id
        LEFT JOIN reviews ON reviews.lottery_match_id = mb.lottery_match_id
        LEFT JOIN intel ON intel.lottery_match_id = mb.lottery_match_id
        LEFT JOIN ou ON ou.event_id = mb.oddsfe_event_id
        ORDER BY mb.d, mb.match_num
        """,
        (date_from, date_to, league, league, league),
    ).fetchall()

    summary = {
        "total": 0,
        "missing_odds": 0,
        "missing_score": 0,
        "missing_half": 0,
        "missing_analysis": 0,
        "missing_intelligence": 0,
        "missing_ou_line": 0,
        "missing_validation": 0,
        "missing_review": 0,
    }
    examples: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        summary["total"] += 1
        missing: List[str] = []
        result_due = is_result_due(item)
        if int(item.get("odds_count") or 0) <= 0:
            summary["missing_odds"] += 1
            missing.append("odds")
        if result_due and not int(item.get("has_score") or 0):
            summary["missing_score"] += 1
            missing.append("score")
        if result_due and not int(item.get("has_half") or 0):
            summary["missing_half"] += 1
            missing.append("half")
        if int(item.get("report_count") or 0) <= 0:
            summary["missing_analysis"] += 1
            missing.append("analysis")
        if has_intel and int(item.get("intel_count") or 0) <= 0:
            summary["missing_intelligence"] += 1
            missing.append("intelligence")
        if has_oddsfe_matches and item.get("oddsfe_event_id") and int(item.get("ou_count") or 0) <= 0:
            summary["missing_ou_line"] += 1
            missing.append("ou_line")
        if has_validation and result_due and int(item.get("has_score") or 0) and int(item.get("report_count") or 0) and int(item.get("validation_count") or 0) <= 0:
            summary["missing_validation"] += 1
            missing.append("validation")
        if has_review and result_due and int(item.get("validation_count") or 0) and int(item.get("review_count") or 0) <= 0:
            summary["missing_review"] += 1
            missing.append("review")
        if missing and len(examples) < 20:
            examples.append({
                "lottery_match_id": item.get("lottery_match_id"),
                "match_num": item.get("match_num"),
                "date": item.get("d"),
                "teams": f"{item.get('home_team_cn') or '-'} vs {item.get('away_team_cn') or '-'}",
                "missing": missing,
            })

    missing_total = sum(value for key, value in summary.items() if key.startswith("missing_"))
    return {
        "exists": True,
        "range": {"start_date": date_from, "end_date": date_to},
        "league": league,
        "summary": {**summary, "missing_total": missing_total},
        "examples": examples,
    }


def build_findings(
    collection_runs: Dict[str, Any],
    reports: Dict[str, Any],
    snapshots: Dict[str, Any],
    completeness: Dict[str, Any],
    db_stats: Dict[str, Any],
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    if collection_runs.get("stale_running"):
        findings.append({
            "severity": "high",
            "code": "stale_running_jobs",
            "message": f"{len(collection_runs['stale_running'])} collection runs are still marked running beyond threshold.",
        })
    if collection_runs.get("recent_failures"):
        findings.append({
            "severity": "medium",
            "code": "recent_failed_jobs",
            "message": f"{len(collection_runs['recent_failures'])} recent collection runs are not successful/completed.",
        })
    active_duplicate_rows = int(
        reports.get("active_duplicate_report_rows")
        if "active_duplicate_report_rows" in reports
        else reports.get("duplicate_report_rows") or 0
    )
    if active_duplicate_rows > 0:
        severity = "high" if active_duplicate_rows > 100 else "medium"
        findings.append({
            "severity": severity,
            "code": "active_duplicate_reports",
            "message": f"{active_duplicate_rows} active prediction report rows exist beyond latest-per-match needs.",
        })
    recent_active_duplicates = int(
        reports.get("recent_active_duplicate_rows")
        if "recent_active_duplicate_rows" in reports
        else reports.get("recent_duplicate_rows") or 0
    )
    if recent_active_duplicates > 0:
        findings.append({
            "severity": "high",
            "code": "recent_active_duplicate_reports",
            "message": f"{recent_active_duplicates} active duplicate prediction reports were created in the recent audit window.",
        })
    missing_total = int((completeness.get("summary") or {}).get("missing_total") or 0)
    if missing_total > 0:
        findings.append({
            "severity": "medium",
            "code": "current_window_data_gaps",
            "message": f"{missing_total} data gaps remain in the selected match window.",
        })
    if db_stats.get("reusable_ratio", 0) > 0.4:
        findings.append({
            "severity": "low",
            "code": "sqlite_free_pages_high",
            "message": f"SQLite has {db_stats.get('free_mb')} MB reusable free pages after cleanup.",
        })
    for table, item in snapshots.items():
        if item.get("avg_per_match", 0) > 80:
            findings.append({
                "severity": "medium",
                "code": f"{table}_many_snapshots_per_match",
                "message": f"{table} averages {item.get('avg_per_match')} snapshots per match.",
            })
    return findings


def audit_auto_loop_health(
    db_path: Path,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    league: str = "",
    recent_hours: int = 24,
    stale_running_hours: int = 6,
    duplicate_threshold: int = 10,
) -> Dict[str, Any]:
    db_path = Path(db_path)
    if not date_from or not date_to:
        date_from, date_to = default_window(21)

    conn = connect(db_path)
    try:
        db_stats = db_size_stats(conn, db_path)
        collection_runs = collection_run_audit(conn, recent_hours, stale_running_hours)
        reports = analysis_report_audit(conn, recent_hours, duplicate_threshold)
        snapshots = snapshot_audit(conn)
        completeness = completeness_audit(conn, date_from, date_to, league=league)
        findings = build_findings(collection_runs, reports, snapshots, completeness, db_stats)
        return {
            "success": True,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "db_path": str(db_path),
            "window": {
                "date_from": date_from,
                "date_to": date_to,
                "league": league,
                "recent_hours": recent_hours,
                "stale_running_hours": stale_running_hours,
                "duplicate_threshold": duplicate_threshold,
            },
            "db": db_stats,
            "collection_runs": collection_runs,
            "analysis_reports": reports,
            "snapshots": snapshots,
            "completeness": completeness,
            "findings": findings,
        }
    finally:
        conn.close()


def print_text(result: Dict[str, Any]) -> None:
    print(f"Automation audit: {result['generated_at']}")
    print(f"DB: {result['db']['file_mb']} MB, reusable {result['db']['free_mb']} MB")
    print("\nFindings:")
    if not result["findings"]:
        print("- none")
    for item in result["findings"]:
        print(f"- [{item['severity']}] {item['code']}: {item['message']}")
    cr = result["collection_runs"]
    print(f"\nRecent runs ({cr.get('recent_hours')}h): {cr.get('total_recent', 0)}")
    for run_type, statuses in (cr.get("by_type_status") or {}).items():
        print(f"- {run_type}: {statuses}")
    ar = result["analysis_reports"]
    print(
        "\nPrediction reports: "
        f"active {ar.get('active_prediction_reports', 0)} rows / {ar.get('active_prediction_matches', 0)} matches, "
        f"active_extra={ar.get('active_duplicate_report_rows', 0)}, "
        f"recent_active_extra={ar.get('recent_active_duplicate_rows', 0)}"
    )
    print(
        "Prediction report history: "
        f"total {ar.get('prediction_reports', 0)} rows / {ar.get('prediction_matches', 0)} matches, "
        f"stale={ar.get('stale_prediction_reports', 0)}, "
        f"archived_extra={ar.get('duplicate_report_rows', 0)}, "
        f"recent_archived_extra={ar.get('recent_duplicate_rows', 0)}"
    )
    if ar.get("top_active_duplicates"):
        print("Top active duplicate report matches:")
        for row in ar["top_active_duplicates"][:8]:
            print(f"- {row['lottery_match_id']}: {row['report_count']} reports, latest {row['latest_report_at']}")
    elif ar.get("top_duplicates"):
        print("Largest archived report histories:")
        for row in ar["top_duplicates"][:8]:
            print(
                f"- {row['lottery_match_id']}: {row['report_count']} rows, "
                f"stale={row.get('stale_count', 0)}, latest {row['latest_report_at']}"
            )
    comp = result["completeness"]
    if comp.get("exists"):
        print(f"\nCompleteness {comp['range']['start_date']}..{comp['range']['end_date']}: {comp['summary']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only automated loop health audit")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    parser.add_argument("--date-from", default=None, help="Completeness start date YYYY-MM-DD")
    parser.add_argument("--date-to", default=None, help="Completeness end date YYYY-MM-DD")
    parser.add_argument("--league", default="", help="Optional league name filter for completeness audit")
    parser.add_argument("--recent-hours", type=int, default=24, help="Recent run/report window")
    parser.add_argument("--stale-running-hours", type=int, default=6, help="Running job stale threshold")
    parser.add_argument("--duplicate-threshold", type=int, default=10, help="Top duplicate report threshold per match")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = audit_auto_loop_health(
        Path(args.db),
        date_from=args.date_from,
        date_to=args.date_to,
        league=args.league,
        recent_hours=args.recent_hours,
        stale_running_hours=args.stale_running_hours,
        duplicate_threshold=args.duplicate_threshold,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
