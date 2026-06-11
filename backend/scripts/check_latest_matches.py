"""检查并补充最新的国家队比赛（2025年）"""
import json
import sqlite3
import urllib.request
import time
from pathlib import Path
from datetime import datetime

DB_PATH = Path('d:/football_tools/data/football_v2.db')
API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
BASE_URL = 'https://apiv3.apifootball.com'

# 主要国家队（FIFA排名前50）
TOP_TEAMS = [
    ('Argentina', 66), ('Brazil', 75), ('France', 22), ('England', 10),
    ('Spain', 9), ('Germany', 34), ('Netherlands', 82), ('Portugal', 95),
    ('Belgium', 7), ('Italy', 54), ('Croatia', 50), ('Switzerland', 166),
    ('Denmark', 59), ('Poland', 96), ('Ukraine', 179), ('Serbia', 159),
    ('Austria', 5), ('Czech Republic', 52), ('Turkey', 174), ('Hungary', 48),
    ('Uruguay', 115), ('Colombia', 94), ('Chile', 91), ('Peru', 110),
    ('Ecuador', 101), ('Senegal', 149), ('Morocco', 79), ('Egypt', 60),
    ('Nigeria', 86), ('Cameroon', 27), ('USA', 180), ('Mexico', 77),
    ('Canada', 28), ('Japan', 61), ('South Korea', 156), ('Iran', 53),
    ('Australia', 6), ('Saudi Arabia', 138), ('Qatar', 102), ('China', 31),
]

def fetch_recent_matches(team_id, from_date, to_date):
    """获取最近的比赛"""
    url = f"{BASE_URL}/?action=get_events&APIkey={API_KEY}&team_id={team_id}&from={from_date}&to={to_date}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            if isinstance(data, list):
                return data
    except:
        pass
    return []

def main():
    print("=" * 70)
    print("检查并补充最新国家队比赛")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    # 获取数据库中最新的比赛日期
    cursor.execute("""
        SELECT MAX(match_date) FROM matches
        WHERE match_id LIKE 'intl_%'
    """)
    latest_date = cursor.fetchone()[0]
    print(f"数据库中最新比赛日期: {latest_date}")

    # 当前日期
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"当前日期: {today}")

    # 检查是否有缺失的近期比赛
    if latest_date and latest_date < today:
        print(f"\n需要补充 {latest_date} 到 {today} 的比赛")

        total_new = 0

        for team_name, team_id in TOP_TEAMS:
            matches = fetch_recent_matches(team_id, latest_date, today)

            if matches:
                print(f"  {team_name}: {len(matches)} 场新比赛")
                total_new += len(matches)

                for m in matches:
                    try:
                        match_id = f"intl_{m.get('match_id', '')}"
                        # ... 导入逻辑（简化）
                    except:
                        pass

                time.sleep(0.3)

        print(f"\n总计发现 {total_new} 场新比赛")
    else:
        print("\n数据已是最新，无需补充")

    # 检查2025年比赛分布
    cursor.execute("""
        SELECT l.name_cn, COUNT(*) as matches
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.match_id LIKE 'intl_%'
        AND m.match_date LIKE '2025%'
        GROUP BY l.name_cn
        ORDER BY matches DESC
    """)
    leagues_2025 = cursor.fetchall()

    print("\n2025年比赛分布:")
    for league, count in leagues_2025[:10]:
        print(f"  {league}: {count} 场")

    conn.close()

if __name__ == '__main__':
    main()