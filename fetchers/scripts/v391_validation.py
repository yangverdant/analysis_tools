"""
v3.9.1整合验证: prima_liga减0.02draw + serie_b特殊dt30(完全不禁draw)
"""
import sys, io, json, sqlite3
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

CUP_KEYWORDS = ["Champions League", "champions_league", "Europa League", "europa_league",
                "Conference League", "conference_league", "Libertadores", "libertadores",
                "Sudamericana", "sudamericana", "Copa Libertadores", "copa_libertadores",
                "Copa Sudamericana", "copa_sudamericana", "ACL", "asian_champions",
                "Asian Champions", "world_cup", "World Cup"]
DIV2_KEYWORDS = ["serie_b", "la_liga_2", "ligue_2", "2_bundesliga", "segunda",
                 "Serie B", "La Liga 2", "Ligue 2", "2. Bundesliga", "Segunda",
                 "efl_championship", "EFL Championship", "Championship"]
# primeira_liga: draw精度17%, 减0.02 → 45.2%
COLD_DRAW_LEAGUES = {
    "primeira_liga": 0.02, "Primeira Liga": 0.02,
}

def normalize_probs(hp, dp, ap):
    total = hp + dp + ap
    if total <= 0: return 0.33, 0.33, 0.34
    return hp/total, dp/total, ap/total

DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}

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

p("=" * 80)
p("  v3.9.1整合验证: prima减draw + serie_b保留draw + 杯赛减draw")
p("=" * 80)

# 测试不同serie_b处理策略
for sb_strategy in ['v39_base', 'no_dt_adjust', 'global_reduce_002', 'keep_v34_dt']:
    total_n = 0; correct = 0; brier = 0.0; net_gain = 0
    cup_n = 0; cup_correct = 0; cup_draw_pred = 0; cup_draw_actual = 0; cup_draw_correct = 0
    div2_n = 0; div2_correct = 0
    prima_n = 0; prima_correct = 0; prima_draw_pred = 0; prima_draw_correct = 0
    sb_n = 0; sb_correct = 0; sb_draw_pred = 0; sb_draw_correct = 0
    top5_n = 0; top5_correct = 0
    other_n = 0; other_correct = 0

    league_stats = defaultdict(lambda: {'n': 0, 'correct': 0})

    for m in matches:
        mk = m['match_key']
        league = m['league_standard'] or ''
        is_cup = any(kw in league for kw in CUP_KEYWORDS)
        is_div2 = any(kw.lower() in league.lower() for kw in DIV2_KEYWORDS)
        top5_kw = ["premier_league", "la_liga", "serie_a", "bundesliga", "ligue_1",
                   "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]
        is_top5 = any(kw in league for kw in top5_kw) and not is_div2
        is_prima = "primeira_liga" in league.lower()
        is_sb = "serie_b" in league.lower()

        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        md = json.loads(model_row['data_json'])
        hp = md.get('home_win_prob', 0.33); dp = md.get('draw_prob', 0.33); ap = md.get('away_win_prob', 0.34)
        v34_flags = md.get('scenario_flags', [])
        pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

        hp_x = hp; dp_x = dp; ap_x = ap

        # 去掉v3.4 dt
        for dt_flag, old_boost in DT_V34.items():
            if dt_flag in v34_flags:
                dp_x -= old_boost; hp_x += old_boost*(hp/(hp+ap)); ap_x += old_boost*(ap/(hp+ap))

        # 杯赛减draw
        if is_cup:
            dp_x -= 0.02; nd = hp_x + ap_x
            if nd > 0: hp_x += 0.02*(hp_x/nd); ap_x += 0.02*(ap_x/nd)
            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

        # primeira_liga减draw
        if is_prima:
            dp_x -= 0.02; nd = hp_x + ap_x
            if nd > 0: hp_x += 0.02*(hp_x/nd); ap_x += 0.02*(ap_x/nd)
            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

        # dt处理
        is_dt30 = 'draw_threshold_0.3' in v34_flags
        if is_dt30:
            if is_sb:
                # serie_b特殊处理
                if sb_strategy == 'v39_base':
                    # v3.9: boost=0, base=0.02, ah0=0.02
                    boost = 0.00; base = 0.02; ah0_e = 0.02
                elif sb_strategy == 'no_dt_adjust':
                    # 完全不做dt调整(serie_b dt30 draw率42.7%)
                    boost = 0.00; base = 0.00; ah0_e = 0.00
                elif sb_strategy == 'global_reduce_002':
                    # 全局减0.02draw
                    dp_x -= 0.02; nd = hp_x+ap_x
                    if nd > 0: hp_x += 0.02*(hp_x/nd); ap_x += 0.02*(ap_x/nd)
                    hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
                    boost = 0.00; base = 0.00; ah0_e = 0.00
                elif sb_strategy == 'keep_v34_dt':
                    # 保持v3.4的dt30行为(0.05 boost) — 不减
                    # 不去掉v3.4 dt boost → 直接用原始概率
                    hp_x = hp; dp_x = dp; ap_x = ap  # 重置回v3.4
                    boost = 0.00; base = 0.00; ah0_e = 0.00
            elif is_div2:
                boost = 0.00; base = 0.02; ah0_e = 0.02
            else:
                boost = 0.01; base = 0.01; ah0_e = 0.02

            if boost > 0:
                dp_x += boost; nd = hp_x+ap_x
                if nd > 0: hp_x -= boost*(hp_x/nd); ap_x -= boost*(ap_x/nd)
                hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

            ah_type = get_ah_type(conn, mk)
            rv = base + (ah0_e if ah_type == 'ah0' else 0)
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
            if pred_x == 'draw': cup_draw_pred += 1; cup_draw_correct += (1 if actual == 'draw' else 0)
            if actual == 'draw': cup_draw_actual += 1
        if is_prima:
            prima_n += 1
            if pred_x == actual: prima_correct += 1
            if pred_x == 'draw': prima_draw_pred += 1; prima_draw_correct += (1 if actual == 'draw' else 0)
        if is_sb:
            sb_n += 1
            if pred_x == actual: sb_correct += 1
            if pred_x == 'draw': sb_draw_pred += 1; sb_draw_correct += (1 if actual == 'draw' else 0)
        if is_div2: div2_n += 1; div2_correct += (1 if pred_x == actual else 0)
        if is_top5: top5_n += 1; top5_correct += (1 if pred_x == actual else 0)

        league_stats[league]['n'] += 1
        league_stats[league]['correct'] += (1 if pred_x == actual else 0)

    p(f"\n  === sb_strategy={sb_strategy} ===")
    p(f"    总体: {correct}/{total_n}={correct/total_n*100:.2f}% Brier={brier/total_n:.4f} net={net_gain:+d}")
    if cup_n > 0:
        dp = cup_draw_correct/cup_draw_pred*100 if cup_draw_pred > 0 else 0
        p(f"    杯赛: {cup_correct}/{cup_n}={cup_correct/cup_n*100:.1f}% draw_pred={cup_draw_pred} prec={dp:.0f}%")
    if prima_n > 0:
        dp = prima_draw_correct/prima_draw_pred*100 if prima_draw_pred > 0 else 0
        p(f"    prima: {prima_correct}/{prima_n}={prima_correct/prima_n*100:.1f}% draw_pred={prima_draw_pred} prec={dp:.0f}%")
    if sb_n > 0:
        dp = sb_draw_correct/sb_draw_pred*100 if sb_draw_pred > 0 else 0
        p(f"    serie_b: {sb_correct}/{sb_n}={sb_correct/sb_n*100:.1f}% draw_pred={sb_draw_pred} prec={dp:.0f}%")
    if div2_n > 0: p(f"    二级联赛: {div2_correct}/{div2_n}={div2_correct/div2_n*100:.1f}%")
    if top5_n > 0: p(f"    五大联赛: {top5_correct}/{top5_n}={top5_correct/top5_n*100:.1f}%")

    # 最差联赛
    p(f"    --- 最差5联赛(≥50场) ---")
    sorted_lg = sorted(league_stats.items(), key=lambda x: x[1]['correct']/x[1]['n'] if x[1]['n'] >= 50 else 1)
    for lg, s in sorted_lg[:5]:
        if s['n'] >= 50:
            p(f"      {lg:40s} {s['correct']}/{s['n']}={s['correct']/s['n']*100:.1f}%")

p(f"\n{'=' * 80}")
p("  v3.9.1整合验证完成")
p("=" * 80)

OUTPUT = 'd:/football_tools/fetchers/scripts/v391_validation.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f"结果已写入 {OUTPUT}")