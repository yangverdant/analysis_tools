"""
采集意大利联赛球员数据

数据源: API-Football
"""

import sqlite3
import json
import ssl
import urllib.request
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

API_KEY = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"
BASE_URL = "https://apiv3.apifootball.com"

# API联赛ID
SERIE_A_API_ID = 135
SERIE_B_API_ID = 136


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
        print(f"  API error: {e}")
        return None


def get_or_create_player(conn, player_data: dict) -> int:
    """获取或创建球员"""
    cursor = conn.cursor()
    player_name = player_data.get('player_name', '')

    if not player_name:
        return None

    try:
        cursor.execute('SELECT player_id FROM players WHERE name_en = ?', (player_name,))
        row = cursor.fetchone()
        if row:
            return row[0]

        cursor.execute('''
            INSERT INTO players (name_en, position_main, nationality, created_at, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (player_name, player_data.get('player_type', ''), player_data.get('player_country', '')))
        conn.commit()
        return cursor.lastrowid
    except:
        conn.rollback()
        return None


def get_team_id(conn, team_name: str) -> int:
    """查找球队ID"""
    cursor = conn.cursor()
    cursor.execute('SELECT team_id FROM teams WHERE name_en = ? OR name_en LIKE ?',
                  (team_name, f'%{team_name}%'))
    row = cursor.fetchone()
    return row[0] if row else None


def collect_players(api_id: int, league_name: str):
    """采集球员数据"""
    print(f"\nCollecting {league_name} players...")

    conn = get_db()

    teams = fetch_api("get_teams", {"league_id": api_id})

    if not teams or not isinstance(teams, list):
        print("  Failed to get teams")
        conn.close()
        return 0

    print(f"  Got {len(teams)} teams")

    total_players = 0

    for team in teams:
        team_name = team.get('team_name', '')
        players = team.get('players', [])

        if not players:
            continue

        team_id = get_team_id(conn, team_name)
        try:
            print(f"  Team: {len(players)} players")
        except:
            print(f"  Team: {len(players)} players")

        for player in players:
            player_id = get_or_create_player(conn, player)
            if player_id:
                total_players += 1

        time.sleep(0.3)

    conn.close()
    print(f"  Total: {total_players} players")
    return total_players


def show_stats():
    """显示统计"""
    print("\n" + "=" * 60)
    print("Italian Players Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM players')
    total = cursor.fetchone()[0]
    print(f"Total players in database: {total}")

    # 位置分布
    cursor.execute('''
        SELECT position_main, COUNT(*) FROM players
        WHERE position_main IS NOT NULL AND position_main != ''
        GROUP BY position_main ORDER BY COUNT(*) DESC
    ''')
    print("\nBy position:")
    for r in cursor.fetchall():
        print(f"  {r[0]}: {r[1]}")

    # 国籍分布
    cursor.execute('''
        SELECT nationality, COUNT(*) FROM players
        WHERE nationality IS NOT NULL AND nationality != ''
        GROUP BY nationality ORDER BY COUNT(*) DESC
        LIMIT 10
    ''')
    print("\nBy nationality (Top 10):")
    for r in cursor.fetchall():
        print(f"  {r[0]}: {r[1]}")

    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Italian Player Data Collection")
    print("=" * 60)

    collect_players(SERIE_A_API_ID, "Serie A")
    collect_players(SERIE_B_API_ID, "Serie B")

    show_stats()
    print("\nDone!")