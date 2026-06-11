"""
诊断: dp_o值 vs v34_flags的draw_threshold_0.3
为什么dp_o >= 0.30检测不到任何dt30?
"""
import sys, io, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 查几场有draw_threshold_0.3 flag的比赛
matches = conn.execute("""
    SELECT m.match_key, m.date, m.home_team, m.away_team
    FROM matches m
    WHERE m.status='finished' AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
    AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                AND md.source='model' AND md.data_type='model:enhanced_linear')
    AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                AND md.source='factor' AND md.data_type='factor:euro_odds')
    ORDER BY m.date
    LIMIT 20
""").fetchall()

for m in matches:
    mk = m['match_key']
    model_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
        (mk,)).fetchone()
    model_data = json.loads(model_row['data_json'])
    flags = model_data.get('scenario_flags', [])

    if 'draw_threshold_0.3' not in flags:
        continue

    odds_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
        (mk,)).fetchone()
    odds_data = json.loads(odds_row['data_json'])
    dp_o = float(odds_data.get('draw_value', 0) or 0)
    raw_odds = odds_data.get('raw', {})
    avg_dp = float(raw_odds.get('avg_draw_odds', 0) or raw_odds.get('closing_avg_draw_odds', 0) or 0)

    print(f"{m['date']} {m['home_team']} vs {m['away_team']}")
    print(f"  flags={flags}")
    print(f"  draw_value={dp_o} avg_draw_odds={avg_dp}")
    print(f"  dp_o >= 0.30? {dp_o >= 0.30}")
    if avg_dp > 0:
        implied_dp = 1.0 / avg_dp
        print(f"  implied_dp from odds={implied_dp:.4f} >= 0.30? {implied_dp >= 0.30}")

conn.close()