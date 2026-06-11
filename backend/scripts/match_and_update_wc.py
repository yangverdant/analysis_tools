"""
通过日期和球队名匹配并更新世界杯数据
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path('d:/football_tools/data/football_v2.db')
DETAIL_DIR = Path('d:/football_tools/world_cup_details')


def normalize_team_name(name):
    """标准化球队名"""
    if not name:
        return ''
    name = name.lower().strip()
    # 常见名称映射
    mappings = {
        'argentina': 'argentina',
        'france': 'france',
        'brazil': 'brazil',
        'germany': 'germany',
        'spain': 'spain',
        'england': 'england',
        'netherlands': 'netherlands',
        'portugal': 'portugal',
        'belgium': 'belgium',
        'croatia': 'croatia',
        'uruguay': 'uruguay',
        'switzerland': 'switzerland',
        'usa': 'united states',
        'united states': 'united states',
        'mexico': 'mexico',
        'japan': 'japan',
        'senegal': 'senegal',
        'morocco': 'morocco',
        'australia': 'australia',
        'poland': 'poland',
        'serbia': 'serbia',
        'south korea': 'south korea',
        'korea republic': 'south korea',
        'tunisia': 'tunisia',
        'canada': 'canada',
        'cameroon': 'cameroon',
        'ecuador': 'ecuador',
        'saudi arabia': 'saudi arabia',
        'iran': 'iran',
        'wales': 'wales',
        'qatar': 'qatar',
        'ghana': 'ghana',
        'denmark': 'denmark',
    }
    return mappings.get(name, name)


def match_and_update():
    """匹配并更新数据"""
    print("=" * 60)
    print("通过日期和球队匹配更新世界杯数据")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    stats_updated = 0
    details_updated = 0
    not_matched = 0

    # 获取所有世界杯比赛
    cursor.execute('''
        SELECT m.match_id, m.match_date, t1.name_en as home, t2.name_en as away
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.team_id
        JOIN teams t2 ON m.away_team_id = t2.team_id
        WHERE m.league_id IN (40, 7514, 7541)
    ''')
    matches = {f"{r['match_date']}_{normalize_team_name(r['home'])}_{normalize_team_name(r['away'])}": r['match_id'] for r in cursor.fetchall()}

    print(f"数据库中世界杯比赛: {len(matches)}")

    # 处理统计文件
    print("\n处理统计数据...")
    for f in DETAIL_DIR.glob('stats_*.json'):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                if isinstance(data, dict):
                    for api_mid, stats_data in data.items():
                        stats = stats_data.get('statistics', [])
                        if not stats:
                            continue

                        # 获取对应的详情文件找日期和球队
                        detail_file = DETAIL_DIR / f'detail_{api_mid}.json'
                        if not detail_file.exists():
                            continue

                        with open(detail_file, 'r', encoding='utf-8') as dfp:
                            detail_data = json.load(dfp)
                            if not (isinstance(detail_data, list) and len(detail_data) > 0):
                                continue
                            m = detail_data[0]
                            match_date = m.get('match_date', '')
                            home_team = normalize_team_name(m.get('match_hometeam_name', ''))
                            away_team = normalize_team_name(m.get('match_awayteam_name', ''))

                        # 构建匹配key
                        match_key = f"{match_date}_{home_team}_{away_team}"
                        if match_key not in matches:
                            not_matched += 1
                            continue

                        db_match_id = matches[match_key]

                        # 检查是否已有统计数据
                        cursor.execute('SELECT home_shots FROM matches WHERE match_id = ?', (db_match_id,))
                        row = cursor.fetchone()
                        if row and row[0] is not None:
                            continue

                        # 提取统计
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

                        possession = stat_map.get('Ball Possession', ('', ''))
                        home_poss = possession[0].replace('%', '') if possession[0] else ''
                        away_poss = possession[1].replace('%', '') if possession[1] else ''

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
                            WHERE match_id = ?
                        ''', (
                            to_int(stat_map.get('Shots Total', ('', ''))[0]),
                            to_int(stat_map.get('Shots Total', ('', ''))[1]),
                            to_int(stat_map.get('Shots On Goal', ('', ''))[0]),
                            to_int(stat_map.get('Shots On Goal', ('', ''))[1]),
                            to_int(stat_map.get('Corners', ('', ''))[0]),
                            to_int(stat_map.get('Corners', ('', ''))[1]),
                            to_int(stat_map.get('Fouls', ('', ''))[0]),
                            to_int(stat_map.get('Fouls', ('', ''))[1]),
                            to_int(home_poss),
                            to_int(away_poss),
                            to_int(stat_map.get('Yellow Cards', ('', ''))[0]),
                            to_int(stat_map.get('Yellow Cards', ('', ''))[1]),
                            to_int(stat_map.get('Red Cards', ('', ''))[0]),
                            to_int(stat_map.get('Red Cards', ('', ''))[1]),
                            db_match_id
                        ))
                        if cursor.rowcount > 0:
                            stats_updated += 1
        except Exception as e:
            pass

    conn.commit()

    # 处理详情文件
    print("处理详情数据...")
    for f in DETAIL_DIR.glob('detail_*.json'):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                if isinstance(data, list) and len(data) > 0:
                    m = data[0]
                    match_date = m.get('match_date', '')
                    home_team = normalize_team_name(m.get('match_hometeam_name', ''))
                    away_team = normalize_team_name(m.get('match_awayteam_name', ''))

                    match_key = f"{match_date}_{home_team}_{away_team}"
                    if match_key not in matches:
                        continue

                    db_match_id = matches[match_key]

                    stadium = m.get('match_stadium', '')
                    referee = m.get('match_referee', '')
                    match_time = m.get('match_time', '')
                    home_goals_ht = m.get('match_hometeam_halftime_score')
                    away_goals_ht = m.get('match_awayteam_halftime_score')

                    city = ''
                    if stadium and '(' in stadium:
                        city = stadium.split('(')[-1].rstrip(')')

                    cursor.execute('''
                        UPDATE matches SET
                            venue = COALESCE(?, venue),
                            venue_city = COALESCE(?, venue_city),
                            referee = COALESCE(?, referee),
                            match_time = COALESCE(?, match_time),
                            home_goals_ht = COALESCE(?, home_goals_ht),
                            away_goals_ht = COALESCE(?, away_goals_ht)
                        WHERE match_id = ?
                    ''', (stadium, city, referee, match_time,
                          home_goals_ht, away_goals_ht, db_match_id))
                    if cursor.rowcount > 0:
                        details_updated += 1
        except:
            pass

    conn.commit()
    conn.close()

    print(f"\n完成!")
    print(f"  统计更新: {stats_updated}")
    print(f"  详情更新: {details_updated}")
    print(f"  未匹配: {not_matched}")


if __name__ == '__main__':
    match_and_update()