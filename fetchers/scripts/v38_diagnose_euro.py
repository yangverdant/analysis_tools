"""
诊断v5: euro_odds的完整数据结构
确认draw_value的含义
"""
import sys, io, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 看几条euro_odds记录的完整结构
rows = conn.execute("""
    SELECT match_key, data_json
    FROM match_data
    WHERE source='factor' AND data_type='factor:euro_odds'
    LIMIT 5
""").fetchall()

for row in rows:
    data = json.loads(row['data_json'])
    print(f"match_key={row['match_key']}")
    print(f"  top keys: {list(data.keys())}")
    s = json.dumps(data, indent=2, ensure_ascii=False)
    if len(s) > 800:
        s = s[:800] + "..."
    print(f"  data: {s}")
    print()

# 特别查draw_threshold_0.3的比赛的euro_odds
mk = '2024-09-15|mirandes|albacete'
row = conn.execute(
    "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
    (mk,)).fetchone()
if row:
    data = json.loads(row['data_json'])
    print(f"dt30 match: {mk}")
    print(f"  home_value={data.get('home_value')}")
    print(f"  draw_value={data.get('draw_value')}")
    print(f"  away_value={data.get('away_value')}")
    raw = data.get('raw', {})
    print(f"  avg_draw_odds={raw.get('avg_draw_odds')}")
    print(f"  closing_avg_draw_odds={raw.get('closing_avg_draw_odds')}")
    dp = data.get('draw_value', 0)
    print(f"  dp_o type={type(dp)} value={dp}")

conn.close()