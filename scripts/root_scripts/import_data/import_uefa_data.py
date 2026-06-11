"""
UEFA欧战赛事数据采集

包含:
1. UEFA Champions League (欧冠) - ID: 10, API ID: 7
2. UEFA Europa League (欧联杯) - ID: 7511, API ID: 5
3. UEFA Conference League (欧协联) - ID: 7512, API ID: 848
"""

import sqlite3
import json
import ssl
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

API_KEY = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"
BASE_URL = "https://apiv3.apifootball.com"

# 欧战赛事配置
EUROPEAN_COMPETITIONS = {
    3: ('UEFA Champions League', 10),
    4: ('UEFA Europa League', 7511),
    683: ('UEFA Conference League', 7512),
}


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_api(action: str, params: dict) -> dict:
    """调用API"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        url = f"{BASE_URL}?action={action}&{param_str}&APIkey={API_KEY}"

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"    API error: {e}")
        return None


def get_or_create_team(conn, team_name: str, country: str = None) -> int:
    """获取或创建球队"""
    cursor = conn.cursor()
    team_name = team_name.strip()

    try:
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ? OR name_en LIKE ?',
                      (team_name, f'%{team_name}%'))
        row = cursor.fetchone()
        if row:
            return row[0]

        cursor.execute('''
            INSERT INTO teams (name_en, created_at, updated_at)
            VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (team_name,))
        conn.commit()
        return cursor.lastrowid
    except:
        conn.rollback()
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
        row = cursor.fetchone()
        return row[0] if row else None


def update_from_api(api_id: int, name: str, db_id: int, from_date: str, to_date: str):
    """从API更新数据"""
    print(f"\nUpdating {name} from API...")

    conn = get_db()
    cursor = conn.cursor()

    fixtures = fetch_api("get_events", {
        "league_id": api_id,
        "from": from_date,
        "to": to_date
    })

    if not fixtures or not isinstance(fixtures, list):
        print(f"  No data received")
        conn.close()
        return 0

    print(f"  Got {len(fixtures)} matches")

    added = 0
    for fixture in fixtures:
        match_date = fixture.get('match_date', '')
        home_team = fixture.get('match_hometeam_name', '')
        away_team = fixture.get('match_awayteam_name', '')
        home_goals = fixture.get('match_hometeam_score')
        away_goals = fixture.get('match_awayteam_score')
        match_time = fixture.get('match_time', '')

        if not match_date or not home_team or not away_team:
            continue

        home_team_id = get_or_create_team(conn, home_team)
        away_team_id = get_or_create_team(conn, away_team)

        if not home_team_id or not away_team_id:
            continue

        cursor.execute('''
            SELECT rowid FROM matches
            WHERE match_date = ? AND home_team_id = ? AND away_team_id = ? AND league_id = ?
        ''', (match_date, home_team_id, away_team_id, db_id))

        try:
            hg = int(home_goals) if home_goals else None
            ag = int(away_goals) if away_goals else None
        except:
            hg = None
            ag = None

        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO matches (
                    league_id, match_date, match_time,
                    home_team_id, away_team_id,
                    home_goals, away_goals,
                    home_xg, away_xg,
                    source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'api_import', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (db_id, match_date, match_time, home_team_id, away_team_id,
                  hg, ag, hg, ag))
            added += 1

    conn.commit()
    conn.close()
    print(f"  Added {added} matches")
    return added


def show_stats():
    """显示统计"""
    print("\n" + "=" * 60)
    print("UEFA European Competitions Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    for db_id, name in [(10, 'UEFA Champions League'), (7511, 'UEFA Europa League'),
                        (7512, 'UEFA Conference League')]:
        cursor.execute('SELECT COUNT(*), MIN(match_date), MAX(match_date) FROM matches WHERE league_id = ?', (db_id,))
        r = cursor.fetchone()
        print(f"\n{name}:")
        print(f"  Matches: {r[0]}")
        if r[1]:
            print(f"  Range: {r[1]} ~ {r[2]}")
        else:
            print(f"  Range: No data")

    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("UEFA European Competitions Data Collection")
    print("=" * 60)

    # Update from API (2020-2026)
    for api_id, (name, db_id) in EUROPEAN_COMPETITIONS.items():
        update_from_api(api_id, name, db_id, "2020-01-01", "2026-12-31")

    # Show statistics
    show_stats()

    print("\nDone!")