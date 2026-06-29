"""Repair World Cup lottery rows with canonical Beijing time and oddsfe ids.

This script is intentionally conservative:
- dry-run by default;
- creates a database backup before --apply;
- records before/after values in lottery_match_time_corrections.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "football_v2.db"
ODDSFE_DB_PATH = ROOT / "fetchers" / "odds_feed_api" / "oddsfe_merged.db"
BACKUP_DIR = Path(os.environ.get("FOOTBALL_BACKUP_DIR", ROOT.parent / "football_backups")) / "wc_bridge_repairs"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.worldcup.service import WorldCupContextService  # noqa: E402


MANUAL_ALIASES = {
    "Bosnia-H.": ["Bosnia-Herzegovina", "Bosnia and Herzegovina", "Bosnia"],
    "Congo DR": ["D.R. Congo", "DR Congo", "Democratic Republic of the Congo"],
    "Czechia": ["Czech Republic"],
    "Ivory Coast": ["Cote d'Ivoire", "Côte d'Ivoire"],
    "Korea Republic": ["South Korea"],
    "USA": ["United States", "United States of America"],
}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_id(value: Any) -> str:
    text = _clean_text(value)
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _normalize_time(value: Any) -> Optional[str]:
    text = _clean_text(value)
    if not text:
        return None
    if len(text) == 5:
        return f"{text}:00"
    if len(text) == 8:
        return text
    return text[:8] if len(text) > 8 else text


def _normalize_beijing_time(value: Any) -> Optional[str]:
    text = _clean_text(value).replace("T", " ")
    if not text:
        return None
    if len(text) == 16:
        return f"{text}:00"
    if len(text) >= 19:
        return text[:19]
    return text


def _as_db_match_id(value: Any) -> Optional[Any]:
    text = _normalize_id(value)
    if not text:
        return None
    return int(text) if text.isdigit() else text


def _backup_db(db_path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{db_path.stem}_before_wc_bridge_{stamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def _write_audit_json(repairs: Iterable[Dict[str, Any]]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_path = BACKUP_DIR / f"world_cup_lottery_bridge_audit_{stamp}.json"
    audit_path.write_text(json.dumps(list(repairs), ensure_ascii=False, indent=2), encoding="utf-8")
    return audit_path


def _ensure_audit_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lottery_match_time_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            lottery_match_id TEXT NOT NULL,
            match_num TEXT,
            home_team_cn TEXT,
            away_team_cn TEXT,
            status TEXT NOT NULL,
            reasons_json TEXT,
            original_json TEXT NOT NULL,
            corrected_json TEXT NOT NULL,
            applied INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _canonical_norm(service: WorldCupContextService, value: Any) -> str:
    text = service._norm_name(value)
    aliases = {
        "drcongo": "congodr",
        "democraticrepublicofthecongo": "congodr",
        "southkorea": "korearepublic",
        "unitedstates": "usa",
        "unitedstatesofamerica": "usa",
        "czechrepublic": "czechia",
        "cotedivoire": "ivorycoast",
        "bosniaherzegovina": "bosniah",
        "bosniaandherzegovina": "bosniah",
    }
    return aliases.get(text, text)


def _team_aliases(service: WorldCupContextService, team: Dict[str, Any]) -> Set[str]:
    aliases: Set[str] = set()
    for alias in service._team_aliases(team):
        aliases.add(_canonical_norm(service, alias))
    display = service._display_team_name(team)
    if display:
        aliases.add(_canonical_norm(service, display))
    for value in (team.get("name"), team.get("short_name")):
        for extra in MANUAL_ALIASES.get(value or "", []):
            aliases.add(_canonical_norm(service, extra))
    return {item for item in aliases if item}


def _build_schedule(service: WorldCupContextService) -> Tuple[Dict[Tuple[str, str], Dict[str, Any]], Dict[str, Set[str]]]:
    context = service.get_context(live=False, include_matches=True)
    by_pair: Dict[Tuple[str, str], Dict[str, Any]] = {}
    alias_by_match_id: Dict[str, Set[str]] = {}
    for match in context.get("matches", []):
        home = match.get("home_team") or {}
        away = match.get("away_team") or {}
        home_aliases = _team_aliases(service, home)
        away_aliases = _team_aliases(service, away)
        match_id = str(match.get("match_id") or "")
        alias_by_match_id[f"{match_id}:home"] = home_aliases
        alias_by_match_id[f"{match_id}:away"] = away_aliases
        for home_key in home_aliases:
            for away_key in away_aliases:
                by_pair[(home_key, away_key)] = match
    return by_pair, alias_by_match_id


def _fetch_lottery_rows(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT lottery_match_id, match_id, match_num, league_name_cn,
               home_team_cn, away_team_cn, match_date, match_time,
               beijing_time, oddsfe_event_id
        FROM lottery_matches
        WHERE match_date BETWEEN '2026-06-10' AND '2026-07-21'
          AND (
              league_name_cn LIKE '%世界杯%'
              OR league_name_cn LIKE '%World Cup%'
              OR lottery_match_id LIKE 'wc2026_%'
              OR UPPER(match_num) LIKE 'WC%'
          )
        ORDER BY match_date, match_time, match_num
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _find_oddsfe_event(
    odds_conn: sqlite3.Connection,
    service: WorldCupContextService,
    schedule_match: Dict[str, Any],
    home_aliases: Set[str],
    away_aliases: Set[str],
) -> Optional[Dict[str, Any]]:
    utc_date = schedule_match.get("utc_date")
    if not utc_date:
        return None
    utc_dt = datetime.fromisoformat(str(utc_date).replace("Z", "+00:00")).replace(tzinfo=None)
    start = (utc_dt - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
    end = (utc_dt + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
    odds_conn.row_factory = sqlite3.Row
    rows = odds_conn.execute(
        """
        SELECT event_id, event_start_at, event_status,
               event_score_home, event_score_away,
               team_home_name, team_away_name, tournament_name, category_name
        FROM oddsfe
        WHERE event_start_at BETWEEN ? AND ?
        ORDER BY event_start_at
        """,
        (start, end),
    ).fetchall()

    best: Optional[Dict[str, Any]] = None
    best_score = -1.0
    for row in rows:
        item = dict(row)
        home_key = _canonical_norm(service, item.get("team_home_name"))
        away_key = _canonical_norm(service, item.get("team_away_name"))
        score = 0.0
        if home_key in home_aliases:
            score += 2.0
        if away_key in away_aliases:
            score += 2.0
        if home_key in away_aliases and away_key in home_aliases:
            score += 1.0
        try:
            event_dt = datetime.fromisoformat(str(item.get("event_start_at"))[:19])
            score += max(0.0, 1.0 - abs((event_dt - utc_dt).total_seconds()) / 10800)
        except Exception:
            pass
        if score > best_score:
            best = item
            best_score = score

    return best if best and best_score >= 4.0 else None


def _planned_repairs() -> List[Dict[str, Any]]:
    service = WorldCupContextService()
    by_pair, alias_by_match_id = _build_schedule(service)
    conn = sqlite3.connect(DB_PATH)
    odds_conn = sqlite3.connect(ODDSFE_DB_PATH)
    try:
        repairs: List[Dict[str, Any]] = []
        for row in _fetch_lottery_rows(conn):
            home_key = _canonical_norm(service, row.get("home_team_cn"))
            away_key = _canonical_norm(service, row.get("away_team_cn"))
            schedule_match = by_pair.get((home_key, away_key))
            if not schedule_match:
                repairs.append({"lottery_match_id": row["lottery_match_id"], "status": "missing_world_cup_match", "row": row})
                continue

            match_id = str(schedule_match.get("match_id") or "")
            home_aliases = alias_by_match_id.get(f"{match_id}:home", set())
            away_aliases = alias_by_match_id.get(f"{match_id}:away", set())
            odds_event = _find_oddsfe_event(odds_conn, service, schedule_match, home_aliases, away_aliases)
            corrected_bt = schedule_match.get("beijing_time")
            corrected_bt = _normalize_beijing_time(corrected_bt)
            corrected_time = _normalize_time(corrected_bt[11:19]) if corrected_bt else None
            corrected_date = corrected_bt[:10] if corrected_bt else None
            current_eid = _normalize_id(row.get("oddsfe_event_id"))
            found_eid = _normalize_id((odds_event or {}).get("event_id"))
            corrected_eid = found_eid or current_eid
            reasons: List[str] = []
            if _normalize_id(row.get("match_id")) != _normalize_id(match_id):
                reasons.append("match_id")
            if _clean_text(row.get("match_date")) != _clean_text(corrected_date):
                reasons.append("match_date")
            if _normalize_time(row.get("match_time")) != _normalize_time(corrected_time):
                reasons.append("match_time")
            if _normalize_beijing_time(row.get("beijing_time")) != _normalize_beijing_time(corrected_bt):
                reasons.append("beijing_time")
            if found_eid and current_eid != found_eid:
                reasons.append("oddsfe_event_id")
            repairs.append(
                {
                    "lottery_match_id": row["lottery_match_id"],
                    "match_num": row.get("match_num"),
                    "home_team_cn": row.get("home_team_cn"),
                    "away_team_cn": row.get("away_team_cn"),
                    "status": "update" if reasons else "ok",
                    "reasons": reasons,
                    "original": {
                        "match_id": row.get("match_id"),
                        "match_date": row.get("match_date"),
                        "match_time": _normalize_time(row.get("match_time")),
                        "beijing_time": _normalize_beijing_time(row.get("beijing_time")),
                        "oddsfe_event_id": row.get("oddsfe_event_id"),
                    },
                    "corrected": {
                        "match_id": match_id,
                        "match_date": corrected_date,
                        "match_time": corrected_time,
                        "beijing_time": corrected_bt,
                        "oddsfe_event_id": corrected_eid or None,
                        "source_utc_date": schedule_match.get("utc_date"),
                        "oddsfe_event_status": (odds_event or {}).get("event_status"),
                    },
                }
            )
        return repairs
    finally:
        odds_conn.close()
        conn.close()


def _apply_repairs(repairs: Iterable[Dict[str, Any]]) -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        # The project DB can be sensitive to rollback-journal files on Windows.
        # A full DB backup and JSON audit are written before this function runs.
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("BEGIN IMMEDIATE")
        run_id = f"wc_bridge_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        _ensure_audit_table(conn)
        applied = 0
        for repair in repairs:
            original = repair.get("original") or {}
            corrected = repair.get("corrected") or {}
            conn.execute(
                """
                INSERT INTO lottery_match_time_corrections (
                    run_id, lottery_match_id, match_num, home_team_cn, away_team_cn,
                    status, reasons_json, original_json, corrected_json, applied
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    repair.get("lottery_match_id"),
                    repair.get("match_num"),
                    repair.get("home_team_cn"),
                    repair.get("away_team_cn"),
                    repair.get("status"),
                    json.dumps(repair.get("reasons") or [], ensure_ascii=False),
                    json.dumps(original, ensure_ascii=False),
                    json.dumps(corrected, ensure_ascii=False),
                    1 if repair.get("status") == "update" else 0,
                ),
            )
            if repair.get("status") != "update":
                continue
            lm_id = repair["lottery_match_id"]
            cursor = conn.execute(
                """
                UPDATE lottery_matches
                SET match_id = ?,
                    match_date = ?,
                    match_time = ?,
                    beijing_time = ?,
                    oddsfe_event_id = COALESCE(?, oddsfe_event_id),
                    updated_at = CURRENT_TIMESTAMP
                WHERE lottery_match_id = ?
                """,
                (
                    _as_db_match_id(corrected.get("match_id")),
                    corrected.get("match_date"),
                    corrected.get("match_time"),
                    corrected.get("beijing_time"),
                    _normalize_id(corrected.get("oddsfe_event_id")) or None,
                    lm_id,
                ),
            )
            applied += cursor.rowcount
        conn.commit()
        return applied
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write repairs to football_v2.db")
    parser.add_argument("--json", action="store_true", help="print full JSON result")
    args = parser.parse_args()

    repairs = _planned_repairs()
    summary = {
        "total": len(repairs),
        "updates": sum(1 for item in repairs if item.get("status") == "update"),
        "ok": sum(1 for item in repairs if item.get("status") == "ok"),
        "missing": sum(1 for item in repairs if item.get("status") == "missing_world_cup_match"),
    }
    if args.apply:
        backup_path = _backup_db(DB_PATH)
        audit_path = _write_audit_json(repairs)
        changed = _apply_repairs(repairs)
        summary["backup"] = str(backup_path)
        summary["audit_json"] = str(audit_path)
        summary["sqlite_changes"] = changed
    print(json.dumps({"summary": summary, "repairs": repairs if args.json else repairs[:20]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
