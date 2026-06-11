"""
采集德甲联赛球员数据

数据源: API-Football (通过SSL绕过)
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

# 德甲在API-Football中的联赛ID
BUNDESLIGA_API_ID = 175


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
        print(f"API错误: {e}")
        return None


def get_or_create_team(conn, team_name: str, team_key: str = None) -> int:
    """获取或创建球队"""
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT team_id FROM teams WHERE name_en = ? OR name_en LIKE ?
        ''', (team_name, f'%{team_name}%'))
        row = cursor.fetchone()
        if row:
            return row[0]

        cursor.execute('''
            INSERT INTO teams (name_en, country, created_at, updated_at)
            VALUES (?, 'Germany', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (team_name,))
        conn.commit()
        return cursor.lastrowid
    except:
        conn.rollback()
        # 再次查找
        cursor.execute('''
            SELECT team_id FROM teams WHERE name_en = ?
        ''', (team_name,))
        return cursor.fetchone()[0] if cursor.fetchone() else None


def get_or_create_player(conn, player_data: dict) -> int:
    """获取或创建球员"""
    cursor = conn.cursor()

    player_name = player_data.get('player_name', '')
    if not player_name:
        return None

    try:
        # 检查是否已存在
        cursor.execute('''
            SELECT player_id FROM players WHERE name_en = ?
        ''', (player_name,))
        row = cursor.fetchone()
        if row:
            return row[0]

        # 创建新球员
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


def collect_bundesliga_players():
    """采集德甲球员数据"""
    print("=" * 60)
    print("采集德甲球员数据")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 检查players表结构
    cursor.execute("PRAGMA table_info(players)")
    columns = [r[1] for r in cursor.fetchall()]
    print(f"球员表字段: {columns}")

    # 获取德甲球队
    print("\n1. 获取德甲球队...")
    teams_data = fetch_api("get_teams", {"league_id": BUNDESLIGA_API_ID})

    if not teams_data or not isinstance(teams_data, list):
        print("获取球队失败")
        conn.close()
        return

    print(f"获取到 {len(teams_data)} 支球队")

    total_players = 0
    total_teams = 0

    for team in teams_data:
        team_name = team.get('team_name', '')
        team_key = team.get('team_key', '')
        team_founded = team.get('team_founded', '')
        team_badge = team.get('team_badge', '')
        venue = team.get('venue', {})

        # 更新球队信息
        team_id = get_or_create_team(conn, team_name, team_key)

        # 更新球队详细信息
        if venue:
            venue_name = venue.get('venue_name', '')
            venue_capacity = venue.get('venue_capacity', '')
            venue_city = venue.get('venue_city', '')

            try:
                cursor.execute('''
                    UPDATE teams SET
                        stadium = COALESCE(?, stadium),
                        stadium_capacity = COALESCE(?, stadium_capacity),
                        founded = COALESCE(?, founded),
                        logo_url = COALESCE(?, logo_url)
                    WHERE team_id = ?
                ''', (venue_name or None, int(venue_capacity) if venue_capacity else None,
                      int(team_founded) if team_founded else None, team_badge or None, team_id))
                conn.commit()
            except:
                conn.rollback()

        # 处理球员
        players = team.get('players', [])
        if players:
            try:
                print(f"  {team_id}: {len(players)} players")
            except:
                print(f"  team_id={team_id}: {len(players)} players")
            total_teams += 1

            for player in players:
                player_id = get_or_create_player(conn, player)
                if player_id:
                    total_players += 1

        # 避免请求过快
        time.sleep(0.5)

    conn.commit()
    conn.close()

    print(f"\n采集完成:")
    print(f"  球队: {total_teams} 支")
    print(f"  球员: {total_players} 名")


def collect_bundesliga_fixtures():
    """采集德甲比赛详情"""
    print("\n" + "=" * 60)
    print("采集德甲比赛详情")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 获取当前赛季比赛
    print("获取2024-2025赛季比赛...")
    fixtures = fetch_api("get_events", {
        "league_id": BUNDESLIGA_API_ID,
        "from": "2024-08-01",
        "to": "2025-05-31"
    })

    if not fixtures or not isinstance(fixtures, list):
        print("获取比赛失败")
        conn.close()
        return

    print(f"获取到 {len(fixtures)} 场比赛")

    updated = 0
    for fixture in fixtures:
        match_date = fixture.get('match_date', '')
        home_team = fixture.get('match_hometeam_name', '')
        away_team = fixture.get('match_awayteam_name', '')

        if not match_date or not home_team or not away_team:
            continue

        # 查找数据库中的比赛
        cursor.execute('''
            SELECT m.match_id FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.match_date = ?
            AND ht.name_en LIKE ?
            AND at.name_en LIKE ?
            AND m.league_id = 7
        ''', (match_date, f'%{home_team}%', f'%{away_team}%'))

        match = cursor.fetchone()
        if match:
            match_id = match[0]

            # 更新比赛详情
            referee = fixture.get('match_referee', '')

            if referee:
                cursor.execute('''
                    UPDATE matches SET
                        referee = COALESCE(?, referee)
                    WHERE match_id = ? AND (referee IS NULL OR referee = '')
                ''', (referee, match_id))
                updated += 1

    conn.commit()
    conn.close()
    print(f"更新 {updated} 场比赛")


def show_final_stats():
    """显示最终统计"""
    print("\n" + "=" * 60)
    print("德甲数据统计")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 球员统计
    cursor.execute('SELECT COUNT(*) FROM players')
    total_players = cursor.fetchone()[0]
    print(f"球员总数: {total_players}")

    # 球队统计
    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN stadium IS NOT NULL THEN 1 ELSE 0 END) as has_stadium,
            SUM(CASE WHEN logo_url IS NOT NULL THEN 1 ELSE 0 END) as has_logo
        FROM teams
        WHERE team_id IN (
            SELECT DISTINCT home_team_id FROM matches WHERE league_id = 7
            UNION
            SELECT DISTINCT away_team_id FROM matches WHERE league_id = 7
        )
    ''')
    r = cursor.fetchone()
    print(f"\n球队统计:")
    print(f"  总数: {r[0]}")
    print(f"  有球场: {r[1]}")
    print(f"  有Logo: {r[3]}")

    conn.close()


if __name__ == "__main__":
    # 1. 采集球员数据
    collect_bundesliga_players()

    # 2. 采集比赛详情
    collect_bundesliga_fixtures()

    # 3. 显示统计
    show_final_stats()

    print("\n德甲数据采集完成！")
