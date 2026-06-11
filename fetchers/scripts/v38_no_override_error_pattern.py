"""
v3.8诊断: no_override改错的290场具体pattern
这些比赛信号覆盖没触发，但模型仍改错了赔率方向
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
        ORDER BY m.date
    """).fetchall()

    lines = []
    def p(s=""):
        lines.append(s)

    p("=" * 70)
    p("  v3.8诊断: no_override改错的pattern分析")
    p("=" * 70)

    # 改错pattern分类
    pattern_stats = defaultdict(int)
    flag_in_error = defaultdict(lambda: {"n": 0, "error": 0})

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
        signal = model_data.get('signal_value', 0)
        flags = model_data.get('scenario_flags', [])

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        hp_o = float(odds_data.get('home_value', 0) or 0)
        dp_o = float(odds_data.get('draw_value', 0) or 0)
        ap_o = float(odds_data.get('away_value', 0) or 0)
        odds_h = float(odds_data.get('raw', {}).get('avg_home_odds', 0) or odds_data.get('raw', {}).get('closing_avg_home_odds', 0) or 0)

        pred_m = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_m, 'draw': dp_m, 'away': ap_m}[x])
        pred_o = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])
        euro_conf = max(hp_o, dp_o, ap_o)

        if not (2.0 <= odds_h < 3.0): continue

        # 只看赔率正确但模型错误的
        if pred_o != actual or pred_m == actual: continue

        # 判断是否属于no_override
        is_override = False
        if euro_conf < 0.45:
            if pred_o == 'home' and signal < -0.15:
                is_override = True
            elif pred_o == 'away' and signal > 0.15:
                is_override = True

        if is_override: continue

        # 改错pattern
        pat = f"赔率→{pred_o}(✓) 模型→{pred_m}(✗)"
        pattern_stats[pat] += 1

        # flags统计
        for f in flags:
            flag_in_error[f]["n"] += 1
            flag_in_error[f]["error"] += 1

    # 输出
    p(f"\n  === 改错pattern分布 (no_override, 2-3区间) ===")
    total_errors = sum(pattern_stats.values())
    for pat, cnt in sorted(pattern_stats.items(), key=lambda x: x[1], reverse=True):
        p(f"  {pat}: {cnt}场 ({cnt/total_errors*100:.1f}%)")

    p(f"\n  === 改错比赛中的flag分布 ===")
    for f, data in sorted(flag_in_error.items(), key=lambda x: x[1]["error"], reverse=True):
        p(f"  {f}: 出现{data['n']}场 全在改错中({data['error']}场)")

    p(f"\n  总改错: {total_errors}场")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_no_override_error_pattern.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()