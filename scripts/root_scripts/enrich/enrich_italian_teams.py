"""
补充意大利球队详细信息

包含:
- 中文名
- 城市
- 球场
- 球场容量
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

# 意甲球队详细信息
SERIE_A_TEAMS = {
    'Juventus': {
        'name_cn': '尤文图斯',
        'city': 'Turin',
        'city_cn': '都灵',
        'stadium': 'Allianz Stadium',
        'stadium_capacity': 41507,
    },
    'Inter': {
        'name_cn': '国际米兰',
        'city': 'Milan',
        'city_cn': '米兰',
        'stadium': 'San Siro',
        'stadium_capacity': 75923,
    },
    'Milan': {
        'name_cn': 'AC米兰',
        'city': 'Milan',
        'city_cn': '米兰',
        'stadium': 'San Siro',
        'stadium_capacity': 75923,
    },
    'Napoli': {
        'name_cn': '那不勒斯',
        'city': 'Naples',
        'city_cn': '那不勒斯',
        'stadium': 'Diego Armando Maradona Stadium',
        'stadium_capacity': 54726,
    },
    'Roma': {
        'name_cn': '罗马',
        'city': 'Rome',
        'city_cn': '罗马',
        'stadium': 'Stadio Olimpico',
        'stadium_capacity': 70634,
    },
    'Lazio': {
        'name_cn': '拉齐奥',
        'city': 'Rome',
        'city_cn': '罗马',
        'stadium': 'Stadio Olimpico',
        'stadium_capacity': 70634,
    },
    'Atalanta': {
        'name_cn': '亚特兰大',
        'city': 'Bergamo',
        'city_cn': '贝加莫',
        'stadium': 'Gewiss Stadium',
        'stadium_capacity': 23849,
    },
    'Fiorentina': {
        'name_cn': '佛罗伦萨',
        'city': 'Florence',
        'city_cn': '佛罗伦萨',
        'stadium': 'Artemio Franchi',
        'stadium_capacity': 43147,
    },
    'Bologna': {
        'name_cn': '博洛尼亚',
        'city': 'Bologna',
        'city_cn': '博洛尼亚',
        'stadium': 'Stadio Renato Dall\'Ara',
        'stadium_capacity': 38279,
    },
    'Torino': {
        'name_cn': '都灵',
        'city': 'Turin',
        'city_cn': '都灵',
        'stadium': 'Stadio Olimpico Grande Torino',
        'stadium_capacity': 27958,
    },
    'Udinese': {
        'name_cn': '乌迪内斯',
        'city': 'Udine',
        'city_cn': '乌迪内',
        'stadium': 'Dacia Arena',
        'stadium_capacity': 25144,
    },
    'Sassuolo': {
        'name_cn': '萨索洛',
        'city': 'Sassuolo',
        'city_cn': '萨索洛',
        'stadium': 'Mapei Stadium',
        'stadium_capacity': 23584,
    },
    'Sampdoria': {
        'name_cn': '桑普多利亚',
        'city': 'Genoa',
        'city_cn': '热那亚',
        'stadium': 'Luigi Ferraris',
        'stadium_capacity': 36599,
    },
    'Genoa': {
        'name_cn': '热那亚',
        'city': 'Genoa',
        'city_cn': '热那亚',
        'stadium': 'Luigi Ferraris',
        'stadium_capacity': 36599,
    },
    'Cagliari': {
        'name_cn': '卡利亚里',
        'city': 'Cagliari',
        'city_cn': '卡利亚里',
        'stadium': 'Unipol Domus',
        'stadium_capacity': 16500,
    },
    'Verona': {
        'name_cn': '维罗纳',
        'city': 'Verona',
        'city_cn': '维罗纳',
        'stadium': 'Stadio Marc\'Antonio Bentegodi',
        'stadium_capacity': 39211,
    },
    'Empoli': {
        'name_cn': '恩波利',
        'city': 'Empoli',
        'city_cn': '恩波利',
        'stadium': 'Stadio Carlo Castellani',
        'stadium_capacity': 16284,
    },
    'Lecce': {
        'name_cn': '莱切',
        'city': 'Lecce',
        'city_cn': '莱切',
        'stadium': 'Stadio Via del Mare',
        'stadium_capacity': 31455,
    },
    'Monza': {
        'name_cn': '蒙扎',
        'city': 'Monza',
        'city_cn': '蒙扎',
        'stadium': 'Stadio Brianteo',
        'stadium_capacity': 15293,
    },
    'Salernitana': {
        'name_cn': '萨勒尼塔纳',
        'city': 'Salerno',
        'city_cn': '萨勒诺',
        'stadium': 'Stadio Arechi',
        'stadium_capacity': 37245,
    },
    'Spezia': {
        'name_cn': '斯佩齐亚',
        'city': 'La Spezia',
        'city_cn': '拉斯佩齐亚',
        'stadium': 'Stadio Alberto Picco',
        'stadium_capacity': 11204,
    },
    'Cremonese': {
        'name_cn': '克雷莫纳',
        'city': 'Cremona',
        'city_cn': '克雷莫纳',
        'stadium': 'Stadio Giovanni Zini',
        'stadium_capacity': 16003,
    },
    'Frosinone': {
        'name_cn': '弗罗西诺内',
        'city': 'Frosinone',
        'city_cn': '弗罗西诺内',
        'stadium': 'Stadio Benito Stirpe',
        'stadium_capacity': 16227,
    },
    'Venezia': {
        'name_cn': '威尼斯',
        'city': 'Venice',
        'city_cn': '威尼斯',
        'stadium': 'Stadio Pier Luigi Penzo',
        'stadium_capacity': 11150,
    },
    'Parma': {
        'name_cn': '帕尔马',
        'city': 'Parma',
        'city_cn': '帕尔马',
        'stadium': 'Stadio Ennio Tardini',
        'stadium_capacity': 22352,
    },
    'Como': {
        'name_cn': '科莫',
        'city': 'Como',
        'city_cn': '科莫',
        'stadium': 'Stadio Giuseppe Sinigaglia',
        'stadium_capacity': 13602,
    },
    'Hellas Verona': {
        'name_cn': '维罗纳',
        'city': 'Verona',
        'city_cn': '维罗纳',
        'stadium': 'Stadio Marc\'Antonio Bentegodi',
        'stadium_capacity': 39211,
    },
    'Cagliari': {
        'name_cn': '卡利亚里',
        'city': 'Cagliari',
        'city_cn': '卡利亚里',
        'stadium': 'Unipol Domus',
        'stadium_capacity': 16500,
    },
}


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def update_team_details():
    """更新球队详细信息"""
    print("=" * 60)
    print("Updating Italian team details...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    updated = 0
    for team_name, details in SERIE_A_TEAMS.items():
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
    print("Italian Teams Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 意甲球队
    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN stadium IS NOT NULL AND stadium != '' THEN 1 ELSE 0 END) as has_stadium,
            SUM(CASE WHEN stadium_capacity IS NOT NULL THEN 1 ELSE 0 END) as has_capacity,
            SUM(CASE WHEN name_cn IS NOT NULL AND name_cn != '' THEN 1 ELSE 0 END) as has_cn
        FROM teams
        WHERE team_id IN (
            SELECT DISTINCT home_team_id FROM matches WHERE league_id = 35
            UNION
            SELECT DISTINCT away_team_id FROM matches WHERE league_id = 35
        )
    ''')

    r = cursor.fetchone()
    print(f"Serie A teams: {r[0]}")
    print(f"  With stadium: {r[1]}")
    print(f"  With capacity: {r[2]}")
    print(f"  With Chinese name: {r[3]}")

    conn.close()


if __name__ == "__main__":
    update_team_details()
    show_stats()
    print("\nDone!")