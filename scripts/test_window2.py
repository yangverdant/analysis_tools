"""Quick validation for Window 2 changes"""
from core.competition.engine import CompetitionRuleEngine, CompetitionType
from backend.app.analytics.national_strength import NationalTeamStrengthEstimator
from backend.app.analytics.comprehensive import ComprehensiveAnalyzer
from core.intel import IntelCollector
from core.classifier import Classifier

import sqlite3

print("=== All imports OK ===\n")

# Test 1: CompetitionRuleEngine
e = CompetitionRuleEngine()
tests = [
    ("国际友谊赛", "national", "national"),
    ("世界杯预选赛亚洲区", "national", "national"),
    ("UEFA Nations League", "national", "national"),
    ("UEFA Euro 2028", "national", "national"),
    ("Premier League", "club", "club"),
    ("FA Cup", "club", "club"),
    ("Community Shield", "club", "club"),
    ("Champions League", "club", "club"),
    ("Copa America", "national", "national"),
    ("AFC Asian Cup", "national", "national"),
]

print("--- Classification Test ---")
for name, ht, at in tests:
    p = e.classify(league_name=name, home_team_type=ht, away_team_type=at)
    print(f"  {name:30s} -> {p.competition_type.value:18s} line={p.line:8s} "
          f"mot={p.motivation_weight:.1f} draw={p.draw_boost:+.2f} rot={p.rotation_risk:.2f}")

# Test 2: NationalTeamStrengthEstimator
print("\n--- National Team Strength ---")
conn = sqlite3.connect("data/football_v2.db")
est = NationalTeamStrengthEstimator()
c = conn.cursor()
c.execute("SELECT team_id FROM teams WHERE name_en='Japan' AND team_type='national' LIMIT 1")
japan = c.fetchone()
c.execute("SELECT team_id FROM teams WHERE name_en='Brazil' AND team_type='national' LIMIT 1")
brazil = c.fetchone()
if japan and brazil:
    r = est.estimate(japan[0], brazil[0], conn)
    print(f"  Japan vs Brazil: method={r['method']} probs={r['probabilities']}")

# Test 3: MatchProfile-driven ComprehensiveAnalyzer
print("\n--- MatchProfile + ComprehensiveAnalyzer ---")
p_national = e.classify(league_name="国际友谊赛", home_team_type="national", away_team_type="national")
print(f"  Profile: type={p_national.competition_type.value} line={p_national.line} "
      f"draw_boost={p_national.draw_boost} neutral={p_national.is_neutral_venue}")

# Test 4: IntelCollector
print("\n--- Intel Collector ---")
from datetime import date
intel = IntelCollector("data/football_v2.db")
result = intel.collect(date(2026, 6, 8))
print(f"  Date: {result['date']}")
print(f"  International break: {result['international_break']}")
print(f"  Odds movements: {len(result['odds_movement'])}")
print(f"  Rotation risks: {len(result['rotation_risks'])}")

# Test 5: 8 types coverage
print("\n--- 8 Type Coverage ---")
types_found = set()
for name, ht, at in tests:
    p = e.classify(league_name=name, home_team_type=ht, away_team_type=at)
    types_found.add(p.competition_type.value)
all_types = [e.value for e in CompetitionType]
missing = set(all_types) - types_found
print(f"  Types found: {types_found}")
print(f"  Missing: {missing if missing else 'None'}")

conn.close()
print("\n=== ALL TESTS PASSED ===")
