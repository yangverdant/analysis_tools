"""
诊断v3: 检查AH数据结构和dt30子群统计
"""
import sys, io, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 统计dt30比赛中AH数据的情况
dt30_with_ah0 = 0; dt30_with_ah_non0 = 0; dt30_no_ah = 0
total_dt30 = 0

rows = conn.execute("""
    SELECT md.match_key, md.data_json
    FROM match_data md
    WHERE md.source='model' AND md.data_type='model:enhanced_linear'
    AND md.data_json LIKE '%draw_threshold_0.3%'
""").fetchall()

print(f"Total dt30 matches: {len(rows)}")

for i, row in enumerate(rows):
    mk = row['match_key']
    model_data = json.loads(row['data_json'])
    flags = model_data.get('scenario_flags', [])

    # 检查是否是dt30
    if 'draw_threshold_0.3' not in flags:
        continue
    total_dt30 += 1

    # 查AH数据
    ah_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
        (mk,)).fetchone()

    if not ah_row:
        dt30_no_ah += 1
        if dt30_no_ah <= 3:
            print(f"  NO AH: {mk}")
        continue

    ah_data = json.loads(ah_row['data_json'])
    raw = ah_data.get('raw', {})

    # 检查各种可能的字段名
    closing_hc = raw.get('closing_handicap', None)
    handicap = raw.get('handicap', None)
    ah_value = ah_data.get('handicap_value', None)

    if i < 5:
        print(f"  {mk}: closing_handicap={closing_hc}, handicap={handicap}, ah_value={ah_value}")
        print(f"    raw keys: {list(raw.keys())}")
        if not raw:
            print(f"    top keys: {list(ah_data.keys())}")

    if closing_hc is not None:
        hc = float(closing_hc)
        if abs(hc) < 0.01:
            dt30_with_ah0 += 1
        else:
            dt30_with_ah_non0 += 1
    elif handicap is not None:
        hc = float(handicap)
        if abs(hc) < 0.01:
            dt30_with_ah0 += 1
        else:
            dt30_with_ah_non0 += 1
    else:
        dt30_no_ah += 1

print(f"\n  dt30总计: {total_dt30}")
print(f"  AH=0: {dt30_with_ah0}")
print(f"  AH≠0: {dt30_with_ah_non0}")
print(f"  无AH/无盘口: {dt30_no_ah}")

conn.close()