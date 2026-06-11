"""
v3.8.1+聚焦: 解放者杯/南美杯赛改错模式
模型落后赔率6pp, 为什么?
"""
import sys, io, json, sqlite3
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 解放者杯 + 南美杯赛
SA_LEAGUES = ["Libertadores", "libertadores", "Sudamericana", "sudamericana",
              "Copa Libertadores", "copa_libertadores", "Copa Sudamericana", "copa_sudamericana"]

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
p("  解放者杯/南美杯赛改错模式分析")
p("=" * 70)

patterns = defaultdict(int)
flag_in_error = defaultdict(int)
odds_dist = defaultdict(int)
sig_stats = defaultdict(lambda: {'n': 0, 'correct': 0, 'odds_correct': 0})

for m in matches:
    league = m['league_standard'] or ''
    if not any(kw in league for kw in SA_LEAGUES): continue

    mk = m['match_key']
    actual = 'home' if m['home_score'] > m['away_score'] else \
             'draw' if m['home_score'] == m['away_score'] else 'away'

    model_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
        (mk,)).fetchone()
    if not model_row: continue
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
    hp_o = float(od.get('home_value', 0) or 0)
    dp_o = float(od.get('draw_value', 0) or 0)
    ap_o = float(od.get('away_value', 0) or 0)
    raw = od.get('raw', {})
    odds_h = float(raw.get('avg_home_odds', 0) or raw.get('closing_avg_home_odds', 0) or 0)
    pred_odds = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

    model_correct = (pred_model == actual)
    odds_correct = (pred_odds == actual)

    # 改对改错
    if not model_correct and odds_correct:
        pat = f"赔率→{pred_odds}(✓) 模型→{pred_model}(✗)"
        patterns[pat] += 1
        for f in v34_flags:
            flag_in_error[f] += 1

    # 信号效果
    sig_dir = 'home' if signal > 0.05 else ('away' if signal < -0.05 else 'neutral')
    sig_stats[sig_dir]['n'] += 1
    sig_stats[sig_dir]['correct'] += (1 if model_correct else 0)
    sig_stats[sig_dir]['odds_correct'] += (1 if odds_correct else 0)

    # 赔率区间
    if odds_h > 0:
        if odds_h < 1.5: odds_dist["<1.5"] += 1
        elif odds_h < 2.0: odds_dist["1.5-2"] += 1
        elif odds_h < 3.0: odds_dist["2-3"] += 1
        elif odds_h < 4.0: odds_dist["3-4"] += 1
        else: odds_dist["4+"] += 1

conn.close()

total_errors = sum(patterns.values())
p(f"\n  === 改错模式 ===")
for pat, cnt in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
    p(f"  {pat}: {cnt}场 ({cnt/total_errors*100:.1f}%)")

p(f"\n  === 改错中flag分布 ===")
for f, cnt in sorted(flag_in_error.items(), key=lambda x: x[1], reverse=True):
    p(f"  {f}: {cnt}场 ({cnt/total_errors*100:.1f}%)")

p(f"\n  === 信号效果 ===")
for d, g in sorted(sig_stats.items()):
    m_acc = g['correct']/g['n']*100 if g['n'] > 0 else 0
    o_acc = g['odds_correct']/g['n']*100 if g['n'] > 0 else 0
    p(f"  signal={d}: n={g['n']} model={m_acc:.1f}% odds={o_acc:.1f}% gap={m_acc-o_acc:+.1f}pp")

p(f"\n  === 赔率区间分布 ===")
for k, v in sorted(odds_dist.items()):
    p(f"  {k}: {v}场")

p(f"\n{'=' * 70}")
p("  分析完成")
p("=" * 70)

OUTPUT = 'd:/football_tools/fetchers/scripts/v381_sa_league_error.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f"结果已写入 {OUTPUT}")