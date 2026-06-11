"""
补充比利时球队详细信息
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

# 比甲球队详细信息
JUPILER_TEAMS = {
    'Anderlecht': {
        'name_cn': '安德莱赫特',
        'city': 'Brussels',
        'city_cn': '布鲁塞尔',
        'stadium': 'Constant Vanden Stock Stadium',
        'stadium_capacity': 50093,
    },
    'Club Brugge': {
        'name_cn': '布鲁日',
        'city': 'Bruges',
        'city_cn': '布鲁日',
        'stadium': 'Jan Breydel Stadium',
        'stadium_capacity': 29062,
    },
    'Brugge': {
        'name_cn': '布鲁日',
        'city': 'Bruges',
        'city_cn': '布鲁日',
        'stadium': 'Jan Breydel Stadium',
        'stadium_capacity': 29062,
    },
    'Genk': {
        'name_cn': '亨克',
        'city': 'Genk',
        'city_cn': '亨克',
        'stadium': 'Cegeka Arena',
        'stadium_capacity': 24596,
    },
    'KRC Genk': {
        'name_cn': '亨克',
        'city': 'Genk',
        'city_cn': '亨克',
        'stadium': 'Cegeka Arena',
        'stadium_capacity': 24596,
    },
    'Gent': {
        'name_cn': '根特',
        'city': 'Ghent',
        'city_cn': '根特',
        'stadium': 'Ghelamco Arena',
        'stadium_capacity': 19968,
    },
    'AA Gent': {
        'name_cn': '根特',
        'city': 'Ghent',
        'city_cn': '根特',
        'stadium': 'Ghelamco Arena',
        'stadium_capacity': 19968,
    },
    'Antwerp': {
        'name_cn': '安特卫普',
        'city': 'Antwerp',
        'city_cn': '安特卫普',
        'stadium': 'Bosuilstadion',
        'stadium_capacity': 12420,
    },
    'Royal Antwerp': {
        'name_cn': '安特卫普',
        'city': 'Antwerp',
        'city_cn': '安特卫普',
        'stadium': 'Bosuilstadion',
        'stadium_capacity': 12420,
    },
    'Standard Liege': {
        'name_cn': '标准列日',
        'city': 'Liege',
        'city_cn': '列日',
        'stadium': 'Stade Maurice Dufrasne',
        'stadium_capacity': 28063,
    },
    'Standard': {
        'name_cn': '标准列日',
        'city': 'Liege',
        'city_cn': '列日',
        'stadium': 'Stade Maurice Dufrasne',
        'stadium_capacity': 28063,
    },
    'Charleroi': {
        'name_cn': '沙勒罗瓦',
        'city': 'Charleroi',
        'city_cn': '沙勒罗瓦',
        'stadium': 'Stade du Pays de Charleroi',
        'stadium_capacity': 15174,
    },
    'Mechelen': {
        'name_cn': '梅赫伦',
        'city': 'Mechelen',
        'city_cn': '梅赫伦',
        'stadium': 'Afv Thomas Park',
        'stadium_capacity': 14412,
    },
    'KV Mechelen': {
        'name_cn': '梅赫伦',
        'city': 'Mechelen',
        'city_cn': '梅赫伦',
        'stadium': 'Afv Thomas Park',
        'stadium_capacity': 14412,
    },
    'Cercle Brugge': {
        'name_cn': '布鲁日Cercle',
        'city': 'Bruges',
        'city_cn': '布鲁日',
        'stadium': 'Jan Breydel Stadium',
        'stadium_capacity': 29062,
    },
    'Sint-Truiden': {
        'name_cn': '圣图尔登',
        'city': 'Sint-Truiden',
        'city_cn': '圣图尔登',
        'stadium': 'Staaien',
        'stadium_capacity': 11080,
    },
    'STVV': {
        'name_cn': '圣图尔登',
        'city': 'Sint-Truiden',
        'city_cn': '圣图尔登',
        'stadium': 'Staaien',
        'stadium_capacity': 11080,
    },
    'Oostende': {
        'name_cn': '奥斯坦德',
        'city': 'Oostende',
        'city_cn': '奥斯坦德',
        'stadium': 'Serge Vanderputten Stadion',
        'stadium_capacity': 8072,
    },
    'KV Oostende': {
        'name_cn': '奥斯坦德',
        'city': 'Oostende',
        'city_cn': '奥斯坦德',
        'stadium': 'Serge Vanderputten Stadion',
        'stadium_capacity': 8072,
    },
    'Eupen': {
        'name_cn': '奥伊彭',
        'city': 'Eupen',
        'city_cn': '奥伊彭',
        'stadium': 'Kehrwegstadion',
        'stadium_capacity': 8540,
    },
    'KAS Eupen': {
        'name_cn': '奥伊彭',
        'city': 'Eupen',
        'city_cn': '奥伊彭',
        'stadium': 'Kehrwegstadion',
        'stadium_capacity': 8540,
    },
    'Leuven': {
        'name_cn': '鲁汶',
        'city': 'Leuven',
        'city_cn': '鲁汶',
        'stadium': 'Den Dreef',
        'stadium_capacity': 6352,
    },
    'Oud-Heverlee Leuven': {
        'name_cn': '鲁汶',
        'city': 'Leuven',
        'city_cn': '鲁汶',
        'stadium': 'Den Dreef',
        'stadium_capacity': 6352,
    },
    'Lokeren': {
        'name_cn': '洛克伦',
        'city': 'Lokeren',
        'city_cn': '洛克伦',
        'stadium': 'Daknamstadion',
        'stadium_capacity': 9271,
    },
    'Westerlo': {
        'name_cn': '韦斯特洛',
        'city': 'Westerlo',
        'city_cn': '韦斯特洛',
        'stadium': 'Het Kuipje',
        'stadium_capacity': 7873,
    },
    'KVC Westerlo': {
        'name_cn': '韦斯特洛',
        'city': 'Westerlo',
        'city_cn': '韦斯特洛',
        'stadium': 'Het Kuipje',
        'stadium_capacity': 7873,
    },
    'Zulte-Waregem': {
        'name_cn': '祖尔特瓦雷gem',
        'city': 'Waregem',
        'city_cn': '瓦雷gem',
        'stadium': 'Regenboogstadion',
        'stadium_capacity': 10427,
    },
    'Essevee': {
        'name_cn': '祖尔特瓦雷gem',
        'city': 'Waregem',
        'city_cn': '瓦雷gem',
        'stadium': 'Regenboogstadion',
        'stadium_capacity': 10427,
    },
    'Beerschot': {
        'name_cn': '贝尔肖特',
        'city': 'Antwerp',
        'city_cn': '安特卫普',
        'stadium': 'Olympisch Stadion',
        'stadium_capacity': 12388,
    },
    'Beerschot VA': {
        'name_cn': '贝尔肖特',
        'city': 'Antwerp',
        'city_cn': '安特卫普',
        'stadium': 'Olympisch Stadion',
        'stadium_capacity': 12388,
    },
    'Lierse': {
        'name_cn': '利亚斯',
        'city': 'Lier',
        'city_cn': '利亚尔',
        'stadium': 'Herman Vanderpoortenstadion',
        'stadium_capacity': 14638,
    },
}


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def update_team_details():
    """Update team details"""
    print("=" * 60)
    print("Updating Belgian team details...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    updated = 0
    for team_name, details in JUPILER_TEAMS.items():
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
    print("Belgian Teams Statistics")
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
        WHERE country = 'Belgium' OR team_id IN (
            SELECT DISTINCT home_team_id FROM matches WHERE league_id = 26
            UNION
            SELECT DISTINCT away_team_id FROM matches WHERE league_id = 26
        )
    ''')

    r = cursor.fetchone()
    print(f"Belgian teams: {r[0]}")
    print(f"  With stadium: {r[1]}")
    print(f"  With capacity: {r[2]}")
    print(f"  With Chinese name: {r[3]}")

    conn.close()


if __name__ == "__main__":
    update_team_details()
    show_stats()
    print("\nDone!")