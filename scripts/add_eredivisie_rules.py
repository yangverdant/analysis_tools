"""
Add Eredivisie league rules to database
"""
import sqlite3
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'football_v2.db')

def add_eredivisie_rules():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get league ID
    cursor.execute('SELECT league_id FROM leagues WHERE name_en = "Eredivisie"')
    league_row = cursor.fetchone()
    league_id = league_row[0] if league_row else 14

    # Eredivisie rules data (2000-2026)
    # Dutch league runs August-May
    # 18 teams, each plays others twice (home/away) = 34 matches
    # Champion qualifies for Champions League
    # 2nd qualifies for Champions League qualifying
    # 3rd qualifies for Europa League
    # 4th-5th qualify for Europa Conference League qualifying
    # 16th plays relegation playoff
    # 17th-18th directly relegated

    eredivisie_rules = []

    for year in range(2000, 2027):
        if year >= 2021:
            # Conference League era
            cl_spots = 2  # Champion + 2nd
            cl_qualifying = 0
            el_spots = 1  # 3rd
            ecl_spots = 2  # 4th-5th
        elif year >= 2018:
            cl_spots = 1
            cl_qualifying = 1  # 2nd
            el_spots = 2  # 3rd-4th
            ecl_spots = 0
        else:
            cl_spots = 1
            cl_qualifying = 1
            el_spots = 2
            ecl_spots = 0

        eredivisie_rules.append({
            'season': year,
            'teams_count': 18,
            'matches_per_team': 34,
            'format_type': 'double_round_robin',
            'points_for_win': 3,
            'champions_league_spots': cl_spots,
            'champions_league_qualifying_spots': cl_qualifying,
            'europa_league_spots': el_spots,
            'conference_league_spots': ecl_spots,
            'promotion_spots': 2,
            'relegation_spots': 2,
            'relegation_playoff_spots': 2,
            'has_relegation_playoff': 1,
            'season_start_month': 8,
            'season_end_month': 5,
        })

    # Delete existing rules
    cursor.execute('DELETE FROM league_rules WHERE league_id = ?', (league_id,))

    # Insert new rules
    inserted = 0
    for rule in eredivisie_rules:
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
    print(f'Inserted {inserted} league rules for Eredivisie')

    # Verify
    cursor.execute('''
        SELECT season, teams_count, champions_league_spots, europa_league_spots, conference_league_spots
        FROM league_rules WHERE league_id = ? ORDER BY season
    ''', (league_id,))
    print('\nEredivisie League Rules:')
    for row in cursor.fetchall()[-5:]:
        print(f'  {row[0]}: {row[1]} teams, CL:{row[2]}, EL:{row[3]}, ECL:{row[4]}')

    conn.close()

if __name__ == '__main__':
    add_eredivisie_rules()
