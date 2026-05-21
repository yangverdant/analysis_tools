#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接爬取FBref网站获取免费数据
使用requests + BeautifulSoup慢速爬取
"""

import sys
import os
import time
import random
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re

if sys.platform == 'win32':
    pass

DATA_DIR = Path("data")

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

# FBref联赛URL映射
FBREF_URLS = {
    # 韩国联赛
    'k1_league': 'https://fbref.com/en/comps/55/K-League-1-Stats',
    'k2_league': 'https://fbref.com/en/comps/56/K-League-2-Stats',

    # 日本联赛
    'j1_league': 'https://fbref.com/en/comps/51/J1-League-Stats',
    'j2_league': 'https://fbref.com/en/comps/52/J2-League-Stats',

    # 北欧联赛
    'allsvenskan': 'https://fbref.com/en/comps/45/Allsvenskan-Stats',
    'superligaen': 'https://fbref.com/en/comps/46/Superliga-Stats',
    'veikkausliiga': 'https://fbref.com/en/comps/47/Veikkausliiga-Stats',

    # 欧战
    'europa_league': 'https://fbref.com/en/comps/19/Europa-League-Stats',

    # 美洲
    'mls': 'https://fbref.com/en/comps/74/MLS-Stats',
    'liga_mx': 'https://fbref.com/en/comps/31/Liga-MX-Stats',
    'serie_a_brazil': 'https://fbref.com/en/comps/38/Serie-A-Stats',
}

def get_with_retry(url, max_retries=3):
    """带重试的请求"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                # 被限流，等待更长时间
                wait_time = 60 + random.randint(30, 60)
                print(f"    被限流，等待 {wait_time} 秒...")
                time.sleep(wait_time)
            else:
                print(f"    HTTP {response.status_code}")
                time.sleep(5)
        except Exception as e:
            print(f"    请求错误: {e}")
            time.sleep(10)

    return None

def parse_match_table(html_content, league_name):
    """解析比赛表格"""
    soup = BeautifulSoup(html_content, 'html.parser')

    matches = []

    # 查找比赛表格
    tables = soup.find_all('table')

    for table in tables:
        # 检查是否是赛程表
        table_id = table.get('id', '')
        if 'schedule' in table_id or 'match' in table_id.lower():
            rows = table.find_all('tr')

            for row in rows[1:]:  # 跳过表头
                cols = row.find_all('td')
                if len(cols) >= 6:
                    try:
                        # 尝试提取比赛信息
                        date = cols[0].get_text(strip=True) if cols[0] else ''
                        home = cols[2].get_text(strip=True) if len(cols) > 2 else ''
                        away = cols[4].get_text(strip=True) if len(cols) > 4 else ''
                        score = cols[3].get_text(strip=True) if len(cols) > 3 else ''

                        if date and home and away:
                            # 解析比分
                            home_goals, away_goals = 0, 0
                            if score:
                                parts = score.split('–')
                                if len(parts) == 2:
                                    try:
                                        home_goals = int(parts[0].strip())
                                        away_goals = int(parts[1].strip())
                                    except:
                                        pass

                            matches.append({
                                'Date': date,
                                'HomeTeam': home,
                                'AwayTeam': away,
                                'FTHG': home_goals,
                                'FTAG': away_goals,
                                'Div': league_name[:2].upper(),
                            })
                    except Exception as e:
                        continue

    return matches

def scrape_league_season(league_name, url, season):
    """爬取单个联赛赛季"""
    print(f"  获取 {season} 赛季...")

    # 构建赛季URL
    if '?' in url:
        season_url = f"{url}&season={season}"
    else:
        season_url = f"{url}?season={season}"

    response = get_with_retry(season_url)

    if response:
        matches = parse_match_table(response.text, league_name)

        if matches:
            df = pd.DataFrame(matches)
            print(f"    找到 {len(df)} 场比赛")
            return df
        else:
            print(f"    未找到比赛数据")
    else:
        print(f"    请求失败")

    return None

def main():
    print("=" * 70)
    print("FBref免费数据爬虫 (慢速防封禁版)")
    print("=" * 70)
    print("策略: 慢速请求 + 随机休眠")
    print("建议: 睡前运行，让脚本慢慢跑")
    print()

    # 要爬取的联赛
    leagues_to_scrape = [
        ('k1_league', '05_asia_leagues'),
        ('j1_league', '05_asia_leagues'),
        ('europa_league', '03_european_competitions'),
        ('allsvenskan', '01_europe_leagues'),
    ]

    seasons = ['2023', '2022', '2021', '2020', '2019', '2018']

    total_saved = 0

    for league_name, category in leagues_to_scrape:
        if league_name not in FBREF_URLS:
            print(f"\n{league_name}: 无URL配置")
            continue

        url = FBREF_URLS[league_name]
        print(f"\n【{league_name}】")
        print(f"URL: {url}")

        for season in seasons:
            df = scrape_league_season(league_name, url, season)

            if df and len(df) > 0:
                # 保存
                league_path = DATA_DIR / category / league_name
                league_path.mkdir(parents=True, exist_ok=True)

                season_file = league_path / f"{league_name}_{season}.csv"
                df.to_csv(season_file, index=False, encoding='utf-8')
                print(f"    保存: {season_file.name}")
                total_saved += 1

            # 随机休眠
            sleep_time = random.randint(15, 35)
            print(f"    休息 {sleep_time} 秒...")
            time.sleep(sleep_time)

    print()
    print("=" * 70)
    print(f"爬取完成! 共保存 {total_saved} 个赛季数据")
    print("=" * 70)

if __name__ == "__main__":
    main()