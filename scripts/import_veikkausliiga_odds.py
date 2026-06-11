"""
导入芬超完整数据到数据库
- 比赛日期时间
- 赔率数据 (PSC, Max, Avg, Bet365等)
- 比赛统计
"""

import pandas as pd
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'football_v2.db')
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', '01_leagues', 'finland', 'veikkausliiga_raw.csv')

def parse_date(date_str):
    """转换日期格式 DD/MM/YYYY -> YYYY-MM-DD"""
    try:
        parts = date_str.split('/')
        if len(parts) == 3:
            day, month, year = parts
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except:
        pass
    return date_str

def get_team_id(cursor, team_name):
    """获取球队ID"""
    # 直接匹配
    cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (team_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    # 尝试模糊匹配
    cursor.execute("SELECT team_id, name_en FROM teams WHERE name_en LIKE ?", (f"%{team_name}%",))
    row = cursor.fetchone()
    if row:
        return row[0]

    return None

def import_veikkausliiga_data():
    """导入芬超数据"""
    print("=" * 60)
    print("Importing Veikkausliiga Data")
    print("=" * 60)

    # 读取CSV
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')

    # 清理列名
    df.columns = [c.replace('﻿', '').strip() for c in df.columns]

    print(f"\nLoaded {len(df)} matches from CSV")
    print(f"Seasons: {sorted(df['Season'].unique())}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查是否需要添加赔率列
    cursor.execute("PRAGMA table_info(matches)")
    columns = [c[1] for c in cursor.fetchall()]

    odds_columns = [
        ('odds_home', 'REAL'),
        ('odds_draw', 'REAL'),
        ('odds_away', 'REAL'),
        ('odds_home_max', 'REAL'),
        ('odds_draw_max', 'REAL'),
        ('odds_away_max', 'REAL'),
        ('odds_home_avg', 'REAL'),
        ('odds_draw_avg', 'REAL'),
        ('odds_away_avg', 'REAL'),
        ('odds_b365_home', 'REAL'),
        ('odds_b365_draw', 'REAL'),
        ('odds_b365_away', 'REAL'),
    ]

    for col_name, col_type in odds_columns:
        if col_name not in columns:
            cursor.execute(f"ALTER TABLE matches ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")

    conn.commit()

    # 获取联赛ID
    cursor.execute("SELECT league_id FROM leagues WHERE name_en = 'Veikkausliiga'")
    league_row = cursor.fetchone()
    league_id = league_row[0] if league_row else 39

    # 导入数据
    updated = 0
    inserted = 0

    for idx, row in df.iterrows():
        try:
            # 解析数据
            season = int(row['Season'])
            date = parse_date(str(row['Date']))
            time_str = str(row['Time']) if pd.notna(row['Time']) else None
            home_team = row['Home']
            away_team = row['Away']
            home_goals = int(row['HG']) if pd.notna(row['HG']) else None
            away_goals = int(row['AG']) if pd.notna(row['AG']) else None

            # 赔率
            odds_home = float(row['PSCH']) if pd.notna(row['PSCH']) else None
            odds_draw = float(row['PSCD']) if pd.notna(row['PSCD']) else None
            odds_away = float(row['PSCA']) if pd.notna(row['PSCA']) else None
            odds_home_max = float(row['MaxCH']) if pd.notna(row['MaxCH']) else None
            odds_draw_max = float(row['MaxCD']) if pd.notna(row['MaxCD']) else None
            odds_away_max = float(row['MaxCA']) if pd.notna(row['MaxCA']) else None
            odds_home_avg = float(row['AvgCH']) if pd.notna(row['AvgCH']) else None
            odds_draw_avg = float(row['AvgCD']) if pd.notna(row['AvgCD']) else None
            odds_away_avg = float(row['AvgCA']) if pd.notna(row['AvgCA']) else None
            odds_b365_home = float(row['B365CH']) if pd.notna(row.get('B365CH')) else None
            odds_b365_draw = float(row['B365CD']) if pd.notna(row.get('B365CD')) else None
            odds_b365_away = float(row['B365CA']) if pd.notna(row.get('B365CA')) else None

            # 获取球队ID
            home_team_id = get_team_id(cursor, home_team)
            away_team_id = get_team_id(cursor, away_team)

            if not home_team_id or not away_team_id:
                continue

            # 检查比赛是否存在
            cursor.execute("""
                SELECT match_id FROM matches
                WHERE league_id = ? AND match_date = ?
                AND home_team_id = ? AND away_team_id = ?
            """, (league_id, date, home_team_id, away_team_id))

            existing = cursor.fetchone()

            if existing:
                # 更新现有比赛
                cursor.execute("""
                    UPDATE matches SET
                        match_time = COALESCE(match_time, ?),
                        home_goals = COALESCE(home_goals, ?),
                        away_goals = COALESCE(away_goals, ?),
                        odds_home = ?,
                        odds_draw = ?,
                        odds_away = ?,
                        odds_home_max = ?,
                        odds_draw_max = ?,
                        odds_away_max = ?,
                        odds_home_avg = ?,
                        odds_draw_avg = ?,
                        odds_away_avg = ?,
                        odds_b365_home = ?,
                        odds_b365_draw = ?,
                        odds_b365_away = ?,
                        status = 'finished'
                    WHERE match_id = ?
                """, (
                    time_str, home_goals, away_goals,
                    odds_home, odds_draw, odds_away,
                    odds_home_max, odds_draw_max, odds_away_max,
                    odds_home_avg, odds_draw_avg, odds_away_avg,
                    odds_b365_home, odds_b365_draw, odds_b365_away,
                    existing[0]
                ))
                updated += 1
            else:
                # 插入新比赛
                match_id = f"veikkausliiga_{season}_{date}_{home_team_id}_vs_{away_team_id}"
                cursor.execute("""
                    INSERT INTO matches (
                        match_id, league_id, season_id, match_date, match_time,
                        home_team_id, away_team_id, home_goals, away_goals,
                        odds_home, odds_draw, odds_away,
                        odds_home_max, odds_draw_max, odds_away_max,
                        odds_home_avg, odds_draw_avg, odds_away_avg,
                        odds_b365_home, odds_b365_draw, odds_b365_away,
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'finished')
                """, (
                    match_id, league_id, season, date, time_str,
                    home_team_id, away_team_id, home_goals, away_goals,
                    odds_home, odds_draw, odds_away,
                    odds_home_max, odds_draw_max, odds_away_max,
                    odds_home_avg, odds_draw_avg, odds_away_avg,
                    odds_b365_home, odds_b365_draw, odds_b365_away
                ))
                inserted += 1

            if (idx + 1) % 500 == 0:
                conn.commit()
                print(f"Processed {idx + 1}/{len(df)} matches...")

        except Exception as e:
            print(f"Error at row {idx}: {e}")
            continue

    conn.commit()
    print(f"\nDone! Updated: {updated}, Inserted: {inserted}")

    # 验证
    cursor.execute("""
        SELECT COUNT(*) FROM matches WHERE league_id = ? AND odds_home IS NOT NULL
    """, (league_id,))
    with_odds = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM matches WHERE league_id = ?
    """, (league_id,))
    total = cursor.fetchone()[0]

    print(f"\nVeikkausliiga matches with odds: {with_odds}/{total}")

    conn.close()

if __name__ == "__main__":
    import_veikkausliiga_data()
