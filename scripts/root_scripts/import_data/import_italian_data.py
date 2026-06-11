"""
意大利足球数据完整采集

包含:
1. Serie A (意甲) - ID: 35, API ID: 135
2. Serie B (意乙) - ID: 36, API ID: 136
3. Coppa Italia (意大利杯) - ID: 7484, API ID: 137
4. Supercoppa Italiana (意大利超级杯) - ID: 7485, API ID: 138
"""

import sqlite3
import json
import ssl
import urllib.request
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

API_KEY = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"
BASE_URL = "https://apiv3.apifootball.com"

# 联赛配置
LEAGUES = {
    135: ('Serie A', 35),
    136: ('Serie B', 36),
    137: ('Coppa Italia', 7484),
    138: ('Supercoppa Italiana', 7485),
}

# CSV目录
SERIE_A_CSV = PROJECT_ROOT / "data" / "01_europe_leagues" / "serie_a"
SERIE_B_CSV = PROJECT_ROOT / "data" / "01_europe_leagues" / "serie_b"


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_api(action: str, params: dict) -> dict:
    """调用API"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        url = f"{BASE_URL}?action={action}&{param_str}&APIkey={API_KEY}"

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"    API error: {e}")
        return None


def get_or_create_team(conn, team_name: str, country: str = 'Italy') -> int:
    """获取或创建球队"""
    cursor = conn.cursor()
    team_name = team_name.strip()

    try:
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ? OR name_en LIKE ?',
                      (team_name, f'%{team_name}%'))
        row = cursor.fetchone()
        if row:
            return row[0]

        cursor.execute('''
            INSERT INTO teams (name_en, country, created_at, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (team_name, country))
        conn.commit()
        return cursor.lastrowid
    except:
        conn.rollback()
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
        row = cursor.fetchone()
        return row[0] if row else None


def parse_date(date_str: str) -> str:
    """解析日期"""
    if not date_str:
        return None
    try:
        if '-' in date_str and len(date_str.split('-')[0]) == 4:
            return date_str
        if '/' in date_str:
            parts = date_str.split('/')
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{year:04d}-{month:02d}-{day:02d}"
    except:
        pass
    return None


def import_serie_a_csv():
    """导入意甲CSV数据"""
    print("\n" + "=" * 60)
    print("Importing Serie A CSV data...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    csv_files = sorted(SERIE_A_CSV.glob("serie_a_*.csv"))
    csv_files = [f for f in csv_files if '_all' not in f.name]

    total_imported = 0

    for csv_file in csv_files:
        season = csv_file.stem.replace('serie_a_', '')

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if len(rows) == 0:
                continue

            imported = 0
            for row in rows:
                home_team = row.get('HomeTeam', '').strip()
                away_team = row.get('AwayTeam', '').strip()
                date_str = row.get('Date', '')

                if not home_team or not away_team or not date_str:
                    continue

                match_date = parse_date(date_str)
                if not match_date:
                    continue

                home_team_id = get_or_create_team(conn, home_team)
                away_team_id = get_or_create_team(conn, away_team)

                if not home_team_id or not away_team_id:
                    continue

                # 解析数据
                try:
                    home_goals = int(row.get('FTHG', 0)) if row.get('FTHG') else None
                    away_goals = int(row.get('FTAG', 0)) if row.get('FTAG') else None
                    home_goals_ht = int(row.get('HTHG', 0)) if row.get('HTHG') else None
                    away_goals_ht = int(row.get('HTAG', 0)) if row.get('HTAG') else None
                    home_shots = int(row.get('HS', 0)) if row.get('HS') else None
                    away_shots = int(row.get('AS', 0)) if row.get('AS') else None
                    home_shots_on = int(row.get('HST', 0)) if row.get('HST') else None
                    away_shots_on = int(row.get('AST', 0)) if row.get('AST') else None
                    home_corners = int(row.get('HC', 0)) if row.get('HC') else None
                    away_corners = int(row.get('AC', 0)) if row.get('AC') else None
                    home_fouls = int(row.get('HF', 0)) if row.get('HF') else None
                    away_fouls = int(row.get('AF', 0)) if row.get('AF') else None
                    home_yellows = int(row.get('HY', 0)) if row.get('HY') else None
                    away_yellows = int(row.get('AY', 0)) if row.get('AY') else None
                    home_reds = int(row.get('HR', 0)) if row.get('HR') else None
                    away_reds = int(row.get('AR', 0)) if row.get('AR') else None
                    referee = row.get('Referee', '').strip() if row.get('Referee') else None
                    match_time = row.get('Time', '') if row.get('Time') else None
                    odds_home = float(row.get('B365H', 0)) if row.get('B365H') else None
                    odds_draw = float(row.get('B365D', 0)) if row.get('B365D') else None
                    odds_away = float(row.get('B365A', 0)) if row.get('B365A') else None
                except:
                    continue

                # 检查是否已存在
                cursor.execute('''
                    SELECT rowid FROM matches
                    WHERE match_date = ? AND home_team_id = ? AND away_team_id = ? AND league_id = 35
                ''', (match_date, home_team_id, away_team_id))

                if cursor.fetchone():
                    continue

                # 计算xG
                home_xg = None
                away_xg = None
                if home_shots_on and home_shots:
                    home_xg = round(home_shots_on * 0.28 + (home_shots - home_shots_on) * 0.06, 2)
                elif home_goals is not None:
                    home_xg = home_goals
                if away_shots_on and away_shots:
                    away_xg = round(away_shots_on * 0.28 + (away_shots - away_shots_on) * 0.06, 2)
                elif away_goals is not None:
                    away_xg = away_goals

                cursor.execute('''
                    INSERT INTO matches (
                        league_id, match_date, match_time,
                        home_team_id, away_team_id,
                        home_goals, away_goals, home_goals_ht, away_goals_ht,
                        home_shots, away_shots, home_shots_target, away_shots_target,
                        home_corners, away_corners, home_fouls, away_fouls,
                        home_yellow, away_yellow, home_red, away_red,
                        referee, odds_home, odds_draw, odds_away,
                        home_xg, away_xg,
                        source, created_at, updated_at
                    ) VALUES (35, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'csv_import', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (match_date, match_time, home_team_id, away_team_id,
                      home_goals, away_goals, home_goals_ht, away_goals_ht,
                      home_shots, away_shots, home_shots_on, away_shots_on,
                      home_corners, away_corners, home_fouls, away_fouls,
                      home_yellows, away_yellows, home_reds, away_reds,
                      referee, odds_home, odds_draw, odds_away, home_xg, away_xg))

                imported += 1

            conn.commit()
            if imported > 0:
                print(f"  {season}: {imported} matches")
                total_imported += imported

        except Exception as e:
            print(f"  {season}: Error - {e}")

    conn.close()
    print(f"\nTotal imported: {total_imported}")
    return total_imported


def import_serie_b_csv():
    """导入意乙CSV数据"""
    print("\n" + "=" * 60)
    print("Importing Serie B CSV data...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    csv_files = sorted(SERIE_B_CSV.glob("serie_b_*.csv"))
    csv_files = [f for f in csv_files if '_all' not in f.name]

    total_imported = 0

    for csv_file in csv_files:
        season = csv_file.stem.replace('serie_b_', '')

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if len(rows) == 0:
                continue

            imported = 0
            for row in rows:
                home_team = row.get('HomeTeam', '').strip()
                away_team = row.get('AwayTeam', '').strip()
                date_str = row.get('Date', '')

                if not home_team or not away_team or not date_str:
                    continue

                match_date = parse_date(date_str)
                if not match_date:
                    continue

                home_team_id = get_or_create_team(conn, home_team)
                away_team_id = get_or_create_team(conn, away_team)

                if not home_team_id or not away_team_id:
                    continue

                try:
                    home_goals = int(row.get('FTHG', 0)) if row.get('FTHG') else None
                    away_goals = int(row.get('FTAG', 0)) if row.get('FTAG') else None
                    home_goals_ht = int(row.get('HTHG', 0)) if row.get('HTHG') else None
                    away_goals_ht = int(row.get('HTAG', 0)) if row.get('HTAG') else None
                    home_shots = int(row.get('HS', 0)) if row.get('HS') else None
                    away_shots = int(row.get('AS', 0)) if row.get('AS') else None
                    home_shots_on = int(row.get('HST', 0)) if row.get('HST') else None
                    away_shots_on = int(row.get('AST', 0)) if row.get('AST') else None
                    match_time = row.get('Time', '') if row.get('Time') else None
                except:
                    continue

                cursor.execute('''
                    SELECT rowid FROM matches
                    WHERE match_date = ? AND home_team_id = ? AND away_team_id = ? AND league_id = 36
                ''', (match_date, home_team_id, away_team_id))

                if cursor.fetchone():
                    continue

                # 计算xG
                home_xg = home_goals
                away_xg = away_goals

                cursor.execute('''
                    INSERT INTO matches (
                        league_id, match_date, match_time,
                        home_team_id, away_team_id,
                        home_goals, away_goals, home_goals_ht, away_goals_ht,
                        home_shots, away_shots, home_shots_target, away_shots_target,
                        home_xg, away_xg,
                        source, created_at, updated_at
                    ) VALUES (36, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'csv_import', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (match_date, match_time, home_team_id, away_team_id,
                      home_goals, away_goals, home_goals_ht, away_goals_ht,
                      home_shots, away_shots, home_shots_on, away_shots_on,
                      home_xg, away_xg))

                imported += 1

            conn.commit()
            if imported > 0:
                print(f"  {season}: {imported} matches")
                total_imported += imported

        except Exception as e:
            print(f"  {season}: Error - {e}")

    conn.close()
    print(f"\nTotal imported: {total_imported}")
    return total_imported


def update_from_api(api_id: int, name: str, db_id: int, from_date: str, to_date: str):
    """从API更新数据"""
    print(f"\nUpdating {name} from API ({from_date} ~ {to_date})...")

    conn = get_db()
    cursor = conn.cursor()

    fixtures = fetch_api("get_events", {
        "league_id": api_id,
        "from": from_date,
        "to": to_date
    })

    if not fixtures or not isinstance(fixtures, list):
        print(f"  No data received")
        conn.close()
        return 0

    print(f"  Got {len(fixtures)} matches")

    added = 0
    for fixture in fixtures:
        match_date = fixture.get('match_date', '')
        home_team = fixture.get('match_hometeam_name', '')
        away_team = fixture.get('match_awayteam_name', '')
        home_goals = fixture.get('match_hometeam_score')
        away_goals = fixture.get('match_awayteam_score')
        match_time = fixture.get('match_time', '')

        if not match_date or not home_team or not away_team:
            continue

        home_team_id = get_or_create_team(conn, home_team)
        away_team_id = get_or_create_team(conn, away_team)

        if not home_team_id or not away_team_id:
            continue

        cursor.execute('''
            SELECT rowid FROM matches
            WHERE match_date = ? AND home_team_id = ? AND away_team_id = ? AND league_id = ?
        ''', (match_date, home_team_id, away_team_id, db_id))

        try:
            hg = int(home_goals) if home_goals else None
            ag = int(away_goals) if away_goals else None
        except:
            hg = None
            ag = None

        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO matches (
                    league_id, match_date, match_time,
                    home_team_id, away_team_id,
                    home_goals, away_goals,
                    home_xg, away_xg,
                    source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'api_import', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (db_id, match_date, match_time, home_team_id, away_team_id,
                  hg, ag, hg, ag))
            added += 1

    conn.commit()
    conn.close()
    print(f"  Added {added} matches")
    return added


def show_stats():
    """显示统计"""
    print("\n" + "=" * 60)
    print("Italian Football Data Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    for db_id, name in [(35, 'Serie A'), (36, 'Serie B'), (7484, 'Coppa Italia'), (7485, 'Supercoppa Italiana')]:
        cursor.execute('SELECT COUNT(*), MIN(match_date), MAX(match_date) FROM matches WHERE league_id = ?', (db_id,))
        r = cursor.fetchone()
        print(f"\n{name}:")
        print(f"  Matches: {r[0]}")
        print(f"  Range: {r[1]} ~ {r[2]}")

        # 按赛季统计
        cursor.execute('''
            SELECT
                CASE
                    WHEN match_date BETWEEN '2020-08-01' AND '2021-07-31' THEN '2020-21'
                    WHEN match_date BETWEEN '2021-08-01' AND '2022-07-31' THEN '2021-22'
                    WHEN match_date BETWEEN '2022-08-01' AND '2023-07-31' THEN '2022-23'
                    WHEN match_date BETWEEN '2023-08-01' AND '2024-07-31' THEN '2023-24'
                    WHEN match_date BETWEEN '2024-08-01' AND '2025-07-31' THEN '2024-25'
                    WHEN match_date >= '2025-08-01' THEN '2025-26'
                END as season,
                COUNT(*) as matches
            FROM matches WHERE league_id = ? AND match_date >= '2020-08-01'
            GROUP BY season ORDER BY season
        ''', (db_id,))
        for s in cursor.fetchall():
            if s[0]:
                print(f"    {s[0]}: {s[1]}")

    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Italian Football Data Collection")
    print("=" * 60)

    # 1. 导入意甲CSV
    import_serie_a_csv()

    # 2. 导入意乙CSV
    import_serie_b_csv()

    # 3. 从API更新最新数据
    for api_id, (name, db_id) in LEAGUES.items():
        update_from_api(api_id, name, db_id, "2024-08-01", "2026-12-31")

    # 4. 显示统计
    show_stats()

    print("\nDone!")