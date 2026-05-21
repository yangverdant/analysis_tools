#!/usr/bin/env python3
"""
重新链接player_match_stats到matches表
通过sb_match_id字段
"""

import sqlite3
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'd:/football_tools/data/football_v2.db'

def link_player_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=" * 60)
    print("重新链接player_match_stats到matches表")
    print("=" * 60)

    # 统计当前状态
    cursor.execute('SELECT COUNT(*) FROM player_match_stats')
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM player_match_stats p
        WHERE p.sb_match_id IS NOT NULL
    ''')
    has_sb_id = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM player_match_stats p
        JOIN matches m ON m.sb_match_id = p.sb_match_id
    ''')
    linked_via_sb = cursor.fetchone()[0]

    print(f"\n当前状态:")
    print(f"  player_match_stats总数: {total}")
    print(f"  有sb_match_id的记录: {has_sb_id}")
    print(f"  通过sb_match_id已链接: {linked_via_sb}")

    # 更新match_id字段
    print("\n正在更新match_id字段...")
    cursor.execute('''
        UPDATE player_match_stats
        SET match_id = (
            SELECT m.match_id
            FROM matches m
            WHERE m.sb_match_id = player_match_stats.sb_match_id
        )
        WHERE sb_match_id IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM matches m
            WHERE m.sb_match_id = player_match_stats.sb_match_id
        )
    ''')

    updated = cursor.rowcount
    print(f"  更新了 {updated} 条记录")

    # 检查剩余孤儿记录
    cursor.execute('''
        SELECT COUNT(*) FROM player_match_stats
        WHERE match_id IS NULL OR match_id = ''
    ''')
    orphan = cursor.fetchone()[0]

    print(f"\n结果:")
    print(f"  剩余孤儿记录: {orphan}")

    # 按联赛查看孤儿记录
    cursor.execute('''
        SELECT SUBSTR(match_id, 1, INSTR(match_id, '_') - 1) as league_prefix, COUNT(*) as cnt
        FROM player_match_stats
        WHERE match_id IS NULL OR match_id = ''
        AND original_match_id IS NOT NULL
        GROUP BY league_prefix
        ORDER BY cnt DESC
    ''')
    print("\n孤儿记录按联赛前缀:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print("链接完成!")
    print("=" * 60)

if __name__ == '__main__':
    link_player_stats()