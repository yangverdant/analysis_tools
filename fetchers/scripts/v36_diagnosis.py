"""
v3.6全局诊断 — 模型预测分布 vs 实际分布
找出模型最大的系统性偏差
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
        ORDER BY m.date
    """).fetchall()

    lines = []
    def p(s=""):
        lines.append(s)

    p("=" * 70)
    p("  v3.6全局诊断 — 预测分布 vs 实际分布")
    p("=" * 70)
    p(f"  总比赛数: {len(matches)}")

    # === 1. 总体预测/实际分布 ===
    actual_dist = defaultdict(int)
    pred_dist = defaultdict(int)
    pred_correct = defaultdict(int)

    # === 2. 按赔率区间的预测偏差 ===
    odds_stats = defaultdict(lambda: {"n": 0, "actual_home": 0, "actual_draw": 0, "actual_away": 0,
                                       "pred_home": 0, "pred_draw": 0, "pred_away": 0,
                                       "pred_home_correct": 0, "pred_draw_correct": 0, "pred_away_correct": 0,
                                       "avg_hp_pred": 0.0, "avg_dp_pred": 0.0, "avg_ap_pred": 0.0,
                                       "brier": 0.0})

    # === 3. 按联赛的预测偏差 ===
    league_stats = defaultdict(lambda: {"n": 0, "actual_home": 0, "actual_draw": 0, "actual_away": 0,
                                         "pred_home": 0, "pred_draw": 0, "pred_away": 0,
                                         "correct": 0, "brier": 0.0})

    # === 4. 模型概率校准 — 按预测概率区间 ===
    hp_calibration = defaultdict(lambda: {"n": 0, "actual_home": 0})
    dp_calibration = defaultdict(lambda: {"n": 0, "actual_draw": 0})
    ap_calibration = defaultdict(lambda: {"n": 0, "actual_away": 0})

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)
        ).fetchone()
        if not model_row:
            continue

        model_data = json.loads(model_row['data_json'])
        hp = model_data.get('home_win_prob', 0.33)
        dp = model_data.get('draw_prob', 0.33)
        ap = model_data.get('away_win_prob', 0.34)
        pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

        actual_dist[actual] += 1
        pred_dist[pred] += 1
        pred_correct[pred] += (1 if pred == actual else 0)

        # Brier
        if actual == 'home':   brier = (hp-1)**2 + dp**2 + ap**2
        elif actual == 'draw': brier = hp**2 + (dp-1)**2 + ap**2
        else:                  brier = hp**2 + dp**2 + (ap-1)**2

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

        # 赔率区间
        if odds_h > 0:
            if odds_h < 1.30:     odds_key = "<1.30"
            elif odds_h < 1.50:   odds_key = "1.30-1.50"
            elif odds_h < 2.00:   odds_key = "1.50-2.00"
            elif odds_h < 3.00:   odds_key = "2.00-3.00"
            elif odds_h < 5.00:   odds_key = "3.00-5.00"
            else:                 odds_key = ">5.00"
        else:
            odds_key = "无赔率"

        os = odds_stats[odds_key]
        os["n"] += 1
        os[f"actual_{actual}"] += 1
        os[f"pred_{pred}"] += 1
        if pred == actual: os[f"pred_{pred}_correct"] += 1
        os["avg_hp_pred"] += hp
        os["avg_dp_pred"] += dp
        os["avg_ap_pred"] += ap
        os["brier"] += brier

        # 联赛
        league = m['league_standard'] or 'unknown'
        ls = league_stats[league]
        ls["n"] += 1
        ls[f"actual_{actual}"] += 1
        ls[f"pred_{pred}"] += 1
        if pred == actual: ls["correct"] += 1
        ls["brier"] += brier

        # 概率校准
        hp_bin = f"{int(hp*10)*10}%"
        dp_bin = f"{int(dp*10)*10}%"
        ap_bin = f"{int(ap*10)*10}%"
        hp_calibration[hp_bin]["n"] += 1
        hp_calibration[hp_bin]["actual_home"] += (1 if actual == 'home' else 0)
        dp_calibration[dp_bin]["n"] += 1
        dp_calibration[dp_bin]["actual_draw"] += (1 if actual == 'draw' else 0)
        ap_calibration[ap_bin]["n"] += 1
        ap_calibration[ap_bin]["actual_away"] += (1 if actual == 'away' else 0)

    conn.close()

    # === 输出 ===
    total = sum(actual_dist.values())
    p(f"\n  === 1. 总体分布 ===")
    p(f"  实际: home={actual_dist['home']}({actual_dist['home']/total*100:.1f}%) "
      f"draw={actual_dist['draw']}({actual_dist['draw']/total*100:.1f}%) "
      f"away={actual_dist['away']}({actual_dist['away']/total*100:.1f}%)")
    p(f"  预测: home={pred_dist['home']}({pred_dist['home']/total*100:.1f}%) "
      f"draw={pred_dist['draw']}({pred_dist['draw']/total*100:.1f}%) "
      f"away={pred_dist['away']}({pred_dist['away']/total*100:.1f}%)")
    p(f"  偏差: home预测多了{pred_dist['home']-actual_dist['home']}场 "
      f"draw预测少了{actual_dist['draw']-pred_dist['draw']}场 "
      f"away预测多了{pred_dist['away']-actual_dist['away']}场")
    p(f"  预测准确率: home={pred_correct['home']/pred_dist['home']*100:.1f}% "
      f"draw={pred_correct['draw']}/{pred_dist['draw']}={pred_correct['draw']/max(pred_dist['draw'],1)*100:.1f}% "
      f"away={pred_correct['away']/pred_dist['away']*100:.1f}%")

    p(f"\n  === 2. 按赔率区间 ===")
    odds_order = ["<1.30", "1.30-1.50", "1.50-2.00", "2.00-3.00", "3.00-5.00", ">5.00", "无赔率"]
    for ok in odds_order:
        os = odds_stats[ok]
        n = os["n"]
        if n < 10:
            continue
        actual_h = os["actual_home"]/n*100
        actual_d = os["actual_draw"]/n*100
        actual_a = os["actual_away"]/n*100
        pred_h_pct = os["avg_hp_pred"]/n*100
        pred_d_pct = os["avg_dp_pred"]/n*100
        pred_a_pct = os["avg_ap_pred"]/n*100
        acc = (os["pred_home_correct"]+os["pred_draw_correct"]+os["pred_away_correct"])/n*100
        brier_avg = os["brier"]/n
        # 主胜概率偏差: 模型平均预测 vs 实际
        hp_bias = pred_h_pct - actual_h
        dp_bias = pred_d_pct - actual_d
        ap_bias = pred_a_pct - actual_a
        p(f"  {ok}: n={n} acc={acc:.1f}% Brier={brier_avg:.4f}")
        p(f"    实际: h={actual_h:.1f}% d={actual_d:.1f}% a={actual_a:.1f}%")
        p(f"    预测: h={pred_h_pct:.1f}% d={pred_d_pct:.1f}% a={pred_a_pct:.1f}%")
        p(f"    偏差: hp={hp_bias:+.1f}pp dp={dp_bias:+.1f}pp ap={ap_bias:+.1f}pp")

    p(f"\n  === 3. 按联赛 (n>=100) ===")
    for league, ls in sorted(league_stats.items(), key=lambda x: x[1]["n"], reverse=True):
        n = ls["n"]
        if n < 100:
            continue
        acc = ls["correct"]/n*100
        brier_avg = ls["brier"]/n
        actual_h = ls["actual_home"]/n*100
        actual_d = ls["actual_draw"]/n*100
        actual_a = ls["actual_away"]/n*100
        pred_h_pct = ls["pred_home"]/n*100
        pred_d_pct = ls["pred_draw"]/n*100
        pred_a_pct = ls["pred_away"]/n*100
        p(f"  {league}: n={n} acc={acc:.1f}% Brier={brier_avg:.4f}")
        p(f"    实际: h={actual_h:.1f}% d={actual_d:.1f}% a={actual_a:.1f}% 预测: h={pred_h_pct:.1f}% d={pred_d_pct:.1f}% a={pred_a_pct:.1f}%")

    p(f"\n  === 4. 概率校准 — 主胜 ===")
    hp_bins_order = sorted(hp_calibration.keys(), key=lambda x: int(x.replace('%','')))
    for bin_key in hp_bins_order:
        cs = hp_calibration[bin_key]
        n = cs["n"]
        if n < 20:
            continue
        actual_pct = cs["actual_home"]/n*100
        pred_pct = int(bin_key.replace('%',''))
        p(f"  预测{bin_key}: n={n} 实际主胜={actual_pct:.1f}% 偏差={actual_pct-pred_pct:+.1f}pp")

    p(f"\n  === 5. 概率校准 — 平局 ===")
    dp_bins_order = sorted(dp_calibration.keys(), key=lambda x: int(x.replace('%','')))
    for bin_key in dp_bins_order:
        cs = dp_calibration[bin_key]
        n = cs["n"]
        if n < 20:
            continue
        actual_pct = cs["actual_draw"]/n*100
        pred_pct = int(bin_key.replace('%',''))
        p(f"  预测{bin_key}: n={n} 实际平局={actual_pct:.1f}% 偏差={actual_pct-pred_pct:+.1f}pp")

    p(f"\n  === 6. 概率校准 — 客胜 ===")
    ap_bins_order = sorted(ap_calibration.keys(), key=lambda x: int(x.replace('%','')))
    for bin_key in ap_bins_order:
        cs = ap_calibration[bin_key]
        n = cs["n"]
        if n < 20:
            continue
        actual_pct = cs["actual_away"]/n*100
        pred_pct = int(bin_key.replace('%',''))
        p(f"  预测{bin_key}: n={n} 实际客胜={actual_pct:.1f}% 偏差={actual_pct-pred_pct:+.1f}pp")

    p(f"\n{'=' * 70}")
    p("  诊断完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v36_diagnosis.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()