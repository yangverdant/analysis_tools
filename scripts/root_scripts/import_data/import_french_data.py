"""
法国足球数据完整采集

包含:
1. Ligue 1 (法甲) - ID: 24, API ID: 61
2. Ligue 2 (法乙) - ID: 25, API ID: 62
3. Coupe de France (法国杯) - ID: 7486, API ID: 60
4. Trophee des Champions (法国超级杯) - ID: 7488, API ID: 63
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
    61: ('Ligue 1', 24),
    62: ('Ligue 2', 25),
    60: ('Coupe de France', 7486),
    63: ('Trophee des Champions', 7488),
}

# CSV目录
LIGUE_1_CSV = PROJECT_ROOT / "data" / "01_europe_leagues" / "ligue_1"
LIGUE_2_CSV = PROJECT_ROOT / "data" / "01_europe_leagues" / "ligue_2"


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


def get_or_create_team(conn, team_name: str, country: str = 'France') -> int:
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


def import_csv_league(csv_dir: Path, league_id: int, league_name: str):
    """导入CSV联赛数据"""
    print(f"\nImporting {league_name} CSV...")

    conn = get_db()
    cursor = conn.cursor()

    csv_files = sorted(csv_dir.glob("*.csv"))
    csv_files = [f for f in csv_files if '_all' not in f.name]

    total_imported = 0

    for csv_file in csv_files:
        season = csv_file.stem.replace(league_name.lower().replace(' ', '_') + '_', '').replace('ligue_1_', '').replace('ligue_2_', '')

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
                    WHERE match_date = ? AND home_team_id = ? AND away_team_id = ? AND league_id = ?
                ''', (match_date, home_team_id, away_team_id, league_id))

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
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'csv_import', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (league_id, match_date, match_time, home_team_id, away_team_id,
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
    print(f"Total imported: {total_imported}")
    return total_imported


def update_from_api(api_id: int, name: str, db_id: int, from_date: str, to_date: str):
    """从API更新数据"""
    print(f"\nUpdating {name} from API...")

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
    print("French Football Data Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    for db_id, name in [(24, 'Ligue 1'), (25, 'Ligue 2'), (7486, 'Coupe de France'), (7488, 'Trophee des Champions')]:
        cursor.execute('SELECT COUNT(*), MIN(match_date), MAX(match_date) FROM matches WHERE league_id = ?', (db_id,))
        r = cursor.fetchone()
        print(f"\n{name}:")
        print(f"  Matches: {r[0]}")
        print(f"  Range: {r[1]} ~ {r[2]}")

    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("French Football Data Collection")
    print("=" * 60)

    # 1. 导入法甲CSV
    import_csv_league(LIGUE_1_CSV, 24, "Ligue 1")

    # 2. 导入法乙CSV
    import_csv_league(LIGUE_2_CSV, 25, "Ligue 2")

    # 3. 从API更新最新数据 (2020-2026)
    for api_id, (name, db_id) in LEAGUES.items():
        update_from_api(api_id, name, db_id, "2020-08-01", "2026-12-31")

    # 4. 显示统计
    show_stats()

    print("\nDone!")