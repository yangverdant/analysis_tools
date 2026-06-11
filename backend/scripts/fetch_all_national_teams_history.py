"""
批量获取所有FIFA国家队的完整比赛历史
"""

import json
import sqlite3
import urllib.request
import time
from pathlib import Path

DATA_DIR = Path('d:/football_tools')
OUTPUT_DIR = DATA_DIR / 'national_teams_history'
OUTPUT_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / 'data' / 'football_v2.db'

API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
BASE_URL = 'https://apiv3.apifootball.com'

# 年份范围
YEARS = ['2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011', '2010']


def fetch_team_matches(team_id, team_name):
    """获取球队的所有比赛"""
    all_matches = []

    for year in YEARS:
        url = f"{BASE_URL}/?action=get_events&APIkey={API_KEY}&team_id={team_id}&from={year}-01-01&to={year}-12-31"

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=60) as response:
                data = json.loads(response.read().decode('utf-8'))

                if isinstance(data, list):
                    all_matches.extend(data)

        except:
            pass

        time.sleep(0.2)

    # 去重
    seen = set()
    unique = []
    for m in all_matches:
        mid = m.get('match_id')
        if mid and mid not in seen:
            seen.add(mid)
            unique.append(m)

    return unique


def main():
    print("=" * 70)
    print("批量获取FIFA国家队比赛历史")
    print("=" * 70)

    # 读取国家队列表
    with open(DATA_DIR / 'fifa_national_teams.json', 'r', encoding='utf-8') as f:
        teams = json.load(f)

    # 只处理有ID的球队
    teams_with_id = [t for t in teams if t['id']]
    print(f"共 {len(teams_with_id)} 支国家队需要获取数据")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    total_matches = 0
    processed = 0

    for team in teams_with_id:
        team_id = team['id']
        team_name = team['name_en']
        team_cn = team.get('name_cn', '')

        processed += 1
        if processed % 10 == 0:
            print(f"\n进度: {processed}/{len(teams_with_id)}, 已获取: {total_matches} 场")

        # 获取比赛
        matches = fetch_team_matches(team_id, team_name)

        if matches:
            # 保存JSON
            filename = f"{team_id}_{team_name.replace(' ', '_')}.json"
            filepath = OUTPUT_DIR / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(matches, f, ensure_ascii=False, indent=2)

            total_matches += len(matches)
            print(f"  {team_cn or team_name}: {len(matches)} 场")

        time.sleep(0.3)

    conn.close()

    print(f"\n{'=' * 70}")
    print(f"完成! 总计获取 {total_matches} 场比赛")
    print(f"数据保存在: {OUTPUT_DIR}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()