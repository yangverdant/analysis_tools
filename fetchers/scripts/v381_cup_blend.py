"""
v3.8.1分赛事实验: 在杯赛中降低AH_DRAW_BLEND
杯赛: dt30不触发但AH blend仍推高draw, 导致draw预测过多
实验: cup赛事AH blend从0.50降到不同值
"""
import sys, io, json, sqlite3, math
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

CUP_KEYWORDS = ["Champions League", "champions_league", "Europa League", "europa_league",
                "Conference League", "conference_league", "Libertadores", "libertadores",
                "Sudamericana", "sudamericana", "Copa Libertadores", "copa_libertadores",
                "Copa Sudamericana", "copa_sudamericana", "ACL", "asian_champions",
                "Asian Champions", "world_cup", "World Cup"]

def normalize_probs(hp, dp, ap):
    total = hp + dp + ap
    if total <= 0: return 0.33, 0.33, 0.34
    return hp/total, dp/total, ap/total

DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}
DT_V38 = {0.30: 0.01, 0.28: 0.01, 0.26: 0.005}
DT30_BASE = 0.01; DT30_AH0_EXTRA = 0.02

# AH draw rate lookup (from model)
AH_DRAW_RATES = {
    0.0: 0.35, 0.25: 0.33, 0.5: 0.30, 0.75: 0.27, 1.0: 0.24,
    1.25: 0.22, 1.5: 0.19, 1.75: 0.16, 2.0: 0.13, 2.5: 0.10, 3.0: 0.07,
}

def ah_draw_rate(abs_hc):
    if abs_hc <= 0: return 0.35
    rates = sorted(AH_DRAW_RATES.keys())
    for i in range(len(rates)-1):
        lo, hi = rates[i], rates[i+1]
        if lo <= abs_hc <= hi:
            t = (abs_hc - lo) / (hi - lo)
            return AH_DRAW_RATES[lo] + t * (AH_DRAW_RATES[hi] - AH_DRAW_RATES[lo])
    return 0.07

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
p("  分赛事实验: 杯赛中降低AH_DRAW_BLEND")
p("=" * 70)

# 策略: 全局AH blend保持0.50, 但杯赛中降低
# 模拟: 从v3.4概率出发, 扣除AH blend部分, 重新用新blend计算
# AH blend效果: draw_prob_new = (1-blend)*odds_draw + blend*ah_draw
# 所以: 去掉旧blend → draw -= (0.50*(ah_draw - odds_draw))
# 加上新blend → draw += (new_blend*(ah_draw - odds_draw))

for cup_blend in [0.50, 0.40, 0.30, 0.20, 0.10, 0.00]:
    total_n = 0; correct = 0; brier = 0.0; net_gain = 0
    cup_n = 0; cup_correct = 0; cup_brier = 0.0
    cup_draw_pred = 0; cup_draw_correct = 0; cup_draw_actual = 0

    for m in matches:
        mk = m['match_key']
        league = m['league_standard'] or ''
        is_cup = any(kw in league for kw in CUP_KEYWORDS)
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        md = json.loads(model_row['data_json'])
        hp = md.get('home_win_prob', 0.33); dp = md.get('draw_prob', 0.33); ap = md.get('away_win_prob', 0.34)
        v34_flags = md.get('scenario_flags', [])
        pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        od = json.loads(odds_row['data_json'])
        raw = od.get('raw', {})
        odds_h = float(raw.get('avg_home_odds', 0) or raw.get('closing_avg_home_odds', 0) or 0)

        # AH数据
        ah_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
            (mk,)).fetchone()
        ah_data = json.loads(ah_row['data_json']) if ah_row else {}
        ah_conf = ah_data.get('confidence', 0)
        ah_hc = ah_data.get('raw', {}).get('closing_handicap', None)

        hp_x = hp; dp_x = dp; ap_x = ap

        # Step 1: 去掉v3.4 dt
        for dt_flag, old_boost in DT_V34.items():
            if dt_flag in v34_flags:
                dp_x -= old_boost; hp_x += old_boost*(hp/(hp+ap)); ap_x += old_boost*(ap/(hp+ap))

        # Step 2: 去掉旧AH blend(0.50), 加上杯赛新blend
        # v3.4概率已经包含了AH blend(0.50)的效果
        # 需要反推: draw_prob_v34包含了AH blend调整
        # AH blend: draw_new = (1-0.50)*draw_before + 0.50*ah_draw
        # → draw_before = 2*draw_new - ah_draw (如果draw_before > 0)
        # 然后用新blend: draw_final = (1-new_blend)*draw_before + new_blend*ah_draw
        # 简化: draw_final = draw_new + (new_blend - 0.50)*(ah_draw - draw_before)
        # 但draw_before = 2*draw_new - ah_draw
        # → draw_final = draw_new + (new_blend - 0.50)*(ah_draw - 2*draw_new + ah_draw)
        # = draw_new + (new_blend - 0.50)*(2*ah_draw - 2*draw_new)
        # = draw_new + 2*(new_blend - 0.50)*(ah_draw - draw_new)

        if is_cup and ah_conf > 0 and ah_hc is not None and cup_blend != 0.50:
            abs_hc = abs(float(ah_hc))
            ah_draw_prob = ah_draw_rate(abs_hc)
            # 去掉0.50 blend, 加上新blend
            dp_change = 2 * (cup_blend - 0.50) * (ah_draw_prob - dp_x)
            dp_x += dp_change
            non_draw = hp_x + ap_x
            if non_draw > 0:
                hp_x -= dp_change * (hp_x / (hp_x + ap_x))
                ap_x -= dp_change * (ap_x / (hp_x + ap_x))
            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

        # Step 3: v3.8.1 dt
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

        correct += (1 if pred_x == actual else 0)
        if actual == 'home':   brier += (hp_x-1)**2 + dp_x**2 + ap_x**2
        elif actual == 'draw': brier += hp_x**2 + (dp_x-1)**2 + ap_x**2
        else:                  brier += hp_x**2 + dp_x**2 + (ap_x-1)**2
        total_n += 1

        if pred_x != pred_v34:
            if pred_x == actual: net_gain += 1
            elif pred_v34 == actual: net_gain -= 1

        if is_cup:
            cup_n += 1
            if pred_x == actual: cup_correct += 1
            if actual == 'home':   cup_brier += (hp_x-1)**2 + dp_x**2 + ap_x**2
            elif actual == 'draw': cup_brier += hp_x**2 + (dp_x-1)**2 + ap_x**2
            else:                  cup_brier += hp_x**2 + dp_x**2 + (ap_x-1)**2
            if pred_x == 'draw': cup_draw_pred += 1; cup_draw_correct += (1 if actual == 'draw' else 0)
            if actual == 'draw': cup_draw_actual += 1

    cup_acc = cup_correct/cup_n*100 if cup_n > 0 else 0
    cup_br = cup_brier/cup_n if cup_n > 0 else 0
    cup_dp = cup_draw_correct/cup_draw_pred*100 if cup_draw_pred > 0 else 0
    cup_dr = cup_draw_correct/cup_draw_actual*100 if cup_draw_actual > 0 else 0

    p(f"\n  cup_blend={cup_blend:.2f}:")
    p(f"    总体: {correct}/{total_n}={correct/total_n*100:.2f}% Brier={brier/total_n:.4f} net={net_gain:+d}")
    p(f"    杯赛: {cup_correct}/{cup_n}={cup_acc:.1f}% Brier={cup_br:.4f} draw_pred={cup_draw_pred} prec={cup_dp:.1f}% recall={cup_dr:.1f}%")

p(f"\n{'=' * 70}")
p("  实验完成")
p("=" * 70)

OUTPUT = 'd:/football_tools/fetchers/scripts/v381_cup_blend.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f"结果已写入 {OUTPUT}")