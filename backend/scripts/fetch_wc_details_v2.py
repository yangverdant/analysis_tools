"""
获取世界杯比赛的详细数据：阵容、统计
使用PowerShell的Invoke-WebRequest避免编码问题
"""

import json
import subprocess
from pathlib import Path
import time

DATA_DIR = Path('d:/football_tools')
OUTPUT_DIR = DATA_DIR / 'world_cup_details'
OUTPUT_DIR.mkdir(exist_ok=True)

API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
BASE_URL = 'https://apiv3.apifootball.com'


def get_match_ids():
    """获取所有世界杯比赛的match_id"""
    match_ids = []
    for filename in ['wc_2022.json', 'wc_2018.json', 'wc_2014.json']:
        filepath = DATA_DIR / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for m in data:
                        mid = m.get('match_id')
                        if mid:
                            match_ids.append((mid, m.get('match_date', ''), filename))
    return match_ids


def fetch_with_curl(url, output_file):
    """使用curl获取数据"""
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', output_file, url],
            capture_output=True,
            timeout=30
        )
        return result.returncode == 0
    except:
        return False


def fetch_match_details():
    """获取比赛详情"""
    print("=" * 60)
    print("获取世界杯比赛详细数据")
    print("=" * 60)

    match_ids = get_match_ids()
    print(f"共 {len(match_ids)} 场比赛需要获取")

    # 分批获取，每批10场
    batch_size = 10
    details = []
    lineups = []
    statistics = []

    for i, (mid, date, source) in enumerate(match_ids):
        print(f"获取第 {i+1}/{len(match_ids)} 场: match_id={mid}")

        # 获取详情
        detail_url = f"{BASE_URL}/?action=get_events&APIkey={API_KEY}&match_id={mid}"
        detail_file = OUTPUT_DIR / f'detail_{mid}.json'

        if fetch_with_curl(detail_url, str(detail_file)):
            try:
                with open(detail_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        details.append(data[0])
                        print(f"  [OK] detail")
            except:
                print(f"  [FAIL] detail parse")

        # 获取阵容
        lineup_url = f"{BASE_URL}/?action=get_lineups&APIkey={API_KEY}&match_id={mid}"
        lineup_file = OUTPUT_DIR / f'lineup_{mid}.json'

        if fetch_with_curl(lineup_url, str(lineup_file)):
            try:
                with open(lineup_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and str(mid) in data:
                        lineups.append({'match_id': mid, 'data': data[str(mid)]})
                        print(f"  [OK] lineup")
            except:
                print(f"  [FAIL] lineup parse")

        # 获取统计
        stats_url = f"{BASE_URL}/?action=get_statistics&APIkey={API_KEY}&match_id={mid}"
        stats_file = OUTPUT_DIR / f'stats_{mid}.json'

        if fetch_with_curl(stats_url, str(stats_file)):
            try:
                with open(stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and str(mid) in data:
                        statistics.append({'match_id': mid, 'data': data[str(mid)]})
                        print(f"  [OK] statistics")
            except:
                print(f"  [FAIL] statistics parse")

        # 每10场保存一次
        if (i + 1) % batch_size == 0:
            save_data(details, lineups, statistics)
            print(f"\n已保存 {len(details)} 场详情数据\n")

        # 避免请求过快
        time.sleep(0.5)

    # 最终保存
    save_data(details, lineups, statistics)

    print(f"\n{'=' * 60}")
    print(f"完成!")
    print(f"  比赛详情: {len(details)}")
    print(f"  阵容数据: {len(lineups)}")
    print(f"  统计数据: {len(statistics)}")
    print(f"{'=' * 60}")


def save_data(details, lineups, statistics):
    """保存数据到JSON文件"""
    with open(OUTPUT_DIR / 'match_details.json', 'w', encoding='utf-8') as f:
        json.dump(details, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_DIR / 'match_lineups.json', 'w', encoding='utf-8') as f:
        json.dump(lineups, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_DIR / 'match_statistics.json', 'w', encoding='utf-8') as f:
        json.dump(statistics, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    fetch_match_details()