"""
serie_b深度分析: 为什么44.1%这么低?
- draw率33.1%极高, 但dt30=49%
- 模型预测0场draw, 但实际有251场draw
- 问题: dt30减draw后, 高draw率联赛反而从不预测draw
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

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

matches = conn.execute("""
    SELECT m.match_key, m.date, m.home_team, m.away_team,
           m.league_standard, m.home_score, m.away_score
    FROM matches m
    WHERE m.status='finished' AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
    AND m.league_standard LIKE '%serie_b%'
    AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                AND md.source='model' AND md.data_type='model:enhanced_linear')
    AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                AND md.source='factor' AND md.data_type='factor:euro_odds')
    ORDER BY m.date
""").fetchall()

lines = []
def p(s=""): lines.append(s)

p("=" * 80)
p("  serie_b深度分析: 为什么44.1%? draw率33%但预测0场draw")
p("=" * 80)

# 分析: v3.4模型输出 vs v3.9调整后 vs 实际结果
p(f"\n  总场次: {len(matches)}")

# 按实际结果分组
actual_dist = defaultdict(int)
pred_v34_dist = defaultdict(int)
pred_v39_dist = defaultdict(int)

# v3.4模型的draw概率分布
draw_probs = []
draw_probs_dt30 = []
draw_probs_no_dt30 = []

# v3.9调整后的draw概率分布
draw_probs_v39 = []
draw_probs_v39_dt30 = []

# 各组合: dt30 vs actual
dt30_actual = defaultdict(lambda: defaultdict(int))  # dt30=True/False → home/draw/away
no_dt30_actual = defaultdict(lambda: defaultdict(int))

for m in matches:
    mk = m['match_key']
    actual = 'home' if m['home_score'] > m['away_score'] else \
             'draw' if m['home_score'] == m['away_score'] else 'away'
    actual_dist[actual] += 1

    model_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
        (mk,)).fetchone()
    md = json.loads(model_row['data_json'])
    hp = md.get('home_win_prob', 0.33); dp = md.get('draw_prob', 0.33); ap = md.get('away_win_prob', 0.34)
    v34_flags = md.get('scenario_flags', [])

    # v3.4预测
    pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
    pred_v34_dist[pred_v34] += 1

    # v3.9调整
    hp_x = hp; dp_x = dp; ap_x = ap
    for dt_flag, old_boost in DT_V34.items():
        if dt_flag in v34_flags:
            dp_x -= old_boost; hp_x += old_boost*(hp/(hp+ap)); ap_x += old_boost*(ap/(hp+ap))
    # dt处理
    is_dt30 = 'draw_threshold_0.3' in v34_flags
    if is_dt30:
        # DIV2参数: boost=0, base=0.02, ah0=0.02
        ah_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
            (mk,)).fetchone()
        ah_type = 'no_data'
        if ah_row:
            ah_data = json.loads(ah_row['data_json'])
            raw = ah_data.get('raw', {})
            hc = raw.get('closing_handicap', None) or raw.get('handicap', None) or ah_data.get('handicap_value', None)
            if hc is not None:
                try: ah_type = 'ah0' if abs(float(hc)) < 0.01 else 'ah_non0'
                except: pass
        rv = 0.02 + (0.02 if ah_type == 'ah0' else 0)
        dp_x -= rv; nd = hp_x+ap_x
        if nd > 0: hp_x += rv*(hp_x/nd); ap_x += rv*(ap_x/nd)
    elif 'draw_threshold_0.28' in v34_flags:
        dp_x += 0.01; nd = hp_x+ap_x
        if nd > 0: hp_x -= 0.01*(hp_x/nd); ap_x -= 0.01*(ap_x/nd)
    elif 'draw_threshold_0.26' in v34_flags:
        dp_x += 0.005; nd = hp_x+ap_x
        if nd > 0: hp_x -= 0.005*(hp_x/nd); ap_x -= 0.005*(ap_x/nd)

    hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
    pred_v39 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])
    pred_v39_dist[pred_v39] += 1

    draw_probs.append(dp)
    draw_probs_v39.append(dp_x)
    if is_dt30:
        draw_probs_dt30.append(dp)
        draw_probs_v39_dt30.append(dp_x)
    else:
        draw_probs_no_dt30.append(dp)

    # dt30 vs actual
    is_dt30_flag = 'draw_threshold_0.3' in v34_flags
    if is_dt30_flag:
        dt30_actual[True][actual] += 1
    else:
        dt30_actual[False][actual] += 1

p(f"\n  === 实际结果分布 ===")
for result in ['home', 'draw', 'away']:
    p(f"    {result}: {actual_dist[result]} ({actual_dist[result]/len(matches)*100:.1f}%)")

p(f"\n  === v3.4预测分布 ===")
for result in ['home', 'draw', 'away']:
    p(f"    {result}: {pred_v34_dist[result]} ({pred_v34_dist[result]/len(matches)*100:.1f}%)")

p(f"\n  === v3.9预测分布 ===")
for result in ['home', 'draw', 'away']:
    p(f"    {result}: {pred_v39_dist[result]} ({pred_v39_dist[result]/len(matches)*100:.1f}%)")

p(f"\n  === Draw概率分布 ===")
p(f"    v3.4 avg draw_prob: {sum(draw_probs)/len(draw_probs):.4f}")
p(f"    v3.9 avg draw_prob: {sum(draw_probs_v39)/len(draw_probs_v39):.4f}")
if draw_probs_dt30:
    p(f"    v3.4 dt30 avg draw_prob: {sum(draw_probs_dt30)/len(draw_probs_dt30):.4f}")
    p(f"    v3.9 dt30 avg draw_prob: {sum(draw_probs_v39_dt30)/len(draw_probs_v39_dt30):.4f}")
if draw_probs_no_dt30:
    p(f"    v3.4 no-dt30 avg draw_prob: {sum(draw_probs_no_dt30)/len(draw_probs_no_dt30):.4f}")

p(f"\n  === dt30 vs 实际结果 ===")
for dt_flag in [True, False]:
    total = sum(dt30_actual[dt_flag].values())
    if total == 0: continue
    label = "dt30" if dt_flag else "no_dt30"
    p(f"    {label}: N={total}")
    for result in ['home', 'draw', 'away']:
        n = dt30_actual[dt_flag][result]
        p(f"      {result}: {n} ({n/total*100:.1f}%)")

# 实验不同参数: serie_b的特殊处理
p(f"\n  === serie_b参数实验 ===")
for sb_boost, sb_base, sb_ah0_extra, sb_draw_reduce in [
    (0.00, 0.02, 0.02, 0.00),  # 基线v3.9
    (0.00, 0.01, 0.02, 0.00),  # base更小
    (0.00, 0.03, 0.03, 0.00),  # base更大
    (0.01, 0.02, 0.02, 0.00),  # 加boost+减base
    (0.01, 0.01, 0.02, 0.00),  # 加小boost+减小base
    (0.00, 0.00, 0.00, 0.00),  # 完全不调(原始v3.4dt30行为)
    (0.00, 0.02, 0.02, 0.01),  # 全局减1pp draw
    (0.00, 0.02, 0.02, 0.02),  # 全局减2pp draw
    (0.02, 0.00, 0.00, 0.00),  # 只加boost(serie_b draw率33%, dt30加boost可能更好?)
]:
    sb_n = 0; sb_correct = 0; sb_draw_pred = 0; sb_draw_correct = 0
    sb_draw_actual = 0; sb_brier = 0.0

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

        hp_x = hp; dp_x = dp; ap_x = ap
        for dt_flag, old_boost in DT_V34.items():
            if dt_flag in v34_flags:
                dp_x -= old_boost; hp_x += old_boost*(hp/(hp+ap)); ap_x += old_boost*(ap/(hp+ap))

        # 全局draw减
        if sb_draw_reduce > 0:
            dp_x -= sb_draw_reduce; nd = hp_x + ap_x
            if nd > 0: hp_x += sb_draw_reduce*(hp_x/nd); ap_x += sb_draw_reduce*(ap_x/nd)
            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

        is_dt30 = 'draw_threshold_0.3' in v34_flags
        if is_dt30:
            if sb_boost > 0:
                dp_x += sb_boost; nd = hp_x+ap_x
                if nd > 0: hp_x -= sb_boost*(hp_x/nd); ap_x -= sb_boost*(ap_x/nd)
                hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

            ah_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
                (mk,)).fetchone()
            ah_type = 'no_data'
            if ah_row:
                ah_data = json.loads(ah_row['data_json'])
                raw = ah_data.get('raw', {})
                hc = raw.get('closing_handicap', None) or raw.get('handicap', None) or ah_data.get('handicap_value', None)
                if hc is not None:
                    try: ah_type = 'ah0' if abs(float(hc)) < 0.01 else 'ah_non0'
                    except: pass
            rv = sb_base + (sb_ah0_extra if ah_type == 'ah0' else 0)
            if rv > 0:
                dp_x -= rv; nd = hp_x+ap_x
                if nd > 0: hp_x += rv*(hp_x/nd); ap_x += rv*(ap_x/nd)
                hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
        elif 'draw_threshold_0.28' in v34_flags:
            dp_x += 0.01; nd = hp_x+ap_x
            if nd > 0: hp_x -= 0.01*(hp_x/nd); ap_x -= 0.01*(ap_x/nd)
            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
        elif 'draw_threshold_0.26' in v34_flags:
            dp_x += 0.005; nd = hp_x+ap_x
            if nd > 0: hp_x -= 0.005*(hp_x/nd); ap_x -= 0.005*(ap_x/nd)
            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
        pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])

        sb_n += 1
        if pred == actual: sb_correct += 1
        if pred == 'draw': sb_draw_pred += 1; sb_draw_correct += (1 if actual == 'draw' else 0)
        if actual == 'draw': sb_draw_actual += 1
        if actual == 'home':   sb_brier += (hp_x-1)**2 + dp_x**2 + ap_x**2
        elif actual == 'draw': sb_brier += hp_x**2 + (dp_x-1)**2 + ap_x**2
        else:                  sb_brier += hp_x**2 + dp_x**2 + (ap_x-1)**2

    dp_prec = sb_draw_correct/sb_draw_pred*100 if sb_draw_pred > 0 else 0
    draw_recall = sb_draw_correct/sb_draw_actual*100 if sb_draw_actual > 0 else 0
    p(f"    boost={sb_boost} base={sb_base} ah0={sb_ah0_extra} draw_reduce={sb_draw_reduce}: "
      f"acc={sb_correct}/{sb_n}={sb_correct/sb_n*100:.1f}% Brier={sb_brier/sb_n:.4f} "
      f"draw_pred={sb_draw_pred} prec={dp_prec:.0f}% recall={draw_recall:.0f}%")

p(f"\n{'=' * 80}")
p("  serie_b深度分析完成")
p("=" * 80)

OUTPUT = 'd:/football_tools/fetchers/scripts/v39_serie_b_deep.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f"结果已写入 {OUTPUT}")