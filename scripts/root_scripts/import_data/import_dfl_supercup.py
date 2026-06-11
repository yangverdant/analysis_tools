"""
采集德国超级杯 (DFL-Supercup) 数据

数据源: API-Football
联赛ID: 7483
API联赛ID: 176
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

# DFL-Supercup API ID
DFL_SUPERCUP_API_ID = 176
DFL_SUPERCUP_DB_ID = 7483


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


def get_or_create_team(conn, team_name: str, country: str = 'Germany') -> int:
    """获取或创建球队"""
    cursor = conn.cursor()
    team_name = team_name.strip()

    try:
        cursor.execute('''
            SELECT team_id FROM teams WHERE name_en = ? OR name_en LIKE ?
        ''', (team_name, f'%{team_name}%'))
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


def import_dfl_supercup():
    """导入DFL-Supercup数据"""
    print("=" * 60)
    print("Importing DFL-Supercup (German Super Cup) data...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 从API获取数据
    fixtures = fetch_api("get_events", {
        "league_id": DFL_SUPERCUP_API_ID,
        "from": "2010-01-01",
        "to": "2026-12-31"
    })

    if not fixtures or not isinstance(fixtures, list):
        print("  Failed to get data from API")
        conn.close()
        return 0

    print(f"  Found {len(fixtures)} matches from API")

    imported = 0
    for fixture in fixtures:
        match_date = fixture.get('match_date', '')
        home_team = fixture.get('match_hometeam_name', '')
        away_team = fixture.get('match_awayteam_name', '')
        home_goals = fixture.get('match_hometeam_score', '')
        away_goals = fixture.get('match_awayteam_score', '')
        match_time = fixture.get('match_time', '')

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
        ''', (match_date, home_team_id, away_team_id, DFL_SUPERCUP_DB_ID))

        if cursor.fetchone():
            continue

        # 解析比分
        try:
            hg = int(home_goals) if home_goals else None
            ag = int(away_goals) if away_goals else None
        except:
            hg = None
            ag = None

        # 插入比赛
        cursor.execute('''
            INSERT INTO matches (
                league_id, match_date, match_time,
                home_team_id, away_team_id,
                home_goals, away_goals,
                home_xg, away_xg,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (
            DFL_SUPERCUP_DB_ID, match_date, match_time,
            home_team_id, away_team_id,
            hg, ag, hg, ag
        ))

        imported += 1

    conn.commit()
    conn.close()
    print(f"  Imported {imported} matches")
    return imported


def show_stats():
    """显示统计"""
    print("\n" + "=" * 60)
    print("DFL-Supercup Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (DFL_SUPERCUP_DB_ID,))
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(DISTINCT team_id) FROM (
            SELECT home_team_id as team_id FROM matches WHERE league_id = ?
            UNION
            SELECT away_team_id FROM matches WHERE league_id = ?
        )
    ''', (DFL_SUPERCUP_DB_ID, DFL_SUPERCUP_DB_ID))
    teams = cursor.fetchone()[0]

    print(f"Matches: {total}")
    print(f"Teams: {teams}")

    conn.close()


if __name__ == "__main__":
    import_dfl_supercup()
    show_stats()
    print("\nDone!")