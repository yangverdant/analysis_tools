"""
检查欧战赛事数据时间范围
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def check_date_ranges():
    print("=" * 60)
    print("UEFA Competitions Date Range Check")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # Check each competition
    competitions = [
        (10, 'UEFA Champions League'),
        (7511, 'UEFA Europa League'),
        (7512, 'UEFA Conference League'),
    ]

    for league_id, name in competitions:
        print(f"\n{name} (ID: {league_id}):")

        # Total matches
        cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (league_id,))
        total = cursor.fetchone()[0]
        print(f"  Total matches: {total}")

        # Date range
        cursor.execute('SELECT MIN(match_date), MAX(match_date) FROM matches WHERE league_id = ?', (league_id,))
        min_date, max_date = cursor.fetchone()
        print(f"  Date range: {min_date} to {max_date}")

        # Matches per season
        print(f"  Matches by season:")
        seasons = ['2020', '2021', '2022', '2023', '2024', '2025', '2026']
        for season in seasons:
            cursor.execute('''
                SELECT COUNT(*) FROM matches
                WHERE league_id = ?
                AND match_date >= ?
                AND match_date < ?
            ''', (league_id, f'{season}-01-01', f'{season}-12-31'))
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"    {season}: {count} matches")

        # Check if 2023-2026 data exists
        cursor.execute('''
            SELECT COUNT(*) FROM matches
            WHERE league_id = ?
            AND match_date >= '2023-01-01'
        ''', (league_id,))
        recent = cursor.fetchone()[0]
        print(f"  Matches 2023+: {recent}")

        if recent == 0:
            print(f"  WARNING: Missing recent data (2023-2026)!")

    conn.close()

if __name__ == "__main__":
    check_date_ranges()
    print("\nDone!")