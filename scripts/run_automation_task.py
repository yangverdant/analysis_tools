"""Run one automation-center task in an isolated subprocess."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DB = Path(os.environ.get("DB_PATH") or ROOT / "data" / "football_v2.db")
DEFAULT_ODDSFE_DB = Path(
    os.environ.get("ODDSFE_DB_PATH") or ROOT / "fetchers" / "odds_feed_api" / "oddsfe_merged.db"
)
SENTINEL = "AUTOMATION_TASK_JSON="

from backend.app.data_access.task_lock import clean_path_arg, inspect_task_lock  # noqa: E402


def emit(payload: Dict[str, Any]) -> None:
    print(SENTINEL + json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def run_event_details(args: argparse.Namespace) -> Dict[str, Any]:
    from backend.app.lottery.services.oddsfe_event_sync import OddsfeEventDetailSync

    return OddsfeEventDetailSync(args.db).run(
        args.date_from,
        args.date_to,
        apply=True,
        refresh=False,
        fetch_schedule=True,
        include_schedule_only=True,
        max_events=args.max_events,
        schedule_padding_days=1,
        cache_minutes=12,
        sleep_seconds=0.12,
        trigger_source=f"{args.trigger_source}_event_details",
    )


def run_football_data_wc(args: argparse.Namespace) -> Dict[str, Any]:
    from backend.app.lottery.services.football_data_wc_sync import FootballDataWorldCupSync

    return FootballDataWorldCupSync(args.db).run(
        args.date_from,
        args.date_to,
        apply=True,
        season=2026,
        overwrite_results=False,
        max_matches=args.max_events,
        trigger_source=f"{args.trigger_source}_football_data_wc",
    )


def run_ou_lines(args: argparse.Namespace) -> Dict[str, Any]:
    from backend.app.lottery.services.oddsfe_ou_line_sync import OddsfeOuLineSync

    return OddsfeOuLineSync(args.db, args.oddsfe_db).run(
        args.date_from,
        args.date_to,
        apply=True,
        fetch_live=args.fetch_live_ou,
        max_events=args.max_events,
        reanalyze=False,
        trigger_source=f"{args.trigger_source}_ou_lines",
    )


def run_intelligence(args: argparse.Namespace) -> Dict[str, Any]:
    from backend.app.intelligence.service import IntelligenceService

    return IntelligenceService(args.db).fill_gaps_logged(
        start_date=args.date_from,
        end_date=args.date_to,
        collectors=["injuries_suspensions", "team_news", "expected_lineup", "weather"],
        network=args.network_intelligence,
        force=False,
        include_optional=True,
        include_builtin=True,
        limit=args.max_intelligence,
        trigger_source=f"{args.trigger_source}_intelligence",
    )


def run_analysis(args: argparse.Namespace) -> Dict[str, Any]:
    from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner
    from backend.app.core.analyze import analyze_single

    if args.force:
        import sqlite3

        conn = sqlite3.connect(args.db, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            where = [
                "substr(COALESCE(beijing_time, match_date), 1, 10) BETWEEN ? AND ?",
                "home_team_id IS NOT NULL",
                "away_team_id IS NOT NULL",
            ]
            params: list[Any] = [args.date_from, args.date_to]
            if args.league:
                where.append("COALESCE(league_name_cn, '') = ?")
                params.append(args.league)
            params.append(args.max_analysis)
            rows = conn.execute(
                f"""
                SELECT lottery_match_id
                FROM lottery_matches
                WHERE {' AND '.join(where)}
                ORDER BY substr(COALESCE(beijing_time, match_date), 1, 10), match_time, lottery_match_id
                LIMIT ?
                """,
                params,
            ).fetchall()
        finally:
            conn.close()

        analyzed = []
        failed = []
        for row in rows:
            match_id = str(row["lottery_match_id"])
            try:
                report = analyze_single(args.db, match_id)
                if report:
                    analyzed.append(match_id)
                else:
                    failed.append({"lottery_match_id": match_id, "error": "empty_report"})
            except Exception as exc:
                failed.append({"lottery_match_id": match_id, "error": str(exc)[:180]})
        return {
            "success": True,
            "forced": True,
            "targets": len(rows),
            "analyzed": len(analyzed),
            "failed": len(failed),
            "analyzed_ids": analyzed[:20],
            "failed_examples": failed[:8],
        }

    return LotteryAutoGapRunner(args.db, args.oddsfe_db)._analyze_missing_or_stale(
        args.date_from,
        args.date_to,
        limit=args.max_analysis,
        league=args.league or None,
    )


def _prediction_consistency_audit(args: argparse.Namespace, *, limit: int = 100) -> Dict[str, Any]:
    import sqlite3
    from scripts.model_change_gate import consistency_audit

    conn = sqlite3.connect(args.db, timeout=60)
    conn.row_factory = sqlite3.Row
    try:
        return consistency_audit(
            conn,
            date_from=args.date_from,
            date_to=args.date_to,
            league=args.league or "",
            limit=limit,
        )
    finally:
        conn.close()


def _remediate_prediction_consistency(args: argparse.Namespace, issues: list[Dict[str, Any]]) -> Dict[str, Any]:
    import sqlite3
    from backend.app.core.analyze import analyze_single
    from backend.app.core.validate import _validate_predictions

    match_ids = []
    seen = set()
    for issue in issues:
        match_id = str(issue.get("lottery_match_id") or "").strip()
        if match_id and match_id not in seen:
            seen.add(match_id)
            match_ids.append(match_id)
    if not match_ids:
        return {"attempted": False, "reason": "no_issue_match_ids"}

    limited_ids = match_ids[: max(1, int(args.max_analysis or 10))]
    analyzed = []
    failed = []
    for match_id in limited_ids:
        try:
            report = analyze_single(args.db, match_id)
            if report:
                analyzed.append(match_id)
            else:
                failed.append({"lottery_match_id": match_id, "error": "empty_report"})
        except Exception as exc:
            failed.append({"lottery_match_id": match_id, "error": str(exc)[:180]})

    conn = sqlite3.connect(args.db, timeout=60)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"""
            SELECT DISTINCT substr(COALESCE(beijing_time, match_date), 1, 10) AS match_date
            FROM lottery_matches
            WHERE lottery_match_id IN ({",".join(["?"] * len(limited_ids))})
              AND substr(COALESCE(beijing_time, match_date), 1, 10) IS NOT NULL
            ORDER BY match_date
            """,
            limited_ids,
        ).fetchall()
        dates = [str(row["match_date"]) for row in rows if row["match_date"]]
    finally:
        conn.close()

    validation = {}
    if dates:
        try:
            validation = _validate_predictions(args.db, dates)
        except Exception as exc:
            validation = {"error": str(exc)[:180]}

    return {
        "attempted": True,
        "issue_matches": len(match_ids),
        "limited": len(limited_ids) < len(match_ids),
        "targets": len(limited_ids),
        "analyzed": len(analyzed),
        "failed": len(failed),
        "analyzed_ids": analyzed[:20],
        "failed_examples": failed[:8],
        "validation": validation,
    }


def run_result_audit(args: argparse.Namespace) -> Dict[str, Any]:
    from backend.app.lottery.services.result_consistency import run_result_consistency_audit

    result = run_result_consistency_audit(
        args.db,
        args.date_from,
        args.date_to,
        apply=True,
        league=args.league or None,
        trigger_source=f"{args.trigger_source}_result_audit",
    )
    prediction_consistency = _prediction_consistency_audit(args)
    hard_issues = int(prediction_consistency.get("hard_issues") or 0)
    parse_errors = int(prediction_consistency.get("parse_errors") or 0)
    if hard_issues and not parse_errors:
        result["prediction_consistency_initial"] = prediction_consistency
        result["prediction_remediation"] = _remediate_prediction_consistency(
            args,
            prediction_consistency.get("issue_preview") or [],
        )
        prediction_consistency = _prediction_consistency_audit(args)
        hard_issues = int(prediction_consistency.get("hard_issues") or 0)
        parse_errors = int(prediction_consistency.get("parse_errors") or 0)
    result["prediction_consistency"] = prediction_consistency
    result["prediction_consistency_ok"] = hard_issues == 0 and parse_errors == 0
    result["hard_prediction_issues"] = hard_issues
    result["prediction_parse_errors"] = parse_errors
    if hard_issues or parse_errors:
        result["success"] = False
        result["error"] = f"prediction consistency audit failed: hard_issues={hard_issues}, parse_errors={parse_errors}"
    return result


POST_PREDICTION_CONSISTENCY_TASKS = {
    "analysis",
    "play_consistency_gate",
    "bqc_full_axis_gate",
    "handicap_margin_gate",
    "national_ou_gate",
    "future_reanalysis",
}


def _attach_post_prediction_consistency(args: argparse.Namespace, payload: Dict[str, Any]) -> Dict[str, Any]:
    if args.task not in POST_PREDICTION_CONSISTENCY_TASKS:
        return payload
    if payload.get("success") is False:
        return payload

    consistency = _prediction_consistency_audit(args, limit=50)
    hard_issues = int(consistency.get("hard_issues") or 0)
    parse_errors = int(consistency.get("parse_errors") or 0)
    if hard_issues and not parse_errors:
        payload["post_prediction_consistency_initial"] = consistency
        payload["post_prediction_remediation"] = _remediate_prediction_consistency(
            args,
            consistency.get("issue_preview") or [],
        )
        consistency = _prediction_consistency_audit(args, limit=50)
        hard_issues = int(consistency.get("hard_issues") or 0)
        parse_errors = int(consistency.get("parse_errors") or 0)

    payload["post_prediction_consistency"] = consistency
    payload["post_prediction_consistency_ok"] = hard_issues == 0 and parse_errors == 0
    payload["post_prediction_hard_issues"] = hard_issues
    payload["post_prediction_parse_errors"] = parse_errors
    if hard_issues or parse_errors:
        payload["success"] = False
        payload["error"] = f"post prediction consistency audit failed: hard_issues={hard_issues}, parse_errors={parse_errors}"
    return payload


def run_validation(args: argparse.Namespace) -> Dict[str, Any]:
    from backend.app.core.validate import validate
    from backend.app.core.agent.client import AnalystAgent

    agent = None
    try:
        agent = AnalystAgent(args.db)
    except Exception:
        pass

    result = validate(state=None, db_path=args.db, agent=agent)

    # Mark revalidation processed
    try:
        from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner, date_list
        dates = date_list(args.date_from, args.date_to)[: args.max_validation_dates]
        runner = LotteryAutoGapRunner(args.db, args.oddsfe_db)
        result["queued_revalidation"] = runner._mark_revalidation_processed(dates)
    except Exception as e:
        result["revalidation_mark_error"] = str(e)

    return result


def run_learning(args: argparse.Namespace) -> Dict[str, Any]:
    from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner

    return LotteryAutoGapRunner(args.db, args.oddsfe_db)._refresh_learning(
        args.date_from,
        args.date_to,
        league=args.league or None,
    )


def _wait_for_learning_lock_release(
    db_path: str,
    *,
    wait_seconds: int,
    poll_seconds: float,
) -> Dict[str, Any]:
    waited = 0.0
    last_state = inspect_task_lock("learning", db_path)
    while last_state.get("locked") and not last_state.get("stale") and waited < max(0, int(wait_seconds)):
        sleep_for = min(max(poll_seconds, 0.5), max(0, int(wait_seconds)) - waited)
        if sleep_for <= 0:
            break
        time.sleep(sleep_for)
        waited += sleep_for
        last_state = inspect_task_lock("learning", db_path)
    return {
        "waited_seconds": round(waited, 1),
        "lock_cleared": not bool(last_state.get("locked")) or bool(last_state.get("stale")),
        "lock_state": last_state,
    }


def run_future_reanalysis(args: argparse.Namespace) -> Dict[str, Any]:
    from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner

    wait_info = _wait_for_learning_lock_release(
        args.db,
        wait_seconds=args.future_reanalysis_wait_seconds,
        poll_seconds=args.future_reanalysis_poll_seconds,
    )
    result = LotteryAutoGapRunner(args.db, args.oddsfe_db).reanalyze_unstarted_after_learning(
        args.date_from,
        args.date_to,
        league=args.league or None,
        limit=args.max_analysis,
        trigger_source=f"{args.trigger_source}_future_reanalysis",
    )
    result["learning_wait"] = wait_info
    if not wait_info.get("lock_cleared"):
        result["learning_wait"]["proceeded_with_running_learning"] = True
    return result



def _national_ou_args(args: argparse.Namespace, *, apply: bool, refresh_notes: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        db=args.db,
        fact_table=args.national_ou_fact_table,
        date_from=args.date_from,
        date_to=args.date_to,
        league=args.league or "世界杯",
        report_type=args.national_ou_report_type,
        limit=args.national_ou_limit,
        min_sample=args.national_ou_min_sample,
        band=args.national_ou_band,
        apply=apply,
        rollback_on_worse=True,
        rebuild_validation=args.national_ou_rebuild_validation,
        refresh_notes=refresh_notes,
        examples_limit=args.national_ou_examples_limit,
    )


def _compact_national_ou_result(result: Dict[str, Any], *, skipped: bool = False, reason: str = "") -> Dict[str, Any]:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    apply_result = result.get("apply_result") if isinstance(result.get("apply_result"), dict) else {}
    validation = result.get("validation_result") if isinstance(result.get("validation_result"), dict) else {}
    payload = {
        "success": result.get("success", True),
        "skipped": skipped,
        "reason": reason or result.get("abort_reason") or result.get("reason"),
        "accepted": result.get("accepted"),
        "fact_table": result.get("fact_table"),
        "reports_checked": result.get("reports_checked"),
        "changes": int(summary.get("changes") or 0),
        "improved": int(summary.get("improved") or 0),
        "regressed": int(summary.get("regressed") or 0),
        "metadata_only": int(summary.get("metadata_only") or 0),
        "scored": int(summary.get("scored") or 0),
        "before_correct": int(summary.get("before_correct") or 0),
        "after_correct": int(summary.get("after_correct") or 0),
        "delta_correct": int(summary.get("delta_correct") or 0),
        "changed_reports": int(apply_result.get("reports") or 0),
        "prediction_rows": int(apply_result.get("prediction_rows") or 0),
        "backup_path": result.get("backup_path"),
        "changed_dates": result.get("changed_dates") or [],
        "validated": int(validation.get("validated") or 0),
        "validation_accuracy": validation.get("accuracy"),
    }
    return {key: value for key, value in payload.items() if value not in (None, "", [])}


def run_national_ou_gate(args: argparse.Namespace) -> Dict[str, Any]:
    from scripts.apply_national_ou_conflict_gate import connect, run as run_gate, table_exists

    with connect(Path(args.db)) as conn:
        if not table_exists(conn, args.national_ou_fact_table):
            return {
                "success": True,
                "skipped": True,
                "reason": "national_reference_fact_table_missing",
                "fact_table": args.national_ou_fact_table,
            }

    dry_result = run_gate(_national_ou_args(args, apply=False))
    dry_summary = dry_result.get("summary") if isinstance(dry_result.get("summary"), dict) else {}
    if int(dry_summary.get("changes") or 0) <= 0:
        return _compact_national_ou_result(dry_result, skipped=True, reason="no_eligible_ou_conflicts")
    if int(dry_summary.get("delta_correct") or 0) < 0:
        return _compact_national_ou_result(dry_result, skipped=True, reason="dry_run_delta_worse")

    apply_result = run_gate(_national_ou_args(args, apply=True))
    compact = _compact_national_ou_result(apply_result)
    compact["dry_run"] = {
        "changes": int(dry_summary.get("changes") or 0),
        "improved": int(dry_summary.get("improved") or 0),
        "regressed": int(dry_summary.get("regressed") or 0),
        "delta_correct": int(dry_summary.get("delta_correct") or 0),
    }
    return compact


def _play_consistency_args(args: argparse.Namespace, *, apply: bool) -> argparse.Namespace:
    return argparse.Namespace(
        db=args.db,
        date_from=args.date_from,
        date_to=args.date_to,
        league=args.league or "世界杯",
        report_type=args.play_consistency_report_type,
        apply=apply,
        rollback_on_worse=True,
        rebuild_validation=args.play_consistency_rebuild_validation,
        examples_limit=args.play_consistency_examples_limit,
    )


def _compact_play_consistency_result(result: Dict[str, Any], *, skipped: bool = False, reason: str = "") -> Dict[str, Any]:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    apply_result = result.get("apply_result") if isinstance(result.get("apply_result"), dict) else {}
    validation = result.get("validation_result") if isinstance(result.get("validation_result"), dict) else {}
    return {
        "success": result.get("success", True),
        "skipped": skipped,
        "reason": reason or result.get("abort_reason") or result.get("reason"),
        "accepted": result.get("accepted"),
        "reports_checked": result.get("reports_checked"),
        "changes": int(summary.get("changes") or 0),
        "changed_reports": int(apply_result.get("reports") or 0),
        "prediction_rows": int(apply_result.get("prediction_rows") or 0),
        "improved": int(summary.get("improved") or 0),
        "regressed": int(summary.get("regressed") or 0),
        "scored": int(summary.get("scored") or 0),
        "before_correct": int(summary.get("before_correct") or 0),
        "after_correct": int(summary.get("after_correct") or 0),
        "delta_correct": int(summary.get("delta_correct") or 0),
        "by_play_type": summary.get("by_play_type") or {},
        "backup_path": result.get("backup_path"),
        "changed_dates": result.get("changed_dates") or [],
        "validated": int(validation.get("validated") or 0),
        "validation_accuracy": validation.get("accuracy"),
    }


def run_play_consistency_gate(args: argparse.Namespace) -> Dict[str, Any]:
    from scripts.apply_play_consistency_gate import run as run_gate

    dry_result = run_gate(_play_consistency_args(args, apply=False))
    dry_summary = dry_result.get("summary") if isinstance(dry_result.get("summary"), dict) else {}
    if int(dry_summary.get("changes") or 0) <= 0:
        return _compact_play_consistency_result(dry_result, skipped=True, reason="no_hard_play_conflicts")
    if int(dry_summary.get("delta_correct") or 0) < 0:
        return _compact_play_consistency_result(dry_result, skipped=True, reason="dry_run_delta_worse")

    apply_result = run_gate(_play_consistency_args(args, apply=True))
    compact = _compact_play_consistency_result(apply_result)
    compact["dry_run"] = {
        "changes": int(dry_summary.get("changes") or 0),
        "improved": int(dry_summary.get("improved") or 0),
        "regressed": int(dry_summary.get("regressed") or 0),
        "delta_correct": int(dry_summary.get("delta_correct") or 0),
    }
    return compact


def _bqc_full_axis_gate_args(args: argparse.Namespace, *, apply: bool) -> argparse.Namespace:
    return argparse.Namespace(
        db=args.db,
        date_from=args.date_from,
        date_to=args.date_to,
        league=args.league or "世界杯",
        report_type=args.bqc_full_axis_gate_report_type,
        min_spf_gap=args.bqc_full_axis_gate_min_spf_gap,
        min_expected_margin=args.bqc_full_axis_gate_min_expected_margin,
        max_draw_probability=args.bqc_full_axis_gate_max_draw_probability,
        apply=apply,
        rollback_on_worse=True,
        rebuild_validation=args.bqc_full_axis_gate_rebuild_validation,
        examples_limit=args.bqc_full_axis_gate_examples_limit,
    )


def _compact_bqc_full_axis_gate_result(result: Dict[str, Any], *, skipped: bool = False, reason: str = "") -> Dict[str, Any]:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    apply_result = result.get("apply_result") if isinstance(result.get("apply_result"), dict) else {}
    validation = result.get("validation_result") if isinstance(result.get("validation_result"), dict) else {}
    return {
        "success": result.get("success", True),
        "task": "bqc_full_axis_gate",
        "skipped": skipped,
        "reason": reason or result.get("abort_reason") or result.get("reason"),
        "accepted": result.get("accepted"),
        "reports_checked": result.get("reports_checked"),
        "changes": int(summary.get("changes") or 0),
        "changed_reports": int(apply_result.get("reports") or 0),
        "prediction_rows": int(apply_result.get("prediction_rows") or 0),
        "improved": int(summary.get("improved") or 0),
        "regressed": int(summary.get("regressed") or 0),
        "delta_correct": int(summary.get("delta_correct") or 0),
        "full_improved": int(summary.get("full_improved") or 0),
        "full_regressed": int(summary.get("full_regressed") or 0),
        "full_delta_correct": int(summary.get("full_delta_correct") or 0),
        "by_reason": (summary.get("by_reason") or [])[:8],
        "backup_path": result.get("backup_path"),
        "changed_dates": result.get("changed_dates") or [],
        "validated": int(validation.get("validated") or 0),
        "validation_accuracy": validation.get("accuracy"),
    }


def run_bqc_full_axis_gate(args: argparse.Namespace) -> Dict[str, Any]:
    from scripts.apply_bqc_full_axis_gate import run as run_gate

    dry_result = run_gate(_bqc_full_axis_gate_args(args, apply=False))
    dry_summary = dry_result.get("summary") if isinstance(dry_result.get("summary"), dict) else {}
    if int(dry_summary.get("changes") or 0) <= 0:
        return _compact_bqc_full_axis_gate_result(dry_result, skipped=True, reason="no_bqc_full_axis_gate_signal")
    if int(dry_summary.get("delta_correct") or 0) < 0 or int(dry_summary.get("full_delta_correct") or 0) < 0:
        return _compact_bqc_full_axis_gate_result(dry_result, skipped=True, reason="dry_run_delta_worse")

    apply_result = run_gate(_bqc_full_axis_gate_args(args, apply=True))
    compact = _compact_bqc_full_axis_gate_result(apply_result)
    compact["dry_run"] = {
        "changes": int(dry_summary.get("changes") or 0),
        "improved": int(dry_summary.get("improved") or 0),
        "regressed": int(dry_summary.get("regressed") or 0),
        "delta_correct": int(dry_summary.get("delta_correct") or 0),
        "full_delta_correct": int(dry_summary.get("full_delta_correct") or 0),
    }
    return compact


def run_prediction_error_review(args: argparse.Namespace) -> Dict[str, Any]:
    from scripts.diagnose_prediction_errors import run as run_diagnosis

    review_args = argparse.Namespace(
        db=args.db,
        date_from=args.date_from,
        date_to=args.date_to,
        league=args.league or "",
        match_nums="",
        limit=args.prediction_error_limit,
        version_tag=args.prediction_error_version_tag,
        apply=True,
        compact=False,
        summary_only=True,
    )
    result = run_diagnosis(review_args)
    consistency = result.get("validation_consistency") if isinstance(result.get("validation_consistency"), dict) else {}
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    payload = {
        "success": bool(result.get("success")),
        "task": "prediction_error_review",
        "mode": result.get("mode"),
        "version_tag": result.get("version_tag"),
        "saved": int(result.get("saved") or 0),
        "matches": int(summary.get("matches") or 0),
        "plays": int(summary.get("plays") or 0),
        "wrong": int(summary.get("wrong") or 0),
        "by_play_type": summary.get("by_play_type") or {},
        "top_error_categories": (summary.get("top_error_categories") or [])[:8],
        "collection_actions": (summary.get("collection_actions") or [])[:8],
        "model_actions": (summary.get("model_actions") or [])[:8],
        "validation_consistency_ok": bool(consistency.get("ok")),
        "validation_mismatches": (consistency.get("mismatches") or [])[:8],
    }
    if not result.get("success"):
        payload["error"] = "prediction_error_review_validation_mismatch"
    return payload


def run_bqc_half_time_profile(args: argparse.Namespace) -> Dict[str, Any]:
    from scripts.audit_bqc_half_time_profiles import run as run_bqc_profile

    profile_args = argparse.Namespace(
        db=args.db,
        date_from=args.date_from,
        date_to=args.date_to,
        league=args.league or "",
        match_nums="",
        report_type=args.bqc_profile_report_type,
        fact_table=args.bqc_profile_fact_table,
        sample_limit=args.bqc_profile_sample_limit,
        min_sample=args.bqc_profile_min_sample,
        draw_edge=args.bqc_profile_draw_edge,
        draw_threshold=args.bqc_profile_draw_threshold,
        max_draw_edge=args.bqc_profile_max_draw_edge,
        limit=args.bqc_profile_limit,
        version_tag=args.bqc_profile_version_tag,
        apply=True,
        finished_only=True,
        summary_only=True,
        examples_limit=args.bqc_profile_examples_limit,
    )
    result = run_bqc_profile(profile_args)
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    return {
        "success": bool(result.get("success", True)),
        "task": "bqc_half_time_profile",
        "mode": result.get("mode"),
        "version_tag": result.get("version_tag"),
        "fact_table": result.get("fact_table"),
        "targets": int(summary.get("targets") or 0),
        "eligible": int(summary.get("eligible") or 0),
        "scored_matches": int(summary.get("scored_matches") or 0),
        "changed_candidates": int(summary.get("changed_candidates") or 0),
        "current_correct": int(summary.get("current_correct") or 0),
        "profile_correct": int(summary.get("profile_correct") or 0),
        "delta_correct": int(summary.get("delta_correct") or 0),
        "changed_improved": int(summary.get("changed_improved") or 0),
        "changed_regressed": int(summary.get("changed_regressed") or 0),
        "half_axis_errors": int(summary.get("half_axis_errors") or 0),
        "full_axis_errors": int(summary.get("full_axis_errors") or 0),
        "path_flips": int(summary.get("path_flips") or 0),
        "patterns": (summary.get("patterns") or [])[:8],
        "profile_roles": (summary.get("profile_roles") or [])[:8],
        "saved_profiles": int(result.get("saved_profiles") or 0),
        "saved_audits": int(result.get("saved_audits") or 0),
        "saved_patterns": int(result.get("saved_patterns") or 0),
        "skipped": bool(result.get("skipped")),
        "reason": result.get("reason"),
    }


def run_bqc_full_time_axis(args: argparse.Namespace) -> Dict[str, Any]:
    from scripts.audit_bqc_full_time_axis import run as run_bqc_full_axis

    axis_args = argparse.Namespace(
        db=args.db,
        date_from=args.date_from,
        date_to=args.date_to,
        league=args.league or "",
        match_nums="",
        report_type=args.bqc_full_axis_report_type,
        version_tag=args.bqc_full_axis_version_tag,
        limit=args.bqc_full_axis_limit,
        apply=True,
        summary_only=True,
        examples_limit=args.bqc_full_axis_examples_limit,
        only_bqc_full_miss=not args.bqc_full_axis_all_bqc,
    )
    result = run_bqc_full_axis(axis_args)
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    return {
        "success": bool(result.get("success", True)),
        "task": "bqc_full_time_axis",
        "mode": result.get("mode"),
        "version_tag": result.get("version_tag"),
        "targets": int(summary.get("targets") or 0),
        "scored_matches": int(summary.get("scored_matches") or 0),
        "bqc_full_correct": int(summary.get("bqc_full_correct") or 0),
        "spf_correct": int(summary.get("spf_correct") or 0),
        "score_top_correct": int(summary.get("score_top_correct") or 0),
        "score_weighted_correct": int(summary.get("score_weighted_correct") or 0),
        "drivers": (summary.get("drivers") or [])[:8],
        "risk_tags": (summary.get("risk_tags") or [])[:8],
        "saved": int(result.get("saved") or 0),
    }


def run_handicap_margin_axis(args: argparse.Namespace) -> Dict[str, Any]:
    from scripts.apply_handicap_margin_axis import run as run_handicap_axis

    axis_args = argparse.Namespace(
        db=args.db,
        date_from=args.date_from,
        date_to=args.date_to,
        league=args.league or "",
        match_nums="",
        report_type=args.handicap_margin_report_type,
        limit=args.handicap_margin_limit,
        score_limit=args.handicap_margin_score_limit,
        expected_edge=args.handicap_margin_expected_edge,
        apply=True,
        summary_only=True,
        examples_limit=args.handicap_margin_examples_limit,
    )
    result = run_handicap_axis(axis_args)
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    return {
        "success": bool(result.get("success", True)),
        "task": "handicap_margin_axis",
        "mode": result.get("mode"),
        "version_tag": result.get("version_tag"),
        "reports_checked": int(result.get("reports_checked") or 0),
        "saved": int(result.get("saved") or 0),
        "targets": int(summary.get("targets") or 0),
        "scored_matches": int(summary.get("scored_matches") or 0),
        "current_correct": int(summary.get("current_correct") or 0),
        "current_accuracy": summary.get("current_accuracy"),
        "expected_axis": summary.get("expected_axis") or {},
        "score_axis": summary.get("score_axis") or {},
        "market_axis": summary.get("market_axis") or {},
        "conditional_axis": summary.get("conditional_axis") or {},
        "top_categories": (summary.get("top_categories") or [])[:8],
        "top_tags": (summary.get("top_tags") or [])[:8],
        "model_actions": (summary.get("model_actions") or [])[:8],
        "parse_errors": (result.get("parse_errors") or [])[:5],
    }


def _handicap_margin_gate_args(args: argparse.Namespace, *, apply: bool) -> argparse.Namespace:
    return argparse.Namespace(
        db=args.db,
        date_from=args.date_from,
        date_to=args.date_to,
        league=args.league or "\u4e16\u754c\u676f",
        match_nums="",
        report_type=args.handicap_margin_gate_report_type,
        limit=args.handicap_margin_gate_limit,
        min_home_tail_gap=args.handicap_margin_gate_min_home_tail_gap,
        min_market_gap=args.handicap_margin_gate_min_market_gap,
        finished_only=True,
        apply=apply,
        rollback_on_worse=True,
        require_no_regression=True,
        rebuild_validation=args.handicap_margin_gate_rebuild_validation,
        examples_limit=args.handicap_margin_gate_examples_limit,
    )


def _compact_handicap_margin_gate_result(result: Dict[str, Any], *, skipped: bool = False, reason: str = "") -> Dict[str, Any]:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    apply_result = result.get("apply_result") if isinstance(result.get("apply_result"), dict) else {}
    validation = result.get("validation_result") if isinstance(result.get("validation_result"), dict) else {}
    return {
        "success": result.get("success", True),
        "task": "handicap_margin_gate",
        "skipped": skipped,
        "reason": reason or result.get("abort_reason") or result.get("reason"),
        "accepted": result.get("accepted"),
        "reports_checked": result.get("reports_checked"),
        "changes": int(summary.get("changes") or 0),
        "changed_reports": int(apply_result.get("reports") or 0),
        "prediction_rows": int(apply_result.get("prediction_rows") or 0),
        "improved": int(summary.get("improved") or 0),
        "regressed": int(summary.get("regressed") or 0),
        "scored": int(summary.get("scored") or 0),
        "before_correct": int(summary.get("before_correct") or 0),
        "after_correct": int(summary.get("after_correct") or 0),
        "delta_correct": int(summary.get("delta_correct") or 0),
        "by_reason": summary.get("by_reason") or {},
        "backup_path": result.get("backup_path"),
        "changed_dates": result.get("changed_dates") or [],
        "validated": int(validation.get("validated") or 0),
        "validation_accuracy": validation.get("accuracy"),
    }


def run_handicap_margin_gate(args: argparse.Namespace) -> Dict[str, Any]:
    from scripts.apply_handicap_margin_gate import run as run_gate

    dry_result = run_gate(_handicap_margin_gate_args(args, apply=False))
    dry_summary = dry_result.get("summary") if isinstance(dry_result.get("summary"), dict) else {}
    if int(dry_summary.get("changes") or 0) <= 0:
        return _compact_handicap_margin_gate_result(dry_result, skipped=True, reason="no_handicap_margin_gate_signal")
    if int(dry_summary.get("delta_correct") or 0) < 0:
        return _compact_handicap_margin_gate_result(dry_result, skipped=True, reason="dry_run_delta_worse")
    if int(dry_summary.get("regressed") or 0) > 0:
        return _compact_handicap_margin_gate_result(dry_result, skipped=True, reason="dry_run_has_regression")

    apply_result = run_gate(_handicap_margin_gate_args(args, apply=True))
    compact = _compact_handicap_margin_gate_result(apply_result)
    compact["dry_run"] = {
        "changes": int(dry_summary.get("changes") or 0),
        "improved": int(dry_summary.get("improved") or 0),
        "regressed": int(dry_summary.get("regressed") or 0),
        "delta_correct": int(dry_summary.get("delta_correct") or 0),
    }
    return compact


TASKS = {
    "football_data_wc": run_football_data_wc,
    "event_details": run_event_details,
    "ou_lines": run_ou_lines,
    "intelligence": run_intelligence,
    "result_audit": run_result_audit,
    "analysis": run_analysis,
    "play_consistency_gate": run_play_consistency_gate,
    "bqc_full_axis_gate": run_bqc_full_axis_gate,
    "handicap_margin_gate": run_handicap_margin_gate,
    "validation": run_validation,
    "national_ou_gate": run_national_ou_gate,
    "bqc_half_time_profile": run_bqc_half_time_profile,
    "bqc_full_time_axis": run_bqc_full_time_axis,
    "handicap_margin_axis": run_handicap_margin_axis,
    "prediction_error_review": run_prediction_error_review,
    "learning": run_learning,
    "future_reanalysis": run_future_reanalysis,
}


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=sorted(TASKS), required=True)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--oddsfe-db", default=str(DEFAULT_ODDSFE_DB))
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--to", dest="date_to", required=True)
    parser.add_argument("--league", default="")
    parser.add_argument("--max-events", type=int, default=6)
    parser.add_argument("--max-analysis", type=int, default=10)
    parser.add_argument("--max-intelligence", type=int, default=6)
    parser.add_argument("--max-validation-dates", type=int, default=1)
    parser.add_argument("--fetch-live-ou", action="store_true")
    parser.add_argument("--network-intelligence", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--trigger-source", default="automation_center")
    parser.add_argument("--national-ou-fact-table", default=os.environ.get("FOOTBALL_NATIONAL_REFERENCE_FACT_TABLE", "team_match_facts"))
    parser.add_argument("--national-ou-report-type", default="prediction")
    parser.add_argument("--national-ou-limit", type=int, default=20)
    parser.add_argument("--national-ou-min-sample", type=int, default=16)
    parser.add_argument("--national-ou-band", type=float, default=0.25)
    parser.add_argument("--national-ou-examples-limit", type=int, default=8)
    parser.add_argument("--no-national-ou-rebuild-validation", dest="national_ou_rebuild_validation", action="store_false", default=True)
    parser.add_argument("--play-consistency-report-type", default="prediction")
    parser.add_argument("--play-consistency-examples-limit", type=int, default=8)
    parser.add_argument("--no-play-consistency-rebuild-validation", dest="play_consistency_rebuild_validation", action="store_false", default=True)
    parser.add_argument("--handicap-margin-gate-report-type", default="prediction")
    parser.add_argument("--handicap-margin-gate-limit", type=int, default=0)
    parser.add_argument("--handicap-margin-gate-min-home-tail-gap", type=float, default=0.02)
    parser.add_argument("--handicap-margin-gate-min-market-gap", type=float, default=0.18)
    parser.add_argument("--handicap-margin-gate-examples-limit", type=int, default=8)
    parser.add_argument("--no-handicap-margin-gate-rebuild-validation", dest="handicap_margin_gate_rebuild_validation", action="store_false", default=True)
    parser.add_argument("--bqc-full-axis-gate-report-type", default="prediction")
    parser.add_argument("--bqc-full-axis-gate-min-spf-gap", type=float, default=0.18)
    parser.add_argument("--bqc-full-axis-gate-min-expected-margin", type=float, default=0.50)
    parser.add_argument("--bqc-full-axis-gate-max-draw-probability", type=float, default=0.305)
    parser.add_argument("--bqc-full-axis-gate-examples-limit", type=int, default=8)
    parser.add_argument("--no-bqc-full-axis-gate-rebuild-validation", dest="bqc_full_axis_gate_rebuild_validation", action="store_false", default=True)
    parser.add_argument("--bqc-profile-fact-table", default=os.environ.get("FOOTBALL_BQC_PROFILE_FACT_TABLE", ""))
    parser.add_argument("--bqc-profile-report-type", default="prediction")
    parser.add_argument("--bqc-profile-sample-limit", type=int, default=40)
    parser.add_argument("--bqc-profile-min-sample", type=int, default=12)
    parser.add_argument("--bqc-profile-draw-edge", type=float, default=0.10)
    parser.add_argument("--bqc-profile-draw-threshold", type=float, default=0.62)
    parser.add_argument("--bqc-profile-max-draw-edge", type=float, default=0.18)
    parser.add_argument("--bqc-profile-limit", type=int, default=0)
    parser.add_argument("--bqc-profile-examples-limit", type=int, default=8)
    parser.add_argument("--bqc-profile-version-tag", default=os.environ.get("FOOTBALL_BQC_PROFILE_VERSION", "bqc_half_time_profile_v1"))
    parser.add_argument("--bqc-full-axis-report-type", default="prediction")
    parser.add_argument("--bqc-full-axis-limit", type=int, default=0)
    parser.add_argument("--bqc-full-axis-examples-limit", type=int, default=8)
    parser.add_argument("--bqc-full-axis-version-tag", default=os.environ.get("FOOTBALL_BQC_FULL_AXIS_VERSION", "bqc_full_time_axis_v1"))
    parser.add_argument("--bqc-full-axis-all-bqc", action="store_true")
    parser.add_argument("--handicap-margin-report-type", default="prediction")
    parser.add_argument("--handicap-margin-limit", type=int, default=0)
    parser.add_argument("--handicap-margin-score-limit", type=int, default=5)
    parser.add_argument("--handicap-margin-expected-edge", type=float, default=0.18)
    parser.add_argument("--handicap-margin-examples-limit", type=int, default=8)
    parser.add_argument("--prediction-error-limit", type=int, default=0)
    parser.add_argument("--prediction-error-version-tag", default=os.environ.get("FOOTBALL_PREDICTION_ERROR_VERSION", "prediction_error_review_v1"))
    parser.add_argument("--future-reanalysis-wait-seconds", type=int, default=120)
    parser.add_argument("--future-reanalysis-poll-seconds", type=float, default=3.0)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    args.db = clean_path_arg(args.db)
    args.oddsfe_db = clean_path_arg(args.oddsfe_db)
    try:
        payload = TASKS[args.task](args)
        if payload is None:
            payload = {}
        payload = _attach_post_prediction_consistency(args, payload)
        payload = {"success": payload.get("success", True), "task": args.task, **payload}
        emit(payload)
        return 0 if payload.get("success") is not False else 1
    except Exception as exc:
        emit({"success": False, "task": args.task, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
