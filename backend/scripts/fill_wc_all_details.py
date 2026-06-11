"""
补充历史世界杯比赛的详细数据
"""

import json
import sqlite3
import urllib.request
import time
from pathlib import Path

DB_PATH = Path('d:/football_tools/data/football_v2.db')
DATA_DIR = Path('d:/football_tools')

API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
BASE_URL = 'https://apiv3.apifootball.com'


def fetch_all_details():
    """获取所有世界杯比赛的详细数据"""
    print("=" * 60)
    print("补充历史世界杯详细数据")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    # 获取缺失统计数据的比赛
    wc_leagues = [40, 7514, 7541]

    # 从JSON文件获取match_id
    files_seasons = [
        ('wc_2014.json', '2014'),
        ('wc_2018.json', '2018'),
        ('wc_2022.json', '2022'),
        ('wwc_2023_v2.json', '2023'),
    ]

    all_match_ids = []
    for filename, season in files_seasons:
        filepath = DATA_DIR / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for m in data:
                        mid = m.get('match_id')
                        if mid:
                            all_match_ids.append((str(mid), season))

    print(f"共 {len(all_match_ids)} 场比赛")

    stats_updated = 0
    details_updated = 0

    for i, (mid, season) in enumerate(all_match_ids):
        if (i + 1) % 20 == 0:
            print(f"进度: {i+1}/{len(all_match_ids)}, 统计更新:{stats_updated}, 详情更新:{details_updated}")

        # 检查是否已有统计数据
        cursor.execute('''
            SELECT match_id FROM matches
            WHERE (match_id = ? OR match_id = ?)
            AND home_shots IS NOT NULL
        ''', (f'wc_{mid}', mid))
        if cursor.fetchone():
            continue  # 已有统计数据，跳过

        # 获取统计
        url = f"{BASE_URL}/?action=get_statistics&APIkey={API_KEY}&match_id={mid}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                if isinstance(data, dict) and str(mid) in data:
                    stats_data = data[str(mid)]
                    stats = stats_data.get('statistics', [])
                    stat_map = {}
                    for s in stats:
                        stat_type = s.get('type', '')
                        home_val = s.get('home', '')
                        away_val = s.get('away', '')
                        stat_map[stat_type] = (home_val, away_val)

                    if not stat_map:
                        continue

                    def to_int(val):
                        try:
                            return int(val) if val else None
                        except:
                            return None

                    home_shots = stat_map.get('Shots Total', ('', ''))[0]
                    away_shots = stat_map.get('Shots Total', ('', ''))[1]

                    if not home_shots:
                        continue

                    home_shots_on = stat_map.get('Shots On Goal', ('', ''))[0]
                    away_shots_on = stat_map.get('Shots On Goal', ('', ''))[1]
                    home_corners = stat_map.get('Corners', ('', ''))[0]
                    away_corners = stat_map.get('Corners', ('', ''))[1]
                    home_fouls = stat_map.get('Fouls', ('', ''))[0]
                    away_fouls = stat_map.get('Fouls', ('', ''))[1]

                    possession = stat_map.get('Ball Possession', ('', ''))
                    home_possession = possession[0].replace('%', '') if possession[0] else ''
                    away_possession = possession[1].replace('%', '') if possession[1] else ''

                    home_yellow = stat_map.get('Yellow Cards', ('', ''))[0]
                    away_yellow = stat_map.get('Yellow Cards', ('', ''))[1]
                    home_red = stat_map.get('Red Cards', ('', ''))[0]
                    away_red = stat_map.get('Red Cards', ('', ''))[1]

                    cursor.execute('''
                        UPDATE matches SET
                            home_shots = ?,
                            away_shots = ?,
                            home_shots_on = ?,
                            away_shots_on = ?,
                            home_corners = ?,
                            away_corners = ?,
                            home_fouls = ?,
                            away_fouls = ?,
                            home_possession = ?,
                            away_possession = ?,
                            home_yellow = ?,
                            away_yellow = ?,
                            home_red = ?,
                            away_red = ?
                        WHERE match_id = ? OR match_id = ?
                    ''', (to_int(home_shots), to_int(away_shots),
                          to_int(home_shots_on), to_int(away_shots_on),
                          to_int(home_corners), to_int(away_corners),
                          to_int(home_fouls), to_int(away_fouls),
                          to_int(home_possession), to_int(away_possession),
                          to_int(home_yellow), to_int(away_yellow),
                          to_int(home_red), to_int(away_red),
                          f'wc_{mid}', mid))
                    if cursor.rowcount > 0:
                        stats_updated += 1
                        conn.commit()
        except Exception as e:
            pass

        time.sleep(0.2)

        # 获取详情
        cursor.execute('''
            SELECT match_id FROM matches
            WHERE (match_id = ? OR match_id = ?)
            AND venue IS NOT NULL AND venue != ''
        ''', (f'wc_{mid}', mid))
        if cursor.fetchone():
            continue  # 已有球场信息，跳过

        url = f"{BASE_URL}/?action=get_events&APIkey={API_KEY}&match_id={mid}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                if isinstance(data, list) and len(data) > 0:
                    m = data[0]
                    stadium = m.get('match_stadium', '')
                    referee = m.get('match_referee', '')
                    match_time = m.get('match_time', '')
                    home_goals_ht = m.get('match_hometeam_halftime_score')
                    away_goals_ht = m.get('match_awayteam_halftime_score')

                    city = ''
                    if stadium and '(' in stadium:
                        city = stadium.split('(')[-1].rstrip(')')

                    if stadium or referee:
                        cursor.execute('''
                            UPDATE matches SET
                                venue = COALESCE(?, venue),
                                venue_city = COALESCE(?, venue_city),
                                referee = COALESCE(?, referee),
                                match_time = COALESCE(?, match_time),
                                home_goals_ht = COALESCE(?, home_goals_ht),
                                away_goals_ht = COALESCE(?, away_goals_ht)
                            WHERE match_id = ? OR match_id = ?
                        ''', (stadium, city, referee, match_time,
                              home_goals_ht, away_goals_ht,
                              f'wc_{mid}', mid))
                        if cursor.rowcount > 0:
                            details_updated += 1
                            conn.commit()
        except:
            pass

        time.sleep(0.2)

    conn.close()

    print(f"\n完成! 统计更新:{stats_updated}, 详情更新:{details_updated}")


if __name__ == '__main__':
    fetch_all_details()