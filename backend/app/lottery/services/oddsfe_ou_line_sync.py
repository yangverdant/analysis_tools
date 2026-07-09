"""Targeted oddsfe O/U line audit and backfill.

The event-detail API is good for scores, but real O/U lines live in the oddsfe
market detail pages and the local oddsfe_merged.db cache. This service keeps
football_v2.oddsfe_matches populated by exact event_id, then marks affected
analysis reports stale so the normal analyzer can rebuild them.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.data_access.foundation_dao import FoundationDAO

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB_PATH = str(PROJECT_ROOT / "data" / "football_v2.db")
DEFAULT_ODDSFE_DB_PATH = str(PROJECT_ROOT / "fetchers" / "odds_feed_api" / "oddsfe_merged.db")


def _as_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utc_from_beijing(value: Any) -> Optional[str]:
    text = _as_text(value)
    if not text:
        return None
    for width, fmt in ((19, "%Y-%m-%d %H:%M:%S"), (16, "%Y-%m-%d %H:%M")):
        try:
            dt = datetime.strptime(text[:width], fmt)
            from backend.app.core.time_utils import beijing_to_utc
            return beijing_to_utc(dt).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return None


def _columns(conn: sqlite3.Connection, table: str) -> set:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


class OddsfeOuLineSync:
    """Audit and backfill missing Pinnacle O/U lines by exact oddsfe event id."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH, oddsfe_db_path: Optional[str] = None):
        self.db_path = str(db_path)
        self.oddsfe_db_path = str(
            oddsfe_db_path
            or os.environ.get("ODDSFE_DB_PATH")
            or DEFAULT_ODDSFE_DB_PATH
        )
        self.foundation = FoundationDAO(self.db_path)

    def _connect_v2(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _connect_oddsfe(self) -> Optional[sqlite3.Connection]:
        if not os.path.exists(self.oddsfe_db_path):
            return None
        conn = sqlite3.connect(self.oddsfe_db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_oddsfe_matches(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS oddsfe_matches (
                event_id TEXT PRIMARY KEY,
                event_start_at TEXT,
                team_home_name TEXT,
                team_away_name TEXT,
                category_name TEXT,
                tournament_name TEXT,
                ou_pinnacle_line REAL,
                ou_pinnacle_over REAL,
                ou_pinnacle_under REAL,
                ou_pinnacle_updated_at TEXT,
                spf_pinnacle_home REAL,
                spf_pinnacle_draw REAL,
                spf_pinnacle_away REAL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ou_matches_event ON oddsfe_matches(event_id)")

    def audit(
        self,
        date_from: str,
        date_to: str,
        *,
        include_non_lottery: bool = False,
    ) -> Dict[str, Any]:
        """Return O/U line completeness for lottery rows in a Beijing date range."""
        with self._connect_v2() as conn:
            rows = self._load_lottery_rows(conn, date_from, date_to)

        missing = [row for row in rows if row.get("oddsfe_event_id") and not row.get("has_ou_line")]
        no_bridge = [row for row in rows if not row.get("oddsfe_event_id")]
        available_in_merged = 0
        missing_examples = []

        oddsfe_conn = self._connect_oddsfe()
        try:
            merged_by_event = self._lookup_merged_bulk(
                oddsfe_conn,
                [str(row["oddsfe_event_id"]) for row in missing if row.get("oddsfe_event_id")],
            ) if oddsfe_conn else {}
            for row in missing:
                merged = merged_by_event.get(str(row["oddsfe_event_id"]))
                if merged and merged.get("line"):
                    available_in_merged += 1
                if len(missing_examples) < 20:
                    item = dict(row)
                    item["available_in_oddsfe_merged"] = bool(merged and merged.get("line"))
                    item["merged_line"] = merged.get("line") if merged else None
                    missing_examples.append(item)
        finally:
            if oddsfe_conn:
                oddsfe_conn.close()

        return {
            "success": True,
            "date_from": date_from,
            "date_to": date_to,
            "total": len(rows),
            "bridged": sum(1 for row in rows if row.get("oddsfe_event_id")),
            "with_ou_line": sum(1 for row in rows if row.get("has_ou_line")),
            "missing_ou_line": len(missing),
            "missing_bridge": len(no_bridge),
            "available_in_oddsfe_merged": available_in_merged,
            "needs_live_fetch": max(0, len(missing) - available_in_merged),
            "examples": missing_examples,
            "include_non_lottery": include_non_lottery,
        }

    def run(
        self,
        date_from: str,
        date_to: str,
        *,
        apply: bool = False,
        fetch_live: bool = False,
        max_events: Optional[int] = None,
        reanalyze: bool = False,
        trigger_source: str = "manual",
    ) -> Dict[str, Any]:
        """Backfill missing O/U lines, optionally fetching live market detail."""
        run_id = None
        if apply:
            run_id = self.foundation.start_run(
                run_type="oddsfe_ou_lines",
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
            "already_have_ou": 0,
            "from_oddsfe_merged": 0,
            "live_fetched": 0,
            "live_no_ou": 0,
            "updated": 0,
            "planned": 0,
            "stale_marked": 0,
            "reanalyzed": 0,
            "errors": [],
            "oddsfe_db_path": self.oddsfe_db_path,
        }

        try:
            with self._connect_v2() as conn:
                self._ensure_oddsfe_matches(conn)
                rows = self._load_lottery_rows(conn, date_from, date_to)
                candidates = [
                    row for row in rows
                    if row.get("oddsfe_event_id") and not row.get("has_ou_line")
                ]
                summary["already_have_ou"] = len(rows) - len(candidates)
                summary["candidates"] = len(candidates)
                if max_events is not None and max_events > 0:
                    summary["candidates_deferred"] = max(0, len(candidates) - max_events)
                    candidates = candidates[:max_events]
                else:
                    summary["candidates_deferred"] = 0

                oddsfe_conn = self._connect_oddsfe()
                updated_match_ids: List[str] = []
                try:
                    merged_by_event = self._lookup_merged_bulk(
                        oddsfe_conn,
                        [str(row["oddsfe_event_id"]) for row in candidates if row.get("oddsfe_event_id")],
                    ) if oddsfe_conn else {}
                    for row in candidates:
                        event_id = str(row["oddsfe_event_id"])
                        line_payload = merged_by_event.get(event_id)
                        source = "oddsfe_merged"
                        if not line_payload or not line_payload.get("line"):
                            if not fetch_live:
                                continue
                            line_payload = self._fetch_live_line(event_id, row)
                            source = "oddsfe_live_market"
                            if line_payload and line_payload.get("line"):
                                summary["live_fetched"] += 1
                            else:
                                summary["live_no_ou"] += 1
                                continue
                        else:
                            summary["from_oddsfe_merged"] += 1

                        payload = self._build_upsert_payload(row, line_payload, source)
                        if not apply:
                            summary["planned"] += 1
                            continue
                        self._upsert_football_v2(conn, payload)
                        summary["updated"] += 1
                        updated_match_ids.append(str(row["lottery_match_id"]))
                        self.foundation.record_artifact(
                            run_id=run_id,
                            source_name="oddsfe",
                            source_type="api" if source == "oddsfe_live_market" else "cache",
                            entity_type="event_ou",
                            entity_id=event_id,
                            payload=payload,
                            confidence=0.9 if source == "oddsfe_live_market" else 0.85,
                        )
                    if apply:
                        conn.commit()
                finally:
                    if oddsfe_conn:
                        oddsfe_conn.close()

                if apply and updated_match_ids:
                    summary["stale_marked"] = self._mark_stale(conn, updated_match_ids)
                    conn.commit()

            if apply and reanalyze and updated_match_ids:
                summary["reanalyzed"] = self._reanalyze(updated_match_ids)

            if apply:
                self.foundation.finish_run(run_id, status="success", summary=summary)
            return summary
        except Exception as exc:
            summary["success"] = False
            summary["errors"].append(str(exc))
            if apply:
                self.foundation.finish_run(run_id, status="failed", summary=summary, error=str(exc))
            raise

    def _load_lottery_rows(self, conn: sqlite3.Connection, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT lm.lottery_match_id, lm.match_num, lm.league_name_cn,
                   lm.home_team_cn, lm.away_team_cn,
                   lm.match_date, lm.match_time, lm.beijing_time,
                   lm.oddsfe_event_id,
                   om.event_start_at AS oddsfe_event_start_at,
                   om.ou_pinnacle_line,
                   om.ou_pinnacle_over,
                   om.ou_pinnacle_under
            FROM lottery_matches lm
            LEFT JOIN oddsfe_matches om
              ON CAST(om.event_id AS TEXT) = CAST(lm.oddsfe_event_id AS TEXT)
            WHERE (
                substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?
                OR lm.match_date BETWEEN ? AND ?
            )
            ORDER BY COALESCE(lm.beijing_time, lm.match_date || ' ' || COALESCE(lm.match_time, '99:99')),
                     lm.lottery_match_id
            """,
            (date_from, date_to, date_from, date_to),
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["has_ou_line"] = (
                item.get("ou_pinnacle_line") not in (None, "")
                and item.get("ou_pinnacle_over") not in (None, "")
                and item.get("ou_pinnacle_under") not in (None, "")
            )
            out.append(item)
        return out

    def _lookup_merged(self, conn: Optional[sqlite3.Connection], event_id: str) -> Optional[Dict[str, Any]]:
        return self._lookup_merged_bulk(conn, [event_id]).get(str(event_id))

    def _lookup_merged_bulk(self, conn: Optional[sqlite3.Connection], event_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        if not conn:
            return {}
        ids = sorted({str(event_id) for event_id in event_ids if event_id not in (None, "")})
        if not ids:
            return {}
        cols = _columns(conn, "oddsfe")
        if not cols:
            return {}

        select_cols = [
            "event_id",
            "event_start_at",
            "team_home_name",
            "team_away_name",
            "category_name",
            "tournament_name",
        ]
        optional_cols = [
            "OVER_UNDER_prematch_PINNACLE_line",
            "OVER_UNDER_prematch_PINNACLE_over",
            "OVER_UNDER_prematch_PINNACLE_under",
            "1X2_prematch_PINNACLE_home",
            "1X2_prematch_PINNACLE_draw",
            "1X2_prematch_PINNACLE_away",
        ]
        query_cols = []
        aliases = []
        for col in select_cols + optional_cols:
            if col in cols:
                query_cols.append(f'"{col}"')
                aliases.append(col)
            else:
                query_cols.append("NULL")
                aliases.append(col)
        placeholders = ",".join(["?"] * len(ids))
        rows = conn.execute(
            f"""
            SELECT {', '.join(query_cols)}
            FROM oddsfe
            WHERE CAST(event_id AS TEXT) IN ({placeholders})
            """,
            ids,
        ).fetchall()

        found: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            data = {aliases[idx]: row[idx] for idx in range(len(aliases))}
            event_id = _as_text(data.get("event_id"))
            if not event_id:
                continue
            found[event_id] = self._normalize_merged_payload(data)
        return found

    def _normalize_merged_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        line = _safe_float(data.get("OVER_UNDER_prematch_PINNACLE_line"))
        over = _safe_float(data.get("OVER_UNDER_prematch_PINNACLE_over"))
        under = _safe_float(data.get("OVER_UNDER_prematch_PINNACLE_under"))
        if not line or not over or not under:
            return {**data, "line": None}
        return {
            **data,
            "line": line,
            "over": over,
            "under": under,
            "home_1x2": _safe_float(data.get("1X2_prematch_PINNACLE_home")),
            "draw_1x2": _safe_float(data.get("1X2_prematch_PINNACLE_draw")),
            "away_1x2": _safe_float(data.get("1X2_prematch_PINNACLE_away")),
        }

    def _fetch_live_line(self, event_id: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            from fetchers.odds_feed_api.oddsfe_ou_concurrent import (
                _upsert_event_to_db,
                fetch_event_detail,
            )
        except Exception as exc:
            logger.warning("oddsfe live O/U fetcher unavailable: %s", exc)
            return None

        detail = fetch_event_detail(str(event_id))
        if not detail:
            return None
        event_meta = {
            "event_id": event_id,
            "event_start_at": _utc_from_beijing(row.get("beijing_time")),
            "team_home_name": row.get("home_team_cn"),
            "team_away_name": row.get("away_team_cn"),
            "tournament_name": row.get("league_name_cn"),
        }
        if os.path.exists(self.oddsfe_db_path):
            try:
                _upsert_event_to_db(self.oddsfe_db_path, event_meta, detail)
            except Exception as exc:
                logger.debug("oddsfe_merged live upsert failed for %s: %s", event_id, exc)

        pinnacle = detail.get("pinnacle_best") or {}
        line = _safe_float(pinnacle.get("line"))
        over = _safe_float(pinnacle.get("over"))
        under = _safe_float(pinnacle.get("under"))
        if not line or not over or not under:
            return None
        p1x2 = detail.get("pinnacle_1x2") or {}
        return {
            "event_id": event_id,
            "event_start_at": event_meta["event_start_at"],
            "team_home_name": event_meta["team_home_name"],
            "team_away_name": event_meta["team_away_name"],
            "tournament_name": event_meta["tournament_name"],
            "line": line,
            "over": over,
            "under": under,
            "home_1x2": _safe_float(p1x2.get("home")),
            "draw_1x2": _safe_float(p1x2.get("draw")),
            "away_1x2": _safe_float(p1x2.get("away")),
            "raw_detail": detail,
        }

    def _build_upsert_payload(self, row: Dict[str, Any], line_payload: Dict[str, Any], source: str) -> Dict[str, Any]:
        return {
            "event_id": str(row["oddsfe_event_id"]),
            "lottery_match_id": row.get("lottery_match_id"),
            "event_start_at": line_payload.get("event_start_at") or _utc_from_beijing(row.get("beijing_time")),
            "team_home_name": line_payload.get("team_home_name") or line_payload.get("home_team_name") or row.get("home_team_cn"),
            "team_away_name": line_payload.get("team_away_name") or line_payload.get("away_team_name") or row.get("away_team_cn"),
            "category_name": line_payload.get("category_name"),
            "tournament_name": line_payload.get("tournament_name") or row.get("league_name_cn"),
            "ou_pinnacle_line": line_payload.get("line"),
            "ou_pinnacle_over": line_payload.get("over"),
            "ou_pinnacle_under": line_payload.get("under"),
            "ou_pinnacle_updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "spf_pinnacle_home": line_payload.get("home_1x2"),
            "spf_pinnacle_draw": line_payload.get("draw_1x2"),
            "spf_pinnacle_away": line_payload.get("away_1x2"),
            "source": source,
        }

    def _upsert_football_v2(self, conn: sqlite3.Connection, payload: Dict[str, Any]) -> None:
        cols = _columns(conn, "oddsfe_matches")
        if not cols:
            self._ensure_oddsfe_matches(conn)
            cols = _columns(conn, "oddsfe_matches")

        values: Dict[str, Any] = {}
        for key in (
            "event_id",
            "event_start_at",
            "category_name",
            "tournament_name",
            "ou_pinnacle_line",
            "ou_pinnacle_over",
            "ou_pinnacle_under",
            "ou_pinnacle_updated_at",
            "spf_pinnacle_home",
            "spf_pinnacle_draw",
            "spf_pinnacle_away",
        ):
            if key in cols:
                values[key] = payload.get(key)

        home_value = payload.get("team_home_name")
        away_value = payload.get("team_away_name")
        for col in ("team_home_name", "home_team_name"):
            if col in cols:
                values[col] = home_value
        for col in ("team_away_name", "away_team_name"):
            if col in cols:
                values[col] = away_value
        if "updated_at" in cols:
            values["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        event_id = values.get("event_id") or payload["event_id"]
        existing = conn.execute(
            "SELECT 1 FROM oddsfe_matches WHERE CAST(event_id AS TEXT) = ? LIMIT 1",
            (str(event_id),),
        ).fetchone()
        if existing:
            updates = [(key, val) for key, val in values.items() if key != "event_id" and val is not None]
            if not updates:
                return
            set_clause = ", ".join(f"{key} = ?" for key, _ in updates)
            conn.execute(
                f"UPDATE oddsfe_matches SET {set_clause} WHERE CAST(event_id AS TEXT) = ?",
                [val for _, val in updates] + [str(event_id)],
            )
            return

        if "created_at" in cols:
            values["created_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        insert_values = {key: val for key, val in values.items() if key in cols}
        col_names = list(insert_values.keys())
        placeholders = ", ".join(["?"] * len(col_names))
        conn.execute(
            f"INSERT INTO oddsfe_matches ({', '.join(col_names)}) VALUES ({placeholders})",
            [insert_values[key] for key in col_names],
        )

    def _mark_stale(self, conn: sqlite3.Connection, lottery_match_ids: List[str]) -> int:
        if not lottery_match_ids:
            return 0
        cols = _columns(conn, "lottery_analysis_reports")
        if "is_stale" not in cols:
            try:
                conn.execute("ALTER TABLE lottery_analysis_reports ADD COLUMN is_stale INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
        placeholders = ",".join(["?"] * len(lottery_match_ids))
        cur = conn.execute(
            f"""
            UPDATE lottery_analysis_reports
            SET is_stale = 1
            WHERE lottery_match_id IN ({placeholders})
              AND report_type IN ('prediction', 'full')
              AND COALESCE(is_stale, 0) = 0
            """,
            lottery_match_ids,
        )
        return cur.rowcount

    def _reanalyze(self, lottery_match_ids: List[str]) -> int:
        try:
            from backend.app.core.analyze import analyze_single
        except Exception as exc:
            logger.warning("analyze_single unavailable after O/U sync: %s", exc)
            return 0
        count = 0
        for lottery_match_id in lottery_match_ids:
            try:
                if analyze_single(self.db_path, lottery_match_id):
                    count += 1
            except Exception as exc:
                logger.warning("reanalyze failed for %s: %s", lottery_match_id, exc)
        return count


def default_date_range(days: int = 21) -> Tuple[str, str]:
    end = datetime.now().date()
    start = end - timedelta(days=max(days - 1, 0))
    return start.isoformat(), end.isoformat()
