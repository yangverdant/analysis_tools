"""
Import Copa Libertadores (South American Champions League) complete data
"""

import pandas as pd
import sqlite3
import glob
import os

DB_PATH = 'd:/football_tools/data/football_v2.db'
CSV_DIR = 'd:/football_tools/data/06_south_america/copa_libertadores'

COUNTRY_MAP = {
    'VEN': 'Venezuela',
    'URU': 'Uruguay',
    'PAR': 'Paraguay',
    'PER': 'Peru',
    'BOL': 'Bolivia',
    'ECU': 'Ecuador',
    'ARG': 'Argentina',
    'BRA': 'Brazil',
    'COL': 'Colombia',
    'CHI': 'Chile',
    'MEX': 'Mexico',
}

def clean_team_name(team_name):
    """Remove country code like (VEN), (BRA) from team name"""
    if pd.isna(team_name):
        return None, None
    team_name = str(team_name).strip()
    country_code = None
    if '(' in team_name and ')' in team_name:
        start = team_name.rfind('(')
        end = team_name.rfind(')')
        country_code = team_name[start+1:end].strip()
        team_name = team_name[:start].strip()
    return team_name, country_code

def get_team_id(cursor, team_name, country=None):
    """Get team ID by name"""
    if not team_name:
        return None

    # Direct match
    cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    # Try without common prefixes
    clean_name = team_name
    for prefix in ['Club ', 'SC ', 'CD ', 'CSCyD ', 'CA ', 'CF ', 'CSD ', 'FBC ', 'EC ', 'CDC ', 'LDU ', 'CAI ']:
        clean_name = clean_name.replace(prefix, '')
    clean_name = clean_name.strip()

    cursor.execute('SELECT team_id FROM teams WHERE name_en LIKE ?', (f'%{clean_name}%',))
    row = cursor.fetchone()
    if row:
        return row[0]

    # Try first word
    words = team_name.split()
    if words:
        cursor.execute('SELECT team_id FROM teams WHERE name_en LIKE ?', (f'%{words[0]}%',))
        row = cursor.fetchone()
        if row:
            return row[0]

    return None

def add_team(conn, cursor, team_name, country, added_teams):
    """Add a new team to database"""
    if team_name in added_teams:
        return added_teams[team_name]

    cursor.execute('SELECT MAX(team_id) FROM teams')
    max_id = cursor.fetchone()[0] or 0
    new_id = max_id + 1

    cursor.execute('''
        INSERT INTO teams (team_id, name_en, name_cn, country, country_cn)
        VALUES (?, ?, ?, ?, ?)
    ''', (new_id, team_name, team_name, country or 'South America', country or '南美洲'))

    conn.commit()
    added_teams[team_name] = new_id
    print(f'  Added team: {team_name} ({country})')
    return new_id

def import_copa_libertadores():
    print('=' * 60)
    print('Importing Copa Libertadores Data')
    print('=' * 60)

    # Use the all.csv file which has all the data
    csv_file = CSV_DIR + '/copa_libertadores_all.csv'

    df = pd.read_csv(csv_file, encoding='utf-8-sig', low_memory=False)
    df.columns = [c.replace('﻿', '').strip() for c in df.columns]

    print(f'\nLoaded {len(df)} matches from {os.path.basename(csv_file)}')

    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    league_id = 7515
    print(f'League ID: {league_id}')

    # Track added teams
    added_teams = {}

    inserted = 0
    updated = 0
    errors = 0
    team_errors = set()

    for idx, row in df.iterrows():
        try:
            # Parse date
            date = str(row['Date']).strip()
            time_str = str(row.get('Time', '')) if pd.notna(row.get('Time')) else None

            # Clean team names
            home_raw = row['HomeTeam']
            away_raw = row['AwayTeam']

            home_team, home_cc = clean_team_name(home_raw)
            away_team, away_cc = clean_team_name(away_raw)

            home_country = COUNTRY_MAP.get(home_cc, home_cc) if home_cc else None
            away_country = COUNTRY_MAP.get(away_cc, away_cc) if away_cc else None

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
            home_team_id = get_team_id(cursor, home_team, home_country)
            away_team_id = get_team_id(cursor, away_team, away_country)

            # Add missing teams
            if not home_team_id:
                home_team_id = add_team(conn, cursor, home_team, home_country, added_teams)
            if not away_team_id:
                away_team_id = add_team(conn, cursor, away_team, away_country, added_teams)

            if not home_team_id or not away_team_id:
                team_errors.add(home_team)
                team_errors.add(away_team)
                errors += 1
                continue

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
                season = 2025
                match_id = f'libertadores_{season}_{date}_{home_team_id}_vs_{away_team_id}'
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

            if (idx + 1) % 50 == 0:
                conn.commit()
                print(f'Processed {idx + 1}/{len(df)} matches...')

        except Exception as e:
            errors += 1
            if errors < 10:
                print(f'Error at row {idx}: {e}')
            continue

    conn.commit()
    print(f'\nDone! Inserted: {inserted}, Updated: {updated}, Errors: {errors}')
    print(f'Added teams: {len(added_teams)}')

    if team_errors:
        print(f'\nTeam errors ({len(team_errors)}):')
        for t in sorted(team_errors)[:10]:
            print(f'  {t}')

    # Verify
    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (league_id,))
    total = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND home_goals IS NOT NULL', (league_id,))
    with_goals = cursor.fetchone()[0]

    print(f'\nCopa Libertadores matches: {total}')
    print(f'With goals: {with_goals} ({round(with_goals/total*100, 1) if total > 0 else 0}%)')

    conn.close()

if __name__ == '__main__':
    import_copa_libertadores()