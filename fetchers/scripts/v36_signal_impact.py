"""
核心诊断: 欧赔平局概率 → 信号调整 → 最终模型平局概率
看信号调整把平局概率压低了多少
"""
import sys, io, json, sqlite3
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    lines = []
    def p(s=""):
        lines.append(s)

    # 只看有赔率+有模型的比赛
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

    p("=" * 70)
    p("  信号调整对平局概率的影响")
    p("=" * 70)
    p(f"  比赛数: {len(matches)}")

    # 按欧赔平局概率区间分组，看信号调整效果
    draw_bins = defaultdict(lambda: {"n": 0, "actual_draw": 0,
                                      "market_dp_sum": 0.0, "model_dp_sum": 0.0})

    # 信号分析
    signal_impact = defaultdict(lambda: {"n": 0, "dp_before_sum": 0.0, "dp_after_sum": 0.0,
                                          "actual_draw": 0})

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        # 模型结果
        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        model_data = json.loads(model_row['data_json'])
        hp = model_data.get('home_win_prob', 0.33)
        dp = model_data.get('draw_prob', 0.33)
        ap = model_data.get('away_win_prob', 0.34)
        flags = model_data.get('scenario_flags', [])

        # 欧赔隐含概率
        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        raw = odds_data.get('raw', {})
        market_dp = float(raw.get('draw_prob', 0) or 0)
        market_hp = float(raw.get('home_prob', 0) or 0)
        market_ap = float(raw.get('away_prob', 0) or 0)

        # 有亚盘?
        ah_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
            (mk,)).fetchone()
        has_ah = ah_row is not None

        if market_dp <= 0:
            continue

        # 按赔率平局概率分bin
        if market_dp < 0.22: dp_key = "<22%"
        elif market_dp < 0.26: dp_key = "22-26%"
        elif market_dp < 0.30: dp_key = "26-30%"
        elif market_dp < 0.34: dp_key = "30-34%"
        elif market_dp < 0.38: dp_key = "34-38%"
        else: dp_key = ">38%"

        ds = draw_bins[dp_key]
        ds["n"] += 1
        ds["actual_draw"] += (1 if actual == 'draw' else 0)
        ds["market_dp_sum"] += market_dp
        ds["model_dp_sum"] += dp

        # 信号影响
        has_draw_rule = any(f.startswith('draw_threshold') for f in flags)
        signal_key = "有draw_threshold规则" if has_draw_rule else "无draw_threshold规则"
        si = signal_impact[signal_key]
        si["n"] += 1
        si["dp_before_sum"] += market_dp
        si["dp_after_sum"] += dp
        si["actual_draw"] += (1 if actual == 'draw' else 0)

    # === 1. 赔率平局概率 vs 模型平局概率 vs 实际 ===
    p(f"\n  === 赔率平局 → 模型平局 → 实际 ===")
    bin_order = ["<22%", "22-26%", "26-30%", "30-34%", "34-38%", ">38%"]
    for bk in bin_order:
        bs = draw_bins[bk]
        n = bs["n"]
        if n < 10: continue
        actual_pct = bs["actual_draw"]/n*100
        market_avg = bs["market_dp_sum"]/n*100
        model_avg = bs["model_dp_sum"]/n*100
        diff = model_avg - market_avg
        p(f"  赔率{bk}: n={n} 赔率均={market_avg:.1f}% 模型均={model_avg:.1f}% "
          f"信号Δ={diff:+.1f}pp 实际={actual_pct:.1f}%")

    # === 2. draw_threshold规则效果 ===
    p(f"\n  === draw_threshold规则效果 ===")
    for sk in ["有draw_threshold规则", "无draw_threshold规则"]:
        si = signal_impact[sk]
        n = si["n"]
        if n < 10: continue
        avg_before = si["dp_before_sum"]/n*100
        avg_after = si["dp_after_sum"]/n*100
        actual_pct = si["actual_draw"]/n*100
        p(f"  {sk}: n={n} 赔率平局={avg_before:.1f}% 模型平局={avg_after:.1f}% "
          f"Δ={avg_after-avg_before:+.1f}pp 实际={actual_pct:.1f}%")

    # === 3. 无赔率比赛的模型概率 ===
    no_odds = conn.execute("""
        SELECT m.match_key, m.date, m.home_team, m.away_team,
               m.league_standard, m.home_score, m.away_score
        FROM matches m
        WHERE m.status='finished' AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='model' AND md.data_type='model:enhanced_linear')
        AND NOT EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                        AND md.source='factor' AND md.data_type='factor:euro_odds')
    """).fetchall()

    p(f"\n  === 无赔率比赛 ===")
    p(f"  总数: {len(no_odds)}")
    no_odds_actual = defaultdict(int)
    no_odds_pred = defaultdict(int)
    no_odds_model_dp = 0.0
    for m in no_odds:
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
        pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
        no_odds_actual[actual] += 1
        no_odds_pred[pred] += 1
        no_odds_model_dp += dp

    n_no = len(no_odds)
    if n_no > 0:
        p(f"  实际: home={no_odds_actual['home']}({no_odds_actual['home']/n_no*100:.1f}%) "
          f"draw={no_odds_actual['draw']}({no_odds_actual['draw']/n_no*100:.1f}%) "
          f"away={no_odds_actual['away']}({no_odds_actual['away']/n_no*100:.1f}%)")
        p(f"  预测: home={no_odds_pred['home']}({no_odds_pred['home']/n_no*100:.1f}%) "
          f"draw={no_odds_pred['draw']}({no_odds_pred['draw']/n_no*100:.1f}%) "
          f"away={no_odds_pred['away']}({no_odds_pred['away']/n_no*100:.1f}%)")
        p(f"  模型平均平局概率: {no_odds_model_dp/n_no*100:.1f}%")

    # === 4. 关键: 有赔率+赔率平局>=30% 但模型没选平局 ===
    p(f"\n  === 赔率平局>=30%但模型选非平局 ===")
    high_draw_not_pred = 0
    high_draw_pred = 0
    high_draw_total = 0
    high_draw_actual = 0

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        market_dp = float(odds_data.get('raw', {}).get('draw_prob', 0) or 0)

        if market_dp < 0.30: continue

        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        model_data = json.loads(model_row['data_json'])
        hp = model_data.get('home_win_prob', 0.33)
        dp = model_data.get('draw_prob', 0.33)
        ap = model_data.get('away_win_prob', 0.34)
        pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

        high_draw_total += 1
        if actual == 'draw': high_draw_actual += 1
        if pred == 'draw': high_draw_pred += 1
        else: high_draw_not_pred += 1

    if high_draw_total > 0:
        p(f"  n={high_draw_total} 实际平局={high_draw_actual}({high_draw_actual/high_draw_total*100:.1f}%) "
          f"模型选平局={high_draw_pred}({high_draw_pred/high_draw_total*100:.1f}%) "
          f"模型选非平局={high_draw_not_pred}({high_draw_not_pred/high_draw_total*100:.1f}%)")

    p(f"\n{'=' * 70}")
    p("  诊断完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v36_signal_impact.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

    conn.close()


if __name__ == "__main__":
    main()