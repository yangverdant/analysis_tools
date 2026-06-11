"""
v3.8诊断: signal在2-3区间的影响
核心问题: 去掉draw_threshold后模型还是比赔率差，是否signal调整本身也有负贡献?
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
    p("  v3.8诊断: signal调整在2-3区间的净贡献")
    p("=" * 70)
    p(f"  总比赛数: {len(matches)}")

    # 在2-3区间，比较三种预测：
    # 1. 纯赔率argmax
    # 2. 模型(含signal+draw_threshold)
    # 3. 赔率概率+signal调整(无draw_threshold)

    stats = {
        "2-3区间": {"n": 0, "odds_correct": 0, "model_correct": 0,
                    "odds_only_correct": 0, "signal_hurts_odds": 0, "signal_helps_odds": 0,
                    "dt_hurts": 0, "dt_helps": 0,
                    "signal_changes": 0, "signal_correct": 0, "signal_wrong": 0,
                    "both_wrong": 0, "both_correct": 0,
                    "actual_dist": defaultdict(int),
                    "model_pred_dist": defaultdict(int),
                    "odds_pred_dist": defaultdict(int),
                    "brier_odds": 0.0, "brier_model": 0.0},
        "全区间": {"n": 0, "odds_correct": 0, "model_correct": 0,
                   "signal_changes": 0, "signal_correct": 0, "signal_wrong": 0,
                   "brier_odds": 0.0, "brier_model": 0.0},
    }

    # 按信号大小细分
    signal_impact = defaultdict(lambda: {"n": 0, "odds_ok": 0, "model_ok": 0,
                                          "signal_change": 0, "signal_correct": 0, "signal_wrong": 0})

    # 看模型信号到底把赔率概率推了多远
    prob_shift_stats = defaultdict(lambda: {"n": 0, "odds_ok": 0, "model_ok": 0})

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

        pred_m = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_m, 'draw': dp_m, 'away': ap_m}[x])
        pred_o = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

        # 概率偏移量
        prob_shift = abs(hp_m - hp_o) + abs(dp_m - dp_o) + abs(ap_m - ap_o)

        # 全区间统计
        s_all = stats["全区间"]
        s_all["n"] += 1
        if pred_o == actual: s_all["odds_correct"] += 1
        if pred_m == actual: s_all["model_correct"] += 1
        if pred_o != pred_m:
            s_all["signal_changes"] += 1
            if pred_m == actual: s_all["signal_correct"] += 1
            else: s_all["signal_wrong"] += 1
        if actual == 'home':   s_all["brier_odds"] += (hp_o-1)**2 + dp_o**2 + ap_o**2; s_all["brier_model"] += (hp_m-1)**2 + dp_m**2 + ap_m**2
        elif actual == 'draw': s_all["brier_odds"] += hp_o**2 + (dp_o-1)**2 + ap_o**2; s_all["brier_model"] += hp_m**2 + (dp_m-1)**2 + ap_m**2
        else:                  s_all["brier_odds"] += hp_o**2 + dp_o**2 + (ap_o-1)**2; s_all["brier_model"] += hp_m**2 + dp_m**2 + (ap_m-1)**2

        # 2-3区间详细
        if 2.0 <= odds_h < 3.0:
            s = stats["2-3区间"]
            s["n"] += 1
            s["actual_dist"][actual] += 1
            s["model_pred_dist"][pred_m] += 1
            s["odds_pred_dist"][pred_o] += 1
            if pred_o == actual: s["odds_correct"] += 1
            if pred_m == actual: s["model_correct"] += 1
            if pred_o != pred_m:
                s["signal_changes"] += 1
                if pred_m == actual: s["signal_correct"] += 1; s["signal_helps_odds"] += 1
                else: s["signal_wrong"] += 1; s["signal_hurts_odds"] += 1
            if pred_o == actual and pred_m == actual: s["both_correct"] += 1
            if pred_o != actual and pred_m != actual: s["both_wrong"] += 1
            if actual == 'home':   s["brier_odds"] += (hp_o-1)**2 + dp_o**2 + ap_o**2; s["brier_model"] += (hp_m-1)**2 + dp_m**2 + ap_m**2
            elif actual == 'draw': s["brier_odds"] += hp_o**2 + (dp_o-1)**2 + ap_o**2; s["brier_model"] += hp_m**2 + (dp_m-1)**2 + ap_m**2
            else:                  s["brier_odds"] += hp_o**2 + dp_o**2 + (ap_o-1)**2; s["brier_model"] += hp_m**2 + dp_m**2 + (ap_m-1)**2

            # 按信号大小
            sig_abs = abs(signal)
            if sig_abs < 0.05:
                sig_key = "<0.05"
            elif sig_abs < 0.15:
                sig_key = "0.05-0.15"
            elif sig_abs < 0.30:
                sig_key = "0.15-0.30"
            else:
                sig_key = ">0.30"

            si = signal_impact[sig_key]
            si["n"] += 1
            if pred_o == actual: si["odds_ok"] += 1
            if pred_m == actual: si["model_ok"] += 1
            if pred_o != pred_m:
                si["signal_change"] += 1
                if pred_m == actual: si["signal_correct"] += 1
                else: si["signal_wrong"] += 1

            # 按概率偏移量
            shift_key = f"{prob_shift*100:.0f}%"
            ps = prob_shift_stats[shift_key]
            ps["n"] += 1
            if pred_o == actual: ps["odds_ok"] += 1
            if pred_m == actual: ps["model_ok"] += 1

    conn.close()

    # 输出
    s = stats["2-3区间"]
    n = s["n"]
    p(f"\n  === 2-3区间基本统计 ===")
    p(f"  总场次: {n}")
    p(f"  实际分布: {dict(s['actual_dist'])}")
    p(f"  赔率预测分布: {dict(s['odds_pred_dist'])}")
    p(f"  模型预测分布: {dict(s['model_pred_dist'])}")
    p(f"  赔率argmax: {s['odds_correct']}/{n}={s['odds_correct']/n*100:.1f}%")
    p(f"  模型argmax: {s['model_correct']}/{n}={s['model_correct']/n*100:.1f}%")
    p(f"  差: {(s['model_correct']-s['odds_correct'])/n*100:+.1f}pp")
    p(f"  Brier: 赔率={s['brier_odds']/n:.4f} 模型={s['brier_model']/n:.4f}")
    p(f"  模型改赔率: 改对={s['signal_correct']} 改错={s['signal_wrong']} 净={s['signal_correct']-s['signal_wrong']:+d}")
    p(f"  两者都对: {s['both_correct']} 两者都错: {s['both_wrong']}")

    s_all = stats["全区间"]
    p(f"\n  === 全区间对比 ===")
    p(f"  赔率argmax: {s_all['odds_correct']}/{s_all['n']}={s_all['odds_correct']/s_all['n']*100:.1f}%")
    p(f"  模型argmax: {s_all['model_correct']}/{s_all['n']}={s_all['model_correct']/s_all['n']*100:.1f}%")
    p(f"  改赔率: 改对={s_all['signal_correct']} 改错={s_all['signal_wrong']} 净={s_all['signal_correct']-s_all['signal_wrong']:+d}")
    p(f"  Brier: 赔率={s_all['brier_odds']/s_all['n']:.4f} 模型={s_all['brier_model']/s_all['n']:.4f}")

    p(f"\n  === 按信号强度(2-3区间) ===")
    for sig_key in ["<0.05", "0.05-0.15", "0.15-0.30", ">0.30"]:
        si = signal_impact[sig_key]
        n = si["n"]
        if n == 0: continue
        p(f"  |signal|{sig_key}: n={n} 赔率={si['odds_ok']/n*100:.1f}% 模型={si['model_ok']/n*100:.1f}% "
          f"改对={si['signal_correct']} 改错={si['signal_wrong']} 净={si['signal_correct']-si['signal_wrong']:+d}")

    p(f"\n  === 按概率偏移量(2-3区间, top 15) ===")
    for shift_key in sorted(prob_shift_stats.keys(), key=lambda x: prob_shift_stats[x]["n"], reverse=True)[:15]:
        ps = prob_shift_stats[shift_key]
        n = ps["n"]
        if n < 20: continue
        p(f"  偏移{shift_key}: n={n} 赔率={ps['odds_ok']/n*100:.1f}% 模型={ps['model_ok']/n*100:.1f}%")

    p(f"\n{'=' * 70}")
    p("  诊断完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_signal_impact_2_3.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()