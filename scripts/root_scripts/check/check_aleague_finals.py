"""
检查澳超季后赛比赛
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

def check_aleague_finals():
    print("=" * 60)
    print("A-League Finals Series Check")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    cursor = conn.cursor()

    # 检查2026年最近的比赛
    cursor.execute('''
        SELECT m.match_date, h.name_en, a.name_en, m.home_goals, m.away_goals
        FROM matches m
        JOIN teams h ON m.home_team_id = h.team_id
        JOIN teams a ON m.away_team_id = a.team_id
        WHERE m.league_id = 1 AND m.match_date >= '2026-04-01'
        ORDER BY m.match_date DESC
        LIMIT 30
    ''')

    print("\nRecent A-League matches (April-May 2026):")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} vs {row[2]} ({row[3]}-{row[4]})")

    # 检查最新日期
    cursor.execute('SELECT MAX(match_date) FROM matches WHERE league_id = 1')
    latest = cursor.fetchone()[0]
    print(f"\nLatest match date: {latest}")

    # 检查是否有季后赛标识
    cursor.execute('''
        SELECT COUNT(*) FROM matches
        WHERE league_id = 1
        AND match_date >= '2026-04-15'
    ''')
    late_season = cursor.fetchone()[0]
    print(f"Matches in late season (April 15+): {late_season}")

    conn.close()

if __name__ == "__main__":
    check_aleague_finals()
    print("\nDone!")