"""
导入德丙联赛 (3. Liga) CSV数据

数据源: football-data.co.uk
覆盖赛季: 2014-2015 ~ 2025-2026
"""

import sqlite3
import csv
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CSV_DIR = PROJECT_ROOT / "data" / "01_europe_leagues" / "bundesliga_3"

# 德丙联赛ID
BUNDESLIGA3_ID = 7402


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def parse_date(date_str: str) -> str:
    """解析日期格式"""
    if not date_str:
        return None
    try:
        # YYYY-MM-DD format
        if '-' in date_str and len(date_str.split('-')[0]) == 4:
            return date_str
        # DD/MM/YYYY format
        if '/' in date_str:
            parts = date_str.split('/')
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{year:04d}-{month:02d}-{day:02d}"
        # YY-MM-DD format
        if '-' in date_str and len(date_str.split('-')[0]) == 2:
            parts = date_str.split('-')
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            full_year = 2000 + year if year <= 26 else 1900 + year
            return f"{full_year:04d}-{month:02d}-{day:02d}"
    except:
        pass
    return None


def get_or_create_team(conn, team_name: str) -> int:
    """获取或创建球队"""
    cursor = conn.cursor()

    # 清理球队名称
    team_name = team_name.strip()

    try:
        # 尝试查找球队
        cursor.execute('''
            SELECT team_id FROM teams
            WHERE name_en = ? OR name_en LIKE ?
        ''', (team_name, f'%{team_name}%'))
        row = cursor.fetchone()
        if row:
            return row[0]

        # 创建新球队
        cursor.execute('''
            INSERT INTO teams (name_en, country, created_at, updated_at)
            VALUES (?, 'Germany', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (team_name,))
        conn.commit()
        return cursor.lastrowid
    except:
        conn.rollback()
        # 再次尝试查找
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
        row = cursor.fetchone()
        return row[0] if row else None


def import_csv_file(csv_file: Path) -> int:
    """导入单个CSV文件"""
    season = csv_file.stem.replace('bundesliga_3_', '')

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if len(rows) == 0:
            print(f"  {season}: empty file")
            return 0

        conn = get_db()
        cursor = conn.cursor()

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

            # 获取球队ID
            home_team_id = get_or_create_team(conn, home_team)
            away_team_id = get_or_create_team(conn, away_team)

            if not home_team_id or not away_team_id:
                continue

            # 解析数据
            home_goals = int(row.get('FTHG', 0)) if row.get('FTHG') else None
            away_goals = int(row.get('FTAG', 0)) if row.get('FTAG') else None
            home_goals_ht = int(row.get('HTHG', 0)) if row.get('HTHG') else None
            away_goals_ht = int(row.get('HTAG', 0)) if row.get('HTAG') else None

            match_time = row.get('Time', '') if row.get('Time') else None

            # 射门等统计
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

            # 赔率
            try:
                odds_home = float(row.get('B365H', 0)) if row.get('B365H') else None
                odds_draw = float(row.get('B365D', 0)) if row.get('B365D') else None
                odds_away = float(row.get('B365A', 0)) if row.get('B365A') else None
            except:
                odds_home = None
                odds_draw = None
                odds_away = None

            # 检查是否已存在
            cursor.execute('''
                SELECT match_id FROM matches
                WHERE match_date = ? AND home_team_id = ? AND away_team_id = ? AND league_id = ?
            ''', (match_date, home_team_id, away_team_id, BUNDESLIGA3_ID))

            if cursor.fetchone():
                continue

            # 插入比赛
            cursor.execute('''
                INSERT INTO matches (
                    league_id, match_date, match_time,
                    home_team_id, away_team_id,
                    home_goals, away_goals, home_goals_ht, away_goals_ht,
                    home_shots, away_shots, home_shots_on, away_shots_on,
                    home_corners, away_corners,
                    home_fouls, away_fouls,
                    home_yellows, away_yellows, home_reds, away_reds,
                    referee,
                    odds_home, odds_draw, odds_away,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (
                BUNDESLIGA3_ID, match_date, match_time,
                home_team_id, away_team_id,
                home_goals, away_goals, home_goals_ht, away_goals_ht,
                home_shots, away_shots, home_shots_on, away_shots_on,
                home_corners, away_corners,
                home_fouls, away_fouls,
                home_yellows, away_yellows, home_reds, away_reds,
                referee,
                odds_home, odds_draw, odds_away
            ))

            imported += 1

        conn.commit()
        conn.close()
        print(f"  {season}: {imported} matches imported")
        return imported

    except Exception as e:
        print(f"  Error: {e}")
        return 0


def import_all_csvs():
    """导入所有CSV文件"""
    print("=" * 60)
    print("Importing 3. Liga CSV data...")
    print("=" * 60)

    csv_files = sorted(CSV_DIR.glob("bundesliga_3_*.csv"))
    csv_files = [f for f in csv_files if '_all' not in f.name]

    total = 0
    for csv_file in csv_files:
        count = import_csv_file(csv_file)
        total += count

    print(f"\nTotal imported: {total} matches")
    return total


def show_stats():
    """显示导入统计"""
    print("\n" + "=" * 60)
    print("3. Liga Data Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 比赛总数
    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (BUNDESLIGA3_ID,))
    total = cursor.fetchone()[0]
    print(f"Total matches: {total}")

    # 球队数
    cursor.execute('''
        SELECT COUNT(DISTINCT team_id) FROM (
            SELECT home_team_id as team_id FROM matches WHERE league_id = ?
            UNION
            SELECT away_team_id FROM matches WHERE league_id = ?
        )
    ''', (BUNDESLIGA3_ID, BUNDESLIGA3_ID))
    teams = cursor.fetchone()[0]
    print(f"Teams: {teams}")

    # 数据覆盖率
    fields = [
        ('match_time', 'Match time'),
        ('home_goals', 'Home goals'),
        ('home_goals_ht', 'Half-time goals'),
        ('home_shots', 'Shots'),
        ('home_shots_on', 'Shots on target'),
        ('referee', 'Referee'),
        ('odds_home', 'Odds'),
    ]

    print("\nData coverage:")
    for field, name in fields:
        cursor.execute(f'''
            SELECT COUNT(*) FROM matches
            WHERE league_id = ? AND {field} IS NOT NULL AND {field} != ''
        ''', (BUNDESLIGA3_ID,))
        count = cursor.fetchone()[0]
        pct = count / total * 100 if total > 0 else 0
        print(f"  {name}: {count} ({pct:.1f}%)")

    conn.close()


if __name__ == "__main__":
    import_all_csvs()
    show_stats()
    print("\n3. Liga data import completed!")