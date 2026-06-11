"""
实时赛果更新系统
使用Tavily API获取今日比赛结果，并更新到CSV文件
"""
import os
import json
import requests
import pandas as pd
from datetime import datetime

# API配置
TAVILY_API_KEY = "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"

DATA_DIR = 'd:/football_tools/data'
NO_PROXY = {'http': None, 'https': None}


def search_tavily(query):
    """使用Tavily搜索"""
    url = "https://api.tavily.com/search"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TAVILY_API_KEY}"
    }
    data = {
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "include_raw_content": True,
        "max_results": 15
    }

    try:
        session = requests.Session()
        session.trust_env = False
        session.proxies = NO_PROXY
        response = session.post(url, headers=headers, json=data, timeout=60)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Tavily请求失败: {e}")
    return None


def parse_match_result(text):
    """从文本解析比赛结果"""
    import re

    # 匹配比分格式: Team1 3-2 Team2 或 Team1 1-0 Team2
    patterns = [
        r'(\w+(?:\s+\w+)*)\s+(\d+)-(\d+)\s+(\w+(?:\s+\w+)*)',
        r'(\w+(?:\s+\w+)*)\s+defeated\s+(\w+(?:\s+\w+)*)\s+(\d+)-(\d+)',
        r'(\w+(?:\s+\w+)*)\s+beat\s+(\w+(?:\s+\w+)*)\s+(\d+)-(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            if 'defeated' in pattern or 'beat' in pattern:
                return {
                    'home_team': groups[0],
                    'away_team': groups[1],
                    'home_goals': int(groups[2]),
                    'away_goals': int(groups[3])
                }
            else:
                return {
                    'home_team': groups[0],
                    'home_goals': int(groups[1]),
                    'away_goals': int(groups[2]),
                    'away_team': groups[3]
                }
    return None


def get_today_premier_league_results():
    """获取今日英超结果"""
    today = datetime.now().strftime('%Y-%m-%d')

    queries = [
        f"Premier League results today {today}",
        f"English Premier League match results May 18 2026",
        f"Arsenal Burnley result today",
        f"Manchester United Nottingham Forest result today",
    ]

    matches = []

    for query in queries:
        print(f"搜索: {query}")
        result = search_tavily(query)

        if result:
            answer = result.get('answer', '')
            print(f"  回答: {answer}")

            # 解析比赛结果
            parsed = parse_match_result(answer)
            if parsed:
                parsed['date'] = today
                parsed['league'] = 'Premier League'
                matches.append(parsed)

            # 从搜索结果中解析
            for r in result.get('results', []):
                content = r.get('content', '')
                parsed = parse_match_result(content)
                if parsed:
                    parsed['date'] = today
                    parsed['league'] = 'Premier League'
                    if parsed not in matches:
                        matches.append(parsed)

    return matches


def update_premier_league_csv(matches):
    """更新英超CSV文件"""
    if not matches:
        print("没有新比赛数据")
        return

    season = "2025-2026"
    csv_path = os.path.join(DATA_DIR, '01_leagues', 'england', f'premier_league_{season}.csv')

    if not os.path.exists(csv_path):
        print(f"CSV文件不存在: {csv_path}")
        return

    # 读取现有数据
    df = pd.read_csv(csv_path, encoding='utf-8')

    # 添加新比赛
    today = datetime.now().strftime('%Y-%m-%d')
    new_rows = []

    for match in matches:
        # 检查是否已存在
        existing = df[(df['Date'] == today) &
                      (df['HomeTeam'] == match['home_team']) &
                      (df['AwayTeam'] == match['away_team'])]

        if len(existing) == 0:
            # 确定结果
            if match['home_goals'] > match['away_goals']:
                ftr = 'H'
            elif match['home_goals'] < match['away_goals']:
                ftr = 'A'
            else:
                ftr = 'D'

            new_row = {
                'Date': today,
                'HomeTeam': match['home_team'],
                'AwayTeam': match['away_team'],
                'FTHG': match['home_goals'],
                'FTAG': match['away_goals'],
                'FTR': ftr,
                'Div': 'E0',
                'Season': season,
            }
            new_rows.append(new_row)
            print(f"  新增: {match['home_team']} {match['home_goals']}-{match['away_goals']} {match['away_team']}")

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        df = pd.concat([df, new_df], ignore_index=True)
        df = df.sort_values('Date')
        df.to_csv(csv_path, index=False, encoding='utf-8')
        print(f"\n已更新 {len(new_rows)} 条新记录到 {csv_path}")
    else:
        print("所有比赛已存在于CSV中")


def main():
    print("=" * 60)
    print(f"实时赛果更新 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 获取今日英超结果
    print("\n获取今日英超比赛结果...")
    matches = get_today_premier_league_results()

    print(f"\n解析到 {len(matches)} 场比赛:")
    for m in matches:
        print(f"  {m.get('home_team', 'N/A')} {m.get('home_goals', '?')}-{m.get('away_goals', '?')} {m.get('away_team', 'N/A')}")

    # 更新CSV
    print("\n更新CSV文件...")
    update_premier_league_csv(matches)

    print("\n完成!")


if __name__ == '__main__':
    main()