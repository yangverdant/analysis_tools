"""Check attribution distribution and schema in lottery_validation."""
import sqlite3

conn = sqlite3.connect('/opt/football_tools/data/football_v2.db')
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT play_type, attribution, COUNT(*) as cnt,
           AVG(predicted_prob) as avg_prob,
           SUM(is_correct) as correct
    FROM lottery_validation
    WHERE validated_at >= datetime('now', '-30 days')
    GROUP BY play_type, attribution
    ORDER BY play_type, cnt DESC
""").fetchall()

print('=== attribution distribution (30d) ===')
for r in rows:
    avg_acc = (r['correct'] / r['cnt']) if r['cnt'] > 0 else 0
    prob = r['avg_prob'] or 0
    print(f"{r['play_type']:6} | {r['attribution'] or 'NULL':30} | n={r['cnt']:3} | avg_prob={prob:.3f} | acc={avg_acc:.0%}")

print()
cols = conn.execute('PRAGMA table_info(lottery_validation)').fetchall()
print('=== lottery_validation schema ===')
for c in cols:
    print(f"  {c[1]} {c[2]}")

print()
# Show sample attribution_reason values
print('=== sample attribution_detail (10 rows) ===')
rows = conn.execute("""
    SELECT play_type, attribution, predicted_prob, actual_result, predicted_result,
           attribution_detail
    FROM lottery_validation
    WHERE attribution IS NOT NULL
    AND validated_at >= datetime('now', '-30 days')
    ORDER BY validated_at DESC
    LIMIT 15
""").fetchall()
for r in rows:
    print(f"{r['play_type']:6} | {r['attribution']:25} | prob={r['predicted_prob'] or 0:.3f} | pred={r['predicted_result']} actual={r['actual_result']} | detail={r['attribution_detail']}")

print()
# Check what columns exist for scenario
print('=== scenario distribution ===')
rows = conn.execute("""
    SELECT scenario_type, play_type, COUNT(*) as cnt, SUM(is_correct) as correct
    FROM lottery_validation
    WHERE validated_at >= datetime('now', '-30 days')
    GROUP BY scenario_type, play_type
    ORDER BY cnt DESC
""").fetchall()
for r in rows:
    acc = (r['correct'] / r['cnt']) if r['cnt'] > 0 else 0
    print(f"{r['scenario_type'] or 'NULL':25} | {r['play_type']:6} | n={r['cnt']:3} | acc={acc:.0%}")
