"""
v3.8.1完整增量验证v2: 分档dp reduce + 全部v3.5+规则
对比v3.8(统一0.02) vs v3.8.1(分档0.01+ah0.02)
"""
import sys, io, json, sqlite3, math
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

RULE_ADJUST = {
    'global_upset_zone':        {'hp': -0.02, 'dp': 0.01,  'ap': 0.01},
    'motivation_mismatch':      {'hp': 0.02,  'dp': -0.01, 'ap': -0.01},
    'motivation_mismatch_light':{'hp': 0.007, 'dp': -0.003,'ap': -0.004},
    'cup_low_odds_risk':        {'hp': -0.02, 'dp': 0.008, 'ap': 0.012},
    'altitude_home':            {'hp': 0.05,  'dp': -0.015,'ap': -0.035},
    'sa_upset_zone':            {'hp': -0.02, 'dp': 0.012, 'ap': 0.008},
}
MOTIVATION_MISMATCH_THRESHOLD = -1.0
MOTIVATION_MISMATCH_MAX_ODDS = 1.50
MOTIVATION_MISMATCH_END_MONTHS = [4, 5, 6]
CUP_LOW_ODDS_THRESHOLD = 1.40
GLOBAL_UPSET_ODDS_RANGE = (1.25, 1.35)
GLOBAL_UPSET_MONTHS = [5, 6]
CUP_LEAGUE_KEYWORDS = ["Champions League", "champions_league", "Europa League", "europa_league",
                       "Conference League", "conference_league", "Libertadores", "libertadores",
                       "Sudamericana", "sudamericana", "Copa Libertadores", "copa_libertadores",
                       "Copa Sudamericana", "copa_sudamericana", "ACL", "asian_champions", "Asian Champions"]
SA_LEAGUE_KEYWORDS = ["Libertadores", "libertadores", "Sudamericana", "sudamericana",
                      "Copa Libertadores", "copa_libertadores"]
ALTITUDE_TEAMS = ["Always Ready", "Bolivar", "The Strongest", "Jorge Wilstermann",
                  "Real Potosi", "Oriente Petrolero", "Cienciano", "Cusco FC",
                  "Universidad San Martin", "LDU Quito", "Universidad Catolica Ecuador",
                  "Aucas", "Deportivo Cali", "Atletico Nacional"]

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

def apply_v35_rules(hp_x, dp_x, ap_x, v34_flags, m, conn, odds_h, dp_o, mot_f, home_team_raw):
    actual_month = int(m['date'][5:7]) if len(m['date']) >= 7 else 0
    league = m['league_standard'] or ''

    had_global = 'global_upset_zone' in v34_flags
    should_global = odds_h > 0 and GLOBAL_UPSET_ODDS_RANGE[0] <= odds_h <= GLOBAL_UPSET_ODDS_RANGE[1] and actual_month in GLOBAL_UPSET_MONTHS
    if had_global and not should_global:
        a = RULE_ADJUST['global_upset_zone']; hp_x += a['hp']; dp_x += a['dp']; ap_x += a['ap']
    if should_global and not had_global:
        a = RULE_ADJUST['global_upset_zone']; hp_x -= a['hp']; dp_x += a['dp']; ap_x += a['ap']

    mot_diff = 0; home_cat = ""; away_cat = ""
    if mot_f:
        mot_diff = mot_f.get('diff', 0)
        mr = mot_f.get('raw', {})
        home_cat = mr.get('home_category', '') or mot_f.get('home_category', '')
        away_cat = mr.get('away_category', '') or mot_f.get('away_category', '')
    is_home_dead = home_cat in ("dead_rubber", "mid_table")
    is_away_desp = away_cat in ("relegation", "relegation_battle", "title_race", "european")
    had_mismatch = 'motivation_mismatch' in v34_flags or 'motivation_mismatch_light' in v34_flags
    should_full = False; should_light = False
    if mot_f and mot_f.get('confidence', 0) > 0 and is_home_dead and is_away_desp and mot_diff < MOTIVATION_MISMATCH_THRESHOLD:
        if odds_h and odds_h <= MOTIVATION_MISMATCH_MAX_ODDS:
            if actual_month in MOTIVATION_MISMATCH_END_MONTHS: should_full = True
            else: should_light = True
    if had_mismatch:
        of = 'motivation_mismatch' if 'motivation_mismatch' in v34_flags else 'motivation_mismatch_light'
        a = RULE_ADJUST[of]; hp_x += a['hp']; dp_x += a['dp']; ap_x += a['ap']
    if should_full:
        a = RULE_ADJUST['motivation_mismatch']; hp_x += a['hp']; dp_x += a['dp']; ap_x += a['ap']
    elif should_light:
        a = RULE_ADJUST['motivation_mismatch_light']; hp_x += a['hp']; dp_x += a['dp']; ap_x += a['ap']

    is_cup = any(kw in league for kw in CUP_LEAGUE_KEYWORDS)
    had_cup = 'cup_low_odds_risk' in v34_flags
    should_cup = is_cup and odds_h and odds_h <= CUP_LOW_ODDS_THRESHOLD
    if had_cup: a = RULE_ADJUST['cup_low_odds_risk']; hp_x += a['hp']; dp_x += a['dp']; ap_x += a['ap']
    if should_cup: a = RULE_ADJUST['cup_low_odds_risk']; hp_x -= a['hp']; dp_x += a['dp']; ap_x += a['ap']

    is_alt = False
    if home_team_raw:
        for t in ALTITUDE_TEAMS:
            if home_team_raw == t or (len(t) > 5 and t.lower() in home_team_raw.lower()): is_alt = True; break
    if is_alt and odds_h and odds_h >= 2.0: a = RULE_ADJUST['altitude_home']; hp_x += a['hp']; dp_x += a['dp']; ap_x += a['ap']

    is_sa = any(kw in league for kw in SA_LEAGUE_KEYWORDS)
    had_sa = 'sa_upset_zone' in v34_flags
    should_sa = is_sa and odds_h and 1.35 <= odds_h <= 1.50
    if had_sa: a = RULE_ADJUST['sa_upset_zone']; hp_x += a['hp']; dp_x += a['dp']; ap_x += a['ap']
    if should_sa: a = RULE_ADJUST['sa_upset_zone']; hp_x -= a['hp']; dp_x += a['dp']; ap_x += a['ap']

    return hp_x, dp_x, ap_x

def main():
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
    p("  v3.8 vs v3.8.1完整对比: 统一reduce vs 分档reduce + v3.5+规则")
    p("=" * 70)

    # 测试两种策略
    for version, dp_reduce_logic in [
        ("v3.8(统一0.02)", "uniform_0.02"),
        ("v3.8.1(分档0.01+ah0.02)", "tiered"),
    ]:
        total_n = 0; correct = 0; brier = 0.0; net_gain = 0
        subs = defaultdict(lambda: {'n': 0, 'correct': 0})
        draw_pred_n = 0; draw_pred_correct = 0; draw_actual = 0

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
            pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

            odds_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
                (mk,)).fetchone()
            od = json.loads(odds_row['data_json'])
            raw = od.get('raw', {})
            odds_h = float(raw.get('avg_home_odds', 0) or raw.get('closing_avg_home_odds', 0) or 0)

            mot_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:motivation'",
                (mk,)).fetchone()
            mot_f = json.loads(mot_row['data_json']) if mot_row else {}

            hp_x = hp; dp_x = dp; ap_x = ap

            # 去掉v3.4 dt
            for dt_flag, old_boost in DT_V34.items():
                if dt_flag in v34_flags:
                    dp_x -= old_boost; hp_x += old_boost * (hp/(hp+ap)); ap_x += old_boost * (ap/(hp+ap))

            # 新dt + dp reduce
            is_dt30 = 'draw_threshold_0.3' in v34_flags
            is_dt28 = 'draw_threshold_0.28' in v34_flags and not is_dt30
            is_dt26 = 'draw_threshold_0.26' in v34_flags and not is_dt30 and not is_dt28

            dt30_ah_type = None
            if is_dt30:
                dp_x += DT_V38[0.30]
                nd = hp_x + ap_x
                if nd > 0: hp_x -= DT_V38[0.30]*(hp_x/nd); ap_x -= DT_V38[0.30]*(ap_x/nd)
                hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
                # dp reduce
                if dp_reduce_logic == "uniform_0.02":
                    reduce_val = 0.02
                    dt30_ah_type = 'all'
                else:  # tiered
                    dt30_ah_type = get_ah_type(conn, mk)
                    reduce_val = 0.01 + (0.02 if dt30_ah_type == 'ah0' else 0)
                if reduce_val > 0:
                    dp_x -= reduce_val; nd = hp_x + ap_x
                    if nd > 0: hp_x += reduce_val*(hp_x/nd); ap_x += reduce_val*(ap_x/nd)
                    hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
            elif is_dt28:
                dp_x += DT_V38[0.28]; nd = hp_x + ap_x
                if nd > 0: hp_x -= DT_V38[0.28]*(hp_x/nd); ap_x -= DT_V38[0.28]*(ap_x/nd)
                hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
            elif is_dt26:
                dp_x += DT_V38[0.26]; nd = hp_x + ap_x
                if nd > 0: hp_x -= DT_V38[0.26]*(hp_x/nd); ap_x -= DT_V38[0.26]*(ap_x/nd)
                hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

            # v3.5+规则
            hp_x, dp_x, ap_x = apply_v35_rules(hp_x, dp_x, ap_x, v34_flags, m, conn, odds_h, 0, mot_f, m['home_team'] or '')
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

            if is_dt30:
                subs[f"dt30_{dt30_ah_type}"]['n'] += 1
                if pred_x == actual: subs[f"dt30_{dt30_ah_type}"]['correct'] += 1
            if 2.0 <= odds_h < 3.0:
                subs['odds_2_3']['n'] += 1
                if pred_x == actual: subs['odds_2_3']['correct'] += 1
            if pred_x == 'draw': draw_pred_n += 1; draw_pred_correct += (1 if actual == 'draw' else 0)
            if actual == 'draw': draw_actual += 1

        p(f"\n  === {version} ===")
        p(f"  argmax={correct}/{total_n}={correct/total_n*100:.2f}% Brier={brier/total_n:.4f} net={net_gain:+d}")
        p(f"  draw: pred={draw_pred_n} prec={draw_pred_correct/draw_pred_n*100:.1f}% recall={draw_pred_correct/draw_actual*100:.1f}%")
        for k, g in sorted(subs.items()):
            if g['n'] > 0:
                p(f"    [{k}] {g['correct']}/{g['n']}={g['correct']/g['n']*100:.1f}%")

    p(f"\n{'=' * 70}")
    p("  对比完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v381_comparison.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

if __name__ == "__main__":
    main()