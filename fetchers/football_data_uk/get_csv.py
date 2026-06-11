"""
football-data.co.uk - 下载并解析CSV数据

功能:
1. 下载当前赛季CSV
2. 下载历史赛季CSV (批量)
3. 解析CSV为标准格式 (pandas DataFrame)
4. 保存CSV到本地

数据包含:
- 比赛结果 (日期、队名、比分、半场比分)
- 赔率 (B365/WH/IW/PIN等公司的欧赔、亚盘、大小球)
- 比赛统计 (射门、角球、犯规、红黄牌)

使用示例:
    from fetchers.football_data_uk.get_csv import fetch_league, fetch_historical

    # 获取英超当前赛季数据
    df = fetch_league("英超")
    print(df[["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "B365H", "B365D", "B365A"]].head())

    # 获取英超2020-2025历史数据
    dfs = fetch_historical("英超", from_season="2021", to_season="2025")

    # 获取所有联赛当前赛季
    from fetchers.football_data_uk.get_csv import fetch_all_leagues
    results = fetch_all_leagues()
"""

import os
import time
from io import StringIO
from datetime import datetime
from typing import Dict, List, Optional

import requests
import pandas as pd

from fetchers.football_data_uk.config import (
    BASE_URL, LEAGUES, URL_CSV, REQUEST_TIMEOUT, CURRENT_SEASON
)

# 绕过代理
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'


def _create_session() -> requests.Session:
    """创建HTTP会话"""
    session = requests.Session()
    session.verify = False
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    return session


def get_season_code(year: int = None) -> str:
    """获取赛季代码

    Args:
        year: 赛季开始年份, 如2024表示2024-25赛季. None=当前赛季

    Returns:
        "2425" (表示2024-25赛季)
    """
    if year is None:
        now = datetime.now()
        year = now.year if now.month >= 8 else now.year - 1
    return f"{str(year)[2:]}{str(year+1)[2:]}"


def season_code_to_years(code: str) -> tuple:
    """赛季代码转年份

    Args:
        code: "2425"

    Returns:
        (2024, 2025)
    """
    start = int(f"20{code[:2]}")
    end = int(f"20{code[2:]}")
    return (start, end)


def season_code_to_string(code: str) -> str:
    """赛季代码转字符串

    Args:
        code: "2425"

    Returns:
        "2024-25"
    """
    start, end = season_code_to_years(code)
    return f"{start}-{str(end)[2:]}"


# ==================== 核心接口 ====================

def fetch_league(league_name: str, season: str = None,
                 session: requests.Session = None) -> Optional[pd.DataFrame]:
    """下载联赛CSV数据

    Args:
        league_name: 联赛中文名, 如 "英超", "西甲"
        season: 赛季代码, 如 "2425". None=当前赛季
        session: 复用会话

    Returns:
        pandas DataFrame 或 None (下载失败)
    """
    league_config = LEAGUES.get(league_name)
    if not league_config:
        print(f"[错误] 联赛 '{league_name}' 未在配置中找到")
        print(f"  可用联赛: {', '.join(LEAGUES.keys())}")
        return None

    league_code = league_config["league_code"]
    if season is None:
        season = get_season_code()

    url = URL_CSV.format(season=season, league_code=league_code)
    own_session = session is None
    if own_session:
        session = _create_session()

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.text), encoding='utf-8', on_bad_lines='skip')
            # 添加元数据列
            df['LeagueCode'] = league_code
            df['LeagueName'] = league_name
            df['Season'] = season_code_to_string(season)
            df['SeasonCode'] = season
            print(f"[ok] {league_name} {season_code_to_string(season)}: {len(df)} 场比赛")
            return df
        elif response.status_code == 404:
            print(f"[404] {league_name} {season_code_to_string(season)}: 该赛季无数据")
            return None
        else:
            print(f"[错误] {league_name}: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"[错误] {league_name}: {str(e)[:60]}")
        return None


def fetch_historical(league_name: str, from_season: str = "2000",
                     to_season: str = None,
                     session: requests.Session = None) -> List[pd.DataFrame]:
    """批量下载历史赛季数据

    Args:
        league_name: 联赛中文名
        from_season: 起始年份, 如 "2000" (表示2000-01赛季起)
        to_season: 截止年份, 如 "2025". None=当前赛季
        session: 复用会话

    Returns:
        List[DataFrame], 按赛季顺序排列
    """
    if to_season is None:
        to_season = str(datetime.now().year)

    start_year = int(from_season)
    end_year = int(to_season)

    own_session = session is None
    if own_session:
        session = _create_session()

    all_data = []
    for year in range(start_year, end_year + 1):
        season = get_season_code(year)
        df = fetch_league(league_name, season, session)
        if df is not None and not df.empty:
            all_data.append(df)
        time.sleep(0.5)  # 避免请求过快

    print(f"\n[结果] {league_name}: {len(all_data)} 个赛季, 共 {sum(len(d) for d in all_data)} 场比赛")
    return all_data


def fetch_all_leagues(season: str = None) -> Dict[str, pd.DataFrame]:
    """下载所有配置联赛的当前赛季数据

    Args:
        season: 赛季代码, None=当前赛季

    Returns:
        {联赛名: DataFrame, ...}
    """
    if season is None:
        season = get_season_code()

    session = _create_session()
    results = {}

    for league_name in LEAGUES:
        df = fetch_league(league_name, season, session)
        if df is not None and not df.empty:
            results[league_name] = df
        time.sleep(0.3)

    print(f"\n[结果] 获取 {len(results)}/{len(LEAGUES)} 个联赛数据")
    return results


def save_csv(df: pd.DataFrame, output_path: str) -> str:
    """保存DataFrame到CSV

    Args:
        df: 数据
        output_path: 输出路径

    Returns:
        保存的文件路径
    """
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"[保存] {len(df)} 行 -> {output_path}")
    return output_path


def get_available_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    """分析DataFrame中可用的列, 按类别分组

    Returns:
        {"比赛信息": [...], "赔率": [...], "统计": [...], ...}
    """
    categories = {
        "比赛信息": ["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
                    "HTHG", "HTAG", "HTR", "Referee", "LeagueCode", "LeagueName", "Season"],
        "赔率-欧赔": [c for c in df.columns if c.endswith(('H', 'D', 'A')) and
                     any(k in c for k in ['B365', 'BW', 'IW', 'PS', 'WH', 'VC', 'Max', 'Avg'])],
        "赔率-亚盘": [c for c in df.columns if 'AH' in c.upper()],
        "赔率-大小球": [c for c in df.columns if '>' in c or '<' in c],
        "比赛统计": ["HS", "AS", "HST", "AST", "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR"],
        "其他": [],
    }

    # 未分类的列
    classified = set()
    for cols in categories.values():
        classified.update(cols)
    categories["其他"] = [c for c in df.columns if c not in classified]

    return {k: v for k, v in categories.items() if v}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.football_data_uk.get_csv current 英超")
        print("  python -m fetchers.football_data_uk.get_csv current 英超 2425")
        print("  python -m fetchers.football_data_uk.get_csv history 英超 2020 2025")
        print("  python -m fetchers.football_data_uk.get_csv all")
        print("  python -m fetchers.football_data_uk.get_csv columns 英超")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "current":
        league = sys.argv[2] if len(sys.argv) > 2 else "英超"
        season = sys.argv[3] if len(sys.argv) > 3 else None
        df = fetch_league(league, season)
        if df is not None:
            print(f"\n列数: {len(df.columns)}")
            print(f"行数: {len(df)}")
            # 显示前5场比赛
            basic_cols = [c for c in ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"] if c in df.columns]
            print(df[basic_cols].head())

    elif cmd == "history":
        league = sys.argv[2] if len(sys.argv) > 2 else "英超"
        from_y = sys.argv[3] if len(sys.argv) > 3 else "2020"
        to_y = sys.argv[4] if len(sys.argv) > 4 else None
        dfs = fetch_historical(league, from_y, to_y)
        if dfs:
            combined = pd.concat(dfs, ignore_index=True)
            print(f"\n总计: {len(combined)} 场比赛, {len(dfs)} 个赛季")

    elif cmd == "all":
        results = fetch_all_leagues()
        for name, df in results.items():
            print(f"  {name}: {len(df)} 场")

    elif cmd == "columns":
        league = sys.argv[2] if len(sys.argv) > 2 else "英超"
        df = fetch_league(league)
        if df is not None:
            cats = get_available_columns(df)
            for cat, cols in cats.items():
                print(f"\n{cat}:")
                for c in cols:
                    print(f"  {c}")
