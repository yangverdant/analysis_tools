"""
Import tournament player statistics
- European Championship players
- Copa America players
"""
import pandas as pd
import sqlite3
import os

DB_PATH = 'd:/football_tools/data/football_v2.db'

def import_euro_players():
    """Import European Championship player stats"""
    csv_path = 'd:/football_tools/data/players/european_championship/european_championship_players_all.csv'

    if not os.path.exists(csv_path):
        print(f'File not found: {csv_path}')
        return

    df = pd.read_csv(csv_path, encoding='utf-8-sig', low_memory=False)

    # Clean data
    df = df[df['player'].notna() & df['team'].notna()]

    print(f'European Championship players: {len(df)} records')

    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    inserted = 0
    updated = 0

    for idx, row in df.iterrows():
        try:
            player_name = str(row['player']).strip()
            team_name = str(row['team']).strip()
            season = int(row['season']) if pd.notna(row['season']) else None
            nation = str(row['nation']).strip() if pd.notna(row['nation']) else None
            position = str(row['pos']).strip() if pd.notna(row['pos']) else None
            age = int(row['age']) if pd.notna(row['age']) else None

            minutes = int(row['Min']) if pd.notna(row.get('Min')) else None
            goals = int(row['Gls']) if pd.notna(row.get('Gls')) else None
            assists = int(row['Ast']) if pd.notna(row.get('Ast')) else None
            yellow_cards = int(row['CrdY']) if pd.notna(row.get('CrdY')) else None
            red_cards = int(row['CrdR']) if pd.notna(row.get('CrdR')) else None

            if not player_name or not team_name:
                continue

            # Check if player exists
            cursor.execute('''
                SELECT player_id FROM players
                WHERE name_en = ? AND (team_name = ? OR team_name IS NULL)
            ''', (player_name, team_name))

            existing = cursor.fetchone()

            if existing:
                updated += 1
            else:
                cursor.execute('SELECT MAX(player_id) FROM players')
                max_id = cursor.fetchone()[0] or 0
                new_id = max_id + 1

                cursor.execute('''
                    INSERT INTO players (player_id, name_en, name_cn, team_name, position, age, country)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (new_id, player_name, player_name, team_name, position, age, nation))
                inserted += 1

        except Exception as e:
            continue

    conn.commit()
    conn.close()
    print(f'European Championship: Inserted {inserted}, Updated {updated}')

def import_copa_america_players():
    """Import Copa America player stats"""
    csv_path = 'd:/football_tools/data/players/copa_america/copa_america_players_all.csv'

    if not os.path.exists(csv_path):
        print(f'File not found: {csv_path}')
        return

    df = pd.read_csv(csv_path, encoding='utf-8-sig', low_memory=False)

    df = df[df['player'].notna() & df['team'].notna()]

    print(f'Copa America players: {len(df)} records')

    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    inserted = 0
    updated = 0

    for idx, row in df.iterrows():
        try:
            player_name = str(row['player']).strip()
            team_name = str(row['team']).strip()
            season = int(row['season']) if pd.notna(row['season']) else None
            nation = str(row['nation']).strip() if pd.notna(row['nation']) else None
            position = str(row['pos']).strip() if pd.notna(row['pos']) else None

            if not player_name or not team_name:
                continue

            cursor.execute('''
                SELECT player_id FROM players
                WHERE name_en = ? AND (team_name = ? OR team_name IS NULL)
            ''', (player_name, team_name))

            existing = cursor.fetchone()

            if not existing:
                cursor.execute('SELECT MAX(player_id) FROM players')
                max_id = cursor.fetchone()[0] or 0
                new_id = max_id + 1

                cursor.execute('''
                    INSERT INTO players (player_id, name_en, name_cn, team_name, position, country)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (new_id, player_name, player_name, team_name, position, nation))
                inserted += 1

        except Exception as e:
            continue

    conn.commit()
    conn.close()
    print(f'Copa America: Inserted {inserted}, Updated {updated}')

if __name__ == '__main__':
    print('=' * 60)
    print('Importing Tournament Player Statistics')
    print('=' * 60)

    import_euro_players()
    import_copa_america_players()

    print('\\nDone!')