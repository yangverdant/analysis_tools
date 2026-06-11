"""
Add MLS league rules
"""
import sqlite3
from datetime import datetime

DB_PATH = 'd:/football_tools/data/football_v2.db'

def add_mls_rules():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    league_id = 26

    rules_data = []

    for year in range(1996, 2027):
        # Team count evolved over time
        if year >= 2023:
            teams_count = 29
        elif year >= 2022:
            teams_count = 28
        elif year >= 2021:
            teams_count = 27
        elif year >= 2018:
            teams_count = 23
        elif year >= 2015:
            teams_count = 20
        elif year >= 2012:
            teams_count = 19
        elif year >= 2011:
            teams_count = 18
        elif year >= 2008:
            teams_count = 14
        else:
            teams_count = 10

        matches_per_team = 34

        # Playoff spots
        if year >= 2023:
            playoff_teams = 18
        elif year >= 2019:
            playoff_teams = 14
        elif year >= 2017:
            playoff_teams = 12
        else:
            playoff_teams = 10

        rules_data.append({
            'season': str(year),
            'teams_count': teams_count,
            'matches_per_team': matches_per_team,
            'format_type': 'conference_playoff',
            'points_for_win': 3,
            'playoff_teams': playoff_teams,
            'has_playoffs': 1,
            'has_conferences': 1,
            'season_start_month': 3,
            'season_end_month': 11,
        })

    # Delete existing rules
    cursor.execute('DELETE FROM league_rules WHERE league_id = ?', (league_id,))

    # Insert new rules
    inserted = 0
    for rule in rules_data:
        try:
            cursor.execute('''
                INSERT INTO league_rules (
                    league_id, season, teams_count, matches_per_team, format_type,
                    points_for_win, has_playoffs, has_conferences,
                    playoff_teams, season_start_month, season_end_month, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                league_id, rule['season'], rule['teams_count'], rule['matches_per_team'],
                rule['format_type'], rule['points_for_win'],
                rule['has_playoffs'], rule['has_conferences'],
                rule['playoff_teams'], rule['season_start_month'], rule['season_end_month'],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            inserted += 1
        except Exception as e:
            print(f'Error inserting {rule["season"]}: {e}')

    conn.commit()
    print(f'Inserted {inserted} rules for MLS')

    # Verify
    cursor.execute('''
        SELECT season, teams_count, matches_per_team, playoff_teams
        FROM league_rules WHERE league_id = ? ORDER BY season DESC LIMIT 5
    ''', (league_id,))
    print('\nRecent MLS rules:')
    for row in cursor.fetchall():
        print(f'  {row[0]}: {row[1]} teams, {row[2]} matches, {row[3]} playoff teams')

    conn.close()

if __name__ == '__main__':
    add_mls_rules()