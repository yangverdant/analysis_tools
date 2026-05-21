"""
采集世界杯历史数据
从多个数据源采集完整的世界杯比赛数据（1930-2022）
"""
import requests
import pandas as pd
import os
from datetime import datetime
import time
import json

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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    return session

def fetch_world_cup_data():
    """从Wikipedia采集世界杯历史数据"""

    # 世界杯年份列表
    world_cup_years = [1930, 1934, 1938, 1950, 1954, 1958, 1962, 1966, 1970, 1974,
                       1978, 1982, 1986, 1990, 1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022]

    all_matches = []

    print("开始采集世界杯历史数据...")

    for year in world_cup_years:
        print(f"\n采集 {year} 年世界杯...")

        # 尝试从不同数据源获取
        matches = fetch_from_wikipedia(year)
        if matches:
            all_matches.extend(matches)
            print(f"  从Wikipedia获取 {len(matches)} 场比赛")
        else:
            print(f"  {year} 年数据获取失败")

        time.sleep(1)

    return all_matches

def fetch_from_wikipedia(year):
    """从Wikipedia获取世界杯数据"""
    session = get_session()

    # Wikipedia URL
    url = f"https://en.wikipedia.org/wiki/{year}_FIFA_World_Cup"

    try:
        response = session.get(url, timeout=30)
        if response.status_code != 200:
            return []

        # 解析HTML获取比赛数据
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        matches = []

        # 查找比赛结果表格
        tables = soup.find_all('table', {'class': 'wikitable'})

        for table in tables:
            rows = table.find_all('tr')
            for row in rows[1:]:  # 跳过表头
                cells = row.find_all('td')
                if len(cells) >= 3:
                    try:
                        # 尝试解析比赛数据
                        match = parse_match_row(cells, year)
                        if match:
                            matches.append(match)
                    except:
                        continue

        return matches

    except Exception as e:
        print(f"  Wikipedia获取失败: {e}")
        return []

def parse_match_row(cells, year):
    """解析比赛行"""
    try:
        # 尝试提取比分
        text = ' '.join([cell.get_text(strip=True) for cell in cells])

        # 查找比分格式 (如 "3–1", "2-0")
        import re
        score_pattern = r'(\d+)\s*[–\-]\s*(\d+)'
        match = re.search(score_pattern, text)

        if match:
            home_score = int(match.group(1))
            away_score = int(match.group(2))

            # 提取球队名称
            parts = text.split(match.group(0))
            if len(parts) >= 2:
                home_team = parts[0].strip().split()[-1] if parts[0].strip() else ""
                away_team = parts[1].strip().split()[0] if parts[1].strip() else ""

                return {
                    'Year': year,
                    'HomeTeam': home_team,
                    'AwayTeam': away_team,
                    'HomeGoals': home_score,
                    'AwayGoals': away_score,
                    'Source': 'Wikipedia'
                }
    except:
        pass

    return None

def create_world_cup_database():
    """创建完整的世界杯数据库"""

    # 手动录入的历史世界杯决赛阶段比赛数据（1930-1998）
    # 数据来源：Wikipedia + FIFA官方记录
    historical_matches = [
        # 1930 乌拉圭世界杯
        {'Year': 1930, 'Host': 'Uruguay', 'Winner': 'Uruguay', 'RunnerUp': 'Argentina', 'Matches': 18},
        # 1934 意大利世界杯
        {'Year': 1934, 'Host': 'Italy', 'Winner': 'Italy', 'RunnerUp': 'Czechoslovakia', 'Matches': 17},
        # 1938 法国世界杯
        {'Year': 1938, 'Host': 'France', 'Winner': 'Italy', 'RunnerUp': 'Hungary', 'Matches': 18},
        # 1950 巴西世界杯
        {'Year': 1950, 'Host': 'Brazil', 'Winner': 'Uruguay', 'RunnerUp': 'Brazil', 'Matches': 22},
        # 1954 瑞士世界杯
        {'Year': 1954, 'Host': 'Switzerland', 'Winner': 'West Germany', 'RunnerUp': 'Hungary', 'Matches': 26},
        # 1958 瑞典世界杯
        {'Year': 1958, 'Host': 'Sweden', 'Winner': 'Brazil', 'RunnerUp': 'Sweden', 'Matches': 35},
        # 1962 智利世界杯
        {'Year': 1962, 'Host': 'Chile', 'Winner': 'Brazil', 'RunnerUp': 'Czechoslovakia', 'Matches': 32},
        # 1966 英格兰世界杯
        {'Year': 1966, 'Host': 'England', 'Winner': 'England', 'RunnerUp': 'West Germany', 'Matches': 32},
        # 1970 墨西哥世界杯
        {'Year': 1970, 'Host': 'Mexico', 'Winner': 'Brazil', 'RunnerUp': 'Italy', 'Matches': 32},
        # 1974 西德世界杯
        {'Year': 1974, 'Host': 'West Germany', 'Winner': 'West Germany', 'RunnerUp': 'Netherlands', 'Matches': 38},
        # 1978 阿根廷世界杯
        {'Year': 1978, 'Host': 'Argentina', 'Winner': 'Argentina', 'RunnerUp': 'Netherlands', 'Matches': 38},
        # 1982 西班牙世界杯
        {'Year': 1982, 'Host': 'Spain', 'Winner': 'Italy', 'RunnerUp': 'West Germany', 'Matches': 52},
        # 1986 墨西哥世界杯
        {'Year': 1986, 'Host': 'Mexico', 'Winner': 'Argentina', 'RunnerUp': 'West Germany', 'Matches': 52},
        # 1990 意大利世界杯
        {'Year': 1990, 'Host': 'Italy', 'Winner': 'West Germany', 'RunnerUp': 'Argentina', 'Matches': 52},
        # 1994 美国世界杯
        {'Year': 1994, 'Host': 'USA', 'Winner': 'Brazil', 'RunnerUp': 'Italy', 'Matches': 52},
        # 1998 法国世界杯
        {'Year': 1998, 'Host': 'France', 'Winner': 'France', 'RunnerUp': 'Brazil', 'Matches': 64},
    ]

    return historical_matches

def download_from_football_data():
    """从football-data.co.uk下载世界杯数据"""

    print("\n尝试从football-data.co.uk获取数据...")

    session = get_session()
    base_url = "https://www.football-data.co.uk"

    # 尝试获取国际比赛数据
    try:
        response = session.get(f"{base_url}/data.php", timeout=30)
        print(f"  连接状态: {response.status_code}")

        if response.status_code == 200:
            # 解析页面查找世界杯数据链接
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            links = soup.find_all('a')
            for link in links:
                href = link.get('href', '')
                text = link.get_text()
                if 'world' in text.lower() or 'wc' in href.lower():
                    print(f"  找到链接: {text} -> {href}")

    except Exception as e:
        print(f"  获取失败: {e}")

def create_comprehensive_world_cup_csv():
    """创建综合世界杯CSV文件"""

    print("\n创建综合世界杯数据文件...")

    # 读取已有的世界杯数据
    existing_file = 'd:/football_tools/data/04_international/world_cup/world_cup_all.csv'

    if os.path.exists(existing_file):
        df_existing = pd.read_csv(existing_file)
        print(f"  已有数据: {len(df_existing)} 场比赛 (2002-2026)")

    # 创建世界杯历史统计文件
    wc_history = [
        {'Year': 1930, 'Host': 'Uruguay', 'Host_CN': '乌拉圭', 'Winner': 'Uruguay', 'Winner_CN': '乌拉圭',
         'RunnerUp': 'Argentina', 'RunnerUp_CN': '阿根廷', 'Third': 'USA', 'Third_CN': '美国',
         'Fourth': 'Yugoslavia', 'Fourth_CN': '南斯拉夫', 'Teams': 13, 'Matches': 18, 'Goals': 70},

        {'Year': 1934, 'Host': 'Italy', 'Host_CN': '意大利', 'Winner': 'Italy', 'Winner_CN': '意大利',
         'RunnerUp': 'Czechoslovakia', 'RunnerUp_CN': '捷克斯洛伐克', 'Third': 'Germany', 'Third_CN': '德国',
         'Fourth': 'Austria', 'Fourth_CN': '奥地利', 'Teams': 16, 'Matches': 17, 'Goals': 70},

        {'Year': 1938, 'Host': 'France', 'Host_CN': '法国', 'Winner': 'Italy', 'Winner_CN': '意大利',
         'RunnerUp': 'Hungary', 'RunnerUp_CN': '匈牙利', 'Third': 'Brazil', 'Third_CN': '巴西',
         'Fourth': 'Sweden', 'Fourth_CN': '瑞典', 'Teams': 15, 'Matches': 18, 'Goals': 84},

        {'Year': 1950, 'Host': 'Brazil', 'Host_CN': '巴西', 'Winner': 'Uruguay', 'Winner_CN': '乌拉圭',
         'RunnerUp': 'Brazil', 'RunnerUp_CN': '巴西', 'Third': 'Sweden', 'Third_CN': '瑞典',
         'Fourth': 'Spain', 'Fourth_CN': '西班牙', 'Teams': 13, 'Matches': 22, 'Goals': 88},

        {'Year': 1954, 'Host': 'Switzerland', 'Host_CN': '瑞士', 'Winner': 'West Germany', 'Winner_CN': '西德',
         'RunnerUp': 'Hungary', 'RunnerUp_CN': '匈牙利', 'Third': 'Austria', 'Third_CN': '奥地利',
         'Fourth': 'Uruguay', 'Fourth_CN': '乌拉圭', 'Teams': 16, 'Matches': 26, 'Goals': 140},

        {'Year': 1958, 'Host': 'Sweden', 'Host_CN': '瑞典', 'Winner': 'Brazil', 'Winner_CN': '巴西',
         'RunnerUp': 'Sweden', 'RunnerUp_CN': '瑞典', 'Third': 'France', 'Third_CN': '法国',
         'Fourth': 'West Germany', 'Fourth_CN': '西德', 'Teams': 16, 'Matches': 35, 'Goals': 126},

        {'Year': 1962, 'Host': 'Chile', 'Host_CN': '智利', 'Winner': 'Brazil', 'Winner_CN': '巴西',
         'RunnerUp': 'Czechoslovakia', 'RunnerUp_CN': '捷克斯洛伐克', 'Third': 'Chile', 'Third_CN': '智利',
         'Fourth': 'Yugoslavia', 'Fourth_CN': '南斯拉夫', 'Teams': 16, 'Matches': 32, 'Goals': 89},

        {'Year': 1966, 'Host': 'England', 'Host_CN': '英格兰', 'Winner': 'England', 'Winner_CN': '英格兰',
         'RunnerUp': 'West Germany', 'RunnerUp_CN': '西德', 'Third': 'Portugal', 'Third_CN': '葡萄牙',
         'Fourth': 'Soviet Union', 'Fourth_CN': '苏联', 'Teams': 16, 'Matches': 32, 'Goals': 89},

        {'Year': 1970, 'Host': 'Mexico', 'Host_CN': '墨西哥', 'Winner': 'Brazil', 'Winner_CN': '巴西',
         'RunnerUp': 'Italy', 'RunnerUp_CN': '意大利', 'Third': 'West Germany', 'Third_CN': '西德',
         'Fourth': 'Uruguay', 'Fourth_CN': '乌拉圭', 'Teams': 16, 'Matches': 32, 'Goals': 95},

        {'Year': 1974, 'Host': 'West Germany', 'Host_CN': '西德', 'Winner': 'West Germany', 'Winner_CN': '西德',
         'RunnerUp': 'Netherlands', 'RunnerUp_CN': '荷兰', 'Third': 'Poland', 'Third_CN': '波兰',
         'Fourth': 'Brazil', 'Fourth_CN': '巴西', 'Teams': 16, 'Matches': 38, 'Goals': 97},

        {'Year': 1978, 'Host': 'Argentina', 'Host_CN': '阿根廷', 'Winner': 'Argentina', 'Winner_CN': '阿根廷',
         'RunnerUp': 'Netherlands', 'RunnerUp_CN': '荷兰', 'Third': 'Brazil', 'Third_CN': '巴西',
         'Fourth': 'Italy', 'Fourth_CN': '意大利', 'Teams': 16, 'Matches': 38, 'Goals': 102},

        {'Year': 1982, 'Host': 'Spain', 'Host_CN': '西班牙', 'Winner': 'Italy', 'Winner_CN': '意大利',
         'RunnerUp': 'West Germany', 'RunnerUp_CN': '西德', 'Third': 'Poland', 'Third_CN': '波兰',
         'Fourth': 'France', 'Fourth_CN': '法国', 'Teams': 24, 'Matches': 52, 'Goals': 146},

        {'Year': 1986, 'Host': 'Mexico', 'Host_CN': '墨西哥', 'Winner': 'Argentina', 'Winner_CN': '阿根廷',
         'RunnerUp': 'West Germany', 'RunnerUp_CN': '西德', 'Third': 'France', 'Third_CN': '法国',
         'Fourth': 'Belgium', 'Fourth_CN': '比利时', 'Teams': 24, 'Matches': 52, 'Goals': 132},

        {'Year': 1990, 'Host': 'Italy', 'Host_CN': '意大利', 'Winner': 'West Germany', 'Winner_CN': '西德',
         'RunnerUp': 'Argentina', 'RunnerUp_CN': '阿根廷', 'Third': 'Italy', 'Third_CN': '意大利',
         'Fourth': 'England', 'Fourth_CN': '英格兰', 'Teams': 24, 'Matches': 52, 'Goals': 115},

        {'Year': 1994, 'Host': 'USA', 'Host_CN': '美国', 'Winner': 'Brazil', 'Winner_CN': '巴西',
         'RunnerUp': 'Italy', 'RunnerUp_CN': '意大利', 'Third': 'Sweden', 'Third_CN': '瑞典',
         'Fourth': 'Bulgaria', 'Fourth_CN': '保加利亚', 'Teams': 24, 'Matches': 52, 'Goals': 141},

        {'Year': 1998, 'Host': 'France', 'Host_CN': '法国', 'Winner': 'France', 'Winner_CN': '法国',
         'RunnerUp': 'Brazil', 'RunnerUp_CN': '巴西', 'Third': 'Croatia', 'Third_CN': '克罗地亚',
         'Fourth': 'Netherlands', 'Fourth_CN': '荷兰', 'Teams': 32, 'Matches': 64, 'Goals': 171},

        {'Year': 2002, 'Host': 'South Korea/Japan', 'Host_CN': '韩国/日本', 'Winner': 'Brazil', 'Winner_CN': '巴西',
         'RunnerUp': 'Germany', 'RunnerUp_CN': '德国', 'Third': 'Turkey', 'Third_CN': '土耳其',
         'Fourth': 'South Korea', 'Fourth_CN': '韩国', 'Teams': 32, 'Matches': 64, 'Goals': 161},

        {'Year': 2006, 'Host': 'Germany', 'Host_CN': '德国', 'Winner': 'Italy', 'Winner_CN': '意大利',
         'RunnerUp': 'France', 'RunnerUp_CN': '法国', 'Third': 'Germany', 'Third_CN': '德国',
         'Fourth': 'Portugal', 'Fourth_CN': '葡萄牙', 'Teams': 32, 'Matches': 64, 'Goals': 147},

        {'Year': 2010, 'Host': 'South Africa', 'Host_CN': '南非', 'Winner': 'Spain', 'Winner_CN': '西班牙',
         'RunnerUp': 'Netherlands', 'RunnerUp_CN': '荷兰', 'Third': 'Germany', 'Third_CN': '德国',
         'Fourth': 'Uruguay', 'Fourth_CN': '乌拉圭', 'Teams': 32, 'Matches': 64, 'Goals': 145},

        {'Year': 2014, 'Host': 'Brazil', 'Host_CN': '巴西', 'Winner': 'Germany', 'Winner_CN': '德国',
         'RunnerUp': 'Argentina', 'RunnerUp_CN': '阿根廷', 'Third': 'Netherlands', 'Third_CN': '荷兰',
         'Fourth': 'Brazil', 'Fourth_CN': '巴西', 'Teams': 32, 'Matches': 64, 'Goals': 171},

        {'Year': 2018, 'Host': 'Russia', 'Host_CN': '俄罗斯', 'Winner': 'France', 'Winner_CN': '法国',
         'RunnerUp': 'Croatia', 'RunnerUp_CN': '克罗地亚', 'Third': 'Belgium', 'Third_CN': '比利时',
         'Fourth': 'England', 'Fourth_CN': '英格兰', 'Teams': 32, 'Matches': 64, 'Goals': 169},

        {'Year': 2022, 'Host': 'Qatar', 'Host_CN': '卡塔尔', 'Winner': 'Argentina', 'Winner_CN': '阿根廷',
         'RunnerUp': 'France', 'RunnerUp_CN': '法国', 'Third': 'Croatia', 'Third_CN': '克罗地亚',
         'Fourth': 'Morocco', 'Fourth_CN': '摩洛哥', 'Teams': 32, 'Matches': 64, 'Goals': 172},
    ]

    # 保存历史统计
    df_history = pd.DataFrame(wc_history)
    history_file = os.path.join(DATA_DIR, 'world_cup_history_summary.csv')
    df_history.to_csv(history_file, index=False, encoding='utf-8-sig')
    print(f"  保存历史统计: {history_file}")

    return df_history

def main():
    print("=" * 60)
    print(f"世界杯历史数据采集 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 创建综合数据
    df_history = create_comprehensive_world_cup_csv()

    print("\n" + "=" * 60)
    print("数据采集完成!")
    print("=" * 60)

    # 显示统计
    print(f"\n世界杯历史统计:")
    print(f"  届数: {len(df_history)}")
    print(f"  年份范围: {df_history['Year'].min()} - {df_history['Year'].max()}")
    print(f"  总比赛数: {df_history['Matches'].sum()}")
    print(f"  总进球数: {df_history['Goals'].sum()}")

    # 显示冠军统计
    print(f"\n冠军统计:")
    winner_counts = df_history['Winner_CN'].value_counts()
    for winner, count in winner_counts.items():
        print(f"  {winner}: {count}次")

if __name__ == '__main__':
    main()
