"""
v3.8最终验证: 包含所有v3.5+规则 + DT30_EXTRA_DP_REDUCE=0.02
对比: v3.4基线 vs v3.8(含extra dp reduce)
"""
import sys, io, json, sqlite3, math
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

def normalize_probs(hp, dp, ap):
    total = hp + dp + ap
    if total <= 0:
        return 0.33, 0.33, 0.34
    return hp/total, dp/total, ap/total

# v3.5+规则调整量
RULE_ADJUST = {
    'global_upset_zone':        {'hp': -0.02, 'dp': 0.01,  'ap': 0.01},
    'motivation_mismatch':      {'hp': 0.02,  'dp': -0.01, 'ap': -0.01},
    'motivation_mismatch_light':{'hp': 0.007, 'dp': -0.003,'ap': -0.004},
    'cup_low_odds_risk':        {'hp': -0.02, 'dp': 0.008, 'ap': 0.012},
    'altitude_home':            {'hp': 0.05,  'dp': -0.015,'ap': -0.035},
    'sa_upset_zone':            {'hp': -0.02, 'dp': 0.012, 'ap': 0.008},
}
DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}
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

def apply_v35_rules(hp_x, dp_x, ap_x, v34_flags, m, conn, odds_h, dp_o, mot_f, home_team_raw):
    actual_month = int(m['date'][5:7]) if len(m['date']) >= 7 else 0
    league = m['league_standard'] or ''

    # global_upset_zone
    had_global_v34 = 'global_upset_zone' in v34_flags
    should_global_v38 = odds_h > 0 and GLOBAL_UPSET_ODDS_RANGE[0] <= odds_h <= GLOBAL_UPSET_ODDS_RANGE[1] and actual_month in GLOBAL_UPSET_MONTHS
    if had_global_v34 and not should_global_v38:
        adj = RULE_ADJUST['global_upset_zone']; hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']
    if should_global_v38 and not had_global_v34:
        adj = RULE_ADJUST['global_upset_zone']; hp_x -= adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']

    # motivation_mismatch
    mot_diff = 0; home_cat = ""; away_cat = ""
    if mot_f:
        mot_diff = mot_f.get('diff', 0)
        mot_raw = mot_f.get('raw', {})
        home_cat = mot_raw.get('home_category', '') or mot_f.get('home_category', '')
        away_cat = mot_raw.get('away_category', '') or mot_f.get('away_category', '')
    is_home_dead = home_cat in ("dead_rubber", "mid_table")
    is_away_desperate = away_cat in ("relegation", "relegation_battle", "title_race", "european")
    had_mismatch_v34 = 'motivation_mismatch' in v34_flags or 'motivation_mismatch_light' in v34_flags
    should_full = False; should_light = False
    if mot_f and mot_f.get('confidence', 0) > 0 and is_home_dead and is_away_desperate and mot_diff < MOTIVATION_MISMATCH_THRESHOLD:
        if odds_h and odds_h <= MOTIVATION_MISMATCH_MAX_ODDS:
            if actual_month in MOTIVATION_MISMATCH_END_MONTHS:
                should_full = True
            else:
                should_light = True
    if had_mismatch_v34:
        old_flag = 'motivation_mismatch' if 'motivation_mismatch' in v34_flags else 'motivation_mismatch_light'
        adj = RULE_ADJUST[old_flag]; hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']
    if should_full:
        adj = RULE_ADJUST['motivation_mismatch']; hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']
    elif should_light:
        adj = RULE_ADJUST['motivation_mismatch_light']; hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']

    # cup_low_odds_risk
    is_cup = any(kw in league for kw in CUP_LEAGUE_KEYWORDS)
    had_cup_v34 = 'cup_low_odds_risk' in v34_flags
    should_cup_v38 = is_cup and odds_h and odds_h <= CUP_LOW_ODDS_THRESHOLD
    if had_cup_v34:
        adj = RULE_ADJUST['cup_low_odds_risk']; hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']
    if should_cup_v38:
        adj = RULE_ADJUST['cup_low_odds_risk']; hp_x -= adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']

    # altitude_home
    is_altitude = False
    if home_team_raw:
        for team in ALTITUDE_TEAMS:
            if home_team_raw == team or (len(team) > 5 and team.lower() in home_team_raw.lower()):
                is_altitude = True; break
    if is_altitude and odds_h and odds_h >= 2.0:
        adj = RULE_ADJUST['altitude_home']; hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']

    # sa_upset_zone
    is_sa = any(kw in league for kw in SA_LEAGUE_KEYWORDS)
    had_sa_v34 = 'sa_upset_zone' in v34_flags
    should_sa_v38 = is_sa and odds_h and 1.35 <= odds_h <= 1.50
    if had_sa_v34:
        adj = RULE_ADJUST['sa_upset_zone']; hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']
    if should_sa_v38:
        adj = RULE_ADJUST['sa_upset_zone']; hp_x -= adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']

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
    def p(s=""):
        lines.append(s)

    p("=" * 70)
    p("  v3.8最终验证: 全部规则 + DT30_EXTRA_DP_REDUCE")
    p("=" * 70)

    # 测试多种extra_dp_reduce值
    for extra_dp_reduce in [0.00, 0.01, 0.02, 0.03, 0.04]:
        DT_V38 = {0.30: 0.01, 0.28: 0.01, 0.26: 0.005}

        total_n = 0
        correct = 0
        brier = 0.0
        net_gain = 0
        dt30_n = 0
        dt30_correct = 0
        dt30_brier = 0.0

        # 子群统计
        odds_2_3_n = 0; odds_2_3_correct = 0
        ah0_n = 0; ah0_correct = 0

        for m in matches:
            mk = m['match_key']
            actual = 'home' if m['home_score'] > m['away_score'] else \
                     'draw' if m['home_score'] == m['away_score'] else 'away'

            model_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
                (mk,)).fetchone()
            model_data = json.loads(model_row['data_json'])
            hp = model_data.get('home_win_prob', 0.33)
            dp = model_data.get('draw_prob', 0.33)
            ap = model_data.get('away_win_prob', 0.34)
            v34_flags = model_data.get('scenario_flags', [])
            pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

            odds_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
                (mk,)).fetchone()
            odds_data = json.loads(odds_row['data_json'])
            raw_odds = odds_data.get('raw', {})
            odds_h = float(raw_odds.get('avg_home_odds', 0) or raw_odds.get('closing_avg_home_odds', 0) or 0)
            dp_o = float(odds_data.get('draw_value', 0) or 0)

            mot_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:motivation'",
                (mk,)).fetchone()
            mot_f = json.loads(mot_row['data_json']) if mot_row else {}

            hp_x = hp; dp_x = dp; ap_x = ap

            # 去掉v3.4 draw_threshold
            for dt_flag, old_boost in DT_V34.items():
                if dt_flag in v34_flags:
                    dp_x -= old_boost
                    hp_x += old_boost * (hp / (hp + ap))
                    ap_x += old_boost * (ap / (hp + ap))

            # 新dt (v3.8)
            for threshold in sorted(DT_V38.keys(), reverse=True):
                boost = DT_V38[threshold]
                if dp_o >= threshold:
                    if boost > 0:
                        dp_x += boost
                        non_draw = hp_x + ap_x
                        if non_draw > 0:
                            hp_x -= boost * (hp_x / non_draw)
                            ap_x -= boost * (ap_x / non_draw)
                        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
                    # dt30触发后额外减draw概率
                    if threshold == 0.30 and extra_dp_reduce > 0:
                        dp_x -= extra_dp_reduce
                        non_draw = hp_x + ap_x
                        if non_draw > 0:
                            hp_x += extra_dp_reduce * (hp_x / non_draw)
                            ap_x += extra_dp_reduce * (ap_x / non_draw)
                        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
                    break

            # v3.5+规则
            hp_x, dp_x, ap_x = apply_v35_rules(hp_x, dp_x, ap_x, v34_flags, m, conn, odds_h, dp_o, mot_f, m['home_team'] or '')
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

            # dt30子群
            if dp_o >= 0.30:
                dt30_n += 1
                if pred_x == actual: dt30_correct += 1
                if actual == 'home':   dt30_brier += (hp_x-1)**2 + dp_x**2 + ap_x**2
                elif actual == 'draw': dt30_brier += hp_x**2 + (dp_x-1)**2 + ap_x**2
                else:                  dt30_brier += hp_x**2 + dp_x**2 + (ap_x-1)**2

            # odds 2-3子群
            if 2.0 <= odds_h < 3.0:
                odds_2_3_n += 1
                if pred_x == actual: odds_2_3_correct += 1

            # AH=0子群
            ah_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
                (mk,)).fetchone()
            if ah_row and 2.0 <= odds_h < 3.0:
                ah_data = json.loads(ah_row['data_json'])
                ah_hc = ah_data.get('raw', {}).get('closing_handicap', None)
                if ah_hc is not None and abs(float(ah_hc)) < 0.01:
                    ah0_n += 1
                    if pred_x == actual: ah0_correct += 1

        p(f"\n  --- extra_dp_reduce={extra_dp_reduce:.2f} ---")
        p(f"  总体: argmax={correct}/{total_n}={correct/total_n*100:.2f}% Brier={brier/total_n:.4f} net={net_gain:+d}")
        if dt30_n > 0:
            p(f"  dt30: {dt30_correct}/{dt30_n}={dt30_correct/dt30_n*100:.1f}% Brier={dt30_brier/dt30_n:.4f}")
        if odds_2_3_n > 0:
            p(f"  odds2-3: {odds_2_3_correct}/{odds_2_3_n}={odds_2_3_correct/odds_2_3_n*100:.1f}%")
        if ah0_n > 0:
            p(f"  AH=0+2-3: {ah0_correct}/{ah0_n}={ah0_correct/ah0_n*100:.1f}%")

    p(f"\n{'=' * 70}")
    p("  验证完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_final_validation.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

if __name__ == "__main__":
    main()
