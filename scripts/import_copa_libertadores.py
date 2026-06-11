"""
Import Copa Libertadores (South American Champions League) complete data
- Match data, odds, statistics
- Add missing teams with stadium info
"""

import pandas as pd
import sqlite3
import os
import glob

DB_PATH = 'd:/football_tools/data/football_v2.db'
CSV_DIR = 'd:/football_tools/data/06_south_america/copa_libertadores'

# Country code mapping
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
    'MEX': 'Mexico',  # Mexico participated before 2017
}

# Team name cleaning - remove country code suffix
def clean_team_name(team_name):
    """Remove country code like (VEN), (BRA) from team name"""
    if pd.isna(team_name):
        return None, None
    team_name = str(team_name).strip()
    # Extract country code
    country_code = None
    if '(' in team_name and ')' in team_name:
        start = team_name.rfind('(')
        end = team_name.rfind(')')
        country_code = team_name[start+1:end].strip()
        team_name = team_name[:start].strip()
    return team_name, country_code

def parse_date(date_str):
    """Convert YYYY-MM-DD or DD/MM/YYYY to YYYY-MM-DD"""
    try:
        if pd.isna(date_str):
            return None
        date_str = str(date_str).strip()
        if '-' in date_str and len(date_str) == 10:
            return date_str
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 3:
                day, month, year = parts
                return f'{year}-{month.zfill(2)}-{day.zfill(2)}'
    except:
        pass
    return date_str

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
    clean_name = team_name.replace('Club ', '').replace('SC ', '').replace('CD ', '').replace('CSCyD ', '').replace('CA ', '').replace('CF ', '').strip()
    cursor.execute('SELECT team_id FROM teams WHERE name_en LIKE ?', (f'%{clean_name}%',))
    row = cursor.fetchone()
    if row:
        return row[0]

    # Fuzzy match
    cursor.execute('SELECT team_id FROM teams WHERE name_en LIKE ?', (f'%{team_name.split()[0]}%',))
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

    # Chinese name placeholder
    name_cn = team_name  # Use English name as placeholder

    cursor.execute('''
        INSERT INTO teams (team_id, name_en, name_cn, country, country_cn)
        VALUES (?, ?, ?, ?, ?)
    ''', (new_id, team_name, name_cn, country or 'South America', country or '南美洲'))

    conn.commit()
    added_teams[team_name] = new_id
    print(f'  Added team: {team_name} ({country})')
    return new_id

def import_copa_libertadores():
    print('=' * 60)
    print('Importing Copa Libertadores Complete Data')
    print('=' * 60)

    # Find all CSV files
    csv_files = glob.glob(CSV_DIR + '/*.csv')

    # Only use copa_libertadores_all.csv and copa_libertadores_2025.csv which have actual data
    # Other seasonal files are empty (headers only)
    csv_files = [f for f in csv_files if 'copa_libertadores_all' in f or 'copa_libertadores_2025.' in f]
    csv_files.sort()

    print(f'\nFound {len(csv_files)} CSV files')

    # Read all CSV files
    all_matches = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, encoding='utf-8-sig', low_memory=False)
            df.columns = [c.replace('﻿', '').strip() for c in df.columns]

            # Extract season from filename
            filename = os.path.basename(csv_file)
            season = filename.replace('copa_libertadores_', '').replace('.csv', '')
            df['Season'] = season

            all_matches.append(df)
            print(f'  {filename}: {len(df)} matches')
        except Exception as e:
            print(f'  Error reading {csv_file}: {e}')

    if not all_matches:
        print('No CSV files found!')
        return

    # Combine all data
    df = pd.concat(all_matches, ignore_index=True)
    print(f'\nTotal matches: {len(df)}')

    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    # Get league ID
    cursor.execute('SELECT league_id FROM leagues WHERE name_en = "Copa Libertadores"')
    league_row = cursor.fetchone()
    league_id = league_row[0] if league_row else 7515

    print(f'League ID: {league_id}')

    # Check/add odds columns
    cursor.execute('PRAGMA table_info(matches)')
    columns = [c[1] for c in cursor.fetchall()]

    odds_columns = [
        ('odds_home', 'REAL'),
        ('odds_draw', 'REAL'),
        ('odds_away', 'REAL'),
        ('odds_home_max', 'REAL'),
        ('odds_draw_max', 'REAL'),
        ('odds_away_max', 'REAL'),
        ('odds_home_avg', 'REAL'),
        ('odds_draw_avg', 'REAL'),
        ('odds_away_avg', 'REAL'),
        ('odds_b365_home', 'REAL'),
        ('odds_b365_draw', 'REAL'),
        ('odds_b365_away', 'REAL'),
    ]

    for col_name, col_type in odds_columns:
        if col_name not in columns:
            cursor.execute(f'ALTER TABLE matches ADD COLUMN {col_name} {col_type}')

    conn.commit()

    # Track added teams
    added_teams = {}

    updated = 0
    inserted = 0
    errors = 0
    team_errors = set()

    for idx, row in df.iterrows():
        try:
            # Parse season
            season_str = str(row.get('Season', ''))
            if '-' in season_str:
                season = int(season_str.split('-')[0])
            else:
                season = int(season_str) if season_str.isdigit() else 2025

            # Parse date
            date = parse_date(str(row['Date']))
            time_str = str(row.get('Time', '')) if pd.notna(row.get('Time')) else None

            # Clean team names
            home_team_raw = row['HomeTeam']
            away_team_raw = row['AwayTeam']

            home_team, home_country_code = clean_team_name(home_team_raw)
            away_team, away_country_code = clean_team_name(away_team_raw)

            home_country = COUNTRY_MAP.get(home_country_code, home_country_code)
            away_country = COUNTRY_MAP.get(away_country_code, away_country_code)

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

            # Corners, fouls
            home_corners = int(row['HC']) if pd.notna(row.get('HC')) else None
            away_corners = int(row['AC']) if pd.notna(row.get('AC')) else None
            home_fouls = int(row['HF']) if pd.notna(row.get('HF')) else None
            away_fouls = int(row['AF']) if pd.notna(row.get('AF')) else None

            # Odds
            odds_home = float(row['PSH']) if pd.notna(row.get('PSH')) else None
            odds_draw = float(row['PSD']) if pd.notna(row.get('PSD')) else None
            odds_away = float(row['PSA']) if pd.notna(row.get('PSA')) else None

            odds_home_max = float(row['MaxH']) if pd.notna(row.get('MaxH')) else None
            odds_draw_max = float(row['MaxD']) if pd.notna(row.get('MaxD')) else None
            odds_away_max = float(row['MaxA']) if pd.notna(row.get('MaxA')) else None

            odds_home_avg = float(row['AvgH']) if pd.notna(row.get('AvgH')) else None
            odds_draw_avg = float(row['AvgD']) if pd.notna(row.get('AvgD')) else None
            odds_away_avg = float(row['AvgA']) if pd.notna(row.get('AvgA')) else None

            odds_b365_home = float(row['B365H']) if pd.notna(row.get('B365H')) else None
            odds_b365_draw = float(row['B365D']) if pd.notna(row.get('B365D')) else None
            odds_b365_away = float(row['B365A']) if pd.notna(row.get('B365A')) else None

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
                        match_time = COALESCE(match_time, ?),
                        home_goals = COALESCE(home_goals, ?),
                        away_goals = COALESCE(away_goals, ?),
                        home_shots = COALESCE(home_shots, ?),
                        away_shots = COALESCE(away_shots, ?),
                        home_shots_target = COALESCE(home_shots_target, ?),
                        away_shots_target = COALESCE(away_shots_target, ?),
                        home_corners = COALESCE(home_corners, ?),
                        away_corners = COALESCE(away_corners, ?),
                        home_fouls = COALESCE(home_fouls, ?),
                        away_fouls = COALESCE(away_fouls, ?),
                        odds_home = ?,
                        odds_draw = ?,
                        odds_away = ?,
                        odds_home_max = ?,
                        odds_draw_max = ?,
                        odds_away_max = ?,
                        odds_home_avg = ?,
                        odds_draw_avg = ?,
                        odds_away_avg = ?,
                        odds_b365_home = ?,
                        odds_b365_draw = ?,
                        odds_b365_away = ?,
                        status = 'finished'
                    WHERE match_id = ?
                ''', (
                    time_str, home_goals, away_goals,
                    home_shots, away_shots, home_shots_target, away_shots_target,
                    home_corners, away_corners, home_fouls, away_fouls,
                    odds_home, odds_draw, odds_away,
                    odds_home_max, odds_draw_max, odds_away_max,
                    odds_home_avg, odds_draw_avg, odds_away_avg,
                    odds_b365_home, odds_b365_draw, odds_b365_away,
                    existing[0]
                ))
                updated += 1
            else:
                match_id = f'libertadores_{season}_{date}_{home_team_id}_vs_{away_team_id}'
                cursor.execute('''
                    INSERT INTO matches (
                        match_id, league_id, season_id, match_date, match_time,
                        home_team_id, away_team_id, home_goals, away_goals,
                        home_shots, away_shots, home_shots_target, away_shots_target,
                        home_corners, away_corners, home_fouls, away_fouls,
                        odds_home, odds_draw, odds_away,
                        odds_home_max, odds_draw_max, odds_away_max,
                        odds_home_avg, odds_draw_avg, odds_away_avg,
                        odds_b365_home, odds_b365_draw, odds_b365_away,
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'finished')
                ''', (
                    match_id, league_id, season, date, time_str,
                    home_team_id, away_team_id, home_goals, away_goals,
                    home_shots, away_shots, home_shots_target, away_shots_target,
                    home_corners, away_corners, home_fouls, away_fouls,
                    odds_home, odds_draw, odds_away,
                    odds_home_max, odds_draw_max, odds_away_max,
                    odds_home_avg, odds_draw_avg, odds_away_avg,
                    odds_b365_home, odds_b365_draw, odds_b365_away
                ))
                inserted += 1

            if (idx + 1) % 500 == 0:
                conn.commit()
                print(f'Processed {idx + 1}/{len(df)} matches...')

        except Exception as e:
            errors += 1
            continue

    conn.commit()
    print(f'\nDone! Updated: {updated}, Inserted: {inserted}, Errors: {errors}')
    print(f'Added teams: {len(added_teams)}')

    if team_errors:
        print(f'\nTeam mapping errors ({len(team_errors)} teams):')
        for t in sorted(team_errors)[:10]:
            print(f'  {t}')

    # Verify
    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (league_id,))
    total = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND odds_home IS NOT NULL', (league_id,))
    with_odds = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND home_shots IS NOT NULL', (league_id,))
    with_shots = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND home_goals IS NOT NULL', (league_id,))
    with_goals = cursor.fetchone()[0]

    print(f'\nCopa Libertadores matches: {total}')
    print(f'With goals: {with_goals} ({round(with_goals/total*100, 1) if total > 0 else 0}%)')
    print(f'With odds: {with_odds} ({round(with_odds/total*100, 1) if total > 0 else 0}%)')
    print(f'With shots: {with_shots} ({round(with_shots/total*100, 1) if total > 0 else 0}%)')

    conn.close()

if __name__ == '__main__':
    import_copa_libertadores()