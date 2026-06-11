"""
v3.8实验: 在dt30触发比赛中降低亚盘draw blend
问题: dt30触发时模型预测draw 50.4%, 实际31.0%
亚盘draw blend=0.50可能过高, 导致draw概率偏大
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

# AH_DRAW_RATES
AH_DRAW_RATES = {
    0.00:  0.315,
    0.25:  0.301,
    0.50:  0.268,
    0.75:  0.250,
    1.00:  0.239,
    1.50:  0.191,
    2.00:  0.128,
}

def ah_draw_rate(abs_hc):
    breakpoints = sorted(AH_DRAW_RATES.keys())
    if abs_hc <= breakpoints[0]:
        return AH_DRAW_RATES[breakpoints[0]]
    if abs_hc >= breakpoints[-1]:
        return AH_DRAW_RATES[breakpoints[-1]]
    for i in range(len(breakpoints) - 1):
        lo, hi = breakpoints[i], breakpoints[i + 1]
        if lo <= abs_hc <= hi:
            t = (abs_hc - lo) / (hi - lo)
            return AH_DRAW_RATES[lo] + t * (AH_DRAW_RATES[hi] - AH_DRAW_RATES[lo])
    return 0.26

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

    # AH blend experiments
    blends = [0.50, 0.40, 0.30, 0.20, 0.10, 0.00]

    for ah_blend in blends:
        DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}
        DT_V38 = {0.30: 0.01, 0.28: 0.01, 0.26: 0.005}

        total_n = 0
        correct = 0
        brier = 0.0
        dt30_n = 0
        dt30_correct = 0
        net_gain = 0

        for m in matches:
            mk = m['match_key']
            actual = 'home' if m['home_score'] > m['away_score'] else \
                     'draw' if m['home_score'] == m['away_score'] else 'away'

            model_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
                (mk,)).fetchone()
            model_data = json.loads(model_row['data_json'])
            hp_v34 = model_data.get('home_win_prob', 0.33)
            dp_v34 = model_data.get('draw_prob', 0.33)
            ap_v34 = model_data.get('away_win_prob', 0.34)
            flags_v34 = model_data.get('scenario_flags', [])
            pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_v34, 'draw': dp_v34, 'away': ap_v34}[x])

            odds_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
                (mk,)).fetchone()
            odds_data = json.loads(odds_row['data_json'])
            hp_o = float(odds_data.get('home_value', 0) or 0)
            dp_o = float(odds_data.get('draw_value', 0) or 0)
            ap_o = float(odds_data.get('away_value', 0) or 0)
            odds_h = float(odds_data.get('raw', {}).get('avg_home_odds', 0) or odds_data.get('raw', {}).get('closing_avg_home_odds', 0) or 0)

            # 重新计算: 从赔率出发，用新的AH blend和DT规则
            # 步骤1: 赔率基础概率
            hp_x = hp_o
            dp_x = dp_o
            ap_x = ap_o

            # 步骤2: 信号覆盖 (使用v3.4模型中的signal)
            signal = model_data.get('signal_value', 0)
            euro_conf = max(hp_o, dp_o, ap_o)
            euro_pred = max([('home',hp_o),('draw',dp_o),('away',ap_o)],key=lambda x:x[1])[0]

            if euro_conf < 0.45:
                if euro_pred == 'home' and signal < -0.15:
                    flip_strength = min(abs(signal) / 0.5, 1.0) * 0.15
                    hp_x -= flip_strength
                    ap_x += flip_strength
                elif euro_pred == 'away' and signal > 0.15:
                    flip_strength = min(abs(signal) / 0.5, 1.0) * 0.15
                    ap_x -= flip_strength
                    hp_x += flip_strength
                if euro_pred == 'home' and signal < -0.02 and dp_o >= 0.30:
                    draw_boost = min(abs(signal) / 0.3, 1.0) * 0.08
                    hp_x -= draw_boost
                    dp_x += draw_boost
                elif euro_pred == 'away' and signal > 0.02 and dp_o >= 0.30:
                    draw_boost = min(abs(signal) / 0.3, 1.0) * 0.08
                    ap_x -= draw_boost
                    dp_x += draw_boost

            total_p = hp_x + dp_x + ap_x
            if total_p > 0:
                hp_x /= total_p; dp_x /= total_p; ap_x /= total_p

            # 步骤3: 亚盘draw校准
            ah_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
                (mk,)).fetchone()
            if ah_row:
                ah_data = json.loads(ah_row['data_json'])
                ah_handicap = ah_data.get('raw', {}).get('closing_handicap', None)
                if ah_handicap is not None:
                    abs_hc = abs(float(ah_handicap))
                    ah_draw = ah_draw_rate(abs_hc)
                    if ah_blend > 0 and ah_data.get('confidence', 0) > 0:
                        dp_new = (1 - ah_blend) * dp_x + ah_blend * ah_draw
                        diff = dp_new - dp_x
                        non_draw = hp_x + ap_x
                        if non_draw > 0 and abs(diff) > 0.001:
                            hp_x -= diff * (hp_x / non_draw)
                            ap_x -= diff * (ap_x / non_draw)
                            dp_x = dp_new
                            total_p = hp_x + dp_x + ap_x
                            hp_x /= total_p; dp_x /= total_p; ap_x /= total_p

            # 步骤4: draw_threshold (v3.8)
            if dp_o > 0:
                for threshold in sorted(DT_V38.keys(), reverse=True):
                    boost = DT_V38[threshold]
                    if dp_o >= threshold:
                        if boost > 0:
                            # 注意: 这里的hp/ap应该用当前值而非原始赔率值
                            hp_x2 = hp_x; dp_x2 = dp_x; ap_x2 = ap_x
                            dp_x2 += boost
                            non_draw = hp_x2 + ap_x2
                            if non_draw > 0:
                                hp_x2 -= boost * (hp_x2 / non_draw)
                                ap_x2 -= boost * (ap_x2 / non_draw)
                            hp_x, dp_x, ap_x = normalize_probs(hp_x2, dp_x2, ap_x2)
                        break

            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
            pred_x = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])

            correct += (1 if pred_x == actual else 0)
            if actual == 'home':   brier += (hp_x-1)**2 + dp_x**2 + ap_x**2
            elif actual == 'draw': brier += hp_x**2 + (dp_x-1)**2 + ap_x**2
            else:                  brier += hp_x**2 + dp_x**2 + (ap_x-1)**2
            total_n += 1

            if 'draw_threshold_0.3' in flags_v34:
                dt30_n += 1
                dt30_correct += (1 if pred_x == actual else 0)

            if pred_x != pred_v34:
                if pred_x == actual: net_gain += 1
                elif pred_v34 == actual: net_gain -= 1

        print(f"AH_blend={ah_blend:.2f}: argmax={correct}/{total_n}={correct/total_n*100:.2f}% "
              f"Brier={brier/total_n:.4f} dt30_argmax={dt30_correct}/{dt30_n}={dt30_correct/dt30_n*100:.1f}% "
              f"net={net_gain:+d}")

    conn.close()


if __name__ == "__main__":
    main()