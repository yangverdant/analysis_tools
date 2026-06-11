"""
Import Allsvenskan (Swedish Premier League) odds data from CSV files
- Match date/time
- Odds data (B365, BW, IW, WH, VC, PS, Max, Avg)
- Match statistics
"""

import pandas as pd
import sqlite3
import os
import time
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'football_v2.db')
CSV_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', '01_europe_leagues', 'allsvenskan')

def parse_date(date_str):
    """Convert date format DD/MM/YYYY -> YYYY-MM-DD"""
    try:
        parts = date_str.split('/')
        if len(parts) == 3:
            day, month, year = parts
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except:
        pass
    return date_str

def get_team_id(cursor, team_name):
    """Get team ID by name"""
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

def import_allsvenskan_odds():
    """Import Allsvenskan odds data"""
    print("=" * 60)
    print("Importing Allsvenskan Odds Data")
    print("=" * 60)

    # Get all CSV files
    csv_files = sorted([f for f in os.listdir(CSV_DIR) if f.endswith('.csv')])
    print(f"\nFound {len(csv_files)} CSV files")

    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    # Get league ID
    cursor.execute("SELECT league_id FROM leagues WHERE name_en = 'Allsvenskan'")
    league_row = cursor.fetchone()
    league_id = league_row[0] if league_row else 3

    print(f"League ID: {league_id}")

    # Check if odds columns exist
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

    total_updated = 0
    total_inserted = 0
    total_errors = 0

    for csv_file in csv_files:
        csv_path = os.path.join(CSV_DIR, csv_file)
        print(f"\nProcessing: {csv_file}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
        except:
            try:
                df = pd.read_csv(csv_path, encoding='latin-1')
            except Exception as e:
                print(f"  Error reading file: {e}")
                total_errors += 1
                continue

        # Clean column names
        df.columns = [c.replace('﻿', '').strip() for c in df.columns]

        if len(df) == 0:
            continue

        print(f"  {len(df)} matches in file")

        file_updated = 0
        file_inserted = 0

        for idx, row in df.iterrows():
            try:
                # Parse data
                date_str = str(row.get('Date', ''))
                if not date_str or date_str == 'nan':
                    continue

                date = parse_date(date_str)
                time_str = str(row.get('Time', '')) if pd.notna(row.get('Time')) else None

                home_team = row.get('HomeTeam', '')
                away_team = row.get('AwayTeam', '')

                if not home_team or not away_team:
                    continue

                home_goals = int(row['FTHG']) if pd.notna(row.get('FTHG')) else None
                away_goals = int(row['FTAG']) if pd.notna(row.get('FTAG')) else None

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

                if not home_team_id or not away_team_id:
                    continue

                # Extract season from filename (e.g., allsvenskan_2024-25.csv -> 2024)
                season_str = csv_file.replace('allsvenskan_', '').replace('.csv', '')
                try:
                    season = int(season_str.split('-')[0])
                except:
                    season = None

                # Check if match exists
                cursor.execute("""
                    SELECT match_id FROM matches
                    WHERE league_id = ? AND match_date = ?
                    AND home_team_id = ? AND away_team_id = ?
                """, (league_id, date, home_team_id, away_team_id))

                existing = cursor.fetchone()

                if existing:
                    # Update existing match
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
                    file_updated += 1
                else:
                    # Insert new match
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
                    file_inserted += 1

            except Exception as e:
                total_errors += 1
                continue

        conn.commit()
        print(f"  Updated: {file_updated}, Inserted: {file_inserted}")
        total_updated += file_updated
        total_inserted += file_inserted

        time.sleep(0.5)  # Avoid database lock

    print(f"\n{'=' * 60}")
    print(f"Total Updated: {total_updated}")
    print(f"Total Inserted: {total_inserted}")
    print(f"Total Errors: {total_errors}")

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
