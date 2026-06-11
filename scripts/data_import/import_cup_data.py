"""
杯赛数据导入脚本
将标准化后的杯赛CSV数据导入到数据库
"""
import os
import sqlite3
import pandas as pd
from datetime import datetime

# 数据库路径
DB_PATH = 'd:/football_tools/data/football_unified.db'
CSV_PATH = 'd:/football_tools/data/cups_final/all_cups_matches.csv'

def create_cup_matches_table():
    """创建杯赛比赛表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cup_matches'")
    if cursor.fetchone():
        print("cup_matches表已存在")
        conn.close()
        return

    # 创建杯赛比赛表
    cursor.execute('''
        CREATE TABLE cup_matches (
            match_id INTEGER PRIMARY KEY,
            league_id INTEGER,
            season VARCHAR(20),
            stage VARCHAR(50),
            stage_order INTEGER,
            group_name VARCHAR(10),
            group_round INTEGER,
            leg INTEGER,
            match_date DATE,
            match_time TIME,
            home_team_id INTEGER,
            away_team_id INTEGER,
            home_team VARCHAR(100),
            away_team VARCHAR(100),
            home_team_cn VARCHAR(100),
            away_team_cn VARCHAR(100),
            home_goals INTEGER,
            away_goals INTEGER,
            home_goals_ht INTEGER,
            away_goals_ht INTEGER,
            home_goals_et INTEGER,
            away_goals_et INTEGER,
            home_penalties INTEGER,
            away_penalties INTEGER,
            result VARCHAR(1),
            venue VARCHAR(100),
            attendance INTEGER,
            referee VARCHAR(50),
            status VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 创建索引
    cursor.execute('CREATE INDEX idx_cup_matches_league ON cup_matches(league_id)')
    cursor.execute('CREATE INDEX idx_cup_matches_season ON cup_matches(season)')
    cursor.execute('CREATE INDEX idx_cup_matches_stage ON cup_matches(stage)')
    cursor.execute('CREATE INDEX idx_cup_matches_date ON cup_matches(match_date)')

    conn.commit()
    conn.close()
    print("cup_matches表创建成功")

def import_cup_data():
    """导入杯赛数据"""
    if not os.path.exists(CSV_PATH):
        print(f"CSV文件不存在: {CSV_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 读取CSV
    df = pd.read_csv(CSV_PATH, encoding='utf-8')
    print(f"读取 {len(df)} 条记录")

    # 清空现有数据
    cursor.execute("DELETE FROM cup_matches")

    # 导入数据
    inserted = 0
    for idx, row in df.iterrows():
        try:
            cursor.execute('''
                INSERT INTO cup_matches (
                    match_id, league_id, season, stage, stage_order,
                    group_name, group_round, leg,
                    match_date, match_time,
                    home_team_id, away_team_id,
                    home_team, away_team,
                    home_team_cn, away_team_cn,
                    home_goals, away_goals,
                    home_goals_ht, away_goals_ht,
                    home_goals_et, away_goals_et,
                    home_penalties, away_penalties,
                    result, venue, attendance, referee, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                int(row['match_id']) if pd.notna(row['match_id']) else None,
                int(row['league_id']) if pd.notna(row['league_id']) else None,
                row['season'] if pd.notna(row['season']) else None,
                row['stage'] if pd.notna(row['stage']) else None,
                int(row['stage_order']) if pd.notna(row['stage_order']) else None,
                row['group_name'] if pd.notna(row['group_name']) else None,
                int(row['group_round']) if pd.notna(row['group_round']) else None,
                int(row['leg']) if pd.notna(row['leg']) else None,
                row['match_date'] if pd.notna(row['match_date']) else None,
                row['match_time'] if pd.notna(row['match_time']) else None,
                int(row['home_team_id']) if pd.notna(row['home_team_id']) else None,
                int(row['away_team_id']) if pd.notna(row['away_team_id']) else None,
                row['home_team'] if pd.notna(row['home_team']) else None,
                row['away_team'] if pd.notna(row['away_team']) else None,
                row['home_team_cn'] if pd.notna(row['home_team_cn']) else None,
                row['away_team_cn'] if pd.notna(row['away_team_cn']) else None,
                int(row['home_goals']) if pd.notna(row['home_goals']) else None,
                int(row['away_goals']) if pd.notna(row['away_goals']) else None,
                int(row['home_goals_ht']) if pd.notna(row['home_goals_ht']) else None,
                int(row['away_goals_ht']) if pd.notna(row['away_goals_ht']) else None,
                int(row['home_goals_et']) if pd.notna(row['home_goals_et']) else None,
                int(row['away_goals_et']) if pd.notna(row['away_goals_et']) else None,
                int(row['home_penalties']) if pd.notna(row['home_penalties']) else None,
                int(row['away_penalties']) if pd.notna(row['away_penalties']) else None,
                row['result'] if pd.notna(row['result']) else None,
                row['venue'] if pd.notna(row['venue']) else None,
                int(row['attendance']) if pd.notna(row['attendance']) else None,
                row['referee'] if pd.notna(row['referee']) else None,
                row['status'] if pd.notna(row['status']) else 'Finished'
            ))
            inserted += 1
        except Exception as e:
            print(f"导入失败 (行 {idx}): {e}")

    conn.commit()
    conn.close()
    print(f"成功导入 {inserted} 条杯赛比赛记录")

def update_leagues_table():
    """更新联赛表，添加杯赛频率字段"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查是否有frequency字段
    cursor.execute("PRAGMA table_info(leagues)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'frequency' not in columns:
        cursor.execute("ALTER TABLE leagues ADD COLUMN frequency VARCHAR(20) DEFAULT 'yearly'")
        print("添加frequency字段")

    # 更新杯赛频率
    cup_frequency = {
        42: 'yearly',  # fa_cup
        43: 'yearly',  # england_league_cup
        44: 'yearly',  # dfb_pokal
        45: 'yearly',  # copa_del_rey
        46: 'yearly',  # italy_cup
        47: 'yearly',  # coupe_de_france
        48: 'yearly',  # champions_league
        49: 'yearly',  # europa_league
        50: 'yearly',  # conference_league
        51: 'quadrennial',  # world_cup
        53: 'quadrennial',  # euro
    }

    for league_id, freq in cup_frequency.items():
        cursor.execute("UPDATE leagues SET frequency = ? WHERE league_id = ?", (freq, league_id))

    conn.commit()
    conn.close()
    print("联赛频率更新完成")

if __name__ == '__main__':
    print("=" * 60)
    print("杯赛数据导入脚本")
    print("=" * 60)

    # 1. 创建表
    create_cup_matches_table()

    # 2. 导入数据
    import_cup_data()

    # 3. 更新联赛频率
    update_leagues_table()

    print("\n导入完成!")