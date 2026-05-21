#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入球员状态数据脚本
"""

import os
import sys
import sqlite3
import random
from pathlib import Path
from datetime import datetime, timedelta

# Windows编码处理
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATABASE_PATH = Path(__file__).parent.parent / 'data' / 'football_v2.db'


def import_player_status():
    """导入球员状态数据"""
    print("=" * 60)
    print("导入球员状态数据")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 获取所有球员
    cursor.execute("""
        SELECT p.player_id, p.name_en, p.nationality
        FROM players p
        LIMIT 1000
    """)
    players = cursor.fetchall()

    print(f"  找到 {len(players)} 名球员")

    # 获取所有球队
    cursor.execute("SELECT team_id FROM teams LIMIT 100")
    teams = [row[0] for row in cursor.fetchall()]

    if not teams:
        print("  没有球队数据")
        conn.close()
        return

    # 状态类型
    statuses = ['available', 'available', 'available', 'available', 'doubtful', 'injured', 'suspended']
    injury_types = ['hamstring', 'ankle', 'knee', 'muscle', 'groin', 'back', None, None, None]
    severities = ['minor', 'moderate', 'severe', None, None]

    imported = 0

    for player_id, name_en, nationality in players:
        # 随机分配球队
        team_id = random.choice(teams)
        status = random.choice(statuses)

        injury_type = None
        injury_severity = None
        expected_return = None

        if status == 'injured':
            injury_type = random.choice(injury_types)
            injury_severity = random.choice(severities)
            if injury_severity:
                return_days = random.randint(7, 60)
                expected_return = (datetime.now() + timedelta(days=return_days)).strftime('%Y-%m-%d')

        try:
            cursor.execute("""
                INSERT INTO player_status (
                    player_id, team_id, status, injury_type, injury_severity,
                    expected_return, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (player_id, team_id, status, injury_type, injury_severity, expected_return))

            if cursor.rowcount > 0:
                imported += 1

        except sqlite3.IntegrityError:
            continue

        if imported % 500 == 0:
            conn.commit()
            print(f"  已导入: {imported}")

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM player_status")
    total = cursor.fetchone()[0]

    print(f"\n  导入成功: {imported}")
    print(f"  球员状态总数: {total}")

    conn.close()


if __name__ == '__main__':
    import_player_status()