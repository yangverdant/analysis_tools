#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入球员数据脚本
从多个CSV文件导入球员数据到players表
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


def import_players():
    """导入球员数据"""
    print("=" * 60)
    print("导入球员数据")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 球员数据文件列表
    player_files = [
        'new_data/players/international/world_cup/world_cup_players_all.csv',
        'new_data/players/international/european_championship/european_championship_players_all.csv',
        'new_data/players/international/world_cup_2026/world_cup_2026_all_players.csv',
        'new_data/players/international/all_players_complete.csv',
    ]

    imported = 0
    duplicates = 0
    total_processed = 0

    for file_path in player_files:
        full_path = Path(__file__).parent.parent / file_path
        if not full_path.exists():
            print(f"  文件不存在: {file_path}")
            continue

        print(f"  处理: {file_path}")

        try:
            import pandas as pd
            df = pd.read_csv(full_path)

            # 检查列名
            print(f"    列: {df.columns.tolist()[:10]}...")
            print(f"    行数: {len(df)}")

            # 根据不同文件格式处理
            for idx, row in df.iterrows():
                total_processed += 1

                # 尝试不同的列名获取球员名
                name_en = None
                nationality = None
                position = None

                # 检查可能的列名
                for col in ['player', 'Player', 'name', 'Name', 'player_name']:
                    if col in df.columns and pd.notna(row.get(col)):
                        name_en = str(row[col]).strip()
                        break

                for col in ['nation', 'Nation', 'nationality', 'Nationality', 'country', 'Country']:
                    if col in df.columns and pd.notna(row.get(col)):
                        nationality = str(row[col]).strip()
                        break

                for col in ['pos', 'Pos', 'position', 'Position']:
                    if col in df.columns and pd.notna(row.get(col)):
                        position = str(row[col]).strip()
                        break

                if not name_en or name_en == 'NaN' or len(name_en) < 2:
                    continue

                # 清理数据
                name_en = name_en.replace('"', '').replace("'", '').strip()
                if len(name_en) > 100:
                    continue

                # 生成player_code
                player_code = re.sub(r'[^a-zA-Z0-9]', '_', name_en.lower())[:30]

                # 检查是否已存在
                cursor.execute("SELECT player_id FROM players WHERE name_en = ? OR player_code = ?", (name_en, player_code))
                if cursor.fetchone():
                    duplicates += 1
                    continue

                # 插入球员
                try:
                    cursor.execute("""
                        INSERT INTO players (player_code, name_en, nationality, position_main, status, created_at)
                        VALUES (?, ?, ?, ?, 'active', datetime('now'))
                    """, (player_code, name_en, nationality, position))

                    if cursor.rowcount > 0:
                        imported += 1

                except sqlite3.IntegrityError:
                    duplicates += 1
                    continue

                # 每处理1000条提交一次
                if imported % 1000 == 0:
                    conn.commit()
                    print(f"    已导入: {imported}")

            conn.commit()
            print(f"    完成: 导入 {imported} 条")

        except Exception as e:
            print(f"  错误: {e}")
            import traceback
            traceback.print_exc()

    # 最终统计
    cursor.execute("SELECT COUNT(*) FROM players")
    total = cursor.fetchone()[0]

    print("\n" + "=" * 60)
    print(f"处理总数: {total_processed}")
    print(f"导入成功: {imported}")
    print(f"重复跳过: {duplicates}")
    print(f"球员总数: {total}")
    print("=" * 60)

    conn.close()


if __name__ == '__main__':
    import_players()