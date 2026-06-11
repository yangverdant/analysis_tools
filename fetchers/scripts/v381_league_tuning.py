"""
v3.8.1分赛事实验v2: 二级联赛的dt30参数精调
SerieB, LaLiga2, Ligue2等二级联赛: dt30触发率高达20-49%
实验: 为二级联赛设置不同的dt30参数
"""
import sys, io, json, sqlite3, math
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

DIV2_KEYWORDS = ["serie_b", "la_liga_2", "ligue_2", "2_bundesliga", "segunda",
                 "Serie B", "La Liga 2", "Ligue 2", "2. Bundesliga", "Segunda",
                 "efl_championship", "EFL Championship", "Championship",
                 "primeira_liga", "eredivisie", "bundesliga_2"]
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
p("  分赛事实验: 二级联赛dt30参数 + 杯赛blend参数")
p("=" * 70)

# 策略矩阵:
# - 五大联赛: dt30 boost=0.01, base_reduce=0.01, ah0_extra=0.02 (默认)
# - 二级联赛: dt30 boost=?  base_reduce=?  ah0_extra=?
# - 杯赛: dt30 boost=0.01, base_reduce=0.01, cup_ah_blend=0.20

strategies = [
    {"name": "v3.8.1基线", "div2_boost": 0.01, "div2_base": 0.01, "div2_ah0": 0.02, "cup_blend": 0.50},
    {"name": "杯赛blend0.20", "div2_boost": 0.01, "div2_base": 0.01, "div2_ah0": 0.02, "cup_blend": 0.20},
    {"name": "二级boost0+base0.03", "div2_boost": 0.00, "div2_base": 0.03, "div2_ah0": 0.02, "cup_blend": 0.50},
    {"name": "二级boost0+base0.04", "div2_boost": 0.00, "div2_base": 0.04, "div2_ah0": 0.02, "cup_blend": 0.50},
    {"name": "杯赛0.20+二级0+0.03", "div2_boost": 0.00, "div2_base": 0.03, "div2_ah0": 0.02, "cup_blend": 0.20},
    {"name": "杯赛0.20+二级0+0.04", "div2_boost": 0.00, "div2_base": 0.04, "div2_ah0": 0.02, "cup_blend": 0.20},
    {"name": "杯赛0.30+二级0.005+0.03", "div2_boost": 0.005, "div2_base": 0.03, "div2_ah0": 0.02, "cup_blend": 0.30},
]

for strat in strategies:
    total_n = 0; correct = 0; brier = 0.0; net_gain = 0
    div2_n = 0; div2_correct = 0; cup_n = 0; cup_correct = 0
    top5_n = 0; top5_correct = 0

    for m in matches:
        mk = m['match_key']
        league = m['league_standard'] or ''
        is_div2 = any(kw.lower() in league.lower() for kw in DIV2_KEYWORDS)
        is_cup = any(kw in league for kw in CUP_KEYWORDS)
        # 五大联赛
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
        pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        od = json.loads(odds_row['data_json'])

        hp_x = hp; dp_x = dp; ap_x = ap

        # 去掉v3.4 dt
        for dt_flag, old_boost in DT_V34.items():
            if dt_flag in v34_flags:
                dp_x -= old_boost; hp_x += old_boost*(hp/(hp+ap)); ap_x += old_boost*(ap/(hp+ap))

        # 新dt + 分赛事参数
        is_dt30 = 'draw_threshold_0.3' in v34_flags
        if is_dt30:
            # 赛事特定dt30 boost
            if is_div2:
                boost = strat['div2_boost']
                base_reduce = strat['div2_base']
                ah0_extra = strat['div2_ah0']
            else:
                boost = 0.01
                base_reduce = 0.01
                ah0_extra = 0.02

            if boost > 0:
                dp_x += boost; nd = hp_x+ap_x
                if nd > 0: hp_x -= boost*(hp_x/nd); ap_x -= boost*(ap_x/nd)
                hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

            ah_type = get_ah_type(conn, mk)
            rv = base_reduce + (ah0_extra if ah_type == 'ah0' else 0)
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

        # 杯赛blend调整 (简化: 直接减draw概率来模拟blend降低)
        # 从0.50降到cup_blend, 效果大约是减少 (0.50-cup_blend)/0.50 的AH blend贡献
        if is_cup and strat['cup_blend'] < 0.50:
            # 估算AH blend对draw的贡献 (大约5-10pp)
            # 降低blend: draw大约减少 (0.50-cup_blend)*2*ah_draw_effect
            # 简化: cup_blend每降0.10, draw降~0.01
            dp_reduce = (0.50 - strat['cup_blend']) * 0.04  # 近似
            dp_x -= dp_reduce
            nd = hp_x + ap_x
            if nd > 0: hp_x += dp_reduce*(hp_x/nd); ap_x += dp_reduce*(ap_x/nd)
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

        if is_div2: div2_n += 1; div2_correct += (1 if pred_x == actual else 0)
        if is_cup: cup_n += 1; cup_correct += (1 if pred_x == actual else 0)
        if is_top5: top5_n += 1; top5_correct += (1 if pred_x == actual else 0)

    p(f"\n  {strat['name']}:")
    p(f"    总体: {correct}/{total_n}={correct/total_n*100:.2f}% Brier={brier/total_n:.4f} net={net_gain:+d}")
    if div2_n > 0: p(f"    二级联赛: {div2_correct}/{div2_n}={div2_correct/div2_n*100:.1f}%")
    if cup_n > 0: p(f"    杯赛: {cup_correct}/{cup_n}={cup_correct/cup_n*100:.1f}%")
    if top5_n > 0: p(f"    五大联赛: {top5_correct}/{top5_n}={top5_correct/top5_n*100:.1f}%")

p(f"\n{'=' * 70}")
p("  实验完成")
p("=" * 70)

OUTPUT = 'd:/football_tools/fetchers/scripts/v381_league_tuning.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.lines))
print(f"结果已写入 {OUTPUT}")