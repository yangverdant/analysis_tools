"""
v3.8精确实验: 在2-3区间按信号强度分级调整
- 强信号(>0.15): 保留信号覆盖逻辑（数据证明有效）
- 中信号(0.03-0.15): 去掉信号覆盖，只保留小幅度概率调整
- 弱信号(<0.03): 完全信任赔率，不做任何调整
- draw_threshold: 在2-3区间全部禁用
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
    p("  v3.8精确实验: 按odds区间+信号强度分级调整策略")
    p("=" * 70)
    p(f"  总比赛数: {len(matches)}")

    # 实验策略
    strategies = {
        "v3.4基线": {"dt": "v34", "signal_scale_2_3": 1.0},
        "v3.7(dt=0.02)": {"dt": "v37", "signal_scale_2_3": 1.0},
        "v3.8-A: 2-3去dt": {"dt": "none_2_3", "signal_scale_2_3": 1.0},
        "v3.8-B: 2-3去dt+弱信号0": {"dt": "none_2_3", "signal_scale_2_3": "tiered"},
        "v3.8-C: 全去dt+弱信号0": {"dt": "none_all", "signal_scale_2_3": "tiered"},
    }

    for strat_name, strat in strategies.items():
        total_n = 0
        correct = 0
        brier = 0.0
        stats_2_3 = {"n": 0, "correct": 0, "brier": 0.0}
        net_gain = 0

        for m in matches:
            mk = m['match_key']
            actual = 'home' if m['home_score'] > m['away_score'] else \
                     'draw' if m['home_score'] == m['away_score'] else 'away'

            # 模型
            model_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
                (mk,)).fetchone()
            model_data = json.loads(model_row['data_json'])
            hp_v34 = model_data.get('home_win_prob', 0.33)
            dp_v34 = model_data.get('draw_prob', 0.33)
            ap_v34 = model_data.get('away_win_prob', 0.34)
            flags = model_data.get('scenario_flags', [])
            signal = model_data.get('signal_value', 0)
            pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_v34, 'draw': dp_v34, 'away': ap_v34}[x])

            # 赔率
            odds_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
                (mk,)).fetchone()
            odds_data = json.loads(odds_row['data_json'])
            odds_h = float(odds_data.get('raw', {}).get('avg_home_odds', 0) or odds_data.get('raw', {}).get('closing_avg_home_odds', 0) or 0)

            # 反推v3.4前的值（去掉draw_threshold和信号覆盖效果）
            # 步骤1: 去掉draw_threshold
            hp_base = hp_v34
            dp_base = dp_v34
            ap_base = ap_v34

            for dt_flag, boost in DT_BOOST_V34.items():
                if dt_flag in flags:
                    dp_base -= boost
                    hp_base += boost * (hp_v34 / (hp_v34 + ap_v34))
                    ap_base += boost * (ap_v34 / (hp_v34 + ap_v34))

            hp_base, dp_base, ap_base = normalize_probs(hp_base, dp_base, ap_base)

            # 步骤2: 去掉信号覆盖的效果（需要从signal推算）
            # 信号覆盖的效果: 当euro_conf<0.45且signal>0.15时，翻转或偏draw
            # 这很难精确反推，因为我们不知道euro_conf
            # 简化：假设v3.4的信号覆盖效果已经encoded在hp_v34/dp_v34/ap_v34中
            # 我们直接从v3.4的值开始，按策略调整

            # 更精确的方法：直接从v3.4值出发，只改draw_threshold
            hp_x = hp_v34
            dp_x = dp_v34
            ap_x = ap_v34

            # 先去掉所有v3.4的draw_threshold
            for dt_flag, boost in DT_BOOST_V34.items():
                if dt_flag in flags:
                    dp_x -= boost
                    hp_x += boost * (hp_v34 / (hp_v34 + ap_v34))
                    ap_x += boost * (ap_v34 / (hp_v34 + ap_v34))

            in_2_3 = odds_h >= 2.0 and odds_h < 3.0

            # 按策略加回draw_threshold
            if strat["dt"] == "v34":
                for dt_flag, boost in DT_BOOST_V34.items():
                    if dt_flag in flags:
                        dp_x += boost
                        hp_x -= boost * (hp_v34 / (hp_v34 + ap_v34))
                        ap_x -= boost * (ap_v34 / (hp_v34 + ap_v34))
            elif strat["dt"] == "v37":
                for dt_flag, boost_v37 in DT_BOOST_V37.items():
                    if dt_flag in flags:
                        dp_x += boost_v37
                        hp_x -= boost_v37 * (hp_v34 / (hp_v34 + ap_v34))
                        ap_x -= boost_v37 * (ap_v34 / (hp_v34 + ap_v34))
            elif strat["dt"] == "none_2_3":
                if not in_2_3:
                    for dt_flag, boost in DT_BOOST_V34.items():
                        if dt_flag in flags:
                            dp_x += boost
                            hp_x -= boost * (hp_v34 / (hp_v34 + ap_v34))
                            ap_x -= boost * (ap_v34 / (hp_v34 + ap_v34))
            elif strat["dt"] == "none_all":
                pass  # 完全不加draw_threshold

            # 按策略调整信号效果
            if strat["signal_scale_2_3"] == "tiered" and in_2_3:
                sig_abs = abs(signal)
                if sig_abs < 0.03:
                    # 弱信号：完全信任赔率，去掉信号覆盖效果
                    # 我们无法精确反推信号覆盖的效果，但可以用近似
                    # 从v3.4值推算：信号覆盖导致概率偏离赔率
                    hp_o = float(odds_data.get('home_value', 0) or 0)
                    dp_o = float(odds_data.get('draw_value', 0) or 0)
                    ap_o = float(odds_data.get('away_value', 0) or 0)
                    if hp_o > 0 and dp_o > 0 and ap_o > 0:
                        # 混合：80%赔率 + 20%模型(无dt)
                        hp_x = 0.8 * hp_o + 0.2 * hp_x
                        dp_x = 0.8 * dp_o + 0.2 * dp_x
                        ap_x = 0.8 * ap_o + 0.2 * ap_x
                elif sig_abs < 0.15:
                    # 中信号：减少信号覆盖效果
                    hp_o = float(odds_data.get('home_value', 0) or 0)
                    dp_o = float(odds_data.get('draw_value', 0) or 0)
                    ap_o = float(odds_data.get('away_value', 0) or 0)
                    if hp_o > 0 and dp_o > 0 and ap_o > 0:
                        # 混合：40%赔率 + 60%模型(无dt)
                        hp_x = 0.4 * hp_o + 0.6 * hp_x
                        dp_x = 0.4 * dp_o + 0.6 * dp_x
                        ap_x = 0.4 * ap_o + 0.6 * ap_x
                # 强信号(>0.15): 保持模型原样

            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
            pred_x = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])

            correct += (1 if pred_x == actual else 0)
            if actual == 'home':   brier += (hp_x-1)**2 + dp_x**2 + ap_x**2
            elif actual == 'draw': brier += hp_x**2 + (dp_x-1)**2 + ap_x**2
            else:                  brier += hp_x**2 + dp_x**2 + (ap_x-1)**2
            total_n += 1

            if in_2_3:
                stats_2_3["n"] += 1
                stats_2_3["correct"] += (1 if pred_x == actual else 0)
                if actual == 'home':   stats_2_3["brier"] += (hp_x-1)**2 + dp_x**2 + ap_x**2
                elif actual == 'draw': stats_2_3["brier"] += hp_x**2 + (dp_x-1)**2 + ap_x**2
                else:                  stats_2_3["brier"] += hp_x**2 + dp_x**2 + (ap_x-1)**2

            if pred_x != pred_v34:
                if pred_x == actual: net_gain += 1
                elif pred_v34 == actual: net_gain -= 1

        p(f"\n  --- {strat_name} ---")
        p(f"  总体: argmax={correct}/{total_n}={correct/total_n*100:.1f}% Brier={brier/total_n:.4f}")
        if stats_2_3["n"] > 0:
            p(f"  2-3区间: argmax={stats_2_3['correct']}/{stats_2_3['n']}={stats_2_3['correct']/stats_2_3['n']*100:.1f}% Brier={stats_2_3['brier']/stats_2_3['n']:.4f}")
        p(f"  vs v3.4 净收益: {net_gain:+d}场")

    p(f"\n{'=' * 70}")
    p("  实验完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_tiered_experiments.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()