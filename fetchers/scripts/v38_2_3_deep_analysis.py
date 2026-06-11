"""
v3.8+深度分析: 2.0-3.0区间的signal override和draw预测效果
重点: 信号flip是否在2-3区间有效？draw预测如何改善？
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
DT30_EXTRA_DP_REDUCE = 0.02

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
    p("  v3.8+ 2-3区间signal & draw深度分析")
    p("=" * 70)

    # 分子群: dt30触发 vs 不触发, signal方向, AH=0 vs 其他
    groups = defaultdict(lambda: {'n': 0, 'correct': 0, 'odds_correct': 0,
                                   'draw_pred_n': 0, 'draw_actual': 0, 'draw_pred_correct': 0,
                                   'home_pred_n': 0, 'home_actual': 0,
                                   'away_pred_n': 0, 'away_actual': 0,
                                   'avg_dp': 0.0, 'avg_dp_o': 0.0})

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
        v34_flags = model_data.get('scenario_flags', [])
        signal = model_data.get('signal_value', 0)
        euro_conf = model_data.get('euro_confidence', 0.5)
        signal_strength = model_data.get('signal_strength', 'none')

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        raw_odds = odds_data.get('raw', {})
        odds_h = float(raw_odds.get('avg_home_odds', 0) or raw_odds.get('closing_avg_home_odds', 0) or 0)
        hp_o = float(odds_data.get('home_value', 0) or 0)
        dp_o = float(odds_data.get('draw_value', 0) or 0)
        ap_o = float(odds_data.get('away_value', 0) or 0)

        if odds_h <= 0 or not (2.0 <= odds_h < 3.0): continue

        # v3.8概率
        hp_x = hp_v34; dp_x = dp_v34; ap_x = ap_v34
        for dt_flag, old_boost in DT_V34.items():
            if dt_flag in v34_flags:
                dp_x -= old_boost
                hp_x += old_boost * (hp_v34 / (hp_v34 + ap_v34))
                ap_x += old_boost * (ap_v34 / (hp_v34 + ap_v34))
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
                if threshold == 0.30 and DT30_EXTRA_DP_REDUCE > 0:
                    dp_x -= DT30_EXTRA_DP_REDUCE
                    non_draw = hp_x + ap_x
                    if non_draw > 0:
                        hp_x += DT30_EXTRA_DP_REDUCE * (hp_x / non_draw)
                        ap_x += DT30_EXTRA_DP_REDUCE * (ap_x / non_draw)
                    hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
                break
        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

        pred_x = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])
        pred_odds = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

        # 分类维度
        has_dt30 = 'draw_threshold_0.3' in v34_flags
        has_clv = 'clv_motivation_aligned' in v34_flags
        sig_dir = 'positive' if signal > 0.05 else ('negative' if signal < -0.05 else 'neutral')

        # AH信息
        ah_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
            (mk,)).fetchone()
        ah_hc = None
        is_ah0 = False
        if ah_row:
            ah_data = json.loads(ah_row['data_json'])
            ah_hc = ah_data.get('raw', {}).get('closing_handicap', None)
            if ah_hc is not None and abs(float(ah_hc)) < 0.01:
                is_ah0 = True

        # 按多个维度分组
        for key in ['total', f"dt30_{has_dt30}", f"ah0_{is_ah0}", f"sig_{sig_dir}",
                    f"clv_{has_clv}", f"dt30_{has_dt30}_ah0_{is_ah0}",
                    f"sig_{sig_dir}_dt30_{has_dt30}"]:
            g = groups[key]
            g['n'] += 1
            g['correct'] += (1 if pred_x == actual else 0)
            g['odds_correct'] += (1 if pred_odds == actual else 0)
            g['avg_dp'] += dp_x
            g['avg_dp_o'] += dp_o
            if pred_x == 'draw':
                g['draw_pred_n'] += 1
                g['draw_pred_correct'] += (1 if actual == 'draw' else 0)
            if actual == 'draw':
                g['draw_actual'] += 1
            if pred_x == 'home':
                g['home_pred_n'] += 1
                g['home_actual'] += (1 if actual == 'home' else 0)
            if pred_x == 'away':
                g['away_pred_n'] += 1
                g['away_actual'] += (1 if actual == 'away' else 0)

    conn.close()

    # 输出
    for key, g in sorted(groups.items()):
        if g['n'] == 0: continue
        acc = g['correct'] / g['n'] * 100
        odds_acc = g['odds_correct'] / g['n'] * 100
        gap = acc - odds_acc
        dp_avg = g['avg_dp'] / g['n'] * 100
        dp_o_avg = g['avg_dp_o'] / g['n'] * 100
        draw_recall = g['draw_pred_correct'] / g['draw_actual'] * 100 if g['draw_actual'] > 0 else 0
        draw_prec = g['draw_pred_correct'] / g['draw_pred_n'] * 100 if g['draw_pred_n'] > 0 else 0
        home_prec = g['home_actual'] / g['home_pred_n'] * 100 if g['home_pred_n'] > 0 else 0
        away_prec = g['away_actual'] / g['away_pred_n'] * 100 if g['away_pred_n'] > 0 else 0

        p(f"\n  [{key}] n={g['n']}")
        p(f"    model={acc:.1f}% odds={odds_acc:.1f}% gap={gap:+.1f}pp")
        p(f"    avg_dp={dp_avg:.1f}% avg_dp_odds={dp_o_avg:.1f}%")
        p(f"    draw: pred={g['draw_pred_n']} actual={g['draw_actual']} prec={draw_prec:.0f}% recall={draw_recall:.0f}%")
        p(f"    home: pred={g['home_pred_n']} prec={home_prec:.0f}% | away: pred={g['away_pred_n']} prec={away_prec:.0f}%")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_2_3_deep_analysis.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

if __name__ == "__main__":
    main()