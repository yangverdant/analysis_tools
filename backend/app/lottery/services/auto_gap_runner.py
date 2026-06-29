"""Automatic lottery data gap runner.

This module turns the completeness/gap plan into small, auditable actions:
event evidence, O/U lines, intelligence, analysis, validation, and learning
refresh. It is intentionally conservative: each run is bounded by limits and
records a collection_runs row.
"""

from __future__ import annotations

import logging
import json
import sqlite3
from argparse import Namespace
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from backend.app.data_access.foundation_dao import FoundationDAO
from backend.app.data_access.task_lock import clean_path_arg, exclusive_task_lock


logger = logging.getLogger(__name__)


DIAGNOSIS_COLLECTION_ACTIONS = {
    "collect_half_time_profiles": ("bqc_half_time_profile", "bqc_full_time_axis", "refresh_learning"),
    "collect_team_tempo": ("national_ou_gate", "refresh_learning"),
    "collect_recent_defense_split": ("national_ou_gate", "refresh_learning"),
    "fill_intelligence_package": ("collect_intelligence", "analyze"),
    "refresh_world_cup_context": ("analyze", "prediction_error_review"),
}

DIAGNOSIS_MODEL_ACTIONS = {
    "similar_case_review": ("refresh_learning",),
    "keep_positive_pattern": ("refresh_learning",),
    "handicap_axis": ("handicap_margin_axis", "handicap_margin_gate", "play_consistency_gate"),
    "bqc_axis": ("bqc_half_time_profile", "bqc_full_time_axis", "play_consistency_gate"),
    "bqc_half_time_axis": ("bqc_half_time_profile", "bqc_full_time_axis"),
    "bqc_full_time_axis": ("bqc_full_time_axis", "bqc_full_axis_gate", "play_consistency_gate"),
    "score_axis": ("play_consistency_gate", "refresh_learning"),
    "score_axis_should_enter_bqc_full_leg": ("bqc_full_time_axis", "bqc_full_axis_gate"),
    "spf_score_axis_arbitration": ("play_consistency_gate", "bqc_full_axis_gate"),
    "direction_axis": ("play_consistency_gate",),
    "direction_axis_recalibration": ("play_consistency_gate", "refresh_learning"),
    "market_disagreement": ("play_consistency_gate",),
    "ou_tie_breaker": ("national_ou_gate",),
    "goal_tail_distribution": ("national_ou_gate", "refresh_learning"),
    "draw_risk_tie_breaker": ("bqc_full_time_axis", "play_consistency_gate"),
    "low_confidence_direction_guard": ("play_consistency_gate",),
}

DIAGNOSIS_ERROR_CATEGORIES = {
    "first_half_tempo_misread": ("bqc_half_time_profile", "bqc_full_time_axis"),
    "half_time_axis_miss": ("bqc_half_time_profile", "bqc_full_time_axis"),
    "full_time_axis_miss": ("bqc_full_time_axis", "bqc_full_axis_gate"),
    "bqc_full_time_axis_misread": ("bqc_full_time_axis", "bqc_full_axis_gate"),
    "handicap_boundary_case": ("handicap_margin_axis", "handicap_margin_gate"),
    "one_goal_margin_sensitivity": ("handicap_margin_axis", "handicap_margin_gate"),
    "goal_total_large_deviation": ("national_ou_gate", "refresh_learning"),
    "tail_risk_underestimated": ("national_ou_gate", "refresh_learning"),
    "low_tempo_underestimated": ("national_ou_gate", "refresh_learning"),
    "model_market_ou_divergence": ("national_ou_gate",),
    "score_candidate_miss": ("refresh_learning",),
    "score_tail_missing": ("refresh_learning",),
    "intel_missing": ("collect_intelligence",),
    "model_weight_error": ("refresh_learning",),
}


def date_window(days: int = 3) -> tuple[str, str]:
    today = datetime.now().date()
    start = today - timedelta(days=max(days - 2, 0))
    end = today + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def date_list(date_from: str, date_to: str) -> List[str]:
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    values: List[str] = []
    current = start
    while current <= end:
        values.append(current.isoformat())
        current += timedelta(days=1)
    return values


def action_counts_from_plan(gap_plan: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in gap_plan or []:
        action = str(item.get("action") or "").strip()
        if not action:
            continue
        try:
            counts[action] = int(item.get("count") or 0)
        except (TypeError, ValueError):
            counts[action] = 0
    return counts


class LotteryAutoGapRunner:
    """Bounded executor for the lottery hub's missing-data plan."""

    def __init__(self, db_path: str, oddsfe_db_path: Optional[str] = None):
        self.db_path = clean_path_arg(db_path)
        self.oddsfe_db_path = clean_path_arg(oddsfe_db_path) if oddsfe_db_path else oddsfe_db_path
        self.foundation = FoundationDAO(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone() is not None

    @staticmethod
    def _loads_list(value: Any) -> List[Any]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        try:
            parsed = json.loads(str(value))
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    @staticmethod
    def _bump_action(counts: Dict[str, int], action: str, amount: int = 1) -> None:
        if not action:
            return
        counts[action] = int(counts.get(action) or 0) + max(1, int(amount or 1))

    def _add_mapped_diagnosis_action(
        self,
        counts: Dict[str, int],
        source_key: str,
        mapping: Dict[str, Iterable[str]],
    ) -> None:
        for action in mapping.get(source_key, ()):
            self._bump_action(counts, action)

    def _diagnosis_action_counts(
        self,
        date_from: str,
        date_to: str,
        league: Optional[str] = None,
    ) -> Dict[str, int]:
        """Turn latest wrong-play diagnoses into follow-up automation actions.

        This does not change predictions. It only schedules audit/gate/learning
        work that can later dry-run and prove whether a model-layer change helps.
        """
        counts: Dict[str, int] = {}
        with self._connect() as conn:
            if not self._table_exists(conn, "prediction_error_diagnoses"):
                return counts
            where = [
                "d.match_date BETWEEN ? AND ?",
                "COALESCE(d.is_correct, 0) = 0",
            ]
            params: List[Any] = [date_from, date_to]
            if league:
                where.append("COALESCE(d.league_name_cn, '') = ?")
                params.append(league)
            rows = conn.execute(
                f"""
                WITH latest AS (
                    SELECT match_key, play_type, MAX(rowid) AS latest_rowid
                    FROM prediction_error_diagnoses
                    WHERE match_date BETWEEN ? AND ?
                      AND COALESCE(is_correct, 0) = 0
                    GROUP BY match_key, play_type
                )
                SELECT d.play_type, d.error_categories_json,
                       d.collection_actions_json, d.model_actions_json
                FROM prediction_error_diagnoses d
                JOIN latest l
                  ON l.latest_rowid = d.rowid
                WHERE {' AND '.join(where)}
                """,
                [date_from, date_to, *params],
            ).fetchall()

        for row in rows:
            play_type = str(row["play_type"] or "")
            if play_type == "bqc":
                self._bump_action(counts, "bqc_half_time_profile")
                self._bump_action(counts, "bqc_full_time_axis")
            elif play_type == "rqspf":
                self._bump_action(counts, "handicap_margin_axis")
                self._bump_action(counts, "handicap_margin_gate")
            elif play_type == "ou":
                self._bump_action(counts, "national_ou_gate")
            elif play_type == "bf":
                self._bump_action(counts, "refresh_learning")

            for item in self._loads_list(row["collection_actions_json"]):
                if isinstance(item, dict):
                    self._add_mapped_diagnosis_action(
                        counts,
                        str(item.get("action") or ""),
                        DIAGNOSIS_COLLECTION_ACTIONS,
                    )
            for item in self._loads_list(row["model_actions_json"]):
                if isinstance(item, dict):
                    self._add_mapped_diagnosis_action(
                        counts,
                        str(item.get("action") or ""),
                        DIAGNOSIS_MODEL_ACTIONS,
                    )
            for category in self._loads_list(row["error_categories_json"]):
                self._add_mapped_diagnosis_action(
                    counts,
                    str(category or ""),
                    DIAGNOSIS_ERROR_CATEGORIES,
                )
        return counts

    @staticmethod
    def _parse_beijing_time(row: sqlite3.Row) -> Optional[datetime]:
        text = str(row["beijing_time"] or "").strip()
        if not text:
            date_text = str(row["match_date"] or "").strip()
            time_text = str(row["match_time"] or "").strip()[:5]
            text = f"{date_text} {time_text}" if date_text and time_text else ""
        if not text:
            return None
        for width, fmt in ((19, "%Y-%m-%d %H:%M:%S"), (16, "%Y-%m-%d %H:%M")):
            try:
                return datetime.strptime(text[:width], fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _estimated_runtime_minutes(row: sqlite3.Row) -> int:
        text = " ".join(str(row[key] or "") for key in ("league_name_cn", "match_date", "beijing_time")).lower()
        match_date = str(row["match_date"] or str(row["beijing_time"] or "")[:10] or "")
        if ("world cup" in text or "世界杯" in text) and match_date >= "2026-06-28":
            return 185
        return 130

    def _is_result_due(self, row: sqlite3.Row) -> bool:
        status = str(row["sell_status"] or "").lower()
        if status in {"finished", "finished_pending"}:
            return True
        kickoff = self._parse_beijing_time(row)
        if not kickoff:
            return status == "closed"
        minutes_since = (datetime.now() - kickoff).total_seconds() / 60
        return minutes_since > self._estimated_runtime_minutes(row)

    def infer_action_counts(
        self,
        date_from: str,
        date_to: str,
        league: Optional[str] = None,
    ) -> Dict[str, int]:
        """Infer the same high-level gap actions without requiring the frontend plan API."""
        counts: Dict[str, int] = {}

        def add(action: str) -> None:
            counts[action] = counts.get(action, 0) + 1

        with self._connect() as conn:
            has_intel = self._table_exists(conn, "intelligence_jobs") and self._table_exists(conn, "intelligence_packages")
            has_artifacts = self._table_exists(conn, "source_artifacts")
            has_source_mappings = self._table_exists(conn, "source_entity_mappings")
            has_ou = self._table_exists(conn, "oddsfe_matches")
            has_validation = self._table_exists(conn, "lottery_validation")
            has_review = self._table_exists(conn, "post_match_reviews")

            intel_expr = (
                """
                EXISTS (
                    SELECT 1
                    FROM intelligence_jobs ij
                    JOIN intelligence_packages ip ON ip.job_id = ij.job_id
                    WHERE ij.lottery_match_id = lm.lottery_match_id
                ) AS has_intelligence,
                EXISTS (
                    SELECT 1
                    FROM intelligence_jobs ij
                    JOIN intelligence_requirements ir ON ir.job_id = ij.job_id
                    WHERE ij.lottery_match_id = lm.lottery_match_id
                      AND ir.required = 1
                      AND (
                          ir.status IN ('missing', 'failed', 'stale')
                          OR (
                              ir.status = 'fallback_used'
                              AND ir.key IN ('odds_1x2', 'injuries_suspensions', 'expected_lineup', 'team_news')
                              AND COALESCE(ir.confidence, 0) < 0.70
                          )
                      )
                ) AS needs_intelligence_refresh,
                """
                if has_intel else "0 AS has_intelligence, 0 AS needs_intelligence_refresh,"
            )
            event_cache_expr = (
                """
                EXISTS (
                    SELECT 1 FROM source_artifacts sa
                    WHERE sa.source_name = 'oddsfe'
                      AND sa.entity_type = 'event'
                      AND sa.entity_id = CAST(lm.oddsfe_event_id AS TEXT)
                ) AS has_event_cache,
                """
                if has_artifacts else "0 AS has_event_cache,"
            )
            football_data_mapping_expr = (
                """
                EXISTS (
                    SELECT 1
                    FROM source_entity_mappings sem
                    WHERE sem.source_name = 'football_data_org'
                      AND sem.entity_type IN ('lottery_match', 'match')
                      AND sem.canonical_id = lm.lottery_match_id
                      AND COALESCE(sem.status, 'active') = 'active'
                ) AS has_football_data_mapping,
                """
                if has_source_mappings else "0 AS has_football_data_mapping,"
            )
            ou_expr = (
                """
                EXISTS (
                    SELECT 1 FROM oddsfe_matches om
                    WHERE CAST(om.event_id AS TEXT) = CAST(lm.oddsfe_event_id AS TEXT)
                      AND om.ou_pinnacle_line IS NOT NULL
                      AND om.ou_pinnacle_line != ''
                      AND om.ou_pinnacle_over IS NOT NULL
                      AND om.ou_pinnacle_over != ''
                      AND om.ou_pinnacle_under IS NOT NULL
                      AND om.ou_pinnacle_under != ''
                ) AS has_ou_line,
                """
                if has_ou else "0 AS has_ou_line,"
            )
            validation_expr = (
                """
                EXISTS (
                    SELECT 1 FROM lottery_validation lv
                    WHERE lv.lottery_match_id = lm.lottery_match_id
                ) AS has_validation,
                """
                if has_validation else "0 AS has_validation,"
            )
            review_expr = (
                """
                EXISTS (
                    SELECT 1 FROM post_match_reviews pr
                    WHERE pr.match_key = lm.lottery_match_id
                ) AS has_post_review
                """
                if has_review else "0 AS has_post_review"
            )

            where = [
                "substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?",
                "lm.home_team_id IS NOT NULL",
                "lm.away_team_id IS NOT NULL",
            ]
            params: List[Any] = [date_from, date_to]
            if league:
                where.append("COALESCE(lm.league_name_cn, '') = ?")
                params.append(league)

            rows = conn.execute(
                f"""
                SELECT lm.lottery_match_id,
                       lm.league_name_cn,
                       lm.match_date,
                       lm.match_time,
                       lm.beijing_time,
                       lm.sell_status,
                       lm.oddsfe_event_id,
                       EXISTS (
                           SELECT 1 FROM lottery_odds lo
                           WHERE lo.lottery_match_id = lm.lottery_match_id
                             AND lo.play_type IN ('spf', 'rqspf')
                       ) AS has_odds,
                       EXISTS (
                           SELECT 1 FROM lottery_results lr
                           WHERE lr.lottery_match_id = lm.lottery_match_id
                             AND lr.home_goals_ft IS NOT NULL
                             AND lr.away_goals_ft IS NOT NULL
                       ) AS has_score,
                       EXISTS (
                           SELECT 1 FROM lottery_results lr
                           WHERE lr.lottery_match_id = lm.lottery_match_id
                             AND lr.home_goals_ht IS NOT NULL
                             AND lr.away_goals_ht IS NOT NULL
                       ) AS has_half,
                       EXISTS (
                           SELECT 1 FROM lottery_analysis_reports ar
                           WHERE ar.lottery_match_id = lm.lottery_match_id
                             AND ar.report_type IN ('prediction', 'full')
                             AND COALESCE(ar.is_stale, 0) = 0
                       ) AS has_analysis,
                       {intel_expr}
                       {event_cache_expr}
                       {football_data_mapping_expr}
                       {ou_expr}
                       {validation_expr}
                       {review_expr}
                FROM lottery_matches lm
                WHERE {' AND '.join(where)}
                ORDER BY COALESCE(lm.beijing_time, lm.match_date || ' ' || COALESCE(lm.match_time, '99:99')),
                         lm.lottery_match_id
                """,
                params,
            ).fetchall()

        for row in rows:
            event_id = str(row["oddsfe_event_id"] or "").strip()
            result_due = self._is_result_due(row)
            has_score = bool(row["has_score"])
            has_analysis = bool(row["has_analysis"])
            has_validation = bool(row["has_validation"])
            is_world_cup = str(row["league_name_cn"] or "") == "\u4e16\u754c\u676f"
            has_football_data_mapping = bool(row["has_football_data_mapping"])

            if not row["has_odds"]:
                add("collect_odds")
            if is_world_cup:
                needs_football_data_wc = False
                if result_due:
                    needs_football_data_wc = (
                        not has_football_data_mapping
                        or not has_score
                        or not bool(row["has_half"])
                    )
                else:
                    needs_football_data_wc = not has_football_data_mapping
                if needs_football_data_wc:
                    add("sync_football_data_wc")
            if event_id and not row["has_event_cache"]:
                add("sync_event_detail")
            if event_id and not row["has_ou_line"]:
                add("sync_ou_line")
            if result_due and (not has_score or not row["has_half"]) and event_id:
                add("sync_event_detail")
            if result_due and has_score:
                add("audit_results")
            if not has_analysis:
                add("analyze")
            if not row["has_intelligence"] or row["needs_intelligence_refresh"]:
                add("collect_intelligence")
            if result_due and has_score and has_analysis and not has_validation:
                add("validate")
            if result_due and has_score and has_validation and not row["has_post_review"]:
                add("refresh_learning")

        for action, amount in self._diagnosis_action_counts(date_from, date_to, league=league).items():
            counts[action] = int(counts.get(action) or 0) + int(amount or 0)

        return counts

    def run(
        self,
        date_from: str,
        date_to: str,
        *,
        action_counts: Optional[Dict[str, int]] = None,
        max_events: int = 8,
        max_analysis: int = 12,
        max_intelligence: int = 8,
        max_validation_dates: int = 4,
        fetch_live_ou: bool = True,
        network_intelligence: bool = True,
        league: Optional[str] = None,
        trigger_source: str = "manual_auto_gap_fill",
    ) -> Dict[str, Any]:
        inferred = action_counts is None
        actions = action_counts if action_counts is not None else self.infer_action_counts(date_from, date_to, league=league)
        run_id = self.foundation.start_run(
            run_type="auto_gap_fill",
            match_date=date_from,
            trigger_source=trigger_source,
            summary={
                "stage": "start",
                "date_from": date_from,
                "date_to": date_to,
                "league": league or "",
                "action_source": "inferred" if inferred else "provided",
                "action_counts": actions,
            },
        )
        summary: Dict[str, Any] = {
            "date_from": date_from,
            "date_to": date_to,
            "league": league or "",
            "action_source": "inferred" if inferred else "provided",
            "action_counts": actions,
            "steps": {},
        }
        try:
            if self._should_run(actions, "sync_football_data_wc"):
                summary["steps"]["football_data_wc"] = self._sync_football_data_wc(
                    date_from,
                    date_to,
                    max_matches=max_events,
                )
            else:
                summary["steps"]["football_data_wc"] = self._skip("no football-data.org WC gap")

            if self._should_run(actions, "sync_event_detail", "collect_odds"):
                summary["steps"]["event_details"] = self._sync_event_details(
                    date_from,
                    date_to,
                    max_events=max_events,
                )
            else:
                summary["steps"]["event_details"] = self._skip("no event/score/odds gap")

            if self._should_run(actions, "sync_ou_line"):
                summary["steps"]["ou_lines"] = self._sync_ou_lines(
                    date_from,
                    date_to,
                    max_events=max_events,
                    fetch_live=fetch_live_ou,
                )
            else:
                summary["steps"]["ou_lines"] = self._skip("no O/U line gap")

            if self._should_run(actions, "audit_results", "sync_event_detail", "sync_ou_line", "sync_football_data_wc"):
                summary["steps"]["result_consistency"] = self._audit_result_consistency(
                    date_from,
                    date_to,
                    league=league,
                )
            else:
                summary["steps"]["result_consistency"] = self._skip("no settled result audit needed")

            result_audit_changed = int(
                (summary["steps"].get("result_consistency") or {}).get("rows_changed") or 0
            ) > 0
            football_data_changed = (
                int((summary["steps"].get("football_data_wc") or {}).get("lottery_results_inserted") or 0)
                + int((summary["steps"].get("football_data_wc") or {}).get("lottery_results_updated") or 0)
            ) > 0

            if self._should_run(actions, "collect_intelligence"):
                summary["steps"]["intelligence"] = self._fill_intelligence_gaps(
                    date_from,
                    date_to,
                    limit=max_intelligence,
                    network=network_intelligence,
                )
            else:
                summary["steps"]["intelligence"] = self._skip("no intelligence gap")

            if self._should_run(actions, "analyze", "collect_intelligence", "sync_ou_line"):
                summary["steps"]["analysis"] = self._analyze_missing_or_stale(
                    date_from,
                    date_to,
                    limit=max_analysis,
                    league=league,
                )
            else:
                summary["steps"]["analysis"] = self._skip("no analysis gap")

            if self._should_run(actions, "validate") or result_audit_changed or football_data_changed:
                summary["steps"]["validation"] = self._validate_dates(
                    date_from,
                    date_to,
                    max_dates=max_validation_dates,
                )
            else:
                summary["steps"]["validation"] = self._skip("no validation gap")

            if self._should_run(actions, "refresh_learning", "validate", "analyze") or result_audit_changed or football_data_changed:
                summary["steps"]["learning"] = self._refresh_learning(date_from, date_to, league=league)
            else:
                summary["steps"]["learning"] = self._skip("no learning refresh needed")

            self.foundation.finish_run(run_id, status="success", summary=summary)
            return {"success": True, "run_id": run_id, **summary}
        except Exception as exc:
            summary["error"] = str(exc)
            self.foundation.finish_run(run_id, status="failed", summary=summary, error=str(exc))
            logger.error("auto gap fill failed: %s", exc, exc_info=True)
            return {"success": False, "run_id": run_id, **summary}

    @staticmethod
    def _skip(reason: str) -> Dict[str, Any]:
        return {"skipped": True, "reason": reason}

    @staticmethod
    def _should_run(actions: Dict[str, int], *names: str) -> bool:
        return any(int(actions.get(name) or 0) > 0 for name in names)

    def _sync_event_details(self, date_from: str, date_to: str, max_events: int) -> Dict[str, Any]:
        from backend.app.lottery.services.oddsfe_event_sync import OddsfeEventDetailSync

        sync = OddsfeEventDetailSync(self.db_path)
        return sync.run(
            date_from,
            date_to,
            apply=True,
            refresh=False,
            fetch_schedule=True,
            include_schedule_only=True,
            max_events=max_events,
            schedule_padding_days=1,
            cache_minutes=12,
            sleep_seconds=0.12,
            trigger_source="auto_gap_fill",
        )

    def _sync_football_data_wc(self, date_from: str, date_to: str, max_matches: int) -> Dict[str, Any]:
        from backend.app.lottery.services.football_data_wc_sync import FootballDataWorldCupSync

        sync = FootballDataWorldCupSync(self.db_path)
        return sync.run(
            date_from,
            date_to,
            apply=True,
            season=2026,
            overwrite_results=False,
            max_matches=max_matches,
            trigger_source="auto_gap_fill",
        )

    def _sync_ou_lines(
        self,
        date_from: str,
        date_to: str,
        *,
        max_events: int,
        fetch_live: bool,
    ) -> Dict[str, Any]:
        from backend.app.lottery.services.oddsfe_ou_line_sync import OddsfeOuLineSync

        sync = OddsfeOuLineSync(self.db_path, self.oddsfe_db_path)
        return sync.run(
            date_from,
            date_to,
            apply=True,
            fetch_live=fetch_live,
            max_events=max_events,
            reanalyze=False,
            trigger_source="auto_gap_fill",
        )

    def _audit_result_consistency(
        self,
        date_from: str,
        date_to: str,
        *,
        league: Optional[str] = None,
    ) -> Dict[str, Any]:
        from backend.app.lottery.services.result_consistency import run_result_consistency_audit

        return run_result_consistency_audit(
            self.db_path,
            date_from,
            date_to,
            apply=True,
            league=league,
            trigger_source="auto_gap_fill",
        )

    def _fill_intelligence_gaps(
        self,
        date_from: str,
        date_to: str,
        *,
        limit: int,
        network: bool,
    ) -> Dict[str, Any]:
        from backend.app.intelligence.service import IntelligenceService

        result = IntelligenceService(self.db_path).fill_gaps_logged(
            start_date=date_from,
            end_date=date_to,
            collectors=None,  # channel-driven selection
            network=network,
            force=False,
            include_optional=True,
            include_builtin=True,
            limit=limit,
            failed_retry_minutes=90,
            fallback_retry_minutes=30,
            trigger_source="auto_gap_fill",
        )

        # Mark analysis reports as stale for matches where intelligence improved
        self._mark_stale_after_intel(date_from, date_to)
        # Consume resolved next_data_requirements
        self._consume_next_data_requirements(date_from, date_to)
        return result

    def _mark_stale_after_intel(self, date_from: str, date_to: str) -> int:
        """After intelligence collection, mark analysis reports as stale
        for unstarted matches that got new intelligence artifacts."""
        try:
            with self._connect() as conn:
                # Find matches that got new intelligence artifacts today
                # AND already have an analysis report that isn't stale
                updated = conn.execute(
                    """
                    UPDATE lottery_analysis_reports
                    SET is_stale = 1
                    WHERE lottery_match_id IN (
                        SELECT DISTINCT ij.lottery_match_id
                        FROM intelligence_jobs ij
                        JOIN intelligence_packages ip ON ip.job_id = ij.job_id
                        JOIN lottery_matches lm ON ij.lottery_match_id = lm.lottery_match_id
                        WHERE ip.updated_at >= datetime('now', '-30 minutes')
                          AND substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?
                          AND COALESCE(lm.beijing_time, lm.match_date) > datetime('now')
                    )
                    AND is_stale = 0
                    AND report_type IN ('prediction', 'full')
                    """,
                    (date_from, date_to),
                ).rowcount
                if updated:
                    conn.commit()
                    logger.info('Marked %d analysis reports stale after intel collection', updated)
                return updated
        except Exception as e:
            logger.debug('mark_stale_after_intel failed: %s', e)
            return 0

    def _consume_next_data_requirements(self, date_from: str, date_to: str) -> int:
        """After intelligence collection, mark next_data_requirements as resolved
        for matches that now have the required intelligence."""
        try:
            with self._connect() as conn:
                # Check if table exists
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='next_data_requirements'"
                ).fetchone()
                if not exists:
                    return 0

                # Mark requirements as resolved for matches that now have
                # collected intelligence artifacts in the relevant category
                resolved = conn.execute(
                    """
                    UPDATE next_data_requirements
                    SET status = 'resolved', resolved_at = datetime('now')
                    WHERE status = 'pending'
                      AND lottery_match_id IN (
                          SELECT DISTINCT ij.lottery_match_id
                          FROM intelligence_jobs ij
                          JOIN intelligence_packages ip ON ip.job_id = ij.job_id
                          WHERE ip.updated_at >= datetime('now', '-30 minutes')
                            AND ip.completeness > 0.5
                      )
                    """,
                ).rowcount
                if resolved:
                    conn.commit()
                    logger.info('Resolved %d next_data_requirements after intel collection', resolved)
                return resolved
        except Exception as e:
            logger.debug('consume_next_data_requirements failed: %s', e)
            return 0

    def _select_analysis_targets(
        self,
        date_from: str,
        date_to: str,
        limit: int,
        league: Optional[str] = None,
    ) -> List[str]:
        with self._connect() as conn:
            where = [
                "substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?",
                "lm.home_team_id IS NOT NULL",
                "lm.away_team_id IS NOT NULL",
                """
                (
                    lr.lottery_match_id IS NULL
                    OR COALESCE(lr.is_stale, 0) = 1
                )
                """,
            ]
            params: List[Any] = [date_from, date_to]
            if league:
                where.append("COALESCE(lm.league_name_cn, '') = ?")
                params.append(league)
            params.append(limit)
            rows = conn.execute(
                f"""
                WITH latest_report_ids AS (
                    SELECT lottery_match_id, MAX(report_id) AS latest_report_id
                    FROM lottery_analysis_reports
                    WHERE report_type = 'prediction'
                    GROUP BY lottery_match_id
                ),
                latest_reports AS (
                    SELECT r.lottery_match_id, COALESCE(r.is_stale, 0) AS is_stale
                    FROM lottery_analysis_reports r
                    JOIN latest_report_ids lr ON lr.latest_report_id = r.report_id
                )
                SELECT lm.lottery_match_id
                FROM lottery_matches lm
                LEFT JOIN latest_reports lr ON lr.lottery_match_id = lm.lottery_match_id
                WHERE {' AND '.join(where)}
                ORDER BY substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10), lm.match_time, lm.lottery_match_id
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [str(row["lottery_match_id"]) for row in rows]

    def _analyze_missing_or_stale(
        self,
        date_from: str,
        date_to: str,
        limit: int,
        league: Optional[str] = None,
    ) -> Dict[str, Any]:
        from backend.app.core.analyze import analyze_single

        targets = self._select_analysis_targets(date_from, date_to, limit, league=league)
        analyzed = []
        failed = []
        for lottery_match_id in targets:
            try:
                report = analyze_single(self.db_path, lottery_match_id)
                if report:
                    analyzed.append(lottery_match_id)
                else:
                    failed.append({"lottery_match_id": lottery_match_id, "error": "empty_report"})
            except Exception as exc:
                failed.append({"lottery_match_id": lottery_match_id, "error": str(exc)[:180]})
        return {
            "targets": len(targets),
            "analyzed": len(analyzed),
            "failed": len(failed),
            "analyzed_ids": analyzed[:20],
            "failed_examples": failed[:5],
        }

    def _latest_prediction_report_meta(self, lottery_match_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT report_id, created_at, report_data
                FROM lottery_analysis_reports
                WHERE lottery_match_id = ?
                  AND report_type = 'prediction'
                  AND COALESCE(is_stale, 0) = 0
                ORDER BY datetime(created_at) DESC, report_id DESC
                LIMIT 1
                """,
                (lottery_match_id,),
            ).fetchone()
        if not row:
            return {}
        report_data = {}
        try:
            report_data = json.loads(row["report_data"] or "{}")
            if not isinstance(report_data, dict):
                report_data = {}
        except Exception:
            report_data = {}
        return {
            "report_id": row["report_id"],
            "created_at": row["created_at"],
            "report_data": report_data,
            "prediction_summary": self._prediction_summary(report_data),
        }

    @staticmethod
    def _stable_json(value: Any) -> str:
        return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True, default=str)

    def _ensure_reanalysis_change_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_reanalysis_changes (
                change_id TEXT PRIMARY KEY,
                run_id TEXT,
                trigger_source TEXT,
                lottery_match_id TEXT NOT NULL,
                match_date TEXT,
                match_num TEXT,
                league_name_cn TEXT,
                home_team_cn TEXT,
                away_team_cn TEXT,
                before_report_id TEXT,
                after_report_id TEXT,
                prediction_changed INTEGER NOT NULL DEFAULT 0,
                change_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                settled_at TEXT,
                validation_json TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prediction_reanalysis_changes_run ON prediction_reanalysis_changes(run_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_prediction_reanalysis_changes_match "
            "ON prediction_reanalysis_changes(lottery_match_id, created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_prediction_reanalysis_changes_changed "
            "ON prediction_reanalysis_changes(prediction_changed, created_at)"
        )

    def _save_reanalysis_change_rows(
        self,
        *,
        run_id: Optional[str],
        trigger_source: str,
        rows: List[Dict[str, Any]],
    ) -> int:
        if not rows:
            return 0
        saved = 0
        with self._connect() as conn:
            self._ensure_reanalysis_change_table(conn)
            for item in rows:
                raw_id = "|".join(
                    str(item.get(key) or "")
                    for key in ("lottery_match_id", "before_report_id", "after_report_id")
                )
                raw_id = f"{run_id or trigger_source}|{raw_id}"
                change_id = "rchg_" + sha256(raw_id.encode("utf-8")).hexdigest()[:32]
                change_json = {
                    "match": item.get("match"),
                    "before_prediction_summary": item.get("before_prediction_summary") or {},
                    "after_prediction_summary": item.get("after_prediction_summary") or {},
                    "prediction_changes": item.get("prediction_changes") or [],
                }
                conn.execute(
                    """
                    INSERT OR REPLACE INTO prediction_reanalysis_changes
                    (change_id, run_id, trigger_source, lottery_match_id, match_date,
                     match_num, league_name_cn, home_team_cn, away_team_cn,
                     before_report_id, after_report_id, prediction_changed, change_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        change_id,
                        run_id,
                        trigger_source,
                        item.get("lottery_match_id"),
                        item.get("match_date"),
                        item.get("match_num"),
                        item.get("league_name_cn"),
                        item.get("home_team_cn"),
                        item.get("away_team_cn"),
                        None if item.get("before_report_id") is None else str(item.get("before_report_id")),
                        None if item.get("after_report_id") is None else str(item.get("after_report_id")),
                        1 if item.get("prediction_changed") else 0,
                        self._stable_json(change_json),
                    ),
                )
                saved += 1
            conn.commit()
        return saved

    def settle_reanalysis_changes(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        *,
        league: Optional[str] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        with self._connect() as conn:
            if not self._table_exists(conn, "prediction_reanalysis_changes"):
                return {"skipped": True, "reason": "prediction_reanalysis_changes_missing"}
            if not self._table_exists(conn, "lottery_validation"):
                return {"skipped": True, "reason": "lottery_validation_missing"}

            where = ["prc.settled_at IS NULL"]
            params: List[Any] = []
            if date_from and date_to:
                where.append("substr(COALESCE(lm.beijing_time, lm.match_date, prc.match_date), 1, 10) BETWEEN ? AND ?")
                params.extend([date_from, date_to])
            if league:
                where.append("COALESCE(lm.league_name_cn, prc.league_name_cn, '') = ?")
                params.append(league)
            params.append(limit)
            changes = conn.execute(
                f"""
                SELECT prc.change_id, prc.lottery_match_id, prc.change_json,
                       COALESCE(lm.beijing_time, lm.match_date, prc.match_date) AS match_date
                FROM prediction_reanalysis_changes prc
                LEFT JOIN lottery_matches lm ON lm.lottery_match_id = prc.lottery_match_id
                WHERE {' AND '.join(where)}
                ORDER BY datetime(prc.created_at) ASC
                LIMIT ?
                """,
                params,
            ).fetchall()

            settled = 0
            pending = 0
            examples: List[Dict[str, Any]] = []
            for change in changes:
                rows = conn.execute(
                    """
                    SELECT play_type, predicted_result, actual_result, is_correct,
                           predicted_prob, confidence, validated_at
                    FROM lottery_validation
                    WHERE lottery_match_id = ?
                      AND predicted_result IS NOT NULL
                      AND actual_result IS NOT NULL
                    ORDER BY play_type
                    """,
                    (change["lottery_match_id"],),
                ).fetchall()
                if not rows:
                    pending += 1
                    continue
                validations = []
                correct = 0
                for row in rows:
                    hit = bool(row["is_correct"])
                    correct += 1 if hit else 0
                    validations.append({
                        "play_type": row["play_type"],
                        "predicted_result": row["predicted_result"],
                        "actual_result": row["actual_result"],
                        "is_correct": hit,
                        "predicted_prob": row["predicted_prob"],
                        "confidence": row["confidence"],
                        "validated_at": row["validated_at"],
                    })
                payload = {
                    "lottery_match_id": change["lottery_match_id"],
                    "validated_plays": len(validations),
                    "correct_plays": correct,
                    "accuracy": round(correct * 100 / len(validations), 1) if validations else 0,
                    "validations": validations,
                }
                conn.execute(
                    """
                    UPDATE prediction_reanalysis_changes
                    SET settled_at = CURRENT_TIMESTAMP,
                        validation_json = ?
                    WHERE change_id = ?
                    """,
                    (self._stable_json(payload), change["change_id"]),
                )
                settled += 1
                if len(examples) < 8:
                    examples.append({
                        "change_id": change["change_id"],
                        "lottery_match_id": change["lottery_match_id"],
                        "accuracy": payload["accuracy"],
                        "validated_plays": len(validations),
                    })
            conn.commit()

        return {
            "checked": len(changes),
            "settled": settled,
            "pending_without_validation": pending,
            "examples": examples,
        }

    @staticmethod
    def _format_score_candidates(items: Any) -> str:
        if not isinstance(items, list):
            return ""
        values: List[str] = []
        for item in items[:3]:
            if not isinstance(item, dict):
                continue
            score = item.get("score")
            if isinstance(score, (list, tuple)) and len(score) >= 2:
                score_text = f"{score[0]}-{score[1]}"
            else:
                score_text = str(score or item.get("score_text") or "").strip()
            if not score_text:
                home = item.get("home_goals")
                away = item.get("away_goals")
                if home is not None and away is not None:
                    score_text = f"{home}-{away}"
            if score_text:
                values.append(score_text)
        return "/".join(values)

    @staticmethod
    def _play_pick(play: Any, *keys: str) -> str:
        if not isinstance(play, dict):
            return ""
        for key in keys:
            value = play.get(key)
            if value not in (None, "", {}, []):
                return str(value)
        return ""

    @classmethod
    def _prediction_summary(cls, report: Dict[str, Any]) -> Dict[str, str]:
        if not isinstance(report, dict):
            return {}
        final = report.get("final_prediction") if isinstance(report.get("final_prediction"), dict) else {}
        plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
        spf = plays.get("spf") if isinstance(plays.get("spf"), dict) else {}
        rqspf = plays.get("rqspf") if isinstance(plays.get("rqspf"), dict) else {}
        bqc = plays.get("bqc") if isinstance(plays.get("bqc"), dict) else {}
        ou = plays.get("ou") if isinstance(plays.get("ou"), dict) else {}
        top_scores = plays.get("top3_scores") or final.get("most_likely_scores")

        ou_line = cls._play_pick(ou, "goal_line_label", "line", "best_line", "goal_line")
        ou_rec = cls._play_pick(ou, "recommendation_cn", "recommendation", "direction", "side")
        if ou_line and ou_rec and str(ou_line) not in str(ou_rec):
            ou_rec = f"{ou_rec}@{ou_line}"

        return {
            "main": cls._play_pick(final, "predicted_result", "recommendation", "direction"),
            "confidence": cls._play_pick(final, "confidence_level"),
            "spf": cls._play_pick(spf, "recommendation_cn", "recommendation", "direction")
            or cls._play_pick(final, "predicted_result"),
            "rqspf": cls._play_pick(rqspf, "recommendation_cn", "recommendation", "direction"),
            "bqc": cls._play_pick(bqc, "recommendation_cn", "recommendation", "direction"),
            "ou": ou_rec,
            "scores": cls._format_score_candidates(top_scores),
        }

    @classmethod
    def _prediction_changes(
        cls,
        before: Dict[str, Any],
        after: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        labels = {
            "main": "主推荐",
            "confidence": "信心",
            "spf": "胜平负",
            "rqspf": "让球",
            "bqc": "半全场",
            "ou": "大小球",
            "scores": "比分",
        }
        before_summary = before.get("prediction_summary") or {}
        after_summary = after.get("prediction_summary") or {}
        changes: List[Dict[str, str]] = []
        for key, label in labels.items():
            left = str(before_summary.get(key) or "").strip()
            right = str(after_summary.get(key) or "").strip()
            if left != right:
                changes.append({
                    "field": key,
                    "label": label,
                    "before": left or "-",
                    "after": right or "-",
                })
        return changes

    def _select_unstarted_reanalysis_targets(
        self,
        date_from: str,
        date_to: str,
        *,
        league: Optional[str] = None,
        limit: int = 24,
    ) -> List[sqlite3.Row]:
        now = datetime.now()
        with self._connect() as conn:
            where = [
                "substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?",
                "lm.home_team_id IS NOT NULL",
                "lm.away_team_id IS NOT NULL",
                """
                NOT EXISTS (
                    SELECT 1 FROM lottery_results lr
                    WHERE lr.lottery_match_id = lm.lottery_match_id
                      AND lr.home_goals_ft IS NOT NULL
                      AND lr.away_goals_ft IS NOT NULL
                )
                """,
            ]
            params: List[Any] = [date_from, date_to]
            if league:
                where.append("COALESCE(lm.league_name_cn, '') = ?")
                params.append(league)
            params.append(limit)
            rows = conn.execute(
                f"""
                SELECT lm.lottery_match_id,
                       lm.match_num,
                       lm.league_name_cn,
                       lm.home_team_cn,
                       lm.away_team_cn,
                       lm.match_date,
                       lm.match_time,
                       lm.beijing_time,
                       lm.sell_status
                FROM lottery_matches lm
                WHERE {' AND '.join(where)}
                ORDER BY COALESCE(lm.beijing_time, lm.match_date || ' ' || COALESCE(lm.match_time, '99:99')),
                         lm.lottery_match_id
                LIMIT ?
                """,
                params,
            ).fetchall()

        targets: List[sqlite3.Row] = []
        for row in rows:
            kickoff = self._parse_beijing_time(row)
            # Do not rewrite a pre-match prediction once the match has kicked off.
            # Result fetching/validation owns that phase so we avoid hindsight leakage.
            if kickoff and kickoff <= now:
                continue
            targets.append(row)
        return targets

    def reanalyze_unstarted_after_learning(
        self,
        date_from: str,
        date_to: str,
        *,
        league: Optional[str] = None,
        limit: int = 24,
        trigger_source: str = "post_learning_refresh",
    ) -> Dict[str, Any]:
        """Refresh not-yet-started match predictions after learning assets changed."""
        from backend.app.core.analyze import analyze_single

        run_id = self.foundation.start_run(
            run_type="post_learning_future_reanalysis",
            match_date=date_from,
            trigger_source=trigger_source,
            summary={
                "stage": "start",
                "date_from": date_from,
                "date_to": date_to,
                "league": league or "",
                "limit": limit,
            },
        )
        targets = self._select_unstarted_reanalysis_targets(
            date_from,
            date_to,
            league=league,
            limit=limit,
        )
        analyzed: List[str] = []
        changed: List[Dict[str, Any]] = []
        unchanged: List[str] = []
        failed: List[Dict[str, Any]] = []

        for row in targets:
            lottery_match_id = str(row["lottery_match_id"])
            before = self._latest_prediction_report_meta(lottery_match_id)
            try:
                report = analyze_single(self.db_path, lottery_match_id)
                after = self._latest_prediction_report_meta(lottery_match_id)
                prediction_changes = self._prediction_changes(before, after)
                if report:
                    analyzed.append(lottery_match_id)
                    if after.get("report_id") != before.get("report_id"):
                        changed.append({
                            "lottery_match_id": lottery_match_id,
                            "match_num": row["match_num"],
                            "match": f"{row['home_team_cn']} vs {row['away_team_cn']}",
                            "match_date": str(row["beijing_time"] or row["match_date"] or "")[:10],
                            "league_name_cn": row["league_name_cn"],
                            "home_team_cn": row["home_team_cn"],
                            "away_team_cn": row["away_team_cn"],
                            "before_report_id": before.get("report_id"),
                            "after_report_id": after.get("report_id"),
                            "after_created_at": after.get("created_at"),
                            "prediction_changed": bool(prediction_changes),
                            "before_prediction_summary": before.get("prediction_summary") or {},
                            "after_prediction_summary": after.get("prediction_summary") or {},
                            "prediction_changes": prediction_changes[:8],
                        })
                    else:
                        unchanged.append(lottery_match_id)
                else:
                    failed.append({"lottery_match_id": lottery_match_id, "error": "empty_report"})
            except Exception as exc:
                failed.append({"lottery_match_id": lottery_match_id, "error": str(exc)[:180]})

        summary = {
            "success": len(failed) == 0,
            "date_from": date_from,
            "date_to": date_to,
            "league": league or "",
            "targets": len(targets),
            "analyzed": len(analyzed),
            "changed_reports": len(changed),
            "prediction_changed": sum(1 for item in changed if item.get("prediction_changed")),
            "change_rows_saved": 0,
            "unchanged": len(unchanged),
            "failed": len(failed),
            "changed_examples": changed[:12],
            "failed_examples": failed[:8],
        }
        try:
            summary["change_rows_saved"] = self._save_reanalysis_change_rows(
                run_id=run_id,
                trigger_source=trigger_source,
                rows=changed,
            )
        except Exception as exc:
            summary["change_rows_error"] = str(exc)[:180]
            logger.warning("failed to save prediction reanalysis change rows: %s", exc)
        self.foundation.finish_run(
            run_id,
            status="success" if summary["success"] else "failed",
            summary=summary,
            error=None if summary["success"] else "future reanalysis failed",
        )
        return summary

    def _validate_dates(self, date_from: str, date_to: str, max_dates: int) -> Dict[str, Any]:
        from backend.app.core.validate import _validate_predictions

        dates = date_list(date_from, date_to)[:max_dates]
        result = _validate_predictions(self.db_path, dates)
        result["queued_revalidation"] = self._mark_revalidation_processed(dates)
        if dates:
            result["reanalysis_change_settlement"] = self.settle_reanalysis_changes(
                min(dates),
                max(dates),
                limit=200,
            )
        return result

    def _mark_revalidation_processed(self, dates: List[str]) -> Dict[str, Any]:
        if not dates:
            return {"processed": 0}
        placeholders = ",".join("?" for _ in dates)
        with self._connect() as conn:
            has_queue = self._table_exists(conn, "lottery_revalidation_queue")
            if not has_queue:
                return {"skipped": True, "reason": "queue_missing"}
            rows = conn.execute(
                f"""
                SELECT q.queue_id
                FROM lottery_revalidation_queue q
                JOIN lottery_matches lm ON lm.lottery_match_id = q.lottery_match_id
                WHERE q.status = 'pending'
                  AND substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) IN ({placeholders})
                """,
                list(dates),
            ).fetchall()
            if not rows:
                return {"processed": 0}
            conn.executemany(
                """
                UPDATE lottery_revalidation_queue
                SET status = 'processed', processed_at = CURRENT_TIMESTAMP
                WHERE queue_id = ?
                """,
                [(row["queue_id"],) for row in rows],
            )
            conn.commit()
            return {"processed": len(rows)}

    def _refresh_learning(
        self,
        date_from: str,
        date_to: str,
        *,
        league: Optional[str] = None,
    ) -> Dict[str, Any]:
        with exclusive_task_lock("learning", self.db_path) as task_lock:
            if not task_lock.acquired:
                return {
                    "skipped": True,
                    "success": True,
                    "reason": "learning_task_already_running",
                    "lock_path": task_lock.path,
                    "lock_holder": task_lock.holder,
                }
            return self._refresh_learning_locked(date_from, date_to, league=league)

    def _refresh_learning_locked(
        self,
        date_from: str,
        date_to: str,
        *,
        league: Optional[str] = None,
    ) -> Dict[str, Any]:
        from scripts.backfill_data_foundation import (
            backfill_reviews,
            backfill_snapshots,
            connect,
        )
        from scripts.build_similar_match_cases import build_cases
        from scripts.build_team_match_facts import build as build_team_match_facts
        from scripts.cleanup_foundation_snapshots import cleanup_snapshots
        from scripts.diagnose_prediction_errors import run as run_error_diagnosis

        summary: Dict[str, Any] = {}
        summary["team_match_facts"] = build_team_match_facts(
            Path(self.db_path),
            date_from,
            date_to,
            league or "",
            True,
        )
        dao = FoundationDAO(self.db_path)
        conn = connect(Path(self.db_path))
        try:
            summary["reviews"] = backfill_reviews(conn, dao, None)
            summary["snapshots"] = backfill_snapshots(conn, dao, None)
        finally:
            conn.close()
        summary["snapshot_cleanup"] = cleanup_snapshots(Path(self.db_path), apply=True, backup=False)
        summary["similar_cases"] = {
            "spf": build_cases(Path(self.db_path), play_type="spf", top_k=5, min_score=0.68),
            "rqspf": build_cases(Path(self.db_path), play_type="rqspf", top_k=5, min_score=0.66),
            "bqc": build_cases(Path(self.db_path), play_type="bqc", top_k=5, min_score=0.64),
            "ou": build_cases(Path(self.db_path), play_type="ou", top_k=5, min_score=0.66),
            "bf": build_cases(Path(self.db_path), play_type="bf", top_k=5, min_score=0.62),
        }
        diagnosis = run_error_diagnosis(Namespace(
            db=self.db_path,
            date_from=date_from,
            date_to=date_to,
            league=league or "",
            match_nums="",
            limit=0,
            version_tag=f"auto_gap_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            apply=True,
            compact=True,
            summary_only=True,
        ))
        summary["error_diagnosis"] = {
            "success": diagnosis.get("success"),
            "saved": diagnosis.get("saved"),
            "summary": diagnosis.get("summary"),
            "validation_consistency": diagnosis.get("validation_consistency"),
        }
        summary["future_reanalysis"] = self.reanalyze_unstarted_after_learning(
            date_from,
            date_to,
            league=league,
            limit=24,
            trigger_source="auto_gap_post_learning",
        )
        return summary
