"""
检查各项赛事未来6个月的数据 (2026-05-23 至 2026-11-23)
"""

import sqlite3
from pathlib import Path
import time

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

def check_future_data():
    print("=" * 70)
    print("Future Data Check (2026-05-23 to 2026-11-23)")
    print("=" * 70)

    time.sleep(1)

    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 所有已采集的联赛
    leagues = [
        (21, 'Bundesliga'),
        (22, '2. Bundesliga'),
        (23, '3. Liga'),
        (7484, 'DFB-Pokal'),
        (7485, 'DFL-Supercup'),
        (17, 'Serie A'),
        (18, 'Serie B'),
        (7482, 'Coppa Italia'),
        (7483, 'Supercoppa'),
        (24, 'Ligue 1'),
        (25, 'Ligue 2'),
        (7486, 'Coupe de France'),
        (7488, 'Trophee des Champions'),
        (26, 'Jupiler Pro League'),
        (27, 'Challenger Pro League'),
        (7489, 'Belgian Cup'),
        (7490, 'Belgian Super Cup'),
        (1, 'A-League'),
        (10, 'UEFA Champions League'),
        (7511, 'UEFA Europa League'),
        (7512, 'UEFA Conference League'),
    ]

    has_future = []
    missing_future = []

    for league_id, name in leagues:
        cursor.execute('''
            SELECT COUNT(*), MIN(match_date), MAX(match_date)
            FROM matches
            WHERE league_id = ? AND match_date >= '2026-05-23'
        ''', (league_id,))

        r = cursor.fetchone()
        future_count = r[0]

        # Get total and date range
        cursor.execute('''
            SELECT COUNT(*), MIN(match_date), MAX(match_date)
            FROM matches
            WHERE league_id = ?
        ''', (league_id,))
        total, min_date, max_date = cursor.fetchone()

        if future_count > 0:
            has_future.append((name, future_count, max_date))
            status = f"HAS FUTURE: {future_count} matches"
        else:
            missing_future.append((name, max_date))
            status = f"NO FUTURE (latest: {max_date})"

        print(f"{name}: {status}")

    conn.close()

    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)

    print(f"\nWITH future data ({len(has_future)}):")
    for name, count, max_date in has_future:
        print(f"  {name}: {count} matches")

    print(f"\nMISSING future data ({len(missing_future)}):")
    for name, max_date in missing_future:
        print(f"  {name}: latest is {max_date}")

if __name__ == "__main__":
    check_future_data()
    print("\nDone!")