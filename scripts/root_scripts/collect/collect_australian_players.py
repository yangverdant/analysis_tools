"""
采集澳大利亚联赛球员数据
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

ALEAGUE_API_ID = 149


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
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


def get_or_create_player(conn, player_data: dict) -> int:
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


def collect_players(api_id: int, league_name: str):
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
        players = team.get('players', [])

        if not players:
            continue

        print(f"  Team: {len(players)} players")

        for player in players:
            player_id = get_or_create_player(conn, player)
            if player_id:
                total_players += 1

        time.sleep(0.3)

    conn.close()
    print(f"  Total: {total_players} players")
    return total_players


if __name__ == "__main__":
    print("=" * 60)
    print("Australian Player Data Collection")
    print("=" * 60)

    collect_players(ALEAGUE_API_ID, "A-League Men")

    print("\nDone!")