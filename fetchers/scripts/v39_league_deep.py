"""
v3.9分联赛深度分析: 每个联赛的模型表现、draw率、dt30比例、冷门率
为后续per-league参数调优提供数据基础
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
p("  v3.9分联赛深度分析: 模型表现 × draw率 × dt30比例 × 冷门率")
p("=" * 80)

# 每个联赛收集详细统计
league_data = defaultdict(lambda: {
    'n': 0, 'correct': 0,
    'home_n': 0, 'draw_n': 0, 'away_n': 0,  # 实际结果分布
    'pred_home': 0, 'pred_draw': 0, 'pred_away': 0,  # 模型预测分布
    'home_correct': 0, 'draw_correct': 0, 'away_correct': 0,  # 各结果正确数
    'dt30_n': 0, 'dt30_correct': 0,
    'dt28_n': 0, 'dt28_correct': 0,
    'dt26_n': 0, 'dt26_correct': 0,
    'no_dt_n': 0, 'no_dt_correct': 0,
    'draw_pred_correct': 0,  # 预测draw且实际draw
    'draw_actual_missed': 0,  # 实际draw但没预测draw
    'brier': 0.0,
    'avg_goals': 0.0,
    'upset_n': 0,  # 冷门(赔率最低的不赢)
    'is_cup': False, 'is_div2': False,
})

# 分组统计
group_data = {
    'cup': {'n': 0, 'correct': 0, 'draw_n': 0, 'draw_pred': 0, 'draw_pred_correct': 0, 'brier': 0.0},
    'div2': {'n': 0, 'correct': 0, 'draw_n': 0, 'draw_pred': 0, 'draw_pred_correct': 0, 'brier': 0.0},
    'top5': {'n': 0, 'correct': 0, 'draw_n': 0, 'draw_pred': 0, 'draw_pred_correct': 0, 'brier': 0.0},
    'other': {'n': 0, 'correct': 0, 'draw_n': 0, 'draw_pred': 0, 'draw_pred_correct': 0, 'brier': 0.0},
}

for m in matches:
    mk = m['match_key']
    league = m['league_standard'] or ''
    is_cup = any(kw in league for kw in CUP_KEYWORDS)
    is_div2 = any(kw.lower() in league.lower() for kw in DIV2_KEYWORDS)
    top5_kw = ["premier_league", "la_liga", "serie_a", "bundesliga", "ligue_1",
               "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]
    is_top5 = any(kw in league for kw in top5_kw) and not is_div2

    actual = 'home' if m['home_score'] > m['away_score'] else \
             'draw' if m['home_score'] == m['away_score'] else 'away'

    model_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
        (mk,)).fetchone()
    md = json.loads(model_row['data_json'])
    hp = md.get('home_win_prob', 0.33); dp = md.get('draw_prob', 0.33); ap = md.get('away_win_prob', 0.34)
    v34_flags = md.get('scenario_flags', [])

    hp_x = hp; dp_x = dp; ap_x = ap

    # 去掉v3.4 dt
    for dt_flag, old_boost in DT_V34.items():
        if dt_flag in v34_flags:
            dp_x -= old_boost; hp_x += old_boost*(hp/(hp+ap)); ap_x += old_boost*(ap/(hp+ap))

    # 杯赛减draw
    if is_cup and 0.02 > 0:
        dp_x -= 0.02
        nd = hp_x + ap_x
        if nd > 0:
            hp_x += 0.02 * (hp_x / nd)
            ap_x += 0.02 * (ap_x / nd)
        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

    # dt处理
    is_dt30 = 'draw_threshold_0.3' in v34_flags
    if is_dt30:
        if is_div2:
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
    pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])

    # 赔率最低的是谁(实际冷门判断)
    euro_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
        (mk,)).fetchone()
    odds_fav = 'home'  # 默认
    if euro_row:
        raw_euro = json.loads(euro_row['data_json']).get('raw', {})
        oh = float(raw_euro.get('avg_home_odds', 99) or 99)
        oa = float(raw_euro.get('avg_away_odds', 99) or 99)
        odds_fav = 'home' if oh < oa else 'away'
    is_upset = (actual != odds_fav and actual != 'draw')  # 非赔率最低方赢了

    # 记录联赛统计
    ld = league_data[league]
    ld['n'] += 1
    ld['correct'] += (1 if pred == actual else 0)
    ld['is_cup'] = is_cup
    ld['is_div2'] = is_div2

    # 实际分布
    if actual == 'home': ld['home_n'] += 1; ld['home_correct'] += (1 if pred == actual else 0)
    elif actual == 'draw': ld['draw_n'] += 1; ld['draw_correct'] += (1 if pred == actual else 0)
    else: ld['away_n'] += 1; ld['away_correct'] += (1 if pred == actual else 0)

    # 预测分布
    if pred == 'home': ld['pred_home'] += 1
    elif pred == 'draw': ld['pred_draw'] += 1
    else: ld['pred_away'] += 1

    # draw详情
    if pred == 'draw' and actual == 'draw': ld['draw_pred_correct'] += 1
    if actual == 'draw' and pred != 'draw': ld['draw_actual_missed'] += 1

    # dt分布
    if is_dt30: ld['dt30_n'] += 1; ld['dt30_correct'] += (1 if pred == actual else 0)
    elif 'draw_threshold_0.28' in v34_flags: ld['dt28_n'] += 1; ld['dt28_correct'] += (1 if pred == actual else 0)
    elif 'draw_threshold_0.26' in v34_flags: ld['dt26_n'] += 1; ld['dt26_correct'] += (1 if pred == actual else 0)
    else: ld['no_dt_n'] += 1; ld['no_dt_correct'] += (1 if pred == actual else 0)

    # Brier
    if actual == 'home':   ld['brier'] += (hp_x-1)**2 + dp_x**2 + ap_x**2
    elif actual == 'draw': ld['brier'] += hp_x**2 + (dp_x-1)**2 + ap_x**2
    else:                  ld['brier'] += hp_x**2 + dp_x**2 + (ap_x-1)**2

    # 场均进球
    ld['avg_goals'] += m['home_score'] + m['away_score']

    # 冷门
    if is_upset: ld['upset_n'] += 1

    # 分组统计
    if is_cup: grp = 'cup'
    elif is_div2: grp = 'div2'
    elif is_top5: grp = 'top5'
    else: grp = 'other'
    group_data[grp]['n'] += 1
    group_data[grp]['correct'] += (1 if pred == actual else 0)
    if actual == 'draw': group_data[grp]['draw_n'] += 1
    if pred == 'draw': group_data[grp]['draw_pred'] += 1
    if pred == 'draw' and actual == 'draw': group_data[grp]['draw_pred_correct'] += 1
    if actual == 'home':   group_data[grp]['brier'] += (hp_x-1)**2 + dp_x**2 + ap_x**2
    elif actual == 'draw': group_data[grp]['brier'] += hp_x**2 + (dp_x-1)**2 + ap_x**2
    else:                  group_data[grp]['brier'] += hp_x**2 + dp_x**2 + (ap_x-1)**2

# 输出分组统计
p(f"\n  === 分组统计 ===")
for grp in ['top5', 'div2', 'cup', 'other']:
    gd = group_data[grp]
    if gd['n'] == 0: continue
    acc = gd['correct']/gd['n']*100
    draw_rate = gd['draw_n']/gd['n']*100
    draw_prec = gd['draw_pred_correct']/gd['draw_pred']*100 if gd['draw_pred'] > 0 else 0
    brier = gd['brier']/gd['n']
    p(f"  {grp:6s}: {gd['correct']:4d}/{gd['n']:4d}={acc:5.1f}% Brier={brier:.4f} draw_rate={draw_rate:.1f}% draw_pred={gd['draw_pred']} prec={draw_prec:.0f}%")

# 输出每个联赛（≥30场）
p(f"\n  === 逐联赛分析(≥30场) ===")
p(f"  {'联赛':40s} {'N':>4s} {'准确率':>6s} {'Brier':>7s} {'Draw率':>6s} {'Draw预测':>8s} {'Draw精度':>7s} {'dt30%':>5s} {'冷门率':>6s} {'场均进球':>7s} {'类型':>5s}")
p(f"  {'-'*40} {'-'*4} {'-'*6} {'-'*7} {'-'*6} {'-'*8} {'-'*7} {'-'*5} {'-'*6} {'-'*7} {'-'*5}")

sorted_leagues = sorted(league_data.items(), key=lambda x: -x[1]['n'])
for lg, ld in sorted_leagues:
    if ld['n'] < 30: continue
    acc = ld['correct']/ld['n']*100
    draw_rate = ld['draw_n']/ld['n']*100
    draw_pred_total = ld['pred_draw']
    draw_prec = ld['draw_pred_correct']/draw_pred_total*100 if draw_pred_total > 0 else 0
    dt30_rate = ld['dt30_n']/ld['n']*100
    upset_rate = ld['upset_n']/ld['n']*100
    avg_goals = ld['avg_goals']/ld['n']
    brier = ld['brier']/ld['n']
    lg_type = 'C' if ld['is_cup'] else ('D2' if ld['is_div2'] else '  ')
    p(f"  {lg:40s} {ld['n']:4d} {acc:5.1f}% {brier:.4f} {draw_rate:5.1f}% {draw_pred_total:4d}/{ld['draw_n']:3d} {draw_prec:5.0f}%  {dt30_rate:4.0f}% {upset_rate:5.1f}% {avg_goals:5.1f}   {lg_type}")

# 重点分析: draw率异常的联赛
p(f"\n  === Draw率异常联赛(实际draw率 > 30% 或 < 20%, ≥50场) ===")
for lg, ld in sorted_leagues:
    if ld['n'] < 50: continue
    draw_rate = ld['draw_n']/ld['n']*100
    if draw_rate > 30 or draw_rate < 20:
        acc = ld['correct']/ld['n']*100
        draw_pred_total = ld['pred_draw']
        draw_prec = ld['draw_pred_correct']/draw_pred_total*100 if draw_pred_total > 0 else 0
        p(f"  {lg:40s} N={ld['n']:4d} acc={acc:5.1f}% draw_rate={draw_rate:.1f}% pred={draw_pred_total} prec={draw_prec:.0f}%")

# 重点分析: 准确率最低的联赛
p(f"\n  === 准确率最低联赛(≤45%, ≥50场) ===")
low_acc = [(lg, ld) for lg, ld in league_data.items() if ld['n'] >= 50 and ld['correct']/ld['n'] <= 0.45]
low_acc.sort(key=lambda x: x[1]['correct']/x[1]['n'])
for lg, ld in low_acc:
    acc = ld['correct']/ld['n']*100
    draw_rate = ld['draw_n']/ld['n']*100
    draw_pred_total = ld['pred_draw']
    draw_prec = ld['draw_pred_correct']/draw_pred_total*100 if draw_pred_total > 0 else 0
    dt30_rate = ld['dt30_n']/ld['n']*100
    avg_goals = ld['avg_goals']/ld['n']
    p(f"  {lg:40s} N={ld['n']:4d} acc={acc:5.1f}% draw_rate={draw_rate:.1f}% pred={draw_pred_total} prec={draw_prec:.0f}% dt30={dt30_rate:.0f}% goals={avg_goals:.1f}")

# 重点分析: draw预测效果最差的联赛
p(f"\n  === Draw预测效果最差(预测draw>5场且precision<20%, ≥50场) ===")
bad_draw = []
for lg, ld in league_data.items():
    if ld['n'] < 50: continue
    draw_pred_total = ld['pred_draw']
    if draw_pred_total <= 5: continue
    draw_prec = ld['draw_pred_correct']/draw_pred_total*100
    if draw_prec < 20:
        bad_draw.append((lg, ld, draw_prec))
bad_draw.sort(key=lambda x: x[2])
for lg, ld, draw_prec in bad_draw:
    acc = ld['correct']/ld['n']*100
    draw_rate = ld['draw_n']/ld['n']*100
    p(f"  {lg:40s} N={ld['n']:4d} acc={acc:5.1f}% draw_rate={draw_rate:.1f}% pred={ld['pred_draw']} prec={draw_prec:.0f}%")

# 场均进球 × draw率关系
p(f"\n  === 场均进球 × Draw率(≥50场) ===")
goal_draw = []
for lg, ld in league_data.items():
    if ld['n'] < 50: continue
    avg_goals = ld['avg_goals']/ld['n']
    draw_rate = ld['draw_n']/ld['n']
    goal_draw.append((lg, avg_goals, draw_rate, ld['n']))
goal_draw.sort(key=lambda x: x[1])
for lg, avg_g, dr, n in goal_draw:
    p(f"  {lg:40s} goals={avg_g:.1f} draw_rate={dr*100:.1f}% N={n}")

p(f"\n{'=' * 80}")
p("  分联赛深度分析完成")
p("=" * 80)

OUTPUT = 'd:/football_tools/fetchers/scripts/v39_league_deep.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f"结果已写入 {OUTPUT}")
