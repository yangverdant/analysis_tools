"""
采集德甲球员年度统计数据

数据源: API-Football
内容包括:
1. 球员基本信息
2. 球员赛季统计
3. 球员比赛统计
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

# API-Football联赛ID
BUNDESLIGA_API_ID = 175  # 德甲
BUNDESLIGA2_API_ID = 171  # 德乙

# 数据库联赛ID
BUNDESLIGA_DB_ID = 7
BUNDESLIGA2_DB_ID = 8


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

        # 创建球员
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


def get_match_id(conn, match_date: str, home_team: str, away_team: str, league_id: int) -> int:
    """查找比赛ID"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.match_id FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        WHERE m.match_date = ? AND m.league_id = ?
        AND (ht.name_en LIKE ? OR ht.name_cn LIKE ?)
        AND (at.name_en LIKE ? OR at.name_cn LIKE ?)
    ''', (match_date, league_id, f'%{home_team}%', f'%{home_team}%', f'%{away_team}%', f'%{away_team}%'))
    row = cursor.fetchone()
    return row[0] if row else None


def collect_player_season_stats(league_api_id: int, league_db_id: int, season: str = "2024-2025"):
    """采集球员赛季统计"""
    print(f"\n采集联赛{league_db_id} {season}赛季球员统计...")

    conn = get_db()
    cursor = conn.cursor()

    # 获取赛季最佳射手和助攻
    top_scorers = fetch_api("get_topscorers", {
        "league_id": league_api_id,
    })

    if top_scorers and isinstance(top_scorers, list):
        print(f"  获取到 {len(top_scorers)} 个射手榜数据")

        saved = 0
        for i, player in enumerate(top_scorers[:50]):  # 前50名
            player_name = player.get('player_name', '')
            team_name = player.get('team_name', '')
            goals = player.get('goals', 0)
            assists = player.get('assists', 0)
            matches = player.get('matches', 0)

            if not player_name:
                continue

            # 查找球队ID
            team_id = get_team_id_by_name(conn, team_name)

            # 创建或获取球员
            player_id = get_or_create_player(conn, {
                'player_name': player_name,
                'player_country': player.get('player_country', '')
            })

            if player_id and saved < 10:
                print(f"    {player_name} ({team_name}): {goals}球 {assists}助 {matches}场")
                saved += 1

            time.sleep(0.1)

    conn.close()


def collect_match_players(league_api_id: int, league_db_id: int, from_date: str, to_date: str):
    """采集比赛球员统计"""
    print(f"\n采集联赛{league_db_id}比赛球员数据 ({from_date} ~ {to_date})...")

    conn = get_db()
    cursor = conn.cursor()

    # 获取比赛列表
    fixtures = fetch_api("get_events", {
        "league_id": league_api_id,
        "from": from_date,
        "to": to_date
    })

    if not fixtures or not isinstance(fixtures, list):
        print("  无法获取比赛数据")
        conn.close()
        return 0

    print(f"  获取到 {len(fixtures)} 场比赛")

    total_stats = 0

    for fixture in fixtures[:30]:  # 限制比赛数量
        match_date = fixture.get('match_date', '')
        home_team = fixture.get('match_hometeam_name', '')
        away_team = fixture.get('match_awayteam_name', '')
        match_key = fixture.get('match_id', '')

        if not match_date or not home_team or not away_team:
            continue

        # 查找数据库中的比赛
        match_id = get_match_id(conn, match_date, home_team, away_team, league_db_id)
        if not match_id:
            continue

        # 获取比赛球员统计
        lineups = fetch_api("get_lineups", {
            "match_id": match_key
        })

        if lineups and isinstance(lineups, list):
            for lineup in lineups:
                team_name = lineup.get('team_name', '')
                players = lineup.get('lineup', [])

                for player in players:
                    player_name = player.get('player_name', '')
                    player_number = player.get('player_number', '')
                    player_position = player.get('player_position', '')
                    minutes = player.get('minutes_played', 0)
                    goals = player.get('goals', 0)
                    assists = player.get('assists', 0)

                    if not player_name:
                        continue

                    try:
                        cursor.execute('''
                            INSERT OR REPLACE INTO player_match_stats
                            (match_id, player_name, team_name, player_number, player_position,
                             minutes_played, goals, assists)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (match_id, player_name, team_name, player_number, player_position,
                              minutes, goals, assists))
                        total_stats += 1
                    except:
                        pass

        time.sleep(0.3)  # 避免请求过快

    conn.commit()
    conn.close()
    print(f"  保存 {total_stats} 条球员统计")
    return total_stats


def collect_team_squads(league_api_id: int, league_db_id: int):
    """采集球队阵容"""
    print(f"\n采集联赛{league_db_id}球队阵容...")

    conn = get_db()
    cursor = conn.cursor()

    # 获取球队列表
    teams = fetch_api("get_teams", {"league_id": league_api_id})

    if not teams or not isinstance(teams, list):
        print("  无法获取球队数据")
        conn.close()
        return 0

    total_players = 0

    for team in teams:
        team_name = team.get('team_name', '')
        players = team.get('players', [])

        if not players:
            continue

        team_id = get_team_id_by_name(conn, team_name)
        try:
            print(f"  team_id={team_id}: {len(players)} players")
        except:
            print(f"  : {len(players)} players")

        for player in players:
            player_id = get_or_create_player(conn, player)
            if player_id:
                total_players += 1

        time.sleep(0.3)

    conn.close()
    print(f"  共采集 {total_players} 名球员")
    return total_players


def show_player_stats():
    """显示球员统计"""
    print("\n" + "=" * 60)
    print("球员数据统计")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 球员总数
    cursor.execute('SELECT COUNT(*) FROM players')
    total = cursor.fetchone()[0]
    print(f"球员总数: {total}")

    # 按联赛统计球员
    cursor.execute('''
        SELECT l.name_cn, COUNT(DISTINCT p.player_id) as cnt
        FROM players p
        LEFT JOIN player_match_stats pms ON p.name_en = pms.player_name
        LEFT JOIN matches m ON pms.match_id = m.match_id
        LEFT JOIN leagues l ON m.league_id = l.league_id
        GROUP BY l.league_id
        ORDER BY cnt DESC
        LIMIT 10
    ''')

    print("\n各联赛球员统计:")
    for r in cursor.fetchall():
        print(f"  {r[0]}: {r[1]}名")

    # 球员比赛统计
    cursor.execute('SELECT COUNT(*) FROM player_match_stats')
    stats_count = cursor.fetchone()[0]
    print(f"\n球员比赛统计记录: {stats_count}条")

    # 德甲比赛统计
    cursor.execute('''
        SELECT COUNT(*) FROM player_match_stats pms
        JOIN matches m ON pms.match_id = m.match_id
        WHERE m.league_id = 7
    ''')
    bundesliga_stats = cursor.fetchone()[0]
    print(f"德甲比赛统计: {bundesliga_stats}条")

    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("德甲/德乙球员年度数据采集")
    print("=" * 60)

    # 1. 采集德甲球队阵容
    collect_team_squads(BUNDESLIGA_API_ID, BUNDESLIGA_DB_ID)

    # 2. 采集德甲球员赛季统计
    collect_player_season_stats(BUNDESLIGA_API_ID, BUNDESLIGA_DB_ID, "2024-2025")

    # 3. 采集德甲比赛球员统计
    collect_match_players(BUNDESLIGA_API_ID, BUNDESLIGA_DB_ID, "2024-08-01", "2025-05-31")

    # 4. 德乙球员数据
    print("\n" + "=" * 60)
    print("采集德乙球员数据")
    print("=" * 60)
    collect_team_squads(BUNDESLIGA2_API_ID, BUNDESLIGA2_DB_ID)

    # 5. 显示统计
    show_player_stats()

    print("\n球员数据采集完成！")
