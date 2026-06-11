"""
Import Allsvenskan odds data from sweden CSV files
- Match date/time
- Odds data (PSC, Max, Avg, Bet365)
"""

import pandas as pd
import sqlite3
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'football_v2.db')
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', '01_leagues', 'sweden', 'allsvenskan_raw.csv')

def parse_date(date_str):
    """Convert DD/MM/YYYY -> YYYY-MM-DD"""
    try:
        parts = date_str.split('/')
        if len(parts) == 3:
            day, month, year = parts
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except:
        pass
    return date_str

# Comprehensive team name mapping
TEAM_MAPPINGS = {
    # Swedish teams
    'AIK': 'AIK',
    'Malmo FF': 'Malmo FF',
    'Elfsborg': 'Elfsborg',
    'Goteborg': 'Goteborg',
    'Djurgarden': 'Djurgarden',
    'Hacken': 'Hacken',
    'Norrkoping': 'Norrkoping',
    'Kalmar': 'Kalmar',
    'Halmstad': 'Halmstad',
    'Mjallby': 'Mjallby',
    'Hammarby': 'Hammarby',
    'Sirius': 'Sirius',
    'Varnamo': 'Varnamo',
    'Varberg': 'Varberg',
    'Degerfors': 'Degerfors',
    'GAIS': 'GAIS',
    'Landskrona': 'Landskrona',
    'Orgryte': 'Orgryte',
    'Oster': 'Oster',
    'Brommapojkarna': 'Brommapojkarna',
    'Vasteras SK': 'Vasteras SK',
    # Missing teams - need to be added or mapped
    'Orebro': None,  # Not in DB
    'Helsingborg': None,  # Not in DB
    'Syrianska': None,  # Not in DB
    'Gefle': None,  # Not in DB
    'Atvidabergs': None,  # Not in DB
    'Sundsvall': None,  # Not in DB
    'Trelleborgs': None,  # Not in DB
    'Osters': None,  # Not in DB
    'Ostersunds': None,  # Not in DB
    'Falkenbergs': None,  # Not in DB
    'Dalkurd': None,  # Not in DB
    'AFC Eskilstuna': None,  # Not in DB
    'Jonkopings': None,  # Not in DB
    'Ljungskile': None,  # Not in DB
    'Brage': None,  # Not in DB
}

def get_team_id(cursor, team_name):
    """Get team ID by name"""
    # Check mapping first
    if team_name in TEAM_MAPPINGS:
        db_name = TEAM_MAPPINGS[team_name]
        if db_name is None:
            return None
        cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (db_name,))
        row = cursor.fetchone()
        if row:
            return row[0]

    # Direct match
    cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (team_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    # Fuzzy match
    cursor.execute("SELECT team_id, name_en FROM teams WHERE name_en LIKE ?", (f"%{team_name}%",))
    row = cursor.fetchone()
    if row:
        return row[0]

    return None

def add_missing_teams(conn, cursor):
    """Add missing teams to database"""
    missing_teams = [
        ('Orebro', '厄勒布鲁', 'Orebro', 'Orebro'),
        ('Helsingborg', '赫尔辛堡', 'Helsingborg', 'Helsingborg'),
        ('Syrianska', '叙利亚人', 'Södertälje', 'Syrianska'),
        ('Gefle', '耶夫勒', 'Gavle', 'Gefle'),
        ('Atvidabergs', '奥特维达贝里', 'Atvidaberghs', 'Atvidabergs'),
        ('Sundsvall', '松兹瓦尔', 'Sundsvall', 'Sundsvall'),
        ('Trelleborgs', '特雷勒堡', 'Trelleborg', 'Trelleborgs'),
        ('Osters', '奥斯特', 'Vaxjo', 'Osters'),
        ('Ostersunds', '厄斯特松德', 'Ostersund', 'Ostersunds'),
        ('Falkenbergs', '法尔肯贝里', 'Falkenberg', 'Falkenbergs'),
        ('Dalkurd', '达尔库德', 'Borlange', 'Dalkurd'),
        ('AFC Eskilstuna', '埃斯基尔斯蒂纳', 'Eskilstuna', 'AFC Eskilstuna'),
        ('Jonkopings', '延雪平', 'Jonkoping', 'Jonkopings'),
        ('Ljungskile', '延斯科莱', 'Ljungskile', 'Ljungskile'),
        ('Brage', '布拉格', 'Borlange', 'Brage'),
    ]

    added = 0
    for name_en, name_cn, city, stadium in missing_teams:
        cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (name_en,))
        if not cursor.fetchone():
            # Get max team_id
            cursor.execute("SELECT MAX(team_id) FROM teams")
            max_id = cursor.fetchone()[0] or 0
            new_id = max_id + 1 + added

            cursor.execute("""
                INSERT INTO teams (team_id, name_en, name_cn, country, country_cn, stadium)
                VALUES (?, ?, ?, 'Sweden', 'Sweden', ?)
            """, (new_id, name_en, name_cn, stadium))
            added += 1
            print(f"Added team: {name_en}")

    conn.commit()
    return added

def import_allsvenskan_odds():
    """Import Allsvenskan odds data"""
    print("=" * 60)
    print("Importing Allsvenskan Odds Data")
    print("=" * 60)

    # Read CSV
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    df.columns = [c.replace('﻿', '').strip() for c in df.columns]

    print(f"\nLoaded {len(df)} matches from CSV")
    print(f"Seasons: {sorted(df['Season'].unique())}")

    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    # Add missing teams first
    print("\nAdding missing teams...")
    add_missing_teams(conn, cursor)

    # Update mappings after adding teams
    global TEAM_MAPPINGS
    TEAM_MAPPINGS = {
        'AIK': 'AIK',
        'Malmo FF': 'Malmo FF',
        'Elfsborg': 'Elfsborg',
        'Goteborg': 'Goteborg',
        'Djurgarden': 'Djurgarden',
        'Hacken': 'Hacken',
        'Norrkoping': 'Norrkoping',
        'Kalmar': 'Kalmar',
        'Halmstad': 'Halmstad',
        'Mjallby': 'Mjallby',
        'Hammarby': 'Hammarby',
        'Sirius': 'Sirius',
        'Varnamo': 'Varnamo',
        'Varberg': 'Varberg',
        'Degerfors': 'Degerfors',
        'GAIS': 'GAIS',
        'Landskrona': 'Landskrona',
        'Orgryte': 'Orgryte',
        'Oster': 'Oster',
        'Brommapojkarna': 'Brommapojkarna',
        'Vasteras SK': 'Vasteras SK',
        'Orebro': 'Orebro',
        'Helsingborg': 'Helsingborg',
        'Syrianska': 'Syrianska',
        'Gefle': 'Gefle',
        'Atvidabergs': 'Atvidabergs',
        'Sundsvall': 'Sundsvall',
        'Trelleborgs': 'Trelleborgs',
        'Osters': 'Osters',
        'Ostersunds': 'Ostersunds',
        'Falkenbergs': 'Falkenbergs',
        'Dalkurd': 'Dalkurd',
        'AFC Eskilstuna': 'AFC Eskilstuna',
        'Jonkopings': 'Jonkopings',
        'Ljungskile': 'Ljungskile',
        'Brage': 'Brage',
    }

    # Get league ID
    cursor.execute("SELECT league_id FROM leagues WHERE name_en = 'Allsvenskan'")
    league_row = cursor.fetchone()
    league_id = league_row[0] if league_row else 3

    print(f"League ID: {league_id}")

    # Check odds columns
    cursor.execute("PRAGMA table_info(matches)")
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
            cursor.execute(f"ALTER TABLE matches ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")

    conn.commit()

    updated = 0
    inserted = 0
    errors = 0

    for idx, row in df.iterrows():
        try:
            # Parse data
            season = int(row['Season'])
            date = parse_date(str(row['Date']))
            time_str = str(row['Time']) if pd.notna(row['Time']) else None

            home_team = row['Home']
            away_team = row['Away']

            home_goals = int(row['HG']) if pd.notna(row['HG']) else None
            away_goals = int(row['AG']) if pd.notna(row['AG']) else None

            # Odds
            odds_home = float(row['PSCH']) if pd.notna(row.get('PSCH')) else None
            odds_draw = float(row['PSCD']) if pd.notna(row.get('PSCD')) else None
            odds_away = float(row['PSCA']) if pd.notna(row.get('PSCA')) else None

            odds_home_max = float(row['MaxCH']) if pd.notna(row.get('MaxCH')) else None
            odds_draw_max = float(row['MaxCD']) if pd.notna(row.get('MaxCD')) else None
            odds_away_max = float(row['MaxCA']) if pd.notna(row.get('MaxCA')) else None

            odds_home_avg = float(row['AvgCH']) if pd.notna(row.get('AvgCH')) else None
            odds_draw_avg = float(row['AvgCD']) if pd.notna(row.get('AvgCD')) else None
            odds_away_avg = float(row['AvgCA']) if pd.notna(row.get('AvgCA')) else None

            odds_b365_home = float(row['B365CH']) if pd.notna(row.get('B365CH')) else None
            odds_b365_draw = float(row['B365CD']) if pd.notna(row.get('B365CD')) else None
            odds_b365_away = float(row['B365CA']) if pd.notna(row.get('B365CA')) else None

            # Get team IDs
            home_team_id = get_team_id(cursor, home_team)
            away_team_id = get_team_id(cursor, away_team)

            if not home_team_id or not away_team_id:
                errors += 1
                continue

            # Check if match exists
            cursor.execute("""
                SELECT match_id FROM matches
                WHERE league_id = ? AND match_date = ?
                AND home_team_id = ? AND away_team_id = ?
            """, (league_id, date, home_team_id, away_team_id))

            existing = cursor.fetchone()

            if existing:
                # Update
                cursor.execute("""
                    UPDATE matches SET
                        match_time = COALESCE(match_time, ?),
                        home_goals = COALESCE(home_goals, ?),
                        away_goals = COALESCE(away_goals, ?),
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
                """, (
                    time_str, home_goals, away_goals,
                    odds_home, odds_draw, odds_away,
                    odds_home_max, odds_draw_max, odds_away_max,
                    odds_home_avg, odds_draw_avg, odds_away_avg,
                    odds_b365_home, odds_b365_draw, odds_b365_away,
                    existing[0]
                ))
                updated += 1
            else:
                # Insert
                match_id = f"allsvenskan_{season}_{date}_{home_team_id}_vs_{away_team_id}"
                cursor.execute("""
                    INSERT INTO matches (
                        match_id, league_id, season_id, match_date, match_time,
                        home_team_id, away_team_id, home_goals, away_goals,
                        odds_home, odds_draw, odds_away,
                        odds_home_max, odds_draw_max, odds_away_max,
                        odds_home_avg, odds_draw_avg, odds_away_avg,
                        odds_b365_home, odds_b365_draw, odds_b365_away,
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'finished')
                """, (
                    match_id, league_id, season, date, time_str,
                    home_team_id, away_team_id, home_goals, away_goals,
                    odds_home, odds_draw, odds_away,
                    odds_home_max, odds_draw_max, odds_away_max,
                    odds_home_avg, odds_draw_avg, odds_away_avg,
                    odds_b365_home, odds_b365_draw, odds_b365_away
                ))
                inserted += 1

            if (idx + 1) % 500 == 0:
                conn.commit()
                print(f"Processed {idx + 1}/{len(df)} matches...")

        except Exception as e:
            errors += 1
            continue

    conn.commit()
    print(f"\nDone! Updated: {updated}, Inserted: {inserted}, Errors: {errors}")

    # Verify
    cursor.execute("""
        SELECT COUNT(*) FROM matches WHERE league_id = ? AND odds_home IS NOT NULL
    """, (league_id,))
    with_odds = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM matches WHERE league_id = ?
    """, (league_id,))
    total = cursor.fetchone()[0]

    print(f"\nAllsvenskan matches with odds: {with_odds}/{total}")
    print(f"Odds coverage: {round(with_odds/total*100, 1) if total > 0 else 0}%")

    conn.close()

if __name__ == "__main__":
    import_allsvenskan_odds()
