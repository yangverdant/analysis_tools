"""
Add UEFA Europa Conference League tournament rules
- Created in 2021-22 season
- 3rd tier European club competition
"""
import sqlite3
from datetime import datetime

DB_PATH = 'd:/football_tools/data/football_v2.db'

def add_conference_league_rules():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    league_id = 7512

    # UEFA Europa Conference League rules
    # - Created 2021-22 season
    # - Group stage: 8 groups of 4 teams
    # - Knockout: Round of 16, Quarter-finals, Semi-finals, Final
    # - Winner qualifies for Europa League next season

    rules_data = []

    for year in range(2021, 2028):
        rules_data.append({
            'season': f'{year}-{year+1}',
            'teams_count': 32,
            'format_type': 'group_knockout',
            'has_playoffs': 1,
            'has_conferences': 0,
            'season_start_month': 7,  # Qualifying starts July
            'season_end_month': 5,    # Final in May
        })

    # Delete existing rules
    cursor.execute('DELETE FROM league_rules WHERE league_id = ?', (league_id,))

    # Insert new rules
    inserted = 0
    for rule in rules_data:
        try:
            cursor.execute('''
                INSERT INTO league_rules (
                    league_id, season, teams_count, format_type,
                    has_playoffs, has_conferences,
                    season_start_month, season_end_month, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                league_id, rule['season'], rule['teams_count'], rule['format_type'],
                rule['has_playoffs'], rule['has_conferences'],
                rule['season_start_month'], rule['season_end_month'],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            inserted += 1
        except Exception as e:
            print(f'Error: {e}')

    conn.commit()
    print(f'Inserted {inserted} rules for UEFA Europa Conference League')

    # Verify
    cursor.execute('''
        SELECT season, teams_count, format_type
        FROM league_rules WHERE league_id = ? ORDER BY season
    ''', (league_id,))
    print('\nUEFA Europa Conference League rules:')
    for row in cursor.fetchall():
        print(f'  {row[0]}: {row[1]} teams, {row[2]}')

    conn.close()

if __name__ == '__main__':
    add_conference_league_rules()