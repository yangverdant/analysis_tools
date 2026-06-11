"""窗口B集成验证"""
import sqlite3
from datetime import date

# Test 1: imports
print("=== Test 1: Imports ===")
from backend.app.core.analyze import (
    analyze, _load_match_profile, _build_profile_on_the_fly,
    _get_match_odds_baseline, _compute_model_vs_odds, _get_weights_used,
    _dict_to_profile,
)
from backend.app.core.intel import intel, _check_international_break, _odds_to_probs
from core.competition.engine import CompetitionRuleEngine, MatchProfile, CompetitionType
print("  All imports OK")

# Test 2: profile loading (on-the-fly)
print("\n=== Test 2: Profile on-the-fly ===")
DB = "data/football_v2.db"
conn = sqlite3.connect(DB, timeout=10)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get a real match
c.execute("""
    SELECT lm.*, ht.team_type AS home_team_type, at.team_type AS away_team_type
    FROM lottery_matches lm
    LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
    LEFT JOIN teams at ON lm.away_team_id = at.team_id
    WHERE lm.home_team_id IS NOT NULL AND lm.away_team_id IS NOT NULL
    LIMIT 3
""")
matches = [dict(row) for row in c.fetchall()]
conn.close()

for m in matches:
    profile = _build_profile_on_the_fly(DB, m)
    print(f"  {m.get('home_team_cn','?')} vs {m.get('away_team_cn','?')}: "
          f"type={profile.competition_type.value} line={profile.line} "
          f"mot={profile.motivation_weight:.1f} draw={profile.draw_boost:+.2f}")

# Test 3: model_vs_odds
print("\n=== Test 3: Model vs Odds ===")
model_probs = {"home_win": 0.45, "draw": 0.28, "away_win": 0.27}
odds_baseline = {"home_win": 0.42, "draw": 0.30, "away_win": 0.28}
result = _compute_model_vs_odds(model_probs, odds_baseline)
print(f"  model_rec={result['model_rec']} odds_rec={result['odds_rec']} "
      f"agreement={result['agreement']} edge={result['edge']}")

# Test 4: weights by competition type
print("\n=== Test 4: Weights by Type ===")
engine = CompetitionRuleEngine()
for name in ["Premier League", "FA Cup", "国际友谊赛", "世界杯预选赛"]:
    p = engine.classify(league_name=name, home_team_type="club", away_team_type="club")
    if "友谊" in name or "预选" in name:
        p = engine.classify(league_name=name, home_team_type="national", away_team_type="national")
    w = _get_weights_used(p)
    print(f"  {name}: {w['competition_type']} -> {w['weights']}")

# Test 5: international break
print("\n=== Test 5: International Break ===")
for d in [date(2026, 6, 10), date(2026, 6, 15), date(2026, 8, 15)]:
    brk = _check_international_break(d)
    print(f"  {d}: {'BREAK' if brk['is_international_break'] else 'normal'}")

# Test 6: odds parsing
print("\n=== Test 6: Odds Parsing ===")
odds_data = {"3": 2.10, "1": 3.40, "0": 3.50}
probs = _odds_to_probs(odds_data)
print(f"  odds {odds_data} -> probs {probs}")

# Test 7: dict -> profile roundtrip
print("\n=== Test 7: Profile Roundtrip ===")
p1 = engine.classify(league_name="国际友谊赛", home_team_type="national", away_team_type="national")
d1 = p1.to_dict()
p2 = _dict_to_profile(d1)
print(f"  original: {p1.competition_type.value} line={p1.line}")
print(f"  restored: {p2.competition_type.value} line={p2.line}")
assert p1.competition_type == p2.competition_type
print("  Roundtrip OK")

print("\n=== ALL TESTS PASSED ===")
