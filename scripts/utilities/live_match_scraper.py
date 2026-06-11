"""
足球赛果自动更新系统
支持多种数据源爬取最新比赛结果
"""
import os
import json
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import sqlite3

# 配置
DATA_DIR = 'd:/football_tools/data'
DB_PATH = 'd:/football_tools/data/football_unified.db'
CONFIG_FILE = 'd:/football_tools/config/scraper_config.json'

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# 禁用代理
NO_PROXY = {
    'http': None,
    'https': None,
}

# 数据源配置
DATA_SOURCES = {
    'football_data_co_uk': {
        'name': 'Football-Data.co.uk',
        'base_url': 'https://www.football-data.co.uk',
        'leagues': {
            'E0': {'name': '英超', 'league_id': 1, 'country': 'England'},
            'E1': {'name': '英冠', 'league_id': 2, 'country': 'England'},
            'D1': {'name': '德甲', 'league_id': 8, 'country': 'Germany'},
            'SP1': {'name': '西甲', 'league_id': 5, 'country': 'Spain'},
            'I1': {'name': '意甲', 'league_id': 6, 'country': 'Italy'},
            'F1': {'name': '法甲', 'league_id': 7, 'country': 'France'},
        }
    },
    'flashscore': {
        'name': 'FlashScore',
        'base_url': 'https://www.flashscore.com',
        'enabled': True
    }
}


class MatchScraper:
    """比赛数据爬取器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.trust_env = False  # 禁用系统代理
        self.session.proxies = NO_PROXY

    def get_latest_results_football_data(self, league_code='E0'):
        """
        从football-data.co.uk获取最新赛果
        这是获取历史数据最可靠的数据源
        """
        url = f"https://www.football-data.co.uk/mmz4281/{self._get_season_path()}/{league_code}.csv"
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                from io import StringIO
                df = pd.read_csv(StringIO(response.text), encoding='utf-8')
                return df
            else:
                print(f"获取数据失败: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"请求失败: {e}")
            return None

    def _get_season_path(self):
        """获取当前赛季路径格式，如 2425 表示2024-2025赛季"""
        now = datetime.now()
        year = now.year
        month = now.month
        # 足球赛季从8月开始，如果当前月份小于8月，则使用上一年的赛季
        if month < 8:
            start_year = year - 1
        else:
            start_year = year
        return f"{str(start_year)[2:]}{str(start_year + 1)[2:]}"

    def get_today_matches_flashscore(self):
        """
        从FlashScore获取今日比赛
        需要解析动态加载的页面
        """
        url = "https://www.flashscore.com/"
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                # FlashScore使用动态加载，这里返回页面内容供解析
                return response.text
        except Exception as e:
            print(f"FlashScore请求失败: {e}")
        return None

    def get_matches_from_api_football(self, date=None, api_key=None):
        """
        使用API-Football (rapidapi) 获取比赛数据
        免费套餐每天100次请求
        """
        if not api_key:
            print("需要API Key")
            return None

        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        headers = {
            'X-RapidAPI-Key': api_key,
            'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'
        }
        params = {'date': date}

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"API-Football请求失败: {e}")
        return None


class DataUpdater:
    """数据更新器 - 将爬取的数据更新到CSV和数据库"""

    def __init__(self):
        self.scraper = MatchScraper()

    def update_league_csv(self, league_code, league_id, country):
        """更新联赛CSV文件"""
        print(f"\n更新 {league_code} 数据...")

        # 获取最新数据
        df = self.scraper.get_latest_results_football_data(league_code)
        if df is None or df.empty:
            print(f"  未获取到数据")
            return 0

        # 标准化列名
        column_mapping = {
            'Date': 'Date',
            'Time': 'Time',
            'HomeTeam': 'HomeTeam',
            'AwayTeam': 'AwayTeam',
            'FTHG': 'FTHG',
            'FTAG': 'FTAG',
            'FTR': 'FTR',
            'HTHG': 'HTHG',
            'HTAG': 'HTAG',
            'HTR': 'HTR',
            'Referee': 'Referee',
            'HS': 'HS',
            'AS': 'AS',
            'HST': 'HST',
            'AST': 'AST',
            'HF': 'HF',
            'AF': 'AF',
            'HC': 'HC',
            'AC': 'AC',
            'HY': 'HY',
            'AY': 'AY',
            'HR': 'HR',
            'AR': 'AR',
            'B365H': 'B365H',
            'B365D': 'B365D',
            'B365A': 'B365A',
            'BWH': 'BWH',
            'BWD': 'BWD',
            'BWA': 'BWA',
            'IWH': 'IWH',
            'IWD': 'IWD',
            'IWA': 'IWA',
            'WHH': 'WHH',
            'WHD': 'WHD',
            'WHA': 'WHA',
        }

        # 只保留需要的列
        existing_cols = [c for c in column_mapping.keys() if c in df.columns]
        df = df[existing_cols]

        # 添加Div和Season
        df['Div'] = league_code
        season = self._get_current_season()
        df['Season'] = season

        # 处理日期格式
        df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
        df = df.dropna(subset=['Date'])
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')

        # 保存到CSV
        output_dir = os.path.join(DATA_DIR, '01_leagues', country.lower().replace(' ', '_'))
        os.makedirs(output_dir, exist_ok=True)

        # 根据联赛ID确定文件名
        league_names = {
            1: 'premier_league',
            2: 'championship',
            5: 'la_liga',
            6: 'serie_a',
            7: 'ligue_1',
            8: 'bundesliga',
        }
        league_name = league_names.get(league_id, f'league_{league_id}')
        output_file = os.path.join(output_dir, f'{league_name}_{season}.csv')

        # 如果文件存在，合并数据
        if os.path.exists(output_file):
            existing_df = pd.read_csv(output_file)
            # 合并并去重
            df = pd.concat([existing_df, df], ignore_index=True)
            df = df.drop_duplicates(subset=['Date', 'HomeTeam', 'AwayTeam'], keep='last')

        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"  已保存 {len(df)} 条记录到 {output_file}")

        return len(df)

    def _get_current_season(self):
        """获取当前赛季"""
        now = datetime.now()
        year = now.year
        month = now.month
        if month < 8:
            return f"{year-1}-{year}"
        return f"{year}-{year+1}"

    def update_all_leagues(self):
        """更新所有联赛数据"""
        total = 0
        for code, info in DATA_SOURCES['football_data_co_uk']['leagues'].items():
            count = self.update_league_csv(code, info['league_id'], info['country'])
            total += count
            time.sleep(1)  # 避免请求过快

        print(f"\n总计更新 {total} 条记录")
        return total

    def import_to_database(self):
        """将更新后的CSV导入数据库"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 这里需要根据实际的数据库结构来实现
        print("导入数据库功能待实现...")

        conn.close()


class LiveMatchFetcher:
    """实时比赛数据获取器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_live_scores(self):
        """获取实时比分"""
        # 使用开放的API或爬取网站
        sources = [
            self._fetch_from_score365(),
            # 可以添加更多数据源
        ]

        for source in sources:
            if source:
                return source

        return None

    def _fetch_from_score365(self):
        """从score365获取实时比分"""
        try:
            # 这里使用一个示例URL，实际需要找到可用的数据源
            url = "https://www.score365.com/api/livescores"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None

    def get_today_fixtures(self):
        """获取今日赛程"""
        today = datetime.now().strftime('%Y-%m-%d')

        # 尝试多个数据源
        results = []

        # 数据源1: football-data (历史数据，非实时)
        # 数据源2: 其他API

        return results


def main():
    """主函数"""
    print("=" * 60)
    print("足球赛果自动更新系统")
    print("=" * 60)
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    updater = DataUpdater()

    # 更新所有联赛数据
    updater.update_all_leagues()

    print("\n更新完成!")


if __name__ == '__main__':
    main()
