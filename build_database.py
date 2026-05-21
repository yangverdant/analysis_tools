#!/usr/bin/env python3
"""
构建统一足球数据库
将所有CSV数据导入SQLite并建立关联关系
"""

import os
import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# 配置
DATA_DIR = 'd:/football_tools/data'
LINKAGE_DIR = 'd:/football_tools/data/linkage'
OUTPUT_DB = 'd:/football_tools/data/football_unified.db'

# 联赛配置
LEAGUES_CONFIG = {
    # 欧洲联赛
    'premier_league': {'name': 'Premier League', 'country': 'England', 'tier': 1},
    'championship': {'name': 'Championship', 'country': 'England', 'tier': 2},
    'league_one': {'name': 'League One', 'country': 'England', 'tier': 3},
    'league_two': {'name': 'League Two', 'country': 'England', 'tier': 4},
    'bundesliga': {'name': 'Bundesliga', 'country': 'Germany', 'tier': 1},
    'bundesliga_2': {'name': '2. Bundesliga', 'country': 'Germany', 'tier': 2},
    'bundesliga_3': {'name': '3. Liga', 'country': 'Germany', 'tier': 3},
    'la_liga': {'name': 'La Liga', 'country': 'Spain', 'tier': 1},
    'segunda_division': {'name': 'Segunda Division', 'country': 'Spain', 'tier': 2},
    'serie_a': {'name': 'Serie A', 'country': 'Italy', 'tier': 1},
    'serie_b': {'name': 'Serie B', 'country': 'Italy', 'tier': 2},
    'ligue_1': {'name': 'Ligue 1', 'country': 'France', 'tier': 1},
    'ligue_2': {'name': 'Ligue 2', 'country': 'France', 'tier': 2},
    'eredivisie': {'name': 'Eredivisie', 'country': 'Netherlands', 'tier': 1},
    'eredivisie_2': {'name': 'Eerste Divisie', 'country': 'Netherlands', 'tier': 2},
    'jupiler_league': {'name': 'Belgian Pro League', 'country': 'Belgium', 'tier': 1},
    'primeira_liga': {'name': 'Primeira Liga', 'country': 'Portugal', 'tier': 1},
    'super_lig': {'name': 'Super Lig', 'country': 'Turkey', 'tier': 1},
    'super_lig_2': {'name': '1. Lig', 'country': 'Turkey', 'tier': 2},
    'ekstraklasa': {'name': 'Ekstraklasa', 'country': 'Poland', 'tier': 1},
    'eliteserien': {'name': 'Eliteserien', 'country': 'Norway', 'tier': 1},
    'superleague': {'name': 'Super League', 'country': 'Greece', 'tier': 1},
    'scotland_premier': {'name': 'Scottish Premiership', 'country': 'Scotland', 'tier': 1},
    'scotland_div1': {'name': 'Scottish Championship', 'country': 'Scotland', 'tier': 2},
    'scotland_div2': {'name': 'Scottish League One', 'country': 'Scotland', 'tier': 3},
    'scotland_div3': {'name': 'Scottish League Two', 'country': 'Scotland', 'tier': 4},
    'austria': {'name': 'Austrian Bundesliga', 'country': 'Austria', 'tier': 1},
    'austria_2': {'name': '2. Liga', 'country': 'Austria', 'tier': 2},
    'switzerland': {'name': 'Swiss Super League', 'country': 'Switzerland', 'tier': 1},
    'switzerland_2': {'name': 'Challenge League', 'country': 'Switzerland', 'tier': 2},
    'russia': {'name': 'Russian Premier League', 'country': 'Russia', 'tier': 1},
    'russia_2': {'name': 'FNL', 'country': 'Russia', 'tier': 2},
    'czech': {'name': 'Czech First League', 'country': 'Czech Republic', 'tier': 1},
    'hungary': {'name': 'NB I', 'country': 'Hungary', 'tier': 1},
    'romania': {'name': 'Liga I', 'country': 'Romania', 'tier': 1},
    'ukraine': {'name': 'Ukrainian Premier League', 'country': 'Ukraine', 'tier': 1},
    'croatia': {'name': 'Croatian First League', 'country': 'Croatia', 'tier': 1},
    'slovakia': {'name': 'Slovak Super Liga', 'country': 'Slovakia', 'tier': 1},
    'sweden': {'name': 'Allsvenskan', 'country': 'Sweden', 'tier': 1},
    'denmark': {'name': 'Danish Superliga', 'country': 'Denmark', 'tier': 1},
    'finland': {'name': 'Veikkausliiga', 'country': 'Finland', 'tier': 1},

    # 欧洲杯赛
    'fa_cup': {'name': 'FA Cup', 'country': 'England', 'tier': 0, 'type': 'cup'},
    'england_league_cup': {'name': 'EFL Cup', 'country': 'England', 'tier': 0, 'type': 'cup'},
    'dfb_pokal': {'name': 'DFB-Pokal', 'country': 'Germany', 'tier': 0, 'type': 'cup'},
    'copa_del_rey': {'name': 'Copa del Rey', 'country': 'Spain', 'tier': 0, 'type': 'cup'},
    'coppa_italia': {'name': 'Coppa Italia', 'country': 'Italy', 'tier': 0, 'type': 'cup'},
    'coupe_de_france': {'name': 'Coupe de France', 'country': 'France', 'tier': 0, 'type': 'cup'},

    # 欧战
    'champions_league': {'name': 'UEFA Champions League', 'country': 'Europe', 'tier': 0, 'type': 'international'},
    'europa_league': {'name': 'UEFA Europa League', 'country': 'Europe', 'tier': 0, 'type': 'international'},
    'conference_league': {'name': 'UEFA Conference League', 'country': 'Europe', 'tier': 0, 'type': 'international'},

    # 国际赛事
    'world_cup': {'name': 'FIFA World Cup', 'country': 'World', 'tier': 0, 'type': 'international'},
    'world_cup_qualifiers': {'name': 'World Cup Qualifiers', 'country': 'World', 'tier': 0, 'type': 'international'},
    'euro': {'name': 'UEFA European Championship', 'country': 'Europe', 'tier': 0, 'type': 'international'},
    'euro_qualifiers': {'name': 'Euro Qualifiers', 'country': 'Europe', 'tier': 0, 'type': 'international'},
    'copa_america': {'name': 'Copa America', 'country': 'South America', 'tier': 0, 'type': 'international'},
    'african_cup': {'name': 'Africa Cup of Nations', 'country': 'Africa', 'tier': 0, 'type': 'international'},
    'asian_cup': {'name': 'AFC Asian Cup', 'country': 'Asia', 'tier': 0, 'type': 'international'},
    'concacaf_gold_cup': {'name': 'CONCACAF Gold Cup', 'country': 'North America', 'tier': 0, 'type': 'international'},
    'nations_league': {'name': 'UEFA Nations League', 'country': 'Europe', 'tier': 0, 'type': 'international'},

    # 亚洲联赛
    'j1_league': {'name': 'J1 League', 'country': 'Japan', 'tier': 1},
    'j2_league': {'name': 'J2 League', 'country': 'Japan', 'tier': 2},
    'k1_league': {'name': 'K League 1', 'country': 'South Korea', 'tier': 1},
    'k2_league': {'name': 'K League 2', 'country': 'South Korea', 'tier': 2},
    'chinese_super': {'name': 'Chinese Super League', 'country': 'China', 'tier': 1},
    'a_league': {'name': 'A-League', 'country': 'Australia', 'tier': 1},
    'saudi_pro': {'name': 'Saudi Pro League', 'country': 'Saudi Arabia', 'tier': 1},
    'afc_champions_league': {'name': 'AFC Champions League', 'country': 'Asia', 'tier': 0, 'type': 'international'},

    # 美洲联赛
    'serie_a_brazil': {'name': 'Campeonato Brasileiro Serie A', 'country': 'Brazil', 'tier': 1},
    'serie_b_brazil': {'name': 'Campeonato Brasileiro Serie B', 'country': 'Brazil', 'tier': 2},
    'primera_division_argentina': {'name': 'Argentine Primera Division', 'country': 'Argentina', 'tier': 1},
    'liga_mx': {'name': 'Liga MX', 'country': 'Mexico', 'tier': 1},
    'mls': {'name': 'Major League Soccer', 'country': 'USA', 'tier': 1},
    'copa_libertadores': {'name': 'Copa Libertadores', 'country': 'South America', 'tier': 0, 'type': 'international'},

    # 非洲联赛
    'egyptian_premier': {'name': 'Egyptian Premier League', 'country': 'Egypt', 'tier': 1},
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
        canonical_name TEXT NOT NULL,
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

    # 2. 球员主表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS players (
        player_id INTEGER PRIMARY KEY,
        canonical_name TEXT NOT NULL,
        alternative_names TEXT,
        birth_date DATE,
        nationality TEXT,
        position TEXT,
        height INTEGER,
        weight INTEGER,
        preferred_foot TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 3. 教练主表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS coaches (
        coach_id INTEGER PRIMARY KEY,
        canonical_name TEXT NOT NULL,
        alternative_names TEXT,
        birth_date DATE,
        nationality TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 4. 联赛表
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

    # 5. 赛季表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS seasons (
        season_id INTEGER PRIMARY KEY,
        league_id INTEGER,
        season_name TEXT,
        start_date DATE,
        end_date DATE,
        FOREIGN KEY (league_id) REFERENCES leagues(league_id)
    )
    ''')

    # 6. 比赛表 (核心)
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (league_id) REFERENCES leagues(league_id),
        FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
        FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
    )
    ''')

    # 7. FIFA国家队排名
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

    # 8. FIFA俱乐部排名
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

    # 9. Elo历史
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS elo_history (
        elo_id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER,
        elo_rating REAL,
        elo_change REAL,
        date DATE,
        FOREIGN KEY (team_id) REFERENCES teams(team_id)
    )
    ''')

    # 10. 球队名称映射表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_name_mapping (
        mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_name TEXT NOT NULL,
        canonical_name TEXT NOT NULL,
        team_type TEXT
    )
    ''')

    # 创建索引
    print("创建索引...")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_home ON matches(home_team_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_away ON matches(away_team_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_league ON matches(league_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fifa_ranking_date ON fifa_rankings(rank_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fifa_club_date ON fifa_club_rankings(rank_date)')

    conn.commit()
    return conn


def load_team_mapping(conn):
    """加载球队名称映射"""
    cursor = conn.cursor()

    # 读取映射文件
    mapping_file = f'{LINKAGE_DIR}/team_name_mapping.json'
    if os.path.exists(mapping_file):
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
    else:
        print("警告: 未找到映射文件")
        mapping = {}

    # 读取球队主表
    teams_file = f'{LINKAGE_DIR}/teams_master.csv'
    if os.path.exists(teams_file):
        teams_df = pd.read_csv(teams_file, encoding='utf-8-sig')

        # 插入球队数据
        for _, row in teams_df.iterrows():
            cursor.execute('''
                INSERT OR IGNORE INTO teams (team_id, canonical_name, team_type, country)
                VALUES (?, ?, ?, ?)
            ''', (row['team_id'], row['canonical_name'], row['team_type'], row.get('country')))

    # 插入映射数据
    for orig, canonical in mapping.items():
        team_type = 'national' if any(kw in orig for kw in ['Germany', 'France', 'Spain', 'England', 'Brazil', 'Argentina', 'Italy']) else 'club'
        cursor.execute('''
            INSERT OR IGNORE INTO team_name_mapping (original_name, canonical_name, team_type)
            VALUES (?, ?, ?)
        ''', (orig, canonical, team_type))

    conn.commit()

    # 创建名称到ID的映射
    cursor.execute('SELECT team_id, canonical_name FROM teams')
    name_to_id = {row[1]: row[0] for row in cursor.fetchall()}

    # 添加映射关系
    name_to_id.update(mapping)

    return name_to_id


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
    import re

    # 尝试匹配 YYYY-YYYY 或 YYYY 格式
    match = re.search(r'(\d{4})-?(\d{2,4})?', filename)
    if match:
        year1 = match.group(1)
        year2 = match.group(2)
        if year2:
            return f"{year1}-{year2}"
        return year1
    return None


def parse_date(date_str):
    """解析日期字符串"""
    if pd.isna(date_str) or date_str == '':
        return None

    date_str = str(date_str).strip()

    # 尝试多种格式
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


def import_matches(conn, name_to_id, league_id_map):
    """导入比赛数据"""
    cursor = conn.cursor()

    # 遍历所有CSV文件
    csv_files = []
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith('.csv') and '_all.csv' not in f:
                csv_files.append((os.path.join(root, f), f))

    print(f"找到 {len(csv_files)} 个CSV文件")

    total_matches = 0
    skipped_matches = 0

    for i, (filepath, filename) in enumerate(csv_files):
        # 确定联赛代码
        league_code = None
        for code in LEAGUES_CONFIG.keys():
            if code in filepath.lower() or code in filename.lower():
                league_code = code
                break

        if not league_code:
            # 尝试从路径推断
            parts = filepath.replace('\\', '/').split('/')
            for part in parts:
                for code in LEAGUES_CONFIG.keys():
                    if code.replace('_', '') in part.replace('_', '').lower():
                        league_code = code
                        break
                if league_code:
                    break

        league_id = league_id_map.get(league_code, 1) if league_code else 1

        # 解析赛季
        season = parse_season_from_filename(filename)

        try:
            # 读取CSV
            df = pd.read_csv(filepath, encoding='utf-8', low_memory=False)
        except:
            try:
                df = pd.read_csv(filepath, encoding='latin-1', low_memory=False)
            except Exception as e:
                continue

        # 查找球队列
        home_col = None
        away_col = None
        for col in ['HomeTeam', 'home_team', 'Home', 'home_team_name']:
            if col in df.columns:
                home_col = col
                break
        for col in ['AwayTeam', 'away_team', 'Away', 'away_team_name']:
            if col in df.columns:
                away_col = col
                break

        if not home_col or not away_col:
            continue

        # 查找日期列
        date_col = None
        for col in ['Date', 'date', 'match_date']:
            if col in df.columns:
                date_col = col
                break

        # 导入比赛数据
        for _, row in df.iterrows():
            try:
                home_team = str(row[home_col]).strip() if pd.notna(row[home_col]) else None
                away_team = str(row[away_col]).strip() if pd.notna(row[away_col]) else None

                if not home_team or not away_team or home_team == 'nan' or away_team == 'nan':
                    skipped_matches += 1
                    continue

                # 获取team_id
                home_canonical = name_to_id.get(home_team, home_team)
                away_canonical = name_to_id.get(away_team, away_team)

                # 如果canonical_name是数字，说明是team_id
                if isinstance(home_canonical, str):
                    home_team_id = None
                    cursor.execute('SELECT team_id FROM teams WHERE canonical_name = ?', (home_canonical,))
                    result = cursor.fetchone()
                    if result:
                        home_team_id = result[0]
                    else:
                        # 创建新球队
                        cursor.execute('''
                            INSERT INTO teams (canonical_name, team_type)
                            VALUES (?, 'club')
                        ''', (home_canonical,))
                        home_team_id = cursor.lastrowid
                        name_to_id[home_canonical] = home_team_id
                else:
                    home_team_id = home_canonical

                if isinstance(away_canonical, str):
                    away_team_id = None
                    cursor.execute('SELECT team_id FROM teams WHERE canonical_name = ?', (away_canonical,))
                    result = cursor.fetchone()
                    if result:
                        away_team_id = result[0]
                    else:
                        cursor.execute('''
                            INSERT INTO teams (canonical_name, team_type)
                            VALUES (?, 'club')
                        ''', (away_canonical,))
                        away_team_id = cursor.lastrowid
                        name_to_id[away_canonical] = away_team_id
                else:
                    away_team_id = away_canonical

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

                # 插入比赛
                cursor.execute('''
                    INSERT INTO matches (
                        league_id, home_team_id, away_team_id, match_date,
                        home_goals, away_goals, home_half_goals, away_half_goals,
                        home_shots, away_shots, home_shots_target, away_shots_target,
                        home_corners, away_corners, home_fouls, away_fouls,
                        home_yellow, away_yellow, home_red, away_red,
                        attendance, home_odds, draw_odds, away_odds, referee,
                        original_home_team, original_away_team
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    league_id, home_team_id, away_team_id, match_date,
                    home_goals, away_goals, home_half_goals, away_half_goals,
                    home_shots, away_shots, home_shots_target, away_shots_target,
                    home_corners, away_corners, home_fouls, away_fouls,
                    home_yellow, away_yellow, home_red, away_red,
                    attendance, home_odds, draw_odds, away_odds, referee,
                    home_team, away_team
                ))

                total_matches += 1

            except Exception as e:
                skipped_matches += 1
                continue

        # 定期提交
        if (i + 1) % 100 == 0:
            conn.commit()
            print(f"已处理 {i + 1}/{len(csv_files)} 个文件，导入 {total_matches} 场比赛")

    conn.commit()
    print(f"\n导入完成: {total_matches} 场比赛，跳过 {skipped_matches} 场")

    return total_matches


def import_fifa_rankings(conn):
    """导入FIFA排名数据"""
    cursor = conn.cursor()

    # 国家队排名
    fifa_file = f'{DATA_DIR}/fifa_rankings/fifa_world_ranking_complete_2000_2026.csv'
    if os.path.exists(fifa_file):
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
    club_file = f'{DATA_DIR}/fifa_rankings/fifa_club_rankings_2000_2026.csv'
    if os.path.exists(club_file):
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


def create_views(conn):
    """创建常用查询视图"""
    cursor = conn.cursor()

    print("创建视图...")

    # 球队比赛统计视图
    cursor.execute('''
    CREATE VIEW IF NOT EXISTS v_team_matches AS
    SELECT
        m.match_id,
        m.match_date,
        l.name as league_name,
        l.country as league_country,
        CASE WHEN m.home_team_id = t.team_id THEN 'H' ELSE 'A' END as venue,
        t.canonical_name as team_name,
        CASE WHEN m.home_team_id = t.team_id THEN m.away_team_id ELSE m.home_team_id END as opponent_id,
        ot.canonical_name as opponent_name,
        CASE WHEN m.home_team_id = t.team_id THEN m.home_goals ELSE m.away_goals END as goals_for,
        CASE WHEN m.home_team_id = t.team_id THEN m.away_goals ELSE m.home_goals END as goals_against,
        CASE
            WHEN (m.home_team_id = t.team_id AND m.home_goals > m.away_goals) THEN 'W'
            WHEN (m.away_team_id = t.team_id AND m.away_goals > m.home_goals) THEN 'W'
            WHEN m.home_goals = m.away_goals THEN 'D'
            ELSE 'L'
        END as result,
        m.home_odds,
        m.draw_odds,
        m.away_odds
    FROM matches m
    CROSS JOIN teams t
    JOIN teams ot ON (
        CASE WHEN m.home_team_id = t.team_id THEN m.away_team_id ELSE m.home_team_id END = ot.team_id
    )
    JOIN leagues l ON m.league_id = l.league_id
    WHERE t.team_id IN (m.home_team_id, m.away_team_id)
    ''')

    # 球队统计汇总视图
    cursor.execute('''
    CREATE VIEW IF NOT EXISTS v_team_stats AS
    SELECT
        t.team_id,
        t.canonical_name as team_name,
        t.team_type,
        t.country,
        COUNT(*) as total_matches,
        SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN result = 'D' THEN 1 ELSE 0 END) as draws,
        SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) as losses,
        SUM(goals_for) as goals_for,
        SUM(goals_against) as goals_against,
        ROUND(AVG(goals_for), 2) as avg_goals_for,
        ROUND(AVG(goals_against), 2) as avg_goals_against,
        ROUND(SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as win_rate
    FROM v_team_matches vm
    JOIN teams t ON vm.team_id = t.team_id
    GROUP BY t.team_id, t.canonical_name, t.team_type, t.country
    ''')

    # 联赛统计视图
    cursor.execute('''
    CREATE VIEW IF NOT EXISTS v_league_stats AS
    SELECT
        l.league_id,
        l.name as league_name,
        l.country,
        l.tier,
        COUNT(*) as total_matches,
        COUNT(DISTINCT m.home_team_id) as home_teams,
        SUM(m.home_goals) as total_home_goals,
        SUM(m.away_goals) as total_away_goals,
        ROUND(AVG(m.home_goals), 2) as avg_home_goals,
        ROUND(AVG(m.away_goals), 2) as avg_away_goals,
        MIN(m.match_date) as first_match,
        MAX(m.match_date) as last_match
    FROM matches m
    JOIN leagues l ON m.league_id = l.league_id
    GROUP BY l.league_id, l.name, l.country, l.tier
    ''')

    conn.commit()
    print("视图创建完成")


def main():
    print("=" * 60)
    print("构建统一足球数据库")
    print("=" * 60)

    # 1. 创建数据库
    print("\n[步骤1] 创建数据库...")
    conn = create_database()

    # 2. 导入联赛
    print("\n[步骤2] 导入联赛数据...")
    league_id_map = import_leagues(conn)
    print(f"导入 {len(league_id_map)} 个联赛")

    # 3. 加载球队映射
    print("\n[步骤3] 加载球队映射...")
    name_to_id = load_team_mapping(conn)
    print(f"加载 {len(name_to_id)} 个球队映射")

    # 4. 导入比赛数据
    print("\n[步骤4] 导入比赛数据...")
    total_matches = import_matches(conn, name_to_id, league_id_map)

    # 5. 导入FIFA排名
    print("\n[步骤5] 导入FIFA排名...")
    import_fifa_rankings(conn)

    # 6. 创建视图
    print("\n[步骤6] 创建视图...")
    create_views(conn)

    # 7. 统计报告
    print("\n" + "=" * 60)
    print("数据库构建完成")
    print("=" * 60)

    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM teams')
    teams_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches')
    matches_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM leagues')
    leagues_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM fifa_rankings')
    fifa_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM fifa_club_rankings')
    fifa_club_count = cursor.fetchone()[0]

    print(f"球队数: {teams_count}")
    print(f"比赛数: {matches_count}")
    print(f"联赛数: {leagues_count}")
    print(f"FIFA国家队排名: {fifa_count} 条")
    print(f"FIFA俱乐部排名: {fifa_club_count} 条")
    print(f"\n数据库位置: {OUTPUT_DB}")

    conn.close()

    print("\n完成！")


if __name__ == '__main__':
    main()
