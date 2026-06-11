"""
v3.5增量验证 — 从DB读取v3.4结果，反推v3.5差异
只重新运行触发了新规则的比赛，大幅提速
"""
import sys, io, json, sqlite3, math
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

# v3.5/v3.6/v3.7规则调整量（v3.7修正draw_threshold_0.30的boost）
RULE_ADJUST = {
    'global_upset_zone':        {'hp': -0.02, 'dp': 0.01,  'ap': 0.01},
    'motivation_mismatch':      {'hp': 0.02,  'dp': -0.01, 'ap': -0.01},  # 强化主胜
    'motivation_mismatch_light':{'hp': 0.007, 'dp': -0.003,'ap': -0.004},
    'cup_low_odds_risk':        {'hp': -0.02, 'dp': 0.008, 'ap': 0.012},
    'altitude_home':            {'hp': 0.05,  'dp': -0.015,'ap': -0.035},
    'sa_upset_zone':            {'hp': -0.02, 'dp': 0.012, 'ap': 0.008},
    'draw_threshold_30':        {'hp': -0.02, 'dp': 0.02,  'ap': 0.00},  # v3.7: 0.06→0.02
    'draw_threshold_28':        {'hp': -0.03, 'dp': 0.03,  'ap': 0.00},  # v3.7: rename
    'draw_threshold_26':        {'hp': -0.015,'dp': 0.015, 'ap': 0.00},  # v3.7: rename
}

# v3.5规则参数（放宽后的阈值）
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


def normalize_probs(hp, dp, ap):
    total = hp + dp + ap
    if total <= 0:
        return 0.33, 0.33, 0.34
    return hp / total, dp / total, ap / total


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 获取所有finished且有模型结果的比赛
    matches = conn.execute("""
        SELECT m.match_key, m.date, m.home_team, m.away_team,
               m.league_standard, m.home_score, m.away_score
        FROM matches m
        WHERE m.status='finished' AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='model' AND md.data_type='model:enhanced_linear')
        ORDER BY m.date
    """).fetchall()

    lines = []
    def p(s=""):
        lines.append(s)

    p("=" * 70)
    p("  v3.5增量验证 — 放宽阈值后各规则触发数和影响")
    p("=" * 70)
    p(f"  总比赛数: {len(matches)}")

    # 统计
    total_n = 0
    correct_v34 = 0
    correct_v35 = 0
    brier_v34 = 0.0
    brier_v35 = 0.0

    # v3.5新增规则触发统计
    flag_counts = defaultdict(int)
    flag_correct_v34 = defaultdict(int)
    flag_correct_v35 = defaultdict(int)
    flag_brier_v34 = defaultdict(float)
    flag_brier_v35 = defaultdict(float)

    # 动机不对称详细
    mismatch_detail = []

    # 杯赛低赔率详细
    cup_detail = []

    # prediction changed
    changed_preds = []

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'
        match_month = int(m['date'][5:7]) if len(m['date']) >= 7 else 0

        # 加载v3.4模型结果
        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)
        ).fetchone()
        if not model_row:
            continue

        model_data = json.loads(model_row['data_json'])
        hp_v34 = model_data.get('home_win_prob', 0.33)
        dp_v34 = model_data.get('draw_prob', 0.33)
        ap_v34 = model_data.get('away_win_prob', 0.34)
        v34_flags = model_data.get('scenario_flags', [])

        pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_v34, 'draw': dp_v34, 'away': ap_v34}[x])

        # 计算v3.5新增调整
        # 先反推v3.4的基础概率（去掉v3.4中的规则调整）
        # 然后重新用v3.5规则计算

        # 简化方法：直接从v3.4概率出发，计算v3.5新增/修改规则的增量
        hp_v35 = hp_v34
        dp_v35 = dp_v34
        ap_v35 = ap_v34

        v35_new_flags = []

        # 加载赔率
        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)
        ).fetchone()
        odds_h = 0
        if odds_row:
            odds_data = json.loads(odds_row['data_json'])
            raw_odds = odds_data.get('raw', {})
            odds_h = float(raw_odds.get('avg_home_odds', 0) or raw_odds.get('closing_avg_home_odds', 0) or 0)

        # 加载动机
        mot_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:motivation'",
            (mk,)
        ).fetchone()
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

        # ---- v3.5规则1: 全球冷门区(5-6月 odds 1.25-1.35) ----
        # 注意: v3.4是全年触发，v3.5改为仅5-6月
        # v3.4中已有global_upset_zone，需要先去掉v3.4的调整，再加v3.5的
        had_global_v34 = 'global_upset_zone' in v34_flags
        should_global_v35 = odds_h > 0 and GLOBAL_UPSET_ODDS_RANGE[0] <= odds_h <= GLOBAL_UPSET_ODDS_RANGE[1] and match_month in GLOBAL_UPSET_MONTHS

        # 如果v3.4触发了但v3.5不应触发(非5-6月)，去掉调整
        if had_global_v34 and not should_global_v35:
            adj = RULE_ADJUST['global_upset_zone']
            hp_v35 += adj['hp']
            dp_v35 += adj['dp']
            ap_v35 += adj['ap']

        # 如果v3.5应触发但v3.4没有（不太可能，v3.4全年触发）
        if should_global_v35 and not had_global_v34:
            adj = RULE_ADJUST['global_upset_zone']
            hp_v35 -= adj['hp']
            dp_v35 += adj['dp']
            ap_v35 += adj['ap']

        if should_global_v35:
            v35_new_flags.append('global_upset_zone')

        # ---- v3.5规则2: 动机不对称(放宽阈值) ----
        # v3.4阈值: diff<-1.5, odds<=1.35, home_cat=dead_rubber only, 4-6月
        # v3.5阈值: diff<-1.0, odds<=1.50, home_cat in (dead_rubber, mid_table), 4-6月
        is_home_dead = home_cat in ("dead_rubber", "mid_table")
        is_away_desperate = away_cat in ("relegation", "relegation_battle", "title_race", "european")

        had_mismatch_v34 = 'motivation_mismatch' in v34_flags or 'motivation_mismatch_light' in v34_flags

        should_mismatch_v35_full = False
        should_mismatch_v35_light = False

        if mot_f.get('confidence', 0) > 0 and is_home_dead and is_away_desperate and mot_diff < MOTIVATION_MISMATCH_THRESHOLD:
            if odds_h and odds_h <= MOTIVATION_MISMATCH_MAX_ODDS:
                if match_month in MOTIVATION_MISMATCH_END_MONTHS:
                    should_mismatch_v35_full = True
                else:
                    should_mismatch_v35_light = True

        # 去掉v3.4的动机不对称调整（如果有的话）
        if had_mismatch_v34:
            # v3.4只有motivation_mismatch（全年触发但阈值严格）
            old_flag = 'motivation_mismatch' if 'motivation_mismatch' in v34_flags else 'motivation_mismatch_light'
            adj = RULE_ADJUST[old_flag]
            hp_v35 += adj['hp']
            dp_v35 += adj['dp']
            ap_v35 += adj['ap']

        # 加上v3.5的动机不对称调整（方向修正：强化主胜）
        if should_mismatch_v35_full:
            adj = RULE_ADJUST['motivation_mismatch']
            hp_v35 += adj['hp']
            dp_v35 += adj['dp']
            ap_v35 += adj['ap']
            v35_new_flags.append('motivation_mismatch')
            mismatch_detail.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'league': league, 'odds_h': odds_h,
                'actual': actual, 'score': f"{m['home_score']}-{m['away_score']}",
                'home_cat': home_cat, 'away_cat': away_cat,
                'mot_diff': mot_diff, 'month': match_month,
                'hp_v34': hp_v34, 'hp_v35_raw': hp_v35,
            })
        elif should_mismatch_v35_light:
            adj = RULE_ADJUST['motivation_mismatch_light']
            hp_v35 += adj['hp']
            dp_v35 += adj['dp']
            ap_v35 += adj['ap']
            v35_new_flags.append('motivation_mismatch_light')

        # ---- v3.5规则3: 杯赛低赔率(1.25→1.40) ----
        is_cup = any(kw in league for kw in CUP_LEAGUE_KEYWORDS)
        had_cup_v34 = 'cup_low_odds_risk' in v34_flags
        should_cup_v35 = is_cup and odds_h and odds_h <= CUP_LOW_ODDS_THRESHOLD

        # 去掉v3.4的杯赛调整
        if had_cup_v34:
            adj = RULE_ADJUST['cup_low_odds_risk']
            hp_v35 += adj['hp']
            dp_v35 += adj['dp']
            ap_v35 += adj['ap']

        # 加上v3.5的杯赛调整
        if should_cup_v35:
            adj = RULE_ADJUST['cup_low_odds_risk']
            hp_v35 -= adj['hp']
            dp_v35 += adj['dp']
            ap_v35 += adj['ap']
            v35_new_flags.append('cup_low_odds_risk')
            cup_detail.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'league': league, 'odds_h': odds_h,
                'actual': actual, 'score': f"{m['home_score']}-{m['away_score']}",
            })

        # ---- v3.5规则4: 高海拔主场 ----
        # 这规则v3.4没有，v3.5新增
        is_altitude = False
        if home_team_raw:
            for team in ALTITUDE_TEAMS:
                if home_team_raw == team:
                    is_altitude = True
                    break
                if len(team) > 5 and team.lower() in home_team_raw.lower():
                    is_altitude = True
                    break

        should_altitude_v35 = is_altitude and odds_h and odds_h >= 2.0
        if should_altitude_v35:
            adj = RULE_ADJUST['altitude_home']
            hp_v35 += adj['hp']
            dp_v35 += adj['dp']
            ap_v35 += adj['ap']
            v35_new_flags.append('altitude_home')

        # ---- v3.5规则5: 南美冷门区 ----
        # v3.4没有，v3.5新增
        is_sa = any(kw in league for kw in SA_LEAGUE_KEYWORDS)
        had_sa_v34 = 'sa_upset_zone' in v34_flags
        should_sa_v35 = is_sa and odds_h and 1.35 <= odds_h <= 1.50

        if had_sa_v34:
            adj = RULE_ADJUST['sa_upset_zone']
            hp_v35 += adj['hp']
            dp_v35 += adj['dp']
            ap_v35 += adj['ap']

        if should_sa_v35:
            adj = RULE_ADJUST['sa_upset_zone']
            hp_v35 -= adj['hp']
            dp_v35 += adj['dp']
            ap_v35 += adj['ap']
            v35_new_flags.append('sa_upset_zone')

        # 保留v3.4中的draw_threshold和已有规则
        for flag in v34_flags:
            if flag.startswith('draw_threshold_') or flag == 'global_upset_zone':
                # draw_threshold不受v3.5影响
                if flag.startswith('draw_threshold_'):
                    v35_new_flags.append(flag)
            # global_upset_zone已在上面处理

        # 归一化v3.5概率
        hp_v35, dp_v35, ap_v35 = normalize_probs(hp_v35, dp_v35, ap_v35)

        pred_v35 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_v35, 'draw': dp_v35, 'away': ap_v35}[x])

        correct_v34 += (1 if pred_v34 == actual else 0)
        correct_v35 += (1 if pred_v35 == actual else 0)

        # Brier
        if actual == 'home':   brier_v34 += (hp_v34-1)**2 + dp_v34**2 + ap_v34**2
        elif actual == 'draw': brier_v34 += hp_v34**2 + (dp_v34-1)**2 + ap_v34**2
        else:                  brier_v34 += hp_v34**2 + dp_v34**2 + (ap_v34-1)**2

        if actual == 'home':   brier_v35 += (hp_v35-1)**2 + dp_v35**2 + ap_v35**2
        elif actual == 'draw': brier_v35 += hp_v35**2 + (dp_v35-1)**2 + ap_v35**2
        else:                  brier_v35 += hp_v35**2 + dp_v35**2 + (ap_v35-1)**2

        total_n += 1

        # Flag统计
        for flag in v35_new_flags:
            flag_counts[flag] += 1
            if pred_v35 == actual:
                flag_correct_v35[flag] += 1
            if pred_v34 == actual:
                flag_correct_v34[flag] += 1
            if actual == 'home':   flag_brier_v35[flag] += (hp_v35-1)**2 + dp_v35**2 + ap_v35**2
            elif actual == 'draw': flag_brier_v35[flag] += hp_v35**2 + (dp_v35-1)**2 + ap_v35**2
            else:                  flag_brier_v35[flag] += hp_v35**2 + dp_v35**2 + (ap_v35-1)**2
            if actual == 'home':   flag_brier_v34[flag] += (hp_v34-1)**2 + dp_v34**2 + ap_v34**2
            elif actual == 'draw': flag_brier_v34[flag] += hp_v34**2 + (dp_v34-1)**2 + ap_v34**2
            else:                  flag_brier_v34[flag] += hp_v34**2 + dp_v34**2 + (ap_v34-1)**2

        # 预测改变
        if pred_v34 != pred_v35:
            changed_preds.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'league': league,
                'pred_v34': pred_v34, 'pred_v35': pred_v35,
                'actual': actual,
                'score': f"{m['home_score']}-{m['away_score']}",
                'flags': v35_new_flags,
            })

    conn.close()

    # 输出
    p(f"\n  === 总体指标 ===")
    p(f"  v3.4: argmax={correct_v34}/{total_n}={correct_v34/total_n*100:.1f}%  Brier={brier_v34/total_n:.4f}")
    p(f"  v3.5: argmax={correct_v35}/{total_n}={correct_v35/total_n*100:.1f}%  Brier={brier_v35/total_n:.4f}")
    delta_acc = (correct_v35 - correct_v34) / total_n * 100
    delta_brier = brier_v35 / total_n - brier_v34 / total_n
    p(f"  变化: argmax {delta_acc:+.2f}pp  Brier {delta_brier:+.4f}")

    p(f"\n  === v3.5规则触发统计 ===")
    for flag, cnt in sorted(flag_counts.items(), key=lambda x: x[1], reverse=True):
        n = cnt
        acc_v35 = flag_correct_v35[flag] / n * 100 if n > 0 else 0
        acc_v34 = flag_correct_v34[flag] / n * 100 if n > 0 else 0
        bs_v35 = flag_brier_v35[flag] / n if n > 0 else 0
        bs_v34 = flag_brier_v34[flag] / n if n > 0 else 0
        p(f"  {flag}: {cnt}场 v3.4准确率={acc_v34:.1f}% v3.5准确率={acc_v35:.1f}% "
          f"Brier_v34={bs_v34:.4f} Brier_v35={bs_v35:.4f} ΔB={bs_v35-bs_v34:+.4f}")

    p(f"\n  === 预测方向改变的比赛 ({len(changed_preds)}场) ===")
    for cp in changed_preds[:30]:
        v35_ok = "✓" if cp['pred_v35'] == cp['actual'] else "✗"
        v34_ok = "✓" if cp['pred_v34'] == cp['actual'] else "✗"
        p(f"  {cp['date']} {cp['home']} vs {cp['away']} ({cp['league']}) "
          f"score={cp['score']} v3.4={cp['pred_v34']}({v34_ok}) v3.5={cp['pred_v35']}({v35_ok}) "
          f"flags={','.join(cp['flags'])}")

    if len(changed_preds) > 30:
        p(f"  ... 还有{len(changed_preds)-30}场")

    # 动机不对称详情
    p(f"\n  === 动机不对称冷门 (触发{len(mismatch_detail)}场) ===")
    mismatch_results = defaultdict(int)
    for mm in sorted(mismatch_detail, key=lambda x: x['date']):
        p(f"  {mm['date']} {mm['home']} vs {mm['away']} ({mm['league']})")
        p(f"    odds={mm['odds_h']:.2f} score={mm['score']} actual={mm['actual']}")
        p(f"    home_cat={mm['home_cat']} away_cat={mm['away_cat']} diff={mm['mot_diff']:.1f} month={mm['month']}")
        mismatch_results[mm['actual']] += 1
    p(f"\n  动机不对称结果分布: {dict(mismatch_results)}")

    # 杯赛低赔率详情
    p(f"\n  === 杯赛低赔率冷门 (触发{len(cup_detail)}场) ===")
    cup_results = defaultdict(int)
    for cm in sorted(cup_detail, key=lambda x: x['date']):
        p(f"  {cm['date']} {cm['home']} vs {cm['away']} ({cm['league']}) "
          f"odds={cm['odds_h']:.2f} score={cm['score']} actual={cm['actual']}")
        cup_results[cm['actual']] += 1
    p(f"\n  杯赛低赔率结果分布: {dict(cup_results)}")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v35_incremental_result.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")
    print(f"v3.5总指标: argmax {correct_v35}/{total_n}={correct_v35/total_n*100:.1f}% Brier {brier_v35/total_n:.4f}")
    print(f"v3.4总指标: argmax {correct_v34}/{total_n}={correct_v34/total_n*100:.1f}% Brier {brier_v34/total_n:.4f}")
    print(f"变化: argmax {delta_acc:+.2f}pp Brier {delta_brier:+.4f}")


if __name__ == "__main__":
    main()