"""
补充世界杯比赛缺失数据 - 批量获取统计和详情
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


def get_missing_match_ids():
    """获取缺失统计数据的比赛ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    wc_leagues = [40, 7514, 7525, 7541]

    # 获取比赛ID列表
    cursor.execute(f'''
        SELECT match_id FROM matches
        WHERE league_id IN ({','.join(map(str, wc_leagues))})
        AND match_id LIKE 'wc_%'
    ''')
    match_ids = [r[0].replace('wc_', '') for r in cursor.fetchall()]
    conn.close()
    return match_ids


def fetch_and_update():
    """获取并更新数据"""
    print("=" * 60)
    print("补充世界杯缺失数据")
    print("=" * 60)

    match_ids = get_missing_match_ids()
    print(f"共 {len(match_ids)} 场世界杯比赛")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    updated_details = 0
    updated_stats = 0

    for i, mid in enumerate(match_ids):
        if (i + 1) % 20 == 0:
            print(f"进度: {i+1}/{len(match_ids)}")

        # 获取详情
        url = f"{BASE_URL}/?action=get_events&APIkey={API_KEY}&match_id={mid}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                if isinstance(data, list) and len(data) > 0:
                    m = data[0]
                    match_time = m.get('match_time', '')
                    stadium = m.get('match_stadium', '')
                    city = ''
                    if stadium and '(' in stadium:
                        city = stadium.split('(')[-1].rstrip(')')
                    referee = m.get('match_referee', '')
                    home_goals_ht = m.get('match_hometeam_halftime_score')
                    away_goals_ht = m.get('match_awayteam_halftime_score')

                    cursor.execute('''
                        UPDATE matches SET
                            match_time = COALESCE(?, match_time),
                            venue = COALESCE(?, venue),
                            venue_city = COALESCE(?, venue_city),
                            referee = COALESCE(?, referee),
                            home_goals_ht = COALESCE(?, home_goals_ht),
                            away_goals_ht = COALESCE(?, away_goals_ht)
                        WHERE match_id = ? OR match_id = ?
                    ''', (match_time, stadium, city, referee,
                          home_goals_ht, away_goals_ht,
                          f'wc_{mid}', mid))
                    if cursor.rowcount > 0:
                        updated_details += 1
        except:
            pass

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

                    def to_int(val):
                        try:
                            return int(val) if val else None
                        except:
                            return None

                    home_shots = stat_map.get('Shots Total', ('', ''))[0]
                    away_shots = stat_map.get('Shots Total', ('', ''))[1]
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
                            home_shots = COALESCE(?, home_shots),
                            away_shots = COALESCE(?, away_shots),
                            home_shots_on = COALESCE(?, home_shots_on),
                            away_shots_on = COALESCE(?, away_shots_on),
                            home_corners = COALESCE(?, home_corners),
                            away_corners = COALESCE(?, away_corners),
                            home_fouls = COALESCE(?, home_fouls),
                            away_fouls = COALESCE(?, away_fouls),
                            home_possession = COALESCE(?, home_possession),
                            away_possession = COALESCE(?, away_possession),
                            home_yellow = COALESCE(?, home_yellow),
                            away_yellow = COALESCE(?, away_yellow),
                            home_red = COALESCE(?, home_red),
                            away_red = COALESCE(?, away_red)
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
                        updated_stats += 1
        except:
            pass

        time.sleep(0.3)

    conn.commit()
    conn.close()

    print(f"\n更新完成:")
    print(f"  详情更新: {updated_details}")
    print(f"  统计更新: {updated_stats}")


if __name__ == '__main__':
    fetch_and_update()