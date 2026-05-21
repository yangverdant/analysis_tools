#!/usr/bin/env python3
"""
重建数据库 - 修复season_id和league_id关联
- 每个联赛的每个赛季创建独立的season记录
- 比赛正确关联到season_id
- 确保积分榜按赛季筛选
"""

import os
import sys
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import re
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_DIR = Path("data")
LINKAGE_DIR = DATA_DIR / "linkage"
OUTPUT_DB = DATA_DIR / "football_unified.db"

# 联赛配置 - 目录名到联赛信息的映射
LEAGUES_CONFIG = {
    # 欧洲联赛
    'premier_league': {'name': 'Premier League', 'country': 'England', 'tier': 1, 'dir': '01_europe_leagues'},
    'championship': {'name': 'Championship', 'country': 'England', 'tier': 2, 'dir': '01_europe_leagues'},
    'league_one': {'name': 'League One', 'country': 'England', 'tier': 3, 'dir': '01_europe_leagues'},
    'league_two': {'name': 'League Two', 'country': 'England', 'tier': 4, 'dir': '01_europe_leagues'},
    'bundesliga': {'name': 'Bundesliga', 'country': 'Germany', 'tier': 1, 'dir': '01_europe_leagues'},
    'bundesliga_2': {'name': '2. Bundesliga', 'country': 'Germany', 'tier': 2, 'dir': '01_europe_leagues'},
    'bundesliga_3': {'name': '3. Liga', 'country': 'Germany', 'tier': 3, 'dir': '01_europe_leagues'},
    'la_liga': {'name': 'La Liga', 'country': 'Spain', 'tier': 1, 'dir': '01_europe_leagues'},
    'segunda_division': {'name': 'Segunda Division', 'country': 'Spain', 'tier': 2, 'dir': '01_europe_leagues'},
    'serie_a': {'name': 'Serie A', 'country': 'Italy', 'tier': 1, 'dir': '01_europe_leagues'},
    'serie_b': {'name': 'Serie B', 'country': 'Italy', 'tier': 2, 'dir': '01_europe_leagues'},
    'ligue_1': {'name': 'Ligue 1', 'country': 'France', 'tier': 1, 'dir': '01_europe_leagues'},
    'ligue_2': {'name': 'Ligue 2', 'country': 'France', 'tier': 2, 'dir': '01_europe_leagues'},
    'eredivisie': {'name': 'Eredivisie', 'country': 'Netherlands', 'tier': 1, 'dir': '01_europe_leagues'},
    'eredivisie_2': {'name': 'Eerste Divisie', 'country': 'Netherlands', 'tier': 2, 'dir': '01_europe_leagues'},
    'jupiler_league': {'name': 'Belgian Pro League', 'country': 'Belgium', 'tier': 1, 'dir': '01_europe_leagues'},
    'primeira_liga': {'name': 'Primeira Liga', 'country': 'Portugal', 'tier': 1, 'dir': '01_europe_leagues'},
    'super_lig': {'name': 'Super Lig', 'country': 'Turkey', 'tier': 1, 'dir': '01_europe_leagues'},
    'super_lig_2': {'name': '1. Lig', 'country': 'Turkey', 'tier': 2, 'dir': '01_europe_leagues'},
    'ekstraklasa': {'name': 'Ekstraklasa', 'country': 'Poland', 'tier': 1, 'dir': '01_europe_leagues'},
    'eliteserien': {'name': 'Eliteserien', 'country': 'Norway', 'tier': 1, 'dir': '01_europe_leagues'},
    'superleague': {'name': 'Super League', 'country': 'Greece', 'tier': 1, 'dir': '01_europe_leagues'},
    'scotland_premier': {'name': 'Scottish Premiership', 'country': 'Scotland', 'tier': 1, 'dir': '01_europe_leagues'},
    'scotland_div1': {'name': 'Scottish Championship', 'country': 'Scotland', 'tier': 2, 'dir': '01_europe_leagues'},
    'scotland_div2': {'name': 'Scottish League One', 'country': 'Scotland', 'tier': 3, 'dir': '01_europe_leagues'},
    'scotland_div3': {'name': 'Scottish League Two', 'country': 'Scotland', 'tier': 4, 'dir': '01_europe_leagues'},
    'austria': {'name': 'Austrian Bundesliga', 'country': 'Austria', 'tier': 1, 'dir': '01_europe_leagues'},
    'austria_2': {'name': '2. Liga', 'country': 'Austria', 'tier': 2, 'dir': '01_europe_leagues'},
    'switzerland': {'name': 'Swiss Super League', 'country': 'Switzerland', 'tier': 1, 'dir': '01_europe_leagues'},
    'switzerland_2': {'name': 'Challenge League', 'country': 'Switzerland', 'tier': 2, 'dir': '01_europe_leagues'},
    'russia': {'name': 'Russian Premier League', 'country': 'Russia', 'tier': 1, 'dir': '01_europe_leagues'},
    'russia_2': {'name': 'FNL', 'country': 'Russia', 'tier': 2, 'dir': '01_europe_leagues'},
    'czech': {'name': 'Czech First League', 'country': 'Czech Republic', 'tier': 1, 'dir': '01_europe_leagues'},
    'hungary': {'name': 'NB I', 'country': 'Hungary', 'tier': 1, 'dir': '01_europe_leagues'},
    'romania': {'name': 'Liga I', 'country': 'Romania', 'tier': 1, 'dir': '01_europe_leagues'},
    'ukraine': {'name': 'Ukrainian Premier League', 'country': 'Ukraine', 'tier': 1, 'dir': '01_europe_leagues'},
    'croatia': {'name': 'Croatian First League', 'country': 'Croatia', 'tier': 1, 'dir': '01_europe_leagues'},
    'slovakia': {'name': 'Slovak Super Liga', 'country': 'Slovakia', 'tier': 1, 'dir': '01_europe_leagues'},
    'sweden': {'name': 'Allsvenskan', 'country': 'Sweden', 'tier': 1, 'dir': '01_europe_leagues'},
    'denmark': {'name': 'Danish Superliga', 'country': 'Denmark', 'tier': 1, 'dir': '01_europe_leagues'},
    'finland': {'name': 'Veikkausliiga', 'country': 'Finland', 'tier': 1, 'dir': '01_europe_leagues'},

    # 欧洲杯赛
    'fa_cup': {'name': 'FA Cup', 'country': 'England', 'tier': 0, 'type': 'cup', 'dir': '02_europe_cups'},
    'england_league_cup': {'name': 'EFL Cup', 'country': 'England', 'tier': 0, 'type': 'cup', 'dir': '02_europe_cups'},
    'dfb_pokal': {'name': 'DFB-Pokal', 'country': 'Germany', 'tier': 0, 'type': 'cup', 'dir': '02_europe_cups'},
    'copa_del_rey': {'name': 'Copa del Rey', 'country': 'Spain', 'tier': 0, 'type': 'cup', 'dir': '02_europe_cups'},
    'coppa_italia': {'name': 'Coppa Italia', 'country': 'Italy', 'tier': 0, 'type': 'cup', 'dir': '02_europe_cups'},
    'coupe_de_france': {'name': 'Coupe de France', 'country': 'France', 'tier': 0, 'type': 'cup', 'dir': '02_europe_cups'},

    # 欧战
    'champions_league': {'name': 'UEFA Champions League', 'country': 'Europe', 'tier': 0, 'type': 'international', 'dir': '03_european_competitions'},
    'europa_league': {'name': 'UEFA Europa League', 'country': 'Europe', 'tier': 0, 'type': 'international', 'dir': '03_european_competitions'},
    'conference_league': {'name': 'UEFA Conference League', 'country': 'Europe', 'tier': 0, 'type': 'international', 'dir': '03_european_competitions'},

    # 国际赛事
    'world_cup': {'name': 'FIFA World Cup', 'country': 'World', 'tier': 0, 'type': 'international', 'dir': '04_international'},
    'world_cup_qualifiers': {'name': 'World Cup Qualifiers', 'country': 'World', 'tier': 0, 'type': 'international', 'dir': '04_international'},
    'euro': {'name': 'UEFA European Championship', 'country': 'Europe', 'tier': 0, 'type': 'international', 'dir': '04_international'},
    'euro_qualifiers': {'name': 'Euro Qualifiers', 'country': 'Europe', 'tier': 0, 'type': 'international', 'dir': '04_international'},
    'copa_america': {'name': 'Copa America', 'country': 'South America', 'tier': 0, 'type': 'international', 'dir': '04_international'},
    'african_cup': {'name': 'Africa Cup of Nations', 'country': 'Africa', 'tier': 0, 'type': 'international', 'dir': '04_international'},
    'asian_cup': {'name': 'AFC Asian Cup', 'country': 'Asia', 'tier': 0, 'type': 'international', 'dir': '04_international'},
    'concacaf_gold_cup': {'name': 'CONCACAF Gold Cup', 'country': 'North America', 'tier': 0, 'type': 'international', 'dir': '04_international'},
    'nations_league': {'name': 'UEFA Nations League', 'country': 'Europe', 'tier': 0, 'type': 'international', 'dir': '04_international'},

    # 亚洲联赛
    'j1_league': {'name': 'J1 League', 'country': 'Japan', 'tier': 1, 'dir': '05_asia_leagues'},
    'j2_league': {'name': 'J2 League', 'country': 'Japan', 'tier': 2, 'dir': '05_asia_leagues'},
    'k1_league': {'name': 'K League 1', 'country': 'South Korea', 'tier': 1, 'dir': '05_asia_leagues'},
    'k2_league': {'name': 'K League 2', 'country': 'South Korea', 'tier': 2, 'dir': '05_asia_leagues'},
    'chinese_super': {'name': 'Chinese Super League', 'country': 'China', 'tier': 1, 'dir': '05_asia_leagues'},
    'a_league': {'name': 'A-League', 'country': 'Australia', 'tier': 1, 'dir': '05_asia_leagues'},
    'saudi_pro': {'name': 'Saudi Pro League', 'country': 'Saudi Arabia', 'tier': 1, 'dir': '05_asia_leagues'},
    'afc_champions_league': {'name': 'AFC Champions League', 'country': 'Asia', 'tier': 0, 'type': 'international', 'dir': '05_asia_leagues'},

    # 美洲联赛
    'serie_a_brazil': {'name': 'Campeonato Brasileiro Serie A', 'country': 'Brazil', 'tier': 1, 'dir': '06_south_america'},
    'serie_b_brazil': {'name': 'Campeonato Brasileiro Serie B', 'country': 'Brazil', 'tier': 2, 'dir': '06_south_america'},
    'primera_division_argentina': {'name': 'Argentine Primera Division', 'country': 'Argentina', 'tier': 1, 'dir': '06_south_america'},
    'liga_mx': {'name': 'Liga MX', 'country': 'Mexico', 'tier': 1, 'dir': '07_north_america'},
    'mls': {'name': 'Major League Soccer', 'country': 'USA', 'tier': 1, 'dir': '07_north_america'},
    'copa_libertadores': {'name': 'Copa Libertadores', 'country': 'South America', 'tier': 0, 'type': 'international', 'dir': '06_south_america'},

    # 非洲联赛
    'egyptian_premier': {'name': 'Egyptian Premier League', 'country': 'Egypt', 'tier': 1, 'dir': '08_africa'},
}


def create_database():
    """创建数据库和表结构"""
    conn = sqlite3.connect(OUTPUT_DB)
    cursor = conn.cursor()

    print("创建数据库表...")

    # 1. 球队主表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS teams (
        team_id INTEGER PRIMARY KEY,
        canonical_name TEXT NOT NULL UNIQUE,
        alternative_names TEXT,
        team_type TEXT CHECK(team_type IN ('club', 'national')),
        country TEXT,
        city TEXT,
        stadium TEXT,
        founded_year INTEGER,
        fifa_code TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 2. 联赛表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS leagues (
        league_id INTEGER PRIMARY KEY,
        league_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        country TEXT,
        tier INTEGER,
        league_type TEXT DEFAULT 'domestic',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 3. 赛季表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS seasons (
        season_id INTEGER PRIMARY KEY,
        league_id INTEGER,
        season_name TEXT NOT NULL,
        start_date DATE,
        end_date DATE,
        status TEXT DEFAULT 'Finished',
        FOREIGN KEY (league_id) REFERENCES leagues(league_id),
        UNIQUE(league_id, season_name)
    )
    ''')

    # 4. 比赛表 (核心)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        match_id INTEGER PRIMARY KEY AUTOINCREMENT,
        season_id INTEGER,
        league_id INTEGER,
        home_team_id INTEGER,
        away_team_id INTEGER,
        match_date DATE,
        match_time TIME,
        stadium TEXT,
        referee TEXT,
        home_goals INTEGER,
        away_goals INTEGER,
        home_half_goals INTEGER,
        away_half_goals INTEGER,
        home_shots INTEGER,
        away_shots INTEGER,
        home_shots_target INTEGER,
        away_shots_target INTEGER,
        home_corners INTEGER,
        away_corners INTEGER,
        home_fouls INTEGER,
        away_fouls INTEGER,
        home_yellow INTEGER,
        away_yellow INTEGER,
        home_red INTEGER,
        away_red INTEGER,
        attendance INTEGER,
        home_odds REAL,
        draw_odds REAL,
        away_odds REAL,
        home_xg REAL,
        away_xg REAL,
        original_home_team TEXT,
        original_away_team TEXT,
        status TEXT DEFAULT 'Finished',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (season_id) REFERENCES seasons(season_id),
        FOREIGN KEY (league_id) REFERENCES leagues(league_id),
        FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
        FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
    )
    ''')

    # 5. FIFA国家队排名
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS fifa_rankings (
        ranking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        country TEXT,
        rank INTEGER,
        points REAL,
        rank_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 6. FIFA俱乐部排名
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS fifa_club_rankings (
        ranking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        club TEXT,
        country TEXT,
        rank INTEGER,
        points REAL,
        rank_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 7. 联赛规则表
    cursor.execute('''
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
    ''')

    # 创建索引
    print("创建索引...")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_league ON matches(league_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_home ON matches(home_team_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_away ON matches(away_team_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_seasons_league ON seasons(league_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fifa_ranking_date ON fifa_rankings(rank_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fifa_club_date ON fifa_club_rankings(rank_date)')

    conn.commit()
    return conn


def import_leagues(conn):
    """导入联赛数据"""
    cursor = conn.cursor()

    for league_code, config in LEAGUES_CONFIG.items():
        league_type = config.get('type', 'domestic')
        cursor.execute('''
            INSERT OR IGNORE INTO leagues (league_code, name, country, tier, league_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (league_code, config['name'], config['country'], config.get('tier', 1), league_type))

    conn.commit()

    # 获取league_id映射
    cursor.execute('SELECT league_id, league_code FROM leagues')
    return {row[1]: row[0] for row in cursor.fetchall()}


def parse_season_from_filename(filename):
    """从文件名解析赛季"""
    # 尝试匹配 YYYY-YYYY 或 YYYY 格式
    match = re.search(r'(\d{4})-(\d{2,4})', filename)
    if match:
        year1 = match.group(1)
        year2 = match.group(2)
        return f"{year1}-{year2}"

    match = re.search(r'(\d{4})', filename)
    if match:
        return match.group(1)

    return None


def parse_date(date_str):
    """解析日期字符串"""
    if pd.isna(date_str) or date_str == '':
        return None

    date_str = str(date_str).strip()

    formats = [
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%d/%m/%y',
        '%Y/%m/%d',
        '%d-%m-%Y',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except:
            continue

    return None


def get_or_create_team(cursor, team_name, name_to_id, team_type='club'):
    """获取或创建球队"""
    if team_name in name_to_id:
        return name_to_id[team_name]

    # 检查是否已存在
    cursor.execute('SELECT team_id FROM teams WHERE canonical_name = ?', (team_name,))
    result = cursor.fetchone()
    if result:
        name_to_id[team_name] = result[0]
        return result[0]

    # 创建新球队
    cursor.execute('''
        INSERT INTO teams (canonical_name, team_type)
        VALUES (?, ?)
    ''', (team_name, team_type))
    team_id = cursor.lastrowid
    name_to_id[team_name] = team_id
    return team_id


def import_matches(conn, league_id_map):
    """导入比赛数据 - 正确关联season_id"""
    cursor = conn.cursor()

    # 球队名称到ID的映射
    name_to_id = {}

    # 获取现有球队
    cursor.execute('SELECT team_id, canonical_name FROM teams')
    for row in cursor.fetchall():
        name_to_id[row[1]] = row[0]

    # 遍历每个联赛目录
    total_matches = 0
    total_seasons = 0
    season_cache = {}  # (league_id, season_name) -> season_id

    for league_code, config in LEAGUES_CONFIG.items():
        league_id = league_id_map.get(league_code)
        if not league_id:
            continue

        dir_name = config.get('dir', '01_europe_leagues')
        league_dir = DATA_DIR / dir_name / league_code

        if not league_dir.exists():
            continue

        print(f"\n处理 {config['name']}...")

        # 遍历该联赛的所有赛季文件
        for csv_file in sorted(league_dir.glob("*.csv")):
            season_name = parse_season_from_filename(csv_file.stem)
            if not season_name:
                continue

            # 创建或获取season_id
            cache_key = (league_id, season_name)
            if cache_key in season_cache:
                season_id = season_cache[cache_key]
            else:
                cursor.execute('''
                    INSERT OR IGNORE INTO seasons (league_id, season_name)
                    VALUES (?, ?)
                ''', (league_id, season_name))

                cursor.execute('''
                    SELECT season_id FROM seasons
                    WHERE league_id = ? AND season_name = ?
                ''', (league_id, season_name))
                result = cursor.fetchone()
                season_id = result[0] if result else None
                if season_id:
                    season_cache[cache_key] = season_id
                    total_seasons += 1

            if not season_id:
                continue

            # 读取CSV文件
            try:
                # 尝试多种读取方式
                try:
                    df = pd.read_csv(csv_file, encoding='utf-8', low_memory=False, on_bad_lines='skip')
                except:
                    try:
                        df = pd.read_csv(csv_file, encoding='latin-1', low_memory=False, on_bad_lines='skip')
                    except:
                        try:
                            df = pd.read_csv(csv_file, encoding='utf-8', low_memory=False, error_bad_lines=False)
                        except:
                            df = pd.read_csv(csv_file, encoding='latin-1', low_memory=False, error_bad_lines=False)
            except Exception as e:
                print(f"  无法读取 {csv_file.name}: {e}")
                continue

            if len(df) == 0:
                continue

            # 查找列名
            home_col = None
            away_col = None
            date_col = None

            for col in ['HomeTeam', 'home_team', 'Home', 'home_team_name']:
                if col in df.columns:
                    home_col = col
                    break
            for col in ['AwayTeam', 'away_team', 'Away', 'away_team_name']:
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
            file_matches = 0
            for _, row in df.iterrows():
                try:
                    home_team = str(row[home_col]).strip() if pd.notna(row[home_col]) else None
                    away_team = str(row[away_col]).strip() if pd.notna(row[away_col]) else None

                    if not home_team or not away_team or home_team == 'nan' or away_team == 'nan':
                        continue

                    # 获取或创建球队ID
                    home_team_id = get_or_create_team(cursor, home_team, name_to_id, 'club')
                    away_team_id = get_or_create_team(cursor, away_team, name_to_id, 'club')

                    # 解析日期
                    match_date = parse_date(row[date_col]) if date_col else None

                    # 解析其他字段
                    def get_value(row, cols, default=None):
                        for col in cols:
                            if col in row.index and pd.notna(row[col]):
                                try:
                                    return float(row[col]) if '.' in str(row[col]) else int(row[col])
                                except:
                                    return row[col]
                        return default

                    home_goals = get_value(row, ['FTHG', 'home_goals', 'HomeGoals'])
                    away_goals = get_value(row, ['FTAG', 'away_goals', 'AwayGoals'])
                    home_half_goals = get_value(row, ['HTHG', 'home_half_goals'])
                    away_half_goals = get_value(row, ['HTAG', 'away_half_goals'])
                    home_shots = get_value(row, ['HS', 'home_shots'])
                    away_shots = get_value(row, ['AS', 'away_shots'])
                    home_shots_target = get_value(row, ['HST', 'home_shots_target'])
                    away_shots_target = get_value(row, ['AST', 'away_shots_target'])
                    home_corners = get_value(row, ['HC', 'home_corners'])
                    away_corners = get_value(row, ['AC', 'away_corners'])
                    home_fouls = get_value(row, ['HF', 'home_fouls'])
                    away_fouls = get_value(row, ['AF', 'away_fouls'])
                    home_yellow = get_value(row, ['HY', 'home_yellow'])
                    away_yellow = get_value(row, ['AY', 'away_yellow'])
                    home_red = get_value(row, ['HR', 'home_red'])
                    away_red = get_value(row, ['AR', 'away_red'])
                    attendance = get_value(row, ['Attendance', 'attendance'])
                    home_odds = get_value(row, ['B365H', 'HomeOdds', 'home_odds'])
                    draw_odds = get_value(row, ['B365D', 'DrawOdds', 'draw_odds'])
                    away_odds = get_value(row, ['B365A', 'AwayOdds', 'away_odds'])
                    referee = get_value(row, ['Referee', 'referee'])
                    match_time = get_value(row, ['Time', 'time', 'match_time'])

                    # 确定比赛状态
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

                    # 插入比赛
                    cursor.execute('''
                        INSERT INTO matches (
                            season_id, league_id, home_team_id, away_team_id, match_date, match_time,
                            home_goals, away_goals, home_half_goals, away_half_goals,
                            home_shots, away_shots, home_shots_target, away_shots_target,
                            home_corners, away_corners, home_fouls, away_fouls,
                            home_yellow, away_yellow, home_red, away_red,
                            attendance, home_odds, draw_odds, away_odds, referee,
                            original_home_team, original_away_team, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        season_id, league_id, home_team_id, away_team_id, match_date, match_time,
                        home_goals, away_goals, home_half_goals, away_half_goals,
                        home_shots, away_shots, home_shots_target, away_shots_target,
                        home_corners, away_corners, home_fouls, away_fouls,
                        home_yellow, away_yellow, home_red, away_red,
                        attendance, home_odds, draw_odds, away_odds, referee,
                        home_team, away_team, status
                    ))

                    file_matches += 1
                    total_matches += 1

                except Exception as e:
                    continue

            if file_matches > 0:
                print(f"  {season_name}: {file_matches} 场比赛")

            conn.commit()

    print(f"\n总计: {total_seasons} 个赛季, {total_matches} 场比赛")
    return total_matches


def import_fifa_rankings(conn):
    """导入FIFA排名数据"""
    cursor = conn.cursor()

    # 国家队排名
    fifa_file = DATA_DIR / 'fifa_rankings' / 'fifa_world_ranking_complete_2000_2026.csv'
    if fifa_file.exists():
        df = pd.read_csv(fifa_file, encoding='utf-8-sig')
        print(f"导入FIFA国家队排名: {len(df)} 条记录")

        for _, row in df.iterrows():
            try:
                cursor.execute('''
                    INSERT INTO fifa_rankings (country, rank, points, rank_date)
                    VALUES (?, ?, ?, ?)
                ''', (row['Country'], row['Rank'], row['Points'], row['Date']))
            except:
                continue

        conn.commit()

    # 俱乐部排名
    club_file = DATA_DIR / 'fifa_rankings' / 'fifa_club_ranking_complete_2000_2026.csv'
    if club_file.exists():
        df = pd.read_csv(club_file, encoding='utf-8-sig')
        print(f"导入FIFA俱乐部排名: {len(df)} 条记录")

        for _, row in df.iterrows():
            try:
                cursor.execute('''
                    INSERT INTO fifa_club_rankings (club, country, rank, points, rank_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (row['Club'], row.get('Country'), row['Rank'], row['Points'], row['Date']))
            except:
                continue

        conn.commit()


def import_league_rules(conn):
    """导入联赛规则"""
    cursor = conn.cursor()

    rules_file = DATA_DIR / '09_other_data' / 'league_rules' / 'league_rules.json'
    if not rules_file.exists():
        print("联赛规则文件不存在")
        return

    import json
    with open(rules_file, 'r', encoding='utf-8') as f:
        rules = json.load(f)

    for code, info in rules.items():
        qual = info.get('qualification', {})
        pro_rel = info.get('promotion_relegation', {})

        cursor.execute('''
            INSERT OR REPLACE INTO league_rules VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        ''', (
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
    print(f"导入 {len(rules)} 条联赛规则")


def main():
    print("=" * 60)
    print("重建数据库 - 修复season_id关联")
    print("=" * 60)

    # 删除旧数据库
    if OUTPUT_DB.exists():
        print(f"\n删除旧数据库...")
        OUTPUT_DB.unlink()

    # 1. 创建数据库
    print("\n[步骤1] 创建数据库...")
    conn = create_database()

    # 2. 导入联赛
    print("\n[步骤2] 导入联赛数据...")
    league_id_map = import_leagues(conn)
    print(f"导入 {len(league_id_map)} 个联赛")

    # 3. 导入比赛数据
    print("\n[步骤3] 导入比赛数据...")
    total_matches = import_matches(conn, league_id_map)

    # 4. 导入FIFA排名
    print("\n[步骤4] 导入FIFA排名...")
    import_fifa_rankings(conn)

    # 5. 导入联赛规则
    print("\n[步骤5] 导入联赛规则...")
    import_league_rules(conn)

    # 6. 统计报告
    print("\n" + "=" * 60)
    print("数据库重建完成")
    print("=" * 60)

    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM teams')
    teams_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches')
    matches_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM leagues')
    leagues_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM seasons')
    seasons_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM fifa_rankings')
    fifa_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM league_rules')
    rules_count = cursor.fetchone()[0]

    print(f"球队数: {teams_count}")
    print(f"比赛数: {matches_count}")
    print(f"联赛数: {leagues_count}")
    print(f"赛季数: {seasons_count}")
    print(f"FIFA排名: {fifa_count} 条")
    print(f"联赛规则: {rules_count} 条")

    # 验证英超数据
    print("\n验证英超2025-2026赛季数据:")
    cursor.execute('''
        SELECT s.season_name, COUNT(*) as match_count
        FROM matches m
        JOIN seasons s ON m.season_id = s.season_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE l.league_code = 'premier_league'
        GROUP BY s.season_name
        ORDER BY s.season_name DESC
        LIMIT 5
    ''')
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} 场比赛")

    conn.close()

    print(f"\n数据库位置: {OUTPUT_DB}")
    print("\n完成！")


if __name__ == '__main__':
    main()
