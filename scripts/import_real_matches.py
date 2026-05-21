#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导入真实比赛数据"""

import csv
import os
import sqlite3

# 球队名称映射
TEAM_MAPPING = {
    '达姆施塔特': 'Darmstadt', '帕德博恩': 'Paderborn',
    '狼队': 'Wolves', '富勒姆': 'Fulham',
    '埃弗顿': 'Everton', '桑德兰': 'Sunderland',
    '布伦特': 'Brentford', '水晶宫': 'Crystal Palace',
    '亚特兰大': 'Atalanta', '博洛尼亚': 'Bologna',
    '纽卡斯尔': 'Newcastle', '西汉姆': 'West Ham',
    '奥萨苏纳': 'Osasuna', '西班牙人': 'Espanyol',
    '毕尔巴鄂': 'Athletic Bilbao', '塞尔塔': 'Celta Vigo',
    '奥维耶多': 'Oviedo', '阿拉维斯': 'Alaves',
    '马竞': 'Atletico Madrid', '赫罗纳': 'Girona',
    '莱万特': 'Levante', '马洛卡': 'Mallorca',
    '巴列卡诺': 'Rayo Vallecano', '比利亚雷': 'Villarreal',
    '埃尔切': 'Elche', '赫塔费': 'Getafe',
    '塞维利亚': 'Sevilla', '皇马': 'Real Madrid',
    '皇家社会': 'Real Sociedad', '巴伦西亚': 'Valencia',
    '萨索洛': 'Sassuolo', '莱切': 'Lecce',
    '乌迪内斯': 'Udinese', '克雷莫纳': 'Cremonese',
    '里昂': 'Lyon', '朗斯': 'Lens',
    '里尔': 'Lille', '欧塞尔': 'Auxerre',
    '马赛': 'Marseille', '雷恩': 'Rennes',
    '巴萨': 'Barcelona', '贝蒂斯': 'Real Betis',
    '纳什维尔': 'Nashville', '洛杉矶FC': 'LAFC',
    '拉赫蒂': 'Lahti', '瓦萨': 'VPS',
    '佐加顿斯': 'Djurgarden', '天狼星': 'Sirius',
    '厄尔格里特': 'Orgryte', '哥德堡': 'IFK Goteborg',
    '阿森纳': 'Arsenal', '伯恩利': 'Burnley',
}

# 联赛代码映射
LEAGUE_MAPPING = {
    '德乙': ('D2', 'Bundesliga 2'),
    '英超': ('E0', 'Premier League'),
    '意甲': ('I1', 'Serie A'),
    '西甲': ('SP1', 'La Liga'),
    '法甲': ('F1', 'Ligue 1'),
    '美职': ('MLS', 'MLS'),
    '芬超': ('FIN', 'Finland'),
    '瑞典超': ('SWE', 'Allsvenskan'),
}

# 时区偏移
TIMEZONE_OFFSETS = {
    'D2': -6, 'E0': -7, 'I1': -6, 'SP1': -6, 'F1': -6,
    'MLS': -12, 'FIN': -5, 'SWE': -6,
}

# CSV路径映射
CSV_PATHS = {
    'D2': 'data/01_europe_leagues/bundesliga_2/bundesliga_2_2024-2025.csv',
    'E0': 'data/01_europe_leagues/premier_league/premier_league_2024-2025.csv',
    'I1': 'data/01_europe_leagues/serie_a/serie_a_2024-2025.csv',
    'SP1': 'data/01_europe_leagues/la_liga/la_liga_2024-2025.csv',
    'F1': 'data/01_europe_leagues/ligue_1/ligue_1_2024-2025.csv',
    'MLS': 'data/07_north_america/mls/mls_2025.csv',
    'FIN': 'data/01_europe_leagues/finland/finland_2025.csv',
    'SWE': 'data/01_europe_leagues/allsvenskan/allsvenskan_2024-2025.csv',
}

# 比赛数据
MATCHES = [
    # 2026-05-17
    ('D2', '2026-05-17', '21:30', '达姆施塔特', '帕德博恩', 3.20, 3.75, 1.82),
    ('E0', '2026-05-17', '22:00', '狼队', '富勒姆', 3.66, 3.55, 1.74),
    ('E0', '2026-05-17', '22:00', '埃弗顿', '桑德兰', 1.70, 3.32, 4.18),
    ('E0', '2026-05-17', '22:00', '布伦特', '水晶宫', 1.56, 3.80, 4.45),
    # 2026-05-18
    ('I1', '2026-05-18', '00:00', '亚特兰大', '博洛尼亚', 1.59, 3.65, 4.45),
    ('E0', '2026-05-18', '00:30', '纽卡斯尔', '西汉姆', 2.06, 3.55, 2.76),
    ('SP1', '2026-05-18', '01:00', '奥萨苏纳', '西班牙人', 2.06, 2.63, 3.80),
    ('SP1', '2026-05-18', '01:00', '毕尔巴鄂', '塞尔塔', 2.05, 3.00, 3.24),
    ('SP1', '2026-05-18', '01:00', '奥维耶多', '阿拉维斯', 3.75, 3.32, 1.78),
    ('SP1', '2026-05-18', '01:00', '马竞', '赫罗纳', 1.57, 3.75, 4.42),
    ('SP1', '2026-05-18', '01:00', '莱万特', '马洛卡', 1.86, 3.30, 3.46),
    ('SP1', '2026-05-18', '01:00', '巴列卡诺', '比利亚雷', 1.95, 3.35, 3.14),
    ('SP1', '2026-05-18', '01:00', '埃尔切', '赫塔费', 2.09, 2.72, 3.55),
    ('SP1', '2026-05-18', '01:00', '塞维利亚', '皇马', 3.21, 3.50, 1.88),
    ('SP1', '2026-05-18', '01:00', '皇家社会', '巴伦西亚', 2.05, 3.04, 3.20),
    ('I1', '2026-05-18', '02:45', '萨索洛', '莱切', 2.48, 3.00, 2.55),
    ('I1', '2026-05-18', '02:45', '乌迪内斯', '克雷莫纳', 2.20, 3.10, 2.85),
    ('F1', '2026-05-18', '03:00', '里昂', '朗斯', 1.50, 4.35, 4.30),
    ('F1', '2026-05-18', '03:00', '里尔', '欧塞尔', 1.26, 4.90, 7.60),
    ('F1', '2026-05-18', '03:00', '马赛', '雷恩', 1.85, 3.85, 3.05),
    ('SP1', '2026-05-18', '03:15', '巴萨', '贝蒂斯', 1.23, 5.60, 7.25),
    ('MLS', '2026-05-18', '08:00', '纳什维尔', '洛杉矶FC', 2.10, 3.30, 2.86),
    ('FIN', '2026-05-18', '23:00', '拉赫蒂', '瓦萨', 2.02, 2.95, 3.38),
    # 2026-05-19
    ('SWE', '2026-05-19', '01:00', '佐加顿斯', '天狼星', 2.15, 3.50, 2.65),
    ('SWE', '2026-05-19', '01:00', '厄尔格里特', '哥德堡', 3.80, 3.55, 1.71),
    ('E0', '2026-05-19', '03:00', '阿森纳', '伯恩利', None, None, None),
]

def convert_time(beijing_time, offset):
    """北京时间转当地时间"""
    try:
        hours, minutes = map(int, beijing_time.split(':'))
        total_minutes = hours * 60 + minutes + offset * 60
        if total_minutes < 0:
            total_minutes += 24 * 60
        elif total_minutes >= 24 * 60:
            total_minutes -= 24 * 60
        return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"
    except:
        return beijing_time

def main():
    conn = sqlite3.connect('data/football_unified.db')
    cursor = conn.cursor()

    # 获取联赛ID
    league_ids = {}
    for cn_name, (code, en_name) in LEAGUE_MAPPING.items():
        cursor.execute('SELECT league_id FROM leagues WHERE name = ?', (en_name,))
        result = cursor.fetchone()
        if result:
            league_ids[code] = result[0]

    # 获取球队ID
    team_ids = {}
    for cn_name, en_name in TEAM_MAPPING.items():
        cursor.execute('SELECT team_id FROM teams WHERE canonical_name = ?', (en_name,))
        result = cursor.fetchone()
        if result:
            team_ids[cn_name] = result[0]

    added = 0
    for league_code, date, time, home_cn, away_cn, home_odds, draw_odds, away_odds in MATCHES:
        # 转换时间
        offset = TIMEZONE_OFFSETS.get(league_code, 0)
        local_time = convert_time(time, offset)

        # 转换球队名称
        home_en = TEAM_MAPPING.get(home_cn, home_cn)
        away_en = TEAM_MAPPING.get(away_cn, away_cn)

        # 获取ID
        league_id = league_ids.get(league_code)
        home_team_id = team_ids.get(home_cn)
        away_team_id = team_ids.get(away_cn)

        if not league_id or not home_team_id or not away_team_id:
            print(f"Missing ID: {league_code} {home_cn} vs {away_cn}")
            continue

        # 检查是否已存在
        cursor.execute('''
            SELECT match_id FROM matches
            WHERE league_id = ? AND match_date = ?
            AND home_team_id = ? AND away_team_id = ?
        ''', (league_id, date, home_team_id, away_team_id))

        if cursor.fetchone():
            print(f"Already exists: {date} {home_en} vs {away_en}")
            continue

        # 插入比赛
        cursor.execute('''
            INSERT INTO matches (
                league_id, match_date, match_time,
                home_team_id, away_team_id,
                home_odds, draw_odds, away_odds,
                original_home_team, original_away_team,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Scheduled')
        ''', (
            league_id, date, local_time,
            home_team_id, away_team_id,
            home_odds, draw_odds, away_odds,
            home_en, away_en
        ))
        added += 1
        print(f"Added: {date} {local_time} {home_en} vs {away_en} ({league_code})")

    conn.commit()
    conn.close()
    print(f"\nTotal added: {added} matches")

if __name__ == '__main__':
    main()
