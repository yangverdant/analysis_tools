"""
获取世界杯比赛的详细数据：阵容、统计、进球者
"""

import json
import sqlite3
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

DB_PATH = Path(__file__).parent.parent.parent / 'data' / 'football_v2.db'
DATA_DIR = Path('d:/football_tools')

API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
BASE_URL = 'https://apiv3.apifootball.com'


def get_match_ids():
    """获取所有世界杯比赛的match_id"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取世界杯相关的match_id (需要从原始API数据中提取)
    # 先从JSON文件获取
    match_ids = []

    for filename in ['wc_2022.json', 'wc_2018.json', 'wc_2014.json', 'wc_2026.json', 'wwc_2023_v2.json']:
        filepath = DATA_DIR / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for m in data:
                        mid = m.get('match_id')
                        if mid:
                            match_ids.append((mid, m.get('match_date', ''), filename))

    conn.close()
    return match_ids


def fetch_match_detail(match_id):
    """获取单场比赛的详细信息"""
    url = f"{BASE_URL}/?action=get_events&APIkey={API_KEY}&match_id={match_id}"
    result = subprocess.run(
        ['curl', '-s', url],
        capture_output=True,
        text=True,
        timeout=30
    )

    try:
        data = json.loads(result.stdout)
        if isinstance(data, list) and len(data) > 0:
            return data[0]
    except:
        pass
    return None


def fetch_lineups(match_id):
    """获取阵容"""
    url = f"{BASE_URL}/?action=get_lineups&APIkey={API_KEY}&match_id={match_id}"
    result = subprocess.run(
        ['curl', '-s', url],
        capture_output=True,
        text=True,
        timeout=30
    )

    try:
        data = json.loads(result.stdout)
        if isinstance(data, dict) and str(match_id) in data:
            return data[str(match_id)]
    except:
        pass
    return None


def fetch_statistics(match_id):
    """获取统计数据"""
    url = f"{BASE_URL}/?action=get_statistics&APIkey={API_KEY}&match_id={match_id}"
    result = subprocess.run(
        ['curl', '-s', url],
        capture_output=True,
        text=True,
        timeout=30
    )

    try:
        data = json.loads(result.stdout)
        if isinstance(data, dict) and str(match_id) in data:
            return data[str(match_id)]
    except:
        pass
    return None


def save_match_details():
    """保存比赛详细信息"""
    print("=" * 60)
    print("获取世界杯比赛详细数据")
    print("=" * 60)

    match_ids = get_match_ids()
    print(f"共 {len(match_ids)} 场比赛")

    # 创建输出目录
    output_dir = DATA_DIR / 'world_cup_details'
    output_dir.mkdir(exist_ok=True)

    details = []
    lineups_data = []
    stats_data = []
    goalscorers = []

    success = 0
    failed = 0

    for i, (mid, date, source) in enumerate(match_ids):
        if (i + 1) % 10 == 0:
            print(f"进度: {i+1}/{len(match_ids)}")

        # 获取比赛详情
        detail = fetch_match_detail(mid)
        if detail:
            details.append(detail)

            # 提取进球者
            gs = detail.get('goalscorer', [])
            if gs:
                for g in gs:
                    g['match_id'] = mid
                    g['match_date'] = date
                goalscorers.extend(gs)

        # 获取阵容
        lineup = fetch_lineups(mid)
        if lineup:
            lineups_data.append({
                'match_id': mid,
                'match_date': date,
                'lineup': lineup
            })

        # 获取统计
        stats = fetch_statistics(mid)
        if stats:
            stats_data.append({
                'match_id': mid,
                'match_date': date,
                'statistics': stats
            })

        if detail or lineup or stats:
            success += 1
        else:
            failed += 1

        # 避免请求过快
        time.sleep(0.3)

    # 保存数据
    print("\n保存数据...")

    with open(output_dir / 'match_details.json', 'w', encoding='utf-8') as f:
        json.dump(details, f, ensure_ascii=False, indent=2)
    print(f"比赛详情: {len(details)} 场")

    with open(output_dir / 'lineups.json', 'w', encoding='utf-8') as f:
        json.dump(lineups_data, f, ensure_ascii=False, indent=2)
    print(f"阵容数据: {len(lineups_data)} 场")

    with open(output_dir / 'statistics.json', 'w', encoding='utf-8') as f:
        json.dump(stats_data, f, ensure_ascii=False, indent=2)
    print(f"统计数据: {len(stats_data)} 场")

    with open(output_dir / 'goalscorers.json', 'w', encoding='utf-8') as f:
        json.dump(goalscorers, f, ensure_ascii=False, indent=2)
    print(f"进球记录: {len(goalscorers)} 条")

    print(f"\n成功: {success}, 失败: {failed}")
    print(f"数据保存在: {output_dir}")


if __name__ == '__main__':
    save_match_details()
