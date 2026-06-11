import sys
sys.path.insert(0, 'd:/football_tools/backend')

from app.analytics.h2h import H2HAnalyzer
from app.analytics.form import FormAnalyzer
from app.analytics.elo import EloAnalyzer
import sqlite3, os

DATABASE_PATH = os.path.join('d:/football_tools/data', 'football_v2.db')

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

match_id = 'a_league_2024-25_2024-10-18_central_coast_mariners_vs_melbourne_victory'

conn = get_db()
cursor = conn.cursor()
cursor.execute("SELECT * FROM matches WHERE match_id = ?", (match_id,))
match = dict(cursor.fetchone())
print(f"Match: {match['home_team_id']} vs {match['away_team_id']}")
print(f"Goals: {match.get('home_goals')} - {match.get('away_goals')}")

# Test H2H
try:
    h2h = H2HAnalyzer(conn)
    result = h2h.analyze(match['home_team_id'], match['away_team_id'])
    print(f"H2H OK: {len(result.get('matches', []))} matches")
except Exception as e:
    print(f"H2H Error: {e}")

# Test Form
try:
    form = FormAnalyzer(conn)
    result = form.analyze(match['home_team_id'], match['away_team_id'])
    print(f"Form OK: {result.keys()}")
except Exception as e:
    print(f"Form Error: {e}")

# Test Elo
try:
    elo = EloAnalyzer(conn)
    result = elo.analyze(match['home_team_id'], match['away_team_id'])
    print(f"Elo OK: {result.keys()}")
except Exception as e:
    print(f"Elo Error: {e}")

conn.close()
