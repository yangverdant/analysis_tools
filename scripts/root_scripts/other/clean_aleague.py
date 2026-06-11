"""
清理澳超错误数据并重新采集
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

ALEAGUE_API_ID = 49

# 澳超球队列表
ALEAGUE_TEAMS = [
    'Adelaide United', 'Brisbane Roar', 'Central Coast Mariners',
    'Melbourne City', 'Melbourne Victory', 'Newcastle Jets',
    'Perth Glory', 'Sydney FC', 'Wellington Phoenix',
    'Western Sydney Wanderers', 'Western United', 'Macarthur FC',
    'Auckland FC'
]


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


def clean_aleague_data():
    """清理澳超错误数据 - 只保留真正的澳超球队比赛"""
    print("=" * 60)
    print("Cleaning A-League data...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 获取所有澳超球队ID
    placeholders = ','.join(['?' for _ in ALEAGUE_TEAMS])
    cursor.execute(f'''
        SELECT team_id FROM teams
        WHERE name_en IN ({placeholders})
    ''', ALEAGUE_TEAMS)

    team_ids = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(team_ids)} A-League teams")

    if len(team_ids) < 10:
        # 如果找到的球队太少，添加更多可能的名称
        cursor.execute('''
            SELECT team_id, name_en FROM teams
            WHERE name_en LIKE '%United%' OR name_en LIKE '%FC%'
            OR name_en LIKE '%Roar%' OR name_en LIKE '%Mariners%'
            OR name_en LIKE '%Victory%' OR name_en LIKE '%Glory%'
            OR name_en LIKE '%Wanderers%' OR name_en LIKE '%Phoenix%'
        ''')
        for row in cursor.fetchall():
            if row[1] in ['Adelaide United', 'Brisbane Roar', 'Central Coast Mariners',
                          'Melbourne City FC', 'Melbourne City', 'Melbourne Victory',
                          'Newcastle United Jets', 'Newcastle Jets', 'Perth Glory',
                          'Sydney FC', 'Wellington Phoenix', 'Western Sydney Wanderers',
                          'Western United', 'Macarthur FC', 'Auckland FC']:
                if row[0] not in team_ids:
                    team_ids.append(row[0])

    print(f"Total A-League team IDs: {len(team_ids)}")

    # 统计删除前的比赛数
    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = 1')
    before = cursor.fetchone()[0]
    print(f"Matches before cleaning: {before}")

    # 删除非澳超球队的比赛
    if team_ids:
        placeholders = ','.join(['?' for _ in team_ids])
        cursor.execute(f'''
            DELETE FROM matches
            WHERE league_id = 1
            AND (
                home_team_id NOT IN ({placeholders})
                OR away_team_id NOT IN ({placeholders})
            )
        ''', team_ids + team_ids)
        deleted = cursor.rowcount
        conn.commit()
        print(f"Deleted {deleted} invalid matches")

    # 统计删除后的比赛数
    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = 1')
    after = cursor.fetchone()[0]
    print(f"Matches after cleaning: {after}")

    conn.close()
    return after


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


def update_aleague_from_api():
    """从API重新采集澳超数据"""
    print("\n" + "=" * 60)
    print("Fetching A-League from API (ID: 49)...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    fixtures = fetch_api("get_events", {
        "league_id": ALEAGUE_API_ID,
        "from": "2020-01-01",
        "to": "2026-12-31"
    })

    if not fixtures or not isinstance(fixtures, list):
        print("  No data received")
        conn.close()
        return 0

    print(f"  Got {len(fixtures)} matches from API")

    # 显示前5场比赛检查
    print("\n  Sample matches from API:")
    for i, f in enumerate(fixtures[:5]):
        print(f"    {f.get('match_date')}: {f.get('match_hometeam_name')} vs {f.get('match_awayteam_name')}")

    added = 0
    for fixture in fixtures:
        match_date = fixture.get('match_date', '')
        home_team = fixture.get('match_hometeam_name', '')
        away_team = fixture.get('match_awayteam_name', '')

        if not match_date or not home_team or not away_team:
            continue

        # 只接受真正的澳超球队
        is_aleague = False
        for team in ALEAGUE_TEAMS:
            if team.lower() in home_team.lower() or team.lower() in away_team.lower():
                is_aleague = True
                break

        if not is_aleague:
            continue

        home_team_id = get_or_create_team(conn, home_team)
        away_team_id = get_or_create_team(conn, away_team)

        if not home_team_id or not away_team_id:
            continue

        home_goals = fixture.get('match_hometeam_score')
        away_goals = fixture.get('match_awayteam_score')
        match_time = fixture.get('match_time', '')

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
    print("Final A-League Check")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT m.match_date, h.name_en, a.name_en, m.home_goals, m.away_goals
        FROM matches m
        JOIN teams h ON m.home_team_id = h.team_id
        JOIN teams a ON m.away_team_id = a.team_id
        WHERE m.league_id = 1
        ORDER BY m.match_date DESC
        LIMIT 15
    ''')

    print("\nRecent A-League matches:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} vs {row[2]} ({row[3]}-{row[4]})")

    cursor.execute('SELECT COUNT(*), MIN(match_date), MAX(match_date) FROM matches WHERE league_id = 1')
    r = cursor.fetchone()
    print(f"\nTotal: {r[0]} matches")
    print(f"Range: {r[1]} to {r[2]}")

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = 1 AND match_date >= "2026-05-23"')
    future = cursor.fetchone()[0]
    print(f"Future matches: {future}")

    conn.close()


if __name__ == "__main__":
    # 1. 清理错误数据
    clean_aleague_data()

    # 2. 从API重新采集
    update_aleague_from_api()

    # 3. 最终检查
    final_check()

    print("\nDone!")