"""
补充德乙联赛详细数据:
1. 球队城市、球场、容量
2. 比赛开球时间
3. 赔率数据 (Bet365等)
"""

import sqlite3
import csv
import os
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CSV_DIR = PROJECT_ROOT / "data" / "01_europe_leagues" / "bundesliga_2"

BUNDESLIGA_2_ID = 8

# 德乙球队球场信息 (手动整理)
TEAM_VENUES = {
    'Hamburger SV': {'city': 'Hamburg', 'stadium': 'Volksparkstadion', 'capacity': 57000},
    'Hertha': {'city': 'Berlin', 'stadium': 'Olympiastadion Berlin', 'capacity': 74475},
    'Fortuna Dusseldorf': {'city': 'Düsseldorf', 'stadium': 'Merkur Spiel-Arena', 'capacity': 54600},
    'Hannover': {'city': 'Hannover', 'stadium': 'HDI-Arena', 'capacity': 49200},
    'Greuther Furth': {'city': 'Fürth', 'stadium': 'Sportpark Ronhof', 'capacity': 18000},
    'Paderborn': {'city': 'Paderborn', 'stadium': 'Benteler-Arena', 'capacity': 15000},
    'Karlsruher': {'city': 'Karlsruhe', 'stadium': 'Wildparkstadion', 'capacity': 32303},
    'Holstein Kiel': {'city': 'Kiel', 'stadium': 'Holstein-Stadion', 'capacity': 15034},
    'Darmstadt': {'city': 'Darmstadt', 'stadium': 'Merck-Stadion am Böllenfalltor', 'capacity': 17820},
    'Elversberg': {'city': 'Spiesen-Elversberg', 'stadium': 'Waldstadion an der Kaiserlinde', 'capacity': 10000},
    'Nurnberg': {'city': 'Nürnberg', 'stadium': 'Max-Morlock-Stadion', 'capacity': 50000},
    'Magdeburg': {'city': 'Magdeburg', 'stadium': 'MDCC-Arena', 'capacity': 27062},
    'Duisburg': {'city': 'Duisburg', 'stadium': 'MSV-Arena', 'capacity': 31512},
    'Dynamo Dresden': {'city': 'Dresden', 'stadium': 'Rudolf-Harbig-Stadion', 'capacity': 32194},
    'Schalke 04': {'city': 'Gelsenkirchen', 'stadium': 'Veltins-Arena', 'capacity': 62371},
    'Bremen': {'city': 'Bremen', 'stadium': 'Weserstadion', 'capacity': 42100},
    'St Pauli': {'city': 'Hamburg', 'stadium': 'Millerntor-Stadion', 'capacity': 29546},
    'Stuttgart': {'city': 'Stuttgart', 'stadium': 'MHPArena', 'capacity': 60449},
    'M\'gladbach': {'city': 'Mönchengladbach', 'stadium': 'Borussia-Park', 'capacity': 54022},
    'Koln': {'city': 'Köln', 'stadium': 'RheinEnergieStadion', 'capacity': 50000},
    'Union Berlin': {'city': 'Berlin', 'stadium': 'Stadion An der Alten Försterei', 'capacity': 22012},
    'Freiburg': {'city': 'Freiburg', 'stadium': 'Europa-Park Stadion', 'capacity': 24000},
    'Mainz': {'city': 'Mainz', 'stadium': 'MEWA Arena', 'capacity': 34034},
    'Ein Frankfurt': {'city': 'Frankfurt', 'stadium': 'Deutsche Bank Park', 'capacity': 51500},
    'Bochum': {'city': 'Bochum', 'stadium': 'Vonovia Ruhrstadion', 'capacity': 27599},
    'Heidenheim': {'city': 'Heidenheim', 'stadium': 'Voith-Arena', 'capacity': 15000},
    'Braunschweig': {'city': 'Braunschweig', 'stadium': 'Eintracht-Stadion', 'capacity': 24406},
    'Kaiserslautern': {'city': 'Kaiserslautern', 'stadium': 'Fritz-Walter-Stadion', 'capacity': 49350},
    'Hansa Rostock': {'city': 'Rostock', 'stadium': 'Ostseestadion', 'capacity': 29200},
    'Erzgebirge Aue': {'city': 'Aue', 'stadium': 'Erzgebirgsstadion', 'capacity': 16656},
    'Sandhausen': {'city': 'Sandhausen', 'stadium': 'BWT-Stadion am Hardtwald', 'capacity': 12300},
    'Ingolstadt': {'city': 'Ingolstadt', 'stadium': 'Audi Sportpark', 'capacity': 15280},
    'Regensburg': {'city': 'Regensburg', 'stadium': 'Continental Arena', 'capacity': 15210},
    'Osnabruck': {'city': 'Osnabrück', 'stadium': 'Bremer Brücke', 'capacity': 16410},
    'Wehen': {'city': 'Wiesbaden', 'stadium': 'BRITA-Arena', 'capacity': 13500},
    'Aachen': {'city': 'Aachen', 'stadium': 'Neues Tivoli', 'capacity': 32273},
    'Bielefeld': {'city': 'Bielefeld', 'stadium': 'SchücoArena', 'capacity': 27332},
    'Cottbus': {'city': 'Cottbus', 'stadium': 'Stadion der Freundschaft', 'capacity': 22528},
    'Ahlen': {'city': 'Ahlen', 'stadium': 'Wersestadion', 'capacity': 12500},
    'Burghausen': {'city': 'Burghausen', 'stadium': 'Wacker-Arena', 'capacity': 12110},
    'Ein Trier': {'city': 'Trier', 'stadium': 'Moselstadion', 'capacity': 10600},
    'Mannheim': {'city': 'Mannheim', 'stadium': 'Carl-Benz-Stadion', 'capacity': 27000},
    'Oberhausen': {'city': 'Oberhausen', 'stadium': 'Niederrheinstadion', 'capacity': 21050},
    'Saarbrucken': {'city': 'Saarbrücken', 'stadium': 'Ludwigsparkstadion', 'capacity': 17885},
    'Unterhaching': {'city': 'Unterhaching', 'stadium': 'Sportpark Unterhaching', 'capacity': 15000},
    'Lubeck': {'city': 'Lübeck', 'stadium': 'Holstein-Stadion', 'capacity': 17900},
    'Essen': {'city': 'Essen', 'stadium': 'Stadion Essen', 'capacity': 20000},
    'Reutlingen': {'city': 'Reutlingen', 'stadium': 'Stadion an der Kreuzeiche', 'capacity': 15228},
    'Babelsberg': {'city': 'Potsdam', 'stadium': 'Karl-Liebknecht-Stadion', 'capacity': 10499},
    'Schweinfurt': {'city': 'Schweinfurt', 'stadium': 'Willy-Sachs-Stadion', 'capacity': 20000},
    'Preußen Münster': {'city': 'Münster', 'stadium': 'Preußen-Stadion', 'capacity': 15050},
    'Preußen Munster': {'city': 'Münster', 'stadium': 'Preußen-Stadion', 'capacity': 15050},
    'Jahn Regensburg': {'city': 'Regensburg', 'stadium': 'Continental Arena', 'capacity': 15210},
    'Grossaspach': {'city': 'Aspach', 'stadium': 'Mechatronik Arena', 'capacity': 10000},
    'Zwickau': {'city': 'Zwickau', 'stadium': 'Stadion Zwickau', 'capacity': 10029},
    'Viktoria Koln': {'city': 'Köln', 'stadium': 'Sportpark Höhenberg', 'capacity': 6271},
    'Munchen 1860': {'city': 'München', 'stadium': 'Städtisches Stadion', 'capacity': 15000},
    'Halle': {'city': 'Halle', 'stadium': 'Leuna-Chemie-Stadion', 'capacity': 15057},
    'Meppen': {'city': 'Meppen', 'stadium': 'Hänsch-Arena', 'capacity': 13208},
    'Chemnitz': {'city': 'Chemnitz', 'stadium': 'community4you ARENA', 'capacity': 15714},
    'Carl Zeiss Jena': {'city': 'Jena', 'stadium': 'Ernst-Abbe-Sportfeld', 'capacity': 12372},
    'Rosenheim': {'city': 'Rosenheim', 'stadium': 'Jahnstadion', 'capacity': 8000},
    'Wattenscheid': {'city': 'Bochum', 'stadium': 'Lohrheidestadion', 'capacity': 11000},
    'Stuttgarter K': {'city': 'Stuttgart', 'stadium': 'Gazi-Stadion auf der Waldau', 'capacity': 11718},
    'Augsburg': {'city': 'Augsburg', 'stadium': 'WWK Arena', 'capacity': 30355},
}


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def update_team_venues(conn) -> int:
    """更新球队球场信息"""
    cursor = conn.cursor()
    updated = 0

    for team_name, venue_info in TEAM_VENUES.items():
        # 尝试匹配球队
        cursor.execute('''
            SELECT team_id, name_en FROM teams
            WHERE name_en = ? OR name_en LIKE ? OR name_cn = ?
        ''', (team_name, f'%{team_name.split()[0]}%', team_name))

        row = cursor.fetchone()
        if row:
            cursor.execute('''
                UPDATE teams SET
                    stadium = ?,
                    stadium_capacity = ?
                WHERE team_id = ?
            ''', (venue_info['stadium'], venue_info['capacity'], row[0]))
            updated += 1
            # print(f"   更新: {row[1]} -> {venue_info['stadium']} ({venue_info['capacity']})")

    conn.commit()
    return updated


def import_match_details(csv_path: Path, conn) -> dict:
    """从CSV导入比赛详细数据（时间、赔率）"""
    result = {
        'file': csv_path.name,
        'total': 0,
        'time_updated': 0,
        'odds_updated': 0,
        'errors': []
    }

    cursor = conn.cursor()

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                result['total'] += 1

                try:
                    home_team = row.get('HomeTeam', '').strip()
                    away_team = row.get('AwayTeam', '').strip()
                    date_str = row.get('Date', '')
                    time_str = row.get('Time', '')

                    if not home_team or not away_team or not date_str:
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
                        WHERE m.match_date = ?
                        AND (ht.name_en = ? OR ht.name_en LIKE ?)
                        AND (at.name_en = ? OR at.name_en LIKE ?)
                        AND m.league_id = ?
                    ''', (match_date, home_team, f'%{home_team}%', away_team, f'%{away_team}%', BUNDESLIGA_2_ID))

                    match_row = cursor.fetchone()
                    if not match_row:
                        continue

                    match_id = match_row[0]

                    # 更新时间
                    if time_str:
                        cursor.execute('''
                            UPDATE matches SET match_time = ? WHERE match_id = ? AND (match_time IS NULL OR match_time = '')
                        ''', (time_str, match_id))
                        if cursor.rowcount > 0:
                            result['time_updated'] += 1

                    # 更新赔率
                    b365h = row.get('B365H')
                    b365d = row.get('B365D')
                    b365a = row.get('B365A')

                    if b365h and b365d and b365a:
                        try:
                            odds_h = float(b365h)
                            odds_d = float(b365d)
                            odds_a = float(b365a)

                            cursor.execute('''
                                UPDATE matches SET
                                    odds_home = ?,
                                    odds_draw = ?,
                                    odds_away = ?
                                WHERE match_id = ?
                            ''', (odds_h, odds_d, odds_a, match_id))
                            result['odds_updated'] += 1
                        except:
                            pass

                except Exception as e:
                    result['errors'].append(str(e))

        conn.commit()

    except Exception as e:
        result['errors'].append(f"File error: {e}")

    return result


def parse_date(date_str: str) -> str:
    """解析日期"""
    if not date_str:
        return None

    try:
        # 格式1: DD/MM/YY
        if '/' in date_str:
            parts = date_str.split('/')
            day, month = int(parts[0]), int(parts[1])
            year = int(parts[2]) if len(parts) > 2 else None
            if year is not None:
                if year >= 0 and year <= 26:
                    full_year = 2000 + year
                else:
                    full_year = 1900 + year
                return f"{full_year:04d}-{month:02d}-{day:02d}"

        # 格式2: YY-MM-DD
        if '-' in date_str and len(date_str.split('-')[0]) == 2:
            parts = date_str.split('-')
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            if year >= 0 and year <= 26:
                full_year = 2000 + year
            else:
                full_year = 1900 + year
            return f"{full_year:04d}-{month:02d}-{day:02d}"

        # 格式3: YYYY-MM-DD
        if '-' in date_str and len(date_str.split('-')[0]) == 4:
            return date_str

    except:
        pass

    return None


def main():
    """主函数"""
    print("=" * 60)
    print("补充德乙联赛详细数据")
    print("=" * 60)

    conn = get_db()

    # 1. 更新球队球场信息
    print("\n1. 更新球队球场信息...")
    updated = update_team_venues(conn)
    print(f"   共更新 {updated} 支球队的球场信息")

    # 2. 导入比赛时间和赔率
    print("\n2. 导入比赛时间和赔率...")
    csv_files = sorted(CSV_DIR.glob("bundesliga_2_*.csv"))
    csv_files = [f for f in csv_files if '_all' not in f.name]

    total_result = {
        'total': 0,
        'time_updated': 0,
        'odds_updated': 0
    }

    for csv_file in csv_files:
        result = import_match_details(csv_file, conn)
        total_result['total'] += result['total']
        total_result['time_updated'] += result['time_updated']
        total_result['odds_updated'] += result['odds_updated']

    print(f"   总记录: {total_result['total']}")
    print(f"   更新时间: {total_result['time_updated']}")
    print(f"   更新赔率: {total_result['odds_updated']}")

    # 3. 统计结果
    print("\n" + "=" * 60)
    print("数据统计")
    print("=" * 60)

    cursor = conn.cursor()

    # 球场信息
    cursor.execute('''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN stadium IS NOT NULL THEN 1 ELSE 0 END) as has_stadium,
               SUM(CASE WHEN stadium_capacity IS NOT NULL THEN 1 ELSE 0 END) as has_capacity
        FROM teams
        WHERE team_id IN (SELECT DISTINCT home_team_id FROM matches WHERE league_id = 8)
    ''')
    r = cursor.fetchone()
    print(f"球队: {r[0]}支 | 有球场: {r[1]} | 有容量: {r[2]}")

    # 比赛时间
    cursor.execute('''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END) as has_time
        FROM matches WHERE league_id = 8
    ''')
    r = cursor.fetchone()
    print(f"比赛: {r[0]}场 | 有时间: {r[1]} | 覆盖率: {r[1]/r[0]*100:.1f}%")

    # 赔率数据
    cursor.execute('''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN odds_home IS NOT NULL THEN 1 ELSE 0 END) as has_odds
        FROM matches WHERE league_id = 8
    ''')
    r = cursor.fetchone()
    print(f"赔率: {r[0]}场 | 有赔率: {r[1]} | 覆盖率: {r[1]/r[0]*100:.1f}%")

    # 示例比赛（含赔率）
    print("\n示例比赛（含赔率）:")
    cursor.execute('''
        SELECT m.match_date, m.match_time, ht.name_en, at.name_en,
               m.home_goals, m.away_goals, m.odds_home, m.odds_draw, m.odds_away
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        WHERE m.league_id = 8 AND m.odds_home IS NOT NULL
        ORDER BY m.match_date DESC
        LIMIT 5
    ''')
    for r in cursor.fetchall():
        odds = f"赔率: {r[6]}/{r[7]}/{r[8]}" if r[6] else ""
        time = f"{r[1]}" if r[1] else "--:--"
        print(f"   {r[0]} {time} | {r[2]} {r[4]}-{r[5]} {r[3]} | {odds}")

    conn.close()
    print("\n补充完成！")


if __name__ == "__main__":
    main()
