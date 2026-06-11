"""
v3.5 场景详细分析 — 写入文件
"""
import sys, io, json, sqlite3, math
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'
OUTPUT = 'd:/football_tools/fetchers/scripts/v35_analysis_result.txt'

def implied_prob(oh, od, oa):
    margin = 1/oh + 1/od + 1/oa
    return {'home': 1/(oh*margin), 'draw': 1/(od*margin), 'away': 1/(oa*margin)}

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    matches = conn.execute("""
        SELECT m.match_key, m.date, m.home_team, m.away_team,
               m.league_standard, m.home_score, m.away_score
        FROM matches m
        WHERE m.status='finished' AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='factor' AND md.data_type='factor:euro_odds')
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='factor' AND md.data_type='factor:motivation'
                    AND json_extract(md.data_json, '$.confidence') > 0)
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='factor' AND md.data_type='factor:odds_movement'
                    AND json_extract(md.data_json, '$.confidence') > 0)
        ORDER BY m.date
    """).fetchall()

    lines = []
    def p(s=""):
        lines.append(s)

    p("=" * 70)
    p("  v3.5 场景详细分析 — 数据完整比赛")
    p("=" * 70)
    p(f"  数据完整比赛数: {len(matches)}")

    total_n = 0
    correct_v34 = 0
    correct_v35 = 0
    brier_v34 = 0.0
    brier_v35 = 0.0

    mismatch_matches = []
    cup_low_matches = []
    global_upset_matches = []
    altitude_matches = []
    sa_upset_matches = []
    mismatch_by_month = defaultdict(list)
    low_odds_may = []
    low_odds_other = []

    # 规则调整量（用于反推v3.4）
    RULE_ADJUST = {
        'global_upset_zone':        {'hp': -0.02, 'dp': 0.01,  'ap': 0.01},
        'motivation_mismatch':      {'hp': -0.03, 'dp': 0.009, 'ap': 0.021},
        'motivation_mismatch_light':{'hp': -0.01, 'dp': 0.003, 'ap': 0.007},
        'cup_low_odds_risk':        {'hp': -0.02, 'dp': 0.008, 'ap': 0.012},
        'altitude_home':            {'hp': 0.05,  'dp': -0.015,'ap': -0.035},
        'sa_upset_zone':            {'hp': -0.02, 'dp': 0.012, 'ap': 0.008},
    }

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'
        match_month = int(m['date'][5:7]) if len(m['date']) >= 7 else 0

        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)
        ).fetchone()
        if not model_row:
            continue

        model_data = json.loads(model_row['data_json'])
        flags = model_data.get('scenario_flags', [])
        hp_v35 = model_data.get('home_win_prob', 0.33)
        dp_v35 = model_data.get('draw_prob', 0.33)
        ap_v35 = model_data.get('away_win_prob', 0.34)
        pred_v35 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_v35, 'draw': dp_v35, 'away': ap_v35}[x])

        # 反推v3.4
        hp_v34 = hp_v35
        dp_v34 = dp_v35
        ap_v34 = ap_v35
        for flag in flags:
            if flag in RULE_ADJUST:
                adj = RULE_ADJUST[flag]
                hp_v34 -= adj['hp']
                dp_v34 -= adj['dp']
                ap_v34 -= adj['ap']

        total_v34 = hp_v34 + dp_v34 + ap_v34
        hp_v34 /= total_v34
        dp_v34 /= total_v34
        ap_v34 /= total_v34
        pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_v34, 'draw': dp_v34, 'away': ap_v34}[x])

        correct_v35 += (1 if pred_v35 == actual else 0)
        correct_v34 += (1 if pred_v34 == actual else 0)

        if actual == 'home':   brier_v35 += (hp_v35-1)**2 + dp_v35**2 + ap_v35**2
        elif actual == 'draw': brier_v35 += hp_v35**2 + (dp_v35-1)**2 + ap_v35**2
        else:                  brier_v35 += hp_v35**2 + dp_v35**2 + (ap_v35-1)**2

        if actual == 'home':   brier_v34 += (hp_v34-1)**2 + dp_v34**2 + ap_v34**2
        elif actual == 'draw': brier_v34 += hp_v34**2 + (dp_v34-1)**2 + ap_v34**2
        else:                  brier_v34 += hp_v34**2 + dp_v34**2 + (ap_v34-1)**2

        total_n += 1

        # 加载motivation factor
        mot_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:motivation'",
            (mk,)
        ).fetchone()
        mot_f = json.loads(mot_row['data_json']) if mot_row else {}
        mot_diff = mot_f.get('diff', 0)
        home_cat = mot_f.get('raw', {}).get('home_category', '') or mot_f.get('home_category', '')
        away_cat = mot_f.get('raw', {}).get('away_category', '') or mot_f.get('away_category', '')

        # 加载赔率
        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)
        ).fetchone()
        odds_f = json.loads(odds_row['data_json']) if odds_row else {}
        raw_odds = odds_f.get('raw', {})
        odds_h = float(raw_odds.get('avg_home_odds', 0) or raw_odds.get('closing_avg_home_odds', 0) or 0)

        if 'motivation_mismatch' in flags or 'motivation_mismatch_light' in flags:
            mismatch_matches.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'],
                'odds_h': odds_h, 'actual': actual,
                'score': f"{m['home_score']}-{m['away_score']}",
                'home_cat': home_cat, 'away_cat': away_cat,
                'mot_diff': mot_diff,
                'pred_v34': pred_v34, 'pred_v35': pred_v35,
                'flag': 'motivation_mismatch' if 'motivation_mismatch' in flags else 'light',
                'month': match_month,
                'hp_v34': hp_v34, 'hp_v35': hp_v35,
            })
            mismatch_by_month[match_month].append(actual)

        if 'cup_low_odds_risk' in flags:
            cup_low_matches.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'],
                'odds_h': odds_h, 'actual': actual,
                'score': f"{m['home_score']}-{m['away_score']}",
                'pred_v34': pred_v34, 'pred_v35': pred_v35,
                'hp_v34': hp_v34, 'hp_v35': hp_v35,
            })

        if 'global_upset_zone' in flags:
            global_upset_matches.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'],
                'odds_h': odds_h, 'actual': actual,
                'score': f"{m['home_score']}-{m['away_score']}",
                'pred_v34': pred_v34, 'pred_v35': pred_v35,
            })

        if 'altitude_home' in flags:
            altitude_matches.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'],
                'odds_h': odds_h, 'actual': actual,
                'pred_v34': pred_v34, 'pred_v35': pred_v35,
            })

        if 'sa_upset_zone' in flags:
            sa_upset_matches.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'],
                'odds_h': odds_h, 'actual': actual,
                'pred_v34': pred_v34, 'pred_v35': pred_v35,
            })

        if odds_h > 0 and odds_h <= 1.35 and m['league_standard'] not in \
           ['conference_league', 'copa_libertadores']:
            if match_month in [4, 5, 6]:
                low_odds_may.append({'odds_h': odds_h, 'actual': actual, 'pred': pred_v35})
            else:
                low_odds_other.append({'odds_h': odds_h, 'actual': actual, 'pred': pred_v35})

    conn.close()

    # 输出
    p(f"\n  === 数据完整比赛总体指标 ===")
    p(f"  v3.4: argmax={correct_v34}/{total_n}={correct_v34/total_n*100:.1f}%  Brier={brier_v34/total_n:.4f}")
    p(f"  v3.5: argmax={correct_v35}/{total_n}={correct_v35/total_n*100:.1f}%  Brier={brier_v35/total_n:.4f}")
    p(f"  变化: argmax {(correct_v35-correct_v34)/total_n*100:+.2f}pp  Brier {(brier_v35-brier_v34)/total_n:+.4f}")

    # 动机不对称详情
    p(f"\n  === 动机不对称冷门 (触发{len(mismatch_matches)}场) ===")
    for mm in sorted(mismatch_matches, key=lambda x: x['date']):
        result = "v" if mm['pred_v35'] == mm['actual'] else "x"
        old_result = "v" if mm['pred_v34'] == mm['actual'] else "x"
        changed = "->CHANGED!" if mm['pred_v34'] != mm['pred_v35'] else ""
        p(f"  {mm['date']} {mm['home']} vs {mm['away']} ({mm['league']})")
        p(f"    odds={mm['odds_h']:.2f} score={mm['score']} actual={mm['actual']}")
        p(f"    home_cat={mm['home_cat']} away_cat={mm['away_cat']} diff={mm['mot_diff']:.1f} month={mm['month']}")
        p(f"    v3.4={mm['pred_v34']}({old_result}) v3.5={mm['pred_v35']}({result}) {changed}")
        p(f"    hp: v3.4={mm['hp_v34']*100:.1f}% -> v3.5={mm['hp_v35']*100:.1f}%")

    mismatch_results = defaultdict(int)
    for mm in mismatch_matches:
        mismatch_results[mm['actual']] += 1
    p(f"\n  动机不对称结果分布: {dict(mismatch_results)}")
    mc35 = sum(1 for mm in mismatch_matches if mm['pred_v35'] == mm['actual'])
    mc34 = sum(1 for mm in mismatch_matches if mm['pred_v34'] == mm['actual'])
    if len(mismatch_matches) > 0:
        p(f"  v3.5准确率: {mc35}/{len(mismatch_matches)}={mc35/len(mismatch_matches)*100:.1f}%")
        p(f"  v3.4准确率: {mc34}/{len(mismatch_matches)}={mc34/len(mismatch_matches)*100:.1f}%")

    p(f"\n  === 动机不对称按月分布 ===")
    for month in sorted(mismatch_by_month.keys()):
        results = mismatch_by_month[month]
        n = len(results)
        home = sum(1 for r in results if r == 'home')
        draw = sum(1 for r in results if r == 'draw')
        away = sum(1 for r in results if r == 'away')
        draw_pct = draw/n*100 if n>0 else 0
        away_pct = away/n*100 if n>0 else 0
        p(f"  {month}月: {n}场 主胜={home}({home/n*100:.0f}%) 平={draw}({draw_pct:.0f}%) 客胜={away}({away_pct:.0f}%)")

    # 全球冷门区
    p(f"\n  === 全球冷门区 (5-6月赔率1.25-1.35, 触发{len(global_upset_matches)}场) ===")
    for gm in global_upset_matches:
        result = "v" if gm['pred_v35'] == gm['actual'] else "x"
        old_result = "v" if gm['pred_v34'] == gm['actual'] else "x"
        changed = "->CHANGED!" if gm['pred_v34'] != gm['pred_v35'] else ""
        p(f"  {gm['date']} {gm['home']} vs {gm['away']} ({gm['league']}) "
          f"odds={gm['odds_h']:.2f} score={gm['score']} "
          f"v3.4={gm['pred_v34']}({old_result}) v3.5={gm['pred_v35']}({result}) {changed}")

    gc35 = sum(1 for gm in global_upset_matches if gm['pred_v35'] == gm['actual'])
    gc34 = sum(1 for gm in global_upset_matches if gm['pred_v34'] == gm['actual'])
    if len(global_upset_matches) > 0:
        p(f"  v3.5准确率: {gc35}/{len(global_upset_matches)}={gc35/len(global_upset_matches)*100:.1f}%")
        p(f"  v3.4准确率: {gc34}/{len(global_upset_matches)}={gc34/len(global_upset_matches)*100:.1f}%")

    # 杯赛低赔率
    p(f"\n  === 杯赛低赔率 (触发{len(cup_low_matches)}场) ===")
    for cm in cup_low_matches:
        result = "v" if cm['pred_v35'] == cm['actual'] else "x"
        old_result = "v" if cm['pred_v34'] == cm['actual'] else "x"
        changed = "->CHANGED!" if cm['pred_v34'] != cm['pred_v35'] else ""
        p(f"  {cm['date']} {cm['home']} vs {cm['away']} ({cm['league']}) "
          f"odds={cm['odds_h']:.2f} score={cm['score']} "
          f"v3.4={cm['pred_v34']}({old_result}) v3.5={cm['pred_v35']}({result}) {changed}")

    # 高海拔
    p(f"\n  === 高海拔主场 (触发{len(altitude_matches)}场) ===")
    for am in altitude_matches:
        result = "v" if am['pred_v35'] == am['actual'] else "x"
        old_result = "v" if am['pred_v34'] == am['actual'] else "x"
        p(f"  {am['date']} {am['home']} vs {am['away']} ({am['league']}) "
          f"odds={am['odds_h']:.2f} actual={am['actual']} "
          f"v3.4={am['pred_v34']}({old_result}) v3.5={am['pred_v35']}({result})")

    # SA冷门区
    p(f"\n  === SA冷门区 (触发{len(sa_upset_matches)}场) ===")
    for sm in sa_upset_matches:
        result = "v" if sm['pred_v35'] == sm['actual'] else "x"
        old_result = "v" if sm['pred_v34'] == sm['actual'] else "x"
        p(f"  {sm['date']} {sm['home']} vs {sm['away']} ({sm['league']}) "
          f"odds={sm['odds_h']:.2f} actual={sm['actual']} "
          f"v3.4={sm['pred_v34']}({old_result}) v3.5={sm['pred_v35']}({result})")

    # 低赔率联赛冷门率
    p(f"\n  === 低赔率联赛(<1.35) 冷门率对比 ===")
    may_upsets = sum(1 for m in low_odds_may if m['actual'] != 'home')
    may_total = len(low_odds_may)
    other_upsets = sum(1 for m in low_odds_other if m['actual'] != 'home')
    other_total = len(low_odds_other)
    may_pct = may_upsets/may_total*100 if may_total > 0 else 0
    other_pct = other_upsets/other_total*100 if other_total > 0 else 0
    p(f"  4-6月: 冷门率={may_upsets}/{may_total}={may_pct:.1f}%")
    p(f"  其他月: 冷门率={other_upsets}/{other_total}={other_pct:.1f}%")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()