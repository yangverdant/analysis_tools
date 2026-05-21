#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
零成本慢速爬虫 - 从FBref免费获取缺失数据
策略：慢速请求 + 随机休眠，模拟人类浏览，避免被封禁
"""

import sys
import os
import time
import random
import pandas as pd
from pathlib import Path

if sys.platform == 'win32':
    pass

DATA_DIR = Path("data")

# 我们要白嫖的免费联赛清单
FREE_LEAGUES = {
    # 亚洲联赛
    'KOR-K League 1': ('05_asia_leagues', 'k1_league'),
    'KOR-K League 2': ('05_asia_leagues', 'k2_league'),
    'JPN-J2 League': ('05_asia_leagues', 'j2_league'),

    # 北欧联赛
    'SWE-Allsvenskan': ('01_europe_leagues', 'allsvenskan'),
    'DEN-Superliga': ('01_europe_leagues', 'superligaen'),
    'FIN-Veikkausliiga': ('01_europe_leagues', 'veikkausliiga'),

    # 欧战
    'INT-Europa League': ('03_european_competitions', 'europa_league'),
}

# 标准列
STANDARD_COLUMNS = [
    'Div', 'Date', 'Time', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG', 'HTR',
    'HS', 'AS', 'HST', 'AST', 'HF', 'AF', 'HC', 'AC', 'HY', 'AY', 'HR', 'AR', 'Referee', 'Attendance',
    'B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA', 'IWH', 'IWD', 'IWA', 'WHH', 'WHD', 'WHA',
    'VCH', 'VCD', 'VCA', 'PSH', 'PSD', 'PSA', 'MaxH', 'MaxD', 'MaxA', 'AvgH', 'AvgD', 'AvgA',
    'B365>2.5', 'B365<2.5', 'P>2.5', 'P<2.5', 'Max>2.5', 'Max<2.5', 'Avg>2.5', 'Avg<2.5',
    'AHh', 'B365AHH', 'B365AHA', 'PAHH', 'PAHA', 'MaxAHH', 'MaxAHA', 'AvgAHH', 'AvgAHA',
]

def standardize_data(df, code=''):
    """标准化数据格式"""
    # 列名映射
    col_map = {
        'home_team': 'HomeTeam',
        'away_team': 'AwayTeam',
        'home_goals': 'FTHG',
        'away_goals': 'FTAG',
        'home_score': 'FTHG',
        'away_score': 'FTAG',
    }

    for old, new in col_map.items():
        if old in df.columns:
            df.rename(columns={old: new}, inplace=True)

    # 添加Div列
    if 'Div' not in df.columns:
        df['Div'] = code

    # 添加缺失的标准列
    for col in STANDARD_COLUMNS:
        if col not in df.columns:
            df[col] = ''

    return df.reindex(columns=STANDARD_COLUMNS)

def scrape_league(league_code, category, league_name, seasons):
    """抓取单个联赛数据"""
    import soccerdata as sd

    print(f"\n{'='*60}")
    print(f"正在获取: {league_code}")
    print(f"赛季: {seasons}")
    print('='*60)

    try:
        # 初始化爬虫
        scraper = sd.FBref(leagues=league_code, seasons=seasons)

        # 读取赛程/赛果
        print("  读取赛程数据...")
        schedule = scraper.read_schedule()

        if schedule.empty:
            print("  无数据")
            return False

        print(f"  获取到 {len(schedule)} 场比赛")

        # 处理每个赛季
        for season in seasons:
            season_data = schedule[schedule['season'] == season] if 'season' in schedule.columns else schedule

            if season_data.empty:
                continue

            # 标准化
            season_data = standardize_data(season_data.copy(), league_name[:2].upper())

            # 保存
            league_path = DATA_DIR / category / league_name
            league_path.mkdir(parents=True, exist_ok=True)

            season_file = league_path / f"{league_name}_{season}.csv"
            season_data.to_csv(season_file, index=False, encoding='utf-8')
            print(f"  保存: {season_file.name} ({len(season_data)}场)")

        return True

    except Exception as e:
        print(f"  错误: {e}")
        return False

def main():
    print("=" * 70)
    print("零成本慢速爬虫 - FBref免费数据获取")
    print("=" * 70)
    print("策略: 慢速请求 + 随机休眠，模拟人类浏览")
    print("预计耗时: 数小时，建议睡前运行")
    print()

    # 分批处理，每次只处理几个赛季
    SEASONS_BATCH1 = ['2018', '2019', '2020', '2021']
    SEASONS_BATCH2 = ['2014', '2015', '2016', '2017']
    SEASONS_BATCH3 = ['2010', '2011', '2012', '2013']

    batches = [SEASONS_BATCH1, SEASONS_BATCH2, SEASONS_BATCH3]

    total_success = 0
    total_failed = 0

    for batch_idx, seasons in enumerate(batches):
        print(f"\n{'#'*70}")
        print(f"# 第 {batch_idx + 1} 批赛季: {seasons[0]}-{seasons[-1]}")
        print('#'*70)

        for league_code, (category, league_name) in FREE_LEAGUES.items():
            print(f"\n[{league_code}]")

            success = scrape_league(league_code, category, league_name, seasons)

            if success:
                total_success += 1
            else:
                total_failed += 1

            # 核心防封禁机制：随机深度休眠
            sleep_time = random.randint(20, 45)
            print(f"  休息 {sleep_time} 秒...")
            time.sleep(sleep_time)

        # 批次间更长休息
        if batch_idx < len(batches) - 1:
            batch_sleep = random.randint(120, 180)
            print(f"\n批次间休息 {batch_sleep} 秒...")
            time.sleep(batch_sleep)

    print()
    print("=" * 70)
    print("抓取完成!")
    print(f"成功: {total_success}, 失败: {total_failed}")
    print("=" * 70)

if __name__ == "__main__":
    main()