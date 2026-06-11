"""
同步CSV数据到数据库
- 实时同步最新数据
- 重复内容覆盖更新
- 不重复内容顺延记录
"""
import os
import csv
import sqlite3
from datetime import datetime

DATABASE_PATH = 'data/football_unified.db'

# 联赛名称映射
LEAGUE_MAPPING = {
    'premier_league': ('Premier League', 'England', 1),
    'bundesliga': ('Bundesliga', 'Germany', 1),
    'la_liga': ('La Liga', 'Spain', 1),
    'serie_a': ('Serie A', 'Italy', 1),
    'ligue_1': ('Ligue 1', 'France', 1),
    'championship': ('Championship', 'England', 2),
    'bundesliga_2': ('Bundesliga 2', 'Germany', 2),
    'segunda_division': ('Segunda Division', 'Spain', 2),
    'serie_b': ('Serie B', 'Italy', 2),
    'ligue_2': ('Ligue 2', 'France', 2),
}

def get_or_create_team(conn, team_name):
    """获取或创建球队"""
    cursor = conn.cursor()
    cursor.execute("SELECT team_id FROM teams WHERE canonical_name = ?", (team_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    cursor.execute("INSERT INTO teams (canonical_name, team_type, country) VALUES (?, 'club', NULL)", (team_name,))
    return cursor.lastrowid

def get_or_create_league(conn, league_name, country, tier):
    """获取或创建联赛"""
    cursor = conn.cursor()
    cursor.execute("SELECT league_id FROM leagues WHERE name = ?", (league_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    base_code = league_name[:3].upper()
    code = base_code
    counter = 1
    while True:
        cursor.execute("SELECT league_id FROM leagues WHERE league_code = ?", (code,))
        if not cursor.fetchone():
            break
        code = f"{base_code}{counter}"
        counter += 1
    cursor.execute("INSERT INTO leagues (league_code, name, country, tier, league_type) VALUES (?, ?, ?, ?, 'league')", (code, league_name, country, tier))
    return cursor.lastrowid

def parse_date(date_str):
    """解析日期"""
    if not date_str:
        return None
    try:
        if len(date_str) == 10:
            return date_str
        elif len(date_str) == 8:
            year = int(date_str[:2])
            full_year = 2000 + year if year < 50 else 1900 + year
            return f"{full_year}-{date_str[3:5]}-{date_str[6:8]}"
        return None
    except:
        return None

def parse_int(value):
    """解析整数"""
    if not value or str(value).strip() == '':
        return None
    try:
        return int(float(value))
    except:
        return None

def parse_float(value):
    """解析浮点数"""
    if not value or str(value).strip() == '':
        return None
    try:
        return float(value)
    except:
        return None

def import_league_csv(conn, filepath, league_info):
    """导入联赛CSV文件 - 支持更新"""
    cursor = conn.cursor()
    league_name, country, tier = league_info
    league_id = get_or_create_league(conn, league_name, country, tier)

    imported = 0
    updated = 0
    skipped = 0

    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']

    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        date = parse_date(row.get('Date', ''))
                        time = row.get('Time', '').strip()[:5] if row.get('Time') else None
                        home_team = row.get('HomeTeam', '').strip()
                        away_team = row.get('AwayTeam', '').strip()

                        if not date or not home_team or not away_team:
                            skipped += 1
                            continue

                        home_team_id = get_or_create_team(conn, home_team)
                        away_team_id = get_or_create_team(conn, away_team)

                        home_goals = parse_int(row.get('FTHG', ''))
                        away_goals = parse_int(row.get('FTAG', ''))
                        status = 'Finished' if home_goals is not None else 'Scheduled'

                        home_odds = parse_float(row.get('B365H') or row.get('BWH') or row.get('IWH'))
                        draw_odds = parse_float(row.get('B365D') or row.get('BWD') or row.get('IWD'))
                        away_odds = parse_float(row.get('B365A') or row.get('BWA') or row.get('IWA'))

                        home_shots = parse_int(row.get('HS', ''))
                        away_shots = parse_int(row.get('AS', ''))
                        home_shots_target = parse_int(row.get('HST', ''))
                        away_shots_target = parse_int(row.get('AST', ''))
                        home_corners = parse_int(row.get('HC', ''))
                        away_corners = parse_int(row.get('AC', ''))
                        home_fouls = parse_int(row.get('HF', ''))
                        away_fouls = parse_int(row.get('AF', ''))
                        home_yellow = parse_int(row.get('HY', ''))
                        away_yellow = parse_int(row.get('AY', ''))
                        home_red = parse_int(row.get('HR', ''))
                        away_red = parse_int(row.get('AR', ''))

                        # 检查是否已存在
                        cursor.execute("""
                            SELECT match_id, home_goals FROM matches
                            WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
                        """, (date, home_team_id, away_team_id))
                        existing = cursor.fetchone()

                        if existing:
                            # 已存在 - 更新时间和比分
                            existing_id, existing_goals = existing
                            cursor.execute("""
                                UPDATE matches SET
                                    match_time = ?,
                                    home_goals = ?, away_goals = ?, status = ?,
                                    home_odds = ?, draw_odds = ?, away_odds = ?,
                                    home_shots = ?, away_shots = ?,
                                    home_shots_target = ?, away_shots_target = ?,
                                    home_corners = ?, away_corners = ?,
                                    home_fouls = ?, away_fouls = ?,
                                    home_yellow = ?, away_yellow = ?,
                                    home_red = ?, away_red = ?,
                                    original_home_team = ?, original_away_team = ?
                                WHERE match_id = ?
                            """, (
                                time,
                                home_goals, away_goals, status,
                                home_odds, draw_odds, away_odds,
                                home_shots, away_shots,
                                home_shots_target, away_shots_target,
                                home_corners, away_corners,
                                home_fouls, away_fouls,
                                home_yellow, away_yellow,
                                home_red, away_red,
                                home_team, away_team,
                                existing_id
                            ))
                            updated += 1
                        else:
                            # 不存在 - 插入新记录
                            cursor.execute("""
                                INSERT INTO matches (
                                    match_date, match_time, league_id,
                                    home_team_id, away_team_id,
                                    home_goals, away_goals, status,
                                    home_odds, draw_odds, away_odds,
                                    home_shots, away_shots,
                                    home_shots_target, away_shots_target,
                                    home_corners, away_corners,
                                    home_fouls, away_fouls,
                                    home_yellow, away_yellow,
                                    home_red, away_red,
                                    original_home_team, original_away_team
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                date, time, league_id,
                                home_team_id, away_team_id,
                                home_goals, away_goals, status,
                                home_odds, draw_odds, away_odds,
                                home_shots, away_shots,
                                home_shots_target, away_shots_target,
                                home_corners, away_corners,
                                home_fouls, away_fouls,
                                home_yellow, away_yellow,
                                home_red, away_red,
                                home_team, away_team
                            ))
                            imported += 1
                    except Exception as e:
                        skipped += 1
                break  # 成功读取，跳出编码循环
        except UnicodeDecodeError:
            continue
        except Exception as e:
            skipped += 1
            break

    return imported, updated, skipped

def import_fixtures_csv(conn, filepath):
    """导入fixtures CSV文件"""
    cursor = conn.cursor()
    imported = 0
    updated = 0
    skipped = 0

    encodings = ['utf-8', 'utf-8-sig', 'latin-1']

    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        date = parse_date(row.get('Date', ''))
                        time = row.get('Time', '').strip()[:5] if row.get('Time') else None
                        competition = row.get('Competition') or row.get('League', '')
                        home_team = row.get('HomeTeam', '').strip()
                        away_team = row.get('AwayTeam', '').strip()
                        status = row.get('Status', 'Scheduled')

                        if not date or not home_team or not away_team:
                            skipped += 1
                            continue

                        home_team_id = get_or_create_team(conn, home_team)
                        away_team_id = get_or_create_team(conn, away_team)
                        league_id = get_or_create_league(conn, competition, 'Unknown', 1)

                        cursor.execute("""
                            SELECT match_id FROM matches
                            WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
                        """, (date, home_team_id, away_team_id))

                        if cursor.fetchone():
                            skipped += 1
                        else:
                            cursor.execute("""
                                INSERT INTO matches (match_date, match_time, league_id, home_team_id, away_team_id, home_goals, away_goals, status)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (date, time, league_id, home_team_id, away_team_id, None, None, status))
                            imported += 1
                    except Exception as e:
                        skipped += 1
                break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            break

    return imported, updated, skipped

def main():
    """主函数"""
    print('开始同步CSV数据到数据库...')
    print('规则: 重复内容覆盖更新，不重复内容顺延记录')
    print()

    conn = sqlite3.connect(DATABASE_PATH)

    total_imported = 0
    total_updated = 0
    total_skipped = 0

    # 导入联赛数据
    print('导入联赛数据...')
    leagues_dir = 'data/01_europe_leagues'
    if os.path.exists(leagues_dir):
        for league_folder in os.listdir(leagues_dir):
            league_path = os.path.join(leagues_dir, league_folder)
            if os.path.isdir(league_path):
                league_info = LEAGUE_MAPPING.get(league_folder, (league_folder.replace('_', ' ').title(), 'Unknown', 1))

                for csv_file in sorted(os.listdir(league_path)):
                    if csv_file.endswith('.csv') and not csv_file.endswith('_all.csv'):
                        filepath = os.path.join(league_path, csv_file)
                        imported, updated, skipped = import_league_csv(conn, filepath, league_info)
                        total_imported += imported
                        total_updated += updated
                        total_skipped += skipped
                        if imported > 0 or updated > 0:
                            print(f'  {csv_file}: 新增{imported}, 更新{updated}, 跳过{skipped}')

    # 导入fixtures数据
    print('\n导入fixtures数据...')
    fixtures_dir = 'data/fixtures'
    if os.path.exists(fixtures_dir):
        for csv_file in os.listdir(fixtures_dir):
            if csv_file.endswith('.csv'):
                filepath = os.path.join(fixtures_dir, csv_file)
                imported, updated, skipped = import_fixtures_csv(conn, filepath)
                total_imported += imported
                total_updated += updated
                total_skipped += skipped
                if imported > 0:
                    print(f'  {csv_file}: 新增{imported}')

    conn.commit()
    conn.close()

    print(f'\n同步完成!')
    print(f'新增: {total_imported}')
    print(f'更新: {total_updated}')
    print(f'跳过: {total_skipped}')

if __name__ == '__main__':
    main()
