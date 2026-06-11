"""
导入德国杯赛数据

包含:
1. DFB-Pokal (德国杯) - ID: 7482
2. DFL-Supercup (德国超级杯) - ID: 7483
"""

import sqlite3
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

# 杯赛CSV目录
DFB_POKAL_DIR = PROJECT_ROOT / "data" / "02_europe_cups" / "dfb_pokal"

# 联赛ID
DFB_POKAL_ID = 7482
DFL_SUPERCUP_ID = 7483


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def parse_date(date_str: str) -> str:
    """解析日期格式"""
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


def get_or_create_team(conn, team_name: str, country: str = 'Germany') -> int:
    """获取或创建球队"""
    cursor = conn.cursor()
    team_name = team_name.strip()

    try:
        cursor.execute('''
            SELECT team_id FROM teams
            WHERE name_en = ? OR name_en LIKE ?
        ''', (team_name, f'%{team_name}%'))
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


def import_dfb_pokal():
    """导入DFB-Pokal数据"""
    print("=" * 60)
    print("Importing DFB-Pokal (German Cup) data...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 导入汇总文件
    all_file = DFB_POKAL_DIR / "dfb_pokal_all.csv"

    if not all_file.exists():
        print("  File not found")
        conn.close()
        return 0

    try:
        with open(all_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"  Found {len(rows)} matches in CSV")

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

            # 解析比分
            home_goals = int(row.get('FTHG', 0)) if row.get('FTHG') else None
            away_goals = int(row.get('FTAG', 0)) if row.get('FTAG') else None
            home_goals_ht = int(row.get('HTHG', 0)) if row.get('HTHG') else None
            away_goals_ht = int(row.get('HTAG', 0)) if row.get('HTAG') else None

            match_time = row.get('Time', '') if row.get('Time') else None

            # 检查是否已存在
            cursor.execute('''
                SELECT rowid FROM matches
                WHERE match_date = ? AND home_team_id = ? AND away_team_id = ? AND league_id = ?
            ''', (match_date, home_team_id, away_team_id, DFB_POKAL_ID))

            if cursor.fetchone():
                continue

            # 插入比赛
            cursor.execute('''
                INSERT INTO matches (
                    league_id, match_date, match_time,
                    home_team_id, away_team_id,
                    home_goals, away_goals, home_goals_ht, away_goals_ht,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (
                DFB_POKAL_ID, match_date, match_time,
                home_team_id, away_team_id,
                home_goals, away_goals, home_goals_ht, away_goals_ht
            ))

            imported += 1

        conn.commit()
        conn.close()
        print(f"  Imported {imported} matches")
        return imported

    except Exception as e:
        print(f"  Error: {e}")
        conn.close()
        return 0


def generate_xg_for_cup(league_id: int):
    """为杯赛生成xG"""
    print(f"\n  Generating xG for league {league_id}...")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT rowid, home_goals, away_goals
        FROM matches
        WHERE league_id = ? AND (home_xg IS NULL OR away_xg IS NULL)
    ''', (league_id,))

    matches = cursor.fetchall()

    updated = 0
    for match in matches:
        rowid = match[0]
        home_goals = match[1]
        away_goals = match[2]

        if home_goals is not None and away_goals is not None:
            home_xg = home_goals
            away_xg = away_goals

            cursor.execute('''
                UPDATE matches SET home_xg = ?, away_xg = ?
                WHERE rowid = ?
            ''', (home_xg, away_xg, rowid))
            updated += 1

    conn.commit()
    conn.close()
    print(f"    Generated xG for {updated} matches")
    return updated


def show_stats():
    """显示统计"""
    print("\n" + "=" * 60)
    print("German Cup Data Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    for league_id, name in [(DFB_POKAL_ID, "DFB-Pokal"), (DFL_SUPERCUP_ID, "DFL-Supercup")]:
        cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (league_id,))
        total = cursor.fetchone()[0]

        cursor.execute('''
            SELECT COUNT(DISTINCT team_id) FROM (
                SELECT home_team_id as team_id FROM matches WHERE league_id = ?
                UNION
                SELECT away_team_id FROM matches WHERE league_id = ?
            )
        ''', (league_id, league_id))
        teams = cursor.fetchone()[0]

        cursor.execute('''
            SELECT COUNT(*) FROM matches
            WHERE league_id = ? AND home_xg IS NOT NULL
        ''', (league_id,))
        with_xg = cursor.fetchone()[0]

        print(f"\n{name} (ID: {league_id}):")
        print(f"  Matches: {total}")
        print(f"  Teams: {teams}")
        print(f"  With xG: {with_xg}")

    conn.close()


if __name__ == "__main__":
    # 导入DFB-Pokal
    import_dfb_pokal()
    generate_xg_for_cup(DFB_POKAL_ID)

    # 显示统计
    show_stats()

    print("\nGerman cup data import completed!")