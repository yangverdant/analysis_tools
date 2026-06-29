"""Sporttery collection entrypoint.

This script intentionally delegates to LotterySyncService, the canonical
collection path that records collection_runs/source_artifacts, writes normalized
odds, bridges oddsfe events, and preserves snapshots. Older versions of this
file wrote partial rows directly and could fail with an asyncio close error.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
DEFAULT_DB = ROOT / "data" / "football_v2.db"

if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lottery.services.sync_service import LotterySyncService  # noqa: E402
from backend.app.data_access.task_lock import inspect_task_lock  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("sporttery_sync")


def _date_range(start: date, days: int) -> Iterable[date]:
    for offset in range(max(1, days)):
        yield start + timedelta(days=offset)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def _health_upsert(db_path: Path, source_name: str, status: str, success: bool, error: str | None = None) -> None:
    """Persist real source health so stale 'healthy' labels do not mislead us."""
    try:
        conn = sqlite3.connect(str(db_path), timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute(
            """
            INSERT OR IGNORE INTO data_source_health
            (source_name, source_category, status, success_rate, failure_count, updated_at)
            VALUES (?, 'collector', 'unknown', 1.0, 0, CURRENT_TIMESTAMP)
            """,
            (source_name,),
        )
        if success:
            conn.execute(
                """
                UPDATE data_source_health
                SET status = ?, last_success = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP,
                    success_rate = CASE
                        WHEN success_rate IS NULL OR success_rate <= 0 THEN 1.0
                        ELSE MIN(1.0, success_rate * 0.90 + 0.10)
                    END
                WHERE source_name = ?
                """,
                (status, source_name),
            )
        else:
            conn.execute(
                """
                UPDATE data_source_health
                SET status = ?, last_failure = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP,
                    failure_count = COALESCE(failure_count, 0) + 1,
                    success_rate = MAX(0.0, COALESCE(success_rate, 1.0) * 0.80)
                WHERE source_name = ?
                """,
                (status, source_name),
            )
        if error:
            logger.warning("%s health marked %s: %s", source_name, status, error)
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.debug("health update skipped: %s", exc)


def _active_collection_runs(db_path: Path, max_age_minutes: int = 45) -> List[Dict[str, Any]]:
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT run_id, run_type, match_date, started_at, summary_json
            FROM collection_runs
            WHERE status = 'running'
              AND run_type IN (
                'sporttery_daily_matches',
                'auto_gap_fill',
                'automation_center',
                'historical_backfill',
                'oddsfe_event_details'
              )
              AND datetime(started_at) >= datetime('now', ?)
            ORDER BY started_at DESC
            LIMIT 8
            """,
            (f"-{int(max_age_minutes)} minutes",),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.debug("active collection check skipped: %s", exc)
        return []


def _should_defer(db_path: Path) -> Dict[str, Any] | None:
    automation_lock = inspect_task_lock("automation_center", str(db_path))
    if automation_lock.get("locked") and not automation_lock.get("stale"):
        return {"reason": "automation_center_lock", "lock": automation_lock}
    active = _active_collection_runs(db_path)
    if active:
        return {"reason": "active_collection_runs", "active": active}
    return None


def _run_service_date(db_path: Path, target: date, include_results: bool, bridge_oddsfe: bool) -> Dict[str, Any]:
    service = LotterySyncService(str(db_path))
    day_result: Dict[str, Any] = {"date": target.isoformat()}
    try:
        match_result = service.sync_daily_matches(
            target,
            bridge_oddsfe=bridge_oddsfe,
            trigger_source="sporttery_realtime_sync",
        )
        day_result["matches"] = match_result
        day_result["success"] = bool(match_result.get("success"))
        if include_results:
            result_sync = service.sync_results(target)
            day_result["results"] = result_sync
            day_result["success"] = day_result["success"] and bool(result_sync.get("success"))
    except Exception as exc:
        day_result["success"] = False
        day_result["error"] = str(exc)
        logger.exception("sporttery worker failed for %s", target)
    return day_result


def _mark_running_stale_for_date(db_path: Path, target: date, reason: str) -> int:
    try:
        conn = sqlite3.connect(str(db_path), timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        rows = conn.execute(
            """
            SELECT run_id, summary_json
            FROM collection_runs
            WHERE status = 'running'
              AND run_type = 'sporttery_daily_matches'
              AND match_date = ?
            """,
            (target.isoformat(),),
        ).fetchall()
        updated = 0
        for run_id, summary_json in rows:
            try:
                summary = json.loads(summary_json or "{}")
                if not isinstance(summary, dict):
                    summary = {"previous_summary": summary}
            except Exception:
                summary = {"previous_summary_json": summary_json}
            summary["stale_marked_at"] = datetime.now().isoformat(timespec="seconds")
            summary["stale_reason"] = reason
            cur = conn.execute(
                """
                UPDATE collection_runs
                SET status = 'stale_failed',
                    finished_at = CURRENT_TIMESTAMP,
                    summary_json = ?,
                    error = ?
                WHERE run_id = ?
                  AND status = 'running'
                """,
                (_json(summary), reason, run_id),
            )
            updated += cur.rowcount
        conn.commit()
        conn.close()
        return updated
    except Exception as exc:
        logger.debug("failed to mark stale sporttery worker rows: %s", exc)
        return 0


def _parse_worker_output(stdout: str, stderr: str) -> Dict[str, Any]:
    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    for line in reversed(lines):
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                if stderr:
                    parsed.setdefault("stderr_tail", stderr[-2000:])
                return parsed
        except Exception:
            continue
    return {
        "success": False,
        "error": "worker JSON output not found",
        "stdout_tail": (stdout or "")[-2000:],
        "stderr_tail": (stderr or "")[-2000:],
    }


def _run_worker_date(
    db_path: Path,
    target: date,
    include_results: bool,
    timeout_seconds: int,
    bridge_oddsfe: bool,
) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--db",
        str(db_path),
        "--worker-date",
        target.isoformat(),
        "--date-timeout",
        str(timeout_seconds),
    ]
    if include_results:
        cmd.append("--results")
    if bridge_oddsfe:
        cmd.append("--bridge-oddsfe")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(20, int(timeout_seconds)),
        )
        result = _parse_worker_output(proc.stdout, proc.stderr)
        result["exit_code"] = proc.returncode
        if proc.returncode != 0:
            result["success"] = False
        return result
    except subprocess.TimeoutExpired as exc:
        stale_count = _mark_running_stale_for_date(
            db_path,
            target,
            f"sporttery worker timed out after {timeout_seconds} seconds",
        )
        return {
            "success": False,
            "date": target.isoformat(),
            "timeout": True,
            "timeout_seconds": timeout_seconds,
            "stale_rows_marked": stale_count,
            "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
        }


def run_once(
    db_path: Path,
    start: date,
    days: int,
    include_results: bool = True,
    date_timeout: int = 180,
    bridge_oddsfe: bool = False,
) -> Dict[str, Any]:
    defer = _should_defer(db_path)
    if defer:
        return {
            "success": True,
            "skipped": True,
            "start": start.isoformat(),
            "days": days,
            "reason": defer.get("reason"),
            "defer": defer,
        }

    summary: Dict[str, Any] = {
        "success": True,
        "start": start.isoformat(),
        "days": days,
        "date_timeout": date_timeout,
        "bridge_oddsfe": bool(bridge_oddsfe),
        "dates": [],
        "matches_saved": 0,
        "odds_saved": 0,
        "results_saved": 0,
        "oddsfe_results_filled": 0,
        "errors": [],
    }

    for target in _date_range(start, days):
        day_result = _run_worker_date(db_path, target, include_results, date_timeout, bridge_oddsfe)
        match_result = day_result.get("matches") if isinstance(day_result.get("matches"), dict) else {}
        result_sync = day_result.get("results") if isinstance(day_result.get("results"), dict) else {}
        summary["matches_saved"] += int(match_result.get("saved") or 0)
        summary["odds_saved"] += int(match_result.get("odds_saved") or 0)
        summary["results_saved"] += int(result_sync.get("saved") or 0)
        summary["oddsfe_results_filled"] += int(result_sync.get("oddsfe_filled") or 0)
        if not day_result.get("success"):
            summary["success"] = False
            summary["errors"].append({
                "date": target.isoformat(),
                "stage": "worker",
                "error": day_result.get("error") or ("timeout" if day_result.get("timeout") else "worker_failed"),
            })

        summary["dates"].append(day_result)

    _health_upsert(
        db_path,
        "sporttery",
        "healthy" if summary["success"] else "error",
        bool(summary["success"]),
        _json(summary["errors"][:3]) if summary["errors"] else None,
    )
    return summary


def run_continuous(
    db_path: Path,
    days: int,
    interval_seconds: int,
    include_results: bool,
    date_timeout: int,
    bridge_oddsfe: bool,
) -> None:
    while True:
        start = date.today()
        summary = run_once(
            db_path=db_path,
            start=start,
            days=days,
            include_results=include_results,
            date_timeout=date_timeout,
            bridge_oddsfe=bridge_oddsfe,
        )
        logger.info("sporttery continuous cycle: %s", _json(summary))
        time.sleep(max(60, interval_seconds))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Sporttery matches/odds/results through the canonical service.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path.")
    parser.add_argument("--start", default=date.today().isoformat(), help="Start date, YYYY-MM-DD.")
    parser.add_argument("--days", type=int, default=3, help="Number of dates to sync from --start.")
    parser.add_argument("--results", action="store_true", help="Also sync finished results for the same dates.")
    parser.add_argument("--no-results", action="store_true", help="Skip result sync even if --results was set.")
    parser.add_argument("--continuous", action="store_true", help="Run forever with interval-based cycles.")
    parser.add_argument("--interval", type=int, default=600, help="Continuous mode interval in seconds.")
    parser.add_argument("--date-timeout", type=int, default=180, help="Hard timeout per date worker.")
    parser.add_argument(
        "--bridge-oddsfe",
        action="store_true",
        help="Run oddsfe schedule bridge inside the Sporttery worker. Default defers it to oddsfe event tasks.",
    )
    parser.add_argument(
        "--no-bridge-oddsfe",
        dest="bridge_oddsfe",
        action="store_false",
        help="Explicitly defer oddsfe schedule bridge to separate event tasks.",
    )
    parser.set_defaults(bridge_oddsfe=False)
    parser.add_argument("--worker-date", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db).resolve()
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    include_results = args.results and not args.no_results

    if args.worker_date:
        target = datetime.strptime(args.worker_date, "%Y-%m-%d").date()
        print(_json(_run_service_date(db_path, target, include_results, args.bridge_oddsfe)))
        return 0

    if args.continuous:
        run_continuous(
            db_path=db_path,
            days=args.days,
            interval_seconds=args.interval,
            include_results=include_results,
            date_timeout=args.date_timeout,
            bridge_oddsfe=args.bridge_oddsfe,
        )
        return 0

    summary = run_once(
        db_path=db_path,
        start=start,
        days=args.days,
        include_results=include_results,
        date_timeout=args.date_timeout,
        bridge_oddsfe=args.bridge_oddsfe,
    )
    print(_json(summary))
    return 0 if summary.get("success") else 2


if __name__ == "__main__":
    raise SystemExit(main())
