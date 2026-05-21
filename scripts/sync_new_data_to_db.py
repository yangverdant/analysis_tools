"""
同步new_data数据到数据库
将new_data目录下的所有CSV数据导入到football_unified.db
"""
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

# 路径配置
NEW_DATA_DIR = Path('d:/football_tools/new_data')
DB_PATH = Path('d:/football_tools/data/football_unified.db')

# 联赛映射
LEAGUE_MAPPING = {
    'premier_league': ('Premier League', '英超', 'England', 1),
    'championship': ('Championship', '英冠', 'England', 2),
    'league_one': ('League One', '英甲', 'England', 3),
    'league_two': ('League Two', '英乙', 'England', 4),
    'bundesliga': ('Bundesliga', '德甲', 'Germany', 1),
    'bundesliga_2': ('Bundesliga 2', '德乙', 'Germany', 2),
    'bundesliga_3': ('3. Liga', '德丙', 'Germany', 3),
    'la_liga': ('La Liga', '西甲', 'Spain', 1),
    'segunda_division': ('Segunda Division', '西乙', 'Spain', 2),
    'serie_a': ('Serie A', '意甲', 'Italy', 1),
    'serie_b': ('Serie B', '意乙', 'Italy', 2),
    'ligue_1': ('Ligue 1', '法甲', 'France', 1),
    'ligue_2': ('Ligue 2', '法乙', 'France', 2),
    'eredivisie': ('Eredivisie', '荷甲', 'Netherlands', 1),
    'primeira_liga': ('Primeira Liga', '葡超', 'Portugal', 1),
    'jupiler_league': ('Belgian Pro League', '比甲', 'Belgium', 1),
    'super_lig': ('Super Lig', '土超', 'Turkey', 1),
    'superleague': ('Super League', '希腊超', 'Greece', 1),
    'scotland_premier': ('Scottish Premiership', '苏超', 'Scotland', 1),
    'scotland_div1': ('Scottish Championship', '苏冠', 'Scotland', 2),
    'scotland_div2': ('Scottish League One', '苏甲', 'Scotland', 3),
    'scotland_div3': ('Scottish League Two', '苏乙', 'Scotland', 4),
    'bundesliga_austria': ('Austrian Bundesliga', '奥甲', 'Austria', 1),
    'austria_2': ('Austrian 2. Liga', '奥乙', 'Austria', 2),
    'gambrinus_liga': ('Czech First League', '捷甲', 'Czech Republic', 1),
    'nb1': ('NB I', '匈甲', 'Hungary', 1),
    'russia_2': ('Russian First Division', '俄甲', 'Russia', 2),
    'turkey_2': ('TFF First League', '土甲', 'Turkey', 2),
    'swiss_2': ('Swiss Challenge League', '瑞士甲', 'Switzerland', 2),
    'allsvenskan': ('Allsvenskan', '瑞典超', 'Sweden', 1),
    'eliteserien': ('Eliteserien', '挪威超', 'Norway', 1),
    'veikkausliiga': ('Veikkausliiga', '芬兰超', 'Finland', 1),
    'j1_league': ('J1 League', 'J1联赛', 'Japan', 1),
    'j2_league': ('J2 League', 'J2联赛', 'Japan', 2),
    'k1_league': ('K League 1', 'K1联赛', 'South Korea', 1),
    'a_league': ('A-League', '澳超', 'Australia', 1),
    'csl': ('Chinese Super League', '中超', 'China', 1),
    'saudi_pro': ('Saudi Pro League', '沙特超', 'Saudi Arabia', 1),
}

# 国家队赛事映射
INTERNATIONAL_MAPPING = {
    'world_cup': ('World Cup', '世界杯', 'FIFA'),
    'euro': ('European Championship', '欧洲杯', 'UEFA'),
    'copa_america': ('Copa America', '美洲杯', 'CONMEBOL'),
    'africa_cup': ('Africa Cup of Nations', '非洲杯', 'CAF'),
    'asian_cup': ('Asian Cup', '亚洲杯', 'AFC'),
    'friendly': ('International Friendly', '友谊赛', 'FIFA'),
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")  # 关闭外键约束提高导入速度
    return conn


def get_or_create_league(conn, name, name_cn, country, tier=1):
    """获取或创建联赛"""
    cursor = conn.cursor()
    cursor.execute("SELECT league_id FROM leagues WHERE name = ?", (name,))
    result = cursor.fetchone()
    if result:
        return result[0]

    # 生成唯一code
    code = name[:3].upper().replace(' ', '')
    counter = 1
    while True:
        cursor.execute("SELECT league_id FROM leagues WHERE league_code = ?", (code,))
        if not cursor.fetchone():
            break
        code = f"{name[:3].upper()}{counter}"
        counter += 1

    cursor.execute(
        "INSERT INTO leagues (league_code, name, name_cn, country, tier, league_type) VALUES (?, ?, ?, ?, ?, 'league')",
        (code, name, name_cn, country, tier)
    )
    return cursor.lastrowid


def get_or_create_team(conn, name, team_type='club', country=None):
    """获取或创建球队"""
    cursor = conn.cursor()
    cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (name,))
    result = cursor.fetchone()
    if result:
        return result[0]

    cursor.execute(
        "INSERT INTO teams (name_en, team_type, country) VALUES (?, ?, ?)",
        (name, team_type, country)
    )
    return cursor.lastrowid


def get_or_create_season(conn, league_id, season_name):
    """获取或创建赛季"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT season_id FROM seasons WHERE league_id = ? AND season_name = ?",
        (league_id, str(season_name))
    )
    result = cursor.fetchone()
    if result:
        return result[0]

    try:
        year = int(str(season_name).split('-')[0])
    except:
        year = datetime.now().year

    cursor.execute(
        "INSERT INTO seasons (league_id, season_name, year, status) VALUES (?, ?, ?, 'active')",
        (league_id, str(season_name), year)
    )
    return cursor.lastrowid


def parse_date(val):
    if pd.isna(val) or not val:
        return None
    try:
        s = str(val)[:10]
        return s if '-' in s else None
    except:
        return None


def parse_int(val):
    if pd.isna(val) or val == '':
        return None
    try:
        return int(float(val))
    except:
        return None


def parse_float(val):
    if pd.isna(val) or val == '':
        return None
    try:
        return float(val)
    except:
        return None


def import_league_matches(conn, csv_path, league_key):
    """导入联赛比赛"""
    if league_key not in LEAGUE_MAPPING:
        return 0

    name, name_cn, country, tier = LEAGUE_MAPPING[league_key]
    league_id = get_or_create_league(conn, name, name_cn, country, tier)

    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
    except:
        try:
            df = pd.read_csv(csv_path, encoding='latin-1')
        except:
            return 0

    if df.empty:
        return 0

    cursor = conn.cursor()
    imported = 0

    for _, row in df.iterrows():
        try:
            match_date = parse_date(row.get('match_date'))
            home_team = str(row.get('home_team', '')).strip()
            away_team = str(row.get('away_team', '')).strip()

            if not match_date or not home_team or not away_team:
                continue

            home_team_id = get_or_create_team(conn, home_team, 'club', country)
            away_team_id = get_or_create_team(conn, away_team, 'club', country)

            season = str(row.get('season', ''))
            if not season or season == 'nan':
                season = f"{datetime.now().year}-{datetime.now().year + 1}"

            season_id = get_or_create_season(conn, league_id, season)

            # 检查重复
            cursor.execute("""
                SELECT match_id FROM matches
                WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
            """, (match_date, home_team_id, away_team_id))
            if cursor.fetchone():
                continue

            cursor.execute("""
                INSERT INTO matches (
                    season_id, league_id, match_date, match_time, round_stage,
                    home_team_id, away_team_id, home_goals, away_goals, result,
                    home_goals_ht, away_goals_ht, result_ht,
                    home_shots, away_shots, home_shots_target, away_shots_target,
                    home_corners, away_corners, home_fouls, away_fouls,
                    home_yellow, away_yellow, home_red, away_red,
                    home_odds, draw_odds, away_odds, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                season_id, league_id, match_date,
                str(row.get('match_time', '')) if pd.notna(row.get('match_time')) else None,
                str(row.get('round_num', '')) if pd.notna(row.get('round_num')) else None,
                home_team_id, away_team_id,
                parse_int(row.get('home_goals')), parse_int(row.get('away_goals')),
                str(row.get('result', '')) if pd.notna(row.get('result')) else None,
                parse_int(row.get('home_goals_ht')), parse_int(row.get('away_goals_ht')),
                str(row.get('result_ht', '')) if pd.notna(row.get('result_ht')) else None,
                parse_int(row.get('home_shots')), parse_int(row.get('away_shots')),
                parse_int(row.get('home_shots_target')), parse_int(row.get('away_shots_target')),
                parse_int(row.get('home_corners')), parse_int(row.get('away_corners')),
                parse_int(row.get('home_fouls')), parse_int(row.get('away_fouls')),
                parse_int(row.get('home_yellow')), parse_int(row.get('away_yellow')),
                parse_int(row.get('home_red')), parse_int(row.get('away_red')),
                parse_float(row.get('home_odds')), parse_float(row.get('draw_odds')),
                parse_float(row.get('away_odds')), 'finished'
            ))
            imported += 1
        except:
            continue

    return imported


def import_international_matches(conn, csv_path, comp_key):
    """导入国家队比赛"""
    if comp_key not in INTERNATIONAL_MAPPING:
        return 0

    name, name_cn, organizer = INTERNATIONAL_MAPPING[comp_key]
    league_id = get_or_create_league(conn, name, name_cn, organizer, 0)

    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
    except:
        try:
            df = pd.read_csv(csv_path, encoding='latin-1')
        except:
            return 0

    if df.empty:
        return 0

    cursor = conn.cursor()
    imported = 0

    for _, row in df.iterrows():
        try:
            match_date = parse_date(row.get('match_date'))
            home_team = str(row.get('home_team', '')).strip()
            away_team = str(row.get('away_team', '')).strip()

            if not match_date or not home_team or not away_team:
                continue

            home_team_id = get_or_create_team(conn, home_team, 'national', None)
            away_team_id = get_or_create_team(conn, away_team, 'national', None)

            season = str(row.get('season', ''))
            if not season or season == 'nan':
                season = str(row.get('competition', datetime.now().year))

            season_id = get_or_create_season(conn, league_id, season)

            cursor.execute("""
                SELECT match_id FROM matches
                WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
            """, (match_date, home_team_id, away_team_id))
            if cursor.fetchone():
                continue

            cursor.execute("""
                INSERT INTO matches (
                    season_id, league_id, match_date, match_time, round_stage,
                    home_team_id, away_team_id, home_goals, away_goals, result,
                    home_goals_ht, away_goals_ht, result_ht,
                    home_goals_et, away_goals_et,
                    home_penalties, away_penalties,
                    home_shots, away_shots, home_shots_target, away_shots_target,
                    home_corners, away_corners, home_fouls, away_fouls,
                    home_yellow, away_yellow, home_red, away_red,
                    neutral, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                season_id, league_id, match_date,
                str(row.get('match_time', '')) if pd.notna(row.get('match_time')) else None,
                str(row.get('round', '')) if pd.notna(row.get('round')) else None,
                home_team_id, away_team_id,
                parse_int(row.get('home_goals')), parse_int(row.get('away_goals')),
                str(row.get('result', '')) if pd.notna(row.get('result')) else None,
                parse_int(row.get('home_goals_ht')), parse_int(row.get('away_goals_ht')),
                str(row.get('result_ht', '')) if pd.notna(row.get('result_ht')) else None,
                parse_int(row.get('home_goals_et')), parse_int(row.get('away_goals_et')),
                parse_int(row.get('home_penalties')), parse_int(row.get('away_penalties')),
                parse_int(row.get('home_shots')), parse_int(row.get('away_shots')),
                parse_int(row.get('home_shots_target')), parse_int(row.get('away_shots_target')),
                parse_int(row.get('home_corners')), parse_int(row.get('away_corners')),
                parse_int(row.get('home_fouls')), parse_int(row.get('away_fouls')),
                parse_int(row.get('home_yellow')), parse_int(row.get('away_yellow')),
                parse_int(row.get('home_red')), parse_int(row.get('away_red')),
                1 if row.get('neutral', False) else 0, 'finished'
            ))
            imported += 1
        except:
            continue

    return imported


def sync_all():
    """同步所有数据"""
    print("=" * 60)
    print(f"同步new_data到数据库 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    conn = get_db()

    # 同步联赛
    print("\n同步联赛数据...")
    leagues_dir = NEW_DATA_DIR / 'matches' / 'clubs' / 'leagues'
    total_league = 0

    if leagues_dir.exists():
        for league_dir in sorted(leagues_dir.iterdir()):
            if not league_dir.is_dir():
                continue
            league_key = league_dir.name
            csv_files = list(league_dir.glob('*.csv'))
            if csv_files:
                league_total = 0
                for csv_file in csv_files:
                    count = import_league_matches(conn, csv_file, league_key)
                    league_total += count
                if league_total > 0:
                    print(f"  {league_key}: {league_total} 场")
                    total_league += league_total

    print(f"\n  联赛总计: {total_league} 场")

    # 同步国家队
    print("\n同步国家队数据...")
    intl_dir = NEW_DATA_DIR / 'matches' / 'international'
    total_intl = 0

    if intl_dir.exists():
        for comp_dir in sorted(intl_dir.iterdir()):
            if not comp_dir.is_dir():
                continue
            comp_key = comp_dir.name
            csv_files = list(comp_dir.glob('*.csv'))
            if csv_files:
                comp_total = 0
                for csv_file in csv_files:
                    count = import_international_matches(conn, csv_file, comp_key)
                    comp_total += count
                if comp_total > 0:
                    print(f"  {comp_key}: {comp_total} 场")
                    total_intl += comp_total

    print(f"\n  国家队总计: {total_intl} 场")

    conn.commit()

    # 统计
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM matches")
    total_matches = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM teams")
    total_teams = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM leagues")
    total_leagues = cursor.fetchone()[0]

    conn.close()

    print("\n" + "=" * 60)
    print(f"同步完成!")
    print(f"  本次导入: {total_league + total_intl} 场比赛")
    print(f"  数据库总计: {total_matches} 场比赛, {total_teams} 支球队, {total_leagues} 个联赛")
    print("=" * 60)


if __name__ == '__main__':
    sync_all()
