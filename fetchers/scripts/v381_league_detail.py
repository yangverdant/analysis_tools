"""
按赛事分析: 样本量、draw率、模型vs赔率表现
目标: 找出哪些赛事值得分赛事调参
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

league_stats = defaultdict(lambda: {
    'n': 0, 'draw_n': 0, 'home_n': 0, 'away_n': 0,
    'model_correct': 0, 'odds_correct': 0,
    'model_draw_pred': 0, 'model_draw_correct': 0,
    'odds_draw_pred': 0, 'odds_draw_correct': 0,
    'dt30_n': 0, 'dt30_draw_actual': 0,
})

for m in matches:
    mk = m['match_key']
    league = m['league_standard'] or 'unknown'
    actual = 'home' if m['home_score'] > m['away_score'] else \
             'draw' if m['home_score'] == m['away_score'] else 'away'

    model_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
        (mk,)).fetchone()
    md = json.loads(model_row['data_json'])
    hp = md.get('home_win_prob', 0.33); dp = md.get('draw_prob', 0.33); ap = md.get('away_win_prob', 0.34)
    v34_flags = md.get('scenario_flags', [])
    pred_m = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

    odds_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
        (mk,)).fetchone()
    od = json.loads(odds_row['data_json'])
    hp_o = float(od.get('home_value', 0) or 0)
    dp_o = float(od.get('draw_value', 0) or 0)
    ap_o = float(od.get('away_value', 0) or 0)
    pred_o = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

    g = league_stats[league]
    g['n'] += 1
    if actual == 'draw': g['draw_n'] += 1
    elif actual == 'home': g['home_n'] += 1
    else: g['away_n'] += 1
    g['model_correct'] += (1 if pred_m == actual else 0)
    g['odds_correct'] += (1 if pred_o == actual else 0)
    if pred_m == 'draw': g['model_draw_pred'] += 1; g['model_draw_correct'] += (1 if actual == 'draw' else 0)
    if pred_o == 'draw': g['odds_draw_pred'] += 1; g['odds_draw_correct'] += (1 if actual == 'draw' else 0)
    if 'draw_threshold_0.3' in v34_flags:
        g['dt30_n'] += 1
        if actual == 'draw': g['dt30_draw_actual'] += 1

conn.close()

lines = []
def p(s=""): lines.append(s)

p("=" * 90)
p("  按赛事分析: 样本量、draw率、模型表现、dt30影响")
p("=" * 90)

# 只看n>=50的赛事
results = []
for league, g in league_stats.items():
    if g['n'] < 50: continue
    draw_rate = g['draw_n'] / g['n'] * 100
    m_acc = g['model_correct'] / g['n'] * 100
    o_acc = g['odds_correct'] / g['n'] * 100
    gap = m_acc - o_acc
    m_draw_prec = g['model_draw_correct'] / g['model_draw_pred'] * 100 if g['model_draw_pred'] > 0 else 0
    o_draw_prec = g['odds_draw_correct'] / g['odds_draw_pred'] * 100 if g['odds_draw_pred'] > 0 else 0
    dt30_rate = g['dt30_n'] / g['n'] * 100 if g['n'] > 0 else 0
    dt30_draw_rate = g['dt30_draw_actual'] / g['dt30_n'] * 100 if g['dt30_n'] > 0 else 0
    results.append({
        'league': league, 'n': g['n'], 'draw_rate': draw_rate,
        'm_acc': m_acc, 'o_acc': o_acc, 'gap': gap,
        'm_draw_pred': g['model_draw_pred'], 'm_draw_prec': m_draw_prec,
        'o_draw_pred': g['odds_draw_pred'], 'o_draw_prec': o_draw_prec,
        'dt30_n': g['dt30_n'], 'dt30_rate': dt30_rate, 'dt30_draw_rate': dt30_draw_rate,
    })

# 按gap排序(模型最差到最好)
results.sort(key=lambda x: x['gap'])

p(f"\n  {'赛事':<25s} {'n':>5s} {'draw%':>6s} {'模型%':>6s} {'赔率%':>6s} {'gap':>6s} "
  f"{'M_draw':>7s} {'M_dpr%':>6s} {'O_draw':>7s} {'O_dpr%':>6s} {'dt30%':>6s} {'dt30draw%':>9s}")
p("  " + "-" * 100)

for r in results:
    p(f"  {r['league']:<25s} {r['n']:>5d} {r['draw_rate']:>5.1f}% {r['m_acc']:>5.1f}% {r['o_acc']:>5.1f}% {r['gap']:>+5.1f}pp "
      f"{r['m_draw_pred']:>7d} {r['m_draw_prec']:>5.1f}% {r['o_draw_pred']:>7d} {r['o_draw_prec']:>5.1f}% "
      f"{r['dt30_rate']:>5.1f}% {r['dt30_draw_rate']:>8.1f}%")

OUTPUT = 'd:/football_tools/fetchers/scripts/v381_league_detail.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f"结果已写入 {OUTPUT}")
