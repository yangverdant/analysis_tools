"""
导入世界杯数据到数据库
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / 'data' / 'football_v2.db'
DATA_DIR = Path('d:/football_tools')

# 数据文件映射
DATA_FILES = {
    'wc_2026.json': {'league_id': 40, 'season': '2026', 'name': '世界杯'},
}


def get_or_create_team(cursor, team_name, country='International'):
    """获取或创建球队"""
    cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute('''
        INSERT INTO teams (name_en, name_cn, country)
        VALUES (?, '', ?)
    ''', (team_name, country))
    return cursor.lastrowid


def get_or_create_season(cursor, league_id, season_name):
    """获取或创建赛季"""
    cursor.execute('''
        SELECT season_id FROM seasons
        WHERE league_id = ? AND season_name = ?
    ''', (league_id, season_name))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute('''
        INSERT INTO seasons (season_name, league_id)
        VALUES (?, ?)
    ''', (season_name, league_id))
    return cursor.lastrowid


def import_data():
    """导入数据"""
    print("="*60)
    print("导入世界杯数据")
    print("="*60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    total_saved = 0

    for filename, meta in DATA_FILES.items():
        filepath = DATA_DIR / filename
        if not filepath.exists():
            print(f"\n{filename}: 文件不存在")
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                matches = json.load(f)
        except Exception as e:
            print(f"\n{filename}: 读取失败 - {e}")
            continue

        if not isinstance(matches, list):
            print(f"\n{filename}: 数据格式错误")
            continue

        print(f"\n{meta['name']} {meta['season']}: {len(matches)} 场")

        # 获取或创建赛季
        season_id = get_or_create_season(cursor, meta['league_id'], meta['season'])

        saved = 0
        for m in matches:
            try:
                match_id = f"wc_{m.get('match_id', '')}"
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

                # 映射状态
                status_map = {
                    'FT': 'finished',
                    'Finished': 'finished',
                    'NS': 'scheduled',
                    'TBD': 'scheduled',
                }
                status = status_map.get(status, status or 'scheduled')

                # 获取球队ID
                home_team_id = get_or_create_team(cursor, home_team)
                away_team_id = get_or_create_team(cursor, away_team)

                # 转换比分
                try:
                    home_goals = int(home_score) if home_score not in (None, '', '-') else None
                except:
                    home_goals = None
                try:
                    away_goals = int(away_score) if away_score not in (None, '', '-') else None
                except:
                    away_goals = None
                try:
                    home_goals_ht = int(home_score_ht) if home_score_ht not in (None, '', '-') else None
                except:
                    home_goals_ht = None
                try:
                    away_goals_ht = int(away_score_ht) if away_score_ht not in (None, '', '-') else None
                except:
                    away_goals_ht = None

                # 插入或更新
                cursor.execute('''
                    INSERT OR REPLACE INTO matches
                    (match_id, league_id, season_id, match_date, match_time,
                     home_team_id, away_team_id, home_goals, away_goals,
                     home_goals_ht, away_goals_ht, status, round_num)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (match_id, meta['league_id'], season_id, match_date, match_time,
                      home_team_id, away_team_id, home_goals, away_goals,
                      home_goals_ht, away_goals_ht, status, round_name))

                saved += 1
            except Exception as e:
                pass

        conn.commit()
        print(f"  保存: {saved} 场")
        total_saved += saved

    conn.close()

    print(f"\n{'='*60}")
    print(f"总计保存: {total_saved} 场")
    print(f"{'='*60}")


def print_summary():
    """打印数据概览"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("\n世界杯数据概览:")
    print("-"*60)

    cursor.execute('''
        SELECT l.name_cn, s.season_name, COUNT(m.match_id) as matches,
               SUM(CASE WHEN m.status = "finished" THEN 1 ELSE 0 END) as finished,
               SUM(CASE WHEN m.home_goals IS NOT NULL THEN 1 ELSE 0 END) as has_scores
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        JOIN seasons s ON m.season_id = s.season_id
        WHERE l.league_id IN (40, 7514, 7541)
        GROUP BY l.league_id, s.season_name
        ORDER BY l.league_id, s.season_name DESC
    ''')

    print(f"{'联赛':<15} {'赛季':<8} {'比赛':<8} {'已结束':<8} {'有比分':<8}")
    print("-"*60)
    for r in cursor.fetchall():
        print(f"{r['name_cn']:<15} {r['season_name']:<8} {r['matches']:<8} {r['finished']:<8} {r['has_scores']:<8}")

    # 球队统计
    cursor.execute('''
        SELECT COUNT(DISTINCT t.team_id)
        FROM teams t
        WHERE EXISTS (
            SELECT 1 FROM matches m
            WHERE (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
            AND m.league_id IN (40, 7514, 7541)
        )
    ''')
    print(f"\n参赛球队: {cursor.fetchone()[0]}")

    conn.close()


if __name__ == '__main__':
    import_data()
    print_summary()
