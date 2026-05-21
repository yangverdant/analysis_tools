#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成联赛积分榜 - 按赛季分开存储
每个联赛每个赛季一个文件
"""

import os
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OUTPUT_DIR = Path("data/standings")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def calculate_standings(df_matches, league_name, season):
    """
    根据比赛数据计算积分榜
    """
    # 只计算已结束的比赛
    finished = df_matches[df_matches['Status'] == 'Finished'].copy()

    if len(finished) == 0:
        return None

    # 获取所有球队
    home_teams = finished['HomeTeam'].unique()
    away_teams = finished['AwayTeam'].unique()
    teams = list(set(home_teams) | set(away_teams))

    # 初始化积分榜
    standings = []

    for team in teams:
        # 主场比赛
        home_matches = finished[finished['HomeTeam'] == team]
        home_wins = len(home_matches[home_matches['FTR'] == 'H'])
        home_draws = len(home_matches[home_matches['FTR'] == 'D'])
        home_losses = len(home_matches[home_matches['FTR'] == 'A'])
        home_goals_for = home_matches['FTHG'].sum()
        home_goals_against = home_matches['FTAG'].sum()

        # 客场比赛
        away_matches = finished[finished['AwayTeam'] == team]
        away_wins = len(away_matches[away_matches['FTR'] == 'A'])
        away_draws = len(away_matches[away_matches['FTR'] == 'D'])
        away_losses = len(away_matches[away_matches['FTR'] == 'H'])
        away_goals_for = away_matches['FTAG'].sum()
        away_goals_against = away_matches['FTHG'].sum()

        # 汇总
        played = len(home_matches) + len(away_matches)
        wins = home_wins + away_wins
        draws = home_draws + away_draws
        losses = home_losses + away_losses
        goals_for = home_goals_for + away_goals_for
        goals_against = home_goals_against + away_goals_against
        goal_diff = goals_for - goals_against
        points = wins * 3 + draws

        standings.append({
            'Team': team,
            'Played': played,
            'Won': wins,
            'Drawn': draws,
            'Lost': losses,
            'GF': int(goals_for),
            'GA': int(goals_against),
            'GD': int(goal_diff),
            'Points': points,
            'Home_W': home_wins,
            'Home_D': home_draws,
            'Home_L': home_losses,
            'Away_W': away_wins,
            'Away_D': away_draws,
            'Away_L': away_losses,
        })

    # 创建DataFrame并排序
    df_standings = pd.DataFrame(standings)
    df_standings = df_standings.sort_values(
        by=['Points', 'GD', 'GF'],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    # 添加排名
    df_standings.insert(0, 'Position', range(1, len(df_standings) + 1))

    # 添加联赛和赛季信息
    df_standings['League'] = league_name
    df_standings['Season'] = season

    # 重排列顺序
    cols = ['Position', 'Team', 'Played', 'Won', 'Drawn', 'Lost',
            'GF', 'GA', 'GD', 'Points',
            'Home_W', 'Home_D', 'Home_L',
            'Away_W', 'Away_D', 'Away_L',
            'League', 'Season']

    df_standings = df_standings[[c for c in cols if c in df_standings.columns]]

    return df_standings

def process_league(league_dir, league_name):
    """处理一个联赛的所有赛季"""
    print(f"\n{league_name}:")

    # 获取所有赛季文件
    season_files = sorted(league_dir.glob("*.csv"))

    for season_file in season_files:
        # 提取赛季名称
        filename = season_file.stem  # 去掉.csv后缀

        # 从文件名提取赛季
        # 例如: premier_league_2025-2026 -> 2025-2026
        parts = filename.split('_')
        if len(parts) >= 2:
            # 查找年份部分
            for part in parts:
                if '-' in part and part[0].isdigit():
                    season = part
                    break
            else:
                season = parts[-1]
        else:
            season = filename

        # 读取比赛数据
        try:
            df = pd.read_csv(season_file, low_memory=True)
            if len(df) == 0:
                continue

            # 计算积分榜
            standings = calculate_standings(df, league_name, season)

            if standings is not None and len(standings) > 0:
                # 保存到对应目录
                output_dir = OUTPUT_DIR / league_name
                output_dir.mkdir(parents=True, exist_ok=True)

                output_file = output_dir / f"{league_name}_{season}_standings.csv"
                standings.to_csv(output_file, index=False, encoding='utf-8-sig')

                print(f"  {season}: {len(standings)} 支球队")

        except Exception as e:
            print(f"  {filename}: Error - {str(e)[:30]}")

def main():
    print("="*60)
    print("生成联赛积分榜 (按赛季分开)")
    print("="*60)

    # 处理所有联赛
    leagues_dir = Path("data/01_europe_leagues")

    for league_dir in sorted(leagues_dir.iterdir()):
        if not league_dir.is_dir():
            continue

        league_name = league_dir.name
        process_league(league_dir, league_name)

    # 统计
    print("\n" + "="*60)
    print("生成完成")
    print("="*60)

    # 统计生成的文件
    total_files = 0
    for league_dir in OUTPUT_DIR.iterdir():
        if league_dir.is_dir():
            files = list(league_dir.glob("*.csv"))
            total_files += len(files)
            print(f"{league_dir.name}: {len(files)} 个赛季")

    print(f"\n总计: {total_files} 个积分榜文件")

if __name__ == "__main__":
    main()