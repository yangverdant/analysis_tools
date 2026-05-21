#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用积分榜/排名计算模块
支持所有赛事类型：
- 联赛（积分榜）
- 杯赛（淘汰赛对阵）
- 小组赛（小组积分榜）
- 国家队赛事（排名）
"""

import os
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_DIR = Path("data")

# 赛事类型映射
COMPETITION_TYPES = {
    # 欧洲联赛
    '01_europe_leagues': 'league',
    # 欧洲杯赛
    '02_europe_cups': 'cup',
    # 欧战赛事
    '03_european_competitions': 'european',
    # 国家队赛事
    '04_international': 'international',
    # 亚洲联赛
    '05_asia_leagues': 'league',
    # 南美洲联赛
    '06_south_america': 'league',
    # 北美洲联赛
    '07_north_america': 'league',
    # 非洲联赛
    '08_africa': 'league',
}

def get_standings(competition_type, competition_code, season):
    """
    获取积分榜/排名

    参数:
        competition_type: 赛事类型目录，如 '01_europe_leagues', '04_international'
        competition_code: 赛事代码，如 'premier_league', 'world_cup'
        season: 赛季，如 '2025-2026', '2024-2025'

    返回:
        DataFrame: 积分榜或排名
    """
    comp_dir = DATA_DIR / competition_type / competition_code
    if not comp_dir.exists():
        print(f"未找到赛事: {competition_type}/{competition_code}")
        return None

    # 查找赛季文件
    season_file = None
    for pattern in [f"*{season}*", "*.csv"]:
        matches = list(comp_dir.glob(pattern))
        if matches:
            season_file = matches[0]
            break

    if not season_file:
        print(f"未找到 {competition_code} {season} 数据")
        return None

    # 读取数据
    df = pd.read_csv(season_file, low_memory=True)
    if len(df) == 0:
        return None

    # 根据赛事类型计算
    comp_type = COMPETITION_TYPES.get(competition_type, 'league')

    if comp_type == 'league':
        return calculate_league_standings(df, competition_code, season)
    elif comp_type == 'cup':
        return calculate_cup_progress(df, competition_code, season)
    elif comp_type == 'european':
        return calculate_european_standings(df, competition_code, season)
    elif comp_type == 'international':
        return calculate_international_rankings(df, competition_code, season)

    return None

def calculate_league_standings(df, league_code, season):
    """计算联赛积分榜"""
    # 筛选已结束的比赛
    if 'Status' in df.columns:
        matches = df[df['Status'] == 'Finished']
    elif 'FTHG' in df.columns:
        matches = df[df['FTHG'].notna() & df['FTAG'].notna()]
    else:
        matches = df

    if len(matches) == 0:
        return None

    # 获取所有球队
    teams = set(matches['HomeTeam'].unique()) | set(matches['AwayTeam'].unique())

    standings = []
    for team in teams:
        home = matches[matches['HomeTeam'] == team]
        away = matches[matches['AwayTeam'] == team]

        home_w = len(home[home['FTR'] == 'H']) if 'FTR' in home.columns else 0
        home_d = len(home[home['FTR'] == 'D']) if 'FTR' in home.columns else 0
        home_l = len(home[home['FTR'] == 'A']) if 'FTR' in home.columns else 0
        away_w = len(away[away['FTR'] == 'A']) if 'FTR' in away.columns else 0
        away_d = len(away[away['FTR'] == 'D']) if 'FTR' in away.columns else 0
        away_l = len(away[away['FTR'] == 'H']) if 'FTR' in away.columns else 0

        home_gf = home['FTHG'].sum() if 'FTHG' in home.columns and len(home) > 0 else 0
        home_ga = home['FTAG'].sum() if 'FTAG' in home.columns and len(home) > 0 else 0
        away_gf = away['FTAG'].sum() if 'FTAG' in away.columns and len(away) > 0 else 0
        away_ga = away['FTHG'].sum() if 'FTHG' in away.columns and len(away) > 0 else 0

        played = len(home) + len(away)
        won = home_w + away_w
        drawn = home_d + away_d
        lost = home_l + away_l
        gf = int(home_gf + away_gf)
        ga = int(home_ga + away_ga)
        gd = gf - ga
        points = won * 3 + drawn

        standings.append({
            'Position': 0,
            'Team': team,
            'Played': played,
            'Won': won,
            'Drawn': drawn,
            'Lost': lost,
            'GF': gf,
            'GA': ga,
            'GD': gd,
            'Points': points,
            'League': league_code,
            'Season': season,
        })

    result = pd.DataFrame(standings)
    result = result.sort_values(['Points', 'GD', 'GF'], ascending=[False, False, False])
    result['Position'] = range(1, len(result) + 1)
    result = result.reset_index(drop=True)

    return result

def calculate_cup_progress(df, cup_code, season):
    """计算杯赛进程（淘汰赛对阵）"""
    # 杯赛显示轮次和对阵
    if 'Round' in df.columns:
        rounds = df['Round'].unique()
        progress = []
        for r in sorted(rounds):
            round_matches = df[df['Round'] == r]
            for _, m in round_matches.iterrows():
                progress.append({
                    'Round': r,
                    'HomeTeam': m.get('HomeTeam', ''),
                    'AwayTeam': m.get('AwayTeam', ''),
                    'HomeScore': m.get('FTHG', ''),
                    'AwayScore': m.get('FTAG', ''),
                    'Status': m.get('Status', 'Unknown'),
                })
        return pd.DataFrame(progress)
    else:
        return df[['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'Status']].copy() if 'Status' in df.columns else df

def calculate_european_standings(df, competition_code, season):
    """计算欧战积分榜（欧冠、欧联等）"""
    # 欧战可能有小组赛和淘汰赛
    if 'Group' in df.columns or 'Stage' in df.columns:
        # 有小组赛
        group_col = 'Group' if 'Group' in df.columns else 'Stage'
        groups = df[group_col].unique()

        all_standings = []
        for group in groups:
            group_matches = df[df[group_col] == group]
            group_standings = calculate_league_standings(group_matches, competition_code, season)
            if group_standings is not None:
                group_standings['Group'] = group
                all_standings.append(group_standings)

        if all_standings:
            return pd.concat(all_standings, ignore_index=True)

    return calculate_league_standings(df, competition_code, season)

def calculate_international_rankings(df, competition_code, season):
    """计算国家队赛事排名"""
    # 国家队赛事可能是世界杯、欧洲杯等
    if 'Stage' in df.columns or 'Round' in df.columns:
        return calculate_cup_progress(df, competition_code, season)

    return calculate_league_standings(df, competition_code, season)

def list_competitions():
    """列出所有可用赛事"""
    competitions = []

    for comp_type, type_name in [
        ('01_europe_leagues', '欧洲联赛'),
        ('02_europe_cups', '欧洲杯赛'),
        ('03_european_competitions', '欧战赛事'),
        ('04_international', '国家队赛事'),
        ('05_asia_leagues', '亚洲联赛'),
        ('06_south_america', '南美洲联赛'),
        ('07_north_america', '北美洲联赛'),
        ('08_africa', '非洲联赛'),
    ]:
        comp_dir = DATA_DIR / comp_type
        if comp_dir.exists():
            for league_dir in sorted(comp_dir.iterdir()):
                if league_dir.is_dir():
                    # 获取可用赛季
                    seasons = []
                    for f in league_dir.glob("*.csv"):
                        filename = f.stem
                        for part in filename.split('_'):
                            if '-' in part and part[0].isdigit():
                                seasons.append(part)
                                break

                    competitions.append({
                        'Type': comp_type,
                        'TypeName': type_name,
                        'Code': league_dir.name,
                        'Seasons': sorted(set(seasons), reverse=True),
                    })

    return competitions

def demo():
    """演示用法"""
    print("="*70)
    print("通用积分榜/排名计算演示")
    print("="*70)

    # 1. 联赛积分榜
    print("\n【英超 2025-26 积分榜 TOP 5】")
    standings = get_standings('01_europe_leagues', 'premier_league', '2025-2026')
    if standings is not None:
        print(standings.head(5).to_string(index=False))

    print("\n【德甲 2025-26 积分榜 TOP 5】")
    standings = get_standings('01_europe_leagues', 'bundesliga', '2025-2026')
    if standings is not None:
        print(standings.head(5).to_string(index=False))

    # 2. 杯赛进程
    print("\n【足总杯 2025-26 进程】")
    progress = get_standings('02_europe_cups', 'fa_cup', '2025-2026')
    if progress is not None:
        print(progress.head(10).to_string(index=False))

    # 3. 国家队赛事
    print("\n【世界杯历史】")
    wc = get_standings('04_international', 'world_cup', '2022')
    if wc is not None:
        print(wc.head(10).to_string(index=False))

    # 4. 列出所有赛事
    print("\n【可用赛事列表】")
    competitions = list_competitions()
    for comp in competitions[:10]:  # 只显示前10个
        print(f"  {comp['TypeName']}: {comp['Code']} ({len(comp['Seasons'])} 个赛季)")

if __name__ == "__main__":
    demo()