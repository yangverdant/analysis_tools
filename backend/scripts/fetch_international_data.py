"""
批量获取所有国际赛事的比赛数据和球队数据
"""

import json
import sqlite3
import urllib.request
import time
from pathlib import Path
from datetime import datetime

DATA_DIR = Path('d:/football_tools')
OUTPUT_DIR = DATA_DIR / 'international_data'
OUTPUT_DIR.mkdir(exist_ok=True)

API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
BASE_URL = 'https://apiv3.apifootball.com'

# 重要国际赛事列表（按优先级排序）
PRIORITY_LEAGUES = [
    # 世界杯系列
    {'id': 28, 'name': 'World Cup', 'cn': '世界杯'},
    {'id': 20, 'name': "FIFA Women's World Cup", 'cn': '女足世界杯'},
    {'id': 21, 'name': 'CAF World Cup Qualifiers', 'cn': '非洲世界杯预选赛'},
    {'id': 22, 'name': 'AFC World Cup Qualifiers', 'cn': '亚洲世界杯预选赛'},
    {'id': 23, 'name': 'Concacaf World Cup Qualifiers', 'cn': '中北美世界杯预选赛'},
    {'id': 24, 'name': 'UEFA World Cup Qualifiers', 'cn': '欧洲世界杯预选赛'},
    {'id': 27, 'name': 'CONMEBOL World Cup Qualifiers', 'cn': '南美世界杯预选赛'},
    {'id': 26, 'name': 'OFC World Cup Qualifiers', 'cn': '大洋洲世界杯预选赛'},

    # 欧洲杯
    {'id': 1, 'name': 'UEFA European Championship', 'cn': '欧洲杯'},
    {'id': 354, 'name': 'UEFA Euro Qualifiers', 'cn': '欧洲杯预选赛'},
    {'id': 633, 'name': 'UEFA Nations League', 'cn': '欧国联'},

    # 美洲赛事
    {'id': 17, 'name': 'Copa America', 'cn': '美洲杯'},
    {'id': 15, 'name': 'Gold Cup', 'cn': '金杯赛'},
    {'id': 664, 'name': 'Concacaf Nations League', 'cn': '中北美国家联赛'},

    # 亚洲赛事
    {'id': 347, 'name': 'AFC Asian Cup', 'cn': '亚洲杯'},
    {'id': 418, 'name': 'Asian Cup Qualification', 'cn': '亚洲杯预选赛'},

    # 非洲赛事
    {'id': 29, 'name': 'Africa Cup of Nations', 'cn': '非洲杯'},
    {'id': 7098, 'name': 'AFCON Qualification', 'cn': '非洲杯预选赛'},

    # 奥运会
    {'id': 500, 'name': 'Olympics Men', 'cn': '奥运会男足'},
    {'id': 522, 'name': 'Olympics Women', 'cn': '奥运会女足'},

    # 友谊赛
    {'id': 356, 'name': 'Friendlies', 'cn': '国际友谊赛'},

    # 青年赛事
    {'id': 415, 'name': 'FIFA U17 World Cup', 'cn': 'U17世界杯'},
    {'id': 425, 'name': 'FIFA U20 World Cup', 'cn': 'U20世界杯'},
]

# 最近几年的赛季
SEASONS = ['2024', '2023', '2022', '2021', '2020', '2019', '2018']


def fetch_url(url):
    """获取URL数据"""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return None


def fetch_international_data():
    """获取所有国际赛事数据"""
    print("=" * 70)
    print("批量获取国际赛事数据")
    print("=" * 70)

    total_matches = 0
    total_teams = 0
    results = []

    for league in PRIORITY_LEAGUES:
        league_id = league['id']
        league_name = league['name']
        league_cn = league['cn']

        print(f"\n{league_cn} ({league_name}) - League ID: {league_id}")
        print("-" * 50)

        league_matches = 0
        league_teams = 0

        for season in SEASONS:
            # 获取比赛数据
            url = f"{BASE_URL}/?action=get_events&APIkey={API_KEY}&league_id={league_id}&from={season}-01-01&to={season}-12-31"
            data = fetch_url(url)

            if isinstance(data, list) and len(data) > 0:
                # 保存数据
                filename = f"{league_id}_{season}.json"
                filepath = OUTPUT_DIR / filename
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                league_matches += len(data)
                print(f"  {season}: {len(data)} 场比赛")
            else:
                print(f"  {season}: 无数据")

            time.sleep(0.5)

            # 获取球队数据
            url = f"{BASE_URL}/?action=get_teams&APIkey={API_KEY}&league_id={league_id}&season={season}"
            data = fetch_url(url)

            if isinstance(data, list) and len(data) > 0:
                filename = f"teams_{league_id}_{season}.json"
                filepath = OUTPUT_DIR / filename
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                league_teams += len(data)

            time.sleep(0.5)

        total_matches += league_matches
        total_teams += league_teams
        results.append({
            'league': league_cn,
            'matches': league_matches,
            'teams': league_teams
        })

        print(f"  小计: {league_matches} 场比赛, {league_teams} 支球队")

    # 汇总
    print("\n" + "=" * 70)
    print("数据获取汇总")
    print("=" * 70)

    for r in results:
        print(f"  {r['league']}: {r['matches']} 场比赛, {r['teams']} 支球队")

    print(f"\n总计: {total_matches} 场比赛, {total_teams} 支球队")
    print(f"数据保存在: {OUTPUT_DIR}")


if __name__ == '__main__':
    fetch_international_data()