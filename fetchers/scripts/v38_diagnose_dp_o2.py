"""
诊断v2: 直接查有draw_threshold_0.3 flag的比赛的dp_o值
"""
import sys, io, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 用JSON search找含draw_threshold_0.3的记录
rows = conn.execute("""
    SELECT md.match_key, md.data_json
    FROM match_data md
    WHERE md.source='model' AND md.data_type='model:enhanced_linear'
    AND md.data_json LIKE '%draw_threshold_0.3%'
    LIMIT 10
""").fetchall()

for row in rows:
    mk = row['match_key']
    model_data = json.loads(row['data_json'])
    flags = model_data.get('scenario_flags', [])
    print(f"match_key={mk}")
    print(f"  flags={flags}")

    # 查euro_odds的draw_value
    odds_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
        (mk,)).fetchone()
    if odds_row:
        odds_data = json.loads(odds_row['data_json'])
        dp_o = float(odds_data.get('draw_value', 0) or 0)
        hp_o = float(odds_data.get('home_value', 0) or 0)
        ap_o = float(odds_data.get('away_value', 0) or 0)
        raw = odds_data.get('raw', {})
        avg_dp_odds = float(raw.get('avg_draw_odds', 0) or raw.get('closing_avg_draw_odds', 0) or 0)
        print(f"  draw_value={dp_o:.4f} home_value={hp_o:.4f} away_value={ap_o:.4f}")
        print(f"  avg_draw_odds={avg_dp_odds:.2f}")
        if avg_dp_odds > 0:
            implied = 1.0/avg_dp_odds
            print(f"  implied_draw_prob={implied:.4f}")
        # 检查: draw_value已经是什么?
        print(f"  dp_o >= 0.30? {dp_o >= 0.30}")
    else:
        print("  NO euro_odds data")

conn.close()