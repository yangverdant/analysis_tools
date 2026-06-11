"""
批量获取世界杯比赛阵容和统计数据
"""

import json
import os
from pathlib import Path
import time
import urllib.request

DATA_DIR = Path('d:/football_tools')
OUTPUT_DIR = DATA_DIR / 'world_cup_details'

API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
BASE_URL = 'https://apiv3.apifootball.com'


def get_match_ids():
    """获取所有世界杯比赛的match_id"""
    match_ids = set()
    for filename in ['wc_2022.json', 'wc_2018.json', 'wc_2014.json']:
        filepath = DATA_DIR / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for m in data:
                        mid = m.get('match_id')
                        if mid:
                            match_ids.add(str(mid))
    return list(match_ids)


def fetch_url(url, output_file):
    """使用urllib获取数据"""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
            with open(output_file, 'wb') as f:
                f.write(data)
            return True
    except:
        return False


def fetch_lineups_and_stats():
    """获取阵容和统计数据"""
    print("=" * 60)
    print("批量获取阵容和统计数据")
    print("=" * 60)

    match_ids = get_match_ids()
    print(f"共 {len(match_ids)} 场比赛")

    # 检查已获取的
    existing_lineups = set()
    existing_stats = set()
    for f in os.listdir(OUTPUT_DIR):
        if f.startswith('lineup_') and f.endswith('.json'):
            mid = f.replace('lineup_', '').replace('.json', '')
            existing_lineups.add(mid)
        elif f.startswith('stats_') and f.endswith('.json'):
            mid = f.replace('stats_', '').replace('.json', '')
            existing_stats.add(mid)

    # 获取阵容
    remaining_lineups = [m for m in match_ids if m not in existing_lineups]
    print(f"\n阵容 - 已获取: {len(existing_lineups)}, 待获取: {len(remaining_lineups)}")

    success = 0
    for i, mid in enumerate(remaining_lineups):
        if (i + 1) % 20 == 0:
            print(f"阵容进度: {i+1}/{len(remaining_lineups)}")

        url = f"{BASE_URL}/?action=get_lineups&APIkey={API_KEY}&match_id={mid}"
        output = OUTPUT_DIR / f'lineup_{mid}.json'
        if fetch_url(url, output):
            success += 1
        time.sleep(0.2)

    print(f"阵容完成: 成功 {success}")

    # 获取统计
    remaining_stats = [m for m in match_ids if m not in existing_stats]
    print(f"\n统计 - 已获取: {len(existing_stats)}, 待获取: {len(remaining_stats)}")

    success = 0
    for i, mid in enumerate(remaining_stats):
        if (i + 1) % 20 == 0:
            print(f"统计进度: {i+1}/{len(remaining_stats)}")

        url = f"{BASE_URL}/?action=get_statistics&APIkey={API_KEY}&match_id={mid}"
        output = OUTPUT_DIR / f'stats_{mid}.json'
        if fetch_url(url, output):
            success += 1
        time.sleep(0.2)

    print(f"统计完成: 成功 {success}")

    # 最终统计
    total_details = len([f for f in os.listdir(OUTPUT_DIR) if f.startswith('detail_')])
    total_lineups = len([f for f in os.listdir(OUTPUT_DIR) if f.startswith('lineup_')])
    total_stats = len([f for f in os.listdir(OUTPUT_DIR) if f.startswith('stats_')])

    print(f"\n{'=' * 60}")
    print(f"最终数据:")
    print(f"  比赛详情: {total_details}")
    print(f"  阵容数据: {total_lineups}")
    print(f"  统计数据: {total_stats}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    fetch_lineups_and_stats()