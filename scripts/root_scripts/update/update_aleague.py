"""
检查和补充澳超季后赛数据
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


def check_aleague_data():
    """检查澳超数据"""
    print("=" * 60)
    print("A-League Data Check")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 检查澳超比赛数据
    cursor.execute('''
        SELECT substr(match_date, 1, 7) as month, COUNT(*)
        FROM matches
        WHERE league_id = 1
        GROUP BY month
        ORDER BY month DESC
        LIMIT 20
    ''')

    print("\nRecent A-League matches by month:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} matches")

    # 检查最新比赛日期
    cursor.execute('SELECT MAX(match_date) FROM matches WHERE league_id = 1')
    latest = cursor.fetchone()[0]
    print(f"\nLatest match date: {latest}")

    # 检查未来比赛
    cursor.execute('''
        SELECT COUNT(*) FROM matches
        WHERE league_id = 1 AND match_date >= '2026-05-23'
    ''')
    future = cursor.fetchone()[0]
    print(f"Future matches: {future}")

    conn.close()


def update_aleague_from_api():
    """从API更新澳超数据"""
    print("\n" + "=" * 60)
    print("Updating A-League from API (2025-2026)...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 澳超API ID是149
    fixtures = fetch_api("get_events", {
        "league_id": 149,
        "from": "2025-01-01",
        "to": "2026-12-31"
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

        # 获取或创建球队
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ? OR name_en LIKE ?',
                      (home_team, f'%{home_team}%'))
        row = cursor.fetchone()
        if row:
            home_team_id = row[0]
        else:
            cursor.execute('''
                INSERT INTO teams (name_en, created_at, updated_at)
                VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (home_team,))
            conn.commit()
            home_team_id = cursor.lastrowid

        cursor.execute('SELECT team_id FROM teams WHERE name_en = ? OR name_en LIKE ?',
                      (away_team, f'%{away_team}%'))
        row = cursor.fetchone()
        if row:
            away_team_id = row[0]
        else:
            cursor.execute('''
                INSERT INTO teams (name_en, created_at, updated_at)
                VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (away_team,))
            conn.commit()
            away_team_id = cursor.lastrowid

        # 检查比赛是否存在
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
    print("Final A-League Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*), MIN(match_date), MAX(match_date) FROM matches WHERE league_id = 1')
    r = cursor.fetchone()
    print(f"Total matches: {r[0]}")
    print(f"Date range: {r[1]} to {r[2]}")

    cursor.execute('''
        SELECT COUNT(*) FROM matches
        WHERE league_id = 1 AND match_date >= '2026-05-23'
    ''')
    future = cursor.fetchone()[0]
    print(f"Future matches (after 2026-05-23): {future}")

    # 按月份统计最近的数据
    cursor.execute('''
        SELECT substr(match_date, 1, 7) as month, COUNT(*)
        FROM matches
        WHERE league_id = 1
        GROUP BY month
        ORDER BY month DESC
        LIMIT 10
    ''')
    print("\nBy month (recent):")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} matches")

    conn.close()


if __name__ == "__main__":
    # 先检查现有数据
    check_aleague_data()

    # 从API更新
    update_aleague_from_api()

    # 最终检查
    final_check()

    print("\nDone!")