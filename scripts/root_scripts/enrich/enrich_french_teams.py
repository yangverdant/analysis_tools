"""
补充法国球队详细信息
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

# 法甲球队详细信息
LIGUE_1_TEAMS = {
    'Paris SG': {
        'name_cn': '巴黎圣日耳曼',
        'city': 'Paris',
        'city_cn': '巴黎',
        'stadium': 'Parc des Princes',
        'stadium_capacity': 47929,
    },
    'PSG': {
        'name_cn': '巴黎圣日耳曼',
        'city': 'Paris',
        'city_cn': '巴黎',
        'stadium': 'Parc des Princes',
        'stadium_capacity': 47929,
    },
    'Marseille': {
        'name_cn': '马赛',
        'city': 'Marseille',
        'city_cn': '马赛',
        'stadium': 'Orange Velodrome',
        'stadium_capacity': 67000,
    },
    'Lyon': {
        'name_cn': '里昂',
        'city': 'Lyon',
        'city_cn': '里昂',
        'stadium': 'Groupama Stadium',
        'stadium_capacity': 59186,
    },
    'Monaco': {
        'name_cn': '摩纳哥',
        'city': 'Monaco',
        'city_cn': '摩纳哥',
        'stadium': 'Stade Louis II',
        'stadium_capacity': 18523,
    },
    'Nice': {
        'name_cn': '尼斯',
        'city': 'Nice',
        'city_cn': '尼斯',
        'stadium': 'Allianz Riviera',
        'stadium_capacity': 35624,
    },
    'Lille': {
        'name_cn': '里尔',
        'city': 'Lille',
        'city_cn': '里尔',
        'stadium': 'Stade Pierre-Mauroy',
        'stadium_capacity': 50186,
    },
    'Rennes': {
        'name_cn': '雷恩',
        'city': 'Rennes',
        'city_cn': '雷恩',
        'stadium': 'Roazhon Park',
        'stadium_capacity': 29197,
    },
    'Nantes': {
        'name_cn': '南特',
        'city': 'Nantes',
        'city_cn': '南特',
        'stadium': 'Stade de la Beaujoire',
        'stadium_capacity': 35322,
    },
    'Strasbourg': {
        'name_cn': '斯特拉斯堡',
        'city': 'Strasbourg',
        'city_cn': '斯特拉斯堡',
        'stadium': 'Stade de la Meinau',
        'stadium_capacity': 26109,
    },
    'Montpellier': {
        'name_cn': '蒙彼利埃',
        'city': 'Montpellier',
        'city_cn': '蒙彼利埃',
        'stadium': 'Stade de la Mosson',
        'stadium_capacity': 15943,
    },
    'Bordeaux': {
        'name_cn': '波尔多',
        'city': 'Bordeaux',
        'city_cn': '波尔多',
        'stadium': 'Matmut Atlantique',
        'stadium_capacity': 42132,
    },
    'Reims': {
        'name_cn': '兰斯',
        'city': 'Reims',
        'city_cn': '兰斯',
        'stadium': 'Stade Auguste Delaune',
        'stadium_capacity': 21068,
    },
    'Toulouse': {
        'name_cn': '图卢兹',
        'city': 'Toulouse',
        'city_cn': '图卢兹',
        'stadium': 'Stadium Municipal',
        'stadium_capacity': 33303,
    },
    'Saint-Etienne': {
        'name_cn': '圣埃蒂安',
        'city': 'Saint-Etienne',
        'city_cn': '圣埃蒂安',
        'stadium': 'Stade Geoffroy Guichard',
        'stadium_capacity': 41379,
    },
    'Angers': {
        'name_cn': '昂热',
        'city': 'Angers',
        'city_cn': '昂热',
        'stadium': 'Stade Raymond Kopa',
        'stadium_capacity': 18210,
    },
    'Troyes': {
        'name_cn': '特鲁瓦',
        'city': 'Troyes',
        'city_cn': '特鲁瓦',
        'stadium': 'Stade de l\'Aube',
        'stadium_capacity': 20400,
    },
    'Metz': {
        'name_cn': '梅斯',
        'city': 'Metz',
        'city_cn': '梅斯',
        'stadium': 'Stade Saint-Symphorien',
        'stadium_capacity': 25736,
    },
    'Brest': {
        'name_cn': '布雷斯特',
        'city': 'Brest',
        'city_cn': '布雷斯特',
        'stadium': 'Stade Francis Le Ble',
        'stadium_capacity': 15220,
    },
    'Lens': {
        'name_cn': '朗斯',
        'city': 'Lens',
        'city_cn': '朗斯',
        'stadium': 'Stade Bollaert-Delelis',
        'stadium_capacity': 38223,
    },
    'Auxerre': {
        'name_cn': '欧塞尔',
        'city': 'Auxerre',
        'city_cn': '欧塞尔',
        'stadium': 'Stade de l\'Abbe-Deschamps',
        'stadium_capacity': 23493,
    },
    'Le Havre': {
        'name_cn': '勒阿弗尔',
        'city': 'Le Havre',
        'city_cn': '勒阿弗尔',
        'stadium': 'Stade Oceane',
        'stadium_capacity': 25178,
    },
}


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def update_team_details():
    """更新球队详细信息"""
    print("=" * 60)
    print("Updating French team details...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    updated = 0
    for team_name, details in LIGUE_1_TEAMS.items():
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
    """显示统计"""
    print("\n" + "=" * 60)
    print("French Teams Statistics")
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
            SELECT DISTINCT home_team_id FROM matches WHERE league_id = 24
            UNION
            SELECT DISTINCT away_team_id FROM matches WHERE league_id = 24
        )
    ''')

    r = cursor.fetchone()
    print(f"Ligue 1 teams: {r[0]}")
    print(f"  With stadium: {r[1]}")
    print(f"  With capacity: {r[2]}")
    print(f"  With Chinese name: {r[3]}")

    conn.close()


if __name__ == "__main__":
    update_team_details()
    show_stats()
    print("\nDone!")