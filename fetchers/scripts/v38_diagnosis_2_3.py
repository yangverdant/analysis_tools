"""
v3.8诊断: odds 2.0-3.0区间深度分析
1. 按odds细分: 2.0-2.2, 2.2-2.5, 2.5-3.0 各自表现
2. 按signal方向: 正/负/近0，模型改赔率的正确率
3. 按场景flag: 哪些规则在2-3区间改错了
4. 概率校准: 模型各概率区间的实际命中率
5. 最大改错案例的pattern
"""
import sys, io, json, sqlite3, math
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

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
    p("  v3.8诊断: odds 2.0-3.0区间深度分析")
    p("=" * 70)
    p(f"  总比赛数: {len(matches)}")

    # === 数据结构 ===
    # 按odds子区间统计
    odds_bins = defaultdict(lambda: {"n": 0, "odds_ok": 0, "model_ok": 0,
                                      "both_ok": 0, "both_wrong": 0,
                                      "model_changes_correct": 0,
                                      "model_changes_wrong": 0,
                                      "actual_home": 0, "actual_draw": 0, "actual_away": 0,
                                      "pred_home": 0, "pred_draw": 0, "pred_away": 0,
                                      "odds_pred_home": 0, "odds_pred_draw": 0, "odds_pred_away": 0,
                                      "brier_model": 0.0, "brier_odds": 0.0})

    # 按signal方向
    signal_stats = defaultdict(lambda: {"n": 0, "model_ok": 0, "odds_ok": 0,
                                         "model_changes_correct": 0, "model_changes_wrong": 0})

    # 按flag在2-3区间的改错
    flag_2_3 = defaultdict(lambda: {"n": 0, "model_ok": 0, "odds_ok": 0,
                                     "model_changes_correct": 0, "model_changes_wrong": 0})

    # 概率校准 — 模型概率 vs 实际命中率
    prob_bins_home = defaultdict(lambda: {"n": 0, "hit": 0})
    prob_bins_draw = defaultdict(lambda: {"n": 0, "hit": 0})
    prob_bins_away = defaultdict(lambda: {"n": 0, "hit": 0})

    # 最大改错案例
    big_errors = []

    # signal对argmax的统计
    signal_argmax = defaultdict(lambda: {"n": 0, "home_n": 0, "draw_n": 0, "away_n": 0,
                                          "home_actual": 0, "draw_actual": 0, "away_actual": 0})

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        # 模型
        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        model_data = json.loads(model_row['data_json'])
        hp_m = model_data.get('home_win_prob', 0.33)
        dp_m = model_data.get('draw_prob', 0.33)
        ap_m = model_data.get('away_win_prob', 0.34)
        signal = model_data.get('signal_value', 0)
        flags = model_data.get('scenario_flags', [])
        pred_m = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_m, 'draw': dp_m, 'away': ap_m}[x])

        # 赔率
        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        hp_o = float(odds_data.get('home_value', 0) or 0)
        dp_o = float(odds_data.get('draw_value', 0) or 0)
        ap_o = float(odds_data.get('away_value', 0) or 0)
        odds_h = float(odds_data.get('raw', {}).get('avg_home_odds', 0) or odds_data.get('raw', {}).get('closing_avg_home_odds', 0) or 0)

        if odds_h <= 0: continue

        pred_o = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

        # --- 只分析2.0-3.0区间 ---
        if 2.0 <= odds_h < 3.0:
            # 子区间
            if odds_h < 2.2:
                bin_key = "2.0-2.2"
            elif odds_h < 2.5:
                bin_key = "2.2-2.5"
            else:
                bin_key = "2.5-3.0"

            b = odds_bins[bin_key]
            b["n"] += 1
            if pred_o == actual: b["odds_ok"] += 1
            if pred_m == actual: b["model_ok"] += 1
            if pred_o == actual and pred_m == actual: b["both_ok"] += 1
            if pred_o != actual and pred_m != actual: b["both_wrong"] += 1
            if pred_o != pred_m:
                if pred_m == actual: b["model_changes_correct"] += 1
                else: b["model_changes_wrong"] += 1
            b[f"actual_{actual}"] += 1
            b[f"pred_{pred_m}"] += 1
            b[f"odds_pred_{pred_o}"] += 1

            # Brier
            if actual == 'home': b["brier_model"] += (hp_m-1)**2 + dp_m**2 + ap_m**2; b["brier_odds"] += (hp_o-1)**2 + dp_o**2 + ap_o**2
            elif actual == 'draw': b["brier_model"] += hp_m**2 + (dp_m-1)**2 + ap_m**2; b["brier_odds"] += hp_o**2 + (dp_o-1)**2 + ap_o**2
            else: b["brier_model"] += hp_m**2 + dp_m**2 + (ap_m-1)**2; b["brier_odds"] += hp_o**2 + dp_o**2 + (ap_o-1)**2

            # Signal方向
            if abs(signal) < 0.03:
                sig_key = "signal~0"
            elif signal > 0.3:
                sig_key = "signal>+0.3"
            elif signal > 0.1:
                sig_key = "signal+0.1~0.3"
            elif signal > 0.03:
                sig_key = "signal+0.03~0.1"
            elif signal < -0.3:
                sig_key = "signal<-0.3"
            elif signal < -0.1:
                sig_key = "signal-0.3~-0.1"
            else:
                sig_key = "signal-0.1~-0.03"

            ss = signal_stats[sig_key]
            ss["n"] += 1
            if pred_m == actual: ss["model_ok"] += 1
            if pred_o == actual: ss["odds_ok"] += 1
            if pred_o != pred_m:
                if pred_m == actual: ss["model_changes_correct"] += 1
                else: ss["model_changes_wrong"] += 1

            # Flag统计
            for flag in flags:
                ff = flag_2_3[flag]
                ff["n"] += 1
                if pred_m == actual: ff["model_ok"] += 1
                if pred_o == actual: ff["odds_ok"] += 1
                if pred_o != pred_m:
                    if pred_m == actual: ff["model_changes_correct"] += 1
                    else: ff["model_changes_wrong"] += 1

            # 概率校准
            hp_bin = round(hp_m * 10) / 10  # 0.1步长
            dp_bin = round(dp_m * 10) / 10
            ap_bin = round(ap_m * 10) / 10
            prob_bins_home[hp_bin]["n"] += 1
            if actual == 'home': prob_bins_home[hp_bin]["hit"] += 1
            prob_bins_draw[dp_bin]["n"] += 1
            if actual == 'draw': prob_bins_draw[dp_bin]["hit"] += 1
            prob_bins_away[ap_bin]["n"] += 1
            if actual == 'away': prob_bins_away[ap_bin]["hit"] += 1

            # 改错案例
            if pred_o == actual and pred_m != actual:
                error_magnitude = max(hp_m, dp_m, ap_m) - {'home': hp_m, 'draw': dp_m, 'away': ap_m}[actual]
                big_errors.append({
                    'mk': mk, 'date': m['date'],
                    'home': m['home_team'], 'away': m['away_team'],
                    'league': m['league_standard'], 'odds_h': odds_h,
                    'actual': actual, 'score': f"{m['home_score']}-{m['away_score']}",
                    'pred_o': pred_o, 'pred_m': pred_m,
                    'hp_m': hp_m, 'dp_m': dp_m, 'ap_m': ap_m,
                    'hp_o': hp_o, 'dp_o': dp_o, 'ap_o': ap_o,
                    'signal': signal, 'flags': flags,
                    'error_mag': error_magnitude,
                })

        # --- signal argmax分析（全odds范围也收集，但主要看2-3） ---
        if 2.0 <= odds_h < 3.0:
            if abs(signal) < 0.03:
                sa_key = "~0"
            elif signal > 0:
                sa_key = "+"
            else:
                sa_key = "-"
            sa = signal_argmax[sa_key]
            sa["n"] += 1
            sa[f"{pred_m}_n"] += 1
            sa[f"{actual}_actual"] += 1

    conn.close()

    # === 输出 ===

    # 1. 子区间统计
    p(f"\n  === 1. Odds子区间: 模型 vs 赔率 ===")
    for bin_key in ["2.0-2.2", "2.2-2.5", "2.5-3.0"]:
        b = odds_bins[bin_key]
        n = b["n"]
        if n == 0: continue
        p(f"\n  --- odds {bin_key} (n={n}) ---")
        p(f"  实际分布: home={b['actual_home']}({b['actual_home']/n*100:.1f}%) draw={b['actual_draw']}({b['actual_draw']/n*100:.1f}%) away={b['actual_away']}({b['actual_away']/n*100:.1f}%)")
        p(f"  赔率预测: home={b['odds_pred_home']} draw={b['odds_pred_draw']} away={b['odds_pred_away']}")
        p(f"  模型预测: home={b['pred_home']} draw={b['pred_draw']} away={b['pred_away']}")
        p(f"  赔率argmax: {b['odds_ok']}/{n}={b['odds_ok']/n*100:.1f}%")
        p(f"  模型argmax: {b['model_ok']}/{n}={b['model_ok']/n*100:.1f}%")
        p(f"  差值: {(b['model_ok']-b['odds_ok'])/n*100:+.1f}pp")
        p(f"  模型Brier: {b['brier_model']/n:.4f}  赔率Brier: {b['brier_odds']/n:.4f}  差: {(b['brier_model']-b['brier_odds'])/n:+.4f}")
        ch = b["model_changes_correct"]
        cw = b["model_changes_wrong"]
        if ch + cw > 0:
            p(f"  模型改赔率: 改对{ch} 改错{cw} 净{ch-cw:+d}")

    # 2. Signal方向
    p(f"\n  === 2. Signal方向对2-3区间的影响 ===")
    for sig_key in sorted(signal_stats.keys()):
        ss = signal_stats[sig_key]
        n = ss["n"]
        if n == 0: continue
        p(f"  {sig_key}: n={n} 模型={ss['model_ok']/n*100:.1f}% 赔率={ss['odds_ok']/n*100:.1f}% "
          f"改对={ss['model_changes_correct']} 改错={ss['model_changes_wrong']} 净={ss['model_changes_correct']-ss['model_changes_wrong']:+d}")

    # 3. Flag在2-3区间
    p(f"\n  === 3. 场景flag在2-3区间的影响 ===")
    for flag in sorted(flag_2_3.keys(), key=lambda x: flag_2_3[x]["n"], reverse=True):
        ff = flag_2_3[flag]
        n = ff["n"]
        if n < 20: continue
        p(f"  {flag}: n={n} 模型={ff['model_ok']/n*100:.1f}% 赔率={ff['odds_ok']/n*100:.1f}% "
          f"改对={ff['model_changes_correct']} 改错={ff['model_changes_wrong']} 净={ff['model_changes_correct']-ff['model_changes_wrong']:+d}")

    # 4. 概率校准
    p(f"\n  === 4. 概率校准 (2-3区间) ===")
    p(f"  --- Home Win ---")
    for bin_val in sorted(prob_bins_home.keys()):
        pb = prob_bins_home[bin_val]
        n = pb["n"]
        if n < 10: continue
        actual_rate = pb["hit"] / n * 100
        p(f"  模型{bin_val*100:.0f}%: n={n} 实际={actual_rate:.1f}% 差={actual_rate-bin_val*100:+.1f}pp")

    p(f"\n  --- Draw ---")
    for bin_val in sorted(prob_bins_draw.keys()):
        pb = prob_bins_draw[bin_val]
        n = pb["n"]
        if n < 10: continue
        actual_rate = pb["hit"] / n * 100
        p(f"  模型{bin_val*100:.0f}%: n={n} 实际={actual_rate:.1f}% 差={actual_rate-bin_val*100:+.1f}pp")

    p(f"\n  --- Away Win ---")
    for bin_val in sorted(prob_bins_away.keys()):
        pb = prob_bins_away[bin_val]
        n = pb["n"]
        if n < 10: continue
        actual_rate = pb["hit"] / n * 100
        p(f"  模型{bin_val*100:.0f}%: n={n} 实际={actual_rate:.1f}% 差={actual_rate-bin_val*100:+.1f}pp")

    # 5. 最大改错案例
    p(f"\n  === 5. 模型改赔率改错的比赛 (按误差排序，top 30) ===")
    big_errors_sorted = sorted(big_errors, key=lambda x: x['error_mag'], reverse=True)
    for be in big_errors_sorted[:30]:
        p(f"  {be['date']} {be['home']} vs {be['away']} ({be['league']})")
        p(f"    odds_h={be['odds_h']:.2f} score={be['score']} actual={be['actual']}")
        p(f"    赔率→{be['pred_o']} 模型→{be['pred_m']}")
        p(f"    模型: h={be['hp_m']*100:.1f}% d={be['dp_m']*100:.1f}% a={be['ap_m']*100:.1f}%")
        p(f"    赔率: h={be['hp_o']*100:.1f}% d={be['dp_o']*100:.1f}% a={be['ap_o']*100:.1f}%")
        p(f"    signal={be['signal']:.4f} flags={','.join(be['flags'][:3])}")

    # 6. 改错pattern总结
    p(f"\n  === 6. 改错pattern ===")
    pattern_counts = defaultdict(int)
    for be in big_errors:
        if be['pred_m'] == 'draw' and be['pred_o'] != 'draw':
            pattern_counts['模型→draw(赔率→H/A)'] += 1
        elif be['pred_o'] == 'draw' and be['pred_m'] != 'draw':
            pattern_counts['赔率→draw(模型→H/A)'] += 1
        elif be['pred_m'] == 'home' and be['pred_o'] == 'away':
            pattern_counts['模型→home 赔率→away'] += 1
        elif be['pred_m'] == 'away' and be['pred_o'] == 'home':
            pattern_counts['模型→away 赔率→home'] += 1
        else:
            pattern_counts['其他'] += 1
    for pattern, cnt in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
        p(f"  {pattern}: {cnt}场")

    p(f"\n{'=' * 70}")
    p("  诊断完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_diagnosis_2_3.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()