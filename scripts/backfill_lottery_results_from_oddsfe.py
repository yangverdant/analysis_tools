"""Backfill lottery_results from oddsfe event API.

Dry-run by default. Use --apply to write after creating a DB backup.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "football_v2.db"
BACKUP_DIR = Path(os.environ.get("FOOTBALL_BACKUP_DIR", ROOT.parent / "football_backups")) / "result_backfills"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.lottery.services.sync_service import (  # noqa: E402
    _derive_play_types,
    _effective_handicap,
    _event_fulltime_score,
    _oddsfe_fetch_score_details,
    _parse_score_details,
)


FINISHED_STATUSES = {"FINISHED", "FT", "ENDED", "AET", "AP"}


def _backup_db(db_path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{db_path.stem}_before_result_backfill_{stamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def _write_audit(rows: Iterable[Dict[str, Any]]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_path = BACKUP_DIR / f"lottery_result_backfill_audit_{stamp}.json"
    audit_path.write_text(json.dumps(list(rows), ensure_ascii=False, indent=2), encoding="utf-8")
    return audit_path


def _fetch_candidates(conn: sqlite3.Connection, date_from: str, date_to: str) -> List[Dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT lm.lottery_match_id, lm.match_id, lm.match_num,
               lm.home_team_cn, lm.away_team_cn, lm.match_date, lm.match_time,
               lm.beijing_time, lm.oddsfe_event_id, lm.handicap_line,
               lr.result_id, lr.home_goals_ft, lr.away_goals_ft,
               lr.home_goals_ht, lr.away_goals_ht, lr.spf_result,
               lr.bf_result, lr.bqc_result, lr.rqspf_result,
               CASE WHEN lr.lottery_match_id IS NULL THEN 0 ELSE 1 END AS has_result
        FROM lottery_matches lm
        LEFT JOIN lottery_results lr ON lm.lottery_match_id = lr.lottery_match_id
        WHERE lm.match_date BETWEEN ? AND ?
          AND lm.oddsfe_event_id IS NOT NULL
          AND lm.oddsfe_event_id <> ''
          AND (
              lr.home_goals_ft IS NULL
              OR lr.away_goals_ft IS NULL
              OR lr.home_goals_ht IS NULL
              OR lr.away_goals_ht IS NULL
              OR lr.spf_result IS NULL
              OR lr.bf_result IS NULL
              OR lr.bqc_result IS NULL
              OR lr.rqspf_result IS NULL
          )
        ORDER BY lm.beijing_time, lm.match_date, lm.match_time
        """,
        (date_from, date_to),
    ).fetchall()
    return [dict(row) for row in rows]


def _plan_row(row: Dict[str, Any]) -> Dict[str, Any]:
    event_data = _oddsfe_fetch_score_details(str(row["oddsfe_event_id"]))
    event_status = str(event_data.get("event_status") or "").upper()
    if event_status and event_status not in FINISHED_STATUSES:
        return {
            "status": "skip_not_finished",
            "lottery_match_id": row["lottery_match_id"],
            "oddsfe_event_id": row["oddsfe_event_id"],
            "event_status": event_status,
        }

    score_details = event_data.get("score_details") or ""
    parsed = _parse_score_details(score_details)
    if not parsed:
        return {
            "status": "skip_no_score_details",
            "lottery_match_id": row["lottery_match_id"],
            "oddsfe_event_id": row["oddsfe_event_id"],
            "event_status": event_status,
        }

    ft_home, ft_away = _event_fulltime_score(event_data, parsed)
    if ft_home is None or ft_away is None:
        return {
            "status": "skip_no_fulltime_score",
            "lottery_match_id": row["lottery_match_id"],
            "oddsfe_event_id": row["oddsfe_event_id"],
            "event_status": event_status,
            "score_details": score_details,
        }

    ht_home, ht_away = parsed.get("ht", (None, None))
    handicap = _effective_handicap(str(DB_PATH), row["lottery_match_id"], row.get("handicap_line") or 0)
    derived = _derive_play_types(ft_home, ft_away, ht_home, ht_away, handicap)

    result = {
        "lottery_match_id": row["lottery_match_id"],
        "match_id": row.get("match_id"),
        "home_goals_ft": ft_home,
        "away_goals_ft": ft_away,
        "home_goals_ht": ht_home,
        "away_goals_ht": ht_away,
        "spf_result": derived.get("spf_result"),
        "bf_result": derived.get("bf_result"),
        "bqc_result": derived.get("bqc_result"),
        "rqspf_result": derived.get("rqspf_result"),
    }
    changed = any(
        row.get(key) != result.get(key)
        for key in (
            "home_goals_ft",
            "away_goals_ft",
            "home_goals_ht",
            "away_goals_ht",
            "spf_result",
            "bf_result",
            "bqc_result",
            "rqspf_result",
        )
    )
    return {
        "status": "upsert" if changed or not row.get("has_result") else "ok",
        "lottery_match_id": row["lottery_match_id"],
        "match_num": row.get("match_num"),
        "home_team_cn": row.get("home_team_cn"),
        "away_team_cn": row.get("away_team_cn"),
        "match_date": row.get("match_date"),
        "beijing_time": row.get("beijing_time"),
        "oddsfe_event_id": row["oddsfe_event_id"],
        "event_status": event_status,
        "score_details": score_details,
        "handicap_used": handicap,
        "result": result,
    }


def _plan(date_from: str, date_to: str, sleep_seconds: float) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = _fetch_candidates(conn, date_from, date_to)
    finally:
        conn.close()

    planned: List[Dict[str, Any]] = []
    for row in rows:
        planned.append(_plan_row(row))
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return planned


def _apply(planned: Iterable[Dict[str, Any]]) -> int:
    rows = [item for item in planned if item.get("status") == "upsert"]
    if not rows:
        return 0

    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("BEGIN IMMEDIATE")
        changed = 0
        for item in rows:
            result = item["result"]
            conn.execute(
                """
                INSERT OR REPLACE INTO lottery_results
                (lottery_match_id, match_id, home_goals_ft, away_goals_ft,
                 home_goals_ht, away_goals_ht, spf_result, bf_result,
                 bqc_result, rqspf_result, draw_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    result["lottery_match_id"],
                    result.get("match_id"),
                    result["home_goals_ft"],
                    result["away_goals_ft"],
                    result["home_goals_ht"],
                    result["away_goals_ht"],
                    result.get("spf_result"),
                    result.get("bf_result"),
                    result.get("bqc_result"),
                    result.get("rqspf_result"),
                ),
            )
            changed += 1
        conn.commit()
        return changed
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="date_from", required=True, help="start date YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", required=True, help="end date YYYY-MM-DD")
    parser.add_argument("--apply", action="store_true", help="write results to DB")
    parser.add_argument("--json", action="store_true", help="print all planned rows")
    parser.add_argument("--sleep", type=float, default=0.15, help="seconds between event API calls")
    args = parser.parse_args()

    planned = _plan(args.date_from, args.date_to, args.sleep)
    summary = {
        "date_from": args.date_from,
        "date_to": args.date_to,
        "total": len(planned),
        "upsert": sum(1 for item in planned if item.get("status") == "upsert"),
        "ok": sum(1 for item in planned if item.get("status") == "ok"),
        "skipped": sum(1 for item in planned if str(item.get("status", "")).startswith("skip")),
    }
    if args.apply:
        summary["backup"] = str(_backup_db(DB_PATH))
        summary["audit_json"] = str(_write_audit(planned))
        summary["sqlite_changes"] = _apply(planned)

    print(json.dumps({"summary": summary, "rows": planned if args.json else planned[:20]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
