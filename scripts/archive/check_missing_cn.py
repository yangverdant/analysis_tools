#!/usr/bin/env python3
"""
检查缺失中文名的球队
"""

import sqlite3
import sys

# 设置输出编码
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'd:/football_tools/data/football_v2.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 球队中文名覆盖
    cursor.execute('SELECT COUNT(*) as total, COUNT(name_cn) as has_cn FROM teams')
    row = cursor.fetchone()
    print(f'球队总数: {row[0]}, 有中文名: {row[1]}')

    # 缺失中文名的球队
    cursor.execute('SELECT name_en FROM teams WHERE name_cn IS NULL OR name_cn = "" ORDER BY name_en')
    teams = cursor.fetchall()
    print(f'\n缺失中文名的球队 ({len(teams)} 个):')
    for t in teams:
        print(f'  {t[0]}')

    conn.close()

if __name__ == '__main__':
    main()