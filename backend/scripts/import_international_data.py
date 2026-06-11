"""
导入国际赛事数据到数据库
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path('d:/football_tools/data/football_v2.db')
DATA_DIR = Path('d:/football_tools/international_data')


def get_or_create_league(cursor, league_id, name_en, name_cn, competition_type='cup'):
    """获取或创建联赛"""
    cursor.execute('SELECT league_id FROM leagues WHERE league_id = ?', (league_id,))
    if cursor.fetchone():
        return league_id

    cursor.execute('''
        INSERT INTO leagues (league_id, name_en, name_cn, competition_type, country)
        VALUES (?, ?, ?, ?, 'International')
    ''', (league_id, name_en, name_cn, competition_type))
    return league_id


def get_or_create_team(cursor, team_name, team_id=None, country='International'):
    """获取或创建球队"""
    if team_id:
        cursor.execute('SELECT team_id FROM teams WHERE team_id = ?', (team_id,))
        if cursor.fetchone():
            return team_id

    cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute('''
        INSERT INTO teams (name_en, name_cn, country, team_type)
        VALUES (?, '', ?, 'national')
    ''', (team_name, country))
    return cursor.lastrowid


def get_or_create_season(cursor, league_id, season_name):
    """获取或创建赛季"""
    cursor.execute('''
        SELECT season_id FROM seasons WHERE league_id = ? AND season_name = ?
    ''', (league_id, season_name))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute('''
        INSERT INTO seasons (season_name, league_id) VALUES (?, ?)
    ''', (season_name, league_id))
    return cursor.lastrowid


def import_matches():
    """导入比赛数据"""
    print("=" * 70)
    print("导入国际赛事比赛数据")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    # 联赛名称映射
    league_names = {
        '1': ('UEFA European Championship', '欧洲杯'),
        '20': ("FIFA Women's World Cup", '女足世界杯'),
        '21': ('CAF World Cup Qualifiers', '非洲世界杯预选赛'),
        '22': ('AFC World Cup Qualifiers', '亚洲世界杯预选赛'),
        '23': ('Concacaf World Cup Qualifiers', '中北美世界杯预选赛'),
        '24': ('UEFA World Cup Qualifiers', '欧洲世界杯预选赛'),
        '27': ('CONMEBOL World Cup Qualifiers', '南美世界杯预选赛'),
        '26': ('OFC World Cup Qualifiers', '大洋洲世界杯预选赛'),
        '28': ('World Cup', '世界杯'),
        '29': ('Africa Cup of Nations', '非洲杯'),
        '15': ('Gold Cup', '金杯赛'),
        '17': ('Copa America', '美洲杯'),
        '347': ('AFC Asian Cup', '亚洲杯'),
        '354': ('UEFA Euro Qualifiers', '欧洲杯预选赛'),
        '356': ('Friendlies', '国际友谊赛'),
        '415': ('FIFA U17 World Cup', 'U17世界杯'),
        '418': ('Asian Cup Qualification', '亚洲杯预选赛'),
        '425': ('FIFA U20 World Cup', 'U20世界杯'),
        '500': ('Olympics Men', '奥运会男足'),
        '522': ('Olympics Women', '奥运会女足'),
        '633': ('UEFA Nations League', '欧国联'),
        '664': ('Concacaf Nations League', '中北美国家联赛'),
        '7098': ('AFCON Qualification', '非洲杯预选赛'),
    }

    total_matches = 0
    total_teams = 0

    # 遍历所有比赛文件
    for filepath in DATA_DIR.glob('*.json'):
        if filepath.name.startswith('teams_'):
            continue

        # 解析文件名
        parts = filepath.stem.split('_')
        if len(parts) < 2:
            continue

        league_id = int(parts[0])
        season = parts[1]

        if league_id not in league_names:
            continue

        name_en, name_cn = league_names[league_id]

        # 创建联赛和赛季
        get_or_create_league(cursor, league_id, name_en, name_cn)
        season_id = get_or_create_season(cursor, league_id, season)

        # 读取比赛数据
        with open(filepath, 'r', encoding='utf-8') as f:
            matches = json.load(f)

        if not isinstance(matches, list):
            continue

        print(f"\n{name_cn} {season}: {len(matches)} 场")

        for m in matches:
            try:
                match_id = f"intl_{m.get('match_id', '')}"
                match_date = m.get('match_date', '')
                match_time = m.get('match_time', '')
                home_team = m.get('match_hometeam_name', '')
                away_team = m.get('match_awayteam_name', '')
                home_team_id_api = m.get('match_hometeam_id')
                away_team_id_api = m.get('match_awayteam_id')
                home_score = m.get('match_hometeam_score')
                away_score = m.get('match_awayteam_score')
                home_score_ht = m.get('match_hometeam_halftime_score')
                away_score_ht = m.get('match_awayteam_halftime_score')
                status = m.get('match_status', '')
                round_name = m.get('match_round', '')
                stadium = m.get('match_stadium', '')

                # 映射状态
                status_map = {
                    'FT': 'finished',
                    'Finished': 'finished',
                    'NS': 'scheduled',
                    'TBD': 'scheduled',
                    'Postponed': 'postponed',
                    'Cancelled': 'cancelled'
                }
                status = status_map.get(status, status or 'scheduled')

                # 获取球队ID
                home_team_id = get_or_create_team(cursor, home_team, home_team_id_api)
                away_team_id = get_or_create_team(cursor, away_team, away_team_id_api)
                total_teams += 2

                # 转换比分
                def to_int(val):
                    try:
                        return int(val) if val not in (None, '', '-') else None
                    except:
                        return None

                # 提取城市
                city = ''
                if stadium and '(' in stadium:
                    city = stadium.split('(')[-1].rstrip(')')

                # 插入或更新
                cursor.execute('''
                    INSERT OR REPLACE INTO matches
                    (match_id, league_id, season_id, match_date, match_time,
                     home_team_id, away_team_id, home_goals, away_goals,
                     home_goals_ht, away_goals_ht, status, round_num, venue, venue_city, neutral, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'apifootball')
                ''', (match_id, league_id, season_id, match_date, match_time,
                      home_team_id, away_team_id, to_int(home_score), to_int(away_score),
                      to_int(home_score_ht), to_int(away_score_ht), status, round_name, stadium, city))

                total_matches += 1
            except Exception as e:
                pass

        conn.commit()

    conn.close()

    print(f"\n{'=' * 70}")
    print(f"导入完成:")
    print(f"  比赛: {total_matches}")
    print(f"{'=' * 70}")


def import_teams():
    """导入球队数据"""
    print("\n" + "=" * 70)
    print("导入国家队球员数据")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    # 检查是否有players表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='players'")
    if not cursor.fetchone():
        print("players表不存在，跳过球员导入")
        conn.close()
        return

    total_players = 0

    for filepath in DATA_DIR.glob('teams_*.json'):
        with open(filepath, 'r', encoding='utf-8') as f:
            teams = json.load(f)

        if not isinstance(teams, list):
            continue

        for team in teams:
            team_name = team.get('team_name', '')
            team_key = team.get('team_key')

            # 更新球队信息
            cursor.execute('''
                UPDATE teams SET team_type = 'national'
                WHERE name_en = ?
            ''', (team_name,))

            # 导入球员
            players = team.get('players', [])
            for p in players:
                player_key = p.get('player_key', '')
                player_id = p.get('player_id') or f"{team_key}_{player_key}"

                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO players
                        (player_id, player_key, team_id, player_name, player_complete_name,
                         player_number, player_country, player_type, player_age,
                         player_birthdate, player_is_captain, player_image)
                        SELECT ?, ?, team_id, ?, ?, ?, ?, ?, ?, ?, ?, ?
                        FROM teams WHERE name_en = ?
                    ''', (player_id, player_key, p.get('player_name', ''),
                          p.get('player_complete_name', ''), p.get('player_number', ''),
                          p.get('player_country', ''), p.get('player_type', ''),
                          p.get('player_age'), p.get('player_birthdate', ''),
                          1 if p.get('player_is_captain') else 0, p.get('player_image', ''),
                          team_name))
                    total_players += 1
                except:
                    pass

        conn.commit()

    conn.close()
    print(f"导入球员: {total_players}")


if __name__ == '__main__':
    import_matches()
    import_teams()