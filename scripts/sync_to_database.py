"""
同步CSV数据到数据库
将最新的联赛和杯赛数据同步到football_unified.db
"""
import sqlite3
import pandas as pd
import os
from datetime import datetime

DATA_DIR = 'd:/football_tools/data'
DB_PATH = os.path.join(DATA_DIR, 'football_unified.db')

# 联赛映射 (根据数据库中的实际league_id)
LEAGUE_MAP = {
    'premier_league': {'id': 1, 'name': 'Premier League'},
    'championship': {'id': 2, 'name': 'Championship'},
    'league_one': {'id': 3, 'name': 'League One'},
    'league_two': {'id': 4, 'name': 'League Two'},
    'scottish_premier': {'id': 23, 'name': 'Scottish Premiership'},
    'scottish_championship': {'id': 24, 'name': 'Scottish Championship'},
    'bundesliga': {'id': 5, 'name': 'Bundesliga'},
    'bundesliga_2': {'id': 6, 'name': '2. Bundesliga'},
    'bundesliga_3': {'id': 7, 'name': '3. Liga'},
    'la_liga': {'id': 8, 'name': 'La Liga'},
    'la_liga_2': {'id': 9, 'name': 'Segunda Division'},
    'serie_a': {'id': 10, 'name': 'Serie A'},
    'serie_b': {'id': 11, 'name': 'Serie B'},
    'ligue_1': {'id': 12, 'name': 'Ligue 1'},
    'ligue_2': {'id': 13, 'name': 'Ligue 2'},
    'eredivisie': {'id': 14, 'name': 'Eredivisie'},
    'eerste_divisie': {'id': 15, 'name': 'Eerste Divisie'},
    'jupiler_league': {'id': 16, 'name': 'Belgian Pro League'},
    'primeira_liga': {'id': 17, 'name': 'Primeira Liga'},
    'super_lig': {'id': 18, 'name': 'Super Lig'},
    'super_league': {'id': 22, 'name': 'Super League'},
    'ekstraklasa': {'id': 20, 'name': 'Ekstraklasa'},
    'eliteserien': {'id': 21, 'name': 'Eliteserien'},
}

# 杯赛映射
CUP_MAP = {
    'fa_cup': {'id': 100, 'name': 'FA Cup'},
    'england_league_cup': {'id': 101, 'name': 'League Cup'},
    'champions_league': {'id': 200, 'name': 'Champions League'},
    'europa_league': {'id': 201, 'name': 'Europa League'},
    'conference_league': {'id': 202, 'name': 'Conference League'},
    'dfb_pokal': {'id': 300, 'name': 'DFB Pokal'},
    'copa_del_rey': {'id': 400, 'name': 'Copa del Rey'},
    'italy_cup': {'id': 500, 'name': 'Coppa Italia'},
    'coupe_de_france': {'id': 600, 'name': 'Coupe de France'},
}


def get_or_create_team_id(cursor, team_name):
    """获取或创建球队ID"""
    cursor.execute('SELECT team_id FROM teams WHERE canonical_name = ? OR name_cn = ?', (team_name, team_name))
    result = cursor.fetchone()
    if result:
        return result[0]

    # 创建新球队
    cursor.execute('INSERT INTO teams (canonical_name, name_cn) VALUES (?, ?)', (team_name, team_name))
    return cursor.lastrowid


def get_season_id(cursor, season_str):
    """获取赛季ID"""
    cursor.execute('SELECT season_id FROM seasons WHERE season_name = ?', (season_str,))
    result = cursor.fetchone()
    if result:
        return result[0]

    # 创建新赛季
    cursor.execute('INSERT INTO seasons (season_name) VALUES (?)', (season_str,))
    return cursor.lastrowid


def sync_league_matches(conn, csv_path, league_key):
    """同步联赛比赛数据"""
    cursor = conn.cursor()

    if league_key not in LEAGUE_MAP:
        return 0

    league_id = LEAGUE_MAP[league_key]['id']

    try:
        df = pd.read_csv(csv_path, encoding='utf-8', on_bad_lines='skip')
    except Exception as e:
        print(f'  Error reading {csv_path}: {e}')
        return 0
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date', 'HomeTeam', 'AwayTeam'])

    added = 0

    for _, row in df.iterrows():
        try:
            match_date = row['Date'].strftime('%Y-%m-%d')
            home_team = str(row['HomeTeam'])
            away_team = str(row['AwayTeam'])

            # 获取球队ID
            home_team_id = get_or_create_team_id(cursor, home_team)
            away_team_id = get_or_create_team_id(cursor, away_team)

            # 检查是否已存在
            cursor.execute('''
                SELECT match_id FROM matches
                WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
            ''', (match_date, home_team_id, away_team_id))

            existing = cursor.fetchone()
            if existing:
                # 更新现有记录
                match_id = existing[0]
                cursor.execute('''
                    UPDATE matches SET
                        match_time = COALESCE(?, match_time),
                        round = COALESCE(?, round),
                        home_odds = COALESCE(?, home_odds),
                        draw_odds = COALESCE(?, draw_odds),
                        away_odds = COALESCE(?, away_odds),
                        referee = COALESCE(?, referee),
                        home_shots = COALESCE(?, home_shots),
                        away_shots = COALESCE(?, away_shots),
                        home_shots_target = COALESCE(?, home_shots_target),
                        away_shots_target = COALESCE(?, away_shots_target),
                        home_corners = COALESCE(?, home_corners),
                        away_corners = COALESCE(?, away_corners),
                        home_fouls = COALESCE(?, home_fouls),
                        away_fouls = COALESCE(?, away_fouls),
                        home_yellow = COALESCE(?, home_yellow),
                        away_yellow = COALESCE(?, away_yellow),
                        home_red = COALESCE(?, home_red),
                        away_red = COALESCE(?, away_red)
                    WHERE match_id = ?
                ''', (
                    row.get('Time', None),
                    row.get('Round', None),
                    row.get('AvgH', None),
                    row.get('AvgD', None),
                    row.get('AvgA', None),
                    row.get('Referee', None),
                    row.get('HS', None),
                    row.get('AS', None),
                    row.get('HST', None),
                    row.get('AST', None),
                    row.get('HC', None),
                    row.get('AC', None),
                    row.get('HF', None),
                    row.get('AF', None),
                    row.get('HY', None),
                    row.get('AY', None),
                    row.get('HR', None),
                    row.get('AR', None),
                    match_id
                ))
                continue

            # 获取赛季ID
            season_str = row.get('Season', '2025-2026')
            season_id = get_season_id(cursor, season_str)

            # 插入比赛记录
            cursor.execute('''
                INSERT INTO matches (season_id, league_id, home_team_id, away_team_id,
                    match_date, match_time, home_goals, away_goals, home_half_goals, away_half_goals,
                    round, home_odds, draw_odds, away_odds, referee, home_shots, away_shots,
                    home_shots_target, away_shots_target, home_corners, away_corners,
                    home_fouls, away_fouls, home_yellow, away_yellow, home_red, away_red)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                season_id, league_id, home_team_id, away_team_id,
                match_date,
                row.get('Time', None),
                row.get('FTHG', None),
                row.get('FTAG', None),
                row.get('HTHG', None),
                row.get('HTAG', None),
                row.get('Round', None),
                row.get('AvgH', None),
                row.get('AvgD', None),
                row.get('AvgA', None),
                row.get('Referee', None),
                row.get('HS', None),
                row.get('AS', None),
                row.get('HST', None),
                row.get('AST', None),
                row.get('HC', None),
                row.get('AC', None),
                row.get('HF', None),
                row.get('AF', None),
                row.get('HY', None),
                row.get('AY', None),
                row.get('HR', None),
                row.get('AR', None),
            ))
            added += 1

        except Exception as e:
            continue

    conn.commit()
    return added


def sync_cup_matches(conn, csv_path, cup_key):
    """同步杯赛比赛数据"""
    cursor = conn.cursor()

    if cup_key not in CUP_MAP:
        return 0

    league_id = CUP_MAP[cup_key]['id']

    df = pd.read_csv(csv_path, encoding='utf-8', low_memory=False)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date', 'HomeTeam', 'AwayTeam'])

    added = 0

    for _, row in df.iterrows():
        try:
            match_date = row['Date'].strftime('%Y-%m-%d')
            home_team = str(row['HomeTeam'])
            away_team = str(row['AwayTeam'])

            # 获取球队ID
            home_team_id = get_or_create_team_id(cursor, home_team)
            away_team_id = get_or_create_team_id(cursor, away_team)

            # 检查是否已存在
            cursor.execute('''
                SELECT match_id FROM cup_matches
                WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
            ''', (match_date, home_team_id, away_team_id))

            if cursor.fetchone():
                continue

            # 插入杯赛记录
            cursor.execute('''
                INSERT INTO cup_matches (league_id, season, stage, stage_order,
                    group_name, group_round, leg, match_date, match_time,
                    home_team_id, away_team_id, home_team, away_team,
                    home_goals, away_goals, home_et_goals, away_et_goals,
                    home_pen_goals, away_pen_goals)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                league_id,
                row.get('Season', '2025-2026'),
                row.get('Stage', ''),
                row.get('StageOrder', 0),
                row.get('GroupName', ''),
                row.get('GroupRound', None),
                row.get('Leg', None),
                match_date,
                row.get('Time', None),
                home_team_id,
                away_team_id,
                home_team,
                away_team,
                row.get('FTHG', None),
                row.get('FTAG', None),
                row.get('ETHG', None),
                row.get('ETAG', None),
                row.get('PTHG', None),
                row.get('PTAG', None),
            ))
            added += 1

        except Exception as e:
            continue

    conn.commit()
    return added


def main():
    print("=" * 60)
    print(f"同步CSV数据到数据库 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)

    # 同步联赛数据
    print("\n同步联赛数据...")
    leagues_dir = os.path.join(DATA_DIR, '01_leagues')
    total_league = 0

    for country in os.listdir(leagues_dir):
        country_path = os.path.join(leagues_dir, country)
        if os.path.isdir(country_path):
            for file in os.listdir(country_path):
                if file.endswith('.csv'):
                    csv_path = os.path.join(country_path, file)

                    # 提取联赛名称
                    league_key = file.replace('_2025-2026.csv', '').replace('_2024-2025.csv', '')

                    added = sync_league_matches(conn, csv_path, league_key)
                    if added > 0:
                        print(f"  {file}: 新增 {added} 条")
                        total_league += added

    print(f"联赛总计新增: {total_league} 条")

    # 同步杯赛数据
    print("\n同步杯赛数据...")
    cups_dir = os.path.join(DATA_DIR, 'cups_standardized')
    total_cup = 0

    for cup_folder in os.listdir(cups_dir):
        cup_path = os.path.join(cups_dir, cup_folder)
        if os.path.isdir(cup_path):
            for file in os.listdir(cup_path):
                if file.endswith('.csv'):
                    csv_path = os.path.join(cup_path, file)
                    added = sync_cup_matches(conn, csv_path, cup_folder)
                    if added > 0:
                        print(f"  {file}: 新增 {added} 条")
                        total_cup += added

    print(f"杯赛总计新增: {total_cup} 条")

    # 显示最终统计
    print("\n" + "=" * 60)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM matches')
    matches_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM cup_matches')
    cup_matches_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM teams')
    teams_count = cursor.fetchone()[0]

    print(f"数据库统计:")
    print(f"  matches: {matches_count} 条")
    print(f"  cup_matches: {cup_matches_count} 条")
    print(f"  teams: {teams_count} 条")
    print(f"\n本次同步新增: {total_league + total_cup} 条")

    conn.close()


if __name__ == '__main__':
    main()
