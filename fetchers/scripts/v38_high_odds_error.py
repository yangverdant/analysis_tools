"""
v3.8+深度分析: 高赔率区间(3.0+)的改错模式
为什么模型在高赔率区间落后赔率8.5pp?
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
    p("  高赔率区间(3.0+)改错模式分析")
    p("=" * 70)

    # 模型vs赔率改对改错统计
    patterns = defaultdict(int)
    flag_in_error = defaultdict(int)
    flag_in_correct = defaultdict(int)
    error_examples = []
    correct_examples = []

    # signal分布
    sig_bins = defaultdict(lambda: {'n': 0, 'model_correct': 0, 'odds_correct': 0})

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

        if odds_h < 3.0 or odds_h <= 0: continue

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

        model_correct = (pred_x == actual)
        odds_correct = (pred_odds == actual)

        # signal分桶
        sig_abs = abs(signal)
        if sig_abs < 0.1: sig_bin = "0-0.1"
        elif sig_abs < 0.2: sig_bin = "0.1-0.2"
        elif sig_abs < 0.3: sig_bin = "0.2-0.3"
        elif sig_abs < 0.5: sig_bin = "0.3-0.5"
        else: sig_bin = "0.5+"
        sig_bins[sig_bin]['n'] += 1
        sig_bins[sig_bin]['model_correct'] += (1 if model_correct else 0)
        sig_bins[sig_bin]['odds_correct'] += (1 if odds_correct else 0)

        # 改对改错模式
        if not model_correct and odds_correct:
            pat = f"赔率→{pred_odds}(✓) 模型→{pred_x}(✗)"
            patterns[pat] += 1
            for f in v34_flags:
                flag_in_error[f] += 1
            error_examples.append({
                'date': m['date'], 'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'], 'odds_h': odds_h,
                'score': f"{m['home_score']}-{m['away_score']}",
                'pred_x': pred_x, 'pred_odds': pred_odds, 'actual': actual,
                'hp_x': hp_x, 'dp_x': dp_x, 'ap_x': ap_x,
                'hp_o': hp_o, 'dp_o': dp_o, 'ap_o': ap_o,
                'signal': signal, 'euro_conf': euro_conf, 'signal_strength': signal_strength,
                'flags': v34_flags,
            })
        elif model_correct and not odds_correct:
            pat = f"模型→{pred_x}(✓) 赔率→{pred_odds}(✗)"
            patterns[pat] += 1
            for f in v34_flags:
                flag_in_correct[f] += 1
            correct_examples.append({
                'date': m['date'], 'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'],
                'pred_x': pred_x, 'pred_odds': pred_odds, 'actual': actual,
                'signal': signal,
            })

    conn.close()

    total_errors = sum(patterns.values())
    total_correct = sum(v for k, v in patterns.items() if '模型' in k and '✓' in k)

    p(f"\n  === 改错模式 (odds>=3.0) ===")
    for pat, cnt in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
        p(f"  {pat}: {cnt}场 ({cnt/total_errors*100:.1f}%)")

    p(f"\n  === 改错中的flag分布 ===")
    for f, cnt in sorted(flag_in_error.items(), key=lambda x: x[1], reverse=True):
        p(f"  {f}: {cnt}场 ({cnt/total_errors*100:.1f}%)")

    p(f"\n  === 改对中的flag分布 ===")
    for f, cnt in sorted(flag_in_correct.items(), key=lambda x: x[1], reverse=True):
        p(f"  {f}: {cnt}场 ({cnt/total_correct*100:.1f}%)")

    p(f"\n  === signal强度分桶 ===")
    for bin_name in ["0-0.1", "0.1-0.2", "0.2-0.3", "0.3-0.5", "0.5+"]:
        g = sig_bins[bin_name]
        if g['n'] == 0: continue
        m_acc = g['model_correct'] / g['n'] * 100
        o_acc = g['odds_correct'] / g['n'] * 100
        p(f"  signal {bin_name}: n={g['n']} model={m_acc:.1f}% odds={o_acc:.1f}% gap={m_acc-o_acc:+.1f}pp")

    p(f"\n  === 典型改错案例 (前20) ===")
    for ex in sorted(error_examples, key=lambda x: x['odds_h'])[:20]:
        p(f"  {ex['date']} {ex['home']} vs {ex['away']} ({ex['league']})")
        p(f"    odds_h={ex['odds_h']:.2f} score={ex['score']}")
        p(f"    模型: h={ex['hp_x']*100:.1f}% d={ex['dp_x']*100:.1f}% a={ex['ap_x']*100:.1f}% → {ex['pred_x']}")
        p(f"    赔率: h={ex['hp_o']*100:.1f}% d={ex['dp_o']*100:.1f}% a={ex['ap_o']*100:.1f}% → {ex['pred_odds']}")
        p(f"    signal={ex['signal']:.3f} conf={ex['euro_conf']:.2f} strength={ex['signal_strength']}")
        p(f"    flags={','.join(ex['flags'])}")

    p(f"\n  总改错: {total_errors}场, 总改对: {total_correct}场, 净差: {total_correct - total_errors}")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_high_odds_error.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

if __name__ == "__main__":
    main()
