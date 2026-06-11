"""
统一数据同步工具
同步new_data目录下的所有数据
包括：比赛数据、球员数据、球队数据
"""
import os
import requests
import pandas as pd
from io import StringIO
from datetime import datetime
import time
from pathlib import Path

# 数据目录
NEW_DATA_DIR = Path('d:/football_tools/new_data')
MATCHES_DIR = NEW_DATA_DIR / 'matches'
PLAYERS_DIR = NEW_DATA_DIR / 'players'
TEAMS_DIR = NEW_DATA_DIR / 'teams'

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
    })
    return session

# ==================== 数据源配置 ====================

# football-data.co.uk 联赛代码映射
FOOTBALL_DATA_LEAGUES = {
    # 英格兰
    'E0': {'name': 'premier_league', 'name_cn': '英超', 'dir': 'clubs/leagues/premier_league'},
    'E1': {'name': 'championship', 'name_cn': '英冠', 'dir': 'clubs/leagues/championship'},
    'E2': {'name': 'league_one', 'name_cn': '英甲', 'dir': 'clubs/leagues/league_one'},
    'E3': {'name': 'league_two', 'name_cn': '英乙', 'dir': 'clubs/leagues/league_two'},
    # 苏格兰
    'SC0': {'name': 'scotland_premier', 'name_cn': '苏超', 'dir': 'clubs/leagues/scotland_premier'},
    # 德国
    'D1': {'name': 'bundesliga', 'name_cn': '德甲', 'dir': 'clubs/leagues/bundesliga'},
    'D2': {'name': 'bundesliga_2', 'name_cn': '德乙', 'dir': 'clubs/leagues/bundesliga_2'},
    # 西班牙
    'SP1': {'name': 'la_liga', 'name_cn': '西甲', 'dir': 'clubs/leagues/la_liga'},
    'SP2': {'name': 'segunda_division', 'name_cn': '西乙', 'dir': 'clubs/leagues/segunda_division'},
    # 意大利
    'I1': {'name': 'serie_a', 'name_cn': '意甲', 'dir': 'clubs/leagues/serie_a'},
    'I2': {'name': 'serie_b', 'name_cn': '意乙', 'dir': 'clubs/leagues/serie_b'},
    # 法国
    'F1': {'name': 'ligue_1', 'name_cn': '法甲', 'dir': 'clubs/leagues/ligue_1'},
    'F2': {'name': 'ligue_2', 'name_cn': '法乙', 'dir': 'clubs/leagues/ligue_2'},
    # 荷兰
    'N1': {'name': 'eredivisie', 'name_cn': '荷甲', 'dir': 'clubs/leagues/eredivisie'},
    # 比利时
    'B1': {'name': 'jupiler_league', 'name_cn': '比甲', 'dir': 'clubs/leagues/jupiler_league'},
    # 葡萄牙
    'P1': {'name': 'primeira_liga', 'name_cn': '葡超', 'dir': 'clubs/leagues/primeira_liga'},
    # 土耳其
    'T1': {'name': 'super_lig', 'name_cn': '土超', 'dir': 'clubs/leagues/super_lig'},
    # 希腊
    'G1': {'name': 'superleague', 'name_cn': '希腊超', 'dir': 'clubs/leagues/superleague'},
}

# FBref 国家队赛事配置
FBREF_TOURNAMENTS = {
    'world_cup': {
        'name': 'World Cup',
        'name_cn': '世界杯',
        'comp_id': '106',
        'dir': 'international/world_cup'
    },
    'euro': {
        'name': 'European Championship',
        'name_cn': '欧洲杯',
        'comp_id': '102',
        'dir': 'international/euro'
    },
    'copa_america': {
        'name': 'Copa America',
        'name_cn': '美洲杯',
        'comp_id': '685',
        'dir': 'international/copa_america'
    },
    'africa_cup': {
        'name': 'Africa Cup of Nations',
        'name_cn': '非洲杯',
        'comp_id': '686',
        'dir': 'international/africa_cup'
    },
    'asian_cup': {
        'name': 'Asian Cup',
        'name_cn': '亚洲杯',
        'comp_id': '682',
        'dir': 'international/asian_cup'
    },
}

# ==================== 数据源接口 ====================

class FootballDataAPI:
    """football-data.co.uk 数据源"""

    BASE_URL = "https://www.football-data.co.uk/mmz4281"

    def __init__(self):
        self.session = get_session()

    def get_season_code(self):
        """获取当前赛季代码"""
        now = datetime.now()
        year = now.year if now.month >= 8 else now.year - 1
        return f"{str(year)[2:]}{str(year+1)[2:]}"

    def fetch_league(self, league_code, season=None):
        """获取联赛数据"""
        if season is None:
            season = self.get_season_code()

        url = f"{self.BASE_URL}/{season}/{league_code}.csv"

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                df = pd.read_csv(StringIO(response.text), encoding='utf-8', on_bad_lines='skip')
                return df
        except Exception as e:
            print(f"  请求失败: {e}")

        return None

    def fetch_historical(self, league_code, seasons):
        """获取历史数据"""
        all_data = []
        for season in seasons:
            df = self.fetch_league(league_code, season)
            if df is not None and not df.empty:
                # 添加赛季标识
                year = int(f"20{season[:2]}")
                df['season'] = f"{year}-{year+1}"
                all_data.append(df)
                print(f"    {season}: {len(df)} 场比赛")
            time.sleep(0.5)
        return all_data


class FBrefAPI:
    """FBref 数据源"""

    BASE_URL = "https://fbref.com/en/comps"

    def __init__(self):
        self.session = get_session()

    def fetch_tournament_history(self, comp_id):
        """获取赛事历史页面"""
        url = f"{self.BASE_URL}/{comp_id}/history/"
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"  请求失败: {e}")
        return None


class TransfermarktAPI:
    """Transfermarkt 数据源（球员身价）"""

    BASE_URL = "https://www.transfermarkt.com"

    def __init__(self):
        self.session = get_session()

    def search_player(self, player_name):
        """搜索球员"""
        # Transfermarkt需要登录或有反爬措施
        # 这里只返回空，实际使用时需要处理
        return None


# ==================== 同步函数 ====================

def sync_league_matches(league_code, config, season=None):
    """同步联赛比赛数据"""
    print(f"\n同步 {config['name_cn']} ({config['name']})...")

    api = FootballDataAPI()
    df = api.fetch_league(league_code, season)

    if df is None or df.empty:
        print(f"  无数据")
        return 0

    # 标准化字段
    df = standardize_league_fields(df)

    # 添加赛季
    if 'season' not in df.columns:
        now = datetime.now()
        year = now.year if now.month >= 8 else now.year - 1
        df['season'] = f"{year}-{year+1}"

    # 保存
    output_dir = MATCHES_DIR / config['dir']
    output_dir.mkdir(parents=True, exist_ok=True)

    season_str = df['season'].iloc[0] if 'season' in df.columns else '2025-26'
    output_file = output_dir / f"{config['name']}_{season_str}.csv"

    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"  保存: {output_file} ({len(df)} 场比赛)")

    return len(df)


def sync_all_leagues(season=None):
    """同步所有联赛"""
    print("=" * 60)
    print(f"同步联赛数据 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    total = 0
    for league_code, config in FOOTBALL_DATA_LEAGUES.items():
        count = sync_league_matches(league_code, config, season)
        total += count
        time.sleep(1)

    print(f"\n总计: {total} 场比赛")
    return total


def standardize_league_fields(df):
    """标准化联赛字段"""
    field_mapping = {
        'Date': 'match_date',
        'Time': 'match_time',
        'HomeTeam': 'home_team',
        'AwayTeam': 'away_team',
        'FTHG': 'home_goals',
        'FTAG': 'away_goals',
        'FTR': 'result',
        'HTHG': 'home_goals_ht',
        'HTAG': 'away_goals_ht',
        'HTR': 'result_ht',
        'HS': 'home_shots',
        'AS': 'away_shots',
        'HST': 'home_shots_target',
        'AST': 'away_shots_target',
        'HF': 'home_fouls',
        'AF': 'away_fouls',
        'HC': 'home_corners',
        'AC': 'away_corners',
        'HY': 'home_yellow',
        'AY': 'away_yellow',
        'HR': 'home_red',
        'AR': 'away_red',
        'B365H': 'home_odds',
        'B365D': 'draw_odds',
        'B365A': 'away_odds',
    }

    # 只重命名存在的列
    existing_cols = {k: v for k, v in field_mapping.items() if k in df.columns}
    df = df.rename(columns=existing_cols)

    # 处理日期
    if 'match_date' in df.columns:
        df['match_date'] = pd.to_datetime(df['match_date'], format='%d/%m/%Y', errors='coerce')

    return df


def sync_player_market_values():
    """同步球员身价数据"""
    print("\n" + "=" * 60)
    print("同步球员身价数据")
    print("=" * 60)

    # 读取在役球员
    active_file = PLAYERS_DIR / 'active' / 'profiles.csv'
    if not active_file.exists():
        print("  未找到在役球员文件")
        return

    df = pd.read_csv(active_file)
    print(f"  在役球员: {len(df)} 人")

    # TODO: 从Transfermarkt获取身价
    # 需要处理反爬措施
    print("  提示: Transfermarkt需要特殊处理，暂跳过")


def sync_team_names():
    """同步球队名称"""
    print("\n" + "=" * 60)
    print("同步球队名称数据")
    print("=" * 60)

    teams_dir = TEAMS_DIR / 'clubs'
    if not teams_dir.exists():
        print("  球队目录不存在")
        return

    # 统计现有球队文件
    csv_files = list(teams_dir.glob('*.csv'))
    print(f"  现有球队文件: {len(csv_files)} 个")

    # 检查字段是否标准
    for f in csv_files[:5]:
        df = pd.read_csv(f)
        cols = list(df.columns)
        is_standard = cols == ['season', 'league_en', 'league_cn', 'team_en', 'team_cn']
        status = "✓" if is_standard else "✗"
        print(f"  {status} {f.name}: {cols}")


def show_data_summary():
    """显示数据统计"""
    print("\n" + "=" * 60)
    print("数据统计")
    print("=" * 60)

    # 比赛数据
    print("\n比赛数据:")
    leagues_dir = MATCHES_DIR / 'clubs' / 'leagues'
    if leagues_dir.exists():
        for league_dir in sorted(leagues_dir.iterdir()):
            if league_dir.is_dir():
                csv_files = list(league_dir.glob('*.csv'))
                print(f"  {league_dir.name}: {len(csv_files)} 个文件")

    # 国家队比赛
    print("\n国家队比赛:")
    intl_dir = MATCHES_DIR / 'international'
    if intl_dir.exists():
        for comp_dir in sorted(intl_dir.iterdir()):
            if comp_dir.is_dir():
                csv_files = list(comp_dir.glob('*.csv'))
                print(f"  {comp_dir.name}: {len(csv_files)} 个文件")

    # 球员数据
    print("\n球员数据:")
    active_file = PLAYERS_DIR / 'active' / 'profiles.csv'
    retired_file = PLAYERS_DIR / 'retired' / 'profiles.csv'

    if active_file.exists():
        df = pd.read_csv(active_file)
        print(f"  在役球员: {len(df)} 人")
    if retired_file.exists():
        df = pd.read_csv(retired_file)
        print(f"  退役球员: {len(df)} 人")

    # 球队数据
    print("\n球队数据:")
    clubs_dir = TEAMS_DIR / 'clubs'
    intl_teams_dir = TEAMS_DIR / 'international'
    if clubs_dir.exists():
        csv_files = list(clubs_dir.glob('*.csv'))
        print(f"  俱乐部: {len(csv_files)} 个文件")
    if intl_teams_dir.exists():
        csv_files = list(intl_teams_dir.glob('*.csv'))
        print(f"  国家队: {len(csv_files)} 个文件")


# ==================== 主函数 ====================

def main():
    """主函数"""
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == 'leagues':
            season = sys.argv[2] if len(sys.argv) > 2 else None
            sync_all_leagues(season)
        elif command == 'players':
            sync_player_market_values()
        elif command == 'teams':
            sync_team_names()
        elif command == 'summary':
            show_data_summary()
        elif command == 'all':
            sync_all_leagues()
            sync_player_market_values()
            sync_team_names()
            show_data_summary()
        else:
            print(f"未知命令: {command}")
    else:
        # 默认显示统计
        show_data_summary()
        print("\n可用命令:")
        print("  python sync_new_data.py leagues [season]  - 同步联赛数据")
        print("  python sync_new_data.py players           - 同步球员身价")
        print("  python sync_new_data.py teams             - 同步球队名称")
        print("  python sync_new_data.py summary           - 显示数据统计")
        print("  python sync_new_data.py all               - 同步所有数据")


if __name__ == '__main__':
    main()
