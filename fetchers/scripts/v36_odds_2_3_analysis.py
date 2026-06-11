"""
分析odds 2.0-3.0区间: 模型把赔率的正确预测改错了多少场?
"""
import sys, io, json, sqlite3
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

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
    """).fetchall()

    lines = []
    def p(s=""):
        lines.append(s)

    p("=" * 70)
    p("  odds 2.0-3.0区间: 模型 vs 赔率预测差异分析")
    p("=" * 70)

    # 分类:
    # A: 赔率正确模型也正确
    # B: 赔率正确模型错误 — 模型改错
    # C: 赔率错误模型正确 — 模型改对
    # D: 赔率错误模型也错误

    a_count = b_count = c_count = d_count = 0
    b_examples = []
    c_examples = []

    # 按信号方向细分
    signal_stats = defaultdict(lambda: {"n": 0, "b": 0, "c": 0})

    # 按场景flag细分
    flag_stats = defaultdict(lambda: {"n": 0, "b": 0, "c": 0})

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        # 模型
        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        model_data = json.loads(model_row['data_json'])
        hp_m = model_data.get('home_win_prob', 0.33)
        dp_m = model_data.get('draw_prob', 0.33)
        ap_m = model_data.get('away_win_prob', 0.34)
        pred_m = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_m, 'draw': dp_m, 'away': ap_m}[x])
        signal = model_data.get('signal_value', 0)
        flags = model_data.get('scenario_flags', [])

        # 赔率
        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        hp_o = float(odds_data.get('home_value', 0) or 0)
        dp_o = float(odds_data.get('draw_value', 0) or 0)
        ap_o = float(odds_data.get('away_value', 0) or 0)
        odds_h = float(odds_data.get('raw', {}).get('avg_home_odds', 0) or odds_data.get('raw', {}).get('closing_avg_home_odds', 0) or 0)

        if odds_h < 2.0 or odds_h >= 3.0 or odds_h <= 0: continue

        pred_o = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

        odds_ok = pred_o == actual
        model_ok = pred_m == actual

        if odds_ok and model_ok:
            a_count += 1
        elif odds_ok and not model_ok:
            b_count += 1
            b_examples.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'],
                'actual': actual, 'score': f"{m['home_score']}-{m['away_score']}",
                'pred_o': pred_o, 'pred_m': pred_m,
                'hp_m': hp_m, 'dp_m': dp_m, 'ap_m': ap_m,
                'hp_o': hp_o, 'dp_o': dp_o, 'ap_o': ap_o,
                'signal': signal, 'flags': flags,
            })
        elif not odds_ok and model_ok:
            c_count += 1
            c_examples.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'],
                'actual': actual, 'score': f"{m['home_score']}-{m['away_score']}",
                'pred_o': pred_o, 'pred_m': pred_m,
                'signal': signal,
            })
        else:
            d_count += 1

        # 信号方向统计
        if abs(signal) < 0.03:
            sig_key = "信号近0(draw倾向)"
        elif signal > 0.03:
            sig_key = "信号正(home倾向)"
        else:
            sig_key = "信号负(away倾向)"
        signal_stats[sig_key]["n"] += 1
        if odds_ok and not model_ok: signal_stats[sig_key]["b"] += 1
        if not odds_ok and model_ok: signal_stats[sig_key]["c"] += 1

        # 场景flag
        for flag in flags:
            flag_stats[flag]["n"] += 1
            if odds_ok and not model_ok: flag_stats[flag]["b"] += 1
            if not odds_ok and model_ok: flag_stats[flag]["c"] += 1

    total = a_count + b_count + c_count + d_count
    p(f"\n  === 总体 ===")
    p(f"  n={total}")
    p(f"  A(赔率✓模型✓): {a_count} ({a_count/total*100:.1f}%)")
    p(f"  B(赔率✓模型✗): {b_count} ({b_count/total*100:.1f}%) — 模型改错")
    p(f"  C(赔率✗模型✓): {c_count} ({c_count/total*100:.1f}%) — 模型改对")
    p(f"  D(赔率✗模型✗): {d_count} ({d_count/total*100:.1f}%) — 都错")
    p(f"  模型改错净损失: {b_count-c_count}场 ({(b_count-c_count)/total*100:.1f}pp)")

    # 模型改错的详情
    p(f"\n  === 模型改错的比赛(B类) — top 30 ===")
    for ex in sorted(b_examples, key=lambda x: abs(x['signal']), reverse=True)[:30]:
        p(f"  {ex['date']} {ex['home']} vs {ex['away']} ({ex['league']})")
        p(f"    score={ex['score']} actual={ex['actual']} 赔率={ex['pred_o']} 模型={ex['pred_m']}")
        p(f"    赔率: h={ex['hp_o']*100:.1f}% d={ex['dp_o']*100:.1f}% a={ex['ap_o']*100:.1f}%")
        p(f"    模型: h={ex['hp_m']*100:.1f}% d={ex['dp_m']*100:.1f}% a={ex['ap_m']*100:.1f}%")
        p(f"    signal={ex['signal']:.4f} flags={','.join(ex['flags'][:3])}")

    # 模型改对的详情
    p(f"\n  === 模型改对的比赛(C类) — top 20 ===")
    for ex in sorted(c_examples, key=lambda x: abs(x['signal']), reverse=True)[:20]:
        p(f"  {ex['date']} {ex['home']} vs {ex['away']} ({ex['league']})")
        p(f"    score={ex['score']} actual={ex['actual']} 赔率={ex['pred_o']} 模型={ex['pred_m']} signal={ex['signal']:.4f}")

    # 信号方向影响
    p(f"\n  === 信号方向对改错率的影响 ===")
    for sig_key in sorted(signal_stats.keys()):
        ss = signal_stats[sig_key]
        n = ss["n"]
        b_pct = ss["b"]/n*100 if n > 0 else 0
        c_pct = ss["c"]/n*100 if n > 0 else 0
        net = ss["b"] - ss["c"]
        p(f"  {sig_key}: n={n} 改错={ss['b']}({b_pct:.1f}%) 改对={ss['c']}({c_pct:.1f}%) 净损={net}")

    # 场景flag影响
    p(f"\n  === 场景flag对改错率的影响 ===")
    for flag in sorted(flag_stats.keys(), key=lambda x: flag_stats[x]["n"], reverse=True):
        fs = flag_stats[flag]
        n = fs["n"]
        if n < 10: continue
        b_pct = fs["b"]/n*100 if n > 0 else 0
        c_pct = fs["c"]/n*100 if n > 0 else 0
        net = fs["b"] - fs["c"]
        p(f"  {flag}: n={n} 改错={fs['b']}({b_pct:.1f}%) 改对={fs['c']}({c_pct:.1f}%) 净损={net}")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v36_odds_2_3_analysis.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

    conn.close()


if __name__ == "__main__":
    main()