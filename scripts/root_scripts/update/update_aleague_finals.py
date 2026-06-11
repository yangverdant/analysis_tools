"""
补充澳超2025-26赛季数据（包括季后赛）
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


def get_db():
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_api(action: str, params: dict) -> dict:
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
        print(f"  API error: {e}")
        return None


def get_or_create_team(conn, team_name: str, country: str = 'Australia') -> int:
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


def update_aleague():
    """更新澳超2025-26赛季数据"""
    print("=" * 60)
    print("Updating A-League 2025-26 Season (including Finals)")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 获取2025年5月季后赛 + 2025-26赛季
    fixtures = fetch_api("get_events", {
        "league_id": 49,
        "from": "2025-05-01",
        "to": "2026-05-31"
    })

    if not fixtures or not isinstance(fixtures, list):
        print("  No data received")
        conn.close()
        return 0

    print(f"  Got {len(fixtures)} matches from API")

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
            WHERE match_date = ? AND home_team_id = ? AND away_team_id = ? AND league_id = 1
        ''', (match_date, home_team_id, away_team_id))

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
            ''', (1, match_date, match_time, home_team_id, away_team_id,
                  hg, ag, hg, ag))
            added += 1

    conn.commit()
    conn.close()
    print(f"  Added {added} new matches")
    return added


def final_check():
    """最终检查"""
    print("\n" + "=" * 60)
    print("A-League Final Check")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 显示最近的比赛（包括季后赛）
    cursor.execute('''
        SELECT m.match_date, h.name_en, a.name_en, m.home_goals, m.away_goals
        FROM matches m
        JOIN teams h ON m.home_team_id = h.team_id
        JOIN teams a ON m.away_team_id = a.team_id
        WHERE m.league_id = 1
        ORDER BY m.match_date DESC
        LIMIT 20
    ''')

    print("\nRecent A-League matches (including Finals):")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} vs {row[2]} ({row[3]}-{row[4]})")

    cursor.execute('SELECT COUNT(*), MIN(match_date), MAX(match_date) FROM matches WHERE league_id = 1')
    r = cursor.fetchone()
    print(f"\nTotal: {r[0]} matches")
    print(f"Range: {r[1]} to {r[2]}")

    # 未来比赛
    cursor.execute('''
        SELECT COUNT(*) FROM matches
        WHERE league_id = 1 AND match_date >= '2026-05-23'
    ''')
    future = cursor.fetchone()[0]
    print(f"Future matches (after 2026-05-23): {future}")

    # 按月份统计
    cursor.execute('''
        SELECT substr(match_date, 1, 7) as month, COUNT(*)
        FROM matches
        WHERE league_id = 1 AND match_date >= '2025-05-01'
        GROUP BY month
        ORDER BY month
    ''')
    print("\nBy month (2025-26 season):")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} matches")

    conn.close()


if __name__ == "__main__":
    update_aleague()
    final_check()
    print("\nDone!")