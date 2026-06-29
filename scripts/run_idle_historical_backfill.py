"""Idle historical backfill worker.

This worker is for the slow lane: when the server is otherwise quiet, it picks
older settled lottery dates in reverse order, fills data gaps, rebuilds review
records, and refreshes learning assets. Each invocation is intentionally small.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get("DB_PATH") or ROOT / "data" / "football_v2.db")
DEFAULT_ODDSFE_DB = Path(
    os.environ.get("ODDSFE_DB_PATH") or ROOT / "fetchers" / "odds_feed_api" / "oddsfe_merged.db"
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.data_access.foundation_dao import FoundationDAO  # noqa: E402
from run_segmented_auto_loop import (  # noqa: E402
    accuracy_snapshot,
    has_budget,
    log,
    resolve_deadline,
    round_learning,
    run_command,
    should_stop,
    time_left,
)


ACTIVE_RUN_TYPES = {
    "auto_loop_cycle",
    "historical_backfill",
    "auto_gap_fill",
    "oddsfe_event_details",
    "oddsfe_ou_lines",
    "learning_refresh",
    "idle_historical_backfill",
}


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def today_local() -> date:
    return datetime.now().date()


def get_load_average() -> Optional[float]:
    try:
        return float(os.getloadavg()[0])
    except (AttributeError, OSError):
        return None


def active_runs(db_path: Path, stale_minutes: int) -> List[Dict[str, Any]]:
    with connect(db_path) as conn:
        if not table_exists(conn, "collection_runs"):
            return []
        placeholders = ",".join("?" for _ in ACTIVE_RUN_TYPES)
        rows = conn.execute(
            f"""
            SELECT run_id, run_type, match_date, started_at,
                   ROUND((julianday('now') - julianday(started_at)) * 24 * 60, 1) AS age_minutes
            FROM collection_runs
            WHERE status = 'running'
              AND run_type IN ({placeholders})
              AND (julianday('now') - julianday(started_at)) * 24 * 60 < ?
            ORDER BY started_at DESC
            """,
            [*sorted(ACTIVE_RUN_TYPES), stale_minutes],
        ).fetchall()
    return [dict(row) for row in rows]


def should_skip_for_idle(args: argparse.Namespace, db_path: Path) -> Optional[Dict[str, Any]]:
    if args.ignore_idle_checks:
        return None

    load_avg = get_load_average()
    if load_avg is not None and args.max_load is not None and load_avg > args.max_load:
        return {
            "reason": "load_too_high",
            "load_1m": round(load_avg, 2),
            "max_load": args.max_load,
        }

    running = active_runs(db_path, args.active_stale_minutes)
    if running:
        return {
            "reason": "active_collection_runs",
            "active_runs": running[:5],
        }
    return None


def candidate_dates(args: argparse.Namespace, db_path: Path) -> List[Dict[str, Any]]:
    latest = today_local() - timedelta(days=max(args.latest_offset_days, 0))
    earliest = latest - timedelta(days=max(args.lookback_days, 1))

    where = [
        "substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?",
        "lm.home_team_id IS NOT NULL",
        "lm.away_team_id IS NOT NULL",
    ]
    params: List[Any] = [earliest.isoformat(), latest.isoformat()]
    if args.league:
        where.append("COALESCE(lm.league_name_cn, '') = ?")
        params.append(args.league)

    with connect(db_path) as conn:
        if not table_exists(conn, "lottery_matches"):
            return []
        has_artifacts = table_exists(conn, "source_artifacts")
        has_ou = table_exists(conn, "oddsfe_matches")
        has_reviews = table_exists(conn, "post_match_reviews")
        has_intel = table_exists(conn, "intelligence_jobs") and table_exists(conn, "intelligence_packages")

        artifact_join = ""
        event_cache_expr = "0"
        if has_artifacts:
            artifact_join = """
                LEFT JOIN (
                    SELECT DISTINCT entity_id
                    FROM source_artifacts
                    WHERE source_name = 'oddsfe'
                      AND entity_type = 'event'
                ) sea ON sea.entity_id = CAST(lm.oddsfe_event_id AS TEXT)
            """
            event_cache_expr = """
                SUM(CASE WHEN lm.oddsfe_event_id IS NOT NULL
                          AND lm.oddsfe_event_id <> ''
                          AND sea.entity_id IS NULL
                         THEN 1 ELSE 0 END)
            """

        ou_join = ""
        ou_expr = "0"
        if has_ou:
            ou_join = """
                LEFT JOIN oddsfe_matches om
                  ON CAST(om.event_id AS TEXT) = CAST(lm.oddsfe_event_id AS TEXT)
            """
            ou_expr = """
                SUM(CASE WHEN lm.oddsfe_event_id IS NOT NULL
                          AND lm.oddsfe_event_id <> ''
                          AND (
                              om.event_id IS NULL
                              OR om.ou_pinnacle_line IS NULL
                              OR om.ou_pinnacle_over IS NULL
                              OR om.ou_pinnacle_under IS NULL
                          )
                         THEN 1 ELSE 0 END)
            """

        review_join = ""
        review_expr = "0"
        if has_reviews:
            review_join = """
                LEFT JOIN (
                    SELECT DISTINCT match_key
                    FROM post_match_reviews
                ) pr ON pr.match_key = lm.lottery_match_id
            """
            review_expr = """
                SUM(CASE WHEN lr.lottery_match_id IS NOT NULL
                          AND ar.lottery_match_id IS NOT NULL
                          AND lv.lottery_match_id IS NOT NULL
                          AND pr.match_key IS NULL
                         THEN 1 ELSE 0 END)
            """

        intel_join = ""
        intel_expr = "0"
        if has_intel:
            intel_join = """
                LEFT JOIN intelligence_jobs ij ON ij.lottery_match_id = lm.lottery_match_id
                LEFT JOIN intelligence_packages ip ON ip.job_id = ij.job_id
            """
            intel_expr = """
                SUM(CASE WHEN ip.job_id IS NULL THEN 1 ELSE 0 END)
            """

        rows = conn.execute(
            f"""
            WITH active_reports AS (
                SELECT DISTINCT lottery_match_id
                FROM lottery_analysis_reports
                WHERE report_type IN ('prediction', 'full')
                  AND COALESCE(is_stale, 0) = 0
            ),
            odds AS (
                SELECT DISTINCT lottery_match_id
                FROM lottery_odds
                WHERE play_type IN ('spf', 'rqspf')
            ),
            validations AS (
                SELECT DISTINCT lottery_match_id
                FROM lottery_validation
            )
            SELECT substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) AS d,
                   COUNT(*) AS total_matches,
                   SUM(CASE WHEN odds.lottery_match_id IS NULL THEN 1 ELSE 0 END) AS missing_odds,
                   SUM(CASE WHEN lm.oddsfe_event_id IS NOT NULL
                             AND lm.oddsfe_event_id <> ''
                             AND (
                                 lr.lottery_match_id IS NULL
                                 OR lr.home_goals_ft IS NULL
                                 OR lr.away_goals_ft IS NULL
                                 OR lr.home_goals_ht IS NULL
                                 OR lr.away_goals_ht IS NULL
                             )
                            THEN 1 ELSE 0 END) AS missing_results,
                   {ou_expr} AS missing_ou_line,
                   SUM(CASE WHEN ar.lottery_match_id IS NULL THEN 1 ELSE 0 END) AS missing_analysis,
                   SUM(CASE WHEN lr.lottery_match_id IS NOT NULL
                             AND ar.lottery_match_id IS NOT NULL
                             AND lv.lottery_match_id IS NULL
                            THEN 1 ELSE 0 END) AS missing_validation,
                   {review_expr} AS missing_review,
                   {intel_expr} AS missing_intelligence,
                   {event_cache_expr} AS missing_event_cache
            FROM lottery_matches lm
            LEFT JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
            LEFT JOIN active_reports ar ON ar.lottery_match_id = lm.lottery_match_id
            LEFT JOIN odds ON odds.lottery_match_id = lm.lottery_match_id
            LEFT JOIN validations lv ON lv.lottery_match_id = lm.lottery_match_id
            {artifact_join}
            {ou_join}
            {review_join}
            {intel_join}
            WHERE {' AND '.join(where)}
            GROUP BY d
            HAVING missing_odds > 0
                OR missing_results > 0
                OR missing_ou_line > 0
                OR missing_analysis > 0
                OR missing_validation > 0
                OR missing_review > 0
                OR missing_intelligence > 0
                OR missing_event_cache > 0
            ORDER BY d DESC
            LIMIT ?
            """,
            [*params, max(args.max_dates * 4, args.max_dates)],
        ).fetchall()

    candidates = []
    for row in rows:
        item = dict(row)
        item["missing_total"] = sum(
            int(item.get(key) or 0)
            for key in (
                "missing_odds",
                "missing_results",
                "missing_ou_line",
                "missing_analysis",
                "missing_validation",
                "missing_review",
                "missing_intelligence",
                "missing_event_cache",
            )
        )
        candidates.append(item)
    return candidates[: args.max_dates]


def process_date(args: argparse.Namespace, target: Dict[str, Any], deadline: Optional[datetime]) -> Dict[str, Any]:
    target_date = str(target["d"])
    db_path = str(Path(args.db))
    oddsfe_db_path = str(Path(args.oddsfe_db))
    summary: Dict[str, Any] = {"date": target_date, "target": target, "steps": {}}

    steps = [
        (
            "event_details",
            [
                "scripts/sync_oddsfe_event_details.py",
                "--db",
                db_path,
                "--from",
                target_date,
                "--to",
                target_date,
                "--apply",
                "--max-events",
                str(args.max_events),
                "--batches",
                "1",
                "--cache-minutes",
                str(args.cache_minutes),
                "--sleep",
                "0.12",
            ],
            args.step_timeout,
        ),
        (
            "ou_lines",
            [
                "scripts/sync_oddsfe_ou_lines.py",
                "--db",
                db_path,
                "--oddsfe-db",
                oddsfe_db_path,
                "--from",
                target_date,
                "--to",
                target_date,
                "--apply",
                "--fetch-live",
                "--max-events",
                str(args.max_events),
            ],
            args.step_timeout,
        ),
        (
            "auto_gap",
            [
                "scripts/run_auto_gap_segment.py",
                "--db",
                db_path,
                "--oddsfe-db",
                oddsfe_db_path,
                "--from",
                target_date,
                "--to",
                target_date,
                "--max-events",
                str(args.max_events),
                "--max-analysis",
                str(args.max_analysis),
                "--max-intelligence",
                str(args.max_intelligence),
                "--max-validation-dates",
                "1",
                "--no-network-intelligence",
            ],
            args.auto_gap_timeout,
        ),
        (
            "validation",
            [
                "scripts/rebuild_lottery_validation.py",
                "--db",
                db_path,
                "--from",
                target_date,
                "--to",
                target_date,
                "--apply",
            ],
            args.validation_timeout,
        ),
        (
            "audit_prediction",
            [
                "scripts/audit_prediction_consistency.py",
                "--db",
                db_path,
                "--date-from",
                target_date,
                "--date-to",
                target_date,
                "--league",
                args.league or "",
                "--fail-on-issues",
            ],
            90,
        ),
        (
            "audit_ou",
            [
                "scripts/audit_ou_goal_axis.py",
                "--db",
                db_path,
                "--date-from",
                target_date,
                "--date-to",
                target_date,
                "--league",
                args.league or "",
                "--fail-on-hard",
            ],
            90,
        ),
    ]

    for name, command, timeout_seconds in steps:
        if should_stop(deadline) or not has_budget(deadline, args.min_step_seconds):
            summary["steps"][name] = {
                "skipped": True,
                "reason": "not_enough_time_budget",
                "seconds_left": round(time_left(deadline) or 0, 1) if deadline else None,
            }
            continue
        summary["steps"][name] = run_command(
            f"idle_{name}",
            command,
            timeout_seconds=timeout_seconds,
            deadline=deadline,
        )

    summary["failed_steps"] = [
        name
        for name, result in summary["steps"].items()
        if isinstance(result, dict)
        and not result.get("skipped")
        and int(result.get("exit_code") or 0) != 0
    ]
    log("IDLE DATE DONE", summary)
    return summary


def run(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    deadline = resolve_deadline(args.deadline, args.max_minutes)
    idle_skip = should_skip_for_idle(args, db_path)
    if idle_skip:
        result = {
            "success": True,
            "skipped": True,
            "idle_skip": idle_skip,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        }
        log("IDLE BACKFILL SKIP", result)
        return result

    foundation = FoundationDAO(str(db_path))
    run_id = foundation.start_run(
        run_type="idle_historical_backfill",
        match_date=today_local().isoformat(),
        trigger_source="idle_backfill_script",
        summary={"stage": "start", "args": vars(args)},
    )

    summary: Dict[str, Any] = {"run_id": run_id, "targets": [], "processed": []}
    try:
        targets = candidate_dates(args, db_path)
        summary["targets"] = targets
        log("IDLE BACKFILL TARGETS", targets)

        for target in targets:
            if should_stop(deadline) or not has_budget(deadline, args.min_date_seconds):
                log(
                    "STOP before next idle date",
                    {
                        "next_date": target.get("d"),
                        "seconds_left": round(time_left(deadline) or 0, 1) if deadline else None,
                        "min_date_seconds": args.min_date_seconds,
                    },
                )
                break
            summary["processed"].append(process_date(args, target, deadline))
            if args.sleep_between_dates > 0 and not should_stop(deadline):
                time.sleep(args.sleep_between_dates)

        if summary["processed"] and args.refresh_learning:
            processed_dates = [item["date"] for item in summary["processed"]]
            args.date_from = min(processed_dates)
            args.date_to = max(processed_dates)
            if has_budget(deadline, args.min_learning_seconds):
                summary["learning"] = round_learning(args, deadline)
            else:
                summary["learning"] = {
                    "skipped": True,
                    "reason": "not_enough_time_budget",
                    "seconds_left": round(time_left(deadline) or 0, 1) if deadline else None,
                }

        if summary["processed"]:
            processed_dates = [item["date"] for item in summary["processed"]]
            summary["accuracy_snapshot"] = accuracy_snapshot(
                db_path,
                min(processed_dates),
                max(processed_dates),
                args.league or None,
            )

        summary["success"] = True
        summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
        foundation.finish_run(run_id, status="success", summary=summary)
        log("IDLE BACKFILL FINISH", summary)
        return summary
    except Exception as exc:
        summary["success"] = False
        summary["error"] = str(exc)
        summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
        foundation.finish_run(run_id, status="failed", summary=summary, error=str(exc))
        log("IDLE BACKFILL FAILED", summary)
        return summary


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--oddsfe-db", default=str(DEFAULT_ODDSFE_DB))
    parser.add_argument("--lookback-days", type=int, default=1095, help="How far back to search")
    parser.add_argument("--latest-offset-days", type=int, default=1, help="0=today, 1=yesterday, 2=day before yesterday")
    parser.add_argument("--league", default="", help="Optional league filter; empty means all leagues")
    parser.add_argument("--max-dates", type=int, default=1, help="Dates to process per idle invocation")
    parser.add_argument("--max-events", type=int, default=6)
    parser.add_argument("--max-analysis", type=int, default=10)
    parser.add_argument("--max-intelligence", type=int, default=5)
    parser.add_argument("--cache-minutes", type=int, default=1440)
    parser.add_argument("--step-timeout", type=int, default=240)
    parser.add_argument("--auto-gap-timeout", type=int, default=300)
    parser.add_argument("--validation-timeout", type=int, default=240)
    parser.add_argument("--sleep-between-dates", type=float, default=3)
    parser.add_argument("--deadline", default=None, help="Local HH:MM or ISO datetime deadline")
    parser.add_argument("--max-minutes", type=float, default=20)
    parser.add_argument("--min-step-seconds", type=int, default=45)
    parser.add_argument("--min-date-seconds", type=int, default=150)
    parser.add_argument("--min-learning-seconds", type=int, default=240)
    parser.add_argument("--refresh-learning", action="store_true", default=True)
    parser.add_argument("--no-refresh-learning", dest="refresh_learning", action="store_false")
    parser.add_argument("--learning-days", type=int, default=90)
    parser.add_argument("--learning-min-samples", type=int, default=10)
    parser.add_argument("--max-load", type=float, default=1.6, help="Skip when 1m load average is above this")
    parser.add_argument("--active-stale-minutes", type=int, default=90)
    parser.add_argument("--ignore-idle-checks", action="store_true")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    result = run(args)
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
