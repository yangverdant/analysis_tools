#!/usr/bin/env python3
"""
导入 last_data 数据到 football_v2.db - 简化版
只处理近3年数据（2023-2026）
"""

import os
import csv
import sqlite3
from datetime import datetime
from collections import defaultdict

# 配置
DB_PATH = 'd:/football_tools/data/football_v2.db'
DATA_DIR = 'd:/football_tools/last_data'
MIN_YEAR = 2023

# 联赛配置
LEAGUE_CONFIG = {
    'premier_league': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'England', 'cn': '英超'},
    'la_liga': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Spain', 'cn': '西甲'},
    'bundesliga': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Germany', 'cn': '德甲'},
    'serie_a': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Italy', 'cn': '意甲'},
    'ligue_1': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'France', 'cn': '法甲'},
    'championship': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'England', 'cn': '英冠', 'tier': 2},
    'bundesliga_2': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Germany', 'cn': '德乙', 'tier': 2},
    'serie_b': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Italy', 'cn': '意乙', 'tier': 2},
    'ligue_2': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'France', 'cn': '法乙', 'tier': 2},
    'segunda_division': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Spain', 'cn': '西乙', 'tier': 2},
    'eredivisie': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Netherlands', 'cn': '荷甲'},
    'primeira_liga': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Portugal', 'cn': '葡超'},
    'jupiler_league': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Belgium', 'cn': '比甲'},
    'scotland_premiership': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Scotland', 'cn': '苏超'},
    'a_league': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Australia', 'cn': '澳超'},
    'allsvenskan': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Sweden', 'cn': '瑞典超'},
    'austrian_bundesliga': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Austria', 'cn': '奥超'},
    'danish_superliga': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Denmark', 'cn': '丹超'},
    'greek_superleague': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Greece', 'cn': '希腊超'},
    'mls': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'USA', 'cn': '美职联'},
    'norwegian_eliteserien': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Norway', 'cn': '挪超'},
    'polish_ekstraklasa': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Poland', 'cn': '波兰超'},
    'swiss_super_league': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Switzerland', 'cn': '瑞士超'},
    'turkish_super_lig': {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Turkey', 'cn': '土超'},
    'world_cup': {'type': 'tournament', 'participant': 'national', 'format': 'group_knockout', 'country': 'World', 'cn': '世界杯', 'intl': 1},
    'euro': {'type': 'tournament', 'participant': 'national', 'format': 'group_knockout', 'country': 'Europe', 'cn': '欧洲杯', 'intl': 1},
    'copa_america': {'type': 'tournament', 'participant': 'national', 'format': 'group_knockout', 'country': 'South America', 'cn': '美洲杯', 'intl': 1},
    'africa_cup': {'type': 'tournament', 'participant': 'national', 'format': 'group_knockout', 'country': 'Africa', 'cn': '非洲杯', 'intl': 1},
    'asian_cup': {'type': 'tournament', 'participant': 'national', 'format': 'group_knockout', 'country': 'Asia', 'cn': '亚洲杯', 'intl': 1},
    'friendly': {'type': 'friendly', 'participant': 'national', 'format': 'friendly', 'country': 'World', 'cn': '国际友谊赛', 'intl': 1},
}


def safe_int(val):
    if val is None or val in ('', 'null', 'NULL', 'None'):
        return None
    try:
        return int(float(val))
    except:
        return None


def safe_float(val):
    if val is None or val in ('', 'null', 'NULL', 'None'):
        return None
    try:
        return float(val)
    except:
        return None


def read_csv(filepath):
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def import_data():
    print("=" * 70)
    print("导入 last_data 数据到 football_v2.db")
    print(f"只处理 {MIN_YEAR} 年及以后的数据")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 读取数据
    print("\n读取CSV文件...")
    matches_csv = read_csv(os.path.join(DATA_DIR, 'matches.csv'))
    match_detail_csv = read_csv(os.path.join(DATA_DIR, 'match_detail.csv'))
    odds_csv = read_csv(os.path.join(DATA_DIR, 'odds.csv'))
    shots_csv = read_csv(os.path.join(DATA_DIR, 'statsbomb_shots.csv'))
    passes_csv = read_csv(os.path.join(DATA_DIR, 'statsbomb_passes.csv'))
    player_csv = read_csv(os.path.join(DATA_DIR, 'statsbomb_player_match.csv'))

    detail_dict = {r['match_id']: r for r in match_detail_csv}
    odds_dict = {r['match_id']: r for r in odds_csv}

    # 筛选近3年数据
    recent_matches = []
    for row in matches_csv:
        season = row.get('season', '')
        date_str = row.get('match_date', '')
        year = None
        if '-' in season:
            try:
                year = int(season.split('-')[0])
            except:
                pass
        elif season:
            try:
                year = int(season)
            except:
                pass
        if date_str:
            try:
                year = int(date_str.split('-')[0])
            except:
                pass
        if year and year >= MIN_YEAR:
            recent_matches.append(row)

    print(f"  筛选后: {len(recent_matches)} 场比赛")

    # 收集实体
    leagues = {}
    teams = {}
    seasons = {}

    for row in recent_matches:
        league_code = row.get('league', '')
        season_name = row.get('season', '')
        home_team = row.get('home_team', '').strip()
        away_team = row.get('away_team', '').strip()

        if league_code and league_code not in leagues:
            cfg = LEAGUE_CONFIG.get(league_code, {'type': 'league', 'participant': 'club', 'format': 'round_robin', 'country': 'Unknown'})
            leagues[league_code] = cfg

        if league_code and season_name and (league_code, season_name) not in seasons:
            seasons[(league_code, season_name)] = True

        if home_team and home_team not in teams:
            teams[home_team] = {'type': 'club'}
        if away_team and away_team not in teams:
            teams[away_team] = {'type': 'club'}

    # 更新国家队类型
    for league_code, cfg in leagues.items():
        if cfg.get('participant') == 'national':
            for row in recent_matches:
                if row.get('league') == league_code:
                    home = row.get('home_team', '').strip()
                    away = row.get('away_team', '').strip()
                    if home in teams:
                        teams[home]['type'] = 'national'
                    if away in teams:
                        teams[away]['type'] = 'national'

    print(f"\n收集到: {len(leagues)} 联赛, {len(seasons)} 赛季, {len(teams)} 球队")

    # 导入联赛
    print("\n导入联赛...")
    league_id_map = {}
    for idx, (code, cfg) in enumerate(sorted(leagues.items()), 1):
        cursor.execute('''
            INSERT OR IGNORE INTO leagues
            (league_id, league_code, name_en, name_cn, country, competition_type, participant_type, format_type, tier, is_international)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (idx, code, code.replace('_', ' ').title(), cfg.get('cn', ''), cfg.get('country', 'Unknown'),
              cfg['type'], cfg['participant'], cfg['format'], cfg.get('tier', 1), cfg.get('intl', 0)))
        league_id_map[code] = idx
    conn.commit()
    print(f"  导入 {len(leagues)} 个联赛")

    # 导入球队
    print("\n导入球队...")
    team_id_map = {}
    for idx, (name, cfg) in enumerate(sorted(teams.items()), 1):
        cursor.execute('''
            INSERT OR IGNORE INTO teams (team_id, name_en, team_type)
            VALUES (?, ?, ?)
        ''', (idx, name, cfg['type']))
        team_id_map[name] = idx
    conn.commit()
    print(f"  导入 {len(teams)} 支球队")

    # 导入赛季
    print("\n导入赛季...")
    season_id_map = {}
    season_keys = list(seasons.keys())
    for idx, key in enumerate(season_keys, 1):
        league_code, season_name = key
        league_id = league_id_map.get(league_code)
        year = None
        if '-' in season_name:
            try:
                year = int(season_name.split('-')[0])
            except:
                pass
        elif season_name:
            try:
                year = int(season_name)
            except:
                pass
        cursor.execute('''
            INSERT OR IGNORE INTO seasons (season_id, league_id, season_name, year)
            VALUES (?, ?, ?, ?)
        ''', (idx, league_id, season_name, year))
        season_id_map[key] = idx
    conn.commit()
    print(f"  导入 {len(seasons)} 个赛季")

    # 导入比赛 - 使用列名映射
    print("\n导入比赛...")
    match_count = 0
    odds_count = 0

    for row in recent_matches:
        match_id = row.get('match_id', '')
        league_code = row.get('league', '')
        season_name = row.get('season', '')
        home_team = row.get('home_team', '').strip()
        away_team = row.get('away_team', '').strip()

        league_id = league_id_map.get(league_code)
        season_id = season_id_map.get((league_code, season_name))
        home_team_id = team_id_map.get(home_team)
        away_team_id = team_id_map.get(away_team)

        if not league_id or not home_team_id or not away_team_id:
            continue

        # 计算result
        hg = safe_int(row.get('home_goals'))
        ag = safe_int(row.get('away_goals'))
        result = None
        if hg is not None and ag is not None:
            if hg > ag:
                result = 'H'
            elif hg < ag:
                result = 'A'
            else:
                result = 'D'

        detail = detail_dict.get(match_id, {})
        odds = odds_dict.get(match_id, {})

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO matches
                (match_id, match_code, season_id, league_id, match_date, match_time, round_num,
                 home_team_id, away_team_id, home_goals, away_goals, result,
                 home_goals_ht, away_goals_ht, status, referee, attendance,
                 home_shots, away_shots, home_shots_target, away_shots_target,
                 home_corners, away_corners, home_fouls, away_fouls,
                 home_yellow, away_yellow, home_red, away_red,
                 home_xg, away_xg,
                 sb_match_id, sb_home_team_id, sb_away_team_id,
                 sb_stadium, sb_home_manager, sb_away_manager,
                 odds_home, odds_draw, odds_away)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                match_id, match_id, season_id, league_id,
                row.get('match_date'), row.get('match_time'), safe_int(row.get('round')),
                home_team_id, away_team_id, hg, ag, result,
                safe_int(row.get('home_goals_ht')), safe_int(row.get('away_goals_ht')),
                row.get('status', 'finished'), row.get('referee'), safe_int(row.get('attendance')),
                safe_int(detail.get('home_shots')), safe_int(detail.get('away_shots')),
                safe_int(detail.get('home_shots_target')), safe_int(detail.get('away_shots_target')),
                safe_int(detail.get('home_corners')), safe_int(detail.get('away_corners')),
                safe_int(detail.get('home_fouls')), safe_int(detail.get('away_fouls')),
                safe_int(detail.get('home_yellow')), safe_int(detail.get('away_yellow')),
                safe_int(detail.get('home_red')), safe_int(detail.get('away_red')),
                safe_float(detail.get('sb_home_xg')), safe_float(detail.get('sb_away_xg')),
                safe_int(detail.get('sb_match_id')),
                detail.get('sb_home_team_id') if detail.get('sb_home_team_id') not in ('null', '') else None,
                detail.get('sb_away_team_id') if detail.get('sb_away_team_id') not in ('null', '') else None,
                detail.get('sb_stadium') if detail.get('sb_stadium') not in ('null', '') else None,
                detail.get('sb_home_manager') if detail.get('sb_home_manager') not in ('null', '') else None,
                detail.get('sb_away_manager') if detail.get('sb_away_manager') not in ('null', '') else None,
                safe_float(odds.get('b365_home')),
                safe_float(odds.get('b365_draw')),
                safe_float(odds.get('b365_away')),
            ))
            match_count += 1

            # 赔率
            if odds and any(odds.get(k) and odds.get(k) not in ('null', '') for k in ['b365_home', 'ps_home', 'max_home']):
                cursor.execute('''
                    INSERT OR REPLACE INTO match_odds
                    (match_id, b365_home, b365_draw, b365_away, ps_home, ps_draw, ps_away,
                     max_home, max_draw, max_away, avg_home, avg_draw, avg_away,
                     b365_over_2_5, b365_under_2_5, asian_handicap,
                     b365_ah_home, b365_ah_away)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_id,
                    safe_float(odds.get('b365_home')), safe_float(odds.get('b365_draw')), safe_float(odds.get('b365_away')),
                    safe_float(odds.get('ps_home')), safe_float(odds.get('ps_draw')), safe_float(odds.get('ps_away')),
                    safe_float(odds.get('max_home')), safe_float(odds.get('max_draw')), safe_float(odds.get('max_away')),
                    safe_float(odds.get('avg_home')), safe_float(odds.get('avg_draw')), safe_float(odds.get('avg_away')),
                    safe_float(odds.get('b365_over_2_5')), safe_float(odds.get('b365_under_2_5')),
                    safe_float(odds.get('asian_handicap')),
                    safe_float(odds.get('b365_ah_home')), safe_float(odds.get('b365_ah_away')),
                ))
                odds_count += 1
        except Exception as e:
            if match_count < 10:
                print(f"  错误: {match_id} - {e}")

    conn.commit()
    print(f"  导入 {match_count} 场比赛, {odds_count} 条赔率")

    # 导入射门数据
    print("\n导入射门数据...")
    shot_count = 0
    for row in shots_csv:
        try:
            cursor.execute('''
                INSERT INTO statsbomb_shots
                (match_id, sb_match_id, team_name, player_id, player_name,
                 minute, second, period, xg, shot_type, shot_outcome,
                 shot_technique, body_part, location_x, location_y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row.get('match_id'), safe_int(row.get('sb_match_id')),
                row.get('team_name') if row.get('team_name') != 'null' else None,
                row.get('player_id') if row.get('player_id') != 'null' else None,
                row.get('player_name') if row.get('player_name') != 'null' else None,
                safe_int(row.get('minute')), safe_int(row.get('second')), safe_int(row.get('period')),
                safe_float(row.get('xg')),
                row.get('shot_type') if row.get('shot_type') != 'null' else None,
                row.get('shot_outcome') if row.get('shot_outcome') != 'null' else None,
                row.get('shot_technique') if row.get('shot_technique') != 'null' else None,
                row.get('body_part') if row.get('body_part') != 'null' else None,
                safe_float(row.get('location_x')), safe_float(row.get('location_y')),
            ))
            shot_count += 1
        except:
            pass
    conn.commit()
    print(f"  导入 {shot_count} 条射门记录")

    # 导入传球数据
    print("\n导入传球数据...")
    pass_count = 0
    for row in passes_csv:
        try:
            cursor.execute('''
                INSERT INTO statsbomb_passes
                (match_id, sb_match_id, team_name, player_id, player_name,
                 minute, second, period, pass_type, pass_outcome, pass_length,
                 pass_angle, pass_height, location_x, location_y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row.get('match_id'), safe_int(row.get('sb_match_id')),
                row.get('team_name') if row.get('team_name') != 'null' else None,
                row.get('player_id') if row.get('player_id') != 'null' else None,
                row.get('player_name') if row.get('player_name') != 'null' else None,
                safe_int(row.get('minute')), safe_int(row.get('second')), safe_int(row.get('period')),
                row.get('pass_type') if row.get('pass_type') != 'null' else None,
                row.get('pass_outcome') if row.get('pass_outcome') != 'null' else None,
                safe_float(row.get('pass_length')), safe_float(row.get('pass_angle')),
                row.get('pass_height') if row.get('pass_height') != 'null' else None,
                safe_float(row.get('location_x')), safe_float(row.get('location_y')),
            ))
            pass_count += 1
        except:
            pass
    conn.commit()
    print(f"  导入 {pass_count} 条传球记录")

    # 导入球员统计
    print("\n导入球员统计...")
    player_count = 0
    for row in player_csv:
        try:
            cursor.execute('''
                INSERT INTO player_match_stats
                (match_id, sb_match_id, team_name, player_id, player_name,
                 jersey_number, position, passes, pass_complete, pass_completion_rate,
                 shots, shots_on_target, xg, pressures, interceptions, clearances,
                 blocks, carries, dribbles_success, dribbles_attempted,
                 fouls_committed, fouls_won, dispossessed, miscontrol, ball_recovery,
                 assists, key_passes, crosses, yellow_card, red_card, minutes_played)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row.get('match_id'), safe_int(row.get('sb_match_id')),
                row.get('team_name') if row.get('team_name') != 'null' else None,
                row.get('player_id') if row.get('player_id') != 'null' else None,
                row.get('player_name') if row.get('player_name') != 'null' else None,
                safe_int(row.get('jersey_number')),
                row.get('position') if row.get('position') != 'null' else None,
                safe_int(row.get('passes')), safe_int(row.get('pass_complete')),
                safe_float(row.get('pass_completion_rate')),
                safe_int(row.get('shots')), safe_int(row.get('shots_on_target')),
                safe_float(row.get('xg')), safe_int(row.get('pressures')),
                safe_int(row.get('interceptions')), safe_int(row.get('clearances')),
                safe_int(row.get('blocks')), safe_int(row.get('carries')),
                safe_int(row.get('dribbles_success')), safe_int(row.get('dribbles_attempted')),
                safe_int(row.get('fouls_committed')), safe_int(row.get('fouls_won')),
                safe_int(row.get('dispossessed')), safe_int(row.get('miscontrol')),
                safe_int(row.get('ball_recovery')), safe_int(row.get('assists')),
                safe_int(row.get('key_passes')), safe_int(row.get('crosses')),
                safe_int(row.get('yellow_card')), safe_int(row.get('red_card')),
                safe_float(row.get('minutes_played')),
            ))
            player_count += 1
        except:
            pass
    conn.commit()
    print(f"  导入 {player_count} 条球员统计")

    # 统计
    print("\n" + "=" * 70)
    print("导入完成！数据库统计：")
    print("=" * 70)

    for table in ['leagues', 'seasons', 'teams', 'matches', 'match_odds',
                  'statsbomb_shots', 'statsbomb_passes', 'player_match_stats']:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {cursor.fetchone()[0]} 行")

    conn.close()
    print("\n完成！")


if __name__ == '__main__':
    import_data()
