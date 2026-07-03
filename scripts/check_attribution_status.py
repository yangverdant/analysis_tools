"""Check daily attribution status."""
import sqlite3
conn = sqlite3.connect('/opt/football_tools/data/football_v2.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT DATE(validated_at) as day,
           COUNT(*) as total,
           SUM(CASE WHEN attribution IS NOT NULL THEN 1 ELSE 0 END) as with_attr,
           SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) as errors,
           SUM(CASE WHEN is_correct = 0 AND attribution IS NOT NULL THEN 1 ELSE 0 END) as errors_with_attr
    FROM lottery_validation
    WHERE validated_at >= date('now', '-12 days')
    GROUP BY DATE(validated_at)
    ORDER BY day DESC
""").fetchall()
print('=== Daily attribution status ===')
for r in rows:
    pct = (r['errors_with_attr'] / r['errors'] * 100) if r['errors'] > 0 else 0
    print(f"  {r['day']} | total={r['total']:3} | with_attr={r['with_attr']:3} | errors={r['errors']:3} | err_with_attr={r['errors_with_attr']:3} ({pct:.0f}%)")

# Check recent automation_center runs
print()
print('=== Recent automation tasks ===')
rows = conn.execute("""
    SELECT task_name, status, started_at, completed_at, error_message
    FROM automation_tasks
    ORDER BY started_at DESC LIMIT 10
""").fetchall()
for r in rows:
    print(f"  {r['started_at']} | {r['task_name']:25} | {r['status']:10} | {r['error_message'] or ''}")
conn.close()
