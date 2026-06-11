"""
批量获取世界杯比赛详细数据 - 简化版
"""

import json
import os
from pathlib import Path
import time
import urllib.request
import urllib.error

DATA_DIR = Path('d:/football_tools')
OUTPUT_DIR = DATA_DIR / 'world_cup_details'
OUTPUT_DIR.mkdir(exist_ok=True)

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
    except Exception as e:
        return False


def main():
    print("=" * 60)
    print("批量获取世界杯比赛详细数据")
    print("=" * 60)

    match_ids = get_match_ids()
    print(f"共 {len(match_ids)} 场比赛")

    # 检查已获取的
    existing = set()
    for f in os.listdir(OUTPUT_DIR):
        if f.startswith('detail_') and f.endswith('.json'):
            mid = f.replace('detail_', '').replace('.json', '')
            existing.add(mid)

    remaining = [m for m in match_ids if m not in existing]
    print(f"已获取: {len(existing)} 场")
    print(f"待获取: {len(remaining)} 场")

    success = 0
    failed = 0

    for i, mid in enumerate(remaining):
        if (i + 1) % 10 == 0:
            print(f"进度: {i+1}/{len(remaining)}")

        # 获取详情
        url = f"{BASE_URL}/?action=get_events&APIkey={API_KEY}&match_id={mid}"
        output = OUTPUT_DIR / f'detail_{mid}.json'
        if fetch_url(url, output):
            success += 1
        else:
            failed += 1

        time.sleep(0.3)

    print(f"\n完成! 成功: {success}, 失败: {failed}")


if __name__ == '__main__':
    main()