"""
v3.8精确实验: draw_threshold_0.3完全去掉 vs v3.7(0.02) vs v3.4(0.05)
只改变draw_threshold_0.3的boost，其他不变
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
    p("  v3.8精确实验: draw_threshold_0.3 boost精细调节")
    p("=" * 70)

    # 实验不同的draw_threshold_0.3 boost值
    dt30_boosts = [0.05, 0.02, 0.01, 0.005, 0.0]

    for dt30_boost in dt30_boosts:
        total_n = 0
        correct = 0
        brier = 0.0
        correct_2_3 = 0
        n_2_3 = 0
        brier_2_3 = 0.0
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

            # 从v3.4值出发
            hp_x = hp
            dp_x = dp
            ap_x = ap

            # 去掉v3.4的draw_threshold_0.3 (boost=0.05)
            if 'draw_threshold_0.3' in flags:
                old_boost = 0.05
                dp_x -= old_boost
                hp_x += old_boost * (hp / (hp + ap))
                ap_x += old_boost * (ap / (hp + ap))

            # 加上新boost
            if 'draw_threshold_0.3' in flags and dt30_boost > 0:
                dp_x += dt30_boost
                hp_x -= dt30_boost * (hp / (hp + ap))
                ap_x -= dt30_boost * (ap / (hp + ap))

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
                if pred_x == actual: net_gain += 1
                elif pred_v34 == actual: net_gain -= 1

        p(f"\n  --- draw_threshold_0.3 boost={dt30_boost} ---")
        p(f"  总体: argmax={correct}/{total_n}={correct/total_n*100:.2f}% Brier={brier/total_n:.4f}")
        if n_2_3 > 0:
            p(f"  2-3区间: argmax={correct_2_3}/{n_2_3}={correct_2_3/n_2_3*100:.2f}% Brier={brier_2_3/n_2_3:.4f}")
        p(f"  vs v3.4净收益: {net_gain:+d}场")

    p(f"\n{'=' * 70}")
    p("  实验完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_dt30_fine_tuning.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()