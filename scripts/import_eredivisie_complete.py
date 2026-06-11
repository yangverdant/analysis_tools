"""
Import Eredivisie (Dutch Premier League) complete data
- Match data, odds, statistics
- Add missing teams with stadium info
- Calculate xG
- Add league rules
"""

import pandas as pd
import sqlite3
import os
import time
from datetime import datetime

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
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except:
        pass
    return date_str

# Dutch team name mappings
TEAM_MAPPINGS = {
    'Ajax': 'Ajax',
    'PSV Eindhoven': 'PSV',
    'PSV': 'PSV',
    'Feyenoord': 'Feyenoord',
    'AZ Alkmaar': 'AZ',
    'AZ': 'AZ',
    'Vitesse': 'Vitesse',
    'Utrecht': 'Utrecht',
    'FC Utrecht': 'Utrecht',
    'Twente': 'Twente',
    'FC Twente': 'Twente',
    'Heerenveen': 'Heerenveen',
    'SC Heerenveen': 'Heerenveen',
    'Groningen': 'Groningen',
    'FC Groningen': 'Groningen',
    'NAC Breda': 'NAC',
    'NAC': 'NAC',
    'Roda JC': 'Roda',
    'Roda': 'Roda',
    'Willem II': 'Willem II',
    'Willem': 'Willem II',
    'Sparta': 'Sparta',
    'Sparta Rotterdam': 'Sparta',
    'Go Ahead Eagles': 'Go Ahead Eagles',
    'NEC': 'NEC',
    'Nijmegen': 'NEC',
    'NEC Nijmegen': 'NEC',
    'Waalwijk': 'Waalwijk',
    'RKC Waalwijk': 'Waalwijk',
    'Graafschap': 'Graafschap',
    'De Graafschap': 'Graafschap',
    'Roosendaal': 'Roosendaal',
    'RBC Roosendaal': 'Roosendaal',
    'For Sittard': 'Fortuna Sittard',
    'Fortuna Sittard': 'Fortuna Sittard',
    'Fortuna': 'Fortuna Sittard',
    'Almere': 'Almere City',
    'Almere City': 'Almere City',
    'Excelsior': 'Excelsior',
    'Venlo': 'Venlo',
    'VVV Venlo': 'Venlo',
    'VVV': 'Venlo',
    'Heracles': 'Heracles',
    'Heracles Almelo': 'Heracles',
    'Cambuur': 'Cambuur',
    'SC Cambuur': 'Cambuur',
    'Volendam': 'Volendam',
    'FC Volendam': 'Volendam',
    'ADO Den Haag': 'ADO Den Haag',
    'Den Haag': 'ADO Den Haag',
    'Zwolle': 'Zwolle',
    'PEC Zwolle': 'Zwolle',
    'Heerenveen': 'Heerenveen',
    'Emmen': 'Emmen',
    'FC Emmen': 'Emmen',
}

def get_team_id(cursor, team_name):
    """Get team ID by name"""
    if team_name in TEAM_MAPPINGS:
        db_name = TEAM_MAPPINGS[team_name]
        cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (db_name,))
        row = cursor.fetchone()
        if row:
            return row[0]

    cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (team_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute("SELECT team_id, name_en FROM teams WHERE name_en LIKE ?", (f"%{team_name}%",))
    row = cursor.fetchone()
    if row:
        return row[0]

    return None

def add_missing_teams(conn, cursor):
    """Add missing Dutch teams"""
    missing_teams = [
        ('Ajax', '阿贾克斯', 'Amsterdam', 'Johan Cruijff Arena', 55865),
        ('PSV', '埃因霍温', 'Eindhoven', 'Philips Stadion', 35119),
        ('Feyenoord', '费耶诺德', 'Rotterdam', 'De Kuip', 51117),
        ('AZ', '阿尔克马尔', 'Alkmaar', 'AFAS Stadion', 19600),
        ('Vitesse', '维特斯', 'Arnhem', 'GelreDome', 21000),
        ('Utrecht', '乌得勒支', 'Utrecht', 'Stadion Woudestein', 23000),
        ('Twente', '特温特', 'Enschede', 'De Grolsch Veste', 30205),
        ('Heerenveen', '海伦芬', 'Heerenveen', 'Abe Lenstra Stadion', 26100),
        ('Groningen', '格罗宁根', 'Groningen', 'Euroborg', 22579),
        ('NAC', 'NAC布雷达', 'Breda', 'Rat Verlegh Stadion', 19000),
        ('Roda', '罗达JC', 'Kerkrade', 'Parkstad Limburg Stadion', 19979),
        ('Willem II', '威廉二世', 'Tilburg', 'Koning Willem II Stadion', 14600),
        ('Sparta', '斯巴达', 'Rotterdam', 'Het Kasteel', 11000),
        ('Go Ahead Eagles', '前进之鹰', 'Deventer', 'De Adelaarshorst', 10200),
        ('NEC', 'NEC奈梅亨', 'Nijmegen', 'Goffertstadion', 12500),
        ('Waalwijk', '瓦尔韦克', 'Waalwijk', 'Mandemakers Stadion', 7500),
        ('Graafschap', '格拉夫沙普', 'Doetinchem', 'De Vijverberg', 13500),
        ('Roosendaal', '罗斯达尔', 'Roosendaal', 'Vast & Goed Stadion', 6500),
        ('Fortuna Sittard', '幸运薛达', 'Sittard', 'Fortuna Sittard Stadion', 12500),
        ('Almere City', '阿尔梅勒城', 'Almere', 'Yankee Stadion', 3050),
        ('Excelsior', '埃克塞尔', 'Rotterdam', 'Stadion Woudestein', 4400),
        ('Venlo', '芬洛', 'Venlo', 'De Koel', 8100),
        ('Heracles', '大力神', 'Almelo', 'Erve Asito', 13500),
        ('Cambuur', '坎布尔', 'Leeuwarden', 'Cambuurstadion', 10500),
        ('Volendam', '沃伦丹', 'Volendam', 'Kras Stadion', 6200),
        ('ADO Den Haag', '海牙', 'Den Haag', 'Cars Jeans Stadion', 15000),
        ('Zwolle', '兹沃勒', 'Zwolle', 'MAC3PARK Stadion', 14000),
        ('Emmen', '埃门', 'Emmen', 'De Oude Meerdijk', 8500),
    ]

    added = 0
    for name_en, name_cn, city, stadium, capacity in missing_teams:
        cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (name_en,))
        if not cursor.fetchone():
            cursor.execute("SELECT MAX(team_id) FROM teams")
            max_id = cursor.fetchone()[0] or 0
            new_id = max_id + 1 + added

            cursor.execute("""
                INSERT INTO teams (team_id, name_en, name_cn, country, country_cn, stadium, stadium_capacity)
                VALUES (?, ?, ?, 'Netherlands', 'Netherlands', ?, ?)
            """, (new_id, name_en, name_cn, stadium, capacity))
            added += 1
            print(f"  Added team: {name_en}")

    conn.commit()
    return added

def import_eredivisie_data():
    """Import Eredivisie complete data"""
    print("=" * 60)
    print("Importing Eredivisie Complete Data")
    print("=" * 60)

    # Read CSV
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    df.columns = [c.replace('﻿', '').strip() for c in df.columns]

    print(f"\nLoaded {len(df)} matches from CSV")

    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    # Add missing teams first
    print("\nAdding missing teams...")
    add_missing_teams(conn, cursor)

    # Get league ID
    cursor.execute("SELECT league_id FROM leagues WHERE name_en = 'Eredivisie'")
    league_row = cursor.fetchone()
    league_id = league_row[0] if league_row else 14

    print(f"League ID: {league_id}")

    # Ensure odds columns exist
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

    conn.commit()

    updated = 0
    inserted = 0
    errors = 0

    for idx, row in df.iterrows():
        try:
            # Parse season
            season_str = str(row.get('Season', ''))
            if '-' in season_str:
                season = int(season_str.split('-')[0])
            else:
                season = 2000

            # Parse date
            date = parse_date(str(row['Date']))
            time_str = str(row.get('Time', '')) if pd.notna(row.get('Time')) else None

            home_team = row['HomeTeam']
            away_team = row['AwayTeam']

            home_goals = int(row['FTHG']) if pd.notna(row.get('FTHG')) else None
            away_goals = int(row['FTAG']) if pd.notna(row.get('FTAG')) else None

            # Shots
            home_shots = int(row['HS']) if pd.notna(row.get('HS')) else None
            away_shots = int(row['AS']) if pd.notna(row.get('AS')) else None
            home_shots_target = int(row['HST']) if pd.notna(row.get('HST')) else None
            away_shots_target = int(row['AST']) if pd.notna(row.get('AST')) else None

            # Corners, fouls, cards
            home_corners = int(row['HC']) if pd.notna(row.get('HC')) else None
            away_corners = int(row['AC']) if pd.notna(row.get('AC')) else None
            home_fouls = int(row['HF']) if pd.notna(row.get('HF')) else None
            away_fouls = int(row['AF']) if pd.notna(row.get('AF')) else None
            home_yellow = int(row['HY']) if pd.notna(row.get('HY')) else None
            away_yellow = int(row['AY']) if pd.notna(row.get('AY')) else None
            home_red = int(row['HR']) if pd.notna(row.get('HR')) else None
            away_red = int(row['AR']) if pd.notna(row.get('AR')) else None

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
                """, (
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
                # Insert
                match_id = f"eredivisie_{season}_{date}_{home_team_id}_vs_{away_team_id}"
                cursor.execute("""
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
                """, (
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

            if (idx + 1) % 1000 == 0:
                conn.commit()
                print(f"Processed {idx + 1}/{len(df)} matches...")

        except Exception as e:
            errors += 1
            continue

    conn.commit()
    print(f"\nDone! Updated: {updated}, Inserted: {inserted}, Errors: {errors}")

    # Verify
    cursor.execute("SELECT COUNT(*) FROM matches WHERE league_id = ?", (league_id,))
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM matches WHERE league_id = ? AND odds_home IS NOT NULL", (league_id,))
    with_odds = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM matches WHERE league_id = ? AND home_shots IS NOT NULL", (league_id,))
    with_shots = cursor.fetchone()[0]

    print(f"\nEredivisie matches: {total}")
    print(f"With odds: {with_odds} ({round(with_odds/total*100,1)}%)")
    print(f"With shots: {with_shots} ({round(with_shots/total*100,1)}%)")

    conn.close()

if __name__ == "__main__":
    import_eredivisie_data()