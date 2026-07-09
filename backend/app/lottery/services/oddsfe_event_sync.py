"""oddsfe event detail sync for durable score/result evidence.

This service is intentionally separate from list/query routes. It fetches
oddsfe event detail in a background/manual collection flow, stores raw event
payloads in source_artifacts, and fills lottery_results only when a row can be
matched to a lottery match.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import hashlib
import re
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from backend.app.data_access.foundation_dao import FoundationDAO
from backend.app.lottery.services.sync_service import (
    _derive_play_types,
    _effective_handicap,
    _event_fulltime_score,
    _oddsfe_fetch_schedule,
    _oddsfe_fetch_score_details,
    _parse_score_details,
    _normalize_bqc_result,
    _resolve_bqc_result,
)

logger = logging.getLogger(__name__)

FINISHED_STATUSES = {"FINISHED", "FT", "ENDED", "AET", "AP"}
ACTIVE_STATUSES = {"LIVE", "INPLAY", "IN_PROGRESS", "1H", "2H", "HT", "ET", "PEN"}


def _date_range(date_from: str, date_to: str) -> Iterable[str]:
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    current = start
    while current <= end:
        yield current.isoformat()
        current += timedelta(days=1)


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("T", " ").replace("Z", "").split(".")[0]
    for width, fmt in ((19, "%Y-%m-%d %H:%M:%S"), (16, "%Y-%m-%d %H:%M")):
        try:
            return datetime.strptime(text[:width], fmt)
        except ValueError:
            continue
    return None


def _event_id(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


def _norm_name(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "", str(value or "").lower())
    aliases = {
        "czechrepublic": "czechia",
        "czech": "czechia",
        "southkorea": "korearepublic",
        "korea": "korearepublic",
        "unitedstates": "usa",
        "unitedstatesofamerica": "usa",
        "usmnt": "usa",
        "drcongo": "congodr",
        "drc": "congodr",
        "democraticrepublicofthecongo": "congodr",
        "cotedivoire": "ivorycoast",
        "cotedivoire": "ivorycoast",
        "bosniaherzegovina": "bosniah",
        "bosniaandherzegovina": "bosniah",
    }
    return aliases.get(text, text)


def _payload_json(payload: Any) -> str:
    return json.dumps(payload if payload is not None else {}, ensure_ascii=False, sort_keys=True, default=str)


def _payload_hash(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _artifact_id(source_name: str, entity_type: str, entity_id: str, payload_hash: str) -> str:
    raw = f"{source_name}|{entity_type}|{entity_id}|{payload_hash}"
    return "art_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _is_world_cup_event(event: Dict[str, Any]) -> bool:
    text = " ".join(
        str(event.get(key) or "")
        for key in ("category_name", "tournament_name", "tournament_slug", "season_slug")
    ).lower()
    return (
        "world championship" in text
        or "world cup" in text
        or ("world" in text and "2026" in text)
    )


def _is_actionable_schedule_event(event: Dict[str, Any]) -> bool:
    status = str(event.get("event_status") or "").upper()
    if status in FINISHED_STATUSES or status in ACTIVE_STATUSES:
        return True
    started_at = _parse_timestamp(event.get("event_start_at"))
    return bool(started_at and started_at <= datetime.utcnow() - timedelta(hours=2))


class OddsfeEventDetailSync:
    """Fetch, cache, and apply oddsfe event detail."""

    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        self.foundation = FoundationDAO(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _latest_artifact(self, conn: sqlite3.Connection, event_id: str) -> Optional[Dict[str, Any]]:
        row = conn.execute(
            """
            SELECT payload_json, captured_at
            FROM source_artifacts
            WHERE source_name = 'oddsfe'
              AND entity_type = 'event'
              AND entity_id = ?
            ORDER BY captured_at DESC
            LIMIT 1
            """,
            (event_id,),
        ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            return None
        if isinstance(payload, dict):
            payload["_captured_at"] = row["captured_at"]
            payload["_score_source"] = "oddsfe_event_cache"
            return payload
        return None

    def _should_fetch_event(self, cached: Optional[Dict[str, Any]], refresh: bool, cache_minutes: int) -> bool:
        if refresh or not cached:
            return True
        status = str(cached.get("event_status") or "").upper()
        if status in FINISHED_STATUSES and (cached.get("score_details") or cached.get("event_score_home") is not None):
            return False
        captured_at = _parse_timestamp(cached.get("_captured_at"))
        if captured_at and captured_at >= datetime.now() - timedelta(minutes=cache_minutes):
            return False
        return True

    def _has_usable_finished_cache(self, cached: Optional[Dict[str, Any]]) -> bool:
        if not cached:
            return False
        status = str(cached.get("event_status") or "").upper()
        return status in FINISHED_STATUSES and bool(
            cached.get("score_details")
            or cached.get("score_home") is not None
            or cached.get("event_score_home") is not None
        )

    def _lottery_rows_need_result(self, rows: List[Dict[str, Any]]) -> bool:
        required = (
            "home_goals_ft",
            "away_goals_ft",
            "home_goals_ht",
            "away_goals_ht",
            "bf_result",
            "bqc_result",
        )
        for row in rows or []:
            if any(row.get(key) is None or row.get(key) == "" for key in required):
                return True
        return False

    def _odds_from_schedule_event(self, event: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
        if not event:
            return None
        try:
            odds = {
                "3": float(event.get("main_out_0") or 0),
                "1": float(event.get("main_out_1") or 0),
                "0": float(event.get("main_out_2") or 0),
            }
        except (TypeError, ValueError):
            return None
        if any(value <= 1.0 or value > 80.0 for value in odds.values()):
            return None
        return odds

    def _beijing_time_from_event(self, event: Optional[Dict[str, Any]]) -> Optional[datetime]:
        started = _parse_timestamp((event or {}).get("event_start_at"))
        if not started:
            return None
        from backend.app.core.time_utils import utc_to_beijing
        return utc_to_beijing(started).replace(tzinfo=None)

    def _score_matches_existing_result(
        self,
        lottery_row: Dict[str, Any],
        schedule_event: Dict[str, Any],
    ) -> bool:
        home_ft = lottery_row.get("home_goals_ft")
        away_ft = lottery_row.get("away_goals_ft")
        if home_ft is None or away_ft is None:
            return True
        try:
            event_home = int(schedule_event.get("event_score_home"))
            event_away = int(schedule_event.get("event_score_away"))
            return int(home_ft) == event_home and int(away_ft) == event_away
        except (TypeError, ValueError):
            return False

    def _upsert_schedule_spf_odds(
        self,
        conn: sqlite3.Connection,
        lottery_row: Dict[str, Any],
        schedule_event: Optional[Dict[str, Any]],
        apply: bool,
    ) -> str:
        odds = self._odds_from_schedule_event(schedule_event)
        if not odds:
            return "missing"
        exists = conn.execute(
            """
            SELECT 1
            FROM lottery_odds
            WHERE lottery_match_id = ?
              AND play_type = 'spf'
            LIMIT 1
            """,
            (lottery_row.get("lottery_match_id"),),
        ).fetchone()
        if exists:
            return "exists"
        if not apply:
            return "would_insert"

        odds_json = json.dumps(odds, ensure_ascii=False, sort_keys=True)
        conn.execute(
            """
            INSERT OR IGNORE INTO lottery_odds
            (lottery_match_id, match_id, play_type, odds_data,
             opening_odds, snapshot_type, update_time)
            VALUES (?, ?, 'spf', ?, ?, 'opening', CURRENT_TIMESTAMP)
            """,
            (
                lottery_row.get("lottery_match_id"),
                lottery_row.get("match_id"),
                odds_json,
                odds_json,
            ),
        )
        return "inserted"

    def _update_lottery_match_bridge(
        self,
        conn: sqlite3.Connection,
        lottery_row: Dict[str, Any],
        schedule_event: Dict[str, Any],
        apply: bool,
    ) -> str:
        event_id = _event_id(schedule_event.get("event_id"))
        if not event_id:
            return "missing"
        current = _event_id(lottery_row.get("oddsfe_event_id"))
        if current:
            return "exists"
        if not apply:
            return "would_update"

        bj_dt = self._beijing_time_from_event(schedule_event)
        updates = ["oddsfe_event_id = ?", "updated_at = CURRENT_TIMESTAMP"]
        params: List[Any] = [event_id]
        if bj_dt:
            updates.extend(["beijing_time = ?", "match_date = ?", "match_time = ?"])
            params.extend([
                bj_dt.strftime("%Y-%m-%d %H:%M:%S"),
                bj_dt.strftime("%Y-%m-%d"),
                bj_dt.strftime("%H:%M:%S"),
            ])
            lottery_row["beijing_time"] = bj_dt.strftime("%Y-%m-%d %H:%M:%S")
            lottery_row["match_date"] = bj_dt.strftime("%Y-%m-%d")
            lottery_row["match_time"] = bj_dt.strftime("%H:%M:%S")
        params.append(lottery_row.get("lottery_match_id"))
        conn.execute(
            f"UPDATE lottery_matches SET {', '.join(updates)} WHERE lottery_match_id = ?",
            params,
        )
        lottery_row["oddsfe_event_id"] = event_id
        return "updated"

    def _load_lottery_candidates(self, conn: sqlite3.Connection, date_from: str, date_to: str) -> Dict[str, Dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT lm.lottery_match_id, lm.match_id, lm.match_num,
                   lm.home_team_cn, lm.away_team_cn, lm.match_date, lm.match_time,
                   lm.beijing_time, lm.oddsfe_event_id, lm.handicap_line,
                   lr.home_goals_ft, lr.away_goals_ft, lr.home_goals_ht, lr.away_goals_ht,
                   lr.spf_result, lr.bf_result, lr.bqc_result, lr.rqspf_result, lr.ou_result
            FROM lottery_matches lm
            LEFT JOIN lottery_results lr ON lm.lottery_match_id = lr.lottery_match_id
            WHERE (
                substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?
                OR lm.match_date BETWEEN ? AND ?
            )
              AND lm.oddsfe_event_id IS NOT NULL
              AND lm.oddsfe_event_id <> ''
            ORDER BY COALESCE(lm.beijing_time, lm.match_date || ' ' || COALESCE(lm.match_time, '99:99'))
            """,
            (date_from, date_to, date_from, date_to),
        ).fetchall()
        candidates: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            event_id = _event_id(row["oddsfe_event_id"])
            if not event_id:
                continue
            item = candidates.setdefault(event_id, {"event_id": event_id, "lottery_matches": [], "schedule_event": None})
            item["lottery_matches"].append(dict(row))
        return candidates

    def _load_unbridged_lottery_rows(self, conn: sqlite3.Connection, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT lm.lottery_match_id, lm.match_id, lm.match_num,
                   lm.home_team_cn, lm.away_team_cn, lm.match_date, lm.match_time,
                   lm.beijing_time, lm.oddsfe_event_id, lm.handicap_line,
                   ht.name_en AS home_team_en, at.name_en AS away_team_en,
                   lr.home_goals_ft, lr.away_goals_ft, lr.home_goals_ht, lr.away_goals_ht,
                   lr.spf_result, lr.bf_result, lr.bqc_result, lr.rqspf_result, lr.ou_result
            FROM lottery_matches lm
            LEFT JOIN teams ht ON ht.team_id = lm.home_team_id
            LEFT JOIN teams at ON at.team_id = lm.away_team_id
            LEFT JOIN lottery_results lr ON lm.lottery_match_id = lr.lottery_match_id
            WHERE (
                substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?
                OR lm.match_date BETWEEN ? AND ?
            )
              AND (lm.oddsfe_event_id IS NULL OR lm.oddsfe_event_id = '')
              AND ht.name_en IS NOT NULL
              AND at.name_en IS NOT NULL
            ORDER BY COALESCE(lm.beijing_time, lm.match_date || ' ' || COALESCE(lm.match_time, '99:99'))
            """,
            (date_from, date_to, date_from, date_to),
        ).fetchall()
        return [dict(row) for row in rows]

    def _match_unbridged_lottery_row(
        self,
        schedule_event: Dict[str, Any],
        unbridged_rows: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        event_home = _norm_name(schedule_event.get("team_home_name"))
        event_away = _norm_name(schedule_event.get("team_away_name"))
        if not event_home or not event_away:
            return None
        matches = [
            row for row in unbridged_rows
            if _norm_name(row.get("home_team_en")) == event_home
            and _norm_name(row.get("away_team_en")) == event_away
            and self._score_matches_existing_result(row, schedule_event)
        ]
        if len(matches) != 1:
            return None
        return matches[0]

    def _load_schedule_artifact_events(self, conn: sqlite3.Connection, date_str: str) -> List[Dict[str, Any]]:
        row = conn.execute(
            """
            SELECT payload_json
            FROM source_artifacts
            WHERE source_name = 'oddsfe'
              AND entity_type = 'schedule'
              AND entity_id = ?
            ORDER BY captured_at DESC
            LIMIT 1
            """,
            (date_str,),
        ).fetchone()
        if not row:
            return []
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            return []
        if isinstance(payload, dict):
            payload = payload.get("data") or payload.get("events") or []
        return [dict(event) for event in payload if isinstance(event, dict)] if isinstance(payload, list) else []

    def _record_artifact(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: Optional[str],
        source_name: str,
        source_type: str,
        entity_type: str,
        entity_id: str,
        payload: Any,
        confidence: float,
    ) -> int:
        payload_json = _payload_json(payload)
        payload_hash = _payload_hash(payload_json)
        artifact_id = _artifact_id(source_name, entity_type, entity_id, payload_hash)
        cur = conn.execute(
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
                entity_id,
                payload_json,
                payload_hash,
                confidence,
            ),
        )
        return cur.rowcount

    def _load_schedule_events(
        self,
        conn: sqlite3.Connection,
        date_str: str,
        run_id: Optional[str],
        fetch_schedule: bool,
    ) -> Tuple[List[Dict[str, Any]], str]:
        if fetch_schedule:
            events = _oddsfe_fetch_schedule(date_str)
            if events:
                self.foundation.record_artifact(
                    run_id=run_id,
                    source_name="oddsfe",
                    source_type="api",
                    entity_type="schedule",
                    entity_id=date_str,
                    payload=events,
                    confidence=0.85,
                )
                return [dict(event) for event in events if isinstance(event, dict)], "api"
        return self._load_schedule_artifact_events(conn, date_str), "cache"

    def _merge_schedule_candidates(
        self,
        conn: sqlite3.Connection,
        candidates: Dict[str, Dict[str, Any]],
        date_from: str,
        date_to: str,
        run_id: Optional[str],
        fetch_schedule: bool,
        include_schedule_only: bool,
        schedule_padding_days: int,
        unbridged_rows: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, int]:
        stats = {
            "schedule_events": 0,
            "schedule_api_days": 0,
            "schedule_cache_days": 0,
            "world_cup_schedule_candidates": 0,
            "schedule_lottery_bridges_planned": 0,
        }
        schedule_start = (datetime.strptime(date_from, "%Y-%m-%d").date() - timedelta(days=schedule_padding_days)).isoformat()
        schedule_end = (datetime.strptime(date_to, "%Y-%m-%d").date() + timedelta(days=schedule_padding_days)).isoformat()
        stats["schedule_date_from"] = schedule_start
        stats["schedule_date_to"] = schedule_end
        for date_str in _date_range(schedule_start, schedule_end):
            events, source = self._load_schedule_events(conn, date_str, run_id, fetch_schedule)
            stats["schedule_events"] += len(events)
            stats["schedule_api_days" if source == "api" else "schedule_cache_days"] += 1
            for event in events:
                event_id = _event_id(event.get("event_id"))
                if not event_id:
                    continue
                if event_id in candidates:
                    candidates[event_id]["schedule_event"] = event
                    continue
                lottery_row = self._match_unbridged_lottery_row(event, unbridged_rows or [])
                if lottery_row:
                    candidates[event_id] = {
                        "event_id": event_id,
                        "lottery_matches": [lottery_row],
                        "schedule_event": event,
                        "_bridged_from_schedule": True,
                    }
                    stats["schedule_lottery_bridges_planned"] += 1
                    continue
                if not include_schedule_only:
                    continue
                if _is_world_cup_event(event) and _is_actionable_schedule_event(event):
                    candidates[event_id] = {
                        "event_id": event_id,
                        "lottery_matches": [],
                        "schedule_event": event,
                    }
                    stats["world_cup_schedule_candidates"] += 1
        return stats

    def _result_from_event(self, lottery_row: Dict[str, Any], event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        status = str(event_data.get("event_status") or "").upper()
        if status and status not in FINISHED_STATUSES:
            return None

        parsed = _parse_score_details(event_data.get("score_details") or "")
        ft_home, ft_away, home_90, away_90, end_type = _event_fulltime_score(event_data, parsed)
        if ft_home is None or ft_away is None:
            return None

        spf_home = home_90 if home_90 is not None else ft_home
        spf_away = away_90 if away_90 is not None else ft_away

        ht_home, ht_away = (None, None)
        if parsed and parsed.get("ht"):
            ht_home, ht_away = parsed["ht"]

        handicap = _effective_handicap(
            self.db_path,
            lottery_row.get("lottery_match_id"),
            lottery_row.get("handicap_line") or 0,
        )
        derived = _derive_play_types(spf_home, spf_away, ht_home, ht_away, handicap)
        bqc_result = _resolve_bqc_result(
            spf_home,
            spf_away,
            ht_home,
            ht_away,
            source_name="oddsfe_event",
            lottery_match_id=lottery_row.get("lottery_match_id"),
        )

        try:
            from backend.app.lottery.services.ou_calculator import compute_ou_result

            ou_line = self._ou_line_for_result(lottery_row)
            ou_result = compute_ou_result(spf_home + spf_away, ou_line or 2.5)
        except Exception:
            ou_result = None

        # 体彩语境: home_goals_ft = 90分钟比分(不含加时), 加时比分单独存home_goals_90min之后
        # 但lottery_results表 home_goals_ft 历史上就是90min含义, 保持一致
        goals_home = home_90 if home_90 is not None else ft_home
        goals_away = away_90 if away_90 is not None else ft_away

        return {
            "lottery_match_id": lottery_row.get("lottery_match_id"),
            "match_id": lottery_row.get("match_id"),
            "home_goals_ft": goals_home,
            "away_goals_ft": goals_away,
            "home_goals_90min": home_90,
            "away_goals_90min": away_90,
            "match_end_type": end_type,
            "home_goals_ht": ht_home,
            "away_goals_ht": ht_away,
            "spf_result": derived.get("spf_result"),
            "bf_result": derived.get("bf_result"),
            "bqc_result": bqc_result,
            "rqspf_result": derived.get("rqspf_result"),
            "ou_result": ou_result,
        }

    def _ou_line_for_result(self, lottery_row: Dict[str, Any]) -> Optional[float]:
        """Use the same O/U line as prediction when settling a result."""
        lottery_match_id = lottery_row.get("lottery_match_id")
        event_id = _event_id(lottery_row.get("oddsfe_event_id"))
        try:
            from backend.app.lottery.services.ou_calculator import parse_ou_line

            with self._connect() as conn:
                if lottery_match_id:
                    row = conn.execute(
                        """
                        SELECT report_data
                        FROM lottery_analysis_reports
                        WHERE lottery_match_id = ?
                          AND report_type IN ('prediction', 'full')
                        ORDER BY created_at DESC, rowid DESC
                        LIMIT 1
                        """,
                        (lottery_match_id,),
                    ).fetchone()
                    if row:
                        try:
                            report = json.loads(row["report_data"])
                            pp = report.get("play_predictions", {}) or {}
                            analyses = report.get("analyses", {}) or {}
                            ou = pp.get("ou") or pp.get("over_under") or analyses.get("ou") or {}
                            line = (
                                parse_ou_line(ou.get("recommendation"))
                                or parse_ou_line(ou.get("best_line"))
                                or parse_ou_line(ou.get("line"))
                            )
                            if line:
                                return line
                        except (TypeError, json.JSONDecodeError):
                            pass
                if event_id:
                    row = conn.execute(
                        """
                        SELECT ou_pinnacle_line
                        FROM oddsfe_matches
                        WHERE CAST(event_id AS TEXT) = ?
                          AND ou_pinnacle_line IS NOT NULL
                          AND ou_pinnacle_line != ''
                        LIMIT 1
                        """,
                        (event_id,),
                    ).fetchone()
                    if row:
                        line = parse_ou_line(row["ou_pinnacle_line"])
                        if line:
                            return line
        except Exception as exc:
            logger.debug("O/U result line lookup failed for %s: %s", lottery_match_id, exc)
        return 2.5

    def _upsert_result(
        self,
        conn: sqlite3.Connection,
        result: Dict[str, Any],
        overwrite: bool,
    ) -> Tuple[str, List[str]]:
        table_cols = {row[1] for row in conn.execute("PRAGMA table_info(lottery_results)").fetchall()}
        row = conn.execute(
            "SELECT rowid AS _rowid, * FROM lottery_results WHERE lottery_match_id = ?",
            (result["lottery_match_id"],),
        ).fetchone()
        columns = {
            "match_id",
            "home_goals_ft",
            "away_goals_ft",
            "home_goals_ht",
            "away_goals_ht",
            "home_goals_90min",
            "away_goals_90min",
            "match_end_type",
            "penalty_home",
            "penalty_away",
            "spf_result",
            "bf_result",
            "bqc_result",
            "rqspf_result",
            "ou_result",
        } & table_cols
        values = {key: value for key, value in result.items() if key in columns and value is not None}
        if not row:
            insert_cols = ["lottery_match_id"] + list(values.keys())
            placeholders = ["?"] * len(insert_cols)
            if "draw_time" in table_cols:
                insert_cols.append("draw_time")
                placeholders.append("CURRENT_TIMESTAMP")
            if "created_at" in table_cols:
                insert_cols.append("created_at")
                placeholders.append("CURRENT_TIMESTAMP")
            conn.execute(
                f"INSERT INTO lottery_results ({', '.join(insert_cols)}) VALUES ({', '.join(placeholders)})",
                [result["lottery_match_id"]] + list(values.values()),
            )
            return "inserted", list(values.keys())

        updates: List[str] = []
        params: List[Any] = []
        changed_cols: List[str] = []
        for key, value in values.items():
            current = row[key] if key in row.keys() else None
            if key == "bqc_result" and _normalize_bqc_result(current) != value:
                updates.append(f"{key} = ?")
                params.append(value)
                changed_cols.append(key)
                continue
            if key == "bqc_result" and current != value:
                updates.append(f"{key} = ?")
                params.append(value)
                changed_cols.append(key)
                continue
            if overwrite or current is None or current == "":
                if current != value:
                    updates.append(f"{key} = ?")
                    params.append(value)
                    changed_cols.append(key)
        if not updates:
            return "unchanged", []
        params.append(row["_rowid"])
        conn.execute(f"UPDATE lottery_results SET {', '.join(updates)} WHERE rowid = ?", params)
        return "updated", changed_cols

    def _queue_revalidation(self, conn: sqlite3.Connection, lottery_match_id: str, reason: str) -> bool:
        """Queue post-result validation without creating duplicate pending work."""
        if not lottery_match_id:
            return False
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lottery_revalidation_queue (
                queue_id TEXT PRIMARY KEY,
                correction_id TEXT NOT NULL,
                lottery_match_id TEXT NOT NULL,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_lottery_revalidation_status
                ON lottery_revalidation_queue(status, created_at)
            """
        )
        existing = conn.execute(
            """
            SELECT 1
            FROM lottery_revalidation_queue
            WHERE lottery_match_id = ?
              AND reason = ?
              AND status = 'pending'
            LIMIT 1
            """,
            (lottery_match_id, reason),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """
            INSERT INTO lottery_revalidation_queue
            (queue_id, correction_id, lottery_match_id, reason)
            VALUES (?, ?, ?, ?)
            """,
            (
                "revalidate:" + uuid.uuid4().hex,
                "event_sync:" + uuid.uuid4().hex,
                lottery_match_id,
                reason,
            ),
        )
        return True

    def run(
        self,
        date_from: str,
        date_to: str,
        *,
        apply: bool = False,
        refresh: bool = False,
        fetch_schedule: bool = True,
        overwrite: bool = False,
        include_schedule_only: bool = True,
        max_events: Optional[int] = None,
        schedule_padding_days: int = 1,
        cache_minutes: int = 30,
        sleep_seconds: float = 0.15,
        trigger_source: str = "manual",
    ) -> Dict[str, Any]:
        run_id = None
        if apply:
            run_id = self.foundation.start_run(
                run_type="oddsfe_event_details",
                match_date=date_from,
                trigger_source=trigger_source,
                summary={"date_from": date_from, "date_to": date_to, "stage": "start"},
            )

        summary: Dict[str, Any] = {
            "success": True,
            "dry_run": not apply,
            "date_from": date_from,
            "date_to": date_to,
            "candidates": 0,
            "event_api_fetched": 0,
            "event_cache_used": 0,
            "event_artifacts_recorded": 0,
            "lottery_rows_seen": 0,
            "lottery_results_inserted": 0,
            "lottery_results_updated": 0,
            "lottery_results_unchanged": 0,
            "schedule_spf_odds_inserted": 0,
            "schedule_spf_odds_existing": 0,
            "schedule_spf_odds_missing": 0,
            "schedule_spf_odds_planned": 0,
            "schedule_lottery_bridges_updated": 0,
            "schedule_lottery_bridges_existing": 0,
            "schedule_lottery_bridges_missing": 0,
            "revalidation_queued": 0,
            "skipped_not_finished": 0,
            "skipped_no_score": 0,
            "schedule_events": 0,
            "world_cup_schedule_candidates": 0,
            "include_schedule_only": include_schedule_only,
            "max_events": max_events,
            "schedule_padding_days": schedule_padding_days,
            "candidates_deferred": 0,
            "remaining_uncached_events": 0,
            "errors": [],
        }

        try:
            with self._connect() as conn:
                candidates = self._load_lottery_candidates(conn, date_from, date_to)
                unbridged_rows = self._load_unbridged_lottery_rows(conn, date_from, date_to)
                schedule_stats = self._merge_schedule_candidates(
                    conn,
                    candidates,
                    date_from,
                    date_to,
                    run_id,
                    fetch_schedule,
                    include_schedule_only,
                    schedule_padding_days,
                    unbridged_rows,
                )
                summary.update(schedule_stats)
                summary["candidates"] = len(candidates)

                for item in candidates.values():
                    cached = self._latest_artifact(conn, str(item.get("event_id") or ""))
                    item["_prefetched_event_cache"] = cached
                    has_lottery = bool(item.get("lottery_matches"))
                    needs_lottery_result = self._lottery_rows_need_result(item.get("lottery_matches") or [])
                    has_finished_cache = self._has_usable_finished_cache(cached)
                    if has_lottery and needs_lottery_result:
                        priority = 0
                    elif not has_finished_cache:
                        priority = 1
                    elif has_lottery:
                        priority = 2
                    else:
                        priority = 3
                    item["_batch_priority"] = priority

                ordered_candidates = sorted(
                    candidates.values(),
                    key=lambda item: (
                        item.get("_batch_priority", 9),
                        str(item.get("event_id") or ""),
                    ),
                )
                if max_events is not None and max_events > 0 and len(ordered_candidates) > max_events:
                    summary["candidates_deferred"] = len(ordered_candidates) - max_events
                    ordered_candidates = ordered_candidates[:max_events]

                for candidate in ordered_candidates:
                    event_id = candidate["event_id"]
                    summary["lottery_rows_seen"] += len(candidate.get("lottery_matches") or [])
                    if candidate.get("_bridged_from_schedule"):
                        for lottery_row in candidate.get("lottery_matches") or []:
                            bridge_action = self._update_lottery_match_bridge(
                                conn,
                                lottery_row,
                                candidate.get("schedule_event") or {},
                                apply=apply,
                            )
                            if bridge_action == "updated":
                                summary["schedule_lottery_bridges_updated"] += 1
                            elif bridge_action == "exists":
                                summary["schedule_lottery_bridges_existing"] += 1
                            else:
                                summary["schedule_lottery_bridges_missing"] += 1

                    for lottery_row in candidate.get("lottery_matches") or []:
                        odds_action = self._upsert_schedule_spf_odds(
                            conn,
                            lottery_row,
                            candidate.get("schedule_event"),
                            apply=apply,
                        )
                        if odds_action == "inserted":
                            summary["schedule_spf_odds_inserted"] += 1
                        elif odds_action == "exists":
                            summary["schedule_spf_odds_existing"] += 1
                        elif odds_action == "would_insert":
                            summary["schedule_spf_odds_planned"] += 1
                        else:
                            summary["schedule_spf_odds_missing"] += 1

                    cached = candidate.get("_prefetched_event_cache") or self._latest_artifact(conn, event_id)
                    if self._should_fetch_event(cached, refresh, cache_minutes):
                        event_data = _oddsfe_fetch_score_details(event_id)
                        if sleep_seconds:
                            time.sleep(sleep_seconds)
                        if not event_data:
                            summary["errors"].append(f"{event_id}: empty event response")
                            continue
                        event_data = dict(event_data)
                        event_data.setdefault("event_id", event_id)
                        event_data["_score_source"] = "oddsfe_event_api"
                        summary["event_api_fetched"] += 1
                        if apply:
                            artifact_payload = {
                                key: value for key, value in event_data.items() if not str(key).startswith("_")
                            }
                            inserted = self._record_artifact(
                                conn,
                                run_id=run_id,
                                source_name="oddsfe",
                                source_type="api",
                                entity_type="event",
                                entity_id=event_id,
                                payload=artifact_payload,
                                confidence=0.9,
                            )
                            summary["event_artifacts_recorded"] += inserted
                    else:
                        event_data = cached or {}
                        summary["event_cache_used"] += 1

                    status = str(event_data.get("event_status") or "").upper()
                    if status and status not in FINISHED_STATUSES:
                        summary["skipped_not_finished"] += 1
                        continue

                    for lottery_row in candidate.get("lottery_matches") or []:
                        result = self._result_from_event(lottery_row, event_data)
                        if not result:
                            summary["skipped_no_score"] += 1
                            continue
                        if not apply:
                            summary["lottery_results_updated"] += 1
                            continue
                        action, changed_cols = self._upsert_result(conn, result, overwrite=overwrite)
                        if action == "inserted":
                            summary["lottery_results_inserted"] += 1
                        elif action == "updated":
                            summary["lottery_results_updated"] += 1
                        else:
                            summary["lottery_results_unchanged"] += 1

                        if action in {"inserted", "updated"}:
                            conn.execute(
                                """
                                UPDATE lottery_matches
                                SET sell_status = 'finished'
                                WHERE lottery_match_id = ?
                                  AND sell_status IN ('selling', 'closed', 'scheduled')
                                """,
                                (result["lottery_match_id"],),
                            )
                            if self._queue_revalidation(
                                conn,
                                result["lottery_match_id"],
                                f"oddsfe_event_result_{action}",
                            ):
                                summary["revalidation_queued"] += 1

                    if apply:
                        conn.commit()

                summary["remaining_uncached_events"] = sum(
                    1
                    for item in candidates.values()
                    if not self._has_usable_finished_cache(
                        self._latest_artifact(conn, str(item.get("event_id") or ""))
                    )
                )

            summary["errors"] = summary["errors"][:20]
            if apply:
                self.foundation.finish_run(run_id, status="success", summary=summary)
            return summary
        except Exception as exc:
            summary["success"] = False
            summary["errors"].append(str(exc))
            if apply:
                self.foundation.finish_run(run_id, status="failed", summary=summary, error=str(exc))
            raise


def default_date_range(days: int = 3) -> Tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=max(days - 1, 0))
    return start.isoformat(), end.isoformat()


def default_db_path() -> str:
    return str(Path(__file__).resolve().parents[4] / "data" / "football_v2.db")
