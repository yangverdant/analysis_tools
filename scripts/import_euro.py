"""
Import European Championship complete data
- Match data from 2000-2024
- Include detailed statistics from FBref
"""

import pandas as pd
import sqlite3
import os

DB_PATH = 'd:/football_tools/data/football_v2.db'
CSV_PATH = 'd:/football_tools/data/04_international/euro/euro_all.csv'
FBREF_PATH = 'd:/football_tools/data/04_international/euro_fbref/euro_fbref_all.csv'

# Team name mappings for national teams
TEAM_MAP = {
    'Belgium': 'Belgium',
    'Sweden': 'Sweden',
    'France': 'France',
    'Denmark': 'Denmark',
    'Netherlands': 'Netherlands',
    'Holland': 'Netherlands',
    'Czech Republic': 'Czech Republic',
    'Czechia': 'Czech Republic',
    'Turkey': 'Turkey',
    'Italy': 'Italy',
    'Germany': 'Germany',
    'Romania': 'Romania',
    'Portugal': 'Portugal',
    'England': 'England',
    'Spain': 'Spain',
    'Russia': 'Russia',
    'Yugoslavia': 'Yugoslavia',
    'Norway': 'Norway',
    'Slovenia': 'Slovenia',
    'Switzerland': 'Switzerland',
    'Croatia': 'Croatia',
    'Poland': 'Poland',
    'Ukraine': 'Ukraine',
    'Austria': 'Austria',
    'Hungary': 'Hungary',
    'Greece': 'Greece',
    'Slovakia': 'Slovakia',
    'Wales': 'Wales',
    'Finland': 'Finland',
    'North Macedonia': 'North Macedonia',
    'Scotland': 'Scotland',
    'Czech Rep': 'Czech Republic',
    'Rep of Ireland': 'Republic of Ireland',
    'Ireland': 'Republic of Ireland',
    'Iceland': 'Iceland',
    'Albania': 'Albania',
    'Serbia': 'Serbia',
    'Georgia': 'Georgia',
    'Turkiye': 'Turkey',
}

def get_team_id(cursor, team_name):
    """Get team ID by name"""
    if not team_name:
        return None

    # Normalize name
    team_name = TEAM_MAP.get(team_name, team_name)

    # Direct match
    cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    # Fuzzy match
    cursor.execute('SELECT team_id FROM teams WHERE name_en LIKE ?', (f'%{team_name}%',))
    row = cursor.fetchone()
    if row:
        return row[0]

    return None

def add_team(conn, cursor, team_name, added_teams):
    """Add a new national team"""
    if team_name in added_teams:
        return added_teams[team_name]

    cursor.execute('SELECT MAX(team_id) FROM teams')
    max_id = cursor.fetchone()[0] or 0
    new_id = max_id + 1

    cursor.execute('''
        INSERT INTO teams (team_id, name_en, name_cn, country, country_cn)
        VALUES (?, ?, ?, ?, ?)
    ''', (new_id, team_name, team_name, team_name, team_name))

    conn.commit()
    added_teams[team_name] = new_id
    print(f'  Added team: {team_name}')
    return new_id

def import_euro():
    print('=' * 60)
    print('Importing European Championship Data')
    print('=' * 60)

    # Read main data
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig', low_memory=False)
    df.columns = [c.replace('﻿', '').strip() for c in df.columns]

    print(f'\nLoaded {len(df)} matches from euro_all.csv')

    # Read FBref detailed data
    df_fbref = pd.read_csv(FBREF_PATH, encoding='utf-8-sig', low_memory=False)
    df_fbref.columns = [c.replace('﻿', '').strip() for c in df_fbref.columns]
    print(f'Loaded {len(df_fbref)} matches from FBref (detailed stats)')

    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    league_id = 15
    print(f'League ID: {league_id}')

    added_teams = {}
    updated = 0
    inserted = 0
    errors = 0

    for idx, row in df.iterrows():
        try:
            date = str(row['Date']).strip()
            time_str = str(row.get('Time', '')) if pd.notna(row.get('Time')) else None

            home_team = str(row['HomeTeam']).strip() if pd.notna(row['HomeTeam']) else None
            away_team = str(row['AwayTeam']).strip() if pd.notna(row['AwayTeam']) else None

            if not home_team or not away_team:
                continue

            # Goals
            home_goals = int(row['FTHG']) if pd.notna(row.get('FTHG')) else None
            away_goals = int(row['FTAG']) if pd.notna(row.get('FTAG')) else None

            # Shots
            home_shots = int(row['HS']) if pd.notna(row.get('HS')) else None
            away_shots = int(row['AS']) if pd.notna(row.get('AS')) else None
            home_shots_target = int(row['HST']) if pd.notna(row.get('HST')) else None
            away_shots_target = int(row['AST']) if pd.notna(row.get('AST')) else None

            # Get team IDs
            home_team_id = get_team_id(cursor, home_team)
            away_team_id = get_team_id(cursor, away_team)

            if not home_team_id:
                home_team_id = add_team(conn, cursor, home_team, added_teams)
            if not away_team_id:
                away_team_id = add_team(conn, cursor, away_team, added_teams)

            if not home_team_id or not away_team_id:
                errors += 1
                continue

            # Parse season from date
            year = int(date.split('-')[0])
            # Euro tournament year
            if year == 2021:
                season = 2020  # Euro 2020 was held in 2021
            else:
                season = year

            # Check if match exists
            cursor.execute('''
                SELECT match_id FROM matches
                WHERE league_id = ? AND match_date = ?
                AND home_team_id = ? AND away_team_id = ?
            ''', (league_id, date, home_team_id, away_team_id))

            existing = cursor.fetchone()

            if existing:
                cursor.execute('''
                    UPDATE matches SET
                        home_goals = COALESCE(home_goals, ?),
                        away_goals = COALESCE(away_goals, ?),
                        home_shots = COALESCE(home_shots, ?),
                        away_shots = COALESCE(away_shots, ?),
                        home_shots_target = COALESCE(home_shots_target, ?),
                        away_shots_target = COALESCE(away_shots_target, ?),
                        status = 'finished'
                    WHERE match_id = ?
                ''', (home_goals, away_goals, home_shots, away_shots,
                      home_shots_target, away_shots_target, existing[0]))
                updated += 1
            else:
                match_id = f'euro_{season}_{date}_{home_team_id}_vs_{away_team_id}'
                cursor.execute('''
                    INSERT INTO matches (
                        match_id, league_id, season_id, match_date, match_time,
                        home_team_id, away_team_id, home_goals, away_goals,
                        home_shots, away_shots, home_shots_target, away_shots_target,
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'finished')
                ''', (match_id, league_id, season, date, time_str,
                      home_team_id, away_team_id, home_goals, away_goals,
                      home_shots, away_shots, home_shots_target, away_shots_target))
                inserted += 1

        except Exception as e:
            errors += 1
            continue

    conn.commit()
    print(f'\nDone! Inserted: {inserted}, Updated: {updated}, Errors: {errors}')

    # Verify
    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (league_id,))
    total = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND home_shots IS NOT NULL', (league_id,))
    with_shots = cursor.fetchone()[0]

    print(f'\nEuropean Championship matches: {total}')
    print(f'With shots: {with_shots} ({round(with_shots/total*100, 1) if total > 0 else 0}%)')

    conn.close()

if __name__ == '__main__':
    import_euro()