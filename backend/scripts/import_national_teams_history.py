"""
将国家队比赛历史导入数据库
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path('d:/football_tools/data/football_v2.db')
DATA_DIR = Path('d:/football_tools/national_teams_history')


def import_national_team_matches():
    """导入国家队比赛数据"""
    print("=" * 70)
    print("导入国家队比赛历史到数据库")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    # 联赛名称映射
    league_names = {
        '1': ('UEFA European Championship', '欧洲杯'),
        '15': ('Gold Cup', '金杯赛'),
        '17': ('Copa America', '美洲杯'),
        '20': ("FIFA Women's World Cup", '女足世界杯'),
        '21': ('CAF World Cup Qualifiers', '非洲世界杯预选赛'),
        '22': ('AFC World Cup Qualifiers', '亚洲世界杯预选赛'),
        '23': ('Concacaf World Cup Qualifiers', '中北美世界杯预选赛'),
        '24': ('UEFA World Cup Qualifiers', '欧洲世界杯预选赛'),
        '26': ('OFC World Cup Qualifiers', '大洋洲世界杯预选赛'),
        '27': ('CONMEBOL World Cup Qualifiers', '南美世界杯预选赛'),
        '28': ('World Cup', '世界杯'),
        '29': ('Africa Cup of Nations', '非洲杯'),
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

    def get_or_create_league(league_id, name_en, name_cn):
        cursor.execute('SELECT league_id FROM leagues WHERE league_id = ?', (league_id,))
        if cursor.fetchone():
            return league_id
        cursor.execute('''
            INSERT INTO leagues (league_id, name_en, name_cn, competition_type, country)
            VALUES (?, ?, ?, 'cup', 'International')
        ''', (league_id, name_en, name_cn))
        return league_id

    def get_or_create_season(league_id, season_name):
        cursor.execute('SELECT season_id FROM seasons WHERE league_id = ? AND season_name = ?', (league_id, season_name))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute('INSERT INTO seasons (season_name, league_id) VALUES (?, ?)', (season_name, league_id))
        return cursor.lastrowid

    def get_or_create_team(team_name):
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute('''
            INSERT INTO teams (name_en, name_cn, country, team_type)
            VALUES (?, '', 'International', 'national')
        ''', (team_name,))
        return cursor.lastrowid

    total_matches = 0
    files_processed = 0

    for filepath in DATA_DIR.glob('*.json'):
        files_processed += 1

        with open(filepath, 'r', encoding='utf-8') as f:
            matches = json.load(f)

        if not isinstance(matches, list):
            continue

        for m in matches:
            try:
                match_id = f"intl_{m.get('match_id', '')}"
                league_id = m.get('league_id')
                match_date = m.get('match_date', '')
                match_time = m.get('match_time', '')
                home_team = m.get('match_hometeam_name', '')
                away_team = m.get('match_awayteam_name', '')
                home_score = m.get('match_hometeam_score')
                away_score = m.get('match_awayteam_score')
                home_score_ht = m.get('match_hometeam_halftime_score')
                away_score_ht = m.get('match_awayteam_halftime_score')
                status = m.get('match_status', '')
                round_name = m.get('match_round', '')
                stadium = m.get('match_stadium', '')

                # 处理联赛
                season = match_date[:4] if match_date else ''
                if league_id and str(league_id) in league_names:
                    name_en, name_cn = league_names[str(league_id)]
                    get_or_create_league(league_id, name_en, name_cn)
                    season_id = get_or_create_season(league_id, season)
                else:
                    league_id = 356  # 默认友谊赛
                    season_id = get_or_create_season(league_id, season)

                # 状态映射
                status_map = {'FT': 'finished', 'NS': 'scheduled', 'TBD': 'scheduled'}
                status = status_map.get(status, status or 'scheduled')

                # 获取球队ID
                home_team_id = get_or_create_team(home_team)
                away_team_id = get_or_create_team(away_team)

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

                # 插入比赛
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

        if files_processed % 20 == 0:
            conn.commit()
            print(f"已处理 {files_processed} 个文件, {total_matches} 场比赛")

    conn.commit()
    conn.close()

    print(f"\n{'=' * 70}")
    print(f"导入完成!")
    print(f"  文件数: {files_processed}")
    print(f"  比赛数: {total_matches}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    import_national_team_matches()