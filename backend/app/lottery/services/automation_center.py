"""Parallel automation center for lottery data work.

The center is intentionally a coordinator, not another analyzer. It splits work
into small dated tasks, runs safe independent tasks concurrently, records every
task result, and keeps later waves moving even when one task fails.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from backend.app.data_access.foundation_dao import FoundationDAO
from backend.app.data_access.task_lock import exclusive_task_lock
from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner, date_list


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = Path(os.environ.get("DB_PATH") or ROOT / "data" / "football_v2.db")
DEFAULT_ODDSFE_DB = Path(
    os.environ.get("ODDSFE_DB_PATH") or ROOT / "fetchers" / "odds_feed_api" / "oddsfe_merged.db"
)
TASK_SENTINEL = "AUTOMATION_TASK_JSON="


@dataclass(frozen=True)
class AutomationTask:
    kind: str
    date_from: str
    date_to: str
    wave: int
    reason: str
    action_counts: Dict[str, int]

    @property
    def match_date(self) -> str:
        return self.date_from

    @property
    def key(self) -> str:
        return f"{self.wave}:{self.kind}:{self.date_from}:{self.date_to}"


def _today() -> datetime.date:
    return datetime.now().date()


def _future_reanalysis_window() -> tuple[str, str]:
    today = _today()
    return today.isoformat(), (today + timedelta(days=2)).isoformat()


def _date_values(date_from: str, date_to: str) -> List[str]:
    return date_list(date_from, date_to)


def _has_action(actions: Dict[str, int], *names: str) -> bool:
    return any(int(actions.get(name) or 0) > 0 for name in names)


def _compact_actions(actions: Dict[str, int]) -> Dict[str, int]:
    return {key: int(value or 0) for key, value in sorted(actions.items()) if int(value or 0) > 0}


def _merge_actions(target: Dict[str, int], source: Dict[str, int]) -> None:
    for key, value in (source or {}).items():
        try:
            amount = int(value or 0)
        except (TypeError, ValueError):
            amount = 0
        if amount > 0:
            target[key] = int(target.get(key) or 0) + amount


def _parse_task_payload(output: str) -> Dict[str, Any]:
    for line in reversed((output or "").splitlines()):
        if line.startswith(TASK_SENTINEL):
            try:
                return json.loads(line[len(TASK_SENTINEL):])
            except Exception as exc:
                return {"success": False, "parse_error": str(exc), "raw": line[-2000:]}
    return {"success": False, "parse_error": "task JSON sentinel not found", "raw_tail": (output or "")[-4000:]}


class AutomationCenter:
    """A small task coordinator with bounded subprocess workers."""

    def __init__(self, db_path: Union[str, Path] = DEFAULT_DB, oddsfe_db_path: Union[str, Path] = DEFAULT_ODDSFE_DB):
        self.db_path = str(db_path)
        self.oddsfe_db_path = str(oddsfe_db_path)
        self.foundation = FoundationDAO(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _table_exists(self, table_name: str) -> bool:
        with self._connect() as conn:
            return conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
                (table_name,),
            ).fetchone() is not None

    def _default_national_ou_fact_table(self) -> str:
        configured = os.environ.get("FOOTBALL_NATIONAL_REFERENCE_FACT_TABLE")
        if configured:
            return configured
        candidate = "team_match_facts_candidate_full_20260624"
        return candidate if self._table_exists(candidate) else "team_match_facts"

    def _default_bqc_profile_fact_table(self) -> str:
        configured = os.environ.get("FOOTBALL_BQC_PROFILE_FACT_TABLE")
        if configured:
            return configured
        candidate = "team_match_facts_candidate_full_20260624"
        return candidate if self._table_exists(candidate) else "team_match_facts"

    def _distinct_match_dates(self, date_from: str, date_to: str, league: str = "") -> List[str]:
        where = ["substr(COALESCE(beijing_time, match_date), 1, 10) BETWEEN ? AND ?"]
        params: List[Any] = [date_from, date_to]
        if league:
            where.append("COALESCE(league_name_cn, '') = ?")
            params.append(league)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT DISTINCT substr(COALESCE(beijing_time, match_date), 1, 10) AS d
                FROM lottery_matches
                WHERE {' AND '.join(where)}
                ORDER BY d
                """,
                params,
            ).fetchall()
        return [str(row["d"]) for row in rows if row["d"]]

    def _match_ids_for_dates(self, date_values: Sequence[str], league: str = "") -> List[str]:
        if not date_values:
            return []
        placeholders = ",".join("?" for _ in date_values)
        where = [
            f"substr(COALESCE(beijing_time, match_date), 1, 10) IN ({placeholders})",
            "home_team_id IS NOT NULL",
            "away_team_id IS NOT NULL",
        ]
        params: List[Any] = list(date_values)
        if league:
            where.append("COALESCE(league_name_cn, '') = ?")
            params.append(league)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT lottery_match_id
                FROM lottery_matches
                WHERE {' AND '.join(where)}
                ORDER BY substr(COALESCE(beijing_time, match_date), 1, 10), lottery_match_id
                """,
                params,
            ).fetchall()
        return [str(row["lottery_match_id"]) for row in rows]

    def _backup_force_targets(self, date_values: Sequence[str], league: str) -> Optional[str]:
        match_ids = self._match_ids_for_dates(date_values, league=league)
        if not match_ids:
            return None
        from scripts.run_model_reanalysis_stage import backup_analysis_layer, connect

        tag = f"automation_center_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        conn = connect(Path(self.db_path))
        try:
            path = backup_analysis_layer(Path(self.db_path), conn, match_ids, date_values, tag)
        finally:
            conn.close()
        return str(path)

    def _mark_duplicate_reports_stale(self) -> Dict[str, Any]:
        try:
            from scripts.mark_duplicate_reports_stale import mark_duplicate_reports_stale

            return mark_duplicate_reports_stale(Path(self.db_path), include_full=True, apply=True)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _mark_stale_collection_runs(self, *, older_than_minutes: int = 90) -> Dict[str, Any]:
        """Close old running rows left behind by crashed segmented jobs."""
        try:
            from scripts.mark_stale_collection_runs import mark_stale, stale_rows

            tracked_types = [
                "auto_loop_cycle",
                "automation_center",
                "automation_learning",
                "auto_gap_fill",
                "historical_backfill",
                "sporttery_daily_matches",
                "sporttery_results",
                "oddsfe_event_details",
                "oddsfe_ou_lines",
                "football_data_wc_sync",
            ]
            conn = sqlite3.connect(self.db_path, timeout=120)
            conn.execute("PRAGMA busy_timeout=120000")
            try:
                rows = stale_rows(
                    conn,
                    older_than_minutes=max(30, int(older_than_minutes)),
                    run_types=tracked_types,
                )
                updated = mark_stale(conn, rows, f"{max(30, int(older_than_minutes))} minutes") if rows else 0
                return {
                    "success": True,
                    "older_than_minutes": max(30, int(older_than_minutes)),
                    "stale_rows": len(rows),
                    "updated": updated,
                    "run_ids": [row.get("run_id") for row in rows[:20]],
                }
            finally:
                conn.close()
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _model_change_gate(self, backup_path: Optional[str], date_values: Sequence[str], league: str) -> Optional[Dict[str, Any]]:
        if not backup_path:
            return None
        try:
            from scripts.model_change_gate import evaluate_model_change

            return evaluate_model_change(
                db_path=Path(self.db_path),
                backup_path=Path(backup_path),
                date_from=min(date_values) if date_values else "",
                date_to=max(date_values) if date_values else "",
                league=league,
                overall_drop_tolerance_pp=1.0,
                play_drop_tolerance_pp=3.0,
                fail_on_missing=True,
                limit=20,
            )
        except Exception as exc:
            return {"success": False, "decision": "fail", "error": str(exc)}

    def _restore_analysis_backup(self, backup_path: Optional[str]) -> Optional[Dict[str, Any]]:
        if not backup_path:
            return None
        try:
            from scripts.run_model_reanalysis_stage import restore_backup

            restored = restore_backup(Path(self.db_path), Path(backup_path))
            return {"success": True, "backup": backup_path, **restored}
        except Exception as exc:
            return {"success": False, "backup": backup_path, "error": str(exc)}

    def _historical_candidates(
        self,
        *,
        latest_offset_days: int,
        lookback_days: int,
        max_dates: int,
        league: str,
    ) -> List[str]:
        latest = _today() - timedelta(days=max(latest_offset_days, 0))
        earliest = latest - timedelta(days=max(lookback_days, 1))
        dates = list(reversed(self._distinct_match_dates(earliest.isoformat(), latest.isoformat(), league)))
        runner = LotteryAutoGapRunner(self.db_path, self.oddsfe_db_path)
        selected: List[str] = []
        for value in dates:
            actions = _compact_actions(runner.infer_action_counts(value, value, league=league or None))
            if actions:
                selected.append(value)
            if len(selected) >= max_dates:
                break
        return selected

    def resolve_dates(
        self,
        *,
        mode: str,
        date_from: Optional[str],
        date_to: Optional[str],
        league: str = "",
        historical_dates: int = 0,
        historical_lookback_days: int = 180,
        historical_latest_offset_days: int = 1,
    ) -> List[str]:
        mode = (mode or "rolling").strip().lower()
        values: List[str] = []
        if mode in {"rolling", "mixed"}:
            today = _today()
            values.extend((today + timedelta(days=offset)).isoformat() for offset in (-1, 0, 1, 2))
        if mode == "range":
            if not date_from or not date_to:
                raise ValueError("date_from/date_to are required for range mode")
            values.extend(_date_values(date_from, date_to))
        if mode == "mixed" and date_from and date_to:
            values.extend(_date_values(date_from, date_to))
        if mode == "historical" or (mode == "mixed" and historical_dates > 0):
            values.extend(
                self._historical_candidates(
                    latest_offset_days=historical_latest_offset_days,
                    lookback_days=historical_lookback_days,
                    max_dates=max(historical_dates, 1),
                    league=league,
                )
            )
        if mode not in {"rolling", "range", "historical", "mixed"}:
            raise ValueError(f"unsupported automation mode: {mode}")
        return sorted(set(values))

    def build_tasks(
        self,
        date_values: Sequence[str],
        *,
        league: str = "",
        include_learning: bool = True,
        national_ou_gate: bool = True,
        force_analysis: bool = False,
        force_validation: bool = False,
        force_learning: bool = False,
    ) -> List[AutomationTask]:
        runner = LotteryAutoGapRunner(self.db_path, self.oddsfe_db_path)
        tasks: List[AutomationTask] = []
        needs_learning = False
        learning_actions: Dict[str, int] = {}

        for value in sorted(set(date_values)):
            actions = _compact_actions(runner.infer_action_counts(value, value, league=league or None))
            if not actions and not (force_analysis or force_validation):
                continue
            if _has_action(actions, "sync_football_data_wc"):
                tasks.append(AutomationTask("football_data_wc", value, value, 1, "football-data.org World Cup source gap", actions))
            if _has_action(actions, "sync_event_detail", "collect_odds"):
                tasks.append(AutomationTask("event_details", value, value, 1, "event/result/odds gap", actions))
            if _has_action(actions, "sync_ou_line"):
                tasks.append(AutomationTask("ou_lines", value, value, 1, "true O/U line gap", actions))
            if _has_action(actions, "collect_intelligence"):
                tasks.append(AutomationTask("intelligence", value, value, 1, "intelligence gap", actions))
            if _has_action(actions, "audit_results", "sync_event_detail", "sync_ou_line"):
                tasks.append(AutomationTask("result_audit", value, value, 2, "settled result consistency audit", actions))
            if _has_action(
                actions,
                "analyze",
                "collect_intelligence",
                "sync_football_data_wc",
                "sync_ou_line",
                "sync_event_detail",
                "collect_odds",
            ):
                tasks.append(AutomationTask("analysis", value, value, 3, "analysis missing/stale or upstream changed", actions))
                needs_learning = True
                _merge_actions(learning_actions, actions)
            elif force_analysis:
                tasks.append(AutomationTask("analysis", value, value, 3, "forced model re-analysis", actions or {"force_analysis": 1}))
                needs_learning = True
                _merge_actions(learning_actions, actions or {"force_analysis": 1})
            broad_gate_needed = (
                _has_action(
                    actions,
                    "analyze",
                    "collect_intelligence",
                    "sync_football_data_wc",
                    "sync_ou_line",
                    "sync_event_detail",
                    "collect_odds",
                    "validate",
                    "audit_results",
                )
                or force_analysis
                or force_validation
            )
            if broad_gate_needed or _has_action(actions, "play_consistency_gate"):
                tasks.append(
                    AutomationTask(
                        "play_consistency_gate",
                        value,
                        value,
                        5,
                        "hard SPF/RQSPF/BQC consistency gate",
                        actions or {"play_consistency_gate": 1},
                    )
                )
                needs_learning = True
                _merge_actions(learning_actions, {"play_consistency_gate": 1})
            if broad_gate_needed or _has_action(actions, "bqc_full_axis_gate"):
                tasks.append(
                    AutomationTask(
                        "bqc_full_axis_gate",
                        value,
                        value,
                        4,
                        "BQC full-time leg arbitration gate",
                        actions or {"bqc_full_axis_gate": 1},
                    )
                )
                needs_learning = True
                _merge_actions(learning_actions, {"bqc_full_axis_gate": 1})
            if broad_gate_needed or _has_action(actions, "handicap_margin_gate"):
                tasks.append(
                    AutomationTask(
                        "handicap_margin_gate",
                        value,
                        value,
                        6,
                        "handicap margin boundary calibration gate",
                        actions or {"handicap_margin_gate": 1},
                    )
                )
                needs_learning = True
                _merge_actions(learning_actions, {"handicap_margin_gate": 1})
            if _has_action(actions, "validate", "audit_results"):
                tasks.append(AutomationTask("validation", value, value, 7, "settled match validation gap", actions))
                needs_learning = True
                _merge_actions(learning_actions, actions)
            elif force_validation:
                tasks.append(AutomationTask("validation", value, value, 7, "forced validation rebuild", actions or {"force_validation": 1}))
                needs_learning = True
                _merge_actions(learning_actions, actions or {"force_validation": 1})
            if national_ou_gate and (_has_action(actions, "validate", "audit_results", "national_ou_gate") or force_validation):
                tasks.append(
                    AutomationTask(
                        "national_ou_gate",
                        value,
                        value,
                        8,
                        "post-validation national-team O/U conflict gate",
                        actions or {"force_validation": 1},
                    )
                )
                needs_learning = True
                _merge_actions(learning_actions, {"national_ou_gate": 1})
            post_validation_needed = _has_action(actions, "validate", "audit_results") or force_validation
            if post_validation_needed or _has_action(actions, "bqc_half_time_profile"):
                tasks.append(
                    AutomationTask(
                        "bqc_half_time_profile",
                        value,
                        value,
                        9,
                        "post-validation BQC half-time profile audit",
                        actions or {"bqc_half_time_profile": 1},
                    )
                )
                needs_learning = True
                _merge_actions(learning_actions, {"bqc_half_time_profile": 1})
            if post_validation_needed or _has_action(actions, "prediction_error_review"):
                tasks.append(
                    AutomationTask(
                        "prediction_error_review",
                        value,
                        value,
                        11,
                        "post-validation error attribution and next-action review",
                        actions or {"prediction_error_review": 1},
                    )
                )
                needs_learning = True
                _merge_actions(learning_actions, {"prediction_error_review": 1})
            if post_validation_needed or _has_action(actions, "bqc_full_time_axis"):
                tasks.append(
                    AutomationTask(
                        "bqc_full_time_axis",
                        value,
                        value,
                        10,
                        "post-validation BQC full-time axis audit",
                        actions or {"bqc_full_time_axis": 1},
                    )
                )
                needs_learning = True
                _merge_actions(learning_actions, {"bqc_full_time_axis": 1})
            if post_validation_needed or _has_action(actions, "handicap_margin_axis"):
                tasks.append(
                    AutomationTask(
                        "handicap_margin_axis",
                        value,
                        value,
                        10,
                        "post-validation handicap margin boundary audit",
                        actions or {"handicap_margin_axis": 1},
                    )
                )
                needs_learning = True
                _merge_actions(learning_actions, {"handicap_margin_axis": 1})
            if _has_action(actions, "refresh_learning"):
                needs_learning = True
                _merge_actions(learning_actions, actions)
            elif _has_action(actions, "audit_results"):
                needs_learning = True

        if include_learning and (needs_learning or force_learning) and date_values:
            future_from, future_to = _future_reanalysis_window()
            tasks.append(
                AutomationTask(
                    "learning",
                    min(date_values),
                    max(date_values),
                    12,
                    "single final learning refresh after dated tasks",
                    _compact_actions(learning_actions or {"refresh_learning": 1}),
                )
            )
            if not (min(date_values) <= future_from and max(date_values) >= future_to):
                future_actions = _compact_actions(
                    {
                        **(learning_actions or {"refresh_learning": 1}),
                        "post_learning_future_reanalysis": 1,
                    }
                )
                tasks.append(
                    AutomationTask(
                        "future_reanalysis",
                        future_from,
                        future_to,
                        13,
                        "refresh current unstarted matches after learning",
                        future_actions,
                    )
                )
        return tasks

    def plan(
        self,
        *,
        mode: str = "rolling",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        league: str = "",
        historical_dates: int = 0,
        historical_lookback_days: int = 180,
        include_learning: bool = True,
        national_ou_gate: bool = True,
        force_analysis: bool = False,
        force_validation: bool = False,
        force_learning: bool = False,
    ) -> Dict[str, Any]:
        date_values = self.resolve_dates(
            mode=mode,
            date_from=date_from,
            date_to=date_to,
            league=league,
            historical_dates=historical_dates,
            historical_lookback_days=historical_lookback_days,
        )
        tasks = self.build_tasks(
            date_values,
            league=league,
            include_learning=include_learning,
            national_ou_gate=national_ou_gate,
            force_analysis=force_analysis,
            force_validation=force_validation,
            force_learning=force_learning,
        )
        by_wave: Dict[str, int] = {}
        by_kind: Dict[str, int] = {}
        for task in tasks:
            by_wave[str(task.wave)] = by_wave.get(str(task.wave), 0) + 1
            by_kind[task.kind] = by_kind.get(task.kind, 0) + 1
        return {
            "success": True,
            "mode": mode,
            "league": league,
            "dates": date_values,
            "task_count": len(tasks),
            "by_wave": by_wave,
            "by_kind": by_kind,
            "tasks": [asdict(task) for task in tasks],
        }

    def run(self, **kwargs) -> Dict[str, Any]:
        """Run one automation-center cycle under a cross-process durable lock."""
        try:
            timeout = int(kwargs.get("task_timeout_seconds") or 300)
        except (TypeError, ValueError):
            timeout = 300
        stale_seconds = max(1800, timeout * 3)
        with exclusive_task_lock("automation_center", self.db_path, stale_seconds=stale_seconds) as task_lock:
            if not task_lock.acquired:
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "automation_center_already_running",
                    "lock_path": task_lock.path,
                    "lock_holder": task_lock.holder,
                    "trigger_source": kwargs.get("trigger_source"),
                }
            result = self._run_unlocked(**kwargs)
            if isinstance(result, dict):
                result["lock"] = {"path": task_lock.path, "acquired": True}
            return result

    def retry_failed_tasks(
        self,
        run_id: str,
        *,
        trigger_source: str = "automation_retry",
        workers: Optional[int] = None,
        task_timeout_seconds: Optional[int] = None,
        task_key: Optional[str] = None,
        task_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        source = self._load_run_summary(run_id)
        if not source:
            return {"success": False, "error": "source_run_not_found", "run_id": run_id}
        requested_task_key = str(task_key or "").strip()
        requested_task_index = None if task_index is None else int(task_index)
        failed_items: List[Dict[str, Any]] = []
        for index, item in enumerate(source.get("tasks") or []):
            if not (isinstance(item, dict) and item.get("success") is False and isinstance(item.get("task"), dict)):
                continue
            source_task_key = self._task_key_from_dict(item["task"])
            if requested_task_key and requested_task_key not in {source_task_key, str(index)}:
                continue
            if requested_task_index is not None and requested_task_index != index:
                continue
            failed_items.append({**item, "source_index": index, "source_task_key": source_task_key})
        if not failed_items:
            if requested_task_key or requested_task_index is not None:
                return {
                    "success": False,
                    "skipped": True,
                    "reason": "failed_task_not_found",
                    "source_run_id": run_id,
                    "task_key": requested_task_key or None,
                    "task_index": requested_task_index,
                }
            return {
                "success": True,
                "skipped": True,
                "reason": "no_failed_tasks",
                "source_run_id": run_id,
            }
        retry_items = [
            {
                "task": AutomationTask(**self._retry_task_fields(item["task"])),
                "source_index": item["source_index"],
                "source_task_key": item["source_task_key"],
            }
            for item in failed_items
        ]
        retry_tasks = [item["task"] for item in retry_items]
        timeout = int(task_timeout_seconds or source.get("task_timeout_seconds") or 300)
        with exclusive_task_lock("automation_center", self.db_path, stale_seconds=max(1800, timeout * 3)) as task_lock:
            if not task_lock.acquired:
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "automation_center_already_running",
                    "source_run_id": run_id,
                    "lock_path": task_lock.path,
                    "lock_holder": task_lock.holder,
                }
            retry_run_id = self.foundation.start_run(
                run_type="automation_retry",
                match_date=(retry_tasks[0].match_date if retry_tasks else None),
                trigger_source=trigger_source,
                summary={
                    "stage": "start",
                    "source_run_id": run_id,
                    "task_count": len(retry_tasks),
                    "retry_scope": "single" if (requested_task_key or requested_task_index is not None) else "all_failed",
                    "task_key": requested_task_key or None,
                    "task_index": requested_task_index,
                },
            )
            summary: Dict[str, Any] = {
                "stage": "running",
                "source_run_id": run_id,
                "task_count": len(retry_tasks),
                "retry_scope": "single" if (requested_task_key or requested_task_index is not None) else "all_failed",
                "task_key": requested_task_key or None,
                "task_index": requested_task_index,
                "workers": max(1, int(workers or source.get("workers") or 1)),
                "tasks": [],
            }
            try:
                retry_workers = max(1, int(workers or source.get("workers") or 1))
                national_ou_fact_table = self._default_national_ou_fact_table()
                bqc_profile_fact_table = self._default_bqc_profile_fact_table()
                with ThreadPoolExecutor(max_workers=retry_workers, thread_name_prefix="auto-retry") as pool:
                    futures = {
                        pool.submit(
                            self._execute_task,
                            item["task"],
                            timeout_seconds=timeout,
                            max_events=int(source.get("max_events") or 6),
                            max_analysis=int(source.get("max_analysis") or 10),
                            max_intelligence=int(source.get("max_intelligence") or 6),
                            max_validation_dates=int(source.get("max_validation_dates") or 1),
                            fetch_live_ou=bool(source.get("fetch_live_ou", False)),
                            network_intelligence=bool(source.get("network_intelligence", False)),
                            national_ou_fact_table=national_ou_fact_table,
                            bqc_profile_fact_table=bqc_profile_fact_table,
                            league=str(source.get("league") or ""),
                            trigger_source=trigger_source,
                            force=False,
                        ): item
                        for item in retry_items
                    }
                    for future in as_completed(futures):
                        retry_item = futures[future]
                        result = future.result()
                        result["source_run_id"] = run_id
                        result["source_task_key"] = retry_item["source_task_key"]
                        result["source_task_index"] = retry_item["source_index"]
                        summary["tasks"].append(result)
                        summary["progress"] = {
                            "stage": "task_finished",
                            "total_tasks": len(retry_tasks),
                            "completed_tasks": len(summary["tasks"]),
                            "failed_tasks": sum(1 for item in summary["tasks"] if item.get("success") is False),
                            "skipped_tasks": sum(1 for item in summary["tasks"] if item.get("skipped")),
                            "running_tasks": max(0, len(retry_tasks) - len(summary["tasks"])),
                            "progress_percent": round(len(summary["tasks"]) * 100 / len(retry_tasks), 1),
                            "updated_at": datetime.now().isoformat(timespec="seconds"),
                        }
                        self.foundation.update_run(retry_run_id, status="running", summary=summary)
                summary["failed_tasks"] = sum(1 for item in summary["tasks"] if item.get("success") is False)
                summary["success"] = summary["failed_tasks"] == 0
                summary["stage"] = "finished"
                summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
                if isinstance(summary.get("progress"), dict):
                    summary["progress"]["stage"] = "finished"
                    summary["progress"]["running_tasks"] = 0
                    summary["progress"]["progress_percent"] = 100.0
                    summary["progress"]["updated_at"] = summary["finished_at"]
                self.foundation.finish_run(
                    retry_run_id,
                    status="success" if summary["success"] else "failed",
                    summary=summary,
                    error=None if summary["success"] else f"{summary['failed_tasks']} retry task(s) failed",
                )
                return {"success": summary["success"], "run_id": retry_run_id, **summary}
            except Exception as exc:
                summary["success"] = False
                summary["stage"] = "failed"
                summary["error"] = str(exc)
                self.foundation.finish_run(retry_run_id, status="failed", summary=summary, error=str(exc))
                return {"success": False, "run_id": retry_run_id, **summary}

    def retry_recent_failed_task(
        self,
        *,
        trigger_source: str = "automation_retry_rescue",
        workers: int = 1,
        task_timeout_seconds: Optional[int] = None,
        recent_runs_limit: int = 60,
    ) -> Dict[str, Any]:
        """Retry the newest unresolved failed automation task.

        This is intentionally small and conservative: one failed task per
        scheduler cycle. A later successful retry with the same task key clears
        the failure from the rescue backlog.
        """
        target = self._latest_unresolved_failed_task(limit=recent_runs_limit)
        if not target:
            return {
                "success": True,
                "skipped": True,
                "reason": "no_unresolved_failed_automation_task",
                "trigger_source": trigger_source,
            }
        result = self.retry_failed_tasks(
            target["run_id"],
            trigger_source=trigger_source,
            workers=max(1, int(workers or 1)),
            task_timeout_seconds=task_timeout_seconds,
            task_key=target["task_key"],
            task_index=target.get("task_index"),
        )
        if isinstance(result, dict):
            result["rescued_task"] = target
        return result

    def _latest_unresolved_failed_task(self, *, limit: int = 60) -> Optional[Dict[str, Any]]:
        if not self._table_exists("collection_runs"):
            return None
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT run_id, run_type, started_at, summary_json
                FROM collection_runs
                WHERE run_type IN ('automation_center', 'automation_retry')
                ORDER BY datetime(started_at) DESC, rowid DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()

        latest_by_key: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            try:
                summary = json.loads(row["summary_json"] or "{}")
            except Exception:
                summary = {}
            if not isinstance(summary, dict):
                continue
            tasks = summary.get("tasks") if isinstance(summary.get("tasks"), list) else []
            for index, item in enumerate(tasks):
                if not isinstance(item, dict) or not isinstance(item.get("task"), dict):
                    continue
                task_key = str(item.get("source_task_key") or self._task_key_from_dict(item["task"]))
                if not task_key or task_key in latest_by_key:
                    continue
                payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                failed = item.get("success") is False or payload.get("success") is False
                latest_by_key[task_key] = {
                    "run_id": row["run_id"],
                    "run_type": row["run_type"],
                    "started_at": row["started_at"],
                    "task_key": task_key,
                    "task_index": int(item.get("source_task_index") if item.get("source_task_index") is not None else index),
                    "task": self._retry_task_fields(item["task"]),
                    "failed": failed,
                    "error": item.get("error") or payload.get("error") or payload.get("parse_error"),
                }
        for item in latest_by_key.values():
            if item.get("failed"):
                return item
        return None

    def _load_run_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT summary_json FROM collection_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        try:
            value = json.loads(row["summary_json"] or "{}")
        except Exception:
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _retry_task_fields(task: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "kind": str(task.get("kind") or ""),
            "date_from": str(task.get("date_from") or ""),
            "date_to": str(task.get("date_to") or task.get("date_from") or ""),
            "wave": int(task.get("wave") or 99),
            "reason": str(task.get("reason") or "retry failed automation task"),
            "action_counts": task.get("action_counts") if isinstance(task.get("action_counts"), dict) else {"retry": 1},
        }

    @staticmethod
    def _task_key_from_dict(task: Dict[str, Any]) -> str:
        return "{wave}:{kind}:{date_from}:{date_to}".format(
            wave=int(task.get("wave") or 99),
            kind=str(task.get("kind") or ""),
            date_from=str(task.get("date_from") or ""),
            date_to=str(task.get("date_to") or task.get("date_from") or ""),
        )

    def _run_unlocked(
        self,
        *,
        mode: str = "rolling",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        league: str = "",
        historical_dates: int = 0,
        historical_lookback_days: int = 180,
        include_learning: bool = True,
        national_ou_gate: bool = True,
        national_ou_fact_table: Optional[str] = None,
        bqc_profile_fact_table: Optional[str] = None,
        force_analysis: bool = False,
        force_validation: bool = False,
        force_learning: bool = False,
        workers: int = 3,
        task_timeout_seconds: int = 300,
        max_events: int = 6,
        max_analysis: int = 10,
        max_intelligence: int = 6,
        max_validation_dates: int = 1,
        fetch_live_ou: bool = True,
        network_intelligence: bool = True,
        trigger_source: str = "automation_center",
    ) -> Dict[str, Any]:
        preflight_stale_cleanup = self._mark_stale_collection_runs(
            older_than_minutes=max(90, min(240, int(task_timeout_seconds or 300) // 20)),
        )
        plan = self.plan(
            mode=mode,
            date_from=date_from,
            date_to=date_to,
            league=league,
            historical_dates=historical_dates,
            historical_lookback_days=historical_lookback_days,
            include_learning=include_learning,
            national_ou_gate=national_ou_gate,
            force_analysis=force_analysis,
            force_validation=force_validation,
            force_learning=force_learning,
        )
        national_ou_fact_table = national_ou_fact_table or self._default_national_ou_fact_table()
        bqc_profile_fact_table = bqc_profile_fact_table or self._default_bqc_profile_fact_table()
        tasks = [AutomationTask(**item) for item in plan["tasks"]]
        run_id = self.foundation.start_run(
            run_type="automation_center",
            match_date=plan["dates"][0] if plan["dates"] else None,
            trigger_source=trigger_source,
            summary={
                "stage": "start",
                "preflight_stale_cleanup": preflight_stale_cleanup,
                **{key: plan[key] for key in ("mode", "league", "dates", "task_count", "by_wave", "by_kind")},
            },
        )
        summary: Dict[str, Any] = {
            **{key: plan[key] for key in ("mode", "league", "dates", "task_count", "by_wave", "by_kind")},
            "workers": max(1, int(workers)),
            "task_timeout_seconds": task_timeout_seconds,
            "max_events": max_events,
            "max_analysis": max_analysis,
            "max_intelligence": max_intelligence,
            "max_validation_dates": max_validation_dates,
            "fetch_live_ou": bool(fetch_live_ou),
            "network_intelligence": bool(network_intelligence),
            "preflight_stale_cleanup": preflight_stale_cleanup,
            "waves": [],
            "tasks": [],
        }

        def _write_progress(
            stage: str,
            *,
            current_wave: Optional[int] = None,
            active_tasks: Optional[Sequence[AutomationTask]] = None,
            last_task: Optional[Dict[str, Any]] = None,
        ) -> None:
            completed = len(summary.get("tasks") or [])
            failed = sum(1 for item in summary.get("tasks") or [] if item.get("success") is False)
            skipped = sum(1 for item in summary.get("tasks") or [] if item.get("skipped"))
            running = len(active_tasks or [])
            total = len(tasks)
            progress = {
                "stage": stage,
                "current_wave": current_wave,
                "total_tasks": total,
                "completed_tasks": completed,
                "failed_tasks": failed,
                "skipped_tasks": skipped,
                "running_tasks": running,
                "progress_percent": round(completed * 100 / total, 1) if total else 100.0,
                "active_tasks": [
                    {
                        "kind": task.kind,
                        "date_from": task.date_from,
                        "date_to": task.date_to,
                        "wave": task.wave,
                    }
                    for task in (active_tasks or [])
                ][:8],
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            if last_task:
                task = last_task.get("task") if isinstance(last_task.get("task"), dict) else {}
                progress["last_task"] = {
                    "kind": task.get("kind"),
                    "date_from": task.get("date_from"),
                    "date_to": task.get("date_to"),
                    "wave": task.get("wave"),
                    "success": last_task.get("success"),
                    "skipped": last_task.get("skipped"),
                    "reason": last_task.get("reason"),
                }
            summary["stage"] = stage
            summary["progress"] = progress
            self.foundation.update_run(run_id, status="running", summary=summary)

        _write_progress("planned")
        try:
            if not tasks:
                summary["report_stale_marking"] = self._mark_duplicate_reports_stale()
                summary["maintenance_failed"] = not bool((summary.get("report_stale_marking") or {}).get("success", True))
                summary["success"] = not summary["maintenance_failed"]
                summary["skipped"] = True
                summary["reason"] = "no actionable automation tasks"
                _write_progress("no_tasks")
                self.foundation.finish_run(
                    run_id,
                    status="success" if summary["success"] else "failed",
                    summary=summary,
                    error=None if summary["success"] else "report stale marking failed",
                )
                return {"success": summary["success"], "run_id": run_id, **summary}

            if force_analysis or force_validation or force_learning:
                summary["analysis_layer_backup"] = self._backup_force_targets(plan["dates"], league)

            for wave in sorted({task.wave for task in tasks}):
                wave_tasks = [task for task in tasks if task.wave == wave]
                wave_started = time.time()
                wave_result = {"wave": wave, "task_count": len(wave_tasks), "results": []}
                runnable_tasks: List[AutomationTask] = []
                for task in wave_tasks:
                    skip_reason = self._skip_task_reason(
                        task,
                        summary,
                        force=force_analysis or force_validation or force_learning,
                    )
                    if skip_reason:
                        result = self._skipped_task_result(task, skip_reason)
                        wave_result["results"].append(result)
                        summary["tasks"].append(result)
                    else:
                        runnable_tasks.append(task)

                _write_progress(
                    "wave_running" if runnable_tasks else "wave_skipped",
                    current_wave=wave,
                    active_tasks=runnable_tasks,
                )
                if runnable_tasks:
                    active_by_key = {task.key: task for task in runnable_tasks}
                    with ThreadPoolExecutor(max_workers=max(1, int(workers)), thread_name_prefix=f"auto-wave-{wave}") as pool:
                        futures = {
                            pool.submit(
                                self._execute_task,
                                task,
                                timeout_seconds=task_timeout_seconds,
                                max_events=max_events,
                                max_analysis=max_analysis,
                                max_intelligence=max_intelligence,
                                max_validation_dates=max_validation_dates,
                                fetch_live_ou=fetch_live_ou,
                                network_intelligence=network_intelligence,
                                national_ou_fact_table=national_ou_fact_table,
                                bqc_profile_fact_table=bqc_profile_fact_table,
                                league=league,
                                trigger_source=trigger_source,
                                force=force_analysis or force_validation or force_learning,
                            ): task
                            for task in runnable_tasks
                        }
                        for future in as_completed(futures):
                            task = futures[future]
                            result = future.result()
                            wave_result["results"].append(result)
                            summary["tasks"].append(result)
                            active_by_key.pop(task.key, None)
                            _write_progress(
                                "task_finished",
                                current_wave=wave,
                                active_tasks=list(active_by_key.values()),
                                last_task=result,
                            )
                wave_result["elapsed_seconds"] = round(time.time() - wave_started, 1)
                wave_result["skipped"] = sum(1 for item in wave_result["results"] if item.get("skipped"))
                wave_result["failed"] = sum(1 for item in wave_result["results"] if not item.get("success"))
                summary["waves"].append(wave_result)
                _write_progress("wave_finished", current_wave=wave)

            _write_progress("maintenance")
            summary["report_stale_marking"] = self._mark_duplicate_reports_stale()
            summary["model_gate"] = self._model_change_gate(summary.get("analysis_layer_backup"), plan["dates"], league)
            summary["failed_tasks"] = sum(1 for item in summary["tasks"] if not item.get("success"))
            summary["maintenance_failed"] = not bool((summary.get("report_stale_marking") or {}).get("success", True))
            summary["model_gate_failed"] = bool((summary.get("model_gate") or {}).get("decision") == "fail")
            summary["model_gate_error"] = bool(
                summary["model_gate_failed"]
                and (summary.get("model_gate") or {}).get("success") is False
                and (summary.get("model_gate") or {}).get("error")
            )
            if summary["model_gate_failed"]:
                summary["model_gate_rollback"] = self._restore_analysis_backup(summary.get("analysis_layer_backup"))
                summary["model_gate_rollback_failed"] = not bool((summary.get("model_gate_rollback") or {}).get("success"))
            else:
                summary["model_gate_rollback"] = None
                summary["model_gate_rollback_failed"] = False
            summary["success"] = (
                summary["failed_tasks"] == 0
                and not summary["maintenance_failed"]
                and not summary["model_gate_error"]
                and not summary["model_gate_rollback_failed"]
            )
            summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
            summary["stage"] = "finished"
            if isinstance(summary.get("progress"), dict):
                summary["progress"]["stage"] = "finished"
                summary["progress"]["running_tasks"] = 0
                summary["progress"]["progress_percent"] = 100.0
                summary["progress"]["updated_at"] = summary["finished_at"]
            status = "success" if summary["success"] else "failed"
            error = None
            if not summary["success"]:
                errors = []
                if summary["failed_tasks"]:
                    errors.append(f"{summary['failed_tasks']} automation task(s) failed")
                if summary["maintenance_failed"]:
                    errors.append("report stale marking failed")
                if summary["model_gate_error"]:
                    errors.append("model change gate failed")
                if summary.get("model_gate_rollback_failed"):
                    errors.append("model change rollback failed")
                error = "; ".join(errors)
            self.foundation.finish_run(run_id, status=status, summary=summary, error=error)
            return {"success": summary["success"], "run_id": run_id, **summary}
        except Exception as exc:
            summary["success"] = False
            summary["error"] = str(exc)
            summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
            summary["stage"] = "failed"
            if isinstance(summary.get("progress"), dict):
                summary["progress"]["stage"] = "failed"
                summary["progress"]["running_tasks"] = 0
                summary["progress"]["updated_at"] = summary["finished_at"]
            self.foundation.finish_run(run_id, status="failed", summary=summary, error=str(exc))
            return {"success": False, "run_id": run_id, **summary}

    @staticmethod
    def _date_ranges_overlap(left_from: str, left_to: str, right_from: str, right_to: str) -> bool:
        return not (left_to < right_from or right_to < left_from)

    @staticmethod
    def _payload_int(payload: Dict[str, Any], *keys: str) -> int:
        total = 0
        for key in keys:
            try:
                total += int(payload.get(key) or 0)
            except (TypeError, ValueError):
                pass
        return total

    def _prior_task_results(self, summary: Dict[str, Any], task: AutomationTask) -> List[Dict[str, Any]]:
        matches: List[Dict[str, Any]] = []
        for item in summary.get("tasks") or []:
            prior = item.get("task") or {}
            if not prior:
                continue
            if self._date_ranges_overlap(
                str(prior.get("date_from") or ""),
                str(prior.get("date_to") or ""),
                task.date_from,
                task.date_to,
            ):
                matches.append(item)
        return matches

    def _prior_result_changed(self, summary: Dict[str, Any], task: AutomationTask) -> bool:
        for item in self._prior_task_results(summary, task):
            if not item.get("success") or item.get("skipped"):
                continue
            payload = item.get("payload") or {}
            if self._payload_int(
                payload,
                "rows_changed",
                "field_changes",
                "queued_revalidation",
                "lottery_results_inserted",
                "lottery_results_updated",
                "sqlite_changes",
                "updated",
                "inserted",
                "changed_reports",
                "prediction_rows",
                "saved",
            ) > 0:
                return True
        return False

    def _prior_learning_needed(self, summary: Dict[str, Any], task: AutomationTask) -> bool:
        if self._prior_result_changed(summary, task):
            return True
        for item in self._prior_task_results(summary, task):
            if not item.get("success") or item.get("skipped"):
                continue
            payload = item.get("payload") or {}
            prior_kind = str((item.get("task") or {}).get("kind") or payload.get("task") or "")
            if prior_kind == "analysis" and self._payload_int(payload, "analyzed", "targets") > 0:
                return True
            if prior_kind == "validation" and self._payload_int(payload, "validated") > 0:
                return True
            if prior_kind == "national_ou_gate" and self._payload_int(payload, "changed_reports", "prediction_rows") > 0:
                return True
            if prior_kind == "bqc_full_axis_gate" and self._payload_int(payload, "changed_reports", "prediction_rows") > 0:
                return True
            if prior_kind == "handicap_margin_gate" and self._payload_int(payload, "changed_reports", "prediction_rows") > 0:
                return True
            if prior_kind == "bqc_half_time_profile" and self._payload_int(payload, "saved_profiles", "saved_audits") > 0:
                return True
            if prior_kind == "bqc_full_time_axis" and self._payload_int(payload, "saved") > 0:
                return True
            if prior_kind == "handicap_margin_axis" and self._payload_int(payload, "saved") > 0:
                return True
            if prior_kind == "prediction_error_review" and self._payload_int(payload, "saved") > 0:
                return True
        return False

    def _prior_future_reanalysis_skip_reason(self, summary: Dict[str, Any]) -> Optional[str]:
        saw_learning = False
        learning_locked_elsewhere = False
        for item in summary.get("tasks") or []:
            payload = item.get("payload") or {}
            prior_kind = str((item.get("task") or {}).get("kind") or payload.get("task") or "")
            if prior_kind != "learning":
                continue
            saw_learning = True
            if item.get("skipped") and item.get("reason") == "learning_task_already_running":
                learning_locked_elsewhere = True
                continue
            if not item.get("success") or item.get("skipped"):
                continue
            nested_future = payload.get("future_reanalysis") if isinstance(payload, dict) else None
            if isinstance(nested_future, dict) and int(nested_future.get("targets") or 0) > 0:
                return "skipped_future_reanalysis_already_done_inside_learning"
        if learning_locked_elsewhere:
            return None
        if not saw_learning:
            return "skipped_future_reanalysis_without_successful_learning"
        return None

    @staticmethod
    def _skipped_task_result(task: AutomationTask, reason: str) -> Dict[str, Any]:
        payload = {"success": True, "task": task.kind, "skipped": True, "reason": reason}
        return {
            "task": asdict(task),
            "success": True,
            "skipped": True,
            "reason": reason,
            "payload": payload,
            "elapsed_seconds": 0,
        }

    def _skip_task_reason(self, task: AutomationTask, summary: Dict[str, Any], *, force: bool) -> Optional[str]:
        if force:
            return None
        if task.kind == "validation":
            if _has_action(task.action_counts, "validate"):
                return None
            if self._prior_result_changed(summary, task):
                return None
            return "skipped_validation_no_result_changes_after_audit"
        if task.kind == "learning":
            if _has_action(task.action_counts, "refresh_learning"):
                return None
            if self._prior_learning_needed(summary, task):
                return None
            return "skipped_learning_no_analysis_validation_or_result_changes"
        if task.kind == "future_reanalysis":
            return self._prior_future_reanalysis_skip_reason(summary)
        return None
    def _execute_task(
        self,
        task: AutomationTask,
        *,
        timeout_seconds: int,
        max_events: int,
        max_analysis: int,
        max_intelligence: int,
        max_validation_dates: int,
        fetch_live_ou: bool,
        network_intelligence: bool,
        national_ou_fact_table: str,
        bqc_profile_fact_table: str,
        league: str,
        trigger_source: str,
        force: bool,
    ) -> Dict[str, Any]:
        task_run_id = self.foundation.start_run(
            run_type=f"automation_{task.kind}",
            match_date=task.match_date,
            trigger_source=trigger_source,
            summary={"stage": "start", "task": asdict(task)},
        )
        cmd = [
            sys.executable,
            "-X",
            "utf8",
            str(ROOT / "scripts" / "run_automation_task.py"),
            "--task",
            task.kind,
            "--db",
            self.db_path,
            "--oddsfe-db",
            self.oddsfe_db_path,
            "--from",
            task.date_from,
            "--to",
            task.date_to,
            "--max-events",
            str(max_events),
            "--max-analysis",
            str(max_analysis),
            "--max-intelligence",
            str(max_intelligence),
            "--max-validation-dates",
            str(max_validation_dates),
            "--trigger-source",
            trigger_source,
            "--national-ou-fact-table",
            national_ou_fact_table,
            "--bqc-profile-fact-table",
            bqc_profile_fact_table,
        ]
        if league:
            cmd.extend(["--league", league])
        if fetch_live_ou:
            cmd.append("--fetch-live-ou")
        if network_intelligence:
            cmd.append("--network-intelligence")
        if force:
            cmd.append("--force")

        started = time.time()
        base = {"task": asdict(task), "run_id": task_run_id, "cmd": " ".join(cmd)}
        effective_timeout = max(30, int(timeout_seconds))
        if task.kind == "learning":
            effective_timeout = max(effective_timeout, 900)
        if task.kind == "future_reanalysis":
            effective_timeout = max(effective_timeout, 600)
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT),
                env=None,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=effective_timeout,
            )
            elapsed = round(time.time() - started, 1)
            output = proc.stdout or ""
            payload = _parse_task_payload(output)
            success = proc.returncode == 0 and payload.get("success") is not False
            result = {
                **base,
                "success": success,
                "skipped": bool(payload.get("skipped")),
                "reason": payload.get("reason") if payload.get("skipped") else None,
                "exit_code": proc.returncode,
                "elapsed_seconds": elapsed,
                "payload": payload,
                "output_tail": output[-4000:],
            }
            self.foundation.finish_run(task_run_id, status="success" if success else "failed", summary=result, error=None if success else payload.get("error") or payload.get("parse_error"))
            return result
        except subprocess.TimeoutExpired as exc:
            elapsed = round(time.time() - started, 1)
            output = exc.stdout if isinstance(exc.stdout, str) else ""
            result = {
                **base,
                "success": False,
                "timeout": True,
                "elapsed_seconds": elapsed,
                "output_tail": (output or "")[-4000:],
            }
            self.foundation.finish_run(task_run_id, status="failed", summary=result, error="timeout")
            return result
        except Exception as exc:
            elapsed = round(time.time() - started, 1)
            result = {**base, "success": False, "elapsed_seconds": elapsed, "error": str(exc)}
            self.foundation.finish_run(task_run_id, status="failed", summary=result, error=str(exc))
            return result




