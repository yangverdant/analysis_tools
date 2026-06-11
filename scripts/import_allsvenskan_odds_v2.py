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

def get_team_id(cursor, team_name):
    """Get team ID by name with multiple matching strategies"""
    # Direct match
    cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (team_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    # Common name mappings
    name_mappings = {
        'Malmo FF': ['Malmo FF', 'Malmö FF', 'Malmoe FF'],
        'Elfsborg': ['Elfsborg', 'IF Elfsborg'],
        'Goteborg': ['Goteborg', 'Göteborg', 'IFK Göteborg', 'IFK Goteborg'],
        'Djurgarden': ['Djurgarden', 'Djurgårdens', 'Djurgardens IF'],
        'Hacken': ['Hacken', 'Häcken', 'BK Häcken'],
        'Norrkoping': ['Norrkoping', 'Norrköping', 'IFK Norrköping'],
        'Orebro': ['Orebro', 'Örebro', 'Örebro SK'],
        'Helsingborg': ['Helsingborg', 'Helsingborgs IF'],
        'Syrianska': ['Syrianska', 'Syrianska FC'],
        'Gefle': ['Gefle', 'Gävle', 'Gefle IF'],
        'Atvidabergs': ['Atvidabergs', 'Åtvidabergs', 'Åtvidabergs FF'],
        'Sundsvall': ['Sundsvall', 'GIF Sundsvall'],
        'Varnamo': ['Varnamo', 'Värnamo', 'IFK Värnamo'],
        'Vasteras': ['Vasteras', 'Västerås', 'Västerås SK'],
        'Degerfors': ['Degerfors', 'Degerfors IF'],
        'Halmstad': ['Halmstad', 'Halmstads BK'],
        'Jönköping': ['Jönköping', 'Jönköpings Södra'],
        'Trelleborg': ['Trelleborg', 'Trelleborgs FF'],
        'Landskrona': ['Landskrona', 'Landskrona BoIS'],
        'Orgryte': ['Orgryte', 'Örgryte', 'Örgryte IS'],
        'Oster': ['Oster', 'Öster', 'Jönköpings Östra'],
        'AFC United': ['AFC United', 'AFC Eskilstuna'],
        'Frej': ['Frej', 'IFK Bergsjö'],
    }

    for db_name, variants in name_mappings.items():
        if team_name in variants:
            cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (db_name,))
            row = cursor.fetchone()
            if row:
                return row[0]

    # Fuzzy match
    cursor.execute("SELECT team_id, name_en FROM teams WHERE name_en LIKE ?", (f"%{team_name}%",))
    row = cursor.fetchone()
    if row:
        return row[0]

    return None

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
    not_found_teams = set()

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

            if not home_team_id:
                not_found_teams.add(home_team)
            if not away_team_id:
                not_found_teams.add(away_team)

            if not home_team_id or not away_team_id:
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
            continue

    conn.commit()
    print(f"\nDone! Updated: {updated}, Inserted: {inserted}")

    if not_found_teams:
        print(f"\nTeams not found in database: {sorted(not_found_teams)}")

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
