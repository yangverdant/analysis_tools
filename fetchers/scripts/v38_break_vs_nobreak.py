"""
v3.8对比: break vs no-break(只跳过boost=0) 两种dt逻辑
"""
import sys, io, json, sqlite3
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

    DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}
    DT_NEW = {0.30: 0.00, 0.28: 0.01, 0.26: 0.005}

    for logic_name, use_break in [("break(跳过boost=0)", True), ("no-break(跳过boost=0继续)", False)]:
        total_n = 0
        correct = 0
        brier = 0.0
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
            dp_o = float(odds_data.get('draw_value', 0) or 0)

            hp_x = hp
            dp_x = dp
            ap_x = ap

            # 去掉v3.4的draw_threshold
            for dt_flag, old_boost in DT_V34.items():
                if dt_flag in flags:
                    dp_x -= old_boost
                    hp_x += old_boost * (hp / (hp + ap))
                    ap_x += old_boost * (ap / (hp + ap))

            # 新逻辑
            if use_break:
                for threshold in sorted(DT_NEW.keys(), reverse=True):
                    boost = DT_NEW[threshold]
                    if dp_o >= threshold:
                        if boost > 0:
                            dp_x += boost
                            non_draw = hp_x + ap_x
                            if non_draw > 0:
                                hp_x -= boost * (hp_x / non_draw)
                                ap_x -= boost * (ap_x / non_draw)
                            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
                        break
            else:
                for threshold in sorted(DT_NEW.keys(), reverse=True):
                    boost = DT_NEW[threshold]
                    if dp_o >= threshold and boost > 0:
                        dp_x += boost
                        non_draw = hp_x + ap_x
                        if non_draw > 0:
                            hp_x -= boost * (hp_x / non_draw)
                            ap_x -= boost * (ap_x / non_draw)
                        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

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

        print(f"{logic_name}: argmax={correct}/{total_n}={correct/total_n*100:.2f}% Brier={brier/total_n:.4f} net={net_gain:+d}")

    conn.close()


if __name__ == "__main__":
    main()