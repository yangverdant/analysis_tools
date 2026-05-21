"""
采集各国国家队完整比赛数据
包括友谊赛、世界杯、洲际杯赛、预选赛等所有比赛
"""
import requests
import pandas as pd
import os
from datetime import datetime
import time
import json

DATA_DIR = 'd:/football_tools/data/04_international/national_teams_all_matches'
os.makedirs(DATA_DIR, exist_ok=True)

# 禁用代理
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

def get_session():
    """创建请求会话"""
    session = requests.Session()
    session.trust_env = False
    session.proxies = {}
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    return session

def load_fifa_teams():
    """加载FIFA国家队列表"""
    json_file = 'd:/football_tools/data/09_other_data/fifa_national_teams_by_code.json'
    if os.path.exists(json_file):
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def analyze_existing_data():
    """分析现有国际比赛数据"""

    print("\n分析现有国际比赛数据...")

    intl_file = 'd:/football_tools/data/04_international/all_international/all_international_all.csv'

    if not os.path.exists(intl_file):
        print("  文件不存在")
        return None

    df = pd.read_csv(intl_file, low_memory=False)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date', 'HomeTeam', 'AwayTeam'])

    print(f"  总比赛数: {len(df)}")
    print(f"  有比分比赛: {len(df[df['FTHG'].notna()])}")

    # 统计各球队比赛数
    home_counts = df['HomeTeam'].value_counts()
    away_counts = df['AwayTeam'].value_counts()
    total_counts = home_counts.add(away_counts, fill_value=0).sort_values(ascending=False)

    print(f"  涉及球队数: {len(total_counts)}")

    return df, total_counts

def classify_match_types(df):
    """根据日期和球队推断比赛类型"""

    print("\n推断比赛类型...")

    df['Year'] = df['Date'].dt.year
    df['Month'] = df['Date'].dt.month

    # 世界杯年份和月份（通常5-7月）
    world_cup_years = [2002, 2006, 2010, 2014, 2018, 2022]
    world_cup_months = [5, 6, 7]

    # 欧洲杯年份和月份（通常6-7月）
    euro_years = [2000, 2004, 2008, 2012, 2016, 2020, 2024]
    euro_months = [6, 7]

    # 美洲杯年份
    copa_years = [2001, 2004, 2007, 2011, 2015, 2016, 2019, 2021, 2024]

    # 非洲杯年份
    afcon_years = [2000, 2002, 2004, 2006, 2008, 2010, 2012, 2013, 2015, 2017, 2019, 2021, 2023]

    # 亚洲杯年份
    asian_cup_years = [2000, 2004, 2007, 2011, 2015, 2019, 2023]

    # 初始化比赛类型
    df['MatchType'] = 'Friendly'  # 默认为友谊赛

    # 根据年份和月份推断
    # 世界杯
    df.loc[df['Year'].isin(world_cup_years) & df['Month'].isin(world_cup_months), 'MatchType'] = 'World Cup'

    # 欧洲杯
    df.loc[df['Year'].isin(euro_years) & df['Month'].isin(euro_months), 'MatchType'] = 'European Championship'

    # 美洲杯
    df.loc[df['Year'].isin(copa_years) & df['Month'].isin([6, 7]), 'MatchType'] = 'Copa America'

    # 非洲杯
    df.loc[df['Year'].isin(afcon_years) & df['Month'].isin([1, 2]), 'MatchType'] = 'Africa Cup of Nations'

    # 亚洲杯
    df.loc[df['Year'].isin(asian_cup_years) & df['Month'].isin([1, 2]), 'MatchType'] = 'Asian Cup'

    # 统计各类型比赛数
    print("\n  比赛类型统计:")
    for match_type, count in df['MatchType'].value_counts().items():
        print(f"    {match_type}: {count}场")

    return df

def create_team_match_summary(df, team_counts):
    """创建各球队比赛统计"""

    print("\n创建各球队比赛统计...")

    summaries = []

    for team in team_counts.index[:50]:  # 前50支球队
        team_matches = df[(df['HomeTeam'] == team) | (df['AwayTeam'] == team)]

        # 主场比赛
        home_matches = team_matches[team_matches['HomeTeam'] == team]
        # 客场比赛
        away_matches = team_matches[team_matches['AwayTeam'] == team]

        # 计算胜负
        home_wins = len(home_matches[home_matches['FTHG'] > home_matches['FTAG']])
        home_draws = len(home_matches[home_matches['FTHG'] == home_matches['FTAG']])
        home_losses = len(home_matches[home_matches['FTHG'] < home_matches['FTAG']])

        away_wins = len(away_matches[away_matches['FTAG'] > away_matches['FTHG']])
        away_draws = len(away_matches[away_matches['FTAG'] == away_matches['FTHG']])
        away_losses = len(away_matches[away_matches['FTAG'] < away_matches['FTHG']])

        # 进球
        home_goals = home_matches['FTHG'].sum()
        away_goals = away_matches['FTAG'].sum()
        home_conceded = home_matches['FTAG'].sum()
        away_conceded = away_matches['FTHG'].sum()

        summaries.append({
            'Team': team,
            'TotalMatches': len(team_matches),
            'HomeMatches': len(home_matches),
            'AwayMatches': len(away_matches),
            'Wins': home_wins + away_wins,
            'Draws': home_draws + away_draws,
            'Losses': home_losses + away_losses,
            'GoalsScored': home_goals + away_goals,
            'GoalsConceded': home_conceded + away_conceded,
            'WinRate': round((home_wins + away_wins) / len(team_matches) * 100, 2) if len(team_matches) > 0 else 0
        })

    summary_df = pd.DataFrame(summaries)

    # 保存统计
    output_file = os.path.join(DATA_DIR, 'national_team_match_summary.csv')
    summary_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"  保存统计: {output_file}")

    return summary_df

def create_team_match_files(df, team_counts):
    """为每个球队创建单独的比赛文件"""

    print("\n创建各球队比赛文件...")

    fifa_teams = load_fifa_teams()

    # 创建球队名称到FIFA代码的映射
    team_to_code = {}
    for code, info in fifa_teams.items():
        team_to_code[info['name_en']] = code

    created = 0
    for team in team_counts.index[:100]:  # 前100支球队
        team_matches = df[(df['HomeTeam'] == team) | (df['AwayTeam'] == team)]

        if len(team_matches) > 0:
            # 获取FIFA代码
            fifa_code = team_to_code.get(team, team[:3].upper())

            # 保存文件
            output_file = os.path.join(DATA_DIR, f'{fifa_code}_{team.replace(" ", "_")}.csv')
            team_matches.to_csv(output_file, index=False, encoding='utf-8-sig')
            created += 1

    print(f"  创建了 {created} 个球队文件")

def main():
    print("=" * 60)
    print(f"国家队完整比赛数据处理 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 分析现有数据
    result = analyze_existing_data()
    if result is None:
        return

    df, team_counts = result

    # 推断比赛类型
    df = classify_match_types(df)

    # 保存带比赛类型的完整数据
    output_file = os.path.join(DATA_DIR, 'all_international_matches_classified.csv')
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n保存分类数据: {output_file}")

    # 创建球队统计
    summary_df = create_team_match_summary(df, team_counts)

    # 创建各球队文件
    create_team_match_files(df, team_counts)

    print("\n" + "=" * 60)
    print("数据处理完成!")
    print("=" * 60)

    # 显示统计
    print(f"\n数据统计:")
    print(f"  总比赛数: {len(df)}")
    print(f"  涉及球队: {len(team_counts)}")
    print(f"  年份范围: {int(df['Year'].min())} - {int(df['Year'].max())}")

    print(f"\n前10球队比赛数:")
    for _, row in summary_df.head(10).iterrows():
        print(f"  {row['Team']}: {row['TotalMatches']}场 (胜率{row['WinRate']}%)")

if __name__ == '__main__':
    main()
