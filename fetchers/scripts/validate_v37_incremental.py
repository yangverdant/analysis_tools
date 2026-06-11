"""
v3.7增量验证 — draw_threshold_0.30的boost从0.06→0.02
对比: v3.4(基线) vs v3.7(修正后)
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
    p("  v3.7增量验证 — draw_threshold_0.30: 0.06→0.02")
    p("=" * 70)
    p(f"  总比赛数: {len(matches)}")

    # v3.4基线统计
    total_n = 0
    correct_v34 = 0
    brier_v34 = 0.0
    correct_v37 = 0
    brier_v37 = 0.0

    # 受draw_threshold影响的比赛
    dt30_matches_v34 = []  # v3.4中受0.30规则影响的
    dt28_matches = []
    dt26_matches = []
    changed_preds = []

    # 整体flag统计
    flag_counts = defaultdict(int)
    flag_correct_v34 = defaultdict(int)
    flag_correct_v37 = defaultdict(int)

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        # 加载v3.4模型结果
        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)
        ).fetchone()
        model_data = json.loads(model_row['data_json'])
        hp_v34 = model_data.get('home_win_prob', 0.33)
        dp_v34 = model_data.get('draw_prob', 0.33)
        ap_v34 = model_data.get('away_win_prob', 0.34)
        flags_v34 = model_data.get('scenario_flags', [])
        pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_v34, 'draw': dp_v34, 'away': ap_v34}[x])

        # v3.7: 唯一变化是draw_threshold_0.30的boost从0.06→0.02
        hp_v37 = hp_v34
        dp_v37 = dp_v34
        ap_v37 = ap_v34

        if 'draw_threshold_0.3' in flags_v34:
            # 去掉v3.4的+0.06，换成v3.7的+0.02
            dp_v37 = dp_v34 - 0.06 + 0.02
            hp_v37 = hp_v34 + 0.06 * (hp_v34 / (hp_v34 + ap_v34)) - 0.02 * (hp_v34 / (hp_v34 + ap_v34))
            ap_v37 = ap_v34 + 0.06 * (ap_v34 / (hp_v34 + ap_v34)) - 0.02 * (ap_v34 / (hp_v34 + ap_v34))
            hp_v37, dp_v37, ap_v37 = normalize_probs(hp_v37, dp_v37, ap_v37)
            dt30_matches_v34.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'actual': actual, 'score': f"{m['home_score']}-{m['away_score']}",
                'pred_v34': pred_v34, 'hp_v34': hp_v34, 'dp_v34': dp_v34, 'ap_v34': ap_v34,
            })

        hp_v37, dp_v37, ap_v37 = normalize_probs(hp_v37, dp_v37, ap_v37)
        pred_v37 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_v37, 'draw': dp_v37, 'away': ap_v37}[x])

        # 统计
        correct_v34 += (1 if pred_v34 == actual else 0)
        correct_v37 += (1 if pred_v37 == actual else 0)

        if actual == 'home':   brier_v34 += (hp_v34-1)**2 + dp_v34**2 + ap_v34**2; brier_v37 += (hp_v37-1)**2 + dp_v37**2 + ap_v37**2
        elif actual == 'draw': brier_v34 += hp_v34**2 + (dp_v34-1)**2 + ap_v34**2; brier_v37 += hp_v37**2 + (dp_v37-1)**2 + ap_v37**2
        else:                  brier_v34 += hp_v34**2 + dp_v34**2 + (ap_v34-1)**2; brier_v37 += hp_v37**2 + dp_v37**2 + (ap_v37-1)**2

        total_n += 1

        if pred_v34 != pred_v37:
            changed_preds.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'],
                'actual': actual, 'score': f"{m['home_score']}-{m['away_score']}",
                'pred_v34': pred_v34, 'pred_v37': pred_v37,
                'flags': flags_v34,
            })

        # flag统计
        v37_flags = []
        for f in flags_v34:
            if f == 'draw_threshold_0.3':
                v37_flags.append(f)  # 规则仍触发，只是boost不同
            else:
                v37_flags.append(f)

        for f in flags_v34:
            flag_counts[f] += 1
            if pred_v34 == actual: flag_correct_v34[f] += 1
        for f in v37_flags:
            if pred_v37 == actual: flag_correct_v37[f] += 1

    conn.close()

    # 输出
    p(f"\n  === 总体指标 ===")
    p(f"  v3.4: argmax={correct_v34}/{total_n}={correct_v34/total_n*100:.1f}%  Brier={brier_v34/total_n:.4f}")
    p(f"  v3.7: argmax={correct_v37}/{total_n}={correct_v37/total_n*100:.1f}%  Brier={brier_v37/total_n:.4f}")
    p(f"  变化: argmax {(correct_v37-correct_v34)/total_n*100:+.2f}pp  Brier {brier_v37/total_n-brier_v34/total_n:+.4f}")

    p(f"\n  === draw_threshold_0.30 触发比赛 ({len(dt30_matches_v34)}场) ===")
    dt30_correct_v34 = sum(1 for m in dt30_matches_v34 if m['pred_v34'] == m['actual'])
    dt30_actual_draw = sum(1 for m in dt30_matches_v34 if m['actual'] == 'draw')
    dt30_pred_draw_v34 = sum(1 for m in dt30_matches_v34 if m['dp_v34'] > m['hp_v34'] and m['dp_v34'] > m['ap_v34'])
    p(f"  v3.4 argmax准确率: {dt30_correct_v34}/{len(dt30_matches_v34)}={dt30_correct_v34/len(dt30_matches_v34)*100:.1f}%")
    p(f"  实际平局: {dt30_actual_draw}({dt30_actual_draw/len(dt30_matches_v34)*100:.1f}%)")
    p(f"  v3.4 预测draw方向: {dt30_pred_draw_v34}场")

    p(f"\n  === 预测方向改变的比赛 ({len(changed_preds)}场) ===")
    v37_net_gain = 0
    for cp in changed_preds[:50]:
        v37_ok = "✓" if cp['pred_v37'] == cp['actual'] else "✗"
        v34_ok = "✓" if cp['pred_v34'] == cp['actual'] else "✗"
        if cp['pred_v37'] == cp['actual']: v37_net_gain += 1
        elif cp['pred_v34'] == cp['actual']: v37_net_gain -= 1
        p(f"  {cp['date']} {cp['home']} vs {cp['away']} ({cp['league']}) "
          f"score={cp['score']} v3.4={cp['pred_v34']}({v34_ok}) v3.7={cp['pred_v37']}({v37_ok})")

    if len(changed_preds) > 50:
        p(f"  ... 还有{len(changed_preds)-50}场")

    p(f"\n  v3.7净收益: {v37_net_gain:+d}场")

    p(f"\n  === 规则触发统计 ===")
    for flag, cnt in sorted(flag_counts.items(), key=lambda x: x[1], reverse=True):
        p(f"  {flag}: {cnt}场")

    p(f"\n{'=' * 70}")
    p("  验证完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v37_incremental_result.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")
    print(f"v3.7总指标: argmax {correct_v37}/{total_n}={correct_v37/total_n*100:.1f}% Brier {brier_v37/total_n:.4f}")
    print(f"v3.4总指标: argmax {correct_v34}/{total_n}={correct_v34/total_n*100:.1f}% Brier {brier_v34/total_n:.4f}")
    print(f"净收益: {v37_net_gain:+d}场")


if __name__ == "__main__":
    main()