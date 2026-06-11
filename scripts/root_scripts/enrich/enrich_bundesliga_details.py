"""
德甲联赛数据补充:
1. 球队城市、球场、容量
2. 观众人数（从CSV重新导入）
3. 裁判信息
4. 球队中文名
"""

import sqlite3
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CSV_DIR = PROJECT_ROOT / "data" / "01_europe_leagues" / "bundesliga"

BUNDESLIGA_ID = 7

# 德甲球队详细信息
TEAM_DETAILS = {
    'Bayern Munich': {
        'city': 'Munich',
        'city_cn': '慕尼黑',
        'stadium': 'Allianz Arena',
        'stadium_capacity': 75000,
        'name_cn': '拜仁慕尼黑',
        'founded': 1900,
    },
    'Borussia Dortmund': {
        'city': 'Dortmund',
        'city_cn': '多特蒙德',
        'stadium': 'Signal Iduna Park',
        'stadium_capacity': 81365,
        'name_cn': '多特蒙德',
        'founded': 1909,
    },
    'RB Leipzig': {
        'city': 'Leipzig',
        'city_cn': '莱比锡',
        'stadium': 'Red Bull Arena',
        'stadium_capacity': 42959,
        'name_cn': 'RB莱比锡',
        'founded': 2009,
    },
    'Bayer Leverkusen': {
        'city': 'Leverkusen',
        'city_cn': '勒沃库森',
        'stadium': 'BayArena',
        'stadium_capacity': 30210,
        'name_cn': '勒沃库森',
        'founded': 1904,
    },
    'VfB Stuttgart': {
        'city': 'Stuttgart',
        'city_cn': '斯图加特',
        'stadium': 'MHPArena',
        'stadium_capacity': 60449,
        'name_cn': '斯图加特',
        'founded': 1893,
    },
    'Eintracht Frankfurt': {
        'city': 'Frankfurt',
        'city_cn': '法兰克福',
        'stadium': 'Deutsche Bank Park',
        'stadium_capacity': 51500,
        'name_cn': '法兰克福',
        'founded': 1899,
    },
    'VfL Wolfsburg': {
        'city': 'Wolfsburg',
        'city_cn': '沃尔夫斯堡',
        'stadium': 'Volkswagen Arena',
        'stadium_capacity': 30000,
        'name_cn': '沃尔夫斯堡',
        'founded': 1945,
    },
    'Freiburg': {
        'city': 'Freiburg',
        'city_cn': '弗赖堡',
        'stadium': 'Europa-Park Stadion',
        'stadium_capacity': 24000,
        'name_cn': '弗赖堡',
        'founded': 1904,
    },
    'Hoffenheim': {
        'city': 'Sinsheim',
        'city_cn': '辛斯海姆',
        'stadium': 'Rhein-Neckar-Arena',
        'stadium_capacity': 30164,
        'name_cn': '霍芬海姆',
        'founded': 1899,
    },
    'Mainz': {
        'city': 'Mainz',
        'city_cn': '美因茨',
        'stadium': 'MEWA Arena',
        'stadium_capacity': 34034,
        'name_cn': '美因茨',
        'founded': 1905,
    },
    'Borussia M\'gladbach': {
        'city': 'Mönchengladbach',
        'city_cn': '门兴格拉德巴赫',
        'stadium': 'Borussia-Park',
        'stadium_capacity': 54022,
        'name_cn': '门兴',
        'founded': 1900,
    },
    'FC Koln': {
        'city': 'Cologne',
        'city_cn': '科隆',
        'stadium': 'RheinEnergieStadion',
        'stadium_capacity': 50000,
        'name_cn': '科隆',
        'founded': 1948,
    },
    'Union Berlin': {
        'city': 'Berlin',
        'city_cn': '柏林',
        'stadium': 'Stadion An der Alten Försterei',
        'stadium_capacity': 22012,
        'name_cn': '柏林联合',
        'founded': 1966,
    },
    'Hertha': {
        'city': 'Berlin',
        'city_cn': '柏林',
        'stadium': 'Olympiastadion Berlin',
        'stadium_capacity': 74475,
        'name_cn': '柏林赫塔',
        'founded': 1892,
    },
    'Werder Bremen': {
        'city': 'Bremen',
        'city_cn': '不来梅',
        'stadium': 'Weserstadion',
        'stadium_capacity': 42100,
        'name_cn': '不来梅',
        'founded': 1899,
    },
    'Augsburg': {
        'city': 'Augsburg',
        'city_cn': '奥格斯堡',
        'stadium': 'WWK Arena',
        'stadium_capacity': 30355,
        'name_cn': '奥格斯堡',
        'founded': 1907,
    },
    'Bochum': {
        'city': 'Bochum',
        'city_cn': '波鸿',
        'stadium': 'Vonovia Ruhrstadion',
        'stadium_capacity': 27599,
        'name_cn': '波鸿',
        'founded': 1848,
    },
    'Darmstadt': {
        'city': 'Darmstadt',
        'city_cn': '达姆施塔特',
        'stadium': 'Merck-Stadion am Böllenfalltor',
        'stadium_capacity': 17820,
        'name_cn': '达姆施塔特',
        'founded': 1898,
    },
    'Heidenheim': {
        'city': 'Heidenheim',
        'city_cn': '海登海姆',
        'stadium': 'Voith-Arena',
        'stadium_capacity': 15000,
        'name_cn': '海登海姆',
        'founded': 1846,
    },
    'Hamburger SV': {
        'city': 'Hamburg',
        'city_cn': '汉堡',
        'stadium': 'Volksparkstadion',
        'stadium_capacity': 57000,
        'name_cn': '汉堡',
        'founded': 1887,
    },
    'Schalke 04': {
        'city': 'Gelsenkirchen',
        'city_cn': '盖尔森基兴',
        'stadium': 'Veltins-Arena',
        'stadium_capacity': 62371,
        'name_cn': '沙尔克04',
        'founded': 1904,
    },
    'Stuttgart': {
        'city': 'Stuttgart',
        'city_cn': '斯图加特',
        'stadium': 'MHPArena',
        'stadium_capacity': 60449,
        'name_cn': '斯图加特',
        'founded': 1893,
    },
    'M\'gladbach': {
        'city': 'Mönchengladbach',
        'city_cn': '门兴格拉德巴赫',
        'stadium': 'Borussia-Park',
        'stadium_capacity': 54022,
        'name_cn': '门兴',
        'founded': 1900,
    },
    'Koln': {
        'city': 'Cologne',
        'city_cn': '科隆',
        'stadium': 'RheinEnergieStadion',
        'stadium_capacity': 50000,
        'name_cn': '科隆',
        'founded': 1948,
    },
    'Dortmund': {
        'city': 'Dortmund',
        'city_cn': '多特蒙德',
        'stadium': 'Signal Iduna Park',
        'stadium_capacity': 81365,
        'name_cn': '多特蒙德',
        'founded': 1909,
    },
    'Leverkusen': {
        'city': 'Leverkusen',
        'city_cn': '勒沃库森',
        'stadium': 'BayArena',
        'stadium_capacity': 30210,
        'name_cn': '勒沃库森',
        'founded': 1904,
    },
    'Nurnberg': {
        'city': 'Nuremberg',
        'city_cn': '纽伦堡',
        'stadium': 'Max-Morlock-Stadion',
        'stadium_capacity': 50000,
        'name_cn': '纽伦堡',
        'founded': 1900,
    },
    'Hannover': {
        'city': 'Hannover',
        'city_cn': '汉诺威',
        'stadium': 'HDI-Arena',
        'stadium_capacity': 49200,
        'name_cn': '汉诺威96',
        'founded': 1896,
    },
    'Bielefeld': {
        'city': 'Bielefeld',
        'city_cn': '比勒费尔德',
        'stadium': 'SchücoArena',
        'stadium_capacity': 27332,
        'name_cn': '比勒费尔德',
        'founded': 1899,
    },
    'Greuther Furth': {
        'city': 'Fürth',
        'city_cn': '菲尔特',
        'stadium': 'Sportpark Ronhof',
        'stadium_capacity': 18000,
        'name_cn': '格罗伊特菲尔特',
        'founded': 1903,
    },
}


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def update_team_details():
    """更新球队详细信息"""
    print("=" * 60)
    print("更新德甲球队详细信息")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    updated = 0
    for team_name, details in TEAM_DETAILS.items():
        # 查找球队
        cursor.execute('''
            SELECT team_id, name_en FROM teams
            WHERE name_en = ? OR name_en LIKE ? OR name_en LIKE ?
        ''', (team_name, f'%{team_name}%', f'%{team_name.split()[0]}%'))

        row = cursor.fetchone()
        if row:
            team_id = row[0]
            # 检查是否有city列
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
            try:
                print(f"  Updated: {row[1]}")
            except:
                print(f"  Updated: team_id={team_id}")

    conn.commit()
    conn.close()
    print(f"\n共更新 {updated} 支球队")
    return updated


def import_attendance_from_csv():
    """从CSV导入观众人数"""
    print("\n" + "=" * 60)
    print("导入观众人数数据")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    csv_files = sorted(CSV_DIR.glob("bundesliga_*.csv"))
    csv_files = [f for f in csv_files if '_all' not in f.name]

    total_updated = 0

    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    home_team = row.get('HomeTeam', '').strip()
                    away_team = row.get('AwayTeam', '').strip()
                    date_str = row.get('Date', '')

                    if not home_team or not away_team or not date_str:
                        continue

                    attendance = row.get('Attendance', '')
                    referee = row.get('Referee', '').strip()

                    if not attendance and not referee:
                        continue

                    # 解析日期
                    match_date = parse_date(date_str)
                    if not match_date:
                        continue

                    # 查找比赛
                    cursor.execute('''
                        SELECT m.match_id, ht.name_en, at.name_en
                        FROM matches m
                        JOIN teams ht ON m.home_team_id = ht.team_id
                        JOIN teams at ON m.away_team_id = at.team_id
                        WHERE m.match_date = ? AND m.league_id = ?
                    ''', (match_date, BUNDESLIGA_ID))

                    matches = cursor.fetchall()
                    match_id = None
                    for m in matches:
                        if home_team.lower() in m[1].lower() or m[1].lower() in home_team.lower():
                            if away_team.lower() in m[2].lower() or m[2].lower() in away_team.lower():
                                match_id = m[0]
                                break

                    if not match_id:
                        continue

                    # 更新观众人数和裁判
                    try:
                        att_val = int(float(attendance)) if attendance else None
                    except:
                        att_val = None

                    if att_val or referee:
                        if att_val and referee:
                            cursor.execute('''
                                UPDATE matches SET attendance = ?, referee = ?
                                WHERE match_id = ? AND attendance IS NULL
                            ''', (att_val, referee, match_id))
                        elif att_val:
                            cursor.execute('''
                                UPDATE matches SET attendance = ?
                                WHERE match_id = ? AND attendance IS NULL
                            ''', (att_val, match_id))
                        else:
                            cursor.execute('''
                                UPDATE matches SET referee = ?
                                WHERE match_id = ? AND (referee IS NULL OR referee = '')
                            ''', (referee, match_id))

                        if cursor.rowcount > 0:
                            total_updated += 1

        except Exception as e:
            pass

    conn.commit()
    conn.close()
    print(f"  更新 {total_updated} 条记录")
    return total_updated


def parse_date(date_str: str) -> str:
    """解析日期"""
    if not date_str:
        return None
    try:
        if '/' in date_str:
            parts = date_str.split('/')
            day, month = int(parts[0]), int(parts[1])
            year = int(parts[2]) if len(parts) > 2 else None
            if year is not None:
                full_year = 2000 + year if year <= 26 else 1900 + year
                return f"{full_year:04d}-{month:02d}-{day:02d}"
        if '-' in date_str:
            if len(date_str.split('-')[0]) == 2:
                parts = date_str.split('-')
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                full_year = 2000 + year if year <= 26 else 1900 + year
                return f"{full_year:04d}-{month:02d}-{day:02d}"
            return date_str
    except:
        pass
    return None


def show_final_stats():
    """显示最终统计"""
    print("\n" + "=" * 60)
    print("德甲数据补充结果")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (BUNDESLIGA_ID,))
    total = cursor.fetchone()[0]

    fields = [
        ('attendance', '观众人数'),
        ('referee', '裁判'),
        ('match_time', '开球时间'),
        ('odds_home', '赔率'),
    ]

    print(f"\n比赛总数: {total}")
    for field, name in fields:
        cursor.execute(f'''
            SELECT COUNT(*) FROM matches
            WHERE league_id = ? AND {field} IS NOT NULL AND {field} != ''
        ''', (BUNDESLIGA_ID,))
        count = cursor.fetchone()[0]
        pct = count / total * 100
        print(f"  {name}: {count} ({pct:.1f}%)")

    # 球队统计
    cursor.execute('''
        SELECT
            SUM(CASE WHEN stadium IS NOT NULL THEN 1 ELSE 0 END) as has_stadium,
            SUM(CASE WHEN stadium_capacity IS NOT NULL THEN 1 ELSE 0 END) as has_capacity,
            SUM(CASE WHEN name_cn IS NOT NULL AND name_cn != '' THEN 1 ELSE 0 END) as has_cn
        FROM teams
        WHERE team_id IN (
            SELECT DISTINCT home_team_id FROM matches WHERE league_id = ?
            UNION
            SELECT DISTINCT away_team_id FROM matches WHERE league_id = ?
        )
    ''', (BUNDESLIGA_ID, BUNDESLIGA_ID))
    r = cursor.fetchone()

    print(f"\n球队数据:")
    print(f"  有球场: {r[0]}支")
    print(f"  有容量: {r[1]}支")
    print(f"  有中文名: {r[2]}支")

    conn.close()


if __name__ == "__main__":
    # 1. 更新球队详细信息
    update_team_details()

    # 2. 导入观众人数和裁判
    import_attendance_from_csv()

    # 3. 显示最终统计
    show_final_stats()

    print("\n德甲数据补充完成！")
