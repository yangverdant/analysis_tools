"""
v3.8聚焦分析: |AH|=0(平手盘) + odds 2-3区间的模型表现
这是模型最差的子群: 模型38.5% vs 赔率40.2%
"""
import sys, io, json, sqlite3, math
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
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='factor' AND md.data_type='factor:asian_handicap')
        ORDER BY m.date
    """).fetchall()

    lines = []
    def p(s=""):
        lines.append(s)

    p("=" * 70)
    p("  v3.8聚焦: |AH|=0(平手盘) + odds 2-3的模型改错分析")
    p("=" * 70)

    # 分类
    pattern_stats = defaultdict(int)
    flag_in_error = defaultdict(int)
    error_examples = []

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        model_data = json.loads(model_row['data_json'])
        hp_m = model_data.get('home_win_prob', 0.33)
        dp_m = model_data.get('draw_prob', 0.33)
        ap_m = model_data.get('away_win_prob', 0.34)
        flags = model_data.get('scenario_flags', [])
        signal = model_data.get('signal_value', 0)
        pred_m = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_m, 'draw': dp_m, 'away': ap_m}[x])

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        hp_o = float(odds_data.get('home_value', 0) or 0)
        dp_o = float(odds_data.get('draw_value', 0) or 0)
        ap_o = float(odds_data.get('away_value', 0) or 0)
        odds_h = float(odds_data.get('raw', {}).get('avg_home_odds', 0) or odds_data.get('raw', {}).get('closing_avg_home_odds', 0) or 0)

        pred_o = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

        ah_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
            (mk,)).fetchone()
        ah_data = json.loads(ah_row['data_json'])
        ah_handicap = ah_data.get('raw', {}).get('closing_handicap', None)
        if ah_handicap is None: continue
        abs_hc = abs(float(ah_handicap))

        # 只看 |AH|=0 (平手盘) + odds 2-3
        if abs_hc > 0.01 or not (2.0 <= odds_h < 3.0): continue

        # 只看赔率正确但模型错误的
        if pred_o != actual or pred_m == actual: continue

        pat = f"赔率→{pred_o}(✓) 模型→{pred_m}(✗)"
        pattern_stats[pat] += 1

        for f in flags:
            flag_in_error[f] += 1

        error_examples.append({
            'date': m['date'], 'home': m['home_team'], 'away': m['away_team'],
            'league': m['league_standard'], 'odds_h': odds_h,
            'score': f"{m['home_score']}-{m['away_score']}", 'actual': actual,
            'pred_o': pred_o, 'pred_m': pred_m,
            'hp_m': hp_m, 'dp_m': dp_m, 'ap_m': ap_m,
            'signal': signal, 'flags': flags,
        })

    conn.close()

    p(f"\n  === 改错pattern (|AH|=0, odds 2-3) ===")
    total_errors = sum(pattern_stats.values())
    for pat, cnt in sorted(pattern_stats.items(), key=lambda x: x[1], reverse=True):
        p(f"  {pat}: {cnt}场 ({cnt/total_errors*100:.1f}%)")

    p(f"\n  === 改错中flag分布 ===")
    for f, cnt in sorted(flag_in_error.items(), key=lambda x: x[1], reverse=True):
        p(f"  {f}: {cnt}场 ({cnt/total_errors*100:.1f}%)")

    p(f"\n  === 改错案例 (前30) ===")
    for ex in sorted(error_examples, key=lambda x: abs(x['signal']), reverse=True)[:30]:
        p(f"  {ex['date']} {ex['home']} vs {ex['away']} ({ex['league']}) odds_h={ex['odds_h']:.2f}")
        p(f"    score={ex['score']} 赔率→{ex['pred_o']} 模型→{ex['pred_m']}")
        p(f"    h={ex['hp_m']*100:.1f}% d={ex['dp_m']*100:.1f}% a={ex['ap_m']*100:.1f}%")
        p(f"    signal={ex['signal']:.4f} flags={','.join(ex['flags'])}")

    p(f"\n  总改错: {total_errors}场")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_ah0_error.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()