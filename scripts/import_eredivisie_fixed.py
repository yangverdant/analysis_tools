"""
Import Eredivisie complete data - fixed version
"""
import pandas as pd
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'football_v2.db')
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', '01_europe_leagues', 'eredivisie', 'eredivisie_all.csv')

def parse_date(date_str):
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

# Team mapping
TEAM_MAP = {
    'Ajax': 'Ajax', 'AZ Alkmaar': 'AZ', 'Feyenoord': 'Feyenoord', 'PSV Eindhoven': 'PSV',
    'Vitesse': 'Vitesse', 'Utrecht': 'Utrecht', 'Twente': 'Twente', 'Heerenveen': 'Heerenveen',
    'Groningen': 'Groningen', 'NAC Breda': 'NAC', 'Roda JC': 'Roda', 'Willem II': 'Willem II',
    'Sparta': 'Sparta', 'Go Ahead Eagles': 'Go Ahead Eagles', 'Nijmegen': 'NEC',
    'Waalwijk': 'RKC', 'Graafschap': 'Graafschap', 'Roosendaal': 'Roosendaal',
    'For Sittard': 'Sittard', 'Almere City': 'Almere City', 'Excelsior': 'Excelsior',
    'Venlo': 'Venlo', 'Heracles': 'Heracles', 'Cambuur': 'Cambuur', 'Volendam': 'Volendam',
    'Den Haag': 'Den Haag', 'Zwolle': 'Zwolle', 'FC Emmen': 'FC Emmen', 'Den Bosch': 'Den Bosch',
    'Dordrecht': 'Dordrecht', 'Telstar': 'Telstar', 'ADO Den Haag': 'Den Haag',
    'RKC Waalwijk': 'RKC', 'VVV Venlo': 'Venlo', 'PEC Zwolle': 'Zwolle',
    'SC Cambuur': 'Cambuur', 'FC Volendam': 'Volendam', 'NEC Nijmegen': 'NEC',
}

def get_team_id(cursor, team_name):
    db_name = TEAM_MAP.get(team_name, team_name)
    cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (db_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute('SELECT team_id FROM teams WHERE name_en LIKE ?', (f'%{db_name}%',))
    row = cursor.fetchone()
    return row[0] if row else None

def import_eredivisie():
    print("Importing Eredivisie Data...")

    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig', low_memory=False)
    df.columns = [c.replace('﻿', '').strip() for c in df.columns]
    df['HomeTeam'] = df['HomeTeam'].str.strip()
    df['AwayTeam'] = df['AwayTeam'].str.strip()

    print(f"Loaded {len(df)} matches")

    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    cursor.execute('SELECT league_id FROM leagues WHERE name_en = "Eredivisie"')
    league_id = cursor.fetchone()[0]

    updated, inserted, errors = 0, 0, 0

    for idx, row in df.iterrows():
        try:
            season_str = str(row.get('Season', ''))
            if '-' not in season_str:
                continue
            season = int(season_str.split('-')[0])

            date = parse_date(str(row['Date']))
            home_team = row['HomeTeam']
            away_team = row['AwayTeam']

            home_goals = int(row['FTHG']) if pd.notna(row.get('FTHG')) else None
            away_goals = int(row['FTAG']) if pd.notna(row.get('FTAG')) else None

            home_shots = int(row['HS']) if pd.notna(row.get('HS')) else None
            away_shots = int(row['AS']) if pd.notna(row.get('AS')) else None
            home_shots_target = int(row['HST']) if pd.notna(row.get('HST')) else None
            away_shots_target = int(row['AST']) if pd.notna(row.get('AST')) else None

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

            home_team_id = get_team_id(cursor, home_team)
            away_team_id = get_team_id(cursor, away_team)

            if not home_team_id or not away_team_id:
                errors += 1
                continue

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
                        odds_home = COALESCE(odds_home, ?),
                        odds_draw = COALESCE(odds_draw, ?),
                        odds_away = COALESCE(odds_away, ?),
                        odds_home_max = COALESCE(odds_home_max, ?),
                        odds_draw_max = COALESCE(odds_draw_max, ?),
                        odds_away_max = COALESCE(odds_away_max, ?),
                        odds_home_avg = COALESCE(odds_home_avg, ?),
                        odds_draw_avg = COALESCE(odds_draw_avg, ?),
                        odds_away_avg = COALESCE(odds_away_avg, ?),
                        odds_b365_home = COALESCE(odds_b365_home, ?),
                        odds_b365_draw = COALESCE(odds_b365_draw, ?),
                        odds_b365_away = COALESCE(odds_b365_away, ?),
                        status = 'finished'
                    WHERE match_id = ?
                ''', (
                    home_goals, away_goals,
                    home_shots, away_shots, home_shots_target, away_shots_target,
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
                        odds_home, odds_draw, odds_away,
                        odds_home_max, odds_draw_max, odds_away_max,
                        odds_home_avg, odds_draw_avg, odds_away_avg,
                        odds_b365_home, odds_b365_draw, odds_b365_away,
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'finished')
                ''', (
                    match_id, league_id, season, date,
                    home_team_id, away_team_id, home_goals, away_goals,
                    home_shots, away_shots, home_shots_target, away_shots_target,
                    odds_home, odds_draw, odds_away,
                    odds_home_max, odds_draw_max, odds_away_max,
                    odds_home_avg, odds_draw_avg, odds_away_avg,
                    odds_b365_home, odds_b365_draw, odds_b365_away
                ))
                inserted += 1

            if (idx + 1) % 1000 == 0:
                conn.commit()
                print(f'Processed {idx + 1}/{len(df)}...')

        except Exception as e:
            errors += 1
            continue

    conn.commit()
    print(f'Done! Updated: {updated}, Inserted: {inserted}, Errors: {errors}')

    # Verify
    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (league_id,))
    total = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND odds_home IS NOT NULL', (league_id,))
    with_odds = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND home_shots IS NOT NULL', (league_id,))
    with_shots = cursor.fetchone()[0]

    print(f'Eredivisie: {total} matches, {with_odds} with odds ({round(with_odds/total*100,1)}%), {with_shots} with shots ({round(with_shots/total*100,1)}%)')

    conn.close()

if __name__ == '__main__':
    import_eredivisie()