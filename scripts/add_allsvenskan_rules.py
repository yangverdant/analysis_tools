"""
Add Allsvenskan league rules to database
"""
import sqlite3
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'football_v2.db')

def add_allsvenskan_rules():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get league ID
    cursor.execute('SELECT league_id FROM leagues WHERE name_en = "Allsvenskan"')
    league_row = cursor.fetchone()
    league_id = league_row[0] if league_row else 3

    # Allsvenskan rules data (2012-2026)
    # Swedish league runs April-November
    # 16 teams, each plays others twice (home/away) = 30 matches
    # Champion qualifies for Champions League Q2
    # 2nd/3rd qualify for Europa Conference League Q2/Q1
    # Bottom 2 relegated to Superettan
    # 14th place plays relegation playoff vs 3rd from Superettan

    allsvenskan_rules = []

    for year in range(2012, 2027):
        if year >= 2021:
            # Conference League era
            cl_spots = 1
            el_spots = 0
            ecl_spots = 2
        elif year >= 2017:
            # Mixed era
            cl_spots = 1
            el_spots = 1
            ecl_spots = 1
        else:
            # Pre-Conference League
            cl_spots = 1
            el_spots = 2
            ecl_spots = 0

        start_month = 4
        end_month = 11

        if year == 2020:
            start_month = 6  # COVID delay
            end_month = 12

        allsvenskan_rules.append({
            'season': year,
            'teams_count': 16,
            'matches_per_team': 30,
            'format_type': 'double_round_robin',
            'points_for_win': 3,
            'champions_league_spots': cl_spots,
            'europa_league_spots': el_spots,
            'conference_league_spots': ecl_spots,
            'promotion_spots': 2,
            'relegation_spots': 2,
            'relegation_playoff_spots': 1,
            'has_relegation_playoff': 1,
            'season_start_month': start_month,
            'season_end_month': end_month,
        })

    # Delete existing rules
    cursor.execute('DELETE FROM league_rules WHERE league_id = ?', (league_id,))

    # Insert new rules
    inserted = 0
    for rule in allsvenskan_rules:
        try:
            cursor.execute('''
                INSERT INTO league_rules (
                    league_id, season, teams_count, matches_per_team, format_type,
                    points_for_win, champions_league_spots, europa_league_spots,
                    conference_league_spots, promotion_spots, relegation_spots,
                    relegation_playoff_spots, has_relegation_playoff,
                    season_start_month, season_end_month, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                league_id, rule['season'], rule['teams_count'], rule['matches_per_team'],
                rule['format_type'], rule['points_for_win'], rule['champions_league_spots'],
                rule['europa_league_spots'], rule['conference_league_spots'],
                rule['promotion_spots'], rule['relegation_spots'],
                rule['relegation_playoff_spots'], rule['has_relegation_playoff'],
                rule['season_start_month'], rule['season_end_month'],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            inserted += 1
        except Exception as e:
            print(f'Error inserting {rule["season"]}: {e}')

    conn.commit()
    print(f'Inserted {inserted} league rules for Allsvenskan')

    # Verify
    cursor.execute('SELECT season, teams_count, champions_league_spots, europa_league_spots, conference_league_spots FROM league_rules WHERE league_id = ? ORDER BY season', (league_id,))
    print('\nAllsvenskan League Rules:')
    for row in cursor.fetchall():
        print(f'  {row[0]}: {row[1]} teams, CL:{row[2]}, EL:{row[3]}, ECL:{row[4]}')

    conn.close()

if __name__ == '__main__':
    add_allsvenskan_rules()
