#!/usr/bin/env python3
"""
从StatsBomb事件数据提取xG并更新到数据库
"""

import sqlite3
import json
import os
from collections import defaultdict

DB_PATH = 'd:/football_tools/data/football_v2.db'
SB_EVENTS_DIR = 'd:/football_tools/new_data/matches/clubs/leagues/StatsBomb_events'
SB_MATCHES_DIR = 'd:/football_tools/new_data/matches/clubs/leagues/StatsBomb_matches'

def extract_xg_from_events():
    """从StatsBomb事件文件提取xG数据"""
    print("从StatsBomb提取xG数据...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取所有StatsBomb事件文件
    if not os.path.exists(SB_EVENTS_DIR):
        print(f"  目录不存在: {SB_EVENTS_DIR}")
        return 0

    event_files = [f for f in os.listdir(SB_EVENTS_DIR) if f.endswith('.json')]
    print(f"  找到 {len(event_files)} 个事件文件")

    # 提取每场比赛的xG
    match_xg = {}  # match_id -> {home_xg, away_xg, home_team_id, away_team_id}

    for event_file in event_files:
        try:
            match_id = event_file.replace('.json', '')

            with open(os.path.join(SB_EVENTS_DIR, event_file), 'r', encoding='utf-8') as f:
                events = json.load(f)

            home_xg = 0.0
            away_xg = 0.0
            home_team_id = None
            away_team_id = None

            for event in events:
                # 获取球队ID
                if 'team' in event:
                    team_id = event['team'].get('id')
                    if home_team_id is None:
                        home_team_id = team_id
                    elif team_id != home_team_id and away_team_id is None:
                        away_team_id = team_id

                # 统计射门xG
                if event.get('type', {}).get('name') == 'Shot':
                    shot = event.get('shot', {})
                    xg = shot.get('statsbomb_xg', 0)
                    if xg:
                        team_id = event.get('team', {}).get('id')
                        if team_id == home_team_id:
                            home_xg += xg
                        elif team_id == away_team_id:
                            away_xg += xg

            if home_xg > 0 or away_xg > 0:
                match_xg[match_id] = {
                    'home_xg': round(home_xg, 2),
                    'away_xg': round(away_xg, 2),
                    'home_team_id': home_team_id,
                    'away_team_id': away_team_id
                }

        except Exception as e:
            pass

    print(f"  提取了 {len(match_xg)} 场比赛的xG数据")

    # 更新到数据库
    # 首先建立StatsBomb match_id到数据库match_id的映射
    # 通过match_date和球队匹配

    cursor.execute('''
        SELECT m.match_id, m.match_date, m.home_team_id, m.away_team_id,
               m.home_goals, m.away_goals
        FROM matches m
        WHERE m.status = 'finished'
    ''')
    db_matches = cursor.fetchall()

    # 建立日期+比分映射
    date_score_map = {}
    for match in db_matches:
        match_id, match_date, home_id, away_id, home_goals, away_goals = match
        date_str = str(match_date)[:10] if match_date else None
        if date_str:
            key = (date_str, home_goals, away_goals)
            if key not in date_score_map:
                date_score_map[key] = []
            date_score_map[key].append(match_id)

    # 尝试从StatsBomb matches文件获取映射
    sb_match_info = {}
    if os.path.exists(SB_MATCHES_DIR):
        match_files = [f for f in os.listdir(SB_MATCHES_DIR) if f.endswith('.json')]
        for match_file in match_files:
            try:
                with open(os.path.join(SB_MATCHES_DIR, match_file), 'r', encoding='utf-8') as f:
                    matches = json.load(f)

                for match in matches:
                    sb_match_id = str(match.get('match_id', ''))
                    match_date = match.get('match_date', '')[:10]
                    home_score = match.get('home_score')
                    away_score = match.get('away_score')

                    if sb_match_id and match_date:
                        sb_match_info[sb_match_id] = {
                            'date': match_date,
                            'home_score': home_score,
                            'away_score': away_score
                        }
            except:
                pass

    # 更新数据库
    updated = 0
    for sb_match_id, xg_data in match_xg.items():
        if sb_match_id in sb_match_info:
            info = sb_match_info[sb_match_id]
            date = info['date']
            home_goals = info['home_score']
            away_goals = info['away_score']

            key = (date, home_goals, away_goals)
            if key in date_score_map:
                for db_match_id in date_score_map[key]:
                    cursor.execute('''
                        UPDATE matches
                        SET home_xg = ?, away_xg = ?
                        WHERE match_id = ?
                    ''', (xg_data['home_xg'], xg_data['away_xg'], db_match_id))
                    if cursor.rowcount > 0:
                        updated += 1

    conn.commit()

    # 验证
    cursor.execute('SELECT COUNT(*) FROM matches WHERE home_xg IS NOT NULL AND home_xg != ""')
    new_count = cursor.fetchone()[0]
    print(f"  更新了 {updated} 条记录")
    print(f"  当前有xG的比赛: {new_count}")

    conn.close()
    return updated


if __name__ == '__main__':
    extract_xg_from_events()
