"""football-data.org World Cup sync for durable result evidence.

The source is used as an auxiliary truth source for WC schedule/status/score
and team identity mapping. It does not replace Sporttery odds or oddsfe odds.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import logging
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from backend.app.data_access.foundation_dao import FoundationDAO
from backend.app.lottery.services.oddsfe_event_sync import OddsfeEventDetailSync
from backend.app.lottery.services.ou_calculator import compute_ou_result
from backend.app.lottery.services.sync_service import _derive_play_types, _effective_handicap

logger = logging.getLogger(__name__)

SOURCE_NAME = "football_data_org"
WORLD_CUP_CN = "\u4e16\u754c\u676f"
BEIJING_TZ = timezone(timedelta(hours=8))
FINISHED_STATUSES = {"finished", "fin", "ft"}

NAME_ALIASES = {
    "unitedstates": "usa",
    "unitedstatesofamerica": "usa",
    "usmnt": "usa",
    "usa": "usa",
    "czech": "czechia",
    "czechrepublic": "czechia",
    "korea": "korearepublic",
    "southkorea": "korearepublic",
    "republicofkorea": "korearepublic",
    "bosniah": "bosniaherzegovina",
    "bosnia": "bosniaherzegovina",
    "bosniaandherzegovina": "bosniaherzegovina",
    "cotedivoire": "ivorycoast",
    "ivorycoast": "ivorycoast",
    "curacao": "curacao",
    "iriran": "iran",
    "iran": "iran",
    "congodr": "drcongo",
    "drcongo": "drcongo",
    "drc": "drcongo",
    "democraticrepublicofthecongo": "drcongo",
}


def default_db_path() -> str:
    return str(Path(__file__).resolve().parents[4] / "data" / "football_v2.db")


def default_date_range(days: int = 3) -> Tuple[str, str]:
    today = datetime.now().date()
    start = today - timedelta(days=max(int(days) - 1, 0))
    return start.isoformat(), today.isoformat()


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True, default=str)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _compact_id(prefix: str, *parts: Any) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    return f"{prefix}_{_hash(raw)[:32]}"


def _norm_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return NAME_ALIASES.get(text, text)


def _safe_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_local_dt(row: Dict[str, Any]) -> Optional[datetime]:
    text = str(row.get("beijing_time") or "").strip()
    if not text:
        date_text = str(row.get("match_date") or "").strip()
        time_text = str(row.get("match_time") or "").strip()[:5]
        text = f"{date_text} {time_text}" if date_text and time_text else ""
    for width, fmt in ((19, "%Y-%m-%d %H:%M:%S"), (16, "%Y-%m-%d %H:%M")):
        try:
            return datetime.strptime(text[:width], fmt)
        except (TypeError, ValueError):
            continue
    return None


def _beijing_dt_from_fd(match: Dict[str, Any]) -> Optional[datetime]:
    date_text = str(match.get("date") or "").strip()
    time_text = str(match.get("time") or "").strip()[:5]
    if not date_text or not time_text:
        return None
    try:
        utc_dt = datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return utc_dt.astimezone(BEIJING_TZ).replace(tzinfo=None)


def _status_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _clean_result_value(field: str, value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan", "-", "--"}:
        return None
    if field == "bf_result":
        return text.replace("-", ":")
    return text


class FootballDataWorldCupSync:
    """Fetch football-data.org WC matches and apply matched evidence locally."""

    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        self.foundation = FoundationDAO(self.db_path)
        self.result_writer = OddsfeEventDetailSync(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _fetch_wc_matches(self, season: int) -> List[Dict[str, Any]]:
        from fetchers.football_data_org.get_matches import get_league_matches

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rows = get_league_matches("WC", str(season))
        matches: List[Dict[str, Any]] = []
        for row in rows or []:
            item = dict(row)
            bj_dt = _beijing_dt_from_fd(item)
            item["beijing_time"] = bj_dt.strftime("%Y-%m-%d %H:%M:00") if bj_dt else None
            item["beijing_date"] = bj_dt.strftime("%Y-%m-%d") if bj_dt else None
            item["beijing_time_only"] = bj_dt.strftime("%H:%M:%S") if bj_dt else None
            item["home_norm"] = _norm_name(item.get("home_team"))
            item["away_norm"] = _norm_name(item.get("away_team"))
            matches.append(item)
        return matches

    def _load_lottery_rows(self, conn: sqlite3.Connection, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT lm.lottery_match_id, lm.match_id, lm.match_num,
                   lm.match_date, lm.match_time, lm.beijing_time,
                   lm.league_name_cn, lm.home_team_cn, lm.away_team_cn,
                   lm.home_team_id, lm.away_team_id, lm.handicap_line,
                   lm.sell_status, lm.oddsfe_event_id,
                   ht.name_en AS home_team_en, ht.name_cn AS home_team_cn_canonical,
                   ht.fd_team_id AS home_fd_team_id,
                   at.name_en AS away_team_en, at.name_cn AS away_team_cn_canonical,
                   at.fd_team_id AS away_fd_team_id,
                   lr.home_goals_ft, lr.away_goals_ft,
                   lr.home_goals_ht, lr.away_goals_ht,
                   lr.spf_result, lr.bf_result, lr.bqc_result, lr.rqspf_result, lr.ou_result
            FROM lottery_matches lm
            LEFT JOIN teams ht ON ht.team_id = lm.home_team_id
            LEFT JOIN teams at ON at.team_id = lm.away_team_id
            LEFT JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
            WHERE substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?
              AND COALESCE(lm.league_name_cn, '') = ?
            ORDER BY COALESCE(lm.beijing_time, lm.match_date || ' ' || COALESCE(lm.match_time, '99:99')),
                     lm.lottery_match_id
            """,
            (date_from, date_to, WORLD_CUP_CN),
        ).fetchall()
        return [dict(row) for row in rows]

    def _local_team_norms(self, row: Dict[str, Any], side: str) -> set[str]:
        values = {
            row.get(f"{side}_team_en"),
            row.get(f"{side}_team_cn"),
            row.get(f"{side}_team_cn_canonical"),
        }
        return {item for item in (_norm_name(value) for value in values) if item}

    def _same_pair(self, row: Dict[str, Any], match: Dict[str, Any]) -> bool:
        return (
            match.get("home_norm") in self._local_team_norms(row, "home")
            and match.get("away_norm") in self._local_team_norms(row, "away")
        )

    def _match_lottery_row(
        self,
        row: Dict[str, Any],
        matches: Iterable[Dict[str, Any]],
        *,
        time_tolerance_minutes: int,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        local_dt = _parse_local_dt(row)
        name_matches = [match for match in matches if self._same_pair(row, match)]
        if not name_matches:
            return None, "no_name_match"
        if local_dt:
            exact = []
            for match in name_matches:
                fd_dt = _beijing_dt_from_fd(match)
                if not fd_dt:
                    continue
                delta = abs((fd_dt - local_dt).total_seconds()) / 60
                if delta <= time_tolerance_minutes:
                    exact.append(match)
            if len(exact) == 1:
                return exact[0], "name_time"
            if len(exact) > 1:
                return None, "ambiguous_name_time"
        same_date = []
        local_date = local_dt.strftime("%Y-%m-%d") if local_dt else str(row.get("match_date") or "")[:10]
        for match in name_matches:
            if str(match.get("beijing_date") or "") == local_date:
                same_date.append(match)
        if len(same_date) == 1:
            return same_date[0], "name_date"
        if len(name_matches) == 1:
            return name_matches[0], "name_only"
        return None, "ambiguous_name"

    def _record_artifact(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: Optional[str],
        source_type: str,
        entity_type: str,
        entity_id: str,
        payload: Any,
        confidence: float,
    ) -> int:
        payload_json = _json(payload)
        payload_hash = _hash(payload_json)
        artifact_id = _compact_id("art", SOURCE_NAME, entity_type, entity_id, payload_hash)
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
                SOURCE_NAME,
                source_type,
                entity_type,
                str(entity_id),
                payload_json,
                payload_hash,
                confidence,
            ),
        )
        return cur.rowcount

    def _upsert_mapping(
        self,
        conn: sqlite3.Connection,
        *,
        entity_type: str,
        canonical_id: Any,
        source_entity_id: Any,
        source_entity_name: Optional[str],
        confidence: float,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        if canonical_id in (None, "") or source_entity_id in (None, ""):
            return "missing", None
        existing = conn.execute(
            """
            SELECT canonical_id, source_entity_name
            FROM source_entity_mappings
            WHERE entity_type = ?
              AND source_name = ?
              AND source_entity_id = ?
              AND COALESCE(status, 'active') = 'active'
            LIMIT 1
            """,
            (entity_type, SOURCE_NAME, str(source_entity_id)),
        ).fetchone()
        if existing and str(existing["canonical_id"]) != str(canonical_id):
            return "conflict", {
                "entity_type": entity_type,
                "source_entity_id": str(source_entity_id),
                "existing_canonical_id": existing["canonical_id"],
                "new_canonical_id": str(canonical_id),
                "source_entity_name": source_entity_name,
            }
        mapping_id = _compact_id("map", entity_type, SOURCE_NAME, source_entity_id)
        conn.execute(
            """
            INSERT OR REPLACE INTO source_entity_mappings
            (mapping_id, entity_type, canonical_id, source_name, source_entity_id,
             source_entity_name, confidence, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
            """,
            (
                mapping_id,
                entity_type,
                str(canonical_id),
                SOURCE_NAME,
                str(source_entity_id),
                source_entity_name,
                confidence,
            ),
        )
        return "upserted", None

    def _upsert_team_identity(
        self,
        conn: sqlite3.Connection,
        *,
        team_id: Any,
        fd_team_id: Any,
        fd_name: Optional[str],
        side: str,
        summary: Dict[str, Any],
    ) -> None:
        if team_id in (None, "") or fd_team_id in (None, ""):
            summary["team_mapping_missing"] += 1
            return
        status, conflict = self._upsert_mapping(
            conn,
            entity_type="team",
            canonical_id=team_id,
            source_entity_id=fd_team_id,
            source_entity_name=fd_name,
            confidence=0.96,
        )
        if status == "conflict":
            conflict["side"] = side
            summary["mapping_conflicts"].append(conflict)
            if self._update_team_fd_column_if_compatible(conn, team_id=team_id, fd_team_id=fd_team_id, fd_name=fd_name):
                summary["team_fd_columns_updated"] += 1
                summary["team_fd_columns_updated_despite_mapping_conflict"] += 1
            return
        summary["team_mappings_upserted"] += 1

        if self._update_team_fd_column_if_compatible(conn, team_id=team_id, fd_team_id=fd_team_id, fd_name=fd_name):
            summary["team_fd_columns_updated"] += 1

    def _update_team_fd_column_if_compatible(
        self,
        conn: sqlite3.Connection,
        *,
        team_id: Any,
        fd_team_id: Any,
        fd_name: Optional[str],
    ) -> bool:
        current = conn.execute(
            "SELECT name_en, name_cn, fd_team_id FROM teams WHERE team_id = ?",
            (team_id,),
        ).fetchone()
        current_fd = _safe_int(current["fd_team_id"] if current else None)
        new_fd = _safe_int(fd_team_id)
        if new_fd is None or current_fd == new_fd:
            return False
        source_norm = _norm_name(fd_name)
        current_norms = {
            _norm_name(current["name_en"] if current else None),
            _norm_name(current["name_cn"] if current else None),
        }
        if source_norm and source_norm not in current_norms:
            return False
        if current_fd is not None and new_fd is not None and current_fd != new_fd:
            return False
        conn.execute(
            "UPDATE teams SET fd_team_id = ?, updated_at = CURRENT_TIMESTAMP WHERE team_id = ?",
            (new_fd, team_id),
        )
        return True

    def _result_from_match(self, lottery_row: Dict[str, Any], fd_match: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if _status_text(fd_match.get("status")) not in FINISHED_STATUSES:
            return None
        ft_home = _safe_int(fd_match.get("home_score"))
        ft_away = _safe_int(fd_match.get("away_score"))
        if ft_home is None or ft_away is None:
            return None
        ht_home = _safe_int(fd_match.get("home_score_ht"))
        ht_away = _safe_int(fd_match.get("away_score_ht"))
        handicap = _effective_handicap(
            self.db_path,
            lottery_row.get("lottery_match_id"),
            lottery_row.get("handicap_line") or 0,
        )
        derived = _derive_play_types(ft_home, ft_away, ht_home, ht_away, handicap)
        try:
            ou_line = self.result_writer._ou_line_for_result(lottery_row)
            ou_result = compute_ou_result(ft_home + ft_away, ou_line or 2.5)
        except Exception:
            ou_result = None
        return {
            "lottery_match_id": lottery_row.get("lottery_match_id"),
            "match_id": lottery_row.get("match_id"),
            "home_goals_ft": ft_home,
            "away_goals_ft": ft_away,
            "home_goals_ht": ht_home,
            "away_goals_ht": ht_away,
            "spf_result": derived.get("spf_result"),
            "bf_result": derived.get("bf_result"),
            "bqc_result": derived.get("bqc_result"),
            "rqspf_result": derived.get("rqspf_result"),
            "ou_result": ou_result,
        }

    def _result_conflicts(self, lottery_row: Dict[str, Any], result: Dict[str, Any]) -> List[Dict[str, Any]]:
        conflicts: List[Dict[str, Any]] = []
        for field in (
            "home_goals_ft",
            "away_goals_ft",
            "home_goals_ht",
            "away_goals_ht",
            "spf_result",
            "bf_result",
            "bqc_result",
            "rqspf_result",
            "ou_result",
        ):
            current = _clean_result_value(field, lottery_row.get(field))
            incoming = _clean_result_value(field, result.get(field))
            if current is None or incoming is None:
                continue
            if current != incoming:
                conflicts.append({"field": field, "current": current, "incoming": incoming})
        return conflicts

    def _record_result_conflicts(
        self,
        summary: Dict[str, Any],
        *,
        lottery_row: Dict[str, Any],
        fd_match: Dict[str, Any],
        result: Dict[str, Any],
        overwrite_results: bool,
    ) -> None:
        conflicts = self._result_conflicts(lottery_row, result)
        if not conflicts:
            return
        summary["source_result_conflict_count"] += 1
        if len(summary["source_result_conflicts"]) < 20:
            summary["source_result_conflicts"].append(
                {
                    "lottery_match_id": lottery_row.get("lottery_match_id"),
                    "match_num": lottery_row.get("match_num"),
                    "home_team": lottery_row.get("home_team_cn"),
                    "away_team": lottery_row.get("away_team_cn"),
                    "football_data_match_id": fd_match.get("match_id"),
                    "conflicts": conflicts,
                    "overwrite_results": overwrite_results,
                }
            )

    def _apply_match(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: Optional[str],
        lottery_row: Dict[str, Any],
        fd_match: Dict[str, Any],
        match_mode: str,
        overwrite_results: bool,
        summary: Dict[str, Any],
    ) -> None:
        fd_match_id = str(fd_match.get("match_id") or "")
        payload = {
            "match_mode": match_mode,
            "lottery_match": {
                "lottery_match_id": lottery_row.get("lottery_match_id"),
                "match_num": lottery_row.get("match_num"),
                "home_team": lottery_row.get("home_team_cn"),
                "away_team": lottery_row.get("away_team_cn"),
                "beijing_time": lottery_row.get("beijing_time"),
            },
            "football_data_match": fd_match,
        }
        summary["event_artifacts_recorded"] += self._record_artifact(
            conn,
            run_id=run_id,
            source_type="api",
            entity_type="event",
            entity_id=fd_match_id,
            payload=payload,
            confidence=0.91,
        )

        status, conflict = self._upsert_mapping(
            conn,
            entity_type="lottery_match",
            canonical_id=lottery_row.get("lottery_match_id"),
            source_entity_id=fd_match_id,
            source_entity_name=f"{fd_match.get('home_team')} vs {fd_match.get('away_team')}",
            confidence=0.94,
        )
        if status == "conflict":
            summary["mapping_conflicts"].append(conflict)
        elif status == "upserted":
            summary["match_mappings_upserted"] += 1

        self._upsert_team_identity(
            conn,
            team_id=lottery_row.get("home_team_id"),
            fd_team_id=fd_match.get("home_team_id"),
            fd_name=fd_match.get("home_team"),
            side="home",
            summary=summary,
        )
        self._upsert_team_identity(
            conn,
            team_id=lottery_row.get("away_team_id"),
            fd_team_id=fd_match.get("away_team_id"),
            fd_name=fd_match.get("away_team"),
            side="away",
            summary=summary,
        )

        if _status_text(fd_match.get("status")) in FINISHED_STATUSES:
            if str(lottery_row.get("sell_status") or "").lower() != "finished":
                conn.execute(
                    "UPDATE lottery_matches SET sell_status = 'finished', updated_at = CURRENT_TIMESTAMP WHERE lottery_match_id = ?",
                    (lottery_row.get("lottery_match_id"),),
                )
                summary["sell_status_finished_updated"] += 1

        result = self._result_from_match(lottery_row, fd_match)
        if not result:
            if _status_text(fd_match.get("status")) in FINISHED_STATUSES:
                summary["skipped_no_score"] += 1
            else:
                summary["skipped_not_finished"] += 1
            return
        self._record_result_conflicts(
            summary,
            lottery_row=lottery_row,
            fd_match=fd_match,
            result=result,
            overwrite_results=overwrite_results,
        )
        action, changed_cols = self.result_writer._upsert_result(conn, result, overwrite=overwrite_results)
        if action == "inserted":
            summary["lottery_results_inserted"] += 1
        elif action == "updated":
            summary["lottery_results_updated"] += 1
        else:
            summary["lottery_results_unchanged"] += 1
        if action in {"inserted", "updated"}:
            if self.result_writer._queue_revalidation(
                conn,
                str(lottery_row.get("lottery_match_id") or ""),
                "football_data_org_result_sync",
            ):
                summary["revalidation_queued"] += 1
            summary["changed_result_fields"][str(lottery_row.get("lottery_match_id"))] = changed_cols

    def run(
        self,
        date_from: str,
        date_to: str,
        *,
        apply: bool = False,
        season: int = 2026,
        overwrite_results: bool = False,
        max_matches: Optional[int] = None,
        time_tolerance_minutes: int = 10,
        trigger_source: str = "manual",
    ) -> Dict[str, Any]:
        run_id = None
        if apply:
            run_id = self.foundation.start_run(
                run_type="football_data_wc_sync",
                match_date=date_from,
                trigger_source=trigger_source,
                summary={"date_from": date_from, "date_to": date_to, "season": season, "stage": "start"},
            )
        summary: Dict[str, Any] = {
            "success": True,
            "dry_run": not apply,
            "source": SOURCE_NAME,
            "date_from": date_from,
            "date_to": date_to,
            "season": season,
            "api_matches": 0,
            "api_matches_in_window": 0,
            "lottery_rows": 0,
            "matched_rows": 0,
            "unmatched_rows": 0,
            "match_modes": {},
            "competition_artifacts_recorded": 0,
            "event_artifacts_recorded": 0,
            "match_mappings_upserted": 0,
            "team_mappings_upserted": 0,
            "team_fd_columns_updated": 0,
            "team_fd_columns_updated_despite_mapping_conflict": 0,
            "team_mapping_missing": 0,
            "lottery_results_inserted": 0,
            "lottery_results_updated": 0,
            "lottery_results_unchanged": 0,
            "sell_status_finished_updated": 0,
            "skipped_not_finished": 0,
            "skipped_no_score": 0,
            "source_result_conflict_count": 0,
            "source_result_conflicts": [],
            "revalidation_queued": 0,
            "changed_result_fields": {},
            "mapping_conflicts": [],
            "unmatched_examples": [],
            "max_matches": max_matches,
            "source_health": "ok",
        }
        try:
            matches = self._fetch_wc_matches(season)
            summary["api_matches"] = len(matches)
            window_matches = [
                match for match in matches
                if date_from <= str(match.get("beijing_date") or "") <= date_to
            ]
            summary["api_matches_in_window"] = len(window_matches)
            with self._connect() as conn:
                lottery_rows = self._load_lottery_rows(conn, date_from, date_to)
                summary["lottery_rows"] = len(lottery_rows)
                if lottery_rows and not matches:
                    error = (
                        f"{SOURCE_NAME} returned zero WC matches for season {season} "
                        f"while {len(lottery_rows)} local lottery rows exist"
                    )
                    summary["success"] = False
                    summary["source_health"] = "empty_api_response"
                    summary["error"] = error
                    if apply:
                        self.foundation.finish_run(run_id, status="failed", summary=summary, error=error)
                    return summary
                if lottery_rows and not window_matches:
                    error = (
                        f"{SOURCE_NAME} returned no WC matches in {date_from}..{date_to} "
                        f"while {len(lottery_rows)} local lottery rows exist"
                    )
                    summary["success"] = False
                    summary["source_health"] = "empty_window_response"
                    summary["error"] = error
                    if apply:
                        self.foundation.finish_run(run_id, status="failed", summary=summary, error=error)
                    return summary
                if apply:
                    summary["competition_artifacts_recorded"] += self._record_artifact(
                        conn,
                        run_id=run_id,
                        source_type="api",
                        entity_type="competition_matches",
                        entity_id=f"WC:{season}:{date_from}:{date_to}",
                        payload={
                            "season": season,
                            "date_from": date_from,
                            "date_to": date_to,
                            "matches": window_matches,
                        },
                        confidence=0.91,
                    )
                processed = 0
                visited_rows = 0
                for row in lottery_rows:
                    visited_rows += 1
                    fd_match, mode = self._match_lottery_row(
                        row,
                        window_matches,
                        time_tolerance_minutes=time_tolerance_minutes,
                    )
                    if not fd_match:
                        summary["unmatched_rows"] += 1
                        if len(summary["unmatched_examples"]) < 12:
                            summary["unmatched_examples"].append(
                                {
                                    "lottery_match_id": row.get("lottery_match_id"),
                                    "match_num": row.get("match_num"),
                                    "home_team": row.get("home_team_cn"),
                                    "away_team": row.get("away_team_cn"),
                                    "beijing_time": row.get("beijing_time"),
                                    "reason": mode,
                                }
                            )
                        continue
                    summary["matched_rows"] += 1
                    summary["match_modes"][mode] = int(summary["match_modes"].get(mode) or 0) + 1
                    if not apply:
                        result = self._result_from_match(row, fd_match)
                        if result:
                            self._record_result_conflicts(
                                summary,
                                lottery_row=row,
                                fd_match=fd_match,
                                result=result,
                                overwrite_results=overwrite_results,
                            )
                        continue
                    self._apply_match(
                        conn,
                        run_id=run_id,
                        lottery_row=row,
                        fd_match=fd_match,
                        match_mode=mode,
                        overwrite_results=overwrite_results,
                        summary=summary,
                    )
                    processed += 1
                    if max_matches is not None and max_matches > 0 and processed >= max_matches:
                        summary["matches_deferred"] = max(0, len(lottery_rows) - visited_rows)
                        break
                if apply:
                    conn.commit()
            if apply:
                self.foundation.finish_run(run_id, status="success", summary=summary)
            return summary
        except Exception as exc:
            summary["success"] = False
            summary["error"] = str(exc)
            if apply:
                self.foundation.finish_run(run_id, status="failed", summary=summary, error=str(exc))
            logger.error("football-data.org WC sync failed: %s", exc, exc_info=True)
            return summary
