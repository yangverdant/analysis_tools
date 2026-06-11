"""
导入世界杯球队和球员数据到数据库
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / 'data' / 'football_v2.db'
DATA_DIR = Path('d:/football_tools')

# 球队数据文件
TEAM_FILES = {
    'wc_teams_2014.json': {'season': '2014', 'league_id': 40},
    'wc_teams_2018_v2.json': {'season': '2018', 'league_id': 40},
    'wc_teams_2022.json': {'season': '2022', 'league_id': 40},
    'wc_teams_2026.json': {'season': '2026', 'league_id': 40},
    'wwc_teams_2023.json': {'season': '2023', 'league_id': 7541},
}


def import_teams_and_players():
    """导入球队和球员数据"""
    print("=" * 60)
    print("导入世界杯球队和球员数据")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 检查是否有teams表扩展字段
    cursor.execute("PRAGMA table_info(teams)")
    team_columns = [col[1] for col in cursor.fetchall()]
    print(f"teams表字段: {team_columns}")

    # 检查是否有players表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='players'")
    has_players_table = cursor.fetchone() is not None

    if not has_players_table:
        # 创建players表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                player_id TEXT PRIMARY KEY,
                player_key TEXT,
                team_id INTEGER,
                player_name TEXT,
                player_complete_name TEXT,
                player_number TEXT,
                player_country TEXT,
                player_type TEXT,
                player_age INTEGER,
                player_birthdate TEXT,
                player_is_captain INTEGER DEFAULT 0,
                player_image TEXT,
                season TEXT,
                league_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("创建players表")

    # 检查players表字段
    cursor.execute("PRAGMA table_info(players)")
    player_columns = [col[1] for col in cursor.fetchall()]

    total_teams = 0
    total_players = 0
    total_venues = 0

    for filename, meta in TEAM_FILES.items():
        filepath = DATA_DIR / filename
        if not filepath.exists():
            print(f"\n{filename}: 文件不存在")
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                teams = json.load(f)
        except Exception as e:
            print(f"\n{filename}: 读取失败 - {e}")
            continue

        if not isinstance(teams, list):
            print(f"\n{filename}: 数据格式错误")
            continue

        print(f"\n{meta['season']}: {len(teams)} 支球队")

        for team in teams:
            team_key = team.get('team_key')
            team_name = team.get('team_name', '')
            team_country = team.get('team_country', '')
            team_founded = team.get('team_founded')
            team_badge = team.get('team_badge', '')

            # 获取venue信息
            venue = team.get('venue', {})
            venue_name = venue.get('venue_name', '')
            venue_city = venue.get('venue_city', '')
            venue_capacity = venue.get('venue_capacity', '')
            venue_address = venue.get('venue_address', '')

            # 更新球队信息
            cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
            row = cursor.fetchone()

            if row:
                team_id = row[0]
                # 更新球队详细信息
                if 'city' in team_columns:
                    cursor.execute('''
                        UPDATE teams SET
                            city = COALESCE(?, city),
                            stadium = COALESCE(?, stadium),
                            founded_year = COALESCE(?, founded_year),
                            stadium_capacity = COALESCE(?, stadium_capacity),
                            logo_url = COALESCE(?, logo_url)
                        WHERE team_id = ?
                    ''', (venue_city, venue_name, team_founded, venue_capacity, team_badge, team_id))
                else:
                    # 简单更新
                    cursor.execute('''
                        UPDATE teams SET
                            country = COALESCE(?, country)
                        WHERE team_id = ?
                    ''', (team_country, team_id))
            else:
                # 创建新球队
                cursor.execute('''
                    INSERT INTO teams (name_en, name_cn, country)
                    VALUES (?, '', ?)
                ''', (team_name, team_country))
                team_id = cursor.lastrowid

            total_teams += 1
            if venue_name or venue_city:
                total_venues += 1

            # 导入球员
            players = team.get('players', [])
            for p in players:
                player_key = p.get('player_key', '')
                player_id = p.get('player_id', '') or f"{team_key}_{player_key}"
                player_name = p.get('player_name', '')
                player_complete_name = p.get('player_complete_name', '')
                player_number = p.get('player_number', '')
                player_country = p.get('player_country', '')
                player_type = p.get('player_type', '')
                player_age = p.get('player_age')
                player_birthdate = p.get('player_birthdate', '')
                player_is_captain = 1 if p.get('player_is_captain') else 0
                player_image = p.get('player_image', '')

                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO players
                        (player_id, player_key, team_id, player_name, player_complete_name,
                         player_number, player_country, player_type, player_age,
                         player_birthdate, player_is_captain, player_image,
                         season, league_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (player_id, player_key, team_id, player_name, player_complete_name,
                          player_number, player_country, player_type, player_age,
                          player_birthdate, player_is_captain, player_image,
                          meta['season'], meta['league_id']))
                    total_players += 1
                except Exception as e:
                    pass

        conn.commit()

    conn.close()

    print(f"\n{'=' * 60}")
    print(f"导入完成:")
    print(f"  球队: {total_teams}")
    print(f"  场地信息: {total_venues}")
    print(f"  球员: {total_players}")
    print(f"{'=' * 60}")


def print_summary():
    """打印数据概览"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n世界杯球员数据概览:")
    print("-" * 60)

    cursor.execute('''
        SELECT season, league_id, COUNT(*) as players
        FROM players
        WHERE league_id IN (40, 7541)
        GROUP BY season, league_id
        ORDER BY season DESC
    ''')

    for r in cursor.fetchall():
        league_name = '世界杯' if r[1] == 40 else '女足世界杯'
        print(f"{league_name} {r[0]}: {r[2]} 名球员")

    # 统计国家队球员数量
    cursor.execute('''
        SELECT t.name_en, COUNT(p.player_id) as players
        FROM players p
        JOIN teams t ON p.team_id = t.team_id
        WHERE p.league_id IN (40, 7541)
        GROUP BY t.team_id
        ORDER BY players DESC
        LIMIT 10
    ''')

    print("\n球员最多的球队 (前10):")
    for r in cursor.fetchall():
        print(f"  {r[0]}: {r[1]} 名球员")

    conn.close()


if __name__ == '__main__':
    import_teams_and_players()
    print_summary()