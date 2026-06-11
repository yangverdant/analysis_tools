"""
Import MLS (Major League Soccer) data 2020-latest
"""

import pandas as pd
import sqlite3
import glob
import os

DB_PATH = 'd:/football_tools/data/football_v2.db'
CSV_DIR = 'd:/football_tools/data/07_north_america/mls'

# MLS team name mappings
TEAM_MAP = {
    'Los Angeles FC': 'Los Angeles FC',
    'LAFC': 'Los Angeles FC',
    'Los Angeles Galaxy': 'LA Galaxy',
    'LA Galaxy': 'LA Galaxy',
    'Inter Miami CF': 'Inter Miami CF',
    'Inter Miami': 'Inter Miami CF',
    'Minnesota United FC': 'Minnesota United FC',
    'Minnesota United': 'Minnesota United FC',
    'Atlanta United FC': 'Atlanta United FC',
    'Atlanta United': 'Atlanta United FC',
    'CF Montréal': 'CF Montréal',
    'CF Montreal': 'CF Montréal',
    'Columbus Crew': 'Columbus Crew',
    'Columbus Crew SC': 'Columbus Crew',
    'Chicago Fire': 'Chicago Fire FC',
    'Chicago Fire FC': 'Chicago Fire FC',
    'D.C. United': 'D.C. United',
    'DC United': 'D.C. United',
    'Toronto FC': 'Toronto FC',
    'New York City FC': 'New York City FC',
    'NYCFC': 'New York City FC',
    'New York Red Bulls': 'New York Red Bulls',
    'NY Red Bulls': 'New York Red Bulls',
    'Seattle Sounders FC': 'Seattle Sounders FC',
    'Seattle Sounders': 'Seattle Sounders FC',
    'Portland Timbers': 'Portland Timbers',
    'Vancouver Whitecaps FC': 'Vancouver Whitecaps FC',
    'Vancouver Whitecaps': 'Vancouver Whitecaps FC',
    'Sporting Kansas City': 'Sporting Kansas City',
    'Real Salt Lake': 'Real Salt Lake',
    'RSL': 'Real Salt Lake',
    'Colorado Rapids': 'Colorado Rapids',
    'FC Dallas': 'FC Dallas',
    'Dallas': 'FC Dallas',
    'Houston Dynamo FC': 'Houston Dynamo FC',
    'Houston Dynamo': 'Houston Dynamo FC',
    'San Jose Earthquakes': 'San Jose Earthquakes',
    'FC Cincinnati': 'FC Cincinnati',
    'Cincinnati': 'FC Cincinnati',
    'Orlando City SC': 'Orlando City SC',
    'Orlando City': 'Orlando City SC',
    'New England Revolution': 'New England Revolution',
    'Nashville SC': 'Nashville SC',
    'Nashville': 'Nashville SC',
    'Austin FC': 'Austin FC',
    'Charlotte FC': 'Charlotte FC',
    'St. Louis City SC': 'St. Louis City SC',
    'St Louis City': 'St. Louis City SC',
    'Philadelphia Union': 'Philadelphia Union',
    'Chivas USA': 'Chivas USA',
    'Montreal Impact': 'CF Montréal',
}

def clean_team_name(team_name):
    """Clean team name and normalize"""
    if pd.isna(team_name):
        return None
    team_name = str(team_name).strip()
    # Use mapping
    return TEAM_MAP.get(team_name, team_name)

def parse_date(date_str):
    """Convert YYYY-MM-DD to standard format"""
    try:
        if pd.isna(date_str):
            return None
        date_str = str(date_str).strip()
        if '-' in date_str and len(date_str) == 10:
            return date_str
    except:
        pass
    return date_str

def get_team_id(cursor, team_name):
    """Get team ID by name"""
    if not team_name:
        return None

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
    """Add a new team to database"""
    if team_name in added_teams:
        return added_teams[team_name]

    cursor.execute('SELECT MAX(team_id) FROM teams')
    max_id = cursor.fetchone()[0] or 0
    new_id = max_id + 1

    cursor.execute('''
        INSERT INTO teams (team_id, name_en, name_cn, country, country_cn)
        VALUES (?, ?, ?, 'USA', '美国')
    ''', (new_id, team_name, team_name))

    conn.commit()
    added_teams[team_name] = new_id
    print(f'  Added team: {team_name}')
    return new_id

def import_mls():
    print('=' * 60)
    print('Importing MLS Data (2020-latest)')
    print('=' * 60)

    # Use mls_2025.csv which has the most data
    csv_file = CSV_DIR + '/mls_2025.csv'

    df = pd.read_csv(csv_file, encoding='utf-8-sig', low_memory=False)
    df.columns = [c.replace('﻿', '').strip() for c in df.columns]

    print(f'\nLoaded {len(df)} matches')

    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    league_id = 26
    print(f'League ID: {league_id}')

    # Track added teams
    added_teams = {}

    inserted = 0
    updated = 0
    errors = 0

    for idx, row in df.iterrows():
        try:
            # Parse date
            date = parse_date(row['Date'])
            if not date:
                continue

            time_str = str(row.get('Time', '')) if pd.notna(row.get('Time')) else None

            # Clean team names
            home_raw = row['HomeTeam']
            away_raw = row['AwayTeam']

            home_team = clean_team_name(home_raw)
            away_team = clean_team_name(away_raw)

            if not home_team or not away_team:
                errors += 1
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

            # Add missing teams
            if not home_team_id:
                home_team_id = add_team(conn, cursor, home_team, added_teams)
            if not away_team_id:
                away_team_id = add_team(conn, cursor, away_team, added_teams)

            if not home_team_id or not away_team_id:
                errors += 1
                continue

            # Parse season from date
            year = int(date.split('-')[0])
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
                match_id = f'mls_{season}_{date}_{home_team_id}_vs_{away_team_id}'
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

            if (idx + 1) % 100 == 0:
                conn.commit()
                print(f'Processed {idx + 1}/{len(df)} matches...')

        except Exception as e:
            errors += 1
            continue

    conn.commit()
    print(f'\nDone! Inserted: {inserted}, Updated: {updated}, Errors: {errors}')
    print(f'Added teams: {len(added_teams)}')

    # Verify
    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (league_id,))
    total = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND home_goals IS NOT NULL', (league_id,))
    with_goals = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND home_shots IS NOT NULL', (league_id,))
    with_shots = cursor.fetchone()[0]

    print(f'\nMLS matches: {total}')
    print(f'With goals: {with_goals} ({round(with_goals/total*100, 1) if total > 0 else 0}%)')
    print(f'With shots: {with_shots} ({round(with_shots/total*100, 1) if total > 0 else 0}%)')

    conn.close()

if __name__ == '__main__':
    import_mls()