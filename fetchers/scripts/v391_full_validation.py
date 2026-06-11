"""
v3.9.1完整验证: cup_reduce=0.02 + prima_liga_reduce=0.02 + div2_dt30(0,0.02,0.02)
"""
import sys, io, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

from fetchers.analysis.models.enhanced_linear import EnhancedLinearModel
from fetchers.storage.crud import UnifiedStorage

DB_PATH = 'd:/football_tools/data/unified_football.db'
storage = UnifiedStorage(DB_PATH)
model = EnhancedLinearModel()

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
p(f"  v{model.model_version}完整验证: {len(matches)}场")
p("=" * 70)

total_n = 0; correct = 0; brier = 0.0; net_gain = 0
cup_n = 0; cup_correct = 0; cup_draw_pred = 0; cup_draw_actual = 0; cup_draw_correct = 0
div2_n = 0; div2_correct = 0
top5_n = 0; top5_correct = 0
prima_n = 0; prima_correct = 0; prima_draw_pred = 0; prima_draw_actual = 0; prima_draw_correct = 0
sb_n = 0; sb_correct = 0

# 读取v3.4预测结果做对比
from collections import defaultdict
league_acc = defaultdict(lambda: {'n': 0, 'correct': 0})

for m in matches:
    mk = m['match_key']
    league = m['league_standard'] or ''
    actual = 'home' if m['home_score'] > m['away_score'] else \
             'draw' if m['home_score'] == m['away_score'] else 'away'

    # 读取v3.4预测
    v34_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
        (mk,)).fetchone()
    md = json.loads(v34_row['data_json'])
    hp34 = md.get('home_win_prob', 0.33); dp34 = md.get('draw_prob', 0.33); ap34 = md.get('away_win_prob', 0.34)
    pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp34, 'draw': dp34, 'away': ap34}[x])

    # 构建factors并调模型
    factors = {}
    for row in conn.execute("SELECT source, data_type, data_json FROM match_data WHERE match_key=?", (mk,)):
        key = row['data_type'].replace(':', '_', 1).replace(':', '_')
        factors[key] = json.loads(row['data_json'])

    result = model.predict(mk, factors, storage)
    probs = {'home': result['home_win_prob'], 'draw': result['draw_prob'], 'away': result['away_win_prob']}
    pred = max(probs, key=probs.get)

    correct += (1 if pred == actual else 0)
    hp = result.get('home_win_prob', 0.33); dp = result.get('draw_prob', 0.33); ap = result.get('away_win_prob', 0.34)
    if actual == 'home':   brier += (hp-1)**2 + dp**2 + ap**2
    elif actual == 'draw': brier += hp**2 + (dp-1)**2 + ap**2
    else:                  brier += hp**2 + dp**2 + (ap-1)**2
    total_n += 1

    if pred != pred_v34:
        if pred == actual: net_gain += 1
        elif pred_v34 == actual: net_gain -= 1

    is_cup = any(kw in league for kw in model.CUP_KEYWORDS)
    is_div2 = any(kw.lower() in league.lower() for kw in model.DIV2_KEYWORDS)
    top5_kw = ["premier_league", "la_liga", "serie_a", "bundesliga", "ligue_1",
               "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]
    is_top5 = any(kw in league for kw in top5_kw) and not is_div2
    is_prima = "primeira_liga" in league.lower()
    is_sb = "serie_b" in league.lower()

    if is_cup:
        cup_n += 1
        if pred == actual: cup_correct += 1
        if pred == 'draw': cup_draw_pred += 1; cup_draw_correct += (1 if actual == 'draw' else 0)
        if actual == 'draw': cup_draw_actual += 1
    if is_prima:
        prima_n += 1
        if pred == actual: prima_correct += 1
        if pred == 'draw': prima_draw_pred += 1; prima_draw_correct += (1 if actual == 'draw' else 0)
        if actual == 'draw': prima_draw_actual += 1
    if is_sb: sb_n += 1; sb_correct += (1 if pred == actual else 0)
    if is_div2: div2_n += 1; div2_correct += (1 if pred == actual else 0)
    if is_top5: top5_n += 1; top5_correct += (1 if pred == actual else 0)

    league_acc[league]['n'] += 1
    league_acc[league]['correct'] += (1 if pred == actual else 0)

p(f"\n  总体: {correct}/{total_n}={correct/total_n*100:.2f}% Brier={brier/total_n:.4f} net={net_gain:+d}")
if cup_n > 0:
    dp = cup_draw_correct/cup_draw_pred*100 if cup_draw_pred > 0 else 0
    p(f"  杯赛: {cup_correct}/{cup_n}={cup_correct/cup_n*100:.1f}% draw_pred={cup_draw_pred} prec={dp:.0f}%")
if prima_n > 0:
    dp = prima_draw_correct/prima_draw_pred*100 if prima_draw_pred > 0 else 0
    p(f"  prima_liga: {prima_correct}/{prima_n}={prima_correct/prima_n*100:.1f}% draw_pred={prima_draw_pred} prec={dp:.0f}%")
if sb_n > 0: p(f"  serie_b: {sb_correct}/{sb_n}={sb_correct/sb_n*100:.1f}%")
if div2_n > 0: p(f"  二级联赛: {div2_correct}/{div2_n}={div2_correct/div2_n*100:.1f}%")
if top5_n > 0: p(f"  五大联赛: {top5_correct}/{top5_n}={top5_correct/top5_n*100:.1f}%")

p(f"\n  --- 最差5联赛(≥50场) ---")
sorted_lg = sorted(league_acc.items(), key=lambda x: x[1]['correct']/x[1]['n'] if x[1]['n'] >= 50 else 1)
for lg, s in sorted_lg[:5]:
    if s['n'] >= 50:
        p(f"    {lg:40s} {s['correct']}/{s['n']}={s['correct']/s['n']*100:.1f}%")

p(f"\n{'=' * 70}")
p(f"  v{model.model_version}验证完成")
p("=" * 70)

OUTPUT = 'd:/football_tools/fetchers/scripts/v391_full_validation.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f"结果已写入 {OUTPUT}")