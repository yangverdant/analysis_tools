#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据后处理脚本
1. 标准化比赛状态
2. 计算Elo评分
3. 生成积分榜
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import math
import sys
import io

# Windows编码处理
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATABASE_PATH = Path(__file__).parent.parent / 'data' / 'football_v2.db'


def standardize_match_status():
    """标准化比赛状态字段"""
    print("=" * 60)
    print("1. 标准化比赛状态")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 查看当前状态分布
    cursor.execute("SELECT status, COUNT(*) FROM matches GROUP BY status")
    print("当前状态分布:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")

    # 标准化映射
    status_map = {
        'FINISHED': 'finished',
        'Finished': 'finished',
        'finished': 'finished',
        'SCHEDULED': 'scheduled',
        'Scheduled': 'scheduled',
        'scheduled': 'scheduled',
        'TIMED': 'scheduled',
        'POSTPONED': 'postponed',
        'CANCELLED': 'cancelled',
        'AWARDED': 'awarded',
        'IN_PLAY': 'live',
        'PAUSED': 'live',
        'HT': 'live',  # Half Time
        'FT': 'finished',  # Full Time
    }

    # 更新状态
    updated = 0
    for old_status, new_status in status_map.items():
        cursor.execute("""
            UPDATE matches SET status = ? WHERE status = ?
        """, (new_status, old_status))
        updated += cursor.rowcount

    # 处理NULL状态
    cursor.execute("""
        UPDATE matches
        SET status = CASE
            WHEN home_goals IS NOT NULL AND away_goals IS NOT NULL THEN 'finished'
            ELSE 'scheduled'
        END
        WHERE status IS NULL OR status = '未知'
    """)

    conn.commit()

    # 查看更新后的状态分布
    cursor.execute("SELECT status, COUNT(*) FROM matches GROUP BY status")
    print("\n更新后状态分布:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")

    print(f"\n更新了 {updated} 条记录")
    conn.close()


def calculate_elo_ratings():
    """计算所有球队的Elo评分"""
    print("\n" + "=" * 60)
    print("2. 计算Elo评分")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Elo参数
    DEFAULT_ELO = 1500
    K_FACTOR = 32
    HOME_ADVANTAGE = 100

    # 清空现有评分
    cursor.execute("DELETE FROM elo_ratings")
    cursor.execute("DELETE FROM elo_history")

    # 获取所有已完成的比赛（按时间排序）
    cursor.execute("""
        SELECT
            match_id,
            match_date,
            home_team_id,
            away_team_id,
            home_goals,
            away_goals,
            neutral
        FROM matches
        WHERE status = 'finished'
        AND home_goals IS NOT NULL
        AND away_goals IS NOT NULL
        ORDER BY match_date ASC
    """)

    matches = cursor.fetchall()
    print(f"共 {len(matches)} 场已完成比赛")

    # 球队Elo缓存
    elo_cache = {}

    def get_elo(team_id):
        return elo_cache.get(team_id, DEFAULT_ELO)

    def expected_score(rating_a, rating_b):
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

    processed = 0
    for match in matches:
        home_id = match['home_team_id']
        away_id = match['away_team_id']

        home_elo = get_elo(home_id)
        away_elo = get_elo(away_id)

        # 主场优势调整（中立场无优势）
        if match['neutral'] == 1:
            home_elo_adj = home_elo
        else:
            home_elo_adj = home_elo + HOME_ADVANTAGE

        # 计算期望胜率
        home_expected = expected_score(home_elo_adj, away_elo)
        away_expected = expected_score(away_elo, home_elo_adj)

        # 实际结果
        if match['home_goals'] > match['away_goals']:
            home_actual = 1.0
            away_actual = 0.0
        elif match['home_goals'] < match['away_goals']:
            home_actual = 0.0
            away_actual = 1.0
        else:
            home_actual = 0.5
            away_actual = 0.5

        # 更新Elo
        new_home_elo = home_elo + K_FACTOR * (home_actual - home_expected)
        new_away_elo = away_elo + K_FACTOR * (away_actual - away_expected)

        elo_cache[home_id] = new_home_elo
        elo_cache[away_id] = new_away_elo

        processed += 1
        if processed % 10000 == 0:
            print(f"  已处理 {processed} 场比赛...")

    # 保存Elo评分
    for team_id, elo in elo_cache.items():
        cursor.execute("""
            INSERT INTO elo_ratings (team_id, elo_rating, calculated_at)
            VALUES (?, ?, datetime('now'))
        """, (team_id, round(elo, 2)))

    conn.commit()

    # 显示Top 20 Elo评分
    cursor.execute("""
        SELECT t.name_en, t.name_cn, e.elo_rating
        FROM elo_ratings e
        JOIN teams t ON e.team_id = t.team_id
        ORDER BY e.elo_rating DESC
        LIMIT 20
    """)

    print("\nElo评分 Top 20:")
    for i, row in enumerate(cursor.fetchall(), 1):
        try:
            name = row['name_cn'] or row['name_en']
            print(f"  {i}. {name}: {row['elo_rating']:.0f}")
        except:
            print(f"  {i}. {row['name_en']}: {row['elo_rating']:.0f}")

    print(f"\n共计算 {len(elo_cache)} 支球队的Elo评分")
    conn.close()


def generate_standings():
    """生成积分榜"""
    print("\n" + "=" * 60)
    print("3. 生成积分榜")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 获取所有联赛-赛季组合
    cursor.execute("""
        SELECT DISTINCT m.league_id, m.season_id, l.name_en, s.season_name
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        JOIN seasons s ON m.season_id = s.season_id
        WHERE m.status = 'finished'
        AND l.competition_type = 'league'
        ORDER BY m.league_id, m.season_id
    """)

    league_seasons = cursor.fetchall()
    print(f"共 {len(league_seasons)} 个联赛-赛季组合")

    # 清空现有积分榜
    cursor.execute("DELETE FROM standings")

    total_standings = 0

    for ls in league_seasons:
        league_id = ls['league_id']
        season_id = ls['season_id']

        # 计算每支球队的积分
        cursor.execute("""
            WITH team_stats AS (
                -- 主场比赛统计
                SELECT
                    home_team_id as team_id,
                    COUNT(*) as played,
                    SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as won,
                    SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as drawn,
                    SUM(CASE WHEN home_goals < away_goals THEN 1 ELSE 0 END) as lost,
                    SUM(home_goals) as goals_for,
                    SUM(away_goals) as goals_against
                FROM matches
                WHERE league_id = ? AND season_id = ? AND status = 'finished'
                GROUP BY home_team_id

                UNION ALL

                -- 客场比赛统计
                SELECT
                    away_team_id as team_id,
                    COUNT(*) as played,
                    SUM(CASE WHEN away_goals > home_goals THEN 1 ELSE 0 END) as won,
                    SUM(CASE WHEN away_goals = home_goals THEN 1 ELSE 0 END) as drawn,
                    SUM(CASE WHEN away_goals < home_goals THEN 1 ELSE 0 END) as lost,
                    SUM(away_goals) as goals_for,
                    SUM(home_goals) as goals_against
                FROM matches
                WHERE league_id = ? AND season_id = ? AND status = 'finished'
                GROUP BY away_team_id
            )
            SELECT
                team_id,
                SUM(played) as played,
                SUM(won) as won,
                SUM(drawn) as drawn,
                SUM(lost) as lost,
                SUM(goals_for) as goals_for,
                SUM(goals_against) as goals_against,
                SUM(won * 3 + drawn) as points
            FROM team_stats
            GROUP BY team_id
            ORDER BY points DESC, (SUM(goals_for) - SUM(goals_against)) DESC, SUM(goals_for) DESC
        """, (league_id, season_id, league_id, season_id))

        teams = cursor.fetchall()

        # 插入积分榜
        for position, team in enumerate(teams, 1):
            cursor.execute("""
                INSERT INTO standings (
                    league_id, season_id, team_id, position,
                    played, won, drawn, lost,
                    goals_for, goals_against, points,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                league_id, season_id, team['team_id'], position,
                team['played'], team['won'], team['drawn'], team['lost'],
                team['goals_for'], team['goals_against'],
                team['points']
            ))
            total_standings += 1

    conn.commit()

    print(f"共生成 {total_standings} 条积分榜记录")

    # 显示英超积分榜示例
    cursor.execute("""
        SELECT s.position, t.name_en, s.played, s.won, s.drawn, s.lost,
               s.goals_for, s.goals_against, s.points
        FROM standings s
        JOIN teams t ON s.team_id = t.team_id
        JOIN leagues l ON s.league_id = l.league_id
        JOIN seasons sn ON s.season_id = sn.season_id
        WHERE l.league_code = 'premier_league' AND sn.season_name = '2024-2025'
        ORDER BY s.position
        LIMIT 10
    """)

    print("\n英超 2024-2025 积分榜:")
    print("  #   球队                场  胜  平  负  进  失  积分")
    print("  " + "-" * 55)
    for row in cursor.fetchall():
        try:
            print(f"  {row[0]:2}  {row[1]:20} {row[2]:2}  {row[3]:2}  {row[4]:2}  {row[5]:2}  {row[6]:2}  {row[7]:2}  {row[8]:3}")
        except:
            print(f"  {row[0]:2}  {row[1][:20]:20} {row[2]:2}  {row[3]:2}  {row[4]:2}  {row[5]:2}  {row[6]:2}  {row[7]:2}  {row[8]:3}")

    conn.close()


def main():
    """主函数"""
    print("数据后处理")
    print("=" * 60)

    # 1. 标准化比赛状态
    standardize_match_status()

    # 2. 计算Elo评分
    calculate_elo_ratings()

    # 3. 生成积分榜
    generate_standings()

    print("\n" + "=" * 60)
    print("处理完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
