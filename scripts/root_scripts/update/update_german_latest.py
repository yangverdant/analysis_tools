"""
更新德国联赛最新数据

使用API-Football获取2024-2026最新比赛数据
"""

import sqlite3
import json
import ssl
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

API_KEY = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"
BASE_URL = "https://apiv3.apifootball.com"

# API联赛ID
LEAGUES = {
    175: ('Bundesliga', 7),
    171: ('2. Bundesliga', 8),
    184: ('3. Liga', 7402),
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
        with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"  API error: {e}")
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


def update_league(api_id: int, name: str, db_id: int, from_date: str, to_date: str):
    """更新联赛数据"""
    print(f"\nUpdating {name} ({from_date} ~ {to_date})...")

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

    print(f"  Got {len(fixtures)} matches from API")

    added = 0
    updated = 0
    for fixture in fixtures:
        match_date = fixture.get('match_date', '')
        home_team = fixture.get('match_hometeam_name', '')
        away_team = fixture.get('match_awayteam_name', '')
        home_goals = fixture.get('match_hometeam_score')
        away_goals = fixture.get('match_awayteam_score')
        match_time = fixture.get('match_time', '')
        status = fixture.get('match_status', '')

        if not match_date or not home_team or not away_team:
            continue

        home_team_id = get_or_create_team(conn, home_team)
        away_team_id = get_or_create_team(conn, away_team)

        if not home_team_id or not away_team_id:
            continue

        # 检查是否已存在
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

        if cursor.fetchone():
            # 更新现有记录
            if hg is not None and ag is not None:
                cursor.execute('''
                    UPDATE matches SET
                        home_goals = ?, away_goals = ?,
                        home_xg = ?, away_xg = ?,
                        status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE match_date = ? AND home_team_id = ? AND away_team_id = ? AND league_id = ?
                ''', (hg, ag, hg, ag, status, match_date, home_team_id, away_team_id, db_id))
                updated += 1
        else:
            # 插入新记录
            cursor.execute('''
                INSERT INTO matches (
                    league_id, match_date, match_time,
                    home_team_id, away_team_id,
                    home_goals, away_goals,
                    home_xg, away_xg,
                    status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (db_id, match_date, match_time, home_team_id, away_team_id,
                  hg, ag, hg, ag, status))
            added += 1

    conn.commit()
    conn.close()
    print(f"  Added {added} new, updated {updated} existing matches")
    return added


def show_latest():
    """显示最新数据日期"""
    print("\n" + "=" * 60)
    print("German Leagues - Latest Data")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    for db_id, name in [(7, 'Bundesliga'), (8, '2. Bundesliga'), (7402, '3. Liga'),
                        (7482, 'DFB-Pokal'), (7483, 'DFL-Supercup')]:
        cursor.execute('SELECT MAX(match_date), COUNT(*) FROM matches WHERE league_id = ?', (db_id,))
        r = cursor.fetchone()
        print(f"{name}: {r[0]} ({r[1]} matches)")

    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Updating German Leagues to Latest")
    print("=" * 60)

    today = datetime.now()

    # 更新德甲和德乙 2020-2026
    for api_id, (name, db_id) in LEAGUES.items():
        from_date = "2020-08-01"
        to_date = today.strftime("%Y-%m-%d")
        update_league(api_id, name, db_id, from_date, to_date)

    show_latest()
    print("\nDone!")