#!/usr/bin/env python3
"""
补齐缺失数据：
1. 从比赛数据计算积分榜
2. 计算Elo评分
3. 从football-data.org获取球队信息
4. 计算FIFA排名（基于国家队比赛）
"""

import sqlite3
import requests
import time
import os
from datetime import datetime
from collections import defaultdict

DB_PATH = 'd:/football_tools/data/football_v2.db'

# football-data.org API配置
FD_API_KEY = os.environ.get('FOOTBALL_DATA_API_KEY', '')  # 需要设置环境变量
FD_BASE_URL = 'https://api.football-data.org/v4'

# 联赛代码映射（football-data.org）
FD_LEAGUE_CODES = {
    'premier_league': 'PL',
    'la_liga': 'PD',
    'bundesliga': 'BL1',
    'serie_a': 'SA',
    'ligue_1': 'FL1',
    'championship': 'ELC',
    'eredivisie': 'DED',
    'primeira_liga': 'PPL',
    'bundesliga_2': 'BL2',
    'ligue_2': 'FL2',
    'segunda_division': 'SD',
    'serie_b': 'SB',
    'world_cup': 'WC',
    'euro': 'EC',
}


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def calculate_standings():
    """从比赛数据计算积分榜"""
    print("\n[1/4] 计算积分榜...")
    conn = get_db()
    cursor = conn.cursor()

    # 获取所有已完成的联赛比赛
    cursor.execute('''
        SELECT m.league_id, m.season_id, m.home_team_id, m.away_team_id,
               m.home_goals, m.away_goals, m.result,
               l.competition_type
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.status = 'finished'
          AND m.home_goals IS NOT NULL
          AND m.away_goals IS NOT NULL
          AND l.format_type = 'round_robin'
    ''')
    matches = cursor.fetchall()

    # 按赛季+球队统计
    stats = defaultdict(lambda: {
        'played': 0, 'won': 0, 'drawn': 0, 'lost': 0,
        'goals_for': 0, 'goals_against': 0, 'points': 0,
        'home_played': 0, 'home_won': 0, 'home_drawn': 0, 'home_lost': 0,
        'home_goals_for': 0, 'home_goals_against': 0, 'home_points': 0,
        'away_played': 0, 'away_won': 0, 'away_drawn': 0, 'away_lost': 0,
        'away_goals_for': 0, 'away_goals_against': 0, 'away_points': 0,
    })

    for match in matches:
        league_id = match['league_id']
        season_id = match['season_id']
        home_id = match['home_team_id']
        away_id = match['away_team_id']
        hg = match['home_goals']
        ag = match['away_goals']

        # 主队统计
        home_key = (league_id, season_id, home_id)
        stats[home_key]['played'] += 1
        stats[home_key]['goals_for'] += hg
        stats[home_key]['goals_against'] += ag
        stats[home_key]['home_played'] += 1
        stats[home_key]['home_goals_for'] += hg
        stats[home_key]['home_goals_against'] += ag

        if hg > ag:
            stats[home_key]['won'] += 1
            stats[home_key]['points'] += 3
            stats[home_key]['home_won'] += 1
            stats[home_key]['home_points'] += 3
        elif hg < ag:
            stats[home_key]['lost'] += 1
            stats[home_key]['home_lost'] += 1
        else:
            stats[home_key]['drawn'] += 1
            stats[home_key]['points'] += 1
            stats[home_key]['home_drawn'] += 1
            stats[home_key]['home_points'] += 1

        # 客队统计
        away_key = (league_id, season_id, away_id)
        stats[away_key]['played'] += 1
        stats[away_key]['goals_for'] += ag
        stats[away_key]['goals_against'] += hg
        stats[away_key]['away_played'] += 1
        stats[away_key]['away_goals_for'] += ag
        stats[away_key]['away_goals_against'] += hg

        if ag > hg:
            stats[away_key]['won'] += 1
            stats[away_key]['points'] += 3
            stats[away_key]['away_won'] += 1
            stats[away_key]['away_points'] += 3
        elif ag < hg:
            stats[away_key]['lost'] += 1
            stats[away_key]['away_lost'] += 1
        else:
            stats[away_key]['drawn'] += 1
            stats[away_key]['points'] += 1
            stats[away_key]['away_drawn'] += 1
            stats[away_key]['away_points'] += 1

    # 插入积分榜
    inserted = 0
    for (league_id, season_id, team_id), s in stats.items():
        goal_diff = s['goals_for'] - s['goals_against']
        home_goal_diff = s['home_goals_for'] - s['home_goals_against']
        away_goal_diff = s['away_goals_for'] - s['away_goals_against']

        cursor.execute('''
            INSERT OR REPLACE INTO standings
            (season_id, league_id, team_id, played, won, drawn, lost,
             goals_for, goals_against, goal_diff, points,
             home_played, home_won, home_drawn, home_lost,
             home_goals_for, home_goals_against, home_points,
             away_played, away_won, away_drawn, away_lost,
             away_goals_for, away_goals_against, away_points,
             standing_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            season_id, league_id, team_id, s['played'], s['won'], s['drawn'], s['lost'],
            s['goals_for'], s['goals_against'], goal_diff, s['points'],
            s['home_played'], s['home_won'], s['home_drawn'], s['home_lost'],
            s['home_goals_for'], s['home_goals_against'], s['home_points'],
            s['away_played'], s['away_won'], s['away_drawn'], s['away_lost'],
            s['away_goals_for'], s['away_goals_against'], s['away_points'],
            'total'
        ))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"  插入 {inserted} 条积分榜记录")
    return inserted


def calculate_elo():
    """计算Elo评分"""
    print("\n[2/4] 计算Elo评分...")
    conn = get_db()
    cursor = conn.cursor()

    DEFAULT_ELO = 1500
    K = 32
    HOME_ADVANTAGE = 100

    # 获取所有球队
    cursor.execute('SELECT team_id FROM teams')
    teams = {row['team_id']: DEFAULT_ELO for row in cursor.fetchall()}

    # 获取所有已完成的比赛，按日期排序
    cursor.execute('''
        SELECT match_id, match_date, home_team_id, away_team_id,
               home_goals, away_goals, neutral
        FROM matches
        WHERE status = 'finished'
          AND home_goals IS NOT NULL
          AND away_goals IS NOT NULL
        ORDER BY match_date, match_id
    ''')
    matches = cursor.fetchall()

    # 逐场更新Elo
    history_count = 0
    for match in matches:
        home_id = match['home_team_id']
        away_id = match['away_team_id']
        hg = match['home_goals']
        ag = match['away_goals']
        neutral = match['neutral'] or 0

        if home_id not in teams or away_id not in teams:
            continue

        home_elo = teams[home_id]
        away_elo = teams[away_id]

        # 主场优势
        home_elo_adj = home_elo + (0 if neutral else HOME_ADVANTAGE)

        # 期望胜率
        home_expected = 1 / (1 + 10 ** ((away_elo - home_elo_adj) / 400))
        away_expected = 1 - home_expected

        # 实际结果
        if hg > ag:
            home_actual = 1
            away_actual = 0
        elif hg < ag:
            home_actual = 0
            away_actual = 1
        else:
            home_actual = 0.5
            away_actual = 0.5

        # 更新Elo
        new_home_elo = home_elo + K * (home_actual - home_expected)
        new_away_elo = away_elo + K * (away_actual - away_expected)

        teams[home_id] = new_home_elo
        teams[away_id] = new_away_elo

        # 记录历史
        cursor.execute('''
            INSERT INTO elo_history (team_id, elo_rating, elo_change, match_id, match_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (home_id, new_home_elo, new_home_elo - home_elo, match['match_id'], match['match_date']))
        cursor.execute('''
            INSERT INTO elo_history (team_id, elo_rating, elo_change, match_id, match_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (away_id, new_away_elo, new_away_elo - away_elo, match['match_id'], match['match_date']))
        history_count += 2

    # 保存最终Elo
    for team_id, elo in teams.items():
        cursor.execute('''
            INSERT OR REPLACE INTO elo_ratings (team_id, elo_rating, matches_count, calculated_at)
            VALUES (?, ?, (SELECT COUNT(*) FROM elo_history WHERE team_id = ?), ?)
        ''', (team_id, elo, team_id, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    print(f"  计算 {len(teams)} 支球队Elo评分")
    print(f"  记录 {history_count} 条历史")
    return len(teams)


def fetch_team_info():
    """从football-data.org获取球队信息"""
    print("\n[3/4] 获取球队信息...")

    if not FD_API_KEY:
        print("  跳过: 未设置FOOTBALL_DATA_API_KEY环境变量")
        return 0

    conn = get_db()
    cursor = conn.cursor()

    headers = {'X-Auth-Token': FD_API_KEY}
    updated = 0

    # 获取需要更新的联赛
    for league_code, fd_code in FD_LEAGUE_CODES.items():
        try:
            url = f"{FD_BASE_URL}/competitions/{fd_code}/teams"
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                print(f"  {league_code}: HTTP {response.status_code}")
                continue

            data = response.json()
            teams = data.get('teams', [])

            for team in teams:
                name = team.get('name', '')
                short_name = team.get('shortName', '')
                tla = team.get('tla', '')
                country = team.get('area', {}).get('name', '')
                founded = team.get('founded')
                venue = team.get('venue', '')
                crest = team.get('crest', '')

                # 更新球队信息
                cursor.execute('''
                    UPDATE teams SET
                        short_name = ?,
                        tla = ?,
                        country = COALESCE(NULLIF(country, ''), ?),
                        founded_year = ?,
                        stadium = ?,
                        logo_url = ?
                    WHERE name_en = ? OR name_en = ?
                ''', (short_name, tla, country, founded, venue, crest, name, short_name))

                if cursor.rowcount > 0:
                    updated += 1

            time.sleep(1)  # 限速

        except Exception as e:
            print(f"  {league_code}: 错误 - {e}")

    conn.commit()
    conn.close()
    print(f"  更新 {updated} 支球队信息")
    return updated


def calculate_fifa_rankings():
    """基于国家队比赛计算模拟FIFA排名"""
    print("\n[4/4] 计算国家队排名...")
    conn = get_db()
    cursor = conn.cursor()

    # 获取所有国家队
    cursor.execute('''
        SELECT team_id, name_en FROM teams
        WHERE team_type = 'national'
    ''')
    national_teams = {row['team_id']: row['name_en'] for row in cursor.fetchall()}

    # 使用Elo评分作为排名依据
    cursor.execute('''
        SELECT t.team_id, t.name_en, e.elo_rating
        FROM teams t
        JOIN elo_ratings e ON t.team_id = e.team_id
        WHERE t.team_type = 'national'
        ORDER BY e.elo_rating DESC
    ''')
    rankings = cursor.fetchall()

    # 插入FIFA排名（模拟）
    today = datetime.now().strftime('%Y-%m-%d')
    inserted = 0

    for idx, row in enumerate(rankings, 1):
        cursor.execute('''
            INSERT OR REPLACE INTO fifa_rankings
            (rank_date, team_id, rank, points, confederation)
            VALUES (?, ?, ?, ?, ?)
        ''', (today, row['team_id'], idx, row['elo_rating'], None))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"  插入 {inserted} 条排名记录")
    return inserted


def main():
    print("=" * 70)
    print("补齐缺失数据")
    print("=" * 70)

    # 1. 计算积分榜
    standings = calculate_standings()

    # 2. 计算Elo评分
    elo = calculate_elo()

    # 3. 获取球队信息
    teams = fetch_team_info()

    # 4. 计算FIFA排名
    fifa = calculate_fifa_rankings()

    # 最终统计
    print("\n" + "=" * 70)
    print("完成统计：")
    print("=" * 70)

    conn = get_db()
    cursor = conn.cursor()

    for table in ['standings', 'elo_ratings', 'elo_history', 'fifa_rankings']:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM teams WHERE country IS NOT NULL AND country != ''")
    print(f"  球队有国家: {cursor.fetchone()[0]}")

    conn.close()
    print("\n完成！")


if __name__ == '__main__':
    main()
