"""
检查欧战赛事球队信息
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def check_uefa_teams():
    print("=" * 60)
    print("UEFA Competition Teams Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # Get teams from UEFA competitions
    cursor.execute('''
        SELECT DISTINCT t.team_id, t.name_en, t.name_cn, t.stadium, t.stadium_capacity, t.city
        FROM teams t
        WHERE t.team_id IN (
            SELECT DISTINCT home_team_id FROM matches WHERE league_id IN (10, 7511, 7512)
            UNION
            SELECT DISTINCT away_team_id FROM matches WHERE league_id IN (10, 7511, 7512)
        )
        ORDER BY t.name_en
    ''')

    teams = cursor.fetchall()

    print(f"\nTotal teams in UEFA competitions: {len(teams)}")

    has_cn = sum(1 for t in teams if t['name_cn'] and t['name_cn'].strip())
    has_stadium = sum(1 for t in teams if t['stadium'] and t['stadium'].strip())
    has_capacity = sum(1 for t in teams if t['stadium_capacity'])
    has_city = sum(1 for t in teams if t['city'] and t['city'].strip())

    print(f"\nStatistics:")
    print(f"  With Chinese name: {has_cn}/{len(teams)}")
    print(f"  With stadium: {has_stadium}/{len(teams)}")
    print(f"  With capacity: {has_capacity}/{len(teams)}")
    print(f"  With city: {has_city}/{len(teams)}")

    # Show sample teams without details
    print(f"\nTeams missing details (sample):")
    missing = [t for t in teams if not t['name_cn'] or not t['stadium']][:20]
    for t in missing:
        print(f"  {t['name_en']}")

    conn.close()
    return teams

if __name__ == "__main__":
    check_uefa_teams()
    print("\nDone!")