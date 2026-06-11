"""
采集德丙联赛球员数据

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

# 德丙在API-Football中的联赛ID
BUNDESLIGA3_API_ID = 184

# 数据库联赛ID
BUNDESLIGA3_DB_ID = 7402


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
        print(f"API error: {e}")
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
        ''', (
            player_name,
            player_data.get('player_type', ''),
            player_data.get('player_country', '')
        ))
        conn.commit()
        return cursor.lastrowid
    except:
        conn.rollback()
        return None


def get_team_id_by_name(conn, team_name: str) -> int:
    """根据名称查找球队ID"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT team_id FROM teams
        WHERE name_en = ? OR name_en LIKE ? OR name_cn = ?
    ''', (team_name, f'%{team_name}%', team_name))
    row = cursor.fetchone()
    return row[0] if row else None


def collect_team_squads(league_api_id: int, league_db_id: int):
    """采集球队阵容"""
    print(f"\nCollecting teams for league {league_db_id}...")

    conn = get_db()
    cursor = conn.cursor()

    teams = fetch_api("get_teams", {"league_id": league_api_id})

    if not teams or not isinstance(teams, list):
        print("  Failed to get teams")
        conn.close()
        return 0

    print(f"  Found {len(teams)} teams")

    total_players = 0

    for team in teams:
        team_name = team.get('team_name', '')
        players = team.get('players', [])

        if not players:
            continue

        team_id = get_team_id_by_name(conn, team_name)
        print(f"  Team {team_id}: {len(players)} players")

        for player in players:
            player_id = get_or_create_player(conn, player)
            if player_id:
                total_players += 1

        time.sleep(0.3)

    conn.close()
    print(f"  Total players: {total_players}")
    return total_players


def show_stats():
    """显示统计"""
    print("\n" + "=" * 60)
    print("3. Liga Player Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM players')
    total = cursor.fetchone()[0]
    print(f"Total players: {total}")

    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("3. Liga Player Data Collection")
    print("=" * 60)

    collect_team_squads(BUNDESLIGA3_API_ID, BUNDESLIGA3_DB_ID)
    show_stats()
    print("\nDone!")