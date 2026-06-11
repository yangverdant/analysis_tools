"""
v3.8+精调: dt30全局reduce vs dt30+AH0额外reduce的最优组合
前一实验确认dp0.01+ah0+0.02和dp0.01+ah0+0.03最优
精调: 测试更细的梯度
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

DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}
DT_V38 = {0.30: 0.01, 0.28: 0.01, 0.26: 0.005}

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
    p("  v3.8+精调: dt30 reduce分档最优组合")
    p("=" * 70)

    # 精调范围: base在0.005-0.02, ah0_extra在0.01-0.04
    strategies = []
    for base in [0.005, 0.01, 0.015, 0.02]:
        for ah0_extra in [0.00, 0.01, 0.02, 0.03, 0.04]:
            strategies.append((base, ah0_extra))

    for base, ah0_extra in strategies:
        total_n = 0; correct = 0; brier = 0.0; net_gain = 0
        dt30_ah0_n = 0; dt30_ah0_correct = 0; dt30_ah0_brier = 0.0
        dt30_noah0_n = 0; dt30_noah0_correct = 0
        draw_pred_n = 0; draw_pred_correct = 0; draw_actual = 0

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
            v34_flags = model_data.get('scenario_flags', [])
            pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

            odds_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
                (mk,)).fetchone()
            odds_data = json.loads(odds_row['data_json'])
            raw_odds = odds_data.get('raw', {})
            odds_h = float(raw_odds.get('avg_home_odds', 0) or raw_odds.get('closing_avg_home_odds', 0) or 0)
            dp_o = float(odds_data.get('draw_value', 0) or 0)

            hp_x = hp; dp_x = dp; ap_x = ap

            for dt_flag, old_boost in DT_V34.items():
                if dt_flag in v34_flags:
                    dp_x -= old_boost
                    hp_x += old_boost * (hp / (hp + ap))
                    ap_x += old_boost * (ap / (hp + ap))

            is_dt30 = False; is_ah0 = False
            ah_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
                (mk,)).fetchone()
            if ah_row:
                ah_data = json.loads(ah_row['data_json'])
                ah_hc = ah_data.get('raw', {}).get('closing_handicap', None)
                if ah_hc is not None and abs(float(ah_hc)) < 0.01:
                    is_ah0 = True

            for threshold in sorted(DT_V38.keys(), reverse=True):
                boost = DT_V38[threshold]
                if dp_o >= threshold:
                    if boost > 0:
                        dp_x += boost
                        non_draw = hp_x + ap_x
                        if non_draw > 0:
                            hp_x -= boost * (hp_x / non_draw)
                            ap_x -= boost * (ap_x / non_draw)
                        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
                    if threshold == 0.30:
                        is_dt30 = True
                        total_reduce = base + (ah0_extra if is_ah0 else 0)
                        if total_reduce > 0:
                            dp_x -= total_reduce
                            non_draw = hp_x + ap_x
                            if non_draw > 0:
                                hp_x += total_reduce * (hp_x / non_draw)
                                ap_x += total_reduce * (ap_x / non_draw)
                            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
                    break

            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
            pred_x = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])

            correct += (1 if pred_x == actual else 0)
            if actual == 'home':   brier += (hp_x-1)**2 + dp_x**2 + ap_x**2
            elif actual == 'draw': brier += hp_x**2 + (dp_x-1)**2 + ap_x**2
            else:                  brier += hp_x**2 + dp_x**2 + (ap_x-1)**2
            total_n += 1

            if pred_x != pred_v34:
                if pred_x == actual: net_gain += 1
                elif pred_v34 == actual: net_gain -= 1

            if is_dt30 and is_ah0:
                dt30_ah0_n += 1
                if pred_x == actual: dt30_ah0_correct += 1
                if actual == 'home':   dt30_ah0_brier += (hp_x-1)**2 + dp_x**2 + ap_x**2
                elif actual == 'draw': dt30_ah0_brier += hp_x**2 + (dp_x-1)**2 + ap_x**2
                else:                  dt30_ah0_brier += hp_x**2 + dp_x**2 + (ap_x-1)**2
            elif is_dt30:
                dt30_noah0_n += 1
                if pred_x == actual: dt30_noah0_correct += 1

            if pred_x == 'draw':
                draw_pred_n += 1
                if actual == 'draw': draw_pred_correct += 1
            if actual == 'draw':
                draw_actual += 1

        ah0_str = f"ah0+{ah0_extra:.2f}" if ah0_extra > 0 else ""
        dt30_ah0_acc = f"{dt30_ah0_correct}/{dt30_ah0_n}={dt30_ah0_correct/dt30_ah0_n*100:.1f}%" if dt30_ah0_n > 0 else "N/A"
        dt30_noah0_acc = f"{dt30_noah0_correct}/{dt30_noah0_n}={dt30_noah0_correct/dt30_noah0_n*100:.1f}%" if dt30_noah0_n > 0 else "N/A"
        draw_prec = f"{draw_pred_correct/draw_pred_n*100:.1f}%" if draw_pred_n > 0 else "N/A"

        p(f"  base={base:.3f} ah0+{ah0_extra:.2f}: argmax={correct}/{total_n}={correct/total_n*100:.2f}% "
          f"Brier={brier/total_n:.4f} net={net_gain:+d} | dt30+AH0={dt30_ah0_acc} dt30非AH0={dt30_noah0_acc} draw_prec={draw_prec}")

    p(f"\n{'=' * 70}")
    p("  实验完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_ah0_dp_finetune.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

if __name__ == "__main__":
    main()
