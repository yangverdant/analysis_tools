#!/usr/bin/env python3
"""
生成数据库质量报告
"""

import sqlite3
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'd:/football_tools/data/football_v2.db'

def generate_report():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=" * 70)
    print("足球数据库质量报告")
    print("=" * 70)

    # 1. 基础统计
    print("\n【基础统计】")
    stats = [
        ('联赛总数', 'SELECT COUNT(*) FROM leagues'),
        ('赛季总数', 'SELECT COUNT(*) FROM seasons'),
        ('球队总数', 'SELECT COUNT(*) FROM teams'),
        ('比赛总数', 'SELECT COUNT(*) FROM matches'),
        ('积分榜记录', 'SELECT COUNT(*) FROM standings'),
        ('Elo评分记录', 'SELECT COUNT(*) FROM elo_ratings'),
        ('FIFA排名记录', 'SELECT COUNT(*) FROM fifa_rankings'),
        ('联赛规则', 'SELECT COUNT(*) FROM league_rules'),
    ]

    for name, query in stats:
        cursor.execute(query)
        print(f"  {name}: {cursor.fetchone()[0]}")

    # 2. 数据完整性
    print("\n【数据完整性】")

    # 比赛状态分布
    cursor.execute('''
        SELECT status, COUNT(*) as cnt
        FROM matches
        GROUP BY status
        ORDER BY cnt DESC
    ''')
    print("  比赛状态分布:")
    for row in cursor.fetchall():
        status = row[0] if row[0] else 'NULL'
        print(f"    {status}: {row[1]}")

    # 已完成比赛有比分
    cursor.execute('''
        SELECT COUNT(*) FROM matches
        WHERE status = 'finished' AND home_goals IS NOT NULL AND away_goals IS NOT NULL
    ''')
    with_goals = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM matches WHERE status = 'finished'")
    finished = cursor.fetchone()[0]
    print(f"  已完成比赛有比分: {with_goals}/{finished} ({with_goals*100/finished:.1f}%)")

    # 3. 中文名覆盖率
    print("\n【中文名覆盖率】")

    cursor.execute('SELECT COUNT(*) FROM leagues')
    total = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM leagues WHERE name_cn IS NOT NULL AND name_cn != ""')
    has_cn = cursor.fetchone()[0]
    print(f"  联赛中文名: {has_cn}/{total} ({has_cn*100/total:.1f}%)")

    cursor.execute('SELECT COUNT(*) FROM teams')
    total = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM teams WHERE name_cn IS NOT NULL AND name_cn != ""')
    has_cn = cursor.fetchone()[0]
    print(f"  球队中文名: {has_cn}/{total} ({has_cn*100/total:.1f}%)")

    # 4. xG数据覆盖
    print("\n【xG数据覆盖】")
    cursor.execute('SELECT COUNT(*) FROM matches WHERE home_xg IS NOT NULL AND home_xg != ""')
    xg_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM matches WHERE status = 'finished'")
    finished = cursor.fetchone()[0]
    print(f"  有xG的比赛: {xg_count}/{finished} ({xg_count*100/finished:.1f}%)")

    cursor.execute('''
        SELECT l.name_cn, COUNT(*) as cnt
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.home_xg IS NOT NULL AND m.home_xg != ""
        GROUP BY m.league_id
        ORDER BY cnt DESC
    ''')
    print("  xG数据分布:")
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]}场")

    # 5. 按联赛统计比赛
    print("\n【比赛数据分布 (Top 15)】")
    cursor.execute('''
        SELECT l.name_cn, l.name_en, COUNT(*) as cnt
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        GROUP BY m.league_id
        ORDER BY cnt DESC
        LIMIT 15
    ''')
    for row in cursor.fetchall():
        name = row[0] if row[0] else row[1]
        print(f"  {name}: {row[2]}场")

    # 6. 按赛季统计
    print("\n【赛季数据分布】")
    cursor.execute('''
        SELECT s.season_name, COUNT(*) as cnt
        FROM matches m
        JOIN seasons s ON m.season_id = s.season_id
        GROUP BY m.season_id
        ORDER BY s.season_name DESC
        LIMIT 10
    ''')
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}场")

    # 7. 球队类型分布
    print("\n【球队类型分布】")
    cursor.execute('''
        SELECT team_type, COUNT(*) as cnt
        FROM teams
        GROUP BY team_type
        ORDER BY cnt DESC
    ''')
    for row in cursor.fetchall():
        team_type = row[0] if row[0] else 'NULL'
        print(f"  {team_type}: {row[1]}")

    # 8. 数据质量问题
    print("\n【数据质量问题】")

    # 检查缺失主键
    cursor.execute('SELECT COUNT(*) FROM matches WHERE match_id IS NULL')
    null_pk = cursor.fetchone()[0]
    if null_pk > 0:
        print(f"  ⚠ match_id为NULL: {null_pk}")
    else:
        print("  ✓ 所有比赛都有match_id")

    # 检查缺失比分
    cursor.execute('''
        SELECT COUNT(*) FROM matches
        WHERE status = 'finished' AND (home_goals IS NULL OR away_goals IS NULL)
    ''')
    missing_goals = cursor.fetchone()[0]
    if missing_goals > 0:
        print(f"  ⚠ 已完成比赛缺失比分: {missing_goals}")
    else:
        print("  ✓ 所有已完成比赛都有比分")

    # 检查缺失球队名
    cursor.execute('SELECT COUNT(*) FROM teams WHERE name_en IS NULL OR name_en = ""')
    missing_name = cursor.fetchone()[0]
    if missing_name > 0:
        print(f"  ⚠ 球队缺失英文名: {missing_name}")
    else:
        print("  ✓ 所有球队都有英文名")

    print("\n" + "=" * 70)
    print("报告生成完成")
    print("=" * 70)

    conn.close()


if __name__ == '__main__':
    generate_report()
