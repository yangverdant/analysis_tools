#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新数据库 - 同步最新数据到前端
- 添加Status字段到matches表
- 更新联赛规则数据
- 确保前后端数据一致
"""

import os
import sys
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import json

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "football_unified.db"

def update_database_schema():
    """更新数据库结构"""
    print("="*60)
    print("更新数据库结构")
    print("="*60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查matches表是否有status字段
    cursor.execute("PRAGMA table_info(matches)")
    cols = [c[1] for c in cursor.fetchall()]

    if 'status' not in cols:
        print("\n添加status字段到matches表...")
        cursor.execute("ALTER TABLE matches ADD COLUMN status TEXT DEFAULT 'Finished'")
        conn.commit()
        print("  [OK] status字段已添加")
    else:
        print("\n  status字段已存在")

    # 检查seasons表
    cursor.execute("PRAGMA table_info(seasons)")
    cols = [c[1] for c in cursor.fetchall()]

    if 'status' not in cols:
        print("\n添加status字段到seasons表...")
        cursor.execute("ALTER TABLE seasons ADD COLUMN status TEXT DEFAULT 'Finished'")
        conn.commit()
        print("  [OK] status字段已添加")

    conn.close()

def update_match_status():
    """更新比赛状态"""
    print("\n" + "="*60)
    print("更新比赛状态")
    print("="*60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    today = datetime.now().strftime('%Y-%m-%d')

    # 更新状态
    # Finished: 有比分
    # Today: 今天的比赛
    # Scheduled: 未来的比赛
    # Postponed: 过去但无比分

    print(f"\n今天日期: {today}")

    # 已结束的比赛
    cursor.execute("""
        UPDATE matches
        SET status = 'Finished'
        WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
    """)
    finished = cursor.rowcount
    print(f"  Finished (有比分): {finished}")

    # 今天的比赛
    cursor.execute("""
        UPDATE matches
        SET status = 'Today'
        WHERE match_date = ?
        AND (home_goals IS NULL OR away_goals IS NULL)
    """, (today,))
    today_count = cursor.rowcount
    print(f"  Today (今天): {today_count}")

    # 未开始的比赛
    cursor.execute("""
        UPDATE matches
        SET status = 'Scheduled'
        WHERE match_date > ?
        AND (home_goals IS NULL OR away_goals IS NULL)
    """, (today,))
    scheduled = cursor.rowcount
    print(f"  Scheduled (未来): {scheduled}")

    # 延期的比赛
    cursor.execute("""
        UPDATE matches
        SET status = 'Postponed'
        WHERE match_date < ?
        AND (home_goals IS NULL OR away_goals IS NULL)
    """, (today,))
    postponed = cursor.rowcount
    print(f"  Postponed (延期): {postponed}")

    conn.commit()
    conn.close()

def add_league_rules_to_db():
    """添加联赛规则到数据库"""
    print("\n" + "="*60)
    print("添加联赛规则数据")
    print("="*60)

    rules_file = DATA_DIR / "09_other_data/league_rules/league_rules.json"
    if not rules_file.exists():
        print("  联赛规则文件不存在")
        return

    with open(rules_file, 'r', encoding='utf-8') as f:
        rules = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 创建联赛规则表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS league_rules (
            league_code TEXT PRIMARY KEY,
            name TEXT,
            name_en TEXT,
            country TEXT,
            teams INTEGER,
            champions_league_spots INTEGER,
            europa_league_spots INTEGER,
            conference_league_spots INTEGER,
            relegation_spots INTEGER,
            rules_json TEXT
        )
    """)

    # 插入数据
    for code, info in rules.items():
        qual = info.get('qualification', {})
        pro_rel = info.get('promotion_relegation', {})

        cursor.execute("""
            INSERT OR REPLACE INTO league_rules VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            code,
            info.get('name', ''),
            info.get('name_en', ''),
            info.get('country', ''),
            info.get('teams', 0),
            qual.get('champions_league', {}).get('spots', 0),
            qual.get('europa_league', {}).get('spots', 0),
            qual.get('conference_league', {}).get('spots', 0),
            pro_rel.get('relegation', {}).get('spots', 0),
            json.dumps(info, ensure_ascii=False)
        ))

    conn.commit()
    print(f"  [OK] 已添加 {len(rules)} 条联赛规则")
    conn.close()

def add_seasons_table():
    """确保seasons表有完整数据"""
    print("\n" + "="*60)
    print("更新赛季数据")
    print("="*60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 统计每个联赛每个赛季的比赛数
    cursor.execute("""
        SELECT l.league_code, s.season_name, COUNT(*) as match_count
        FROM matches m
        JOIN seasons s ON m.season_id = s.season_id
        JOIN leagues l ON m.league_id = l.league_id
        GROUP BY l.league_code, s.season_name
        ORDER BY l.league_code, s.season_name
    """)

    seasons = cursor.fetchall()
    print(f"  总计 {len(seasons)} 个联赛-赛季组合")

    # 显示部分数据
    print("\n  示例:")
    for i, (league, season, count) in enumerate(seasons[:10]):
        print(f"    {league} {season}: {count}场比赛")

    conn.close()

def verify_sync():
    """验证同步结果"""
    print("\n" + "="*60)
    print("验证同步结果")
    print("="*60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查matches状态分布
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM matches
        GROUP BY status
    """)
    print("\n比赛状态分布:")
    for status, count in cursor.fetchall():
        print(f"  {status}: {count}")

    # 检查联赛规则
    cursor.execute("SELECT COUNT(*) FROM league_rules")
    rules_count = cursor.fetchone()[0]
    print(f"\n联赛规则: {rules_count} 条")

    # 检查数据总量
    cursor.execute("SELECT COUNT(*) FROM matches")
    matches = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM teams")
    teams = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM leagues")
    leagues = cursor.fetchone()[0]

    print(f"\n数据总量:")
    print(f"  比赛: {matches}")
    print(f"  球队: {teams}")
    print(f"  联赛: {leagues}")

    conn.close()

def main():
    print("="*60)
    print("数据库同步更新")
    print("="*60)

    # 1. 更新数据库结构
    update_database_schema()

    # 2. 更新比赛状态
    update_match_status()

    # 3. 添加联赛规则
    add_league_rules_to_db()

    # 4. 更新赛季数据
    add_seasons_table()

    # 5. 验证
    verify_sync()

    print("\n" + "="*60)
    print("同步完成")
    print("="*60)

if __name__ == "__main__":
    main()