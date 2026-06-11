"""
v3.8+精调v2: 修复AH数据覆盖问题
只有约95%的dt30比赛有AH数据, 需要分三档:
1. dt30 + AH=0 (平手盘) → 更大reduce
2. dt30 + AH≠0 → base reduce
3. dt30 + 无AH数据 → base reduce (保守策略)
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

    # 修改: 不强制要求AH数据存在(让更多比赛参与)
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
    p("  v3.8+精调v2: 三档dp reduce (dt30+AH0 / dt30+AH≠0 / dt30无AH)")
    p("=" * 70)

    # 先统计AH覆盖
    ah_coverage = 0; ah0_count = 0; no_ah_count = 0; dt30_total = 0
    for m in matches:
        mk = m['match_key']
        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        model_data = json.loads(model_row['data_json'])
        v34_flags = model_data.get('scenario_flags', [])
        if 'draw_threshold_0.3' in v34_flags:
            dt30_total += 1
            ah_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
                (mk,)).fetchone()
            if ah_row:
                ah_data = json.loads(ah_row['data_json'])
                ah_hc = ah_data.get('raw', {}).get('closing_handicap', None)
                if ah_hc is not None:
                    ah_coverage += 1
                    if abs(float(ah_hc)) < 0.01:
                        ah0_count += 1
            else:
                no_ah_count += 1
    p(f"\n  dt30覆盖率: {dt30_total}场, AH数据={ah_coverage}({ah_coverage/dt30_total*100:.1f}%), AH=0={ah0_count}, 无AH={no_ah_count}")

    # 测试策略
    strategies = [
        {"name": "统一0.02",  "base": 0.02, "ah0": 0.00},
        {"name": "base0.01+ah0.02", "base": 0.01, "ah0": 0.02},
        {"name": "base0.01+ah0.03", "base": 0.01, "ah0": 0.03},
        {"name": "base0.015+ah0.02", "base": 0.015, "ah0": 0.02},
        {"name": "base0.015+ah0.03", "base": 0.015, "ah0": 0.03},
        {"name": "base0.02+ah0.02", "base": 0.02, "ah0": 0.02},
        {"name": "base0.02+ah0.03", "base": 0.02, "ah0": 0.03},
        {"name": "base0.02+ah0.04", "base": 0.02, "ah0": 0.04},
        {"name": "base0.03+ah0.02", "base": 0.03, "ah0": 0.02},
        {"name": "base0.03+ah0.03", "base": 0.03, "ah0": 0.03},
    ]

    for strat in strategies:
        base = strat['base']
        ah0_extra = strat['ah0']

        total_n = 0; correct = 0; brier = 0.0; net_gain = 0
        # 三档子群
        s_dt30_ah0 = {'n': 0, 'correct': 0}
        s_dt30_ah_non0 = {'n': 0, 'correct': 0}
        s_dt30_no_ah = {'n': 0, 'correct': 0}
        s_odds_2_3 = {'n': 0, 'correct': 0}

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

            # AH判断(提前查询)
            ah_type = 'no_data'  # no_data / ah0 / ah_non0
            ah_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
                (mk,)).fetchone()
            if ah_row:
                ah_data = json.loads(ah_row['data_json'])
                ah_hc = ah_data.get('raw', {}).get('closing_handicap', None)
                if ah_hc is not None:
                    if abs(float(ah_hc)) < 0.01:
                        ah_type = 'ah0'
                    else:
                        ah_type = 'ah_non0'

            is_dt30 = False
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
                        # 分档reduce
                        if ah_type == 'ah0':
                            reduce_val = base + ah0_extra
                        else:
                            reduce_val = base  # AH≠0 或 无AH数据 → 只用base
                        if reduce_val > 0:
                            dp_x -= reduce_val
                            non_draw = hp_x + ap_x
                            if non_draw > 0:
                                hp_x += reduce_val * (hp_x / non_draw)
                                ap_x += reduce_val * (ap_x / non_draw)
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

            # 子群
            if is_dt30 and ah_type == 'ah0':
                s_dt30_ah0['n'] += 1
                if pred_x == actual: s_dt30_ah0['correct'] += 1
            elif is_dt30 and ah_type == 'ah_non0':
                s_dt30_ah_non0['n'] += 1
                if pred_x == actual: s_dt30_ah_non0['correct'] += 1
            elif is_dt30:
                s_dt30_no_ah['n'] += 1
                if pred_x == actual: s_dt30_no_ah['correct'] += 1

            if 2.0 <= odds_h < 3.0:
                s_odds_2_3['n'] += 1
                if pred_x == actual: s_odds_2_3['correct'] += 1

        ah0_str = f"ah0={s_dt30_ah0['correct']}/{s_dt30_ah0['n']}={s_dt30_ah0['correct']/s_dt30_ah0['n']*100:.1f}%" if s_dt30_ah0['n'] > 0 else "N/A"
        ah_non0_str = f"ah≠0={s_dt30_ah_non0['correct']}/{s_dt30_ah_non0['n']}={s_dt30_ah_non0['correct']/s_dt30_ah_non0['n']*100:.1f}%" if s_dt30_ah_non0['n'] > 0 else "N/A"
        no_ah_str = f"noAH={s_dt30_no_ah['correct']}/{s_dt30_no_ah['n']}={s_dt30_no_ah['correct']/s_dt30_no_ah['n']*100:.1f}%" if s_dt30_no_ah['n'] > 0 else "N/A"
        range23_str = f"2-3={s_odds_2_3['correct']}/{s_odds_2_3['n']}={s_odds_2_3['correct']/s_odds_2_3['n']*100:.1f}%" if s_odds_2_3['n'] > 0 else "N/A"

        p(f"  {strat['name']:20s}: argmax={correct/total_n*100:.2f}% Brier={brier/total_n:.4f} net={net_gain:+d} | {ah0_str} {ah_non0_str} {no_ah_str} {range23_str}")

    p(f"\n{'=' * 70}")
    p("  实验完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_ah0_dp_finetune2.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

if __name__ == "__main__":
    main()