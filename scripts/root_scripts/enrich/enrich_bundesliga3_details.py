"""
德丙联赛球队信息补充
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

BUNDESLIGA3_ID = 7402

# 德丙球队详细信息
TEAM_DETAILS = {
    'Dynamo Dresden': {
        'city': 'Dresden',
        'city_cn': '德累斯顿',
        'stadium': 'DDV-Stadion',
        'stadium_capacity': 32000,
        'name_cn': '德累斯顿迪纳摩',
    },
    'Arminia Bielefeld': {
        'city': 'Bielefeld',
        'city_cn': '比勒费尔德',
        'stadium': 'SchücoArena',
        'stadium_capacity': 27332,
        'name_cn': '比勒费尔德',
    },
    '1. FC Kaiserslautern': {
        'city': 'Kaiserslautern',
        'city_cn': '凯泽斯劳滕',
        'stadium': 'Betzenbergstadion',
        'stadium_capacity': 49500,
        'name_cn': '凯泽斯劳滕',
    },
    'SV Wehen Wiesbaden': {
        'city': 'Wiesbaden',
        'city_cn': '威斯巴登',
        'stadium': 'BRITA-Arena',
        'stadium_capacity': 13500,
        'name_cn': '威斯巴登',
    },
    'Hallescher FC': {
        'city': 'Halle',
        'city_cn': '哈雷',
        'stadium': 'Erdgas Sportpark',
        'stadium_capacity': 15057,
        'name_cn': '哈雷',
    },
    'MSV Duisburg': {
        'city': 'Duisburg',
        'city_cn': '杜伊斯堡',
        'stadium': 'Schauinsland-Reisen-Arena',
        'stadium_capacity': 31514,
        'name_cn': '杜伊斯堡',
    },
    'VfL Osnabrück': {
        'city': 'Osnabrück',
        'city_cn': '奥斯纳布吕克',
        'stadium': 'Bremer Brücke',
        'stadium_capacity': 16350,
        'name_cn': '奥斯纳布吕克',
    },
    'Preußen Münster': {
        'city': 'Münster',
        'city_cn': '明斯特',
        'stadium': 'Preußenstadion',
        'stadium_capacity': 14918,
        'name_cn': '普鲁士明斯特',
    },
    'Hansa Rostock': {
        'city': 'Rostock',
        'city_cn': '罗斯托克',
        'stadium': 'DKB-Arena',
        'stadium_capacity': 29000,
        'name_cn': '罗斯托克',
    },
    'Jahn Regensburg': {
        'city': 'Regensburg',
        'city_cn': '雷根斯堡',
        'stadium': 'Jahnstadion',
        'stadium_capacity': 15250,
        'name_cn': '雷根斯堡',
    },
    'Holstein Kiel': {
        'city': 'Kiel',
        'city_cn': '基尔',
        'stadium': 'Holstein-Stadion',
        'stadium_capacity': 15000,
        'name_cn': '基尔',
    },
    'Chemnitzer FC': {
        'city': 'Chemnitz',
        'city_cn': '开姆尼茨',
        'stadium': 'Sportforum Chemnitz',
        'stadium_capacity': 18600,
        'name_cn': '开姆尼茨',
    },
    'Rot-Weiß Erfurt': {
        'city': 'Erfurt',
        'city_cn': '埃尔福特',
        'stadium': 'Steigerwaldstadion',
        'stadium_capacity': 20785,
        'name_cn': '埃尔福特',
    },
    'SpVgg Unterhaching': {
        'city': 'Unterhaching',
        'city_cn': '温特哈兴',
        'stadium': 'Sportpark Unterhaching',
        'stadium_capacity': 10000,
        'name_cn': '温特哈兴',
    },
    '1. FSV Mainz 05 II': {
        'city': 'Mainz',
        'city_cn': '美因茨',
        'stadium': 'Stadion am Bruchweg',
        'stadium_capacity': 5500,
        'name_cn': '美因茨二队',
    },
    'Borussia Dortmund II': {
        'city': 'Dortmund',
        'city_cn': '多特蒙德',
        'stadium': 'Stadion Rote Erde',
        'stadium_capacity': 10000,
        'name_cn': '多特二队',
    },
    'VfB Stuttgart II': {
        'city': 'Stuttgart',
        'city_cn': '斯图加特',
        'stadium': 'Gazi-Stadion auf der Waldau',
        'stadium_capacity': 11000,
        'name_cn': '斯图加特二队',
    },
    'SG Sonnenhof Großaspach': {
        'city': 'Großaspach',
        'city_cn': '格罗萨斯帕赫',
        'stadium': 'Meimat Arena',
        'stadium_capacity': 3000,
        'name_cn': '格罗萨斯帕赫',
    },
    'Stuttgarter Kickers': {
        'city': 'Stuttgart',
        'city_cn': '斯图加特',
        'stadium': 'Waldau-Stadion',
        'stadium_capacity': 11000,
        'name_cn': '斯图加特踢球者',
    },
    'Energie Cottbus': {
        'city': 'Cottbus',
        'city_cn': '科特布斯',
        'stadium': 'Stadion der Freundschaft',
        'stadium_capacity': 22500,
        'name_cn': '科特布斯',
    },
    'Fortuna Köln': {
        'city': 'Cologne',
        'city_cn': '科隆',
        'stadium': 'Südstadion',
        'stadium_capacity': 14000,
        'name_cn': '科隆幸运',
    },
    'Würzburger Kickers': {
        'city': 'Würzburg',
        'city_cn': '维尔茨堡',
        'stadium': 'Flyeralarm Arena',
        'stadium_capacity': 10050,
        'name_cn': '维尔茨堡踢球者',
    },
    'Zwickau': {
        'city': 'Zwickau',
        'city_cn': '茨维考',
        'stadium': 'Stadion Zwickau',
        'stadium_capacity': 10000,
        'name_cn': '茨维考',
    },
    'KFC Uerdingen': {
        'city': 'Krefeld',
        'city_cn': '克雷费尔德',
        'stadium': 'Grotenburg-Stadion',
        'stadium_capacity': 10000,
        'name_cn': '乌丁根',
    },
    'Bayern Munich II': {
        'city': 'Munich',
        'city_cn': '慕尼黑',
        'stadium': 'Grünwalder Stadion',
        'stadium_capacity': 12000,
        'name_cn': '拜仁二队',
    },
    'Meppen': {
        'city': 'Meppen',
        'city_cn': '梅彭',
        'stadium': 'Hindenburgstadion',
        'stadium_capacity': 6100,
        'name_cn': '梅彭',
    },
    'Waldhof Mannheim': {
        'city': 'Mannheim',
        'city_cn': '曼海姆',
        'stadium': 'Carl-Benz-Stadion',
        'stadium_capacity': 18000,
        'name_cn': '曼海姆',
    },
    '1860 Munich': {
        'city': 'Munich',
        'city_cn': '慕尼黑',
        'stadium': 'Grünwalder Stadion',
        'stadium_capacity': 15000,
        'name_cn': '慕尼黑1860',
    },
    'Viktoria Köln': {
        'city': 'Cologne',
        'city_cn': '科隆',
        'stadium': 'Sportpark Höhenberg',
        'stadium_capacity': 8000,
        'name_cn': '科隆维多利亚',
    },
    'Saarbrücken': {
        'city': 'Saarbrücken',
        'city_cn': '萨尔布吕肯',
        'stadium': 'Ludwigsparkstadion',
        'stadium_capacity': 30000,
        'name_cn': '萨尔布吕肯',
    },
    'Lübeck': {
        'city': 'Lübeck',
        'city_cn': '吕贝克',
        'stadium': 'Lohmühle',
        'stadium_capacity': 15000,
        'name_cn': '吕贝克',
    },
    'Ingolstadt': {
        'city': 'Ingolstadt',
        'city_cn': '因戈尔施塔特',
        'stadium': 'Tuja-Stadion',
        'stadium_capacity': 11000,
        'name_cn': '因戈尔施塔特',
    },
    'Freiburg II': {
        'city': 'Freiburg',
        'city_cn': '弗赖堡',
        'stadium': 'Schwarzwald-Stadion',
        'stadium_capacity': 24000,
        'name_cn': '弗赖堡二队',
    },
    'Elversberg': {
        'city': 'Spiesen-Elversberg',
        'city_cn': '埃尔弗斯贝格',
        'stadium': 'Waldstadion an der Kaiserlinde',
        'stadium_capacity': 5000,
        'name_cn': '埃尔弗斯贝格',
    },
    'Verl': {
        'city': 'Verl',
        'city_cn': '弗尔',
        'stadium': 'Sportclub Arena',
        'stadium_capacity': 4000,
        'name_cn': '弗尔',
    },
    'Duisburg': {
        'city': 'Duisburg',
        'city_cn': '杜伊斯堡',
        'stadium': 'Schauinsland-Reisen-Arena',
        'stadium_capacity': 31514,
        'name_cn': '杜伊斯堡',
    },
    'Rostock': {
        'city': 'Rostock',
        'city_cn': '罗斯托克',
        'stadium': 'DKB-Arena',
        'stadium_capacity': 29000,
        'name_cn': '罗斯托克',
    },
    'Kiel': {
        'city': 'Kiel',
        'city_cn': '基尔',
        'stadium': 'Holstein-Stadion',
        'stadium_capacity': 15000,
        'name_cn': '基尔',
    },
    'Münster': {
        'city': 'Münster',
        'city_cn': '明斯特',
        'stadium': 'Preußenstadion',
        'stadium_capacity': 14918,
        'name_cn': '普鲁士明斯特',
    },
    'Dresden': {
        'city': 'Dresden',
        'city_cn': '德累斯顿',
        'stadium': 'DDV-Stadion',
        'stadium_capacity': 32000,
        'name_cn': '德累斯顿迪纳摩',
    },
}


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def update_team_details():
    """更新球队详细信息"""
    print("=" * 60)
    print("Updating 3. Liga team details...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 获取德丙所有球队
    cursor.execute('''
        SELECT DISTINCT team_id, name_en FROM teams
        WHERE team_id IN (
            SELECT home_team_id FROM matches WHERE league_id = ?
            UNION
            SELECT away_team_id FROM matches WHERE league_id = ?
        )
    ''', (BUNDESLIGA3_ID, BUNDESLIGA3_ID))

    teams = cursor.fetchall()
    print(f"Found {len(teams)} teams")

    updated = 0
    for team in teams:
        team_id = team[0]
        team_name = team[1]

        # 尝试匹配球队
        matched = False
        for key, details in TEAM_DETAILS.items():
            if key.lower() in team_name.lower() or team_name.lower() in key.lower():
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

                updated += 1
                matched = True
                try:
                    print(f"  Updated: {team_name}")
                except:
                    print(f"  Updated: team_id={team_id}")
                break

        if not matched:
            print(f"  No match: {team_name}")

    conn.commit()
    conn.close()
    print(f"\nUpdated {updated} teams")
    return updated


def show_stats():
    """显示统计"""
    print("\n" + "=" * 60)
    print("3. Liga Team Statistics")
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
            SELECT DISTINCT home_team_id FROM matches WHERE league_id = ?
            UNION
            SELECT DISTINCT away_team_id FROM matches WHERE league_id = ?
        )
    ''', (BUNDESLIGA3_ID, BUNDESLIGA3_ID))

    r = cursor.fetchone()
    print(f"Total teams: {r[0]}")
    print(f"With stadium: {r[1]}")
    print(f"With capacity: {r[2]}")
    print(f"With Chinese name: {r[3]}")

    conn.close()


if __name__ == "__main__":
    update_team_details()
    show_stats()
    print("\nDone!")