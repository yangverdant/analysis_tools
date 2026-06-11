"""
Generate standings for Allsvenskan from match data
"""
import sqlite3
import os
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'football_v2.db')

def generate_standings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print('Generating standings for Allsvenskan...')

    # Get all finished matches
    cursor.execute('''
        SELECT season_id, match_date, home_team_id, away_team_id, home_goals, away_goals
        FROM matches
        WHERE league_id = 3
        AND status = 'finished'
        AND home_goals IS NOT NULL
        ORDER BY season_id, match_date
    ''')

    matches = cursor.fetchall()
    print(f'Found {len(matches)} matches')

    # Group by season
    season_matches = defaultdict(list)
    for m in matches:
        season_matches[m[0]].append(m)

    # Calculate standings for each season
    standings_data = []
    for season, season_match_list in season_matches.items():
        team_records = {}

        for m in season_match_list:
            home_team = m[2]
            away_team = m[3]
            home_goals = m[4]
            away_goals = m[5]

            if home_team not in team_records:
                team_records[home_team] = {
                    'played': 0, 'won': 0, 'drawn': 0, 'lost': 0,
                    'gf': 0, 'ga': 0, 'points': 0,
                    'home_played': 0, 'home_won': 0, 'home_drawn': 0, 'home_lost': 0,
                    'home_gf': 0, 'home_ga': 0, 'home_points': 0,
                    'away_played': 0, 'away_won': 0, 'away_drawn': 0, 'away_lost': 0,
                    'away_gf': 0, 'away_ga': 0, 'away_points': 0,
                }
            if away_team not in team_records:
                team_records[away_team] = {
                    'played': 0, 'won': 0, 'drawn': 0, 'lost': 0,
                    'gf': 0, 'ga': 0, 'points': 0,
                    'home_played': 0, 'home_won': 0, 'home_drawn': 0, 'home_lost': 0,
                    'home_gf': 0, 'home_ga': 0, 'home_points': 0,
                    'away_played': 0, 'away_won': 0, 'away_drawn': 0, 'away_lost': 0,
                    'away_gf': 0, 'away_ga': 0, 'away_points': 0,
                }

            # Update overall records
            team_records[home_team]['played'] += 1
            team_records[away_team]['played'] += 1
            team_records[home_team]['gf'] += home_goals
            team_records[home_team]['ga'] += away_goals
            team_records[away_team]['gf'] += away_goals
            team_records[away_team]['ga'] += home_goals

            # Update home/away records
            team_records[home_team]['home_played'] += 1
            team_records[home_team]['home_gf'] += home_goals
            team_records[home_team]['home_ga'] += away_goals

            team_records[away_team]['away_played'] += 1
            team_records[away_team]['away_gf'] += away_goals
            team_records[away_team]['away_ga'] += home_goals

            if home_goals > away_goals:
                team_records[home_team]['won'] += 1
                team_records[home_team]['points'] += 3
                team_records[home_team]['home_won'] += 1
                team_records[home_team]['home_points'] += 3
                team_records[away_team]['lost'] += 1
                team_records[away_team]['away_lost'] += 1
            elif home_goals < away_goals:
                team_records[away_team]['won'] += 1
                team_records[away_team]['points'] += 3
                team_records[away_team]['away_won'] += 1
                team_records[away_team]['away_points'] += 3
                team_records[home_team]['lost'] += 1
                team_records[home_team]['home_lost'] += 1
            else:
                team_records[home_team]['drawn'] += 1
                team_records[home_team]['points'] += 1
                team_records[home_team]['home_drawn'] += 1
                team_records[home_team]['home_points'] += 1
                team_records[away_team]['drawn'] += 1
                team_records[away_team]['points'] += 1
                team_records[away_team]['away_drawn'] += 1
                team_records[away_team]['away_points'] += 1

        # Sort by points
        sorted_teams = sorted(team_records.items(), key=lambda x: (-x[1]['points'], -(x[1]['gf'] - x[1]['ga'])))

        # Insert standings
        for rank, (team_id, record) in enumerate(sorted_teams, 1):
            standings_data.append({
                'league_id': 3,
                'season_id': season,
                'team_id': team_id,
                'position': rank,
                'played': record['played'],
                'won': record['won'],
                'drawn': record['drawn'],
                'lost': record['lost'],
                'goals_for': record['gf'],
                'goals_against': record['ga'],
                'goal_diff': record['gf'] - record['ga'],
                'points': record['points'],
                'home_played': record['home_played'],
                'home_won': record['home_won'],
                'home_drawn': record['home_drawn'],
                'home_lost': record['home_lost'],
                'home_gf': record['home_gf'],
                'home_ga': record['home_ga'],
                'home_points': record['home_points'],
                'away_played': record['away_played'],
                'away_won': record['away_won'],
                'away_drawn': record['away_drawn'],
                'away_lost': record['away_lost'],
                'away_gf': record['away_gf'],
                'away_ga': record['away_ga'],
                'away_points': record['away_points'],
            })

    # Delete existing Allsvenskan standings
    cursor.execute('DELETE FROM standings WHERE league_id = 3')

    # Insert new standings
    for s in standings_data:
        cursor.execute('''
            INSERT INTO standings (
                season_id, league_id, team_id, position,
                played, won, drawn, lost, goals_for, goals_against, goal_diff, points,
                home_played, home_won, home_drawn, home_lost, home_goals_for, home_goals_against, home_points,
                away_played, away_won, away_drawn, away_lost, away_goals_for, away_goals_against, away_points
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            s['season_id'], s['league_id'], s['team_id'], s['position'],
            s['played'], s['won'], s['drawn'], s['lost'],
            s['goals_for'], s['goals_against'], s['goal_diff'], s['points'],
            s['home_played'], s['home_won'], s['home_drawn'], s['home_lost'],
            s['home_gf'], s['home_ga'], s['home_points'],
            s['away_played'], s['away_won'], s['away_drawn'], s['away_lost'],
            s['away_gf'], s['away_ga'], s['away_points']
        ))

    conn.commit()
    print(f'Inserted {len(standings_data)} standings records')

    # Verify
    cursor.execute('SELECT COUNT(*) FROM standings WHERE league_id = 3')
    count = cursor.fetchone()[0]
    print(f'Total Allsvenskan standings: {count}')

    # Show sample
    cursor.execute('''
        SELECT s.season_id, t.name_en, s.position, s.points, s.won, s.drawn, s.lost
        FROM standings s
        JOIN teams t ON s.team_id = t.team_id
        WHERE s.league_id = 3 AND s.position <= 3
        ORDER BY s.season_id DESC, s.position
        LIMIT 15
    ''')
    print('\nTop 3 teams by season:')
    for row in cursor.fetchall():
        print(f'  {row[0]}: {row[1]} - {row[2]}th, {row[3]}pts ({row[4]}W {row[5]}D {row[6]}L)')

    conn.close()

if __name__ == '__main__':
    generate_standings()