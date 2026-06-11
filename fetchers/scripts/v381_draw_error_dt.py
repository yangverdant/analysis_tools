"""
v3.8.1: 225场draw改错中dt30占比和信号特征
"""
import sys, io, json, sqlite3
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

matches = conn.execute("""
    SELECT m.match_key, m.date, m.home_team, m.away_team,
           m.league_standard, m.home_score, m.away_score
    FROM matches m
    WHERE m.status='finished' AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
    AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                AND md.source='model' AND md.data_type='model:enhanced_linear')
    AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                AND md.source='factor' AND md.data_type='factor:euro_odds')
    ORDER BY m.date
""").fetchall()

lines = []
def p(s=""): lines.append(s)

p("=" * 70)
p("  draw改错(赔率对+模型draw错)的dt30占比和信号特征")
p("=" * 70)

# 分类draw改错
draw_error_stats = {
    'dt30': {'n': 0, 'actual_home': 0, 'actual_away': 0, 'actual_draw': 0, 'avg_dp': 0.0},
    'dt28': {'n': 0, 'actual_home': 0, 'actual_away': 0, 'actual_draw': 0, 'avg_dp': 0.0},
    'dt26': {'n': 0, 'actual_home': 0, 'actual_away': 0, 'actual_draw': 0, 'avg_dp': 0.0},
    'no_dt': {'n': 0, 'actual_home': 0, 'actual_away': 0, 'actual_draw': 0, 'avg_dp': 0.0},
}

# 也看draw改对(模型选draw且正确)
draw_correct_stats = {
    'dt30': 0, 'dt28': 0, 'dt26': 0, 'no_dt': 0,
}

for m in matches:
    mk = m['match_key']
    actual = 'home' if m['home_score'] > m['away_score'] else \
             'draw' if m['home_score'] == m['away_score'] else 'away'

    model_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
        (mk,)).fetchone()
    md = json.loads(model_row['data_json'])
    hp = md.get('home_win_prob', 0.33); dp = md.get('draw_prob', 0.33); ap = md.get('away_win_prob', 0.34)
    v34_flags = md.get('scenario_flags', [])
    signal = md.get('signal_value', 0)
    euro_conf = md.get('euro_confidence', 0.5)
    pred_model = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

    odds_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
        (mk,)).fetchone()
    od = json.loads(odds_row['data_json'])
    hp_o = float(od.get('home_value', 0) or 0); dp_o = float(od.get('draw_value', 0) or 0); ap_o = float(od.get('away_value', 0) or 0)
    pred_odds = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

    # draw改错: 赔率对但模型选draw
    if pred_model == 'draw' and pred_odds != 'draw' and pred_odds == actual and actual != 'draw':
        cat = 'dt30' if 'draw_threshold_0.3' in v34_flags else \
              'dt28' if 'draw_threshold_0.28' in v34_flags else \
              'dt26' if 'draw_threshold_0.26' in v34_flags else 'no_dt'
        draw_error_stats[cat]['n'] += 1
        draw_error_stats[cat]['actual_home'] += (1 if actual == 'home' else 0)
        draw_error_stats[cat]['actual_away'] += (1 if actual == 'away' else 0)
        draw_error_stats[cat]['avg_dp'] += dp

    # draw改对: 模型选draw且正确
    if pred_model == 'draw' and actual == 'draw':
        cat = 'dt30' if 'draw_threshold_0.3' in v34_flags else \
              'dt28' if 'draw_threshold_0.28' in v34_flags else \
              'dt26' if 'draw_threshold_0.26' in v34_flags else 'no_dt'
        draw_correct_stats[cat] += 1

conn.close()

p(f"\n  === draw改错分布 ===")
total_draw_error = sum(s['n'] for s in draw_error_stats.values())
for cat in ['dt30', 'dt28', 'dt26', 'no_dt']:
    s = draw_error_stats[cat]
    if s['n'] == 0: continue
    avg_dp = s['avg_dp'] / s['n'] * 100 if s['n'] > 0 else 0
    p(f"  {cat}: {s['n']}场 ({s['n']/total_draw_error*100:.1f}%) home={s['actual_home']} away={s['actual_away']} avg_dp={avg_dp:.1f}%")

p(f"\n  === draw改对分布 ===")
total_draw_correct = sum(draw_correct_stats.values())
for cat in ['dt30', 'dt28', 'dt26', 'no_dt']:
    cnt = draw_correct_stats[cat]
    if cnt == 0: continue
    p(f"  {cat}: {cnt}场 ({cnt/total_draw_correct*100:.1f}%)")

p(f"\n  === 净draw效果 ===")
for cat in ['dt30', 'dt28', 'dt26', 'no_dt']:
    err = draw_error_stats[cat]['n']
    cor = draw_correct_stats[cat]
    p(f"  {cat}: 改对={cor} 改错={err} 净={cor-err:+d}")

OUTPUT = 'd:/football_tools/fetchers/scripts/v381_draw_error_dt.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f"结果已写入 {OUTPUT}")