"""
v3.8实验: 按odds区间调整draw_threshold boost幅度
核心思路: 低赔率区间(主胜明确) → draw_threshold意义大
中赔率区间(竞争激烈) → draw_threshold应减小或禁用
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

    # 多组实验: 不同odds区间的draw_threshold策略
    experiments = {
        "A: 全去掉2-3区间": lambda odds_h: 0.0 if 2.0 <= odds_h < 3.0 else None,
        "B: 2-3区间减半": lambda odds_h: 0.5 if 2.0 <= odds_h < 3.0 else None,
        "C: 2.5-3.0全去掉 2.0-2.5减半": lambda odds_h: 0.0 if odds_h >= 2.5 else 0.5 if odds_h >= 2.0 else None,
        "D: 2.5-3.0减半 2.0-2.5不变": lambda odds_h: 0.5 if odds_h >= 2.5 else None,
        "E: v3.7(0.30→0.02)": lambda odds_h: None,  # baseline, 不改变
    }

    # v3.4原始draw_threshold调整量
    DT_BOOST_V34 = {
        'draw_threshold_0.3': 0.05,
        'draw_threshold_0.28': 0.03,
        'draw_threshold_0.26': 0.015,
    }
    # v3.7调整量
    DT_BOOST_V37 = {
        'draw_threshold_0.3': 0.02,
        'draw_threshold_0.28': 0.03,
        'draw_threshold_0.26': 0.015,
    }

    p("=" * 70)
    p("  v3.8多实验: 按odds区间调整draw_threshold策略")
    p("=" * 70)
    p(f"  总比赛数: {len(matches)}")

    for exp_name, scale_fn in experiments.items():
        total_n = 0
        correct = 0
        brier = 0.0
        correct_2_3 = 0
        n_2_3 = 0
        brier_2_3 = 0.0
        changed = 0
        net_gain = 0

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
            flags = model_data.get('scenario_flags', [])
            pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

            odds_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
                (mk,)).fetchone()
            odds_data = json.loads(odds_row['data_json'])
            odds_h = float(odds_data.get('raw', {}).get('avg_home_odds', 0) or odds_data.get('raw', {}).get('closing_avg_home_odds', 0) or 0)

            # 计算v3.x概率
            hp_x = hp
            dp_x = dp
            ap_x = ap

            # 先去掉v3.4的所有draw_threshold
            for dt_flag, boost_v34 in DT_BOOST_V34.items():
                if dt_flag in flags:
                    dp_x -= boost_v34
                    hp_x += boost_v34 * (hp / (hp + ap))
                    ap_x += boost_v34 * (ap / (hp + ap))

            # 然后按实验策略加回
            scale = scale_fn(odds_h)
            for dt_flag, boost_v34 in DT_BOOST_V34.items():
                if dt_flag in flags:
                    if scale is None:
                        # 不在这个区间，用v3.7的boost
                        boost_x = DT_BOOST_V37[dt_flag]
                    else:
                        # 在这个区间，按比例缩放v3.4的boost
                        boost_x = boost_v34 * scale

                    dp_x += boost_x
                    hp_x -= boost_x * (hp / (hp + ap))
                    ap_x -= boost_x * (ap / (hp + ap))

            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
            pred_x = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])

            correct += (1 if pred_x == actual else 0)
            if actual == 'home':   brier += (hp_x-1)**2 + dp_x**2 + ap_x**2
            elif actual == 'draw': brier += hp_x**2 + (dp_x-1)**2 + ap_x**2
            else:                  brier += hp_x**2 + dp_x**2 + (ap_x-1)**2
            total_n += 1

            if 2.0 <= odds_h < 3.0:
                correct_2_3 += (1 if pred_x == actual else 0)
                if actual == 'home':   brier_2_3 += (hp_x-1)**2 + dp_x**2 + ap_x**2
                elif actual == 'draw': brier_2_3 += hp_x**2 + (dp_x-1)**2 + ap_x**2
                else:                  brier_2_3 += hp_x**2 + dp_x**2 + (ap_x-1)**2
                n_2_3 += 1

            if pred_x != pred_v34:
                changed += 1
                if pred_x == actual: net_gain += 1
                elif pred_v34 == actual: net_gain -= 1

        p(f"\n  --- {exp_name} ---")
        p(f"  总体: argmax={correct}/{total_n}={correct/total_n*100:.1f}% Brier={brier/total_n:.4f}")
        if n_2_3 > 0:
            p(f"  2-3区间: argmax={correct_2_3}/{n_2_3}={correct_2_3/n_2_3*100:.1f}% Brier={brier_2_3/n_2_3:.4f}")
        p(f"  预测改变: {changed}场 净收益: {net_gain:+d}")

    # 也加v3.4基线
    correct_v34 = 0
    brier_v34 = 0.0
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
        pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
        correct_v34 += (1 if pred_v34 == actual else 0)
        if actual == 'home':   brier_v34 += (hp-1)**2 + dp**2 + ap**2
        elif actual == 'draw': brier_v34 += hp**2 + (dp-1)**2 + ap**2
        else:                  brier_v34 += hp**2 + dp**2 + (ap-1)**2

    p(f"\n  --- v3.4基线 ---")
    p(f"  总体: argmax={correct_v34}/{len(matches)}={correct_v34/len(matches)*100:.1f}% Brier={brier_v34/len(matches):.4f}")

    p(f"\n{'=' * 70}")
    p("  实验完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_dt_scale_experiments.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()