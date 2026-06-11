"""
诊断v4: 完整查看AH数据结构
"""
import sys, io, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 查几条有AH数据的记录
rows = conn.execute("""
    SELECT match_key, data_json
    FROM match_data
    WHERE source='factor' AND data_type='factor:asian_handicap'
    LIMIT 5
""").fetchall()

for row in rows:
    data = json.loads(row['data_json'])
    print(f"match_key={row['match_key']}")
    print(f"  top keys: {list(data.keys())}")
    raw = data.get('raw', {})
    print(f"  raw keys: {list(raw.keys()) if raw else 'EMPTY'}")
    # 打印完整数据(截断)
    s = json.dumps(data, indent=2, ensure_ascii=False)
    if len(s) > 500:
        s = s[:500] + "..."
    print(f"  data: {s}")
    print()

conn.close()