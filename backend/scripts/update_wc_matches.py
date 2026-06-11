"""
将世界杯详细数据补充到matches表
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path('d:/football_tools/data/football_v2.db')
DETAIL_DIR = Path('d:/football_tools/world_cup_details')


def update_matches():
    """更新matches表的详细数据"""
    print("=" * 60)
    print("补充世界杯比赛详细数据到matches表")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    updated = 0
    stats_updated = 0

    # 1. 从比赛详情更新基本信息
    print("\n1. 更新比赛基本信息...")
    for f in DETAIL_DIR.glob('detail_*.json'):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                if isinstance(data, list) and len(data) > 0:
                    m = data[0]
                    api_match_id = m.get('match_id')

                    # 构建match_id (wc_前缀)
                    match_id = f"wc_{api_match_id}"

                    # 提取数据
                    match_time = m.get('match_time', '')
                    stadium = m.get('match_stadium', '')
                    city = ''
                    if stadium and '(' in stadium:
                        city = stadium.split('(')[-1].rstrip(')')

                    referee = m.get('match_referee', '')
                    home_formation = m.get('match_hometeam_system', '')
                    away_formation = m.get('match_awayteam_system', '')

                    # 比分数据
                    home_goals = m.get('match_hometeam_score')
                    away_goals = m.get('match_awayteam_score')
                    home_goals_ht = m.get('match_hometeam_halftime_score')
                    away_goals_ht = m.get('match_awayteam_halftime_score')
                    home_goals_et = m.get('match_hometeam_extra_score')
                    away_goals_et = m.get('match_awayteam_extra_score')
                    home_penalties = m.get('match_hometeam_penalty_score')
                    away_penalties = m.get('match_awayteam_penalty_score')

                    # 确定round_stage/stage_type
                    round_name = m.get('match_round', '')
                    stage_name = m.get('stage_name', '')

                    # 更新matches表
                    cursor.execute('''
                        UPDATE matches SET
                            match_time = COALESCE(?, match_time),
                            venue = COALESCE(?, venue),
                            venue_city = COALESCE(?, venue_city),
                            referee = COALESCE(?, referee),
                            home_goals = COALESCE(?, home_goals),
                            away_goals = COALESCE(?, away_goals),
                            home_goals_ht = COALESCE(?, home_goals_ht),
                            away_goals_ht = COALESCE(?, away_goals_ht),
                            home_goals_et = COALESCE(?, home_goals_et),
                            away_goals_et = COALESCE(?, away_goals_et),
                            home_penalties = COALESCE(?, home_penalties),
                            away_penalties = COALESCE(?, away_penalties),
                            round_stage = COALESCE(?, round_stage),
                            stage_type = COALESCE(?, stage_type)
                        WHERE match_id = ? OR match_id = ?
                    ''', (match_time, stadium, city, referee,
                          home_goals, away_goals, home_goals_ht, away_goals_ht,
                          home_goals_et, away_goals_et, home_penalties, away_penalties,
                          round_name, stage_name,
                          match_id, api_match_id))

                    if cursor.rowcount > 0:
                        updated += 1
        except Exception as e:
            pass

    conn.commit()
    print(f"  更新了 {updated} 场比赛基本信息")

    # 2. 从统计数据更新比赛统计
    print("\n2. 更新比赛统计数据...")
    for f in DETAIL_DIR.glob('stats_*.json'):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                if isinstance(data, dict):
                    for api_match_id, stats_data in data.items():
                        match_id = f"wc_{api_match_id}"

                        # 全场统计
                        stats = stats_data.get('statistics', [])
                        stat_map = {}
                        for s in stats:
                            stat_type = s.get('type', '')
                            home_val = s.get('home', '')
                            away_val = s.get('away', '')
                            stat_map[stat_type] = (home_val, away_val)

                        # 映射统计字段
                        home_shots = stat_map.get('Shots Total', ('', ''))[0]
                        away_shots = stat_map.get('Shots Total', ('', ''))[1]
                        home_shots_on = stat_map.get('Shots On Goal', ('', ''))[0]
                        away_shots_on = stat_map.get('Shots On Goal', ('', ''))[1]
                        home_corners = stat_map.get('Corners', ('', ''))[0]
                        away_corners = stat_map.get('Corners', ('', ''))[1]
                        home_fouls = stat_map.get('Fouls', ('', ''))[0]
                        away_fouls = stat_map.get('Fouls', ('', ''))[1]

                        # 控球率
                        possession = stat_map.get('Ball Possession', ('', ''))
                        home_possession = possession[0].replace('%', '') if possession[0] else ''
                        away_possession = possession[1].replace('%', '') if possession[1] else ''

                        # 黄牌红牌
                        home_yellow = stat_map.get('Yellow Cards', ('', ''))[0]
                        away_yellow = stat_map.get('Yellow Cards', ('', ''))[1]
                        home_red = stat_map.get('Red Cards', ('', ''))[0]
                        away_red = stat_map.get('Red Cards', ('', ''))[1]

                        # 转换数值
                        def to_int(val):
                            try:
                                return int(val) if val else None
                            except:
                                return None

                        # 更新
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
                              match_id, api_match_id))

                        if cursor.rowcount > 0:
                            stats_updated += 1
        except Exception as e:
            pass

    conn.commit()
    print(f"  更新了 {stats_updated} 场比赛统计数据")

    # 3. 检查teams表的城市信息
    print("\n3. 更新球队城市信息...")
    teams_updated = 0

    # 从球队JSON文件更新
    team_files = {
        'wc_teams_2014.json': '2014',
        'wc_teams_2022.json': '2022',
        'wc_teams_2026.json': '2026',
        'wwc_teams_2023.json': '2023'
    }

    for filename in team_files.keys():
        filepath = Path('d:/football_tools') / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as fp:
                teams = json.load(fp)
                if isinstance(teams, list):
                    for team in teams:
                        team_name = team.get('team_name', '')
                        venue = team.get('venue', {})
                        if isinstance(venue, dict):
                            venue_city = venue.get('venue_city', '')
                            venue_name = venue.get('venue_name', '')
                            venue_capacity = venue.get('venue_capacity', '')

                            if venue_city or venue_name:
                                cursor.execute('''
                                    UPDATE teams SET
                                        city = COALESCE(?, city),
                                        stadium = COALESCE(?, stadium),
                                        stadium_capacity = COALESCE(?, stadium_capacity)
                                    WHERE name_en = ?
                                ''', (venue_city, venue_name, venue_capacity, team_name))
                                if cursor.rowcount > 0:
                                    teams_updated += 1

    conn.commit()
    print(f"  更新了 {teams_updated} 支球队信息")

    conn.close()

    print(f"\n{'=' * 60}")
    print("数据补充完成!")
    print(f"{'=' * 60}")


def verify_update():
    """验证更新结果"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n验证更新结果:")

    # 世界杯比赛字段填充率
    wc_leagues = [40, 7514, 7525, 7541]

    important_fields = ['match_time', 'venue', 'venue_city', 'referee',
                        'home_goals', 'away_goals', 'home_goals_ht', 'away_goals_ht',
                        'home_shots', 'away_shots', 'home_corners', 'away_corners',
                        'home_possession', 'away_possession']

    print("\n关键字段填充率:")
    for field in important_fields:
        cursor.execute(f'''
            SELECT COUNT(*) FROM matches
            WHERE league_id IN ({','.join(map(str, wc_leagues))})
            AND {field} IS NOT NULL AND {field} != ''
        ''')
        filled = cursor.fetchone()[0]
        cursor.execute(f'''
            SELECT COUNT(*) FROM matches
            WHERE league_id IN ({','.join(map(str, wc_leagues))})
        ''')
        total = cursor.fetchone()[0]
        pct = (filled/total*100) if total > 0 else 0
        print(f'  {field}: {filled}/{total} ({pct:.1f}%)')

    # teams表城市填充率
    cursor.execute('''
        SELECT COUNT(*) FROM teams
        WHERE city IS NOT NULL AND city != ''
    ''')
    teams_with_city = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM teams')
    total_teams = cursor.fetchone()[0]
    print(f'\n球队城市信息: {teams_with_city}/{total_teams} ({teams_with_city/total_teams*100:.1f}%)')

    conn.close()


if __name__ == '__main__':
    update_matches()
    verify_update()