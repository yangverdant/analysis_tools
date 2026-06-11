"""
Add European Championship tournament rules
"""
import sqlite3
from datetime import datetime

DB_PATH = 'd:/football_tools/data/football_v2.db'

def add_euro_rules():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    league_id = 15

    # Euro tournament rules
    # - Group stage: 4 groups of 4 (2000-2012) / 6 groups of 4 (2016-2024)
    # - Knockout: Round of 16 (since 2016), Quarter-finals, Semi-finals, Final
    # - Champion qualifies for Confederations Cup (until 2017)

    rules_data = []

    for year in range(1960, 2029, 4):
        if year >= 2016:
            teams_count = 24
            group_count = 6
            format_type = 'group_knockout_24'
        elif year >= 1980:
            teams_count = 16
            group_count = 4
            format_type = 'group_knockout_16'
        elif year >= 1968:
            teams_count = 8
            group_count = 2
            format_type = 'group_knockout_8'
        else:
            teams_count = 4
            group_count = 0  # Semi-finals only
            format_type = 'knockout_4'

        rules_data.append({
            'season': str(year),
            'teams_count': teams_count,
            'format_type': format_type,
            'has_playoffs': 1,
            'has_conferences': 0,
            'season_start_month': 6,
            'season_end_month': 7,
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
    print(f'Inserted {inserted} rules for European Championship')

    # Verify
    cursor.execute('''
        SELECT season, teams_count, format_type
        FROM league_rules WHERE league_id = ? ORDER BY season DESC LIMIT 5
    ''', (league_id,))
    print('\nRecent Euro tournaments:')
    for row in cursor.fetchall():
        print(f'  {row[0]}: {row[1]} teams, {row[2]}')

    conn.close()

if __name__ == '__main__':
    add_euro_rules()