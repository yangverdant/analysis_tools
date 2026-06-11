"""
世界杯数据获取脚本 - 使用API Football
获取2022、2018、2014等世界杯完整数据
"""

import requests
import sqlite3
import json
from datetime import datetime
from pathlib import Path

# 配置
DB_PATH = Path(__file__).parent.parent.parent / 'data' / 'football_v2.db'
CONFIG_PATH = Path(__file__).parent.parent.parent / 'api_config.json'

with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    API_CONFIG = json.load(f)

API_KEY = API_CONFIG['apis']['apifootball']['api_key']
BASE_URL = API_CONFIG['apis']['apifootball']['base_url']

# 世界杯配置
WORLD_CUP_LEAGUES = {
    28: {'name': 'FIFA World Cup', 'name_cn': '世界杯', 'dates': {
        2022: ('2022-11-20', '2022-12-18'),
        2018: ('2018-06-14', '2018-07-15'),
        2014: ('2014-06-12', '2014-07-13'),
        2010: ('2010-06-11', '2010-07-11'),
    }},
    20: {'name': 'FIFA Women\'s World Cup', 'name_cn': '女足世界杯', 'dates': {
        2023: ('2023-07-20', '2023-08-20'),
        2019: ('2019-06-07', '2019-07-07'),
    }},
    8141: {'name': 'FIFA Club World Cup', 'name_cn': '世俱杯', 'dates': {
        2023: ('2023-12-12', '2023-12-22'),
        2022: ('2023-02-01', '2023-02-11'),
    }}
}


def api_request(action, params=None):
    """发送API请求"""
    url = f"{BASE_URL}/"
    query = {'action': action, 'APIkey': API_KEY}
    if params:
        query.update(params)

    try:
        resp = requests.get(url, params=query, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, list) else []
        print(f"API error: {resp.status_code}")
        return []
    except Exception as e:
        print(f"Request failed: {e}")
        return []


def get_or_create_team(cursor, team_name, country='International'):
    """获取或创建球队"""
    cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute('''
        INSERT INTO teams (name_en, name_cn, country)
        VALUES (?, '', ?)
    ''', (team_name, country))
    return cursor.lastrowid


def get_or_create_league(cursor, league_id, name, name_cn):
    """获取或创建联赛"""
    cursor.execute('SELECT league_id FROM leagues WHERE league_id = ?', (league_id,))
    if cursor.fetchone():
        return league_id

    cursor.execute('''
        INSERT INTO leagues (league_id, name_en, name_cn, competition_type)
        VALUES (?, ?, ?, 'cup')
    ''', (league_id, name, name_cn))
    return league_id


def get_or_create_season(cursor, league_id, season_year):
    """获取或创建赛季"""
    season_name = str(season_year)
    cursor.execute('''
        SELECT season_id FROM seasons
        WHERE league_id = ? AND season_name = ?
    ''', (league_id, season_name))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute('''
        INSERT INTO seasons (season_name, league_id)
        VALUES (?, ?)
    ''', (season_name, league_id))
    return cursor.lastrowid


def save_match(cursor, match_data, league_id, season_id):
    """保存比赛数据"""
    match_id = f"wc_{match_data.get('match_id', '')}"
    match_date = match_data.get('match_date', '')
    match_time = match_data.get('match_time', '')
    home_team = match_data.get('match_hometeam_name', '')
    away_team = match_data.get('match_awayteam_name', '')
    home_score = match_data.get('match_hometeam_score')
    away_score = match_data.get('match_awayteam_score')
    home_score_ht = match_data.get('match_hometeam_halftime_score')
    away_score_ht = match_data.get('match_awayteam_halftime_score')
    status = match_data.get('match_status', '')
    round_name = match_data.get('match_round', '')

    # 映射状态
    status_map = {
        'FT': 'finished',
        'Finished': 'finished',
        'NS': 'scheduled',
        'TBD': 'scheduled',
        'Postponed': 'postponed',
        'Cancelled': 'cancelled'
    }
    status = status_map.get(status, status or 'scheduled')

    # 获取球队ID
    home_team_id = get_or_create_team(cursor, home_team)
    away_team_id = get_or_create_team(cursor, away_team)

    # 转换比分
    try:
        home_goals = int(home_score) if home_score not in (None, '', '-') else None
    except:
        home_goals = None
    try:
        away_goals = int(away_score) if away_score not in (None, '', '-') else None
    except:
        away_goals = None
    try:
        home_goals_ht = int(home_score_ht) if home_score_ht not in (None, '', '-') else None
    except:
        home_goals_ht = None
    try:
        away_goals_ht = int(away_score_ht) if away_score_ht not in (None, '', '-') else None
    except:
        away_goals_ht = None

    # 插入或更新
    cursor.execute('''
        INSERT OR REPLACE INTO matches
        (match_id, league_id, season_id, match_date, match_time,
         home_team_id, away_team_id, home_goals, away_goals,
         home_goals_ht, away_goals_ht, status, round_num)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (match_id, league_id, season_id, match_date, match_time,
          home_team_id, away_team_id, home_goals, away_goals,
          home_goals_ht, away_goals_ht, status, round_name))

    return match_id


def fetch_world_cup_data():
    """获取世界杯数据"""
    print("="*60)
    print("世界杯数据获取 (API Football)")
    print("="*60)

    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    total_matches = 0
    saved_matches = 0

    for league_id, info in WORLD_CUP_LEAGUES.items():
        print(f"\n{info['name']} ({info['name_cn']})")

        # 确保联赛存在
        get_or_create_league(cursor, league_id, info['name'], info['name_cn'])

        for year, (from_date, to_date) in info['dates'].items():
            print(f"\n  {year} ({from_date} ~ {to_date})")

            # 获取比赛数据
            matches = api_request('get_events', {
                'league_id': league_id,
                'from': from_date,
                'to': to_date
            })

            if not matches:
                print(f"    未获取到数据")
                continue

            print(f"    获取到 {len(matches)} 场比赛")

            # 创建赛季
            season_id = get_or_create_season(cursor, league_id, year)

            # 保存比赛
            for m in matches:
                try:
                    match_id = save_match(cursor, m, league_id, season_id)
                    saved_matches += 1
                except Exception as e:
                    print(f"    保存失败: {e}")
                total_matches += 1

            conn.commit()
            print(f"    已保存")

    conn.close()

    print(f"\n{'='*60}")
    print(f"完成: 获取 {total_matches} 场, 保存 {saved_matches} 场")
    print(f"{'='*60}")


def print_summary():
    """打印数据概览"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("\n世界杯数据概览:")
    print("-"*60)

    # 按联赛和赛季统计
    cursor.execute('''
        SELECT l.name_cn, s.season_name, COUNT(m.match_id) as matches,
               SUM(CASE WHEN m.status = "finished" THEN 1 ELSE 0 END) as finished,
               SUM(CASE WHEN m.home_goals IS NOT NULL THEN 1 ELSE 0 END) as has_scores
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        JOIN seasons s ON m.season_id = s.season_id
        WHERE l.name_cn IN ('世界杯', '女足世界杯', '世俱杯')
           OR l.name_en LIKE '%World Cup%'
        GROUP BY l.league_id, s.season_name
        ORDER BY l.name_cn, s.season_name DESC
    ''')

    print(f"{'联赛':<15} {'赛季':<8} {'比赛':<8} {'已结束':<8} {'有比分':<8}")
    print("-"*60)
    for r in cursor.fetchall():
        print(f"{r['name_cn'] or r['name_en']:<15} {r['season_name']:<8} {r['matches']:<8} {r['finished']:<8} {r['has_scores']:<8}")

    # 球队统计
    cursor.execute('''
        SELECT COUNT(DISTINCT t.team_id)
        FROM teams t
        WHERE EXISTS (
            SELECT 1 FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            WHERE (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
            AND (l.name_cn IN ('世界杯', '女足世界杯', '世俱杯') OR l.name_en LIKE '%World Cup%')
        )
    ''')
    print(f"\n参赛球队: {cursor.fetchone()[0]}")

    conn.close()


if __name__ == '__main__':
    fetch_world_cup_data()
    print_summary()
    print("\n完成!")
