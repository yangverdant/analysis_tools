#!/usr/bin/env python3
"""
导入所有比赛数据 - 简化版本
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import re
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_DIR = Path('data')
OUTPUT_DB = DATA_DIR / 'football_unified.db'

# 联赛配置
LEAGUES_CONFIG = {
    'premier_league': {'name': 'Premier League', 'dir': '01_europe_leagues'},
    'championship': {'name': 'Championship', 'dir': '01_europe_leagues'},
    'league_one': {'name': 'League One', 'dir': '01_europe_leagues'},
    'league_two': {'name': 'League Two', 'dir': '01_europe_leagues'},
    'bundesliga': {'name': 'Bundesliga', 'dir': '01_europe_leagues'},
    'bundesliga_2': {'name': '2. Bundesliga', 'dir': '01_europe_leagues'},
    'bundesliga_3': {'name': '3. Liga', 'dir': '01_europe_leagues'},
    'la_liga': {'name': 'La Liga', 'dir': '01_europe_leagues'},
    'segunda_division': {'name': 'Segunda Division', 'dir': '01_europe_leagues'},
    'serie_a': {'name': 'Serie A', 'dir': '01_europe_leagues'},
    'serie_b': {'name': 'Serie B', 'dir': '01_europe_leagues'},
    'ligue_1': {'name': 'Ligue 1', 'dir': '01_europe_leagues'},
    'ligue_2': {'name': 'Ligue 2', 'dir': '01_europe_leagues'},
    'eredivisie': {'name': 'Eredivisie', 'dir': '01_europe_leagues'},
    'eredivisie_2': {'name': 'Eerste Divisie', 'dir': '01_europe_leagues'},
    'jupiler_league': {'name': 'Belgian Pro League', 'dir': '01_europe_leagues'},
    'primeira_liga': {'name': 'Primeira Liga', 'dir': '01_europe_leagues'},
    'super_lig': {'name': 'Super Lig', 'dir': '01_europe_leagues'},
    'super_lig_2': {'name': '1. Lig', 'dir': '01_europe_leagues'},
    'ekstraklasa': {'name': 'Ekstraklasa', 'dir': '01_europe_leagues'},
    'eliteserien': {'name': 'Eliteserien', 'dir': '01_europe_leagues'},
    'superleague': {'name': 'Super League', 'dir': '01_europe_leagues'},
    'scotland_premier': {'name': 'Scottish Premiership', 'dir': '01_europe_leagues'},
    'scotland_div1': {'name': 'Scottish Championship', 'dir': '01_europe_leagues'},
    'scotland_div2': {'name': 'Scottish League One', 'dir': '01_europe_leagues'},
    'scotland_div3': {'name': 'Scottish League Two', 'dir': '01_europe_leagues'},
    'austria': {'name': 'Austrian Bundesliga', 'dir': '01_europe_leagues'},
    'austria_2': {'name': '2. Liga', 'dir': '01_europe_leagues'},
    'switzerland': {'name': 'Swiss Super League', 'dir': '01_europe_leagues'},
    'switzerland_2': {'name': 'Challenge League', 'dir': '01_europe_leagues'},
    'russia': {'name': 'Russian Premier League', 'dir': '01_europe_leagues'},
    'russia_2': {'name': 'FNL', 'dir': '01_europe_leagues'},
    'czech': {'name': 'Czech First League', 'dir': '01_europe_leagues'},
    'hungary': {'name': 'NB I', 'dir': '01_europe_leagues'},
    'romania': {'name': 'Liga I', 'dir': '01_europe_leagues'},
    'ukraine': {'name': 'Ukrainian Premier League', 'dir': '01_europe_leagues'},
    'croatia': {'name': 'Croatian First League', 'dir': '01_europe_leagues'},
    'slovakia': {'name': 'Slovak Super Liga', 'dir': '01_europe_leagues'},
    'sweden': {'name': 'Allsvenskan', 'dir': '01_europe_leagues'},
    'denmark': {'name': 'Danish Superliga', 'dir': '01_europe_leagues'},
    'finland': {'name': 'Veikkausliiga', 'dir': '01_europe_leagues'},
    'j1_league': {'name': 'J1 League', 'dir': '05_asia_leagues'},
    'j2_league': {'name': 'J2 League', 'dir': '05_asia_leagues'},
    'k1_league': {'name': 'K League 1', 'dir': '05_asia_leagues'},
    'k2_league': {'name': 'K League 2', 'dir': '05_asia_leagues'},
    'a_league': {'name': 'A-League', 'dir': '05_asia_leagues'},
    'saudi_pro': {'name': 'Saudi Pro League', 'dir': '05_asia_leagues'},
    'serie_a_brazil': {'name': 'Campeonato Brasileiro Serie A', 'dir': '06_south_america'},
    'serie_b_brazil': {'name': 'Campeonato Brasileiro Serie B', 'dir': '06_south_america'},
    'mls': {'name': 'Major League Soccer', 'dir': '07_north_america'},
    'liga_mx': {'name': 'Liga MX', 'dir': '07_north_america'},
    'egyptian_premier': {'name': 'Egyptian Premier League', 'dir': '08_africa'},
}


def parse_season(filename):
    """解析赛季名称，统一格式为YYYY-YYYY"""
    # 匹配 YYYY-YYYY 或 YYYY-YY 格式
    match = re.search(r'(\d{4})-(\d{2,4})', filename)
    if match:
        year1 = match.group(1)
        year2 = match.group(2)
        # 统一为 YYYY-YYYY 格式
        if len(year2) == 2:
            year2 = year1[:2] + year2
        return f"{year1}-{year2}"
    # 匹配单独的 YYYY 格式
    match = re.search(r'(\d{4})', filename)
    if match:
        return match.group(1)
    return None


def parse_date(date_str):
    if pd.isna(date_str) or date_str == '':
        return None
    date_str = str(date_str).strip()
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
    except:
        return None


def import_all_matches():
    conn = sqlite3.connect(OUTPUT_DB)
    cursor = conn.cursor()

    # 获取现有球队
    name_to_id = {}
    cursor.execute('SELECT team_id, canonical_name FROM teams')
    for row in cursor.fetchall():
        name_to_id[row[1]] = row[0]

    # 获取联赛ID映射
    cursor.execute('SELECT league_id, league_code FROM leagues')
    league_id_map = {row[1]: row[0] for row in cursor.fetchall()}

    def get_or_create_team(team_name):
        if team_name in name_to_id:
            return name_to_id[team_name]
        cursor.execute('INSERT INTO teams (canonical_name, team_type) VALUES (?, ?)', (team_name, 'club'))
        team_id = cursor.lastrowid
        name_to_id[team_name] = team_id
        return team_id

    total_matches = 0
    total_seasons = 0

    for league_code, config in LEAGUES_CONFIG.items():
        league_id = league_id_map.get(league_code)
        if not league_id:
            continue

        dir_name = config.get('dir', '01_europe_leagues')
        league_dir = DATA_DIR / dir_name / league_code

        if not league_dir.exists():
            continue

        print(f"\n处理 {config['name']}...")

        # 跟踪已处理的赛季，避免重复导入
        processed_seasons = set()

        for csv_file in sorted(league_dir.glob("*.csv")):
            season_name = parse_season(csv_file.stem)
            if not season_name:
                continue

            # 跳过已处理的赛季
            if season_name in processed_seasons:
                continue
            processed_seasons.add(season_name)

            # 获取或创建season_id
            cursor.execute('''
                INSERT OR IGNORE INTO seasons (league_id, season_name)
                VALUES (?, ?)
            ''', (league_id, season_name))

            cursor.execute('''
                SELECT season_id FROM seasons
                WHERE league_id = ? AND season_name = ?
            ''', (league_id, season_name))
            season_id = cursor.fetchone()[0]

            # 读取CSV
            try:
                df = pd.read_csv(csv_file, encoding='utf-8', low_memory=False, on_bad_lines='skip')
            except:
                try:
                    df = pd.read_csv(csv_file, encoding='latin-1', low_memory=False, on_bad_lines='skip')
                except:
                    continue

            if len(df) == 0:
                continue

            # 查找列
            home_col = None
            away_col = None
            date_col = None

            for col in ['HomeTeam', 'home_team', 'Home']:
                if col in df.columns:
                    home_col = col
                    break
            for col in ['AwayTeam', 'away_team', 'Away']:
                if col in df.columns:
                    away_col = col
                    break
            for col in ['Date', 'date', 'match_date']:
                if col in df.columns:
                    date_col = col
                    break

            if not home_col or not away_col:
                continue

            # 导入比赛
            file_count = 0
            for _, row in df.iterrows():
                try:
                    home_team = str(row[home_col]).strip() if pd.notna(row[home_col]) else None
                    away_team = str(row[away_col]).strip() if pd.notna(row[away_col]) else None

                    if not home_team or not away_team or home_team == 'nan' or away_team == 'nan':
                        continue

                    home_team_id = get_or_create_team(home_team)
                    away_team_id = get_or_create_team(away_team)

                    match_date = parse_date(row[date_col]) if date_col else None

                    # 获取比分
                    home_goals = None
                    away_goals = None
                    for col in ['FTHG', 'home_goals', 'HomeGoals']:
                        if col in df.columns and pd.notna(row[col]):
                            try:
                                home_goals = int(float(row[col]))
                            except:
                                pass
                    for col in ['FTAG', 'away_goals', 'AwayGoals']:
                        if col in df.columns and pd.notna(row[col]):
                            try:
                                away_goals = int(float(row[col]))
                            except:
                                pass

                    # 获取时间
                    match_time = None
                    for col in ['Time', 'time', 'match_time']:
                        if col in df.columns and pd.notna(row[col]):
                            match_time = str(row[col])
                            break

                    # 确定状态
                    status = 'Finished'
                    if home_goals is None or away_goals is None:
                        if match_date:
                            today = datetime.now().strftime('%Y-%m-%d')
                            if match_date == today:
                                status = 'Today'
                            elif match_date > today:
                                status = 'Scheduled'
                            else:
                                status = 'Postponed'

                    cursor.execute('''
                        INSERT INTO matches (
                            season_id, league_id, home_team_id, away_team_id, match_date, match_time,
                            home_goals, away_goals, original_home_team, original_away_team, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (season_id, league_id, home_team_id, away_team_id, match_date, match_time,
                          home_goals, away_goals, home_team, away_team, status))

                    file_count += 1
                    total_matches += 1

                except Exception as e:
                    continue

            if file_count > 0:
                print(f"  {season_name}: {file_count} 场比赛")
                total_seasons += 1

            conn.commit()

    conn.close()
    print(f"\n总计: {total_seasons} 个赛季, {total_matches} 场比赛")


if __name__ == '__main__':
    import_all_matches()
