"""
v3.8.1全局诊断: 模型vs赔率的改对改错全量分析
不是聚焦某个子群, 而是全局看模型改对/改错赔率方向的模式
"""
import sys, io, json, sqlite3
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

def normalize_probs(hp, dp, ap):
    total = hp + dp + ap
    if total <= 0: return 0.33, 0.33, 0.34
    return hp/total, dp/total, ap/total

DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}
DT_V38 = {0.30: 0.01, 0.28: 0.01, 0.26: 0.005}
DT30_BASE = 0.01; DT30_AH0_EXTRA = 0.02

def get_ah_type(conn, mk):
    ah_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
        (mk,)).fetchone()
    if not ah_row: return 'no_data'
    ah_data = json.loads(ah_row['data_json'])
    raw = ah_data.get('raw', {})
    hc = raw.get('closing_handicap', None) or raw.get('handicap', None) or ah_data.get('handicap_value', None)
    if hc is None: return 'no_data'
    try:
        val = float(hc)
        return 'ah0' if abs(val) < 0.01 else 'ah_non0'
    except: return 'no_data'

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
p("  v3.8.1全局改对改错模式")
p("=" * 70)

# 6种模式: 赔率→X(✓/✗) 模型→Y(✓/✗)
pattern_stats = defaultdict(lambda: {'n': 0, 'flags': defaultdict(int)})

total_n = 0; correct_v381 = 0; correct_odds = 0; brier_v381 = 0.0

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

    odds_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
        (mk,)).fetchone()
    od = json.loads(odds_row['data_json'])
    hp_o = float(od.get('home_value', 0) or 0); dp_o = float(od.get('draw_value', 0) or 0); ap_o = float(od.get('away_value', 0) or 0)
    raw = od.get('raw', {})
    odds_h = float(raw.get('avg_home_odds', 0) or raw.get('closing_avg_home_odds', 0) or 0)

    # v3.8.1概率
    hp_x = hp; dp_x = dp; ap_x = ap
    for dt_flag, old_boost in DT_V34.items():
        if dt_flag in v34_flags:
            dp_x -= old_boost; hp_x += old_boost*(hp/(hp+ap)); ap_x += old_boost*(ap/(hp+ap))

    is_dt30 = 'draw_threshold_0.3' in v34_flags
    if is_dt30:
        dp_x += DT_V38[0.30]; nd = hp_x+ap_x
        if nd > 0: hp_x -= DT_V38[0.30]*(hp_x/nd); ap_x -= DT_V38[0.30]*(ap_x/nd)
        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
        ah_type = get_ah_type(conn, mk)
        rv = DT30_BASE + (DT30_AH0_EXTRA if ah_type == 'ah0' else 0)
        if rv > 0:
            dp_x -= rv; nd = hp_x+ap_x
            if nd > 0: hp_x += rv*(hp_x/nd); ap_x += rv*(ap_x/nd)
            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
    elif 'draw_threshold_0.28' in v34_flags:
        dp_x += DT_V38[0.28]; nd = hp_x+ap_x
        if nd > 0: hp_x -= DT_V38[0.28]*(hp_x/nd); ap_x -= DT_V38[0.28]*(ap_x/nd)
        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
    elif 'draw_threshold_0.26' in v34_flags:
        dp_x += DT_V38[0.26]; nd = hp_x+ap_x
        if nd > 0: hp_x -= DT_V38[0.26]*(hp_x/nd); ap_x -= DT_V38[0.26]*(ap_x/nd)
        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

    hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
    pred_x = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])
    pred_o = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

    correct_v381 += (1 if pred_x == actual else 0)
    correct_odds += (1 if pred_o == actual else 0)
    if actual == 'home':   brier_v381 += (hp_x-1)**2 + dp_x**2 + ap_x**2
    elif actual == 'draw': brier_v381 += hp_x**2 + (dp_x-1)**2 + ap_x**2
    else:                  brier_v381 += hp_x**2 + dp_x**2 + (ap_x-1)**2
    total_n += 1

    m_ok = (pred_x == actual)
    o_ok = (pred_o == actual)

    if o_ok and not m_ok:
        pat = f"赔率→{pred_o}(✓) 模型→{pred_x}(✗)"
        pattern_stats[pat]['n'] += 1
        for f in v34_flags: pattern_stats[pat]['flags'][f] += 1
    elif m_ok and not o_ok:
        pat = f"模型→{pred_x}(✓) 赔率→{pred_o}(✗)"
        pattern_stats[pat]['n'] += 1
        for f in v34_flags: pattern_stats[pat]['flags'][f] += 1
    elif m_ok and o_ok:
        pat = "同对"
        pattern_stats[pat]['n'] += 1
    else:
        pat = "同错"
        pattern_stats[pat]['n'] += 1

conn.close()

p(f"\n  总体: v3.8.1={correct_v381}/{total_n}={correct_v381/total_n*100:.2f}% "
  f"赔率={correct_odds}/{total_n}={correct_odds/total_n*100:.2f}% "
  f"gap={correct_v381/total_n*100-correct_odds/total_n*100:+.2f}pp "
  f"Brier={brier_v381/total_n:.4f}")

p(f"\n  === 改错模式 (赔率对,模型错) ===")
error_total = sum(v['n'] for k, v in pattern_stats.items() if '赔率' in k and '✓' in k and '✗' in k)
for pat, g in sorted(pattern_stats.items(), key=lambda x: x[1]['n'], reverse=True):
    if '赔率' in pat and '✓' in pat:
        p(f"  {pat}: {g['n']}场 ({g['n']/error_total*100:.1f}%)")
        top_flags = sorted(g['flags'].items(), key=lambda x: x[1], reverse=True)[:5]
        for f, cnt in top_flags:
            p(f"    {f}: {cnt}场 ({cnt/g['n']*100:.0f}%)")

p(f"\n  === 改对模式 (模型对,赔率错) ===")
correct_total = sum(v['n'] for k, v in pattern_stats.items() if '模型' in k and '✓' in k and '✗' in k)
for pat, g in sorted(pattern_stats.items(), key=lambda x: x[1]['n'], reverse=True):
    if '模型' in pat and '✓' in pat:
        p(f"  {pat}: {g['n']}场 ({g['n']/correct_total*100:.1f}%)")
        top_flags = sorted(g['flags'].items(), key=lambda x: x[1], reverse=True)[:5]
        for f, cnt in top_flags:
            p(f"    {f}: {cnt}场 ({cnt/g['n']*100:.0f}%)")

p(f"\n  同对: {pattern_stats['同对']['n']}场  同错: {pattern_stats['同错']['n']}场")
p(f"  净改错: {error_total - correct_total}场")

OUTPUT = 'd:/football_tools/fetchers/scripts/v381_global_pattern.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f"结果已写入 {OUTPUT}")