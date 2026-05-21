"""
从多个数据源采集世界杯详细比赛数据
包括每场比赛的具体比分、日期、阶段等信息
"""
import requests
import pandas as pd
import os
from datetime import datetime
import time
import re
from bs4 import BeautifulSoup

DATA_DIR = 'd:/football_tools/data/04_international/world_cup_historical'
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
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    return session

def fetch_world_cup_matches_from_api():
    """从开放API获取世界杯数据"""

    print("\n尝试从开放API获取世界杯数据...")

    session = get_session()

    # 尝试多个API源
    api_sources = [
        # Open Football Data
        "https://raw.githubusercontent.com/openfootball/world-cup.json/master/2014-world-cup.json",
        "https://raw.githubusercontent.com/openfootball/world-cup.json/master/2018-world-cup.json",
        "https://raw.githubusercontent.com/openfootball/world-cup.json/master/2022-world-cup.json",

        # 其他数据源
        "https://raw.githubusercontent.com/estees/worldcup/master/data/worldcup.json",
    ]

    all_matches = []

    for url in api_sources:
        try:
            print(f"  尝试: {url}")
            response = session.get(url, timeout=30)

            if response.status_code == 200:
                data = response.json()
                matches = parse_json_data(data, url)
                if matches:
                    all_matches.extend(matches)
                    print(f"    获取 {len(matches)} 场比赛")
            else:
                print(f"    状态码: {response.status_code}")

        except Exception as e:
            print(f"    错误: {e}")

        time.sleep(0.5)

    return all_matches

def parse_json_data(data, url):
    """解析JSON数据"""
    matches = []

    try:
        # 解析openfootball格式
        if 'rounds' in data:
            year = extract_year_from_url(url)
            for round_data in data['rounds']:
                round_name = round_data.get('name', '')
                for match in round_data.get('matches', []):
                    matches.append({
                        'Year': year,
                        'Round': round_name,
                        'Date': match.get('date', ''),
                        'HomeTeam': match.get('team1', {}).get('name', '') if isinstance(match.get('team1'), dict) else match.get('team1', ''),
                        'AwayTeam': match.get('team2', {}).get('name', '') if isinstance(match.get('team2'), dict) else match.get('team2', ''),
                        'HomeGoals': match.get('score1', match.get('team1', {}).get('score') if isinstance(match.get('team1'), dict) else None),
                        'AwayGoals': match.get('score2', match.get('team2', {}).get('score') if isinstance(match.get('team2'), dict) else None),
                        'Source': 'openfootball'
                    })

        # 解析其他格式
        elif 'matches' in data:
            for match in data['matches']:
                matches.append({
                    'Year': match.get('year', extract_year_from_url(url)),
                    'Round': match.get('round', match.get('stage', '')),
                    'Date': match.get('date', ''),
                    'HomeTeam': match.get('home_team', match.get('team1', '')),
                    'AwayTeam': match.get('away_team', match.get('team2', '')),
                    'HomeGoals': match.get('home_goals', match.get('score1')),
                    'AwayGoals': match.get('away_goals', match.get('score2')),
                    'Source': 'api'
                })

    except Exception as e:
        print(f"    解析错误: {e}")

    return matches

def extract_year_from_url(url):
    """从URL提取年份"""
    year_match = re.search(r'(\d{4})', url)
    return int(year_match.group(1)) if year_match else None

def fetch_from_github_datasets():
    """从GitHub数据集获取世界杯数据"""

    print("\n尝试从GitHub数据集获取...")

    session = get_session()

    # GitHub上的世界杯数据集
    github_sources = [
        "https://raw.githubusercontent.com/datasets/world-cup/master/data/world-cup.csv",
        "https://raw.githubusercontent.com/football-data/football-data/master/data/world-cup.csv",
        "https://raw.githubusercontent.com/jfjelstul/worldcup/master/data/matches.csv",
    ]

    all_matches = []

    for url in github_sources:
        try:
            print(f"  尝试: {url}")
            response = session.get(url, timeout=30)

            if response.status_code == 200:
                # 尝试解析CSV
                try:
                    df = pd.read_csv(pd.io.common.StringIO(response.text))
                    matches = df.to_dict('records')
                    all_matches.extend(matches)
                    print(f"    获取 {len(matches)} 条记录")
                    print(f"    列: {list(df.columns)}")
                except:
                    print(f"    CSV解析失败")

            else:
                print(f"    状态码: {response.status_code}")

        except Exception as e:
            print(f"    错误: {e}")

        time.sleep(0.5)

    return all_matches

def create_detailed_world_cup_matches():
    """创建详细的世界杯比赛数据"""

    print("\n创建详细世界杯比赛数据...")

    # 手动录入历史世界杯关键比赛数据
    # 数据来源：Wikipedia + FIFA官方记录

    detailed_matches = []

    # 1930 乌拉圭世界杯
    detailed_matches.extend([
        {'Year': 1930, 'Round': 'Final', 'Date': '1930-07-30', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Argentina', 'HomeGoals': 4, 'AwayGoals': 2},
        {'Year': 1930, 'Round': 'Semi-final', 'Date': '1930-07-27', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 6, 'AwayGoals': 1},
        {'Year': 1930, 'Round': 'Semi-final', 'Date': '1930-07-26', 'HomeTeam': 'Argentina', 'AwayTeam': 'USA', 'HomeGoals': 6, 'AwayGoals': 1},
    ])

    # 1934 意大利世界杯
    detailed_matches.extend([
        {'Year': 1934, 'Round': 'Final', 'Date': '1934-06-10', 'HomeTeam': 'Italy', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 2, 'AwayGoals': 1},
        {'Year': 1934, 'Round': 'Semi-final', 'Date': '1934-06-03', 'HomeTeam': 'Italy', 'AwayTeam': 'Austria', 'HomeGoals': 1, 'AwayGoals': 0},
        {'Year': 1934, 'Round': 'Semi-final', 'Date': '1934-06-03', 'HomeTeam': 'Czechoslovakia', 'AwayTeam': 'Germany', 'HomeGoals': 3, 'AwayGoals': 1},
    ])

    # 1938 法国世界杯
    detailed_matches.extend([
        {'Year': 1938, 'Round': 'Final', 'Date': '1938-06-19', 'HomeTeam': 'Italy', 'AwayTeam': 'Hungary', 'HomeGoals': 4, 'AwayGoals': 2},
        {'Year': 1938, 'Round': 'Semi-final', 'Date': '1938-06-16', 'HomeTeam': 'Hungary', 'AwayTeam': 'Sweden', 'HomeGoals': 5, 'AwayGoals': 1},
        {'Year': 1938, 'Round': 'Semi-final', 'Date': '1938-06-16', 'HomeTeam': 'Italy', 'AwayTeam': 'Brazil', 'HomeGoals': 2, 'AwayGoals': 1},
    ])

    # 1950 巴西世界杯 (决赛循环赛)
    detailed_matches.extend([
        {'Year': 1950, 'Round': 'Final Round', 'Date': '1950-07-16', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Brazil', 'HomeGoals': 2, 'AwayGoals': 1},
        {'Year': 1950, 'Round': 'Final Round', 'Date': '1950-07-13', 'HomeTeam': 'Brazil', 'AwayTeam': 'Sweden', 'HomeGoals': 7, 'AwayGoals': 1},
        {'Year': 1950, 'Round': 'Final Round', 'Date': '1950-07-09', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Spain', 'HomeGoals': 2, 'AwayGoals': 2},
    ])

    # 1954 瑞士世界杯
    detailed_matches.extend([
        {'Year': 1954, 'Round': 'Final', 'Date': '1954-07-04', 'HomeTeam': 'West Germany', 'AwayTeam': 'Hungary', 'HomeGoals': 3, 'AwayGoals': 2},
        {'Year': 1954, 'Round': 'Semi-final', 'Date': '1954-06-27', 'HomeTeam': 'Hungary', 'AwayTeam': 'Uruguay', 'HomeGoals': 4, 'AwayGoals': 2},
        {'Year': 1954, 'Round': 'Semi-final', 'Date': '1954-06-27', 'HomeTeam': 'West Germany', 'AwayTeam': 'Austria', 'HomeGoals': 6, 'AwayGoals': 1},
    ])

    # 1958 瑞典世界杯
    detailed_matches.extend([
        {'Year': 1958, 'Round': 'Final', 'Date': '1958-06-29', 'HomeTeam': 'Brazil', 'AwayTeam': 'Sweden', 'HomeGoals': 5, 'AwayGoals': 2},
        {'Year': 1958, 'Round': 'Semi-final', 'Date': '1958-06-24', 'HomeTeam': 'Sweden', 'AwayTeam': 'West Germany', 'HomeGoals': 3, 'AwayGoals': 1},
        {'Year': 1958, 'Round': 'Semi-final', 'Date': '1958-06-24', 'HomeTeam': 'Brazil', 'AwayTeam': 'France', 'HomeGoals': 5, 'AwayGoals': 2},
    ])

    # 1962 智利世界杯
    detailed_matches.extend([
        {'Year': 1962, 'Round': 'Final', 'Date': '1962-06-17', 'HomeTeam': 'Brazil', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 3, 'AwayGoals': 1},
        {'Year': 1962, 'Round': 'Semi-final', 'Date': '1962-06-13', 'HomeTeam': 'Czechoslovakia', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 3, 'AwayGoals': 1},
        {'Year': 1962, 'Round': 'Semi-final', 'Date': '1962-06-13', 'HomeTeam': 'Brazil', 'AwayTeam': 'Chile', 'HomeGoals': 4, 'AwayGoals': 2},
    ])

    # 1966 英格兰世界杯
    detailed_matches.extend([
        {'Year': 1966, 'Round': 'Final', 'Date': '1966-07-30', 'HomeTeam': 'England', 'AwayTeam': 'West Germany', 'HomeGoals': 4, 'AwayGoals': 2},
        {'Year': 1966, 'Round': 'Semi-final', 'Date': '1966-07-26', 'HomeTeam': 'England', 'AwayTeam': 'Portugal', 'HomeGoals': 2, 'AwayGoals': 1},
        {'Year': 1966, 'Round': 'Semi-final', 'Date': '1966-07-25', 'HomeTeam': 'West Germany', 'AwayTeam': 'Soviet Union', 'HomeGoals': 2, 'AwayGoals': 1},
    ])

    # 1970 墨西哥世界杯
    detailed_matches.extend([
        {'Year': 1970, 'Round': 'Final', 'Date': '1970-06-21', 'HomeTeam': 'Brazil', 'AwayTeam': 'Italy', 'HomeGoals': 4, 'AwayGoals': 1},
        {'Year': 1970, 'Round': 'Semi-final', 'Date': '1970-06-17', 'HomeTeam': 'Italy', 'AwayTeam': 'West Germany', 'HomeGoals': 4, 'AwayGoals': 3},
        {'Year': 1970, 'Round': 'Semi-final', 'Date': '1970-06-17', 'HomeTeam': 'Brazil', 'AwayTeam': 'Uruguay', 'HomeGoals': 3, 'AwayGoals': 1},
    ])

    # 1974 西德世界杯
    detailed_matches.extend([
        {'Year': 1974, 'Round': 'Final', 'Date': '1974-07-07', 'HomeTeam': 'West Germany', 'AwayTeam': 'Netherlands', 'HomeGoals': 2, 'AwayGoals': 1},
        {'Year': 1974, 'Round': 'Semi-final', 'Date': '1974-07-03', 'HomeTeam': 'Netherlands', 'AwayTeam': 'Brazil', 'HomeGoals': 2, 'AwayGoals': 0},
        {'Year': 1974, 'Round': 'Semi-final', 'Date': '1974-07-03', 'HomeTeam': 'West Germany', 'AwayTeam': 'Poland', 'HomeGoals': 1, 'AwayGoals': 0},
    ])

    # 1978 阿根廷世界杯
    detailed_matches.extend([
        {'Year': 1978, 'Round': 'Final', 'Date': '1978-06-25', 'HomeTeam': 'Argentina', 'AwayTeam': 'Netherlands', 'HomeGoals': 3, 'AwayGoals': 1},
        {'Year': 1978, 'Round': 'Semi-final', 'Date': '1978-06-21', 'HomeTeam': 'Argentina', 'AwayTeam': 'Peru', 'HomeGoals': 6, 'AwayGoals': 0},
        {'Year': 1978, 'Round': 'Semi-final', 'Date': '1978-06-20', 'HomeTeam': 'Netherlands', 'AwayTeam': 'Italy', 'HomeGoals': 2, 'AwayGoals': 1},
    ])

    # 1982 西班牙世界杯
    detailed_matches.extend([
        {'Year': 1982, 'Round': 'Final', 'Date': '1982-07-11', 'HomeTeam': 'Italy', 'AwayTeam': 'West Germany', 'HomeGoals': 3, 'AwayGoals': 1},
        {'Year': 1982, 'Round': 'Semi-final', 'Date': '1982-07-08', 'HomeTeam': 'West Germany', 'AwayTeam': 'France', 'HomeGoals': 3, 'AwayGoals': 3, 'ExtraTime': '5-4', 'Notes': '点球'},
        {'Year': 1982, 'Round': 'Semi-final', 'Date': '1982-07-05', 'HomeTeam': 'Italy', 'AwayTeam': 'Poland', 'HomeGoals': 2, 'AwayGoals': 0},
    ])

    # 1986 墨西哥世界杯
    detailed_matches.extend([
        {'Year': 1986, 'Round': 'Final', 'Date': '1986-06-29', 'HomeTeam': 'Argentina', 'AwayTeam': 'West Germany', 'HomeGoals': 3, 'AwayGoals': 2},
        {'Year': 1986, 'Round': 'Semi-final', 'Date': '1986-06-25', 'HomeTeam': 'Argentina', 'AwayTeam': 'Belgium', 'HomeGoals': 2, 'AwayGoals': 0},
        {'Year': 1986, 'Round': 'Semi-final', 'Date': '1986-06-25', 'HomeTeam': 'West Germany', 'AwayTeam': 'France', 'HomeGoals': 2, 'AwayGoals': 0},
    ])

    # 1990 意大利世界杯
    detailed_matches.extend([
        {'Year': 1990, 'Round': 'Final', 'Date': '1990-07-08', 'HomeTeam': 'West Germany', 'AwayTeam': 'Argentina', 'HomeGoals': 1, 'AwayGoals': 0},
        {'Year': 1990, 'Round': 'Semi-final', 'Date': '1990-07-04', 'HomeTeam': 'Argentina', 'AwayTeam': 'Italy', 'HomeGoals': 1, 'AwayGoals': 1, 'ExtraTime': '1-1', 'Notes': '点球4-3'},
        {'Year': 1990, 'Round': 'Semi-final', 'Date': '1990-07-04', 'HomeTeam': 'West Germany', 'AwayTeam': 'England', 'HomeGoals': 1, 'AwayGoals': 1, 'ExtraTime': '1-1', 'Notes': '点球4-3'},
    ])

    # 1994 美国世界杯
    detailed_matches.extend([
        {'Year': 1994, 'Round': 'Final', 'Date': '1994-07-17', 'HomeTeam': 'Brazil', 'AwayTeam': 'Italy', 'HomeGoals': 0, 'AwayGoals': 0, 'ExtraTime': '0-0', 'Notes': '点球3-2'},
        {'Year': 1994, 'Round': 'Semi-final', 'Date': '1994-07-13', 'HomeTeam': 'Brazil', 'AwayTeam': 'Sweden', 'HomeGoals': 1, 'AwayGoals': 0},
        {'Year': 1994, 'Round': 'Semi-final', 'Date': '1994-07-13', 'HomeTeam': 'Italy', 'AwayTeam': 'Bulgaria', 'HomeGoals': 2, 'AwayGoals': 1},
    ])

    # 1998 法国世界杯
    detailed_matches.extend([
        {'Year': 1998, 'Round': 'Final', 'Date': '1998-07-12', 'HomeTeam': 'France', 'AwayTeam': 'Brazil', 'HomeGoals': 3, 'AwayGoals': 0},
        {'Year': 1998, 'Round': 'Semi-final', 'Date': '1998-07-08', 'HomeTeam': 'France', 'AwayTeam': 'Croatia', 'HomeGoals': 2, 'AwayGoals': 1},
        {'Year': 1998, 'Round': 'Semi-final', 'Date': '1998-07-07', 'HomeTeam': 'Brazil', 'AwayTeam': 'Netherlands', 'HomeGoals': 1, 'AwayGoals': 1, 'ExtraTime': '1-1', 'Notes': '点球4-2'},
    ])

    return detailed_matches

def save_all_world_cup_data():
    """保存所有世界杯数据"""

    print("\n保存世界杯数据...")

    # 获取API数据
    api_matches = fetch_world_cup_matches_from_api()

    # 获取GitHub数据
    github_matches = fetch_from_github_datasets()

    # 创建详细比赛数据
    detailed_matches = create_detailed_world_cup_matches()

    # 合并所有数据
    all_matches = []

    # 添加API数据
    for m in api_matches:
        all_matches.append({
            'Year': m.get('Year'),
            'Round': m.get('Round', ''),
            'Date': m.get('Date', ''),
            'HomeTeam': m.get('HomeTeam', ''),
            'AwayTeam': m.get('AwayTeam', ''),
            'HomeGoals': m.get('HomeGoals'),
            'AwayGoals': m.get('AwayGoals'),
            'ExtraTime': m.get('ExtraTime', ''),
            'Penalty': m.get('Notes', ''),
            'Source': m.get('Source', 'api')
        })

    # 添加详细比赛数据
    for m in detailed_matches:
        all_matches.append({
            'Year': m.get('Year'),
            'Round': m.get('Round', ''),
            'Date': m.get('Date', ''),
            'HomeTeam': m.get('HomeTeam', ''),
            'AwayTeam': m.get('AwayTeam', ''),
            'HomeGoals': m.get('HomeGoals'),
            'AwayGoals': m.get('AwayGoals'),
            'ExtraTime': m.get('ExtraTime', ''),
            'Penalty': m.get('Notes', ''),
            'Source': 'historical'
        })

    # 保存为CSV
    if all_matches:
        df = pd.DataFrame(all_matches)
        df = df.drop_duplicates(subset=['Year', 'HomeTeam', 'AwayTeam'], keep='first')
        df = df.sort_values(['Year', 'Date'])

        output_file = os.path.join(DATA_DIR, 'world_cup_matches_detailed.csv')
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"  保存详细比赛数据: {output_file}")
        print(f"  总比赛数: {len(df)}")

        # 显示统计
        print(f"\n各年份比赛数:")
        year_counts = df.groupby('Year').size()
        for year, count in year_counts.items():
            print(f"  {year}: {count}场")

    return all_matches

def main():
    print("=" * 60)
    print(f"世界杯详细比赛数据采集 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 保存所有数据
    save_all_world_cup_data()

    print("\n" + "=" * 60)
    print("数据采集完成!")
    print("=" * 60)

if __name__ == '__main__':
    main()