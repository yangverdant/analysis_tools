"""
检查欧战赛事数据完整性
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def check_uefa_data():
    print("=" * 60)
    print("UEFA Competitions Data Integrity Check")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # Check matches
    print("\n1. Match Data:")
    for league_id, name in [(10, 'Champions League'), (7511, 'Europa League'), (7512, 'Conference League')]:
        cursor.execute('SELECT COUNT(*), MIN(match_date), MAX(match_date) FROM matches WHERE league_id = ?', (league_id,))
        r = cursor.fetchone()
        print(f"  {name}: {r[0]} matches ({r[1]} to {r[2]})")

    # Check teams
    print("\n2. Team Data:")
    cursor.execute('''
        SELECT COUNT(DISTINCT t.team_id)
        FROM teams t
        WHERE t.team_id IN (
            SELECT DISTINCT home_team_id FROM matches WHERE league_id IN (10, 7511, 7512)
            UNION
            SELECT DISTINCT away_team_id FROM matches WHERE league_id IN (10, 7511, 7512)
        )
    ''')
    total_teams = cursor.fetchone()[0]
    print(f"  Total teams: {total_teams}")

    cursor.execute('''
        SELECT
            SUM(CASE WHEN name_cn IS NOT NULL AND name_cn != '' THEN 1 ELSE 0 END) as has_cn,
            SUM(CASE WHEN stadium IS NOT NULL AND stadium != '' THEN 1 ELSE 0 END) as has_stadium,
            SUM(CASE WHEN stadium_capacity IS NOT NULL THEN 1 ELSE 0 END) as has_capacity,
            SUM(CASE WHEN city IS NOT NULL AND city != '' THEN 1 ELSE 0 END) as has_city
        FROM teams
        WHERE team_id IN (
            SELECT DISTINCT home_team_id FROM matches WHERE league_id IN (10, 7511, 7512)
            UNION
            SELECT DISTINCT away_team_id FROM matches WHERE league_id IN (10, 7511, 7512)
        )
    ''')
    r = cursor.fetchone()
    print(f"  With Chinese name: {r[0]}/{total_teams} ({r[0]*100//total_teams}%)")
    print(f"  With stadium: {r[1]}/{total_teams} ({r[1]*100//total_teams}%)")
    print(f"  With capacity: {r[2]}/{total_teams} ({r[2]*100//total_teams}%)")
    print(f"  With city: {r[3]}/{total_teams} ({r[3]*100//total_teams}%)")

    # Check players
    print("\n3. Player Data:")
    cursor.execute('SELECT COUNT(*) FROM players')
    total_players = cursor.fetchone()[0]
    print(f"  Total players in database: {total_players}")

    # Check xG data
    print("\n4. xG Data:")
    cursor.execute('''
        SELECT COUNT(*) FROM matches
        WHERE league_id IN (10, 7511, 7512)
        AND home_xg IS NOT NULL
    ''')
    has_xg = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id IN (10, 7511, 7512)')
    total_matches = cursor.fetchone()[0]
    print(f"  Matches with xG: {has_xg}/{total_matches}")

    conn.close()

if __name__ == "__main__":
    check_uefa_data()
    print("\nDone!")