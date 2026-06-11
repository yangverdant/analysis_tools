"""
批量更新所有联赛数据
从football-data.co.uk获取最新数据并更新CSV
"""
import os
import requests
import pandas as pd
from io import StringIO
from datetime import datetime
import time

DATA_DIR = 'd:/football_tools/data'
NO_PROXY = {'http': None, 'https': None}

# 所有联赛配置
ALL_LEAGUES = {
    # 英格兰
    'E0': {'name': '英超', 'file': 'england/premier_league_2025-2026.csv'},
    'E1': {'name': '英冠', 'file': 'england/championship_2025-2026.csv'},
    'E2': {'name': '英甲', 'file': 'england/league_one_2025-2026.csv'},
    'E3': {'name': '英乙', 'file': 'england/league_two_2025-2026.csv'},
    # 苏格兰
    'SC0': {'name': '苏超', 'file': 'scotland/scottish_premier_2025-2026.csv'},
    # 德国
    'D1': {'name': '德甲', 'file': 'germany/bundesliga_2025-2026.csv'},
    'D2': {'name': '德乙', 'file': 'germany/bundesliga_2_2025-2026.csv'},
    # 西班牙
    'SP1': {'name': '西甲', 'file': 'spain/la_liga_2025-2026.csv'},
    'SP2': {'name': '西乙', 'file': 'spain/la_liga_2_2025-2026.csv'},
    # 意大利
    'I1': {'name': '意甲', 'file': 'italy/serie_a_2025-2026.csv'},
    'I2': {'name': '意乙', 'file': 'italy/serie_b_2025-2026.csv'},
    # 法国
    'F1': {'name': '法甲', 'file': 'france/ligue_1_2025-2026.csv'},
    'F2': {'name': '法乙', 'file': 'france/ligue_2_2025-2026.csv'},
    # 荷兰
    'N1': {'name': '荷甲', 'file': 'netherlands/eredivisie_2025-2026.csv'},
    # 比利时
    'B1': {'name': '比甲', 'file': 'belgium/jupiler_league_2025-2026.csv'},
    # 葡萄牙
    'P1': {'name': '葡超', 'file': 'portugal/primeira_liga_2025-2026.csv'},
    # 土耳其
    'T1': {'name': '土超', 'file': 'turkey/super_lig_2025-2026.csv'},
    # 希腊
    'G1': {'name': '希腊超', 'file': 'greece/super_league_2025-2026.csv'},
}


def get_season_code():
    """获取当前赛季代码"""
    now = datetime.now()
    year = now.year if now.month >= 8 else now.year - 1
    return f"{str(year)[2:]}{str(year+1)[2:]}"


def fetch_league_data(league_code, season):
    """从football-data.co.uk获取联赛数据"""
    url = f"https://www.football-data.co.uk/mmz4281/{season}/{league_code}.csv"

    session = requests.Session()
    session.trust_env = False
    session.proxies = NO_PROXY

    try:
        response = session.get(url, timeout=30)
        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.text), encoding='utf-8', on_bad_lines='skip')
            return df
        elif response.status_code == 404:
            # 尝试上一赛季
            prev_season = f"{str(int(season[:2])-1)}{str(int(season[2:])-1)}"
            url = f"https://www.football-data.co.uk/mmz4281/{prev_season}/{league_code}.csv"
            response = session.get(url, timeout=30)
            if response.status_code == 200:
                df = pd.read_csv(StringIO(response.text), encoding='utf-8', on_bad_lines='skip')
                return df
    except Exception as e:
        print(f"    请求失败: {e}")

    return None


def update_league_csv(league_code, config, season):
    """更新联赛CSV文件"""
    csv_path = os.path.join(DATA_DIR, '01_leagues', config['file'])

    if not os.path.exists(csv_path):
        print(f"  文件不存在: {csv_path}")
        return 0

    # 获取新数据
    df_new = fetch_league_data(league_code, season)

    if df_new is None or df_new.empty:
        print(f"  获取数据失败")
        return 0

    # 处理日期
    df_new['Date'] = pd.to_datetime(df_new['Date'], format='%d/%m/%Y', errors='coerce')
    df_new = df_new.dropna(subset=['Date', 'HomeTeam', 'AwayTeam'])

    # 读取现有数据
    df_old = pd.read_csv(csv_path, encoding='utf-8')
    df_old['Date'] = pd.to_datetime(df_old['Date'], errors='coerce')

    old_latest = df_old['Date'].max().date()
    new_latest = df_new['Date'].max().date()

    # 格式化日期
    df_new['Date'] = df_new['Date'].dt.strftime('%Y-%m-%d')
    df_old['Date'] = df_old['Date'].dt.strftime('%Y-%m-%d')

    # 合并去重
    combined = pd.concat([df_old, df_new], ignore_index=True)
    combined = combined.drop_duplicates(subset=['Date', 'HomeTeam', 'AwayTeam'], keep='last')

    # 按日期排序
    combined['Date'] = pd.to_datetime(combined['Date'], errors='coerce')
    combined = combined.sort_values('Date')
    combined['Date'] = combined['Date'].dt.strftime('%Y-%m-%d')

    # 保存
    combined.to_csv(csv_path, index=False, encoding='utf-8')

    added = len(combined) - len(df_old)
    print(f"  最新: {new_latest} | 总记录: {len(combined)} | 新增: {added}")

    return added


def main():
    print("=" * 60)
    print(f"批量更新所有联赛数据 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    season = get_season_code()
    print(f"当前赛季: {season}")

    total_added = 0
    success = 0

    for league_code, config in ALL_LEAGUES.items():
        print(f"\n更新 {config['name']} ({league_code})...")
        added = update_league_csv(league_code, config, season)
        total_added += added
        if added >= 0:
            success += 1

        time.sleep(0.5)  # 避免请求过快

    print("\n" + "=" * 60)
    print(f"完成! 成功: {success}/{len(ALL_LEAGUES)} | 总新增: {total_added} 条")


if __name__ == '__main__':
    main()