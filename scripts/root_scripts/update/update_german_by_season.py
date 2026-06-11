"""
分段更新德国联赛数据（避免API超时）
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

# API联赛ID
LEAGUES = {
    175: ('Bundesliga', 7),
    171: ('2. Bundesliga', 8),
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


def get_or_create_team(conn, team_name: str, country: str = 'Germany') -> int:
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
            INSERT INTO teams (name_en, country, created_at, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (team_name, country))
        conn.commit()
        return cursor.lastrowid
    except:
        conn.rollback()
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
        row = cursor.fetchone()
        return row[0] if row else None


def update_league_season(api_id: int, name: str, db_id: int, season: str):
    """更新单个赛季"""
    from_date = f"{season.split('-')[0]}-08-01"
    to_date = f"{season.split('-')[1]}-07-31"

    print(f"  {season} ({from_date} ~ {to_date})")

    conn = get_db()
    cursor = conn.cursor()

    fixtures = fetch_api("get_events", {
        "league_id": api_id,
        "from": from_date,
        "to": to_date
    })

    if not fixtures or not isinstance(fixtures, list):
        print(f"    No data")
        conn.close()
        return 0

    print(f"    Got {len(fixtures)} matches")

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
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (db_id, match_date, match_time, home_team_id, away_team_id,
                  hg, ag, hg, ag))
            added += 1

    conn.commit()
    conn.close()
    print(f"    Added {added}")
    return added


def show_stats():
    """显示统计"""
    print("\n" + "=" * 60)
    print("German Leagues Data Coverage (2020+)")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    for db_id, name in [(7, 'Bundesliga'), (8, '2. Bundesliga'), (7402, '3. Liga')]:
        cursor.execute('''
            SELECT strftime('%Y', match_date) as year, COUNT(*)
            FROM matches WHERE league_id = ? AND match_date >= '2020-01-01'
            GROUP BY year ORDER BY year
        ''', (db_id,))
        print(f"\n{name}:")
        for r in cursor.fetchall():
            print(f"  {r[0]}: {r[1]} matches")

    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Updating German Leagues (Season by Season)")
    print("=" * 60)

    seasons = ['2020-21', '2021-22', '2022-23', '2023-24', '2024-25', '2025-26']

    for api_id, (name, db_id) in LEAGUES.items():
        print(f"\n{name}:")
        total = 0
        for season in seasons:
            total += update_league_season(api_id, name, db_id, season)
        print(f"  Total added: {total}")

    show_stats()
    print("\nDone!")