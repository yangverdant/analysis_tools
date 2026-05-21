#!/usr/bin/env python3
"""
从StatsBomb JSON导入缺失的比赛到matches表
"""

import sqlite3
import json
import os
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'd:/football_tools/data/football_v2.db'
STATSBOOM_MATCHES_PATH = 'd:/football_tools/new_data/matches/clubs/leagues/StatsBomb_matches/'

# StatsBomb competition_id -> 数据库 league_id 映射
COMPETITION_MAPPING = {
    11: 21,      # La Liga
    1238: 41,    # Indian Super League (新建)
    1267: 2,     # African Cup of Nations
    223: 12,     # Copa America
    43: 40,      # FIFA World Cup
    44: 26,      # MLS
    55: 15,      # UEFA Euro
    7: 24,       # Ligue 1
    9: 7,        # Bundesliga
}

def get_or_create_season(cursor, season_name, league_id):
    """获取或创建赛季，返回season_id (整数)"""
    # 解析赛季名称获取年份
    # 例如 "2019/2020" -> 2019 或 2020
    if '/' in season_name:
        year = int(season_name.split('/')[0])
    else:
        year = int(season_name)

    # 查找现有赛季
    cursor.execute('''
        SELECT season_id FROM seasons
        WHERE league_id = ? AND (season_name = ? OR year = ?)
    ''', (league_id, season_name, year))
    row = cursor.fetchone()
    if row:
        return row[0]

    # 创建新赛季
    cursor.execute('SELECT MAX(season_id) FROM seasons')
    max_id = cursor.fetchone()[0] or 0
    new_season_id = max_id + 1

    cursor.execute('''
        INSERT INTO seasons (season_id, league_id, season_name, year)
        VALUES (?, ?, ?, ?)
    ''', (new_season_id, league_id, season_name, year))
    return new_season_id

def get_or_create_team(cursor, sb_team_id, team_name, team_type='club'):
    """获取或创建球队，返回team_id (整数)"""
    # 先通过StatsBomb ID查找
    cursor.execute('SELECT team_id FROM teams WHERE sb_team_id = ?', (str(sb_team_id),))
    row = cursor.fetchone()
    if row:
        return row[0]

    # 通过名称查找
    cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
    row = cursor.fetchone()
    if row:
        # 更新sb_team_id
        cursor.execute('UPDATE teams SET sb_team_id = ? WHERE team_id = ?',
                       (str(sb_team_id), row[0]))
        return row[0]

    # 创建新球队
    cursor.execute('SELECT MAX(team_id) FROM teams')
    max_id = cursor.fetchone()[0] or 0
    new_team_id = max_id + 1

    cursor.execute('''
        INSERT INTO teams (team_id, name_en, name_cn, team_type, sb_team_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (new_team_id, team_name, team_name, team_type, str(sb_team_id)))
    return new_team_id

def import_matches():
    """导入StatsBomb比赛"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stats = {
        'total_matches': 0,
        'imported': 0,
        'skipped': 0,
        'leagues_created': 0,
        'teams_created': 0,
    }

    # 遍历StatsBomb matches目录
    for competition_id in os.listdir(STATSBOOM_MATCHES_PATH):
        comp_path = os.path.join(STATSBOOM_MATCHES_PATH, competition_id)
        if not os.path.isdir(comp_path):
            continue

        try:
            comp_id_int = int(competition_id)
        except ValueError:
            continue

        if comp_id_int not in COMPETITION_MAPPING:
            print(f"跳过未知联赛ID: {competition_id}")
            continue

        league_id = COMPETITION_MAPPING[comp_id_int]

        for season_file in os.listdir(comp_path):
            if not season_file.endswith('.json'):
                continue

            file_path = os.path.join(comp_path, season_file)
            print(f"\n处理: {file_path}")

            with open(file_path, 'r', encoding='utf-8') as f:
                matches = json.load(f)

            if not matches:
                continue

            # 获取联赛信息
            comp_info = matches[0].get('competition', {})
            comp_name = comp_info.get('competition_name', '')

            # 确保联赛存在
            cursor.execute('SELECT league_id FROM leagues WHERE league_id = ?', (league_id,))
            if not cursor.fetchone():
                league_cn_map = {
                    41: '印度超级联赛',
                    21: '西甲',
                    24: '法甲',
                    7: '德甲',
                    15: '欧洲杯',
                    40: '世界杯',
                    12: '美洲杯',
                    2: '非洲杯',
                    26: '美职联',
                }
                print(f"  创建联赛: {league_id} ({comp_name})")
                is_intl = 1 if comp_id_int in [55, 43, 223, 1267] else 0
                cursor.execute('''
                    INSERT INTO leagues (league_id, name_en, name_cn, is_international)
                    VALUES (?, ?, ?, ?)
                ''', (league_id, comp_name, league_cn_map.get(league_id, comp_name), is_intl))
                stats['leagues_created'] += 1

            for match in matches:
                stats['total_matches'] += 1

                sb_match_id = match.get('match_id')
                match_date = match.get('match_date')
                season_info = match.get('season', {})
                season_name = season_info.get('season_name', '')

                # 创建赛季
                season_id = get_or_create_season(cursor, season_name, league_id)

                # 获取球队信息
                home_team_info = match.get('home_team', {})
                away_team_info = match.get('away_team', {})

                home_team_id = get_or_create_team(cursor,
                    home_team_info.get('home_team_id'),
                    home_team_info.get('home_team_name'),
                    'club' if comp_id_int in [11, 7, 9, 1238, 44] else 'national')

                away_team_id = get_or_create_team(cursor,
                    away_team_info.get('away_team_id'),
                    away_team_info.get('away_team_name'),
                    'club' if comp_id_int in [11, 7, 9, 1238, 44] else 'national')

                # 检查是否已存在（通过sb_match_id）
                cursor.execute('SELECT match_id FROM matches WHERE sb_match_id = ?', (sb_match_id,))
                if cursor.fetchone():
                    stats['skipped'] += 1
                    continue

                # 插入比赛
                home_score = match.get('home_score')
                away_score = match.get('away_score')
                kick_off = match.get('kick_off', '')
                match_week = match.get('match_week')
                stadium_info = match.get('stadium', {})
                stadium_name = stadium_info.get('name', '')

                status = 'finished' if home_score is not None else 'scheduled'

                # 生成match_id (文本)
                new_match_id = f"{league_id}_{match_date}_{home_team_id}_vs_{away_team_id}"

                cursor.execute('''
                    INSERT INTO matches (
                        match_id, league_id, season_id, match_date, match_time,
                        home_team_id, away_team_id, home_goals, away_goals,
                        status, round_num, venue, sb_match_id,
                        sb_home_team_id, sb_away_team_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    new_match_id, league_id, season_id, match_date,
                    kick_off[:5] if kick_off else None,
                    home_team_id, away_team_id, home_score, away_score,
                    status, match_week, stadium_name, sb_match_id,
                    str(home_team_info.get('home_team_id')),
                    str(away_team_info.get('away_team_id'))
                ))
                stats['imported'] += 1

    conn.commit()
    conn.close()

    print("\n" + "=" * 50)
    print("导入完成!")
    print(f"  总比赛数: {stats['total_matches']}")
    print(f"  已导入: {stats['imported']}")
    print(f"  已跳过(已存在): {stats['skipped']}")
    print(f"  新建联赛: {stats['leagues_created']}")
    print("=" * 50)

if __name__ == '__main__':
    import_matches()
