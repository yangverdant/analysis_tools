"""
使用OpenLigaDB API获取实时足球赛果
免费API，支持德甲、英超等联赛
"""
import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

DATA_DIR = 'd:/football_tools/data'
NO_PROXY = {'http': None, 'https': None}

# OpenLigaDB联赛映射
OPENLIGADB_LEAGUES = {
    'bl1': {'name': '德甲', 'file': 'germany/bundesliga_2025-2026.csv'},
    'bl2': {'name': '德乙', 'file': 'germany/bundesliga_2_2025-2026.csv'},
    'pl': {'name': '英超', 'file': 'england/premier_league_2025-2026.csv'},
}


def get_openligadb_matches(league_code):
    """从OpenLigaDB获取比赛数据"""
    url = f"https://api.openligadb.de/getmatchdata/{league_code}"

    try:
        session = requests.Session()
        session.trust_env = False
        session.proxies = NO_PROXY

        response = session.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            matches = []

            for match in data:
                team1 = match.get('team1', {}).get('teamName', '')
                team2 = match.get('team2', {}).get('teamName', '')

                # 获取比分（取最终结果）
                match_results = match.get('matchResults', [])
                if match_results:
                    # 取最后一个结果（全场比分）
                    final_result = match_results[-1]
                    score1 = final_result.get('pointsTeam1')
                    score2 = final_result.get('pointsTeam2')

                    if score1 is not None and score2 is not None:
                        matches.append({
                            'home_team': team1,
                            'away_team': team2,
                            'home_goals': int(score1),
                            'away_goals': int(score2),
                            'date': match.get('matchDateTime', ''),
                        })

            return matches
    except Exception as e:
        print(f"    OpenLigaDB请求失败: {e}")

    return []


def normalize_team_name(name):
    """标准化球队名称"""
    name = name.strip()

    # 德甲球队名映射
    bundesliga_mappings = {
        'Bayer 04 Leverkusen': 'Bayer Leverkusen',
        'Borussia Dortmund': 'Borussia Dortmund',
        'Borussia Mönchengladbach': 'Borussia M\'gladbach',
        'Borussia M' + '\xf6' + 'nchengladbach': 'Borussia M\'gladbach',
        'SV Werder Bremen': 'Werder Bremen',
        '1. FC Union Berlin': 'Union Berlin',
        '1. FC Heidenheim 1846': 'Heidenheim',
        '1. FSV Mainz 05': 'Mainz',
        'FC Augsburg': 'Augsburg',
        'VfB Stuttgart': 'Stuttgart',
        'VfL Wolfsburg': 'Wolfsburg',
        'SC Freiburg': 'Freiburg',
        'Eintracht Frankfurt': 'Eintracht Frankfurt',
        'TSG Hoffenheim': 'Hoffenheim',
        'FC Bayern München': 'Bayern Munich',
        'RB Leipzig': 'RB Leipzig',
        'Hamburger SV': 'Hamburg',
        'FC St. Pauli': 'St. Pauli',
        'Holstein Kiel': 'Holstein Kiel',
        'VfL Bochum': 'Bochum',
    }

    return bundesliga_mappings.get(name, name)


def update_league_csv(league_code, config):
    """更新联赛CSV"""
    csv_path = os.path.join(DATA_DIR, '01_leagues', config['file'])

    if not os.path.exists(csv_path):
        print(f"  文件不存在: {csv_path}")
        return 0

    # 获取比赛数据
    print(f"  获取 {config['name']} 数据...")
    matches = get_openligadb_matches(league_code)

    if not matches:
        print(f"  未获取到数据")
        return 0

    print(f"  获取到 {len(matches)} 场比赛")

    # 读取现有数据
    df = pd.read_csv(csv_path, encoding='utf-8')
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    # 检查已存在的比赛
    existing = set()
    for _, row in df.iterrows():
        if pd.notna(row['Date']) and pd.notna(row['HomeTeam']):
            key = (str(row['HomeTeam']), str(row['AwayTeam']))
            existing.add(key)

    # 添加新比赛
    added = 0
    for m in matches:
        home = normalize_team_name(m['home_team'])
        away = normalize_team_name(m['away_team'])

        key = (home, away)

        if key not in existing:
            # 使用API返回的日期
            if m['date']:
                date_str = m['date'][:10]
            else:
                date_str = datetime.now().strftime('%Y-%m-%d')

            if m['home_goals'] > m['away_goals']:
                ftr = 'H'
            elif m['home_goals'] < m['away_goals']:
                ftr = 'A'
            else:
                ftr = 'D'

            new_row = {
                'Date': date_str,
                'HomeTeam': home,
                'AwayTeam': away,
                'FTHG': m['home_goals'],
                'FTAG': m['away_goals'],
                'FTR': ftr,
            }

            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            existing.add(key)
            added += 1
            print(f"    + {home} {m['home_goals']}-{m['away_goals']} {away}")

    if added > 0:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.sort_values('Date')
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        df.to_csv(csv_path, index=False, encoding='utf-8')
        print(f"  新增 {added} 条记录")

    return added


def main():
    print("=" * 60)
    print(f"OpenLigaDB实时赛果获取 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    total_added = 0

    for league_code, config in OPENLIGADB_LEAGUES.items():
        print(f"\n更新 {config['name']}...")
        added = update_league_csv(league_code, config)
        total_added += added

    print("\n" + "=" * 60)
    print(f"完成! 共新增 {total_added} 条记录")


if __name__ == '__main__':
    main()