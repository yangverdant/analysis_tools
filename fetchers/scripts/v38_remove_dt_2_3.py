"""
v3.8实验: 在odds 2.0-3.0区间完全去掉draw_threshold规则
对比: v3.4(基线) vs v3.8(去掉draw_threshold在2-3区间)
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
    p("  v3.8实验: 去掉draw_threshold在odds 2.0-3.0区间")
    p("=" * 70)
    p(f"  总比赛数: {len(matches)}")

    # v3.4 draw_threshold调整量（从代码中提取）
    DT_ADJUST = {
        'draw_threshold_0.3': 0.05,  # dp += 0.05, hp/ap按比例减
        'draw_threshold_0.28': 0.03,
        'draw_threshold_0.26': 0.015,
    }

    total_n = 0
    correct_v34 = 0
    correct_v38 = 0
    brier_v34 = 0.0
    brier_v38 = 0.0

    # 按odds区间分开统计
    stats_by_range = defaultdict(lambda: {
        "n": 0, "correct_v34": 0, "correct_v38": 0,
        "brier_v34": 0.0, "brier_v38": 0.0,
        "changed": 0, "changed_correct": 0, "changed_wrong": 0,
    })

    changed_preds = []

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        # 模型
        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        model_data = json.loads(model_row['data_json'])
        hp = model_data.get('home_win_prob', 0.33)
        dp = model_data.get('draw_prob', 0.33)
        ap = model_data.get('away_win_prob', 0.34)
        flags = model_data.get('scenario_flags', [])
        pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

        # 赔率
        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        odds_h = float(odds_data.get('raw', {}).get('avg_home_odds', 0) or odds_data.get('raw', {}).get('closing_avg_home_odds', 0) or 0)

        # v3.8: 在odds 2.0-3.0区间完全去掉draw_threshold
        hp_v38 = hp
        dp_v38 = dp
        ap_v38 = ap

        in_2_3 = odds_h >= 2.0 and odds_h < 3.0

        if in_2_3:
            # 反推：去掉所有draw_threshold的调整
            for dt_flag, boost in DT_ADJUST.items():
                if dt_flag in flags:
                    # v3.4中: dp += boost, hp -= boost*(hp/(hp+ap)), ap -= boost*(ap/(hp+ap))
                    # 但v3.4中已有normalize，所以需要先反推原始值
                    # 简化：直接从当前值减去boost效果
                    # 更准确的方法：把draw_threshold的boost完全去掉
                    dp_v38 -= boost
                    # hp和ap按原始比例加回
                    hp_v38 += boost * (hp / (hp + ap))
                    ap_v38 += boost * (ap / (hp + ap))

        hp_v38, dp_v38, ap_v38 = normalize_probs(hp_v38, dp_v38, ap_v38)
        pred_v38 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_v38, 'draw': dp_v38, 'away': ap_v38}[x])

        # 统计
        correct_v34 += (1 if pred_v34 == actual else 0)
        correct_v38 += (1 if pred_v38 == actual else 0)

        if actual == 'home':   brier_v34 += (hp-1)**2 + dp**2 + ap**2; brier_v38 += (hp_v38-1)**2 + dp_v38**2 + ap_v38**2
        elif actual == 'draw': brier_v34 += hp**2 + (dp-1)**2 + ap**2; brier_v38 += hp_v38**2 + (dp_v38-1)**2 + ap_v38**2
        else:                  brier_v34 += hp**2 + dp**2 + (ap-1)**2; brier_v38 += hp_v38**2 + dp_v38**2 + (ap_v38-1)**2

        total_n += 1

        # 按odds区间
        if odds_h > 0:
            if odds_h < 1.5:
                rng = "<1.5"
            elif odds_h < 2.0:
                rng = "1.5-2.0"
            elif odds_h < 2.5:
                rng = "2.0-2.5"
            elif odds_h < 3.0:
                rng = "2.5-3.0"
            else:
                rng = "3.0+"

            s = stats_by_range[rng]
            s["n"] += 1
            s["correct_v34"] += (1 if pred_v34 == actual else 0)
            s["correct_v38"] += (1 if pred_v38 == actual else 0)
            if actual == 'home':   s["brier_v34"] += (hp-1)**2 + dp**2 + ap**2; s["brier_v38"] += (hp_v38-1)**2 + dp_v38**2 + ap_v38**2
            elif actual == 'draw': s["brier_v34"] += hp**2 + (dp-1)**2 + ap**2; s["brier_v38"] += hp_v38**2 + (dp_v38-1)**2 + ap_v38**2
            else:                  s["brier_v34"] += hp**2 + dp**2 + (ap-1)**2; s["brier_v38"] += hp_v38**2 + dp_v38**2 + (ap_v38-1)**2

            if pred_v34 != pred_v38:
                s["changed"] += 1
                if pred_v38 == actual: s["changed_correct"] += 1
                else: s["changed_wrong"] += 1

        # 改变详情
        if pred_v34 != pred_v38:
            changed_preds.append({
                'date': m['date'], 'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'], 'odds_h': odds_h,
                'actual': actual, 'score': f"{m['home_score']}-{m['away_score']}",
                'pred_v34': pred_v34, 'pred_v38': pred_v38,
                'dp_v34': dp, 'dp_v38': dp_v38,
                'flags': [f for f in flags if f.startswith('draw_threshold')],
            })

    conn.close()

    # 输出
    p(f"\n  === 总体指标 ===")
    p(f"  v3.4: argmax={correct_v34}/{total_n}={correct_v34/total_n*100:.1f}%  Brier={brier_v34/total_n:.4f}")
    p(f"  v3.8: argmax={correct_v38}/{total_n}={correct_v38/total_n*100:.1f}%  Brier={brier_v38/total_n:.4f}")
    p(f"  变化: argmax {(correct_v38-correct_v34)/total_n*100:+.2f}pp  Brier {brier_v38/total_n-brier_v34/total_n:+.4f}")

    p(f"\n  === 按Odds区间 ===")
    for rng in ["<1.5", "1.5-2.0", "2.0-2.5", "2.5-3.0", "3.0+"]:
        s = stats_by_range[rng]
        n = s["n"]
        if n == 0: continue
        p(f"  odds {rng}: n={n}")
        p(f"    v3.4 argmax={s['correct_v34']/n*100:.1f}% Brier={s['brier_v34']/n:.4f}")
        p(f"    v3.8 argmax={s['correct_v38']/n*100:.1f}% Brier={s['brier_v38']/n:.4f}")
        p(f"    变化: argmax {(s['correct_v38']-s['correct_v34'])/n*100:+.1f}pp Brier {(s['brier_v38']-s['brier_v34'])/n:+.4f}")
        if s["changed"] > 0:
            p(f"    改变预测: {s['changed']}场 改对{s['changed_correct']} 改错{s['changed_wrong']} 净{s['changed_correct']-s['changed_wrong']:+d}")

    p(f"\n  === 预测改变详情 ({len(changed_preds)}场) ===")
    v38_net = 0
    for cp in sorted(changed_preds, key=lambda x: x['odds_h']):
        v38_ok = "✓" if cp['pred_v38'] == cp['actual'] else "✗"
        v34_ok = "✓" if cp['pred_v34'] == cp['actual'] else "✗"
        if cp['pred_v38'] == cp['actual']: v38_net += 1
        elif cp['pred_v34'] == cp['actual']: v38_net -= 1
        if abs(cp['dp_v34'] - cp['dp_v38']) > 0.02:  # 只显示有意义的改变
            p(f"  {cp['date']} {cp['home']} vs {cp['away']} ({cp['league']}) odds_h={cp['odds_h']:.2f}")
            p(f"    score={cp['score']} v3.4={cp['pred_v34']}({v34_ok}) v3.8={cp['pred_v38']}({v38_ok}) "
              f"dp:{cp['dp_v34']*100:.1f}%→{cp['dp_v38']*100:.1f}% flags={','.join(cp['flags'])}")

    p(f"\n  v3.8净收益(2-3区间去draw_threshold): {v38_net:+d}场")

    p(f"\n{'=' * 70}")
    p("  实验完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_remove_dt_2_3_result.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")
    print(f"v3.8总指标: argmax {correct_v38}/{total_n}={correct_v38/total_n*100:.1f}% Brier {brier_v38/total_n:.4f}")
    print(f"v3.4总指标: argmax {correct_v34}/{total_n}={correct_v34/total_n*100:.1f}% Brier {brier_v34/total_n:.4f}")
    print(f"净收益: {v38_net:+d}")


if __name__ == "__main__":
    main()