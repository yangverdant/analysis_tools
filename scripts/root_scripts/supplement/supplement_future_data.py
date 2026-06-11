"""
补充各联赛未来半年数据 (2026-05-23 至 2026-11-23)
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

# 需要补充未来数据的联赛
LEAGUES_TO_UPDATE = {
    # 德国
    79: ('2. Bundesliga', 22),
    80: ('3. Liga', 23),
    81: ('DFB-Pokal', 7484),
    # 意大利
    136: ('Serie B', 18),
    137: ('Coppa Italia', 7482),
    138: ('Supercoppa', 7483),
    # 法国
    61: ('Ligue 1', 24),
    62: ('Ligue 2', 25),
    60: ('Coupe de France', 7486),
    63: ('Trophee des Champions', 7488),
    # 比利时
    144: ('Jupiler Pro League', 26),
    143: ('Belgian Cup', 7489),
    146: ('Belgian Super Cup', 7490),
    # 澳大利亚
    149: ('A-League', 1),
    # 欧战
    4: ('UEFA Europa League', 7511),
}


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
        print(f"    API error: {e}")
        return None


def get_or_create_team(conn, team_name: str) -> int:
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


def update_from_api(api_id: int, name: str, db_id: int):
    """从API更新未来数据"""
    print(f"\nUpdating {name} (future data)...")

    conn = get_db()
    cursor = conn.cursor()

    fixtures = fetch_api("get_events", {
        "league_id": api_id,
        "from": "2026-05-23",
        "to": "2026-11-23"
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
    print(f"  Added {added} new matches")
    return added


def show_final_stats():
    """显示最终统计"""
    print("\n" + "=" * 60)
    print("Final Statistics - Future Data")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    leagues = [
        (22, '2. Bundesliga'),
        (23, '3. Liga'),
        (7484, 'DFB-Pokal'),
        (18, 'Serie B'),
        (7482, 'Coppa Italia'),
        (7483, 'Supercoppa'),
        (24, 'Ligue 1'),
        (25, 'Ligue 2'),
        (7486, 'Coupe de France'),
        (7488, 'Trophee des Champions'),
        (26, 'Jupiler Pro League'),
        (7489, 'Belgian Cup'),
        (7490, 'Belgian Super Cup'),
        (1, 'A-League'),
        (7511, 'UEFA Europa League'),
    ]

    for league_id, name in leagues:
        cursor.execute('''
            SELECT COUNT(*) FROM matches
            WHERE league_id = ? AND match_date >= '2026-05-23'
        ''', (league_id,))
        future_count = cursor.fetchone()[0]

        cursor.execute('SELECT MAX(match_date) FROM matches WHERE league_id = ?', (league_id,))
        max_date = cursor.fetchone()[0]

        status = "HAS FUTURE" if future_count > 0 else "NO FUTURE"
        print(f"{name}: {status} - {future_count} matches (latest: {max_date})")

    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Supplementing Future Data (2026-05-23 to 2026-11-23)")
    print("=" * 60)

    for api_id, (name, db_id) in LEAGUES_TO_UPDATE.items():
        update_from_api(api_id, name, db_id)

    show_final_stats()
    print("\nDone!")