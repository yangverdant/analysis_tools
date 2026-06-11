"""
比利时足球数据完整采集

包含:
1. Jupiler Pro League (比甲) - ID: 26, API ID: 144
2. Challenger Pro League (比乙) - ID: 27, API ID: 145
3. Belgian Cup (比利时杯) - ID: 7489, API ID: 143
4. Belgian Super Cup (比利时超级杯) - ID: 7490, API ID: 146
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
    144: ('Jupiler Pro League', 26),
    145: ('Challenger Pro League', 27),
    143: ('Belgian Cup', 7489),
    146: ('Belgian Super Cup', 7490),
}

# CSV目录
JUPILER_CSV = PROJECT_ROOT / "data" / "01_europe_leagues" / "jupiler_league"


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


def get_or_create_team(conn, team_name: str, country: str = 'Belgium') -> int:
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
        # Extract season from filename
        season = csv_file.stem.replace('jupiler_league_', '')

        # Only import 2020+ data
        try:
            year = int(season.split('-')[0])
            if year < 2020:
                continue
        except:
            continue

        # Check file size
        if csv_file.stat().st_size < 500:
            continue

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

                # Calculate xG
                home_xg = None
                away_xg = None
                if home_shots and home_shots_on:
                    home_xg = home_shots_on * 0.28 + (home_shots - home_shots_on) * 0.06
                if away_shots and away_shots_on:
                    away_xg = away_shots_on * 0.28 + (away_shots - away_shots_on) * 0.06

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
    print("Belgian Football Data Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    for db_id, name in [(26, 'Jupiler Pro League'), (27, 'Challenger Pro League'),
                        (7489, 'Belgian Cup'), (7490, 'Belgian Super Cup')]:
        cursor.execute('SELECT COUNT(*), MIN(match_date), MAX(match_date) FROM matches WHERE league_id = ?', (db_id,))
        r = cursor.fetchone()
        print(f"\n{name}:")
        print(f"  Matches: {r[0]}")
        print(f"  Range: {r[1]} ~ {r[2]}")

    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Belgian Football Data Collection")
    print("=" * 60)

    # 1. Import Jupiler CSV (2020-2026)
    import_csv_league(JUPILER_CSV, 26, "Jupiler Pro League")

    # 2. Update from API (2020-2026)
    for api_id, (name, db_id) in LEAGUES.items():
        update_from_api(api_id, name, db_id, "2020-08-01", "2026-12-31")

    # 3. Show statistics
    show_stats()

    print("\nDone!")