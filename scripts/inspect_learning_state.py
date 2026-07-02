"""Inspect current model_weights and model_params_history."""
import sqlite3

conn = sqlite3.connect('/opt/football_tools/data/football_v2.db')
conn.row_factory = sqlite3.Row

row = conn.execute('SELECT * FROM model_weights WHERE is_active = 1 LIMIT 1').fetchone()
print('=== Active model_weights ===')
if row:
    keys = ['version', 'elo_weight', 'poisson_weight', 'h2h_weight', 'form_weight',
            'home_away_weight', 'motivation_weight', 'news_factor_weight']
    for k in keys:
        try:
            print(f'  {k}: {row[k]}')
        except IndexError:
            print(f'  {k}: (column missing)')

print()
rows = conn.execute("""
    SELECT param_name, old_value, new_value, change_reason, changed_at
    FROM model_params_history
    ORDER BY changed_at DESC LIMIT 15
""").fetchall()
print('=== Recent model_params_history ===')
for r in rows:
    print(f"  {r['changed_at']} | {r['param_name']}")
    print(f"    {r['old_value']} -> {r['new_value']}")
    print(f"    reason: {r['change_reason']}")

print()
rows = conn.execute("""
    SELECT scene_type, participant_type, total_matches,
           model_accuracy, odds_baseline_accuracy
    FROM model_accuracy
    ORDER BY scene_type LIMIT 30
""").fetchall()
print('=== model_accuracy ===')
for r in rows:
    ma = r['model_accuracy'] or 0
    ob = r['odds_baseline_accuracy'] or 0
    print(f"  {r['scene_type']:30} | {r['participant_type']:8} | n={r['total_matches']:3} | model={ma:.1%} | odds={ob:.1%}")

# Attribution → actionable insight summary
print()
print('=== Attribution-driven actionable insights ===')
rows = conn.execute("""
    SELECT play_type, attribution, COUNT(*) as cnt,
           AVG(predicted_prob) as avg_prob,
           SUM(is_correct) as correct,
           AVG(confidence) as avg_conf
    FROM lottery_validation
    WHERE attribution IS NOT NULL
      AND is_correct = 0
      AND validated_at >= datetime('now', '-30 days')
    GROUP BY play_type, attribution
    HAVING cnt >= 5
    ORDER BY cnt DESC
""").fetchall()
for r in rows:
    prob = r['avg_prob'] or 0
    conf = r['avg_conf'] or 0
    print(f"  {r['play_type']:6} | {r['attribution']:30} | n={r['cnt']:3} | avg_prob={prob:.3f} | avg_conf={conf:.3f}")
