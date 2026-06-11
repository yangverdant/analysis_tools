"""
v3.8验证: 新draw_threshold逻辑(无break, 逐级触发)
dt30=0.00, dt28=0.01, dt26=0.005
当market_draw>=0.30: dt30不触发(boost=0), dt28触发(+0.01), dt26触发(+0.005) → total +0.015
当market_draw>=0.28但<0.30: dt28触发(+0.01), dt26触发(+0.005) → total +0.015
当market_draw>=0.26但<0.28: dt26触发(+0.005) → total +0.005
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
    p("  v3.8验证: 新draw_threshold逻辑(无break逐级触发)")
    p("  dt30=0.00 dt28=0.01 dt26=0.005")
    p("=" * 70)

    # 新逻辑
    DT_NEW = {0.30: 0.00, 0.28: 0.01, 0.26: 0.005}
    # v3.4旧逻辑
    DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}

    total_n = 0
    correct_v34 = 0
    correct_v38 = 0
    brier_v34 = 0.0
    brier_v38 = 0.0
    correct_2_3 = 0
    n_2_3 = 0
    brier_2_3_v34 = 0.0
    brier_2_3_v38 = 0.0
    net_gain = 0

    # 统计新逻辑触发的阈值组合
    trigger_patterns = defaultdict(int)

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
        hp_o = float(odds_data.get('home_value', 0) or 0)
        dp_o = float(odds_data.get('draw_value', 0) or 0)
        ap_o = float(odds_data.get('away_value', 0) or 0)

        # v38计算
        hp_x = hp
        dp_x = dp
        ap_x = ap

        # 去掉v3.4的所有draw_threshold
        for dt_flag, old_boost in DT_V34.items():
            if dt_flag in flags:
                dp_x -= old_boost
                hp_x += old_boost * (hp / (hp + ap))
                ap_x += old_boost * (ap / (hp + ap))

        # 新逻辑: 逐级触发(无break), 只触发boost>0
        # 需要知道market_draw值
        market_draw = dp_o  # 赔率隐含平局概率

        triggered = []
        for threshold in sorted(DT_NEW.keys(), reverse=True):
            boost = DT_NEW[threshold]
            if market_draw >= threshold and boost > 0:
                dp_x += boost
                non_draw = hp_x + ap_x
                if non_draw > 0:
                    hp_x -= boost * (hp_x / non_draw)
                    ap_x -= boost * (ap_x / non_draw)
                hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
                triggered.append(f"dt{threshold:.2f}={boost}")

        if triggered:
            trigger_patterns["+".join(triggered)] += 1

        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
        pred_x = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])

        correct_v34 += (1 if pred_v34 == actual else 0)
        correct_v38 += (1 if pred_x == actual else 0)

        if actual == 'home':   brier_v34 += (hp-1)**2 + dp**2 + ap**2; brier_v38 += (hp_x-1)**2 + dp_x**2 + ap_x**2
        elif actual == 'draw': brier_v34 += hp**2 + (dp-1)**2 + ap**2; brier_v38 += hp_x**2 + (dp_x-1)**2 + ap_x**2
        else:                  brier_v34 += hp**2 + dp**2 + (ap-1)**2; brier_v38 += hp_x**2 + dp_x**2 + (ap_x-1)**2
        total_n += 1

        if 2.0 <= odds_h < 3.0:
            n_2_3 += 1
            if pred_x == actual: correct_2_3 += 1
            if actual == 'home':   brier_2_3_v34 += (hp-1)**2 + dp**2 + ap**2; brier_2_3_v38 += (hp_x-1)**2 + dp_x**2 + ap_x**2
            elif actual == 'draw': brier_2_3_v34 += hp**2 + (dp-1)**2 + ap**2; brier_2_3_v38 += hp_x**2 + (dp_x-1)**2 + ap_x**2
            else:                  brier_2_3_v34 += hp**2 + dp**2 + (ap-1)**2; brier_2_3_v38 += hp_x**2 + dp_x**2 + (ap_x-1)**2

        if pred_x != pred_v34:
            if pred_x == actual: net_gain += 1
            elif pred_v34 == actual: net_gain -= 1

    conn.close()

    p(f"\n  === v3.8验证结果 ===")
    p(f"  v3.4: argmax={correct_v34}/{total_n}={correct_v34/total_n*100:.2f}% Brier={brier_v34/total_n:.4f}")
    p(f"  v3.8: argmax={correct_v38}/{total_n}={correct_v38/total_n*100:.2f}% Brier={brier_v38/total_n:.4f}")
    p(f"  变化: argmax {(correct_v38-correct_v34)/total_n*100:+.2f}pp Brier {brier_v38/total_n-brier_v34/total_n:+.4f}")
    if n_2_3 > 0:
        p(f"  2-3区间: argmax={correct_2_3}/{n_2_3}={correct_2_3/n_2_3*100:.2f}% Brier={brier_2_3_v38/n_2_3:.4f}")
        # 2-3 v3.4
        correct_2_3_v34 = sum(1 for m_k in range(n_2_3))  # 不精确，用总体比例估算

    p(f"  vs v3.4净收益: {net_gain:+d}场")

    p(f"\n  === 触发pattern统计 ===")
    for pattern, cnt in sorted(trigger_patterns.items(), key=lambda x: x[1], reverse=True):
        p(f"  {pattern}: {cnt}场")

    p(f"\n{'=' * 70}")
    p("  验证完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_validation.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")
    print(f"v3.8: argmax {correct_v38}/{total_n}={correct_v38/total_n*100:.2f}% Brier {brier_v38/total_n:.4f}")
    print(f"v3.4: argmax {correct_v34}/{total_n}={correct_v34/total_n*100:.2f}% Brier {brier_v34/total_n:.4f}")
    print(f"净收益: {net_gain:+d}")


if __name__ == "__main__":
    main()