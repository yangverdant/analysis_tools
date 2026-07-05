#!/usr/bin/env python3
"""Sync future matches from oddsfe schedule API into lottery_matches.

This is the **primary** match collection path since 2026-07-05, replacing
sporttery which got WAF-banned (see memory: sporttery_waf_ban).

Strategy:
1. Fetch oddsfe schedule for target_date (today + 1, +2)
2. Filter by (tournament_name, category_name) whitelist — only mainstream leagues
3. For each event, normalize team names (EN -> CN via teams table + team_aliases)
4. Insert into lottery_matches with oddsfe_event_id pre-filled
5. Set beijing_time from event_start_at
6. Skip if match already exists (preserve existing rows)

Called by cloud_automation_tick.sh on every tick.
"""
import json
import logging
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = "/opt/football_tools"
DB_PATH = f"{ROOT}/data/football_v2.db"

sys.path.insert(0, ROOT)
sys.path.insert(0, f"{ROOT}/backend")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# Whitelist of (tournament_name, category_name) tuples that map to CN lottery leagues.
# Keyed by CN league name (matching what sporttery historically returns).
# Format: "CN_NAME": [(tournament, category), ...]
# When tournament_name matches *exactly* and category matches, the event is kept
# and league_name_cn is set to the key.
LEAGUE_WHITELIST: Dict[str, List[Tuple[str, str]]] = {
    # 中国彩民关注的国内联赛
    "中超": [("Chinese Super League", "China"), ("Super League", "China")],
    "中甲": [("League One", "China")],
    "中乙": [("League Two", "China")],
    # 日韩
    "日职": [("J1 League", "Japan")],
    "日乙": [("J2 League", "Japan")],
    "韩职": [("K League 1", "South Korea")],
    "韩乙": [("K League 2", "South Korea")],
    "韩联杯": [("Korean Cup", "South Korea")],
    # 北欧
    "瑞超": [("Allsvenskan", "Sweden")],
    "瑞甲": [("Superettan", "Sweden")],
    "挪超": [("Eliteserien", "Norway")],
    "挪甲": [("OBOS-ligaen", "Norway")],
    "芬超": [("Veikkausliiga", "Finland")],
    "芬甲": [("Ykkosliiga", "Finland")],
    "冰岛超": [("Urvalsdeild", "Iceland")],
    # 美洲
    "美职": [("MLS", "USA")],
    "美乙": [("USL Championship", "USA")],
    "美职联杯": [("U.S. Open Cup", "USA")],
    "智利杯": [("Copa Chile", "Chile")],
    "厄甲": [("Liga Pro", "Ecuador")],
    "巴甲": [("Serie A", "Brazil"), ("Brasileirão", "Brazil")],
    "巴乙": [("Serie B", "Brazil"), ("Serie B Superbet", "Brazil")],
    # 欧洲五大联赛
    "英超": [("Premier League", "England")],
    "英冠": [("Championship", "England")],
    "英甲": [("League One", "England")],
    "英乙": [("League Two", "England")],
    "西甲": [("La Liga", "Spain")],
    "西乙": [("Segunda Division", "Spain")],
    "德甲": [("Bundesliga", "Germany")],
    "德乙": [("2. Bundesliga", "Germany")],
    "意甲": [("Serie A", "Italy")],
    "意乙": [("Serie B", "Italy")],
    "法甲": [("Ligue 1", "France")],
    "法乙": [("Ligue 2", "France")],
    # 欧洲其他主流联赛
    "荷甲": [("Eredivisie", "Netherlands")],
    "比甲": [("Pro League", "Belgium")],
    "葡超": [("Primeira Liga", "Portugal")],
    "苏超": [("Premiership", "Scotland")],
    "奥甲": [("Bundesliga", "Austria")],
    "瑞士超": [("Super League", "Switzerland")],
    "丹超": [("Superliga", "Denmark")],
    "捷甲": [("Czech Liga", "Czech Republic")],
    "波超": [("Ekstraklasa", "Poland")],
    "希腊超": [("Super League", "Greece")],
    "土超": [("Süper Lig", "Turkey")],
    "俄超": [("Premier League", "Russia")],
    "乌超": [("Premier League", "Ukraine")],
    # 欧洲杯赛
    "欧冠": [("Champions League", "Europe")],
    "欧联": [("Europa League", "Europe")],
    "欧协联": [("Conference League", "Europe")],
    # 亚洲其他
    "沙特联": [("Pro League", "Saudi Arabia")],
    "卡塔尔联": [("Stars League", "Qatar")],
    "阿联酋联": [("Pro League", "UAE")],
    "日联杯": [("J-League Cup", "Japan")],
    # 国际赛
    "世界杯": [
        ("World Championship", "World"),
        ("World Cup", "World"),
        ("World Cup Qualification", "World"),
    ],
    "国际赛": [
        ("International Friendlies", "World"),
        ("Friendly International", "World"),
    ],
    # 洲际杯赛
    "欧洲杯": [("Euro Championship", "Europe")],
    "美洲杯": [("Copa America", "World")],
    "亚洲杯": [("AFC Asian Cup", "Asia")],
    "非洲杯": [("Africa Cup of Nations", "Africa")],
}


# Inverted index: (tournament_name, category_name) -> league_name_cn
_TOUPLE_TO_CN: Dict[Tuple[str, str], str] = {}
for cn, tlist in LEAGUE_WHITELIST.items():
    for tup in tlist:
        _TOUPLE_TO_CN[tup] = cn


def _resolve_league_cn(tournament: str, category: str) -> Optional[str]:
    """Map (tournament, category) to CN league name. Returns None if not whitelisted."""
    if not tournament:
        return None
    return _TOUPLE_TO_CN.get((tournament, category))


def _cn_team_name(conn: sqlite3.Connection, name_en: str) -> str:
    """Translate EN team name to CN via teams table + team_aliases fallback.

    5-layer matching:
    1. Direct exact match on teams.name_en
    2. team_aliases.alias_name exact match
    3. Case-insensitive exact match
    4. Fuzzy: teams.name_en contains the input as a word (handles "Seoul" -> "FC Seoul")
    5. Fallback: return EN as-is
    """
    if not name_en:
        return ""
    # 1. Direct match
    row = conn.execute(
        "SELECT name_cn FROM teams WHERE name_en = ? LIMIT 1", (name_en,)
    ).fetchone()
    if row and row[0]:
        return row[0]
    # 2. team_aliases
    row = conn.execute(
        "SELECT t.name_cn FROM teams t JOIN team_aliases a ON t.team_id = a.team_id "
        "WHERE a.alias_name = ? LIMIT 1", (name_en,)
    ).fetchone()
    if row and row[0]:
        return row[0]
    # 3. Case-insensitive
    row = conn.execute(
        "SELECT name_cn FROM teams WHERE name_en = ? COLLATE NOCASE LIMIT 1", (name_en,)
    ).fetchone()
    if row and row[0]:
        return row[0]
    # 4. Fuzzy: name_en contains input as a whole word (e.g. "Seoul" matches "FC Seoul")
    #    Skip very short inputs (<3 chars) to avoid false positives like "FC"
    if len(name_en) >= 3:
        row = conn.execute(
            "SELECT name_cn FROM teams "
            "WHERE name_en LIKE ? AND name_cn IS NOT NULL AND name_cn != '' "
            "ORDER BY LENGTH(name_en) ASC LIMIT 1",
            (f"% {name_en} %",)
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT name_cn FROM teams "
                "WHERE (name_en LIKE ? OR name_en LIKE ? OR name_en LIKE ?) "
                "AND name_cn IS NOT NULL AND name_cn != '' "
                "ORDER BY LENGTH(name_en) ASC LIMIT 1",
                (f"% {name_en}", f"{name_en} %", f"% {name_en} %")
            ).fetchone()
        if row and row[0]:
            return row[0]
    return name_en


def _persist_team_name_cn(conn: sqlite3.Connection, name_en: str, name_cn: str) -> bool:
    """Persist learned EN->CN mapping into teams.name_cn (if currently NULL).

    Returns True if a row was updated. This is how the system "memorizes" team
    name translations over time — each tick learns a few more mappings, so the
    teams table gradually fills in name_cn for leagues oddsfe covers.
    """
    if not name_en or not name_cn or name_en == name_cn:
        return False
    # Only update if name_cn is currently NULL/empty (don't overwrite existing CN)
    cur = conn.execute(
        "UPDATE teams SET name_cn = ? WHERE name_en = ? AND (name_cn IS NULL OR name_cn = '')",
        (name_cn, name_en)
    )
    if cur.rowcount > 0:
        # Also add to team_aliases if not present
        row = conn.execute("SELECT team_id FROM teams WHERE name_en = ?", (name_en,)).fetchone()
        if row:
            tid = row[0]
            exists = conn.execute(
                "SELECT 1 FROM team_aliases WHERE team_id=? AND alias_name=?", (tid, name_en)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO team_aliases (team_id, alias_name, source) VALUES (?, ?, 'oddsfe_learned')",
                    (tid, name_en)
                )
        return True
    return False


def _learn_team_names_from_history(conn: sqlite3.Connection,
                                    schedule_by_date: Dict[str, List[Dict]]) -> int:
    """Learn EN->CN team name mappings from historical lottery_matches rows
    that have both home_team_cn (CN) and oddsfe_event_id. Cross-reference with
    schedule to find the oddsfe EN team name for that event.

    Persists each learned mapping into teams.name_cn (if NULL) so future runs
    don't need to relearn. This is the "memory" mechanism: each tick learns
    a few more team name translations.
    """
    from datetime import date, timedelta
    learned = 0
    today = date.today()
    for offset in range(-30, 2):
        d = today + timedelta(days=offset)
        ds = d.strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT home_team_cn, away_team_cn, oddsfe_event_id FROM lottery_matches "
            "WHERE match_date=? AND oddsfe_event_id IS NOT NULL",
            (ds,)
        ).fetchall()
        if not rows:
            continue
        events = schedule_by_date.get(ds, [])
        if not events:
            continue
        eid_to_ev = {str(e.get("event_id")): e for e in events}
        for home_cn, away_cn, eid in rows:
            e = eid_to_ev.get(str(eid))
            if not e:
                continue
            eh = e.get("team_home_name","")
            ea = e.get("team_away_name","")
            if home_cn and eh and home_cn != eh and any("一" <= c <= "鿿" for c in home_cn):
                if _persist_team_name_cn(conn, eh, home_cn):
                    learned += 1
            if away_cn and ea and away_cn != ea and any("一" <= c <= "鿿" for c in away_cn):
                if _persist_team_name_cn(conn, ea, away_cn):
                    learned += 1
    return learned


def _to_beijing_time(start_at: str) -> str:
    """Convert ISO event_start_at to Beijing time string."""
    if not start_at:
        return ""
    try:
        dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        beijing = dt + timedelta(hours=8)
        return beijing.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _derive_match_fields(event: Dict, conn: sqlite3.Connection) -> Optional[Dict]:
    """Build lottery_matches row from oddsfe event. Returns None if filtered out."""
    eid = str(event.get("event_id") or "")
    home_en = (event.get("team_home_name") or "").strip()
    away_en = (event.get("team_away_name") or "").strip()
    start_at = event.get("event_start_at") or ""
    tournament = event.get("tournament_name") or ""
    category = event.get("category_name") or ""

    league_cn = _resolve_league_cn(tournament, category)
    if league_cn is None:
        return None  # Not in whitelist — skip

    if not eid or not home_en or not away_en:
        return None

    home_cn = _cn_team_name(conn, home_en)
    away_cn = _cn_team_name(conn, away_en)

    beijing_time = _to_beijing_time(start_at)
    match_date = beijing_time[:10] if beijing_time else start_at[:10]
    match_time = beijing_time[11:19] if beijing_time else ""

    match_num = eid[-4:] if eid else "0000"
    lottery_match_id = match_date.replace("-", "") + match_num

    return {
        "lottery_match_id": lottery_match_id,
        "home_team_cn": home_cn,
        "away_team_cn": away_cn,
        "league_name_cn": league_cn,
        "match_num": match_num,
        "match_date": match_date,
        "match_time": match_time,
        "beijing_time": beijing_time,
        "sell_status": "selling",
        "play_types": "[]",
        "handicap_line": 0,
        "oddsfe_event_id": eid,
    }


def sync_oddsfe_matches_to_lottery(target_date: date, trigger_source: str = "oddsfe_schedule_sync") -> Dict:
    """Pull oddsfe schedule for target_date and write to lottery_matches."""
    from backend.app.lottery.services.sync_service import _oddsfe_fetch_schedule

    events = _oddsfe_fetch_schedule(target_date.strftime("%Y-%m-%d"))
    if not events:
        return {"date": str(target_date), "fetched": 0, "inserted": 0, "skipped": 0, "filtered": 0}

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    cursor = conn.cursor()

    inserted = 0
    skipped = 0
    filtered_out = 0
    updated = 0

    for event in events:
        try:
            fields = _derive_match_fields(event, conn)
            if fields is None:
                filtered_out += 1
                continue
            if not fields["lottery_match_id"] or not fields["home_team_cn"]:
                skipped += 1
                continue

            # Use oddsfe_event_id as the natural unique key, NOT lottery_match_id.
            # This prevents cross-date duplicates: same event appearing in both
            # 7/5 and 7/6 schedules (because beijing_time crosses midnight) would
            # get different lottery_match_ids but the same oddsfe_event_id.
            existing = cursor.execute(
                "SELECT lottery_match_id, match_date, home_team_cn FROM lottery_matches "
                "WHERE oddsfe_event_id = ? LIMIT 1",
                (fields["oddsfe_event_id"],)
            ).fetchone()

            if existing:
                # Update existing row in place — keep its lottery_match_id to
                # avoid breaking child rows (predictions, results, bets).
                # CN-name handling: if existing home_team_cn is EN-only (no CJK)
                # but the new value has CJK (better translation), overwrite it.
                # This lets the system gradually upgrade EN->CN as name_cn
                # translations are learned/persisted.
                old_id = existing[0]
                new_home = fields["home_team_cn"]
                new_away = fields["away_team_cn"]
                new_home_has_cjk = bool(new_home) and any("一" <= c <= "鿿" for c in new_home)
                new_away_has_cjk = bool(new_away) and any("一" <= c <= "鿿" for c in new_away)
                old_home = existing[2] or ""
                old_home_has_cjk = bool(old_home) and any("一" <= c <= "鿿" for c in old_home)

                # Read old_away in the same pass so we can decide the away_clause.
                old_away_row = cursor.execute(
                    "SELECT away_team_cn FROM lottery_matches WHERE lottery_match_id = ?",
                    (old_id,)
                ).fetchone()
                old_away = (old_away_row[0] if old_away_row else "") or ""
                old_away_has_cjk = bool(old_away) and any("一" <= c <= "鿿" for c in old_away)

                home_clause = ("home_team_cn = ?" if (new_home_has_cjk and not old_home_has_cjk)
                               else "home_team_cn = COALESCE(NULLIF(home_team_cn, ''), ?)")
                away_clause = ("away_team_cn = ?" if (new_away_has_cjk and not old_away_has_cjk)
                               else "away_team_cn = COALESCE(NULLIF(away_team_cn, ''), ?)")

                cursor.execute(
                    f"UPDATE lottery_matches SET "
                    "match_date = ?, match_time = ?, beijing_time = ?, "
                    f"{home_clause}, {away_clause}, "
                    "league_name_cn = COALESCE(NULLIF(league_name_cn, ''), ?), "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE lottery_match_id = ?",
                    (fields["match_date"], fields["match_time"], fields["beijing_time"],
                     new_home, new_away, fields["league_name_cn"],
                     old_id)
                )
                updated += 1
            else:
                cursor.execute(
                    """INSERT OR IGNORE INTO lottery_matches
                       (lottery_match_id, home_team_cn, away_team_cn, league_name_cn,
                        match_num, match_date, match_time, beijing_time, sell_status,
                        play_types, handicap_line, oddsfe_event_id, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                    (
                        fields["lottery_match_id"],
                        fields["home_team_cn"],
                        fields["away_team_cn"],
                        fields["league_name_cn"],
                        fields["match_num"],
                        fields["match_date"],
                        fields["match_time"],
                        fields["beijing_time"],
                        fields["sell_status"],
                        fields["play_types"],
                        fields["handicap_line"],
                        fields["oddsfe_event_id"],
                    ),
                )
                if cursor.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
        except Exception as exc:
            logger.warning("insert failed for event %s: %s", event.get("event_id"), exc)
            skipped += 1

    conn.commit()

    # Learn team name mappings from history + persist into teams.name_cn.
    # Wider window (30 days) than the sync window (3 days) so we can learn
    # mappings from matches that happened earlier this month.
    try:
        from backend.app.lottery.services.sync_service import _oddsfe_fetch_schedule
        from datetime import date as _date, timedelta as _td
        schedule_30d: Dict[str, List[Dict]] = {}
        today = _date.today()
        for off in range(-30, 2):
            d = today + _td(days=off)
            ds = d.strftime("%Y-%m-%d")
            try:
                schedule_30d[ds] = _oddsfe_fetch_schedule(ds)
            except Exception:
                pass
        learned = _learn_team_names_from_history(conn, schedule_30d)
        if learned:
            logger.info("learned %d team name mappings into teams.name_cn", learned)
    except Exception as exc:
        logger.warning("learn_team_names failed: %s", exc)

    conn.close()

    result = {
        "date": str(target_date),
        "fetched": len(events),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "filtered": filtered_out,
    }
    logger.info("oddsfe_schedule_sync %s: %s", target_date, result)
    return result


def main() -> None:
    from datetime import date as _date

    today = _date.today()
    total_inserted = 0
    for offset in (0, 1, 2):
        target = today + timedelta(days=offset)
        try:
            result = sync_oddsfe_matches_to_lottery(target)
            total_inserted += result["inserted"]
        except Exception as exc:
            logger.error("sync failed for %s: %s", target, exc)

    print(f"oddsfe_schedule_sync done: total_inserted={total_inserted}")


if __name__ == "__main__":
    main()
