"""
从 Odds Feed API 采集五大联赛赔率数据
利用 events 接口直接返回的 main_outcome_0/1/2 (欧赔)
一个请求拿到赛事+比分+赔率，高效批量采集
"""

import sys
import io
import os
import time
import json
import sqlite3

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'

from fetchers.odds_feed_api.config import MAJOR_TOURNAMENTS, TEAM_NAME_MAP
from fetchers.common.team_names import normalize_team_name
from fetchers.common.match_key import make_match_key
from fetchers.storage.crud import UnifiedStorage

DB_PATH = "d:/football_tools/data/unified_football.db"


def _normalize_team(name: str) -> str:
    """先用映射表，再走通用normalize"""
    mapped = TEAM_NAME_MAP.get(name)
    if mapped:
        return normalize_team_name(mapped)
    return normalize_team_name(name)


def collect_tournament_odds(tournament_id: int, league_name: str):
    """采集某联赛全部赛事赔率"""
    import requests

    headers = {
        'Content-Type': 'application/json',
        'x-rapidapi-host': 'odds-feed.p.rapidapi.com',
        'x-rapidapi-key': '36ce000ce1msh435e51a1d194fafp1883eejsn26b0639b7066'
    }

    storage = UnifiedStorage()
    print(f"\n=== {league_name} (tid={tournament_id}) ===")

    # 分页获取所有赛事 (API限制per_page=100)
    all_events = []
    page = 0
    last_page = 99  # will be updated from response
    while page <= last_page:
        resp = requests.get(
            'https://odds-feed.p.rapidapi.com/api/v1/events',
            params={
                'sport_id': '1',
                'tournament_id': str(tournament_id),
                'page': str(page),
                'per_page': '100',
            },
            headers=headers,
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"  API error page {page}: {resp.status_code}")
            break

        data = resp.json()
        events = data.get('data', [])
        last_page = data.get('last_page', 0)
        all_events.extend(events)
        print(f"  Page {page}/{last_page}: {len(events)} events")

        if len(events) < 100:
            break
        page += 1
        time.sleep(0.5)

    print(f"  共 {len(all_events)} 场赛事")

    # 逐场提取赔率并存储
    ok = err = skip = 0
    conn = storage._conn()

    for ev in all_events:
        try:
            home_raw = ev.get('team_home', {}).get('name', '')
            away_raw = ev.get('team_away', {}).get('name', '')
            if not home_raw or not away_raw:
                skip += 1
                continue

            home_std = _normalize_team(home_raw)
            away_std = _normalize_team(away_raw)
            date = ev.get('start_at', '')[:10]

            if not date or not home_std or not away_std:
                skip += 1
                continue

            mk = make_match_key(date, home_std, away_std)
            if not mk or '|' not in mk:
                skip += 1
                continue

            # 欧赔 (main_outcome_0=主胜, 1=平, 2=客胜)
            o0 = ev.get('main_outcome_0')
            o1 = ev.get('main_outcome_1')
            o2 = ev.get('main_outcome_2')

            if not o0 and not o1 and not o2:
                skip += 1
                continue

            # 构建赔率JSON
            odds_json = {
                "home_win": o0, "draw": o1, "away_win": o2,
                "home_team": home_std, "away_team": away_std,
                "home_team_original": home_raw, "away_team_original": away_raw,
                "league": league_name, "date": date,
                "event_id": ev.get('id'),
                "bookmaker": "Odds Feed (market avg)",
            }

            # 比分
            sh = ev.get('score_home')
            sa = ev.get('score_away')
            if sh is not None and sa is not None:
                odds_json["home_score"] = sh
                odds_json["away_score"] = sa

            # 确保match存在
            status = "finished" if (sh is not None and sa is not None) else "scheduled"
            conn.execute("""
                INSERT OR IGNORE INTO matches (match_key, date, home_team, away_team, league, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (mk, date, home_std, away_std, league_name, status))

            # 存赔率 (REPLACE去重)
            conn.execute("""
                INSERT OR REPLACE INTO match_data (match_key, source, data_type, data_json)
                VALUES (?, ?, ?, ?)
            """, (mk, "odds_feed", "odds", json.dumps(odds_json, ensure_ascii=False)))

            ok += 1
        except Exception as e:
            err += 1
            if err <= 3:
                print(f"  ERR: {str(e)[:60]}")

    conn.commit()
    conn.close()
    print(f"  完成: ok={ok} err={err} skip={skip}")


def collect_all_odds():
    """采集所有联赛赔率"""
    for tid, name in MAJOR_TOURNAMENTS.items():
        collect_tournament_odds(tid, name)

    # 汇总
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM match_data WHERE source='odds_feed' AND data_type='odds'").fetchone()[0]
    by_lg = conn.execute("""
        SELECT json_extract(data_json, '$.league'), COUNT(*)
        FROM match_data WHERE source='odds_feed' AND data_type='odds'
        GROUP BY json_extract(data_json, '$.league')
    """).fetchall()
    print(f"\n=== 汇总 ===")
    print(f"总赔率记录: {total}")
    for r in by_lg:
        print(f"  {r[0]}: {r[1]}")
    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("league", nargs="?", default="all",
                        choices=["all", "PL", "LaLiga", "SerieA", "Bundesliga", "Ligue1"])
    args = parser.parse_args()

    league_map = {
        "PL": (430, "Premier League"),
        "Bundesliga": (560, "Bundesliga"),
        "SerieA": (719, "Serie A"),
        "LaLiga": (1146, "LaLiga"),
    }

    if args.league == "all":
        collect_all_odds()
    else:
        tid, name = league_map[args.league]
        collect_tournament_odds(tid, name)