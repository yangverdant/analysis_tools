"""
Add Copa Libertadores competition rules
"""
import sqlite3
from datetime import datetime
import os

DB_PATH = 'd:/football_tools/data/football_v2.db'

def add_copa_libertadores_rules():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    league_id = 7515

    # Copa Libertadores rules
    # - 47 teams from 10 CONMEBOL countries
    # - 3 stages: Qualifying, Group Stage, Knockout
    # - Group stage: 32 teams in 8 groups of 4 (double round robin)
    # - Knockout: Round of 16, Quarter-final, Semi-final, Final
    # - Champion qualifies for FIFA Club World Cup and Recopa Sudamericana

    rules_data = []

    for year in range(2000, 2027):
        # Tournament format has evolved over time
        if year >= 2017:
            # Current format
            teams_count = 47
            group_stage_teams = 32
            group_matches_per_team = 6  # Double round robin in groups
            format_type = 'group_knockout'
        elif year >= 2008:
            # Previous format with more teams
            teams_count = 38
            group_stage_teams = 32
            group_matches_per_team = 6
            format_type = 'group_knockout'
        else:
            # Earlier format
            teams_count = 36
            group_stage_teams = 32
            group_matches_per_team = 6
            format_type = 'group_knockout'

        rules_data.append({
            'season': year,
            'teams_count': teams_count,
            'matches_per_team': group_matches_per_team,  # Group stage only
            'format_type': format_type,
            'points_for_win': 3,
            'champions_league_spots': 0,  # N/A for domestic cup
            'europa_league_spots': 0,
            'conference_league_spots': 0,
            'promotion_spots': 0,
            'relegation_spots': 0,
            'relegation_playoff_spots': 0,
            'has_relegation_playoff': 0,
            'season_start_month': 2,  # February
            'season_end_month': 11,   # November (final)
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
    print(f'Inserted {inserted} rules for Copa Libertadores')

    # Verify
    cursor.execute('''
        SELECT season, teams_count, format_type
        FROM league_rules WHERE league_id = ? ORDER BY season DESC LIMIT 5
    ''', (league_id,))
    print('\nRecent Copa Libertadores rules:')
    for row in cursor.fetchall():
        print(f'  {row[0]}: {row[1]} teams, format={row[2]}')

    conn.close()

if __name__ == '__main__':
    add_copa_libertadores_rules()