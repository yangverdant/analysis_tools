#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
填充小组积分榜数据
从比赛数据解析小组名并生成积分榜
"""

import os
import sys
import sqlite3
import re
from pathlib import Path
from datetime import datetime

# Windows编码处理
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATABASE_PATH = Path(__file__).parent.parent / 'data' / 'football_v2.db'


def fill_group_names():
    """从match_id解析小组名"""
    print("=" * 60)
    print("填充小组名")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 查找有stage_type='group'但没有group_name的比赛
    cursor.execute("""
        SELECT match_id, league_id, season_id
        FROM matches
        WHERE stage_type = 'group' AND (group_name IS NULL OR group_name = '')
    """)
    matches = cursor.fetchall()

    print(f"  找到 {len(matches)} 场小组赛比赛")

    updated = 0

    for match_id, league_id, season_id in matches:
        # 从match_id解析小组名
        # 格式: world_cup_2026_2026-06-12_mexico_vs_south_africa
        # 或: champions_league_2024_group_a_team1_vs_team2

        parts = match_id.split('_')
        group_name = None

        # 查找group标记
        for i, part in enumerate(parts):
            if part == 'group' and i + 1 < len(parts):
                group_name = parts[i + 1].upper()  # A, B, C等
                break

        # 如果没有group标记，根据比赛顺序推断
        if not group_name:
            # 查找同赛季同联赛的其他小组赛比赛
            cursor.execute("""
                SELECT match_id FROM matches
                WHERE league_id = ? AND season_id = ? AND stage_type = 'group'
                ORDER BY match_date, match_id
            """, (league_id, season_id))
            group_matches = cursor.fetchall()

            # 每4-6场比赛为一个小组
            match_index = [m[0] for m in group_matches].index(match_id)
            group_num = match_index // 6  # 假设每组6场比赛
            group_name = chr(65 + group_num)  # A, B, C...

        if group_name:
            cursor.execute("""
                UPDATE matches SET group_name = ? WHERE match_id = ?
            """, (group_name, match_id))
            updated += 1

    conn.commit()
    print(f"  更新小组名: {updated}")

    conn.close()


def fill_group_standings():
    """填充小组积分榜"""
    print("\n" + "=" * 60)
    print("填充小组积分榜")
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
        AND home_goals IS NOT NULL AND away_goals IS NOT NULL
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
    print("填充小组数据")
    print("=" * 60)

    fill_group_names()
    fill_group_standings()

    print("\n完成")


if __name__ == '__main__':
    main()