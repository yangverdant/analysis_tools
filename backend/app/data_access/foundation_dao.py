"""Durable collection and learning foundation writes.

These helpers are intentionally best-effort. The core collection, analysis, and
validation flows should keep running even when the foundation tables have not
been migrated yet.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True, default=str)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _compact_id(prefix: str, *parts: Any) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    return f"{prefix}_{_hash(raw)[:32]}"


def _safe_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return str(value)


class FoundationDAO:
    """Small write gateway for collection evidence, snapshots, and reviews."""

    def __init__(self, db_path: str):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def start_run(
        self,
        run_type: str,
        match_date: Any = None,
        trigger_source: str = "manual",
        summary: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        run_id = f"run_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{uuid.uuid4().hex[:8]}"
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO collection_runs
                    (run_id, trigger_source, run_type, match_date, status, summary_json)
                    VALUES (?, ?, ?, ?, 'running', ?)
                    """,
                    (run_id, trigger_source, run_type, _safe_date(match_date), _json(summary or {})),
                )
            return run_id
        except Exception as exc:
            logger.debug("foundation start_run skipped: %s", exc)
            return None

    def finish_run(
        self,
        run_id: Optional[str],
        status: str = "success",
        summary: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        if not run_id:
            return
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE collection_runs
                    SET status = ?, finished_at = CURRENT_TIMESTAMP,
                        summary_json = ?, error = ?
                    WHERE run_id = ?
                    """,
                    (status, _json(summary or {}), error, run_id),
                )
        except Exception as exc:
            logger.debug("foundation finish_run skipped: %s", exc)

    def update_run(
        self,
        run_id: Optional[str],
        status: str = "running",
        summary: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        if not run_id:
            return
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE collection_runs
                    SET status = ?, summary_json = ?, error = ?
                    WHERE run_id = ?
                    """,
                    (status, _json(summary or {}), error, run_id),
                )
        except Exception as exc:
            logger.debug("foundation update_run skipped: %s", exc)

    def record_artifact(
        self,
        source_name: str,
        payload: Any,
        run_id: Optional[str] = None,
        source_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[Any] = None,
        confidence: float = 0.5,
    ) -> Optional[str]:
        payload_json = _json(payload)
        payload_hash = _hash(payload_json)
        artifact_id = _compact_id("art", source_name, entity_type, entity_id, payload_hash)
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO source_artifacts
                    (artifact_id, run_id, source_name, source_type, entity_type,
                     entity_id, payload_json, payload_hash, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        run_id,
                        source_name,
                        source_type,
                        entity_type,
                        None if entity_id is None else str(entity_id),
                        payload_json,
                        payload_hash,
                        confidence,
                    ),
                )
            return artifact_id
        except Exception as exc:
            logger.debug("foundation record_artifact skipped: %s", exc)
            return None

    def upsert_mapping(
        self,
        entity_type: str,
        source_name: str,
        source_entity_id: Any,
        canonical_id: Optional[Any] = None,
        source_entity_name: Optional[str] = None,
        confidence: float = 0.5,
        status: str = "active",
    ) -> Optional[str]:
        if source_entity_id is None:
            return None
        mapping_id = _compact_id("map", entity_type, source_name, source_entity_id)
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO source_entity_mappings
                    (mapping_id, entity_type, canonical_id, source_name, source_entity_id,
                     source_entity_name, confidence, status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        mapping_id,
                        entity_type,
                        None if canonical_id is None else str(canonical_id),
                        source_name,
                        str(source_entity_id),
                        source_entity_name,
                        confidence,
                        status,
                    ),
                )
            return mapping_id
        except Exception as exc:
            logger.debug("foundation upsert_mapping skipped: %s", exc)
            return None

    def save_context_snapshot(
        self,
        match_key: Any,
        competition_context: Optional[Dict[str, Any]] = None,
        odds_context: Optional[Dict[str, Any]] = None,
        intel_context: Optional[Dict[str, Any]] = None,
        data_quality: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if match_key is None:
            return None
        payload = {
            "competition": competition_context or {},
            "odds": odds_context or {},
            "intel": intel_context or {},
            "quality": data_quality or {},
        }
        source_report_id = (data_quality or {}).get("source_report_id")
        snapshot_id = (
            _compact_id("ctx", match_key, source_report_id)
            if source_report_id is not None
            else _compact_id("ctx", match_key, _json(payload))
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO match_context_snapshots
                    (snapshot_id, match_key, competition_context_json,
                     odds_context_json, intel_context_json, data_quality_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        str(match_key),
                        _json(competition_context or {}),
                        _json(odds_context or {}),
                        _json(intel_context or {}),
                        _json(data_quality or {}),
                    ),
                )
            return snapshot_id
        except Exception as exc:
            logger.debug("foundation save_context_snapshot skipped: %s", exc)
            return None

    def save_feature_snapshot(
        self,
        match_key: Any,
        features: Dict[str, Any],
        model_version: Optional[str] = None,
        source_report_id: Optional[Any] = None,
    ) -> Optional[str]:
        if match_key is None:
            return None
        feature_json = _json(features or {})
        snapshot_id = (
            _compact_id("feat", match_key, source_report_id)
            if source_report_id is not None
            else _compact_id("feat", match_key, feature_json)
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO match_feature_snapshots
                    (snapshot_id, match_key, feature_json, model_version, source_report_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        str(match_key),
                        feature_json,
                        model_version,
                        None if source_report_id is None else str(source_report_id),
                    ),
                )
            return snapshot_id
        except Exception as exc:
            logger.debug("foundation save_feature_snapshot skipped: %s", exc)
            return None

    def save_post_match_review(
        self,
        match_key: Any,
        play_type: Optional[str],
        predicted_result: Optional[str],
        actual_result: Optional[str],
        is_correct: Optional[bool],
        attribution: Optional[str] = None,
        review: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if match_key is None:
            return None
        safe_play = play_type or "unknown"
        review_id = _compact_id("review", match_key, safe_play)
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO post_match_reviews
                    (review_id, match_key, play_type, predicted_result, actual_result,
                     is_correct, attribution, review_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        review_id,
                        str(match_key),
                        safe_play,
                        predicted_result,
                        actual_result,
                        None if is_correct is None else int(bool(is_correct)),
                        attribution,
                        _json(review or {}),
                    ),
                )
            return review_id
        except Exception as exc:
            logger.debug("foundation save_post_match_review skipped: %s", exc)
            return None

    def save_similar_case(
        self,
        match_key: Any,
        similar_match_key: Any,
        similarity_score: float,
        similarity: Optional[Dict[str, Any]] = None,
        outcome: Optional[Dict[str, Any]] = None,
        play_type: Optional[str] = None,
    ) -> Optional[str]:
        if match_key is None or similar_match_key is None:
            return None
        safe_play = (
            play_type
            or (outcome or {}).get("play_type")
            or (similarity or {}).get("play_type")
            or "unknown"
        )
        case_id = _compact_id("case", match_key, safe_play, similar_match_key)
        try:
            with self._connect() as conn:
                columns = {row["name"] for row in conn.execute("PRAGMA table_info(similar_match_cases)")}
                if "play_type" in columns:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO similar_match_cases
                        (case_id, match_key, play_type, similar_match_key,
                         similarity_score, similarity_json, outcome_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            case_id,
                            str(match_key),
                            str(safe_play),
                            str(similar_match_key),
                            float(similarity_score),
                            _json(similarity or {}),
                            _json(outcome or {}),
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO similar_match_cases
                        (case_id, match_key, similar_match_key, similarity_score,
                         similarity_json, outcome_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            case_id,
                            str(match_key),
                            str(similar_match_key),
                            float(similarity_score),
                            _json(similarity or {}),
                            _json(outcome or {}),
                        ),
                    )
            return case_id
        except Exception as exc:
            logger.debug("foundation save_similar_case skipped: %s", exc)
            return None


def db_path_from_connection(conn: sqlite3.Connection) -> Optional[str]:
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        if not row:
            return None
        return str(Path(row[2]))
    except Exception:
        return None
