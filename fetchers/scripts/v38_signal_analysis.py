"""
v3.8下一阶段: 分析信号覆盖(signal override)在不同子群的效果
重点: no_override区间的改错空间
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
    p("  v3.8+信号分析: 各子群的signal override效果")
    p("=" * 70)

    # 收集v3.8结果 + signal信息
    groups = defaultdict(lambda: {'n': 0, 'correct': 0, 'odds_correct': 0,
                                   'flip_n': 0, 'flip_correct': 0,
                                   'no_flip_n': 0, 'no_flip_correct': 0,
                                   'draw_pred_n': 0, 'draw_correct': 0,
                                   'draw_actual_n': 0,
                                   'signal_sum': 0.0, 'signal_abs_sum': 0.0})

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

        pred_odds = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

        # 计算v3.8概率(简化: 只做dt调整)
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

        # 分类
        is_flipped = pred_x != pred_odds
        is_draw_pred = pred_x == 'draw'

        # 按赔率区间分组
        if odds_h <= 0: continue
        if odds_h < 1.50: zone = "1.0-1.5"
        elif odds_h < 2.0: zone = "1.5-2.0"
        elif odds_h < 2.5: zone = "2.0-2.5"
        elif odds_h < 3.0: zone = "2.5-3.0"
        elif odds_h < 4.0: zone = "3.0-4.0"
        else: zone = "4.0+"

        # 按signal强度分组
        sig_abs = abs(signal)
        if sig_abs < 0.1: sig_zone = "weak"
        elif sig_abs < 0.3: sig_zone = "medium"
        elif sig_abs < 0.5: sig_zone = "strong"
        else: sig_zone = "very_strong"

        # 按euro_conf分组
        if euro_conf < 0.45: conf_zone = "low"
        elif euro_conf < 0.55: conf_zone = "mid"
        else: conf_zone = "high"

        # 总体
        g = groups['total']
        g['n'] += 1
        g['correct'] += (1 if pred_x == actual else 0)
        g['odds_correct'] += (1 if pred_odds == actual else 0)
        g['signal_sum'] += signal
        g['signal_abs_sum'] += sig_abs
        if is_flipped:
            g['flip_n'] += 1
            g['flip_correct'] += (1 if pred_x == actual else 0)
        else:
            g['no_flip_n'] += 1
            g['no_flip_correct'] += (1 if pred_x == actual else 0)
        if is_draw_pred:
            g['draw_pred_n'] += 1
            g['draw_correct'] += (1 if actual == 'draw' else 0)
        if actual == 'draw':
            g['draw_actual_n'] += 1

        # 赔率区间
        for key in [f"odds_{zone}", f"sig_{sig_zone}", f"conf_{conf_zone}"]:
            g2 = groups[key]
            g2['n'] += 1
            g2['correct'] += (1 if pred_x == actual else 0)
            g2['odds_correct'] += (1 if pred_odds == actual else 0)
            g2['signal_sum'] += signal
            g2['signal_abs_sum'] += sig_abs
            if is_flipped:
                g2['flip_n'] += 1
                g2['flip_correct'] += (1 if pred_x == actual else 0)
            else:
                g2['no_flip_n'] += 1
                g2['no_flip_correct'] += (1 if pred_x == actual else 0)
            if is_draw_pred:
                g2['draw_pred_n'] += 1
                g2['draw_correct'] += (1 if actual == 'draw' else 0)
            if actual == 'draw':
                g2['draw_actual_n'] += 1

    conn.close()

    # 输出
    p(f"\n  === 总体 ===")
    for key, g in sorted(groups.items()):
        if g['n'] == 0: continue
        label = key
        acc = g['correct'] / g['n'] * 100
        odds_acc = g['odds_correct'] / g['n'] * 100
        gap = acc - odds_acc
        flip_rate = g['flip_n'] / g['n'] * 100 if g['n'] > 0 else 0
        flip_acc = g['flip_correct'] / g['flip_n'] * 100 if g['flip_n'] > 0 else 0
        no_flip_acc = g['no_flip_correct'] / g['no_flip_n'] * 100 if g['no_flip_n'] > 0 else 0
        draw_recall = g['draw_correct'] / g['draw_actual_n'] * 100 if g['draw_actual_n'] > 0 else 0
        avg_signal = g['signal_sum'] / g['n']
        avg_signal_abs = g['signal_abs_sum'] / g['n']
        p(f"\n  [{label}] n={g['n']}")
        p(f"    model={acc:.1f}% odds={odds_acc:.1f}% gap={gap:+.1f}pp")
        p(f"    flip={g['flip_n']}({flip_rate:.0f}%) acc={flip_acc:.1f}% | no_flip={g['no_flip_n']} acc={no_flip_acc:.1f}%")
        p(f"    draw_pred={g['draw_pred_n']} recall={draw_recall:.1f}% | draw_actual={g['draw_actual_n']}")
        p(f"    avg_signal={avg_signal:.3f} avg_|signal|={avg_signal_abs:.3f}")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_signal_analysis.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

if __name__ == "__main__":
    main()
