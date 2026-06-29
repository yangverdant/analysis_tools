"""Lottery result consistency audit and repair.

This module keeps settled result fields derived from the actual score:
SPF, BF, BQC, RQSPF and O/U. It does not fetch external sources; source refresh
belongs to the oddsfe/sporttery collectors. This step validates what is already
in the local result row and queues revalidation when corrections are applied.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from backend.app.data_access.foundation_dao import FoundationDAO
from backend.app.lottery.services.ou_calculator import compute_ou_result, parse_ou_line
from backend.app.lottery.services.sync_service import (
    _derive_play_types,
    _effective_handicap,
    _normalize_bqc_result,
)


SPF_TO_CODE = {
    "3": "3",
    "1": "1",
    "0": "0",
    "home_win": "3",
    "draw": "1",
    "away_win": "0",
    "\u4e3b\u80dc": "3",
    "\u5e73\u5c40": "1",
    "\u5e73": "1",
    "\u5ba2\u80dc": "0",
}
RQSPF_TO_CODE = {
    **SPF_TO_CODE,
    "\u8ba9\u80dc": "3",
    "\u8ba9\u5e73": "1",
    "\u8ba9\u8d1f": "0",
}
EMPTY_VALUES = {"", "-", "--", "none", "null", "nan", "unknown", "\u672a\u77e5"}


@dataclass
class ResultAuditChange:
    lottery_match_id: str
    match_num: Optional[str]
    match_date: Optional[str]
    home_team_cn: Optional[str]
    away_team_cn: Optional[str]
    field: str
    before: Any
    after: Any
    reason: str


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in EMPTY_VALUES:
        return None
    return text


def _code(value: Any, mapping: Dict[str, str]) -> Optional[str]:
    text = _clean(value)
    if text is None:
        return None
    return mapping.get(text) or mapping.get(text.lower()) or text


def _score_text(home: Any, away: Any) -> Optional[str]:
    if home is None or away is None:
        return None
    try:
        return f"{int(home)}:{int(away)}"
    except (TypeError, ValueError):
        return None


def _ou_line_from_existing(value: Any) -> Optional[float]:
    return parse_ou_line(value)


class LotteryResultConsistencyAuditor:
    """Audit and optionally repair derived lottery result fields."""

    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        self.foundation = FoundationDAO(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    @staticmethod
    def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
        try:
            return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
        except sqlite3.Error:
            return set()

    def _rows(
        self,
        conn: sqlite3.Connection,
        date_from: str,
        date_to: str,
        league: Optional[str],
        limit: int,
    ) -> List[sqlite3.Row]:
        where = [
            "substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?",
            "lr.home_goals_ft IS NOT NULL",
            "lr.away_goals_ft IS NOT NULL",
        ]
        params: List[Any] = [date_from, date_to]
        if league:
            where.append("COALESCE(lm.league_name_cn, '') = ?")
            params.append(league)
        if limit and limit > 0:
            limit_sql = "LIMIT ?"
            params.append(limit)
        else:
            limit_sql = ""

        return conn.execute(
            f"""
            SELECT lr.rowid AS result_rowid, lr.*,
                   lm.match_num, lm.match_date, lm.beijing_time,
                   lm.home_team_cn, lm.away_team_cn,
                   lm.league_name_cn, lm.handicap_line, lm.oddsfe_event_id
            FROM lottery_results lr
            JOIN lottery_matches lm ON lm.lottery_match_id = lr.lottery_match_id
            WHERE {' AND '.join(where)}
            ORDER BY substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10),
                     lm.match_time, lm.lottery_match_id
            {limit_sql}
            """,
            params,
        ).fetchall()

    def _ou_line_for_row(self, conn: sqlite3.Connection, row: sqlite3.Row) -> Optional[float]:
        lottery_match_id = str(row["lottery_match_id"] or "")
        event_id = str(row["oddsfe_event_id"] or "").strip()
        if event_id and "oddsfe_matches" in self._known_tables(conn):
            try:
                odds_row = conn.execute(
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
                if odds_row:
                    line = parse_ou_line(odds_row["ou_pinnacle_line"])
                    if line:
                        return line
            except Exception:
                pass

        try:
            report_row = conn.execute(
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
            if report_row:
                report = json.loads(report_row["report_data"])
                play_predictions = report.get("play_predictions") or {}
                analyses = report.get("analyses") or {}
                ou = play_predictions.get("ou") or play_predictions.get("over_under") or analyses.get("ou") or {}
                for key in ("recommendation", "best_line", "line"):
                    line = parse_ou_line(ou.get(key))
                    if line:
                        return line
        except Exception:
            pass

        existing = _ou_line_from_existing(row["ou_result"] if "ou_result" in row.keys() else None)
        if existing:
            return existing
        return None

    def _known_tables(self, conn: sqlite3.Connection) -> set[str]:
        return {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

    def _expected(self, conn: sqlite3.Connection, row: sqlite3.Row) -> Dict[str, Any]:
        home_ft = int(row["home_goals_ft"])
        away_ft = int(row["away_goals_ft"])
        home_ht = row["home_goals_ht"]
        away_ht = row["away_goals_ht"]
        if home_ht is not None:
            home_ht = int(home_ht)
        if away_ht is not None:
            away_ht = int(away_ht)

        handicap = _effective_handicap(self.db_path, str(row["lottery_match_id"]), row["handicap_line"] or 0)
        derived = _derive_play_types(home_ft, away_ft, home_ht, away_ht, handicap)
        expected = {
            "spf_result": derived.get("spf_result"),
            "bf_result": _score_text(home_ft, away_ft),
            "bqc_result": derived.get("bqc_result") or _normalize_bqc_result(row["bqc_result"]),
            "rqspf_result": derived.get("rqspf_result"),
        }

        if "ou_result" in row.keys():
            line = self._ou_line_for_row(conn, row)
            if line is not None:
                expected["ou_result"] = compute_ou_result(home_ft + away_ft, line)
        return expected

    def _current(self, field: str, value: Any) -> Optional[str]:
        if field == "spf_result":
            return _code(value, SPF_TO_CODE)
        if field == "rqspf_result":
            return _code(value, RQSPF_TO_CODE)
        if field == "bqc_result":
            return _normalize_bqc_result(value)
        return _clean(value)

    def _change(
        self,
        row: sqlite3.Row,
        field: str,
        before: Any,
        after: Any,
        reason: str,
    ) -> ResultAuditChange:
        return ResultAuditChange(
            lottery_match_id=str(row["lottery_match_id"]),
            match_num=row["match_num"],
            match_date=str(row["beijing_time"] or row["match_date"] or "")[:10],
            home_team_cn=row["home_team_cn"],
            away_team_cn=row["away_team_cn"],
            field=field,
            before=before,
            after=after,
            reason=reason,
        )

    def _ensure_queue(self, conn: sqlite3.Connection) -> None:
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

    def _queue_revalidation(self, conn: sqlite3.Connection, lottery_match_id: str, reason: str) -> bool:
        self._ensure_queue(conn)
        existing = conn.execute(
            """
            SELECT 1 FROM lottery_revalidation_queue
            WHERE lottery_match_id = ? AND status = 'pending'
            LIMIT 1
            """,
            (lottery_match_id,),
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
                "result_audit:" + uuid.uuid4().hex,
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
        league: Optional[str] = None,
        limit: int = 0,
        trigger_source: str = "manual_result_consistency",
    ) -> Dict[str, Any]:
        run_id = self.foundation.start_run(
            run_type="result_consistency_audit",
            match_date=date_from,
            trigger_source=trigger_source,
            summary={
                "stage": "start",
                "date_from": date_from,
                "date_to": date_to,
                "league": league or "",
                "apply": apply,
            },
        )
        summary: Dict[str, Any] = {
            "success": True,
            "dry_run": not apply,
            "date_from": date_from,
            "date_to": date_to,
            "league": league or "",
            "rows_checked": 0,
            "rows_changed": 0,
            "field_changes": 0,
            "queued_revalidation": 0,
            "by_field": {},
            "changes": [],
        }

        try:
            with self._connect() as conn:
                rows = self._rows(conn, date_from, date_to, league, limit)
                summary["rows_checked"] = len(rows)
                table_cols = self._table_columns(conn, "lottery_results")
                updateable_fields = {
                    "spf_result",
                    "bf_result",
                    "bqc_result",
                    "rqspf_result",
                    "ou_result",
                } & table_cols

                changed_match_ids: set[str] = set()
                for row in rows:
                    expected = self._expected(conn, row)
                    updates: Dict[str, Any] = {}
                    row_changes: List[ResultAuditChange] = []
                    for field, after in expected.items():
                        if field not in updateable_fields or after is None:
                            continue
                        before = row[field] if field in row.keys() else None
                        current = self._current(field, before)
                        if current != str(after):
                            change = self._change(
                                row,
                                field,
                                before,
                                after,
                                "derived_from_score_handicap_or_ou_line",
                            )
                            row_changes.append(change)
                            updates[field] = after
                            summary["by_field"][field] = int(summary["by_field"].get(field, 0)) + 1

                    if not row_changes:
                        continue
                    changed_match_ids.add(str(row["lottery_match_id"]))
                    summary["field_changes"] += len(row_changes)
                    summary["changes"].extend(asdict(item) for item in row_changes[:50])

                    if apply and updates:
                        params = list(updates.values()) + [row["result_rowid"]]
                        conn.execute(
                            f"UPDATE lottery_results SET {', '.join(f'{field} = ?' for field in updates)} WHERE rowid = ?",
                            params,
                        )
                        if self._queue_revalidation(
                            conn,
                            str(row["lottery_match_id"]),
                            "result_consistency_audit",
                        ):
                            summary["queued_revalidation"] += 1

                summary["rows_changed"] = len(changed_match_ids)
                if apply:
                    conn.commit()

            if len(summary["changes"]) > 50:
                summary["changes"] = summary["changes"][:50]
            self.foundation.finish_run(run_id, status="success", summary=summary)
            return {"run_id": run_id, **summary}
        except Exception as exc:
            summary["success"] = False
            summary["error"] = str(exc)
            self.foundation.finish_run(run_id, status="failed", summary=summary, error=str(exc))
            return {"run_id": run_id, **summary}


def run_result_consistency_audit(
    db_path: str,
    date_from: str,
    date_to: str,
    *,
    apply: bool = False,
    league: Optional[str] = None,
    limit: int = 0,
    trigger_source: str = "manual_result_consistency",
) -> Dict[str, Any]:
    return LotteryResultConsistencyAuditor(db_path).run(
        date_from,
        date_to,
        apply=apply,
        league=league,
        limit=limit,
        trigger_source=trigger_source,
    )
