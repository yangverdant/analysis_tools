#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入世界杯历史数据（2018、2022、2026）
"""

import os
import sys
import sqlite3
import pandas as pd
import re
from pathlib import Path
from datetime import datetime

# 配置
DATABASE_PATH = Path(__file__).parent.parent / 'data' / 'football_v2.db'

# 世界杯数据文件
WORLD_CUP_FILES = {
    2018: Path('_不需要文件/backup/football_data_backup_20260516_201839/04_international/world_cup_fbref/world_cup_fbref_2018.csv'),
    2022: Path('_不需要文件/backup/football_data_backup_20260516_201839/04_international/world_cup_fbref/world_cup_fbref_2022.csv'),
    2014: Path('_不需要文件/backup/football_data_backup_20260516_201839/04_international/world_cup_fbref/world_cup_fbref_2014.csv'),
}

# 世界杯联赛ID
WORLD_CUP_LEAGUE_ID = 44

# 国家队名称映射（英文 -> 中文）
NATIONAL_TEAM_CN = {
    'Russia': '俄罗斯',
    'Saudi Arabia': '沙特阿拉伯',
    'Egypt': '埃及',
    'Uruguay': '乌拉圭',
    'Morocco': '摩洛哥',
    'IR Iran': '伊朗',
    'Iran': '伊朗',
    'Portugal': '葡萄牙',
    'Spain': '西班牙',
    'Argentina': '阿根廷',
    'Iceland': '冰岛',
    'Croatia': '克罗地亚',
    'Nigeria': '尼日利亚',
    'France': '法国',
    'Australia': '澳大利亚',
    'Peru': '秘鲁',
    'Denmark': '丹麦',
    'Brazil': '巴西',
    'Switzerland': '瑞士',
    'Costa Rica': '哥斯达黎加',
    'Serbia': '塞尔维亚',
    'Germany': '德国',
    'Mexico': '墨西哥',
    'Belgium': '比利时',
    'Panama': '巴拿马',
    'Sweden': '瑞典',
    'Korea Republic': '韩国',
    'South Korea': '韩国',
    'Tunisia': '突尼斯',
    'England': '英格兰',
    'Colombia': '哥伦比亚',
    'Japan': '日本',
    'Poland': '波兰',
    'Senegal': '塞内加尔',
    'Qatar': '卡塔尔',
    'Ecuador': '厄瓜多尔',
    'Netherlands': '荷兰',
    'United States': '美国',
    'Wales': '威尔士',
    'Canada': '加拿大',
    'Cameroon': '喀麦隆',
    'Ghana': '加纳',
    'China PR': '中国',
    'China': '中国',
    'Italy': '意大利',
    'Netherlands': '荷兰',
    'Czech Republic': '捷克',
    'Turkey': '土耳其',
    'Greece': '希腊',
    'Ukraine': '乌克兰',
    'Austria': '奥地利',
    'Hungary': '匈牙利',
    'Slovakia': '斯洛伐克',
    'Romania': '罗马尼亚',
    'Albania': '阿尔巴尼亚',
    'Ireland': '爱尔兰',
    'Scotland': '苏格兰',
    'Norway': '挪威',
    'Finland': '芬兰',
    'Paraguay': '巴拉圭',
    'Chile': '智利',
    'Colombia': '哥伦比亚',
    'Venezuela': '委内瑞拉',
    'Bolivia': '玻利维亚',
    'Ecuador': '厄瓜多尔',
    'Peru': '秘鲁',
    'Algeria': '阿尔及利亚',
    'Tunisia': '突尼斯',
    'Morocco': '摩洛哥',
    'Egypt': '埃及',
    'Nigeria': '尼日利亚',
    'Cameroon': '喀麦隆',
    'Senegal': '塞内加尔',
    'Ghana': '加纳',
    'Ivory Coast': '科特迪瓦',
    "Côte d'Ivoire": '科特迪瓦',
    'Mali': '马里',
    'Burkina Faso': '布基纳法索',
    'Guinea': '几内亚',
    'Congo DR': '刚果民主共和国',
    'Congo': '刚果',
    'Zambia': '赞比亚',
    'Angola': '安哥拉',
    'Libya': '利比亚',
    'Sudan': '苏丹',
    'South Africa': '南非',
    'Kenya': '肯尼亚',
    'Ethiopia': '埃塞俄比亚',
    'Uganda': '乌干达',
    'Tanzania': '坦桑尼亚',
    'Mozambique': '莫桑比克',
    'Zimbabwe': '津巴布韦',
    'Namibia': '纳米比亚',
    'Botswana': '博茨瓦纳',
    'Malawi': '马拉维',
    'Madagascar': '马达加斯加',
}


def parse_score(score_str):
    """解析比分字符串 '5–0' -> (5, 0)"""
    if pd.isna(score_str):
        return None, None

    # 处理各种格式: "5–0", "5-0", "1–1 (a.e.t.)", "1–1 (pen.)"
    score_str = str(score_str)

    # 提取数字
    match = re.match(r'(\d+)[–\-](\d+)', score_str)
    if match:
        return int(match.group(1)), int(match.group(2))

    return None, None


def parse_round(round_str):
    """解析轮次"""
    if pd.isna(round_str):
        return None, None

    round_str = str(round_str)

    if 'Group' in round_str:
        # 小组赛
        return 'group', None
    elif 'Round of 16' in round_str or 'R16' in round_str:
        return 'knockout', 'R16'
    elif 'Quarter-final' in round_str or 'QF' in round_str:
        return 'knockout', 'QF'
    elif 'Semi-final' in round_str or 'SF' in round_str:
        return 'knockout', 'SF'
    elif 'Final' in round_str and 'Semi' not in round_str:
        return 'final', 'Final'
    elif 'Third-place' in round_str or '3rd' in round_str:
        return 'knockout', '3RD'
    else:
        return 'group', None


def import_world_cup():
    """导入世界杯数据"""
    print("=" * 60)
    print("导入世界杯历史数据")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 确保世界杯联赛存在
    world_cup_league_id = WORLD_CUP_LEAGUE_ID
    cursor.execute("SELECT league_id FROM leagues WHERE league_id = ? OR league_code = 'world_cup'",
                  (world_cup_league_id,))
    result = cursor.fetchone()
    if result:
        # 已存在，获取league_id
        world_cup_league_id = result['league_id']
    else:
        cursor.execute("""
            INSERT INTO leagues (league_id, league_code, name_en, name_cn, country,
                               competition_type, participant_type, format_type, tier, is_international)
            VALUES (?, 'world_cup', 'World Cup', '世界杯', 'FIFA',
                   'tournament', 'national', 'group_knockout', 1, 1)
        """, (world_cup_league_id,))
        conn.commit()
        print("创建世界杯联赛记录")

    stats = {
        'matches_imported': 0,
        'matches_skipped': 0,
        'teams_added': 0,
        'errors': []
    }

    team_cache = {}  # 球队名 -> team_id

    for year, file_path in WORLD_CUP_FILES.items():
        if not file_path.exists():
            print(f"文件不存在: {file_path}")
            continue

        print(f"\n处理 {year} 年世界杯...")

        # 创建赛季
        season_name = str(year)
        cursor.execute("""
            SELECT season_id FROM seasons
            WHERE league_id = ? AND season_name = ?
        """, (world_cup_league_id, season_name))
        result = cursor.fetchone()

        if result:
            season_id = result['season_id']
        else:
            cursor.execute("""
                INSERT INTO seasons (league_id, season_name, year, status)
                VALUES (?, ?, ?, 'completed')
            """, (world_cup_league_id, season_name, year))
            season_id = cursor.lastrowid
            conn.commit()

        # 读取CSV
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            print(f"  读取失败: {e}")
            continue

        print(f"  共 {len(df)} 场比赛")

        for idx, row in df.iterrows():
            try:
                # 解析数据
                date = row.get('date')
                home_team = row.get('home_team')
                away_team = row.get('away_team')
                score_str = row.get('score')

                if pd.isna(home_team) or pd.isna(away_team):
                    continue

                # 解析比分
                home_goals, away_goals = parse_score(score_str)

                # 解析轮次
                round_str = row.get('round', '')
                stage_type, round_stage = parse_round(round_str)

                # 获取或创建球队
                home_team_id = get_or_create_team(cursor, home_team, team_cache, stats, conn)
                away_team_id = get_or_create_team(cursor, away_team, team_cache, stats, conn)

                # 检查是否已存在
                cursor.execute("""
                    SELECT match_id FROM matches
                    WHERE match_date = ? AND home_team_id = ? AND away_team_id = ? AND league_id = ?
                """, (date, home_team_id, away_team_id, world_cup_league_id))

                if cursor.fetchone():
                    stats['matches_skipped'] += 1
                    continue

                # 插入比赛
                cursor.execute("""
                    INSERT INTO matches (
                        match_date, league_id, season_id, round_stage, stage_type,
                        home_team_id, away_team_id,
                        home_goals, away_goals,
                        venue, neutral, status, source, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'finished', 'fbref', datetime('now'))
                """, (
                    date,
                    world_cup_league_id,
                    season_id,
                    round_stage,
                    stage_type,
                    home_team_id,
                    away_team_id,
                    home_goals,
                    away_goals,
                    row.get('venue')
                ))

                stats['matches_imported'] += 1

            except Exception as e:
                stats['errors'].append(f"{year}年 第{idx}行: {str(e)}")

        conn.commit()

    # 打印汇总
    print("\n" + "=" * 60)
    print("导入完成")
    print("=" * 60)
    print(f"导入比赛: {stats['matches_imported']}")
    print(f"跳过比赛: {stats['matches_skipped']}")
    print(f"新增球队: {stats['teams_added']}")

    if stats['errors']:
        print(f"错误数: {len(stats['errors'])}")
        for err in stats['errors'][:5]:
            print(f"  {err}")

    conn.close()


def get_or_create_team(cursor, team_name, cache, stats, conn):
    """获取或创建国家队"""
    if team_name in cache:
        return cache[team_name]

    # 查找现有球队
    cursor.execute("""
        SELECT team_id FROM teams
        WHERE name_en = ? AND team_type = 'national'
    """, (team_name,))
    result = cursor.fetchone()

    if result:
        cache[team_name] = result['team_id']
        return result['team_id']

    # 创建新球队
    name_cn = NATIONAL_TEAM_CN.get(team_name)

    cursor.execute("""
        INSERT INTO teams (name_en, name_cn, team_type, country, created_at)
        VALUES (?, ?, 'national', ?, datetime('now'))
    """, (team_name, name_cn, team_name))

    team_id = cursor.lastrowid
    conn.commit()

    cache[team_name] = team_id
    stats['teams_added'] += 1
    print(f"  新增国家队: {team_name} ({name_cn or '未知'})")

    return team_id


if __name__ == '__main__':
    import_world_cup()
