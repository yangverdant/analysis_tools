"""
Add Copa America tournament rules
"""
import sqlite3
from datetime import datetime

DB_PATH = 'd:/football_tools/data/football_v2.db'

def add_copa_america_rules():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    league_id = 12

    # Copa America rules
    # - Usually 12 teams (10 CONMEBOL + 2 invited)
    # - Group stage: 3 groups of 4
    # - Knockout: Quarter-finals, Semi-finals, Final
    # - Held every 4 years (now 2 years for special cases)

    rules_data = []

    # Copa America tournaments since 1916
    for year in [1916, 1917, 1919, 1920, 1921, 1922, 1923, 1924, 1925, 1926, 1927, 1929,
                 1935, 1937, 1939, 1941, 1942, 1945, 1946, 1947, 1949, 1953, 1955, 1956,
                 1957, 1959, 1963, 1967, 1975, 1979, 1983, 1987, 1989, 1991, 1993, 1995,
                 1997, 1999, 2001, 2004, 2007, 2011, 2015, 2016, 2019, 2021, 2024]:

        if year >= 2016:
            teams_count = 16
            format_type = 'group_knockout_16'
        elif year >= 1993:
            teams_count = 12
            format_type = 'group_knockout_12'
        else:
            teams_count = 10
            format_type = 'group_knockout_10'

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
            pass

    conn.commit()
    print(f'Inserted {inserted} rules for Copa America')

    # Verify
    cursor.execute('''
        SELECT season, teams_count, format_type
        FROM league_rules WHERE league_id = ? ORDER BY season DESC LIMIT 10
    ''', (league_id,))
    print('\nRecent Copa America tournaments:')
    for row in cursor.fetchall():
        print(f'  {row[0]}: {row[1]} teams, {row[2]}')

    conn.close()

if __name__ == '__main__':
    add_copa_america_rules()