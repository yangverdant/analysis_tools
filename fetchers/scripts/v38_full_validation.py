"""
v3.8完整验证: 所有改动综合效果
v3.7改动: motivation方向修正, cup阈值1.40, etc
v3.8改动: draw_threshold dt30=0, dt28=0.01, dt26=0.005
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
    p("  v3.8完整验证: 所有改动综合效果")
    p("=" * 70)

    # v3.7/v3.8规则调整量
    RULE_ADJUST = {
        'global_upset_zone':        {'hp': -0.02, 'dp': 0.01,  'ap': 0.01},
        'motivation_mismatch':      {'hp': 0.02,  'dp': -0.01, 'ap': -0.01},
        'motivation_mismatch_light':{'hp': 0.007, 'dp': -0.003,'ap': -0.004},
        'cup_low_odds_risk':        {'hp': -0.02, 'dp': 0.008, 'ap': 0.012},
        'altitude_home':            {'hp': 0.05,  'dp': -0.015,'ap': -0.035},
        'sa_upset_zone':            {'hp': -0.02, 'dp': 0.012, 'ap': 0.008},
    }

    # v3.4 draw_threshold
    DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}
    # v3.8 draw_threshold
    DT_V38 = {0.30: 0.00, 0.28: 0.01, 0.26: 0.005}

    # v3.5规则参数
    MOTIVATION_MISMATCH_THRESHOLD = -1.0
    MOTIVATION_MISMATCH_MAX_ODDS = 1.50
    MOTIVATION_MISMATCH_END_MONTHS = [4, 5, 6]
    CUP_LOW_ODDS_THRESHOLD = 1.40
    GLOBAL_UPSET_ODDS_RANGE = (1.25, 1.35)
    GLOBAL_UPSET_MONTHS = [5, 6]
    CUP_LEAGUE_KEYWORDS = ["Champions League", "champions_league", "Europa League", "europa_league",
                           "Conference League", "conference_league", "Libertadores", "libertadores",
                           "Sudamericana", "sudamericana", "Copa Libertadores", "copa_libertadores",
                           "Copa Sudamericana", "copa_sudamericana", "ACL", "asian_champions",
                           "Asian Champions"]
    SA_LEAGUE_KEYWORDS = ["Libertadores", "libertadores", "Sudamericana", "sudamericana",
                          "Copa Libertadores", "copa_libertadores"]
    ALTITUDE_TEAMS = [
        "Always Ready", "Bolivar", "The Strongest", "Jorge Wilstermann",
        "Real Potosi", "Oriente Petrolero",
        "Cienciano", "Cusco FC", "Universidad San Martin",
        "LDU Quito", "Universidad Catolica Ecuador", "Aucas",
        "Deportivo Cali", "Atletico Nacional",
    ]

    total_n = 0
    correct_v34 = 0
    correct_v38 = 0
    brier_v34 = 0.0
    brier_v38 = 0.0
    net_gain = 0
    changed_preds = []

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'
        match_month = int(m['date'][5:7]) if len(m['date']) >= 7 else 0

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

        # v3.8计算: 从v3.4出发
        hp_x = hp
        dp_x = dp
        ap_x = ap

        # 1. 去掉v3.4的draw_threshold
        for dt_flag, old_boost in DT_V34.items():
            if dt_flag in v34_flags:
                dp_x -= old_boost
                hp_x += old_boost * (hp / (hp + ap))
                ap_x += old_boost * (ap / (hp + ap))

        # 2. 加上v3.8的draw_threshold (break逻辑)
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
                break

        # 3. v3.5+规则调整 (global_upset, motivation, cup, altitude, sa)
        # 加载赔率
        mot_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:motivation'",
            (mk,)).fetchone()
        mot_f = {}
        mot_diff = 0
        home_cat = ""
        away_cat = ""
        if mot_row:
            mot_f = json.loads(mot_row['data_json'])
            mot_diff = mot_f.get('diff', 0)
            mot_raw = mot_f.get('raw', {})
            home_cat = mot_raw.get('home_category', '') or mot_f.get('home_category', '')
            away_cat = mot_raw.get('away_category', '') or mot_f.get('away_category', '')

        league = m['league_standard'] or ''
        home_team_raw = m['home_team'] or ''

        # global_upset_zone
        had_global_v34 = 'global_upset_zone' in v34_flags
        should_global_v38 = odds_h > 0 and GLOBAL_UPSET_ODDS_RANGE[0] <= odds_h <= GLOBAL_UPSET_ODDS_RANGE[1] and match_month in GLOBAL_UPSET_MONTHS
        if had_global_v34 and not should_global_v38:
            adj = RULE_ADJUST['global_upset_zone']
            hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']
        if should_global_v38 and not had_global_v34:
            adj = RULE_ADJUST['global_upset_zone']
            hp_x -= adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']

        # motivation_mismatch
        is_home_dead = home_cat in ("dead_rubber", "mid_table")
        is_away_desperate = away_cat in ("relegation", "relegation_battle", "title_race", "european")
        had_mismatch_v34 = 'motivation_mismatch' in v34_flags or 'motivation_mismatch_light' in v34_flags
        should_mismatch_full = False
        should_mismatch_light = False
        if mot_f.get('confidence', 0) > 0 and is_home_dead and is_away_desperate and mot_diff < MOTIVATION_MISMATCH_THRESHOLD:
            if odds_h and odds_h <= MOTIVATION_MISMATCH_MAX_ODDS:
                if match_month in MOTIVATION_MISMATCH_END_MONTHS:
                    should_mismatch_full = True
                else:
                    should_mismatch_light = True
        if had_mismatch_v34:
            old_flag = 'motivation_mismatch' if 'motivation_mismatch' in v34_flags else 'motivation_mismatch_light'
            adj = RULE_ADJUST[old_flag]
            hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']
        if should_mismatch_full:
            adj = RULE_ADJUST['motivation_mismatch']
            hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']
        elif should_mismatch_light:
            adj = RULE_ADJUST['motivation_mismatch_light']
            hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']

        # cup_low_odds_risk
        is_cup = any(kw in league for kw in CUP_LEAGUE_KEYWORDS)
        had_cup_v34 = 'cup_low_odds_risk' in v34_flags
        should_cup_v38 = is_cup and odds_h and odds_h <= CUP_LOW_ODDS_THRESHOLD
        if had_cup_v34:
            adj = RULE_ADJUST['cup_low_odds_risk']
            hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']
        if should_cup_v38:
            adj = RULE_ADJUST['cup_low_odds_risk']
            hp_x -= adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']

        # altitude_home
        is_altitude = False
        if home_team_raw:
            for team in ALTITUDE_TEAMS:
                if home_team_raw == team or (len(team) > 5 and team.lower() in home_team_raw.lower()):
                    is_altitude = True
                    break
        should_altitude = is_altitude and odds_h and odds_h >= 2.0
        if should_altitude:
            adj = RULE_ADJUST['altitude_home']
            hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']

        # sa_upset_zone
        is_sa = any(kw in league for kw in SA_LEAGUE_KEYWORDS)
        had_sa_v34 = 'sa_upset_zone' in v34_flags
        should_sa_v38 = is_sa and odds_h and 1.35 <= odds_h <= 1.50
        if had_sa_v34:
            adj = RULE_ADJUST['sa_upset_zone']
            hp_x += adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']
        if should_sa_v38:
            adj = RULE_ADJUST['sa_upset_zone']
            hp_x -= adj['hp']; dp_x += adj['dp']; ap_x += adj['ap']

        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
        pred_x = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])

        correct_v34 += (1 if pred_v34 == actual else 0)
        correct_v38 += (1 if pred_x == actual else 0)
        if actual == 'home':   brier_v34 += (hp-1)**2 + dp**2 + ap**2; brier_v38 += (hp_x-1)**2 + dp_x**2 + ap_x**2
        elif actual == 'draw': brier_v34 += hp**2 + (dp-1)**2 + ap**2; brier_v38 += hp_x**2 + (dp_x-1)**2 + ap_x**2
        else:                  brier_v34 += hp**2 + dp**2 + (ap-1)**2; brier_v38 += hp_x**2 + dp_x**2 + (ap_x-1)**2
        total_n += 1

        if pred_x != pred_v34:
            if pred_x == actual: net_gain += 1
            elif pred_v34 == actual: net_gain -= 1
            changed_preds.append({
                'date': m['date'], 'home': m['home_team'], 'away': m['away_team'],
                'league': league, 'actual': actual,
                'score': f"{m['home_score']}-{m['away_score']}",
                'pred_v34': pred_v34, 'pred_v38': pred_x,
            })

    conn.close()

    p(f"\n  === v3.8完整验证 ===")
    p(f"  v3.4: argmax={correct_v34}/{total_n}={correct_v34/total_n*100:.2f}% Brier={brier_v34/total_n:.4f}")
    p(f"  v3.8: argmax={correct_v38}/{total_n}={correct_v38/total_n*100:.2f}% Brier={brier_v38/total_n:.4f}")
    p(f"  变化: argmax {(correct_v38-correct_v34)/total_n*100:+.2f}pp Brier {brier_v38/total_n-brier_v34/total_n:+.4f}")
    p(f"  净收益: {net_gain:+d}场")
    p(f"  预测改变: {len(changed_preds)}场")

    # 改变详情(前20)
    for cp in changed_preds[:20]:
        v38_ok = "✓" if cp['pred_v38'] == cp['actual'] else "✗"
        v34_ok = "✓" if cp['pred_v34'] == cp['actual'] else "✗"
        p(f"  {cp['date']} {cp['home']} vs {cp['away']} ({cp['league']}) "
          f"score={cp['score']} v3.4={cp['pred_v34']}({v34_ok}) v3.8={cp['pred_v38']}({v38_ok})")

    p(f"\n{'=' * 70}")
    p("  验证完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_full_validation.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")
    print(f"v3.8: argmax {correct_v38}/{total_n}={correct_v38/total_n*100:.2f}% Brier {brier_v38/total_n:.4f}")
    print(f"v3.4: argmax {correct_v34}/{total_n}={correct_v34/total_n*100:.2f}% Brier {brier_v34/total_n:.4f}")
    print(f"净收益: {net_gain:+d}")


if __name__ == "__main__":
    main()