#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补充缺失数据脚本
填充空表：players, team_news, player_status, coach_changes, transfers, group_standings
"""

import os
import sys
import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime

# Windows编码处理
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATABASE_PATH = Path(__file__).parent.parent / 'data' / 'football_v2.db'


def fill_players():
    """填充球员数据"""
    print("\n" + "=" * 60)
    print("1. 填充球员数据")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 从本地CSV导入
    player_files = [
        'new_data/players/international/world_cup/world_cup_players_all.csv',
    ]

    imported = 0

    for file_path in player_files:
        full_path = Path(__file__).parent.parent / file_path
        if not full_path.exists():
            print(f"  文件不存在: {file_path}")
            continue

        print(f"  处理: {file_path}")

        try:
            import pandas as pd
            df = pd.read_csv(full_path)

            for idx, row in df.iterrows():
                try:
                    name_en = row.get('player_name') or row.get('name')
                    if not name_en:
                        continue

                    nationality = row.get('country') or row.get('nationality')
                    position = row.get('position')

                    # 生成player_code
                    player_code = re.sub(r'[^a-zA-Z0-9]', '_', name_en.lower())[:20]

                    cursor.execute("""
                        INSERT OR IGNORE INTO players (player_code, name_en, nationality, position_main, status, created_at)
                        VALUES (?, ?, ?, ?, 'active', datetime('now'))
                    """, (player_code, name_en, nationality, position))

                    if cursor.rowcount > 0:
                        imported += 1

                except Exception as e:
                    continue

            conn.commit()

        except Exception as e:
            print(f"  错误: {e}")

    print(f"  导入球员: {imported}")

    cursor.execute("SELECT COUNT(*) FROM players")
    print(f"  球员总数: {cursor.fetchone()[0]}")

    conn.close()


def fill_team_news():
    """填充球队资讯"""
    print("\n" + "=" * 60)
    print("2. 填充球队资讯")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 关键球队的模拟资讯 - 匹配实际表结构
    # 表结构: team_id, title, content, news_type, category, impact_level, impact_type, affected_players, news_date
    news_data = [
        (50, '德布劳内因伤缺阵', '曼城核心中场德布劳内因腿筋伤势将缺席数周比赛', 'injury', 'negative', 3, 'key_player_injury', 'Kevin De Bruyne', '2026-05-15'),
        (50, '哈兰德伤愈复出', '曼城前锋哈兰德已恢复训练，预计下场比赛首发', 'return', 'positive', 2, 'star_player_return', 'Erling Haaland', '2026-05-18'),
        (70, '阿森纳连胜5场', '阿森纳在英超联赛中取得5连胜，状态火热', 'form', 'positive', 2, 'winning_streak', None, '2026-05-16'),
        (70, '新援表现出色', '阿森纳新援在训练中表现出色，有望首发', 'transfer', 'positive', 1, 'new_signing_success', None, '2026-05-12'),
        (113, '主帅续约至2028', '拜仁慕尼黑与主帅完成续约', 'contract', 'positive', 1, 'coach_contract_extension', None, '2026-05-10'),
        (113, '队内矛盾传闻', '媒体爆料拜仁队内存在矛盾', 'conflict', 'negative', 2, 'internal_conflict', None, '2026-05-08'),
        (86, '姆巴佩转会传闻', '媒体报道姆巴佩可能转会', 'transfer', 'negative', 2, 'transfer_saga', 'Kylian Mbappe', '2026-05-14'),
        (86, '欧冠晋级决赛', '皇马成功晋级欧冠决赛', 'win', 'positive', 2, 'winning_streak', None, '2026-05-11'),
        (685, '内马尔长期伤病', '内马尔因伤长期缺席', 'injury', 'negative', 3, 'key_player_injury', 'Neymar', '2026-04-20'),
        (108, '巴萨状态火热', '巴塞罗那近期状态出色，连胜不断', 'form', 'positive', 2, 'winning_streak', None, '2026-05-17'),
    ]

    for team_id, title, content, news_type, category, impact_level, impact_type, affected_players, date in news_data:
        cursor.execute("""
            INSERT OR IGNORE INTO team_news (
                team_id, title, content, news_type, category, impact_level, impact_type,
                affected_players, news_date, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', datetime('now'))
        """, (team_id, title, content, news_type, category, impact_level, impact_type, affected_players, date))

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM team_news")
    print(f"  资讯总数: {cursor.fetchone()[0]}")

    conn.close()


def fill_player_status():
    """填充球员状态"""
    print("\n" + "=" * 60)
    print("3. 填充球员状态")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 先获取一些球员ID
    cursor.execute("SELECT player_id, name_en FROM players LIMIT 20")
    players = cursor.fetchall()

    if not players:
        # 如果没有球员，创建一些模拟数据
        print("  没有球员数据，跳过球员状态填充")
        conn.close()
        return

    # 模拟关键球员状态
    # 表结构: player_id, team_id, status, status_detail, injury_type, injury_severity, expected_return
    status_data = [
        # (player_name, team_id, status, injury_type, is_key_player)
        ('Kevin De Bruyne', 50, 'injured', 'hamstring', 'moderate'),
        ('Erling Haaland', 50, 'available', None, None),
        ('Bukayo Saka', 70, 'available', None, None),
        ('Martin Odegaard', 70, 'available', None, None),
        ('Harry Kane', 113, 'available', None, None),
        ('Vinicius Jr', 86, 'available', None, None),
        ('Kylian Mbappe', 86, 'available', None, None),
        ('Jude Bellingham', 86, 'available', None, None),
        ('Lionel Messi', 685, 'injured', 'ankle', 'severe'),
        ('Robert Lewandowski', 108, 'available', None, None),
    ]

    imported = 0
    for player_name, team_id, status, injury_type, severity in status_data:
        # 查找球员ID
        cursor.execute("SELECT player_id FROM players WHERE name_en = ?", (player_name,))
        result = cursor.fetchone()
        if result:
            player_id = result[0]
        else:
            # 创建球员
            player_code = re.sub(r'[^a-zA-Z0-9]', '_', player_name.lower())[:20]
            cursor.execute("""
                INSERT OR IGNORE INTO players (player_code, name_en, status, created_at)
                VALUES (?, ?, 'active', datetime('now'))
            """, (player_code, player_name))
            player_id = cursor.lastrowid

        if player_id:
            cursor.execute("""
                INSERT OR IGNORE INTO player_status (
                    player_id, team_id, status, injury_type, injury_severity, updated_at
                ) VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (player_id, team_id, status, injury_type, severity))
            if cursor.rowcount > 0:
                imported += 1

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM player_status")
    print(f"  球员状态总数: {cursor.fetchone()[0]}")

    conn.close()


def fill_coach_changes():
    """填充教练变动"""
    print("\n" + "=" * 60)
    print("4. 填充教练变动")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 表结构: team_id, change_type, old_coach_name, new_coach_name, change_date, reason, expected_impact
    changes_data = [
        (50, 'contract_extension', 'Pep Guardiola', 'Pep Guardiola', '2026-05-01', '续约', 'positive'),
        (70, 'contract_extension', 'Mikel Arteta', 'Mikel Arteta', '2026-04-15', '续约', 'positive'),
        (113, 'fired', 'Thomas Tuchel', 'Vincent Kompany', '2026-05-10', '战绩不佳', 'negative'),
        (86, 'contract_extension', 'Carlo Ancelotti', 'Carlo Ancelotti', '2026-03-01', '续约', 'positive'),
        (685, 'contract_extension', 'Luis Enrique', 'Luis Enrique', '2026-02-01', '续约', 'positive'),
    ]

    for team_id, change_type, old_coach, new_coach, change_date, reason, impact in changes_data:
        cursor.execute("""
            INSERT OR IGNORE INTO coach_changes (
                team_id, change_type, old_coach_name, new_coach_name, change_date, reason, expected_impact, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (team_id, change_type, old_coach, new_coach, change_date, reason, impact))

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM coach_changes")
    print(f"  教练变动总数: {cursor.fetchone()[0]}")

    conn.close()


def fill_transfers():
    """填充转会数据"""
    print("\n" + "=" * 60)
    print("5. 填充转会数据")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 表结构: player_name, transfer_type, from_team_id, to_team_id, from_team_name, to_team_name, transfer_date, transfer_fee
    transfers_data = [
        ('Jude Bellingham', 'transfer', 113, 86, 'Borussia Dortmund', 'Real Madrid', '2023-07-01', 100000000),
        ('Erling Haaland', 'transfer', 113, 50, 'Borussia Dortmund', 'Manchester City', '2022-07-01', 60000000),
        ('Harry Kane', 'transfer', 70, 113, 'Tottenham', 'Bayern Munich', '2023-08-01', 100000000),
        ('Enzo Fernandez', 'transfer', None, 64, None, 'Chelsea', '2023-02-01', 120000000),
        ('Moises Caicedo', 'transfer', None, 64, None, 'Chelsea', '2023-08-01', 115000000),
    ]

    for player_name, transfer_type, from_team, to_team, from_name, to_name, transfer_date, fee in transfers_data:
        cursor.execute("""
            INSERT OR IGNORE INTO transfers (
                player_name, transfer_type, from_team_id, to_team_id, from_team_name, to_team_name,
                transfer_date, transfer_fee, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (player_name, transfer_type, from_team, to_team, from_name, to_name, transfer_date, fee))

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM transfers")
    print(f"  转会记录总数: {cursor.fetchone()[0]}")

    conn.close()


def fill_group_standings():
    """填充小组积分榜"""
    print("\n" + "=" * 60)
    print("6. 填充小组积分榜")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 查找有小组赛的比赛
    cursor.execute("""
        SELECT DISTINCT league_id, season_id, group_name
        FROM matches
        WHERE group_name IS NOT NULL AND group_name != ''
        AND status = 'finished'
        LIMIT 50
    """)
    groups = cursor.fetchall()

    print(f"  发现 {len(groups)} 个小组")

    imported = 0

    for group in groups:
        league_id = group['league_id']
        season_id = group['season_id']
        group_name = group['group_name']

        # 计算积分
        cursor.execute("""
            WITH gm AS (
                SELECT home_team_id tid, home_goals gf, away_goals ga,
                    CASE WHEN home_goals > away_goals THEN 3 WHEN home_goals = away_goals THEN 1 ELSE 0 END pts
                FROM matches WHERE league_id=? AND season_id=? AND group_name=? AND status='finished'
                UNION ALL
                SELECT away_team_id, away_goals, home_goals,
                    CASE WHEN away_goals > home_goals THEN 3 WHEN away_goals = home_goals THEN 1 ELSE 0 END
                FROM matches WHERE league_id=? AND season_id=? AND group_name=? AND status='finished'
            )
            SELECT tid, SUM(pts) pts, COUNT(*) played,
                SUM(CASE WHEN pts=3 THEN 1 ELSE 0 END) won,
                SUM(CASE WHEN pts=1 THEN 1 ELSE 0 END) drawn,
                SUM(CASE WHEN pts=0 THEN 1 ELSE 0 END) lost,
                SUM(gf) gf, SUM(ga) ga
            FROM gm GROUP BY tid ORDER BY pts DESC, SUM(gf-ga) DESC
        """, (league_id, season_id, group_name, league_id, season_id, group_name))

        teams = cursor.fetchall()

        for pos, team in enumerate(teams, 1):
            cursor.execute("""
                INSERT OR IGNORE INTO group_standings (
                    season_id, league_id, group_name, team_id, position,
                    played, won, drawn, lost, goals_for, goals_against, goal_diff, points, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (season_id, league_id, group_name, team['tid'], pos,
                  team['played'], team['won'], team['drawn'], team['lost'],
                  team['gf'], team['ga'], team['gf']-team['ga'], team['pts']))

            if cursor.rowcount > 0:
                imported += 1

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM group_standings")
    print(f"  小组积分榜总数: {cursor.fetchone()[0]}")

    conn.close()


def main():
    print("=" * 60)
    print("补充缺失数据")
    print("=" * 60)

    fill_players()
    fill_team_news()
    fill_player_status()
    fill_coach_changes()
    fill_transfers()
    fill_group_standings()

    print("\n" + "=" * 60)
    print("完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
