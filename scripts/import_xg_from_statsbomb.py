#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从StatsBomb数据提取xG数据
"""

import os
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Windows编码处理
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATABASE_PATH = Path(__file__).parent.parent / 'data' / 'football_v2.db'
STATSBOMB_EVENTS_DIR = Path(__file__).parent.parent / 'new_data' / 'matches' / 'clubs' / 'leagues' / 'StatsBomb_events'


def extract_xg_from_statsbomb():
    """从StatsBomb事件数据提取xG"""
    print("=" * 60)
    print("从StatsBomb数据提取xG")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 获取所有StatsBomb事件文件
    events_files = list(STATSBOMB_EVENTS_DIR.glob('*.json'))
    print(f"  找到 {len(events_files)} 个事件文件")

    updated = 0
    no_match = 0

    for events_file in events_files:
        sb_match_id = int(events_file.stem)  # 文件名就是StatsBomb match_id

        # 检查数据库中是否有这个比赛（通过sb_match_id）
        cursor.execute("""
            SELECT match_id, home_team_id, away_team_id FROM matches WHERE sb_match_id = ?
        """, (sb_match_id,))

        result = cursor.fetchone()
        if not result:
            no_match += 1
            continue

        db_match_id, home_team_id, away_team_id = result

        try:
            with open(events_file, 'r', encoding='utf-8') as f:
                events = json.load(f)

            # 计算双方xG
            home_xg = 0.0
            away_xg = 0.0

            # 获取球队名称映射
            cursor.execute("SELECT team_id, name_en FROM teams WHERE team_id IN (?, ?)", (home_team_id, away_team_id))
            team_names = {row[0]: row[1] for row in cursor.fetchall()}

            # 遍历射门事件
            for event in events:
                if event.get('type', {}).get('name') != 'Shot':
                    continue

                shot_xg = event.get('shot', {}).get('statsbomb_xg')
                if shot_xg is None:
                    continue

                team_info = event.get('team', {})
                team_id = team_info.get('id')
                team_name = team_info.get('name', '')

                # 匹配主客队
                if team_id == home_team_id or team_name in team_names.get(home_team_id, ''):
                    home_xg += shot_xg
                elif team_id == away_team_id or team_name in team_names.get(away_team_id, ''):
                    away_xg += shot_xg

            # 更新数据库
            if home_xg > 0 or away_xg > 0:
                cursor.execute("""
                    UPDATE matches
                    SET home_xg = ?, away_xg = ?, source = 'statsbomb'
                    WHERE match_id = ?
                """, (round(home_xg, 3), round(away_xg, 3), db_match_id))

                if cursor.rowcount > 0:
                    updated += 1

                if updated % 100 == 0:
                    conn.commit()
                    print(f"  已更新: {updated}")

        except Exception as e:
            print(f"  处理文件 {match_id} 错误: {e}")
            continue

    conn.commit()

    # 统计结果
    cursor.execute("SELECT COUNT(*) FROM matches WHERE home_xg IS NOT NULL")
    total_with_xg = cursor.fetchone()[0]

    print(f"\n  更新成功: {updated}")
    print(f"  未匹配比赛: {no_match}")
    print(f"  有xG数据比赛总数: {total_with_xg}")

    conn.close()


if __name__ == '__main__':
    extract_xg_from_statsbomb()