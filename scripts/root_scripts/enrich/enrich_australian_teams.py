"""
补充澳大利亚球队详细信息
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

# 澳超球队详细信息
ALEAGUE_TEAMS = {
    'Adelaide United': {
        'name_cn': '阿德莱德联',
        'city': 'Adelaide',
        'city_cn': '阿德莱德',
        'stadium': 'Coopers Stadium',
        'stadium_capacity': 16500,
    },
    'Brisbane Roar': {
        'name_cn': '布里斯班狮吼',
        'city': 'Brisbane',
        'city_cn': '布里斯班',
        'stadium': 'Suncorp Stadium',
        'stadium_capacity': 52500,
    },
    'Central Coast Mariners': {
        'name_cn': '中央海岸水手',
        'city': 'Gosford',
        'city_cn': '戈斯福德',
        'stadium': 'Central Coast Stadium',
        'stadium_capacity': 20059,
    },
    'Melbourne City FC': {
        'name_cn': '墨尔本城',
        'city': 'Melbourne',
        'city_cn': '墨尔本',
        'stadium': 'AAMI Park',
        'stadium_capacity': 30505,
    },
    'Melbourne Victory': {
        'name_cn': '墨尔本胜利',
        'city': 'Melbourne',
        'city_cn': '墨尔本',
        'stadium': 'AAMI Park',
        'stadium_capacity': 30505,
    },
    'Newcastle United Jets': {
        'name_cn': '纽卡斯尔喷气机',
        'city': 'Newcastle',
        'city_cn': '纽卡斯尔',
        'stadium': 'McDonald Jones Stadium',
        'stadium_capacity': 30090,
    },
    'Perth Glory': {
        'name_cn': '珀斯光荣',
        'city': 'Perth',
        'city_cn': '珀斯',
        'stadium': 'HBF Park',
        'stadium_capacity': 20087,
    },
    'Sydney FC': {
        'name_cn': '悉尼FC',
        'city': 'Sydney',
        'city_cn': '悉尼',
        'stadium': 'Allianz Stadium',
        'stadium_capacity': 45000,
    },
    'Wellington Phoenix': {
        'name_cn': '惠灵顿凤凰',
        'city': 'Wellington',
        'city_cn': '惠灵顿',
        'stadium': 'Sky Stadium',
        'stadium_capacity': 34000,
    },
    'Western Sydney Wanderers': {
        'name_cn': '西悉尼流浪者',
        'city': 'Sydney',
        'city_cn': '悉尼',
        'stadium': 'CommBank Stadium',
        'stadium_capacity': 30000,
    },
    'Western United': {
        'name_cn': '西部联',
        'city': 'Melbourne',
        'city_cn': '墨尔本',
        'stadium': 'GMHBA Stadium',
        'stadium_capacity': 36000,
    },
    'Macarthur FC': {
        'name_cn': '麦克阿瑟FC',
        'city': 'Sydney',
        'city_cn': '悉尼',
        'stadium': 'Campbelltown Stadium',
        'stadium_capacity': 17500,
    },
    'Auckland FC': {
        'name_cn': '奥克兰FC',
        'city': 'Auckland',
        'city_cn': '奥克兰',
        'stadium': 'Go Media Stadium',
        'stadium_capacity': 25000,
    },
}


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def update_team_details():
    """Update team details"""
    print("=" * 60)
    print("Updating Australian team details...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    updated = 0
    for team_name, details in ALEAGUE_TEAMS.items():
        cursor.execute('''
            SELECT team_id, name_en FROM teams
            WHERE name_en = ? OR name_en LIKE ? OR name_cn = ?
        ''', (team_name, f'%{team_name}%', details.get('name_cn', '')))

        row = cursor.fetchone()
        if row:
            team_id = row[0]

            cursor.execute("PRAGMA table_info(teams)")
            columns = [r[1] for r in cursor.fetchall()]

            if 'city' in columns:
                cursor.execute('''
                    UPDATE teams SET
                        city = COALESCE(?, city),
                        stadium = COALESCE(?, stadium),
                        stadium_capacity = COALESCE(?, stadium_capacity),
                        name_cn = COALESCE(?, name_cn)
                    WHERE team_id = ?
                ''', (details.get('city'), details.get('stadium'),
                      details.get('stadium_capacity'), details.get('name_cn'), team_id))
            else:
                cursor.execute('''
                    UPDATE teams SET
                        stadium = COALESCE(?, stadium),
                        stadium_capacity = COALESCE(?, stadium_capacity),
                        name_cn = COALESCE(?, name_cn)
                    WHERE team_id = ?
                ''', (details.get('stadium'), details.get('stadium_capacity'),
                      details.get('name_cn'), team_id))

            conn.commit()
            updated += 1
            print(f"  Updated: {team_name}")

    conn.close()
    print(f"\nUpdated {updated} teams")
    return updated


def show_stats():
    """Show statistics"""
    print("\n" + "=" * 60)
    print("Australian Teams Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN stadium IS NOT NULL AND stadium != '' THEN 1 ELSE 0 END) as has_stadium,
            SUM(CASE WHEN stadium_capacity IS NOT NULL THEN 1 ELSE 0 END) as has_capacity,
            SUM(CASE WHEN name_cn IS NOT NULL AND name_cn != '' THEN 1 ELSE 0 END) as has_cn
        FROM teams
        WHERE team_id IN (
            SELECT DISTINCT home_team_id FROM matches WHERE league_id = 1
            UNION
            SELECT DISTINCT away_team_id FROM matches WHERE league_id = 1
        )
    ''')

    r = cursor.fetchone()
    print(f"A-League teams: {r[0]}")
    print(f"  With stadium: {r[1]}")
    print(f"  With capacity: {r[2]}")
    print(f"  With Chinese name: {r[3]}")

    conn.close()


if __name__ == "__main__":
    update_team_details()
    show_stats()
    print("\nDone!")