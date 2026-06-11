"""
Import Eredivisie (Dutch Premier League) complete data - Fixed version
- Match data, odds, statistics
- Add missing teams with stadium info
"""

import pandas as pd
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'football_v2.db')
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', '01_europe_leagues', 'eredivisie', 'eredivisie_all.csv')

def parse_date(date_str):
    """Convert DD-MM-YY -> YYYY-MM-DD"""
    try:
        if '-' in str(date_str):
            parts = str(date_str).split('-')
            if len(parts) == 3:
                day, month, year = parts
                if len(year) == 2:
                    year = '20' + year if int(year) < 50 else '19' + year
                return f'{year}-{month.zfill(2)}-{day.zfill(2)}'
    except:
        pass
    return date_str

# Dutch team name mappings - CSV name -> DB name
TEAM_MAP = {
    'Ajax': 'Ajax',
    'AZ Alkmaar': 'AZ',
    'Feyenoord': 'Feyenoord',
    'PSV Eindhoven': 'PSV',
    'Vitesse': 'Vitesse',
    'Utrecht': 'Utrecht',
    'Twente': 'Twente',
    'Heerenveen': 'Heerenveen',
    'Groningen': 'Groningen',
    'NAC Breda': 'NAC',
    'Roda JC': 'Roda',
    'Roda': 'Roda',
    'Willem II': 'Willem II',
    'Sparta': 'Sparta',
    'Sparta Rotterdam': 'Sparta Rotterdam',
    'Go Ahead Eagles': 'Go Ahead Eagles',
    'Nijmegen': 'NEC',
    'NEC Nijmegen': 'NEC',
    'Waalwijk': 'Waalwijk',
    'RKC Waalwijk': 'RKC',
    'Graafschap': 'Graafschap',
    'De Graafschap': 'Graafschap',
    'Roosendaal': 'Roosendaal',
    'RBC Roosendaal': 'Roosendaal',
    'For Sittard': 'Fortuna Sittard',
    'Fortuna Sittard': 'Fortuna Sittard',
    'Almere City': 'Almere City',
    'Excelsior': 'Excelsior',
    'VVV Venlo': 'Venlo',
    'Venlo': 'Venlo',
    'Heracles': 'Heracles',
    'Heracles Almelo': 'Heracles',
    'Cambuur': 'Cambuur',
    'SC Cambuur': 'Cambuur',
    'Volendam': 'Volendam',
    'FC Volendam': 'Volendam',
    'Den Haag': 'ADO Den Haag',
    'ADO Den Haag': 'ADO Den Haag',
    'Zwolle': 'Zwolle',
    'PEC Zwolle': 'Zwolle',
    'FC Emmen': 'Emmen',
    'Emmen': 'Emmen',
    'Den Bosch': 'Den Bosch',
    'FC Den Bosch': 'Den Bosch',
    'Dordrecht': 'Dordrecht',
    'FC Dordrecht': 'Dordrecht',
    'Telstar': 'Telstar',
    'AZ': 'AZ',
    'NEC': 'NEC',
    'RKC': 'RKC',
    'PSV': 'PSV',
    'Sittard': 'Fortuna Sittard',
}

# Teams to add if missing
MISSING_TEAMS = [
    ('Roda', '罗达JC', 'Kerkrade', 'Parkstad Limburg Stadion', 19979),
    ('Graafschap', '格拉夫沙普', 'Doetinchem', 'De Vijverberg', 13500),
    ('Roosendaal', '罗斯达尔', 'Roosendaal', 'Vast & Goed Stadion', 6500),
    ('Fortuna Sittard', '幸运薛达', 'Sittard', 'Fortuna Sittard Stadion', 12500),
    ('Venlo', '芬洛', 'Venlo', 'De Koel', 8100),
    ('ADO Den Haag', '海牙', 'Den Haag', 'Cars Jeans Stadion', 15000),
    ('Zwolle', '兹沃勒', 'Zwolle', 'MAC3PARK Stadion', 14000),
    ('Emmen', '埃门', 'Emmen', 'De Oude Meerdijk', 8500),
    ('Den Bosch', '登博斯', "'s-Hertogenbosch", 'De Vliert', 9000),
    ('Dordrecht', '多德勒支', 'Dordrecht', 'GN Bouw Stadion', 4100),
]

def get_team_id(cursor, team_name):
    """Get team ID by name"""
    # Strip whitespace
    team_name = team_name.strip() if isinstance(team_name, str) else team_name
    if not team_name:
        return None

    # Check mapping first
    if team_name in TEAM_MAP:
        db_name = TEAM_MAP[team_name]
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (db_name,))
        row = cursor.fetchone()
        if row:
            return row[0]

    # Direct match
    cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    # Fuzzy match - strip and try again
    cursor.execute('SELECT team_id FROM teams WHERE name_en LIKE ?', (f'%{team_name.strip()}%',))
    row = cursor.fetchone()
    if row:
        return row[0]

    return None

def add_missing_teams(conn, cursor):
    """Add missing Dutch teams"""
    added = 0
    for name_en, name_cn, city, stadium, capacity in MISSING_TEAMS:
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (name_en,))
        if not cursor.fetchone():
            cursor.execute('SELECT MAX(team_id) FROM teams')
            max_id = cursor.fetchone()[0] or 0
            new_id = max_id + 1 + added

            cursor.execute('''
                INSERT INTO teams (team_id, name_en, name_cn, country, country_cn, stadium, stadium_capacity)
                VALUES (?, ?, ?, 'Netherlands', 'Netherlands', ?, ?)
            ''', (new_id, name_en, name_cn, stadium, capacity))
            added += 1
            print(f'  Added team: {name_en}')

    conn.commit()
    return added

def import_eredivisie():
    print('=' * 60)
    print('Importing Eredivisie Complete Data')
    print('=' * 60)

    # Read CSV
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig', low_memory=False)
    df.columns = [c.replace('﻿', '').strip() for c in df.columns]

    # Strip team names
    df['HomeTeam'] = df['HomeTeam'].astype(str).str.strip()
    df['AwayTeam'] = df['AwayTeam'].astype(str).str.strip()

    print(f'\nLoaded {len(df)} matches from CSV')

    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    # Add missing teams first
    print('\nAdding missing teams...')
    add_missing_teams(conn, cursor)

    # Get league ID
    cursor.execute('SELECT league_id FROM leagues WHERE name_en = "Eredivisie"')
    league_row = cursor.fetchone()
    league_id = league_row[0] if league_row else 14

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

    updated = 0
    inserted = 0
    errors = 0
    team_errors = set()

    for idx, row in df.iterrows():
        try:
            # Parse season
            season_str = str(row.get('Season', ''))
            if '-' not in season_str:
                continue
            season = int(season_str.split('-')[0])

            # Parse date
            date = parse_date(str(row['Date']))

            home_team = row['HomeTeam']
            away_team = row['AwayTeam']

            if home_team == 'nan' or away_team == 'nan':
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
            home_team_id = get_team_id(cursor, home_team)
            away_team_id = get_team_id(cursor, away_team)

            if not home_team_id:
                team_errors.add(home_team)
                errors += 1
                continue
            if not away_team_id:
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
                    home_goals, away_goals,
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
                match_id = f'eredivisie_{season}_{date}_{home_team_id}_vs_{away_team_id}'
                cursor.execute('''
                    INSERT INTO matches (
                        match_id, league_id, season_id, match_date,
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
                    match_id, league_id, season, date,
                    home_team_id, away_team_id, home_goals, away_goals,
                    home_shots, away_shots, home_shots_target, away_shots_target,
                    home_corners, away_corners, home_fouls, away_fouls,
                    odds_home, odds_draw, odds_away,
                    odds_home_max, odds_draw_max, odds_away_max,
                    odds_home_avg, odds_draw_avg, odds_away_avg,
                    odds_b365_home, odds_b365_draw, odds_b365_away
                ))
                inserted += 1

            if (idx + 1) % 1000 == 0:
                conn.commit()
                print(f'Processed {idx + 1}/{len(df)} matches...')

        except Exception as e:
            errors += 1
            continue

    conn.commit()
    print(f'\nDone! Updated: {updated}, Inserted: {inserted}, Errors: {errors}')

    if team_errors:
        print(f'\nTeam mapping errors ({len(team_errors)} teams):')
        for t in sorted(team_errors):
            print(f'  {t}')

    # Verify
    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (league_id,))
    total = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND odds_home IS NOT NULL', (league_id,))
    with_odds = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND home_shots IS NOT NULL', (league_id,))
    with_shots = cursor.fetchone()[0]

    print(f'\nEredivisie matches: {total}')
    print(f'With odds: {with_odds} ({round(with_odds/total*100, 1) if total > 0 else 0}%)')
    print(f'With shots: {with_shots} ({round(with_shots/total*100, 1) if total > 0 else 0}%)')

    conn.close()

if __name__ == '__main__':
    import_eredivisie()
