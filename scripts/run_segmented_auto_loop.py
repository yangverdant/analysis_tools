"""Run the lottery automation loop in bounded date/content segments.

This is intentionally different from a full-range loop: every segment gets its
own collection, analysis, validation, and audit steps, so long runs are easier
to inspect and failures are contained to a small date window.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get("DB_PATH") or ROOT / "data" / "football_v2.db")
DEFAULT_ODDSFE_DB = Path(
    os.environ.get("ODDSFE_DB_PATH") or ROOT / "fetchers" / "odds_feed_api" / "oddsfe_merged.db"
)

def log(message: str, payload: Optional[Any] = None) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str), flush=True)


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_segments(date_from: str, date_to: str, days: int) -> List[Tuple[str, str]]:
    start = parse_day(date_from)
    end = parse_day(date_to)
    if end < start:
        raise ValueError("--to cannot be earlier than --from")
    width = max(int(days), 1)
    segments: List[Tuple[str, str]] = []
    current = start
    while current <= end:
        segment_end = min(current + timedelta(days=width - 1), end)
        segments.append((current.isoformat(), segment_end.isoformat()))
        current = segment_end + timedelta(days=1)
    return segments


def resolve_deadline(deadline: Optional[str], max_minutes: Optional[float]) -> Optional[datetime]:
    values: List[datetime] = []
    now = datetime.now()
    if deadline:
        text = deadline.strip()
        if len(text) == 5 and text[2] == ":":
            hour, minute = [int(part) for part in text.split(":")]
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
            values.append(candidate)
        else:
            values.append(datetime.fromisoformat(text))
    if max_minutes and max_minutes > 0:
        values.append(now + timedelta(minutes=max_minutes))
    return min(values) if values else None


def time_left(deadline: Optional[datetime]) -> Optional[float]:
    if not deadline:
        return None
    return (deadline - datetime.now()).total_seconds()


def should_stop(deadline: Optional[datetime], min_seconds: int = 20) -> bool:
    left = time_left(deadline)
    return left is not None and left <= min_seconds


def has_budget(deadline: Optional[datetime], min_seconds: int) -> bool:
    left = time_left(deadline)
    return left is None or left > min_seconds


def command_timeout(default_seconds: int, deadline: Optional[datetime]) -> int:
    left = time_left(deadline)
    if left is None:
        return default_seconds
    return max(20, min(default_seconds, int(left) - 5))


def run_command(
    name: str,
    args: Sequence[str],
    *,
    timeout_seconds: int,
    deadline: Optional[datetime],
    check: bool = False,
) -> Dict[str, Any]:
    if should_stop(deadline):
        result = {"skipped": True, "reason": "deadline_reached"}
        log(f"SKIP {name}", result)
        return result

    timeout_value = command_timeout(timeout_seconds, deadline)
    cmd = [sys.executable, *args]
    log(f">>> {name}", {"cmd": " ".join(cmd), "timeout_seconds": timeout_value})
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_value,
        )
        elapsed = round(time.time() - started, 1)
        output = (proc.stdout or "").strip()
        if output:
            print(output[-8000:], flush=True)
        result = {"exit_code": proc.returncode, "elapsed_seconds": elapsed}
        log(f"<<< {name}", result)
        if check and proc.returncode != 0:
            raise RuntimeError(f"{name} failed with exit code {proc.returncode}")
        return result
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.time() - started, 1)
        output = (exc.stdout or "").strip() if isinstance(exc.stdout, str) else ""
        if output:
            print(output[-4000:], flush=True)
        result = {"exit_code": 124, "elapsed_seconds": elapsed, "timeout": True}
        log(f"<<< {name}", result)
        if check:
            raise RuntimeError(f"{name} timed out")
        return result


def accuracy_snapshot(db_path: Path, date_from: str, date_to: str, league: Optional[str] = "\u4e16\u754c\u676f") -> Dict[str, Any]:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        where = ["substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?"]
        params: List[Any] = [date_from, date_to]
        if league:
            where.append("COALESCE(lm.league_name_cn, '') = ?")
            params.append(league)
        rows = conn.execute(
            f"""
            SELECT v.play_type,
                   COUNT(*) AS total,
                   SUM(CASE WHEN v.is_correct THEN 1 ELSE 0 END) AS correct
            FROM lottery_validation v
            JOIN lottery_matches lm ON lm.lottery_match_id = v.lottery_match_id
            WHERE {' AND '.join(where)}
            GROUP BY v.play_type
            ORDER BY v.play_type
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    by_play = {}
    total = 0
    correct = 0
    for row in rows:
        count = int(row["total"] or 0)
        hits = int(row["correct"] or 0)
        by_play[row["play_type"]] = {
            "total": count,
            "correct": hits,
            "accuracy": round(hits * 100 / count, 1) if count else 0,
        }
        total += count
        correct += hits
    return {
        "date_from": date_from,
        "date_to": date_to,
        "league": league or "all",
        "total": total,
        "correct": correct,
        "accuracy": round(correct * 100 / total, 1) if total else 0,
        "by_play_type": by_play,
    }


def segment_steps(args: argparse.Namespace, start: str, end: str, deadline: Optional[datetime]) -> Dict[str, Any]:
    db_path = str(Path(args.db))
    oddsfe_db_path = str(Path(args.oddsfe_db))
    summary: Dict[str, Any] = {"from": start, "to": end, "steps": {}}

    summary["steps"]["football_data_wc"] = run_command(
        "football_data_wc",
        [
            "scripts/sync_football_data_wc.py",
            "--db",
            db_path,
            "--from",
            start,
            "--to",
            end,
            "--apply",
            "--max-matches",
            str(args.max_events),
        ],
        timeout_seconds=args.step_timeout,
        deadline=deadline,
    )
    summary["steps"]["event_details"] = run_command(
        "event_details",
        [
            "scripts/sync_oddsfe_event_details.py",
            "--db",
            db_path,
            "--from",
            start,
            "--to",
            end,
            "--apply",
            "--max-events",
            str(args.max_events),
            "--batches",
            "1",
            "--cache-minutes",
            "8",
            "--sleep",
            "0.12",
        ],
        timeout_seconds=args.step_timeout,
        deadline=deadline,
    )
    summary["steps"]["ou_lines"] = run_command(
        "ou_lines",
        [
            "scripts/sync_oddsfe_ou_lines.py",
            "--db",
            db_path,
            "--oddsfe-db",
            oddsfe_db_path,
            "--from",
            start,
            "--to",
            end,
            "--apply",
            "--fetch-live",
            "--max-events",
            str(args.max_events),
        ],
        timeout_seconds=args.step_timeout,
        deadline=deadline,
    )
    summary["steps"]["auto_gap"] = run_command(
        "auto_gap",
        [
            "scripts/run_auto_gap_segment.py",
            "--db",
            db_path,
            "--oddsfe-db",
            oddsfe_db_path,
            "--from",
            start,
            "--to",
            end,
            "--league",
            args.league or "",
            "--max-events",
            str(args.max_events),
            "--max-analysis",
            str(args.max_analysis),
            "--max-intelligence",
            str(args.max_intelligence),
            "--max-validation-dates",
            str(args.max_validation_dates),
        ],
        timeout_seconds=args.auto_gap_timeout,
        deadline=deadline,
    )
    summary["steps"]["validation"] = run_command(
        "validation",
        [
            "scripts/rebuild_lottery_validation.py",
            "--db",
            db_path,
            "--from",
            start,
            "--to",
            end,
            "--apply",
        ],
        timeout_seconds=args.validation_timeout,
        deadline=deadline,
    )
    summary["steps"]["team_match_facts"] = run_command(
        "team_match_facts_segment",
        [
            "scripts/build_team_match_facts.py",
            "--db",
            db_path,
            "--from",
            start,
            "--to",
            end,
            "--league",
            args.league or "",
            "--apply",
        ],
        timeout_seconds=args.facts_timeout,
        deadline=deadline,
    )
    summary["steps"]["audit_prediction"] = run_command(
        "audit_prediction_segment",
        [
            "scripts/audit_prediction_consistency.py",
            "--db",
            db_path,
            "--date-from",
            start,
            "--date-to",
            end,
            "--fail-on-issues",
        ],
        timeout_seconds=90,
        deadline=deadline,
    )
    summary["steps"]["audit_ou"] = run_command(
        "audit_ou_segment",
        [
            "scripts/audit_ou_goal_axis.py",
            "--db",
            db_path,
            "--date-from",
            start,
            "--date-to",
            end,
            "--fail-on-hard",
        ],
        timeout_seconds=90,
        deadline=deadline,
    )
    summary["failed_steps"] = [
        name
        for name, result in summary["steps"].items()
        if isinstance(result, dict)
        and not result.get("skipped")
        and int(result.get("exit_code") or 0) != 0
    ]
    log("SEGMENT DONE", summary)
    return summary


def round_learning(args: argparse.Namespace, deadline: Optional[datetime]) -> Dict[str, Any]:
    db_path = str(Path(args.db))
    summary: Dict[str, Any] = {"steps": {}}
    summary["steps"]["team_match_facts"] = run_command(
        "team_match_facts_full",
        [
            "scripts/build_team_match_facts.py",
            "--db",
            db_path,
            "--from",
            args.date_from,
            "--to",
            args.date_to,
            "--league",
            args.league or "",
            "--apply",
        ],
        timeout_seconds=args.facts_timeout,
        deadline=deadline,
    )
    summary["steps"]["ou_calibration"] = run_command(
        "ou_calibration",
        ["scripts/build_ou_line_calibration.py", "--db", db_path, "--min-samples-to-print", "1"],
        timeout_seconds=180,
        deadline=deadline,
    )
    summary["steps"]["similar_cases"] = run_command(
        "similar_cases",
        [
            "scripts/build_similar_match_cases.py",
            "--db",
            db_path,
            "--play-type",
            "spf,rqspf,ou",
        ],
        timeout_seconds=300,
        deadline=deadline,
    )
    summary["steps"]["error_diagnosis"] = run_command(
        "error_diagnosis",
        [
            "scripts/diagnose_prediction_errors.py",
            "--db",
            db_path,
            "--from",
            args.date_from,
            "--to",
            args.date_to,
            "--league",
            args.league or "",
            "--version-tag",
            f"auto_loop_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "--apply",
            "--summary-only",
        ],
        timeout_seconds=180,
        deadline=deadline,
    )
    learning_command = [
        "scripts/run_learning_refresh.py",
        "--db",
        db_path,
        "--days",
        str(args.learning_days),
        "--min-samples",
        str(args.learning_min_samples),
    ]
    if not args.apply_guarded_learning:
        learning_command.append("--dry-run")
    summary["steps"]["guarded_learning"] = run_command(
        "guarded_learning",
        learning_command,
        timeout_seconds=180,
        deadline=deadline,
    )
    summary["steps"]["future_reanalysis"] = run_command(
        "future_reanalysis_after_learning",
        [
            "scripts/reanalyze_unstarted_after_learning.py",
            "--db",
            db_path,
            "--oddsfe-db",
            str(Path(args.oddsfe_db)),
            "--from",
            args.date_from,
            "--to",
            args.date_to,
            "--league",
            args.league or "",
            "--limit",
            str(args.max_analysis),
            "--trigger-source",
            "segmented_loop_post_learning",
        ],
        timeout_seconds=240,
        deadline=deadline,
    )
    summary["steps"]["audit_health"] = run_command(
        "audit_health",
        [
            "scripts/audit_auto_loop_health.py",
            "--db",
            db_path,
            "--date-from",
            args.date_from,
            "--date-to",
            args.date_to,
            "--league",
            args.league or "",
        ],
        timeout_seconds=120,
        deadline=deadline,
    )
    summary["steps"]["audit_prediction_full"] = run_command(
        "audit_prediction_full",
        [
            "scripts/audit_prediction_consistency.py",
            "--db",
            db_path,
            "--date-from",
            args.date_from,
            "--date-to",
            args.date_to,
            "--league",
            args.league or "",
            "--fail-on-issues",
        ],
        timeout_seconds=120,
        deadline=deadline,
    )
    summary["steps"]["audit_ou_full"] = run_command(
        "audit_ou_full",
        [
            "scripts/audit_ou_goal_axis.py",
            "--db",
            db_path,
            "--date-from",
            args.date_from,
            "--date-to",
            args.date_to,
            "--league",
            args.league or "",
            "--fail-on-hard",
        ],
        timeout_seconds=120,
        deadline=deadline,
    )
    snapshot = accuracy_snapshot(Path(args.db), args.date_from, args.date_to, args.league)
    summary["accuracy_snapshot"] = snapshot
    log("ACCURACY SNAPSHOT", snapshot)
    return summary


def run(args: argparse.Namespace) -> Dict[str, Any]:
    deadline = resolve_deadline(args.deadline, args.max_minutes)
    segments = build_segments(args.date_from, args.date_to, args.segment_days)
    log(
        "SEGMENTED LOOP START",
        {
            "db": args.db,
            "oddsfe_db": args.oddsfe_db,
            "date_from": args.date_from,
            "date_to": args.date_to,
            "segment_days": args.segment_days,
            "segments": segments,
            "deadline": deadline.isoformat(timespec="seconds") if deadline else None,
            "max_iterations": args.max_iterations,
        },
    )

    iterations: List[Dict[str, Any]] = []
    iteration_index = 0
    while True:
        if args.max_iterations and iteration_index >= args.max_iterations:
            break
        if should_stop(deadline):
            break
        iteration_index += 1
        iteration: Dict[str, Any] = {"iteration": iteration_index, "segments": []}
        log(f"===== iteration {iteration_index} =====")
        for start, end in segments:
            if should_stop(deadline) or not has_budget(deadline, args.min_segment_seconds):
                log(
                    "STOP before next segment",
                    {
                        "next_segment": [start, end],
                        "seconds_left": round(time_left(deadline) or 0, 1) if deadline else None,
                        "min_segment_seconds": args.min_segment_seconds,
                    },
                )
                break
            iteration["segments"].append(segment_steps(args, start, end, deadline))
            if args.sleep_between_segments > 0 and not should_stop(deadline):
                time.sleep(args.sleep_between_segments)
        if not should_stop(deadline) and has_budget(deadline, args.min_learning_seconds):
            iteration["learning"] = round_learning(args, deadline)
        elif not should_stop(deadline):
            log(
                "SKIP round learning",
                {
                    "reason": "not_enough_time_budget",
                    "seconds_left": round(time_left(deadline) or 0, 1) if deadline else None,
                    "min_learning_seconds": args.min_learning_seconds,
                },
            )
        iterations.append(iteration)
        if args.once:
            break
        if args.sleep_between_iterations > 0 and not should_stop(deadline):
            time.sleep(args.sleep_between_iterations)

    result = {
        "success": True,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "deadline": deadline.isoformat(timespec="seconds") if deadline else None,
        "iterations": len(iterations),
        "segment_count": len(segments),
        "accuracy_snapshot": accuracy_snapshot(Path(args.db), args.date_from, args.date_to, args.league),
    }
    log("SEGMENTED LOOP FINISH", result)
    return result


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to football_v2.db")
    parser.add_argument("--oddsfe-db", default=str(DEFAULT_ODDSFE_DB), help="Path to oddsfe_merged.db")
    parser.add_argument("--from", dest="date_from", default="2026-06-11", help="Start Beijing date")
    parser.add_argument("--to", dest="date_to", default="2026-07-19", help="End Beijing date")
    parser.add_argument("--league", default="\u4e16\u754c\u676f", help="Optional league filter for audits/snapshots; empty means all")
    parser.add_argument("--segment-days", type=int, default=4, help="Days per segment")
    parser.add_argument("--max-events", type=int, default=8, help="Max events per fetch step")
    parser.add_argument("--max-analysis", type=int, default=16, help="Max analyses per auto-gap segment")
    parser.add_argument("--max-intelligence", type=int, default=8, help="Max intelligence packages per segment")
    parser.add_argument("--max-validation-dates", type=int, default=4, help="Max validation dates per auto-gap segment")
    parser.add_argument("--step-timeout", type=int, default=420, help="Timeout per collection step")
    parser.add_argument("--auto-gap-timeout", type=int, default=540, help="Timeout for each auto-gap segment subprocess")
    parser.add_argument("--validation-timeout", type=int, default=420, help="Timeout per validation rebuild step")
    parser.add_argument("--facts-timeout", type=int, default=180, help="Timeout per team facts build step")
    parser.add_argument("--learning-days", type=int, default=30, help="Window for guarded parameter learning")
    parser.add_argument("--learning-min-samples", type=int, default=10, help="Minimum samples before guarded learning changes parameters")
    parser.add_argument("--apply-guarded-learning", action="store_true", help="Allow automatic learning to write model weight changes")
    parser.add_argument("--sleep-between-segments", type=float, default=3)
    parser.add_argument("--sleep-between-iterations", type=float, default=90)
    parser.add_argument("--min-segment-seconds", type=int, default=90, help="Do not start a new segment with less time left")
    parser.add_argument("--min-learning-seconds", type=int, default=240, help="Do not start round learning with less time left")
    parser.add_argument("--deadline", default=None, help="Local HH:MM or ISO datetime deadline")
    parser.add_argument("--max-minutes", type=float, default=None, help="Alternative relative deadline")
    parser.add_argument("--max-iterations", type=int, default=1)
    parser.add_argument("--once", action="store_true", help="Run one segmented pass")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
