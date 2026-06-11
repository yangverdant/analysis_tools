"""补充国家队比赛的详细信息（时间、场馆、裁判等）"""
import json
import sqlite3
import urllib.request
import time
from pathlib import Path

DB_PATH = Path('d:/football_tools/data/football_v2.db')
API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
BASE_URL = 'https://apiv3.apifootball.com'

def fetch_match_details(match_id):
    """获取比赛详细信息"""
    url = f"{BASE_URL}/?action=get_events&APIkey={API_KEY}&match_id={match_id}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            if isinstance(data, list) and len(data) > 0:
                return data[0]
    except:
        pass
    return None

def main():
    print("=" * 70)
    print("补充国家队比赛详细信息")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    # 查找缺失比赛时间的2020年后比赛
    cursor.execute("""
        SELECT match_id, match_date, home_team_id, away_team_id
        FROM matches
        WHERE match_id LIKE 'intl_%'
        AND match_date >= '2020-01-01'
        AND (match_time = '' OR match_time IS NULL)
        ORDER BY match_date DESC
    """)
    matches = cursor.fetchall()

    print(f"找到 {len(matches)} 场 2020年后缺失时间的比赛")

    # 获取原始match_id
    cursor.execute("SELECT match_id FROM matches WHERE match_id LIKE 'intl_%' LIMIT 1")
    sample = cursor.fetchone()
    if sample:
        print(f"示例 match_id 格式: {sample[0]}")

    updated = 0
    failed = 0

    for i, (match_id, match_date, home_id, away_id) in enumerate(matches):
        # 提取原始API match_id
        original_id = match_id.replace('intl_', '')

        if i % 100 == 0:
            print(f"进度: {i}/{len(matches)}, 已更新: {updated}")

        # 获取比赛详情
        details = fetch_match_details(original_id)
        if details:
            match_time = details.get('match_time', '')
            stadium = details.get('match_stadium', '')
            referee = details.get('match_referee', '')
            city = ''

            if stadium and '(' in stadium:
                city = stadium.split('(')[-1].rstrip(')')

            # 更新数据库
            try:
                cursor.execute('''
                    UPDATE matches
                    SET match_time = ?, venue = ?, venue_city = ?, referee = ?
                    WHERE match_id = ?
                ''', (match_time, stadium, city, referee, match_id))
                updated += 1
            except:
                failed += 1

            if updated % 50 == 0:
                conn.commit()

        time.sleep(0.15)

    conn.commit()
    conn.close()

    print(f"\n完成! 更新: {updated}, 失败: {failed}")

if __name__ == '__main__':
    main()
