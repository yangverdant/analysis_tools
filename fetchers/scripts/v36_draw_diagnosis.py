"""
诊断: 有赔率比赛的平局概率为什么偏低?
核心问题: 实际平局25.6%但模型只预测8.7%
"""
import sys, io, json, sqlite3, math
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

    # 只看有赔率的比赛
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

    p("=" * 70)
    p("  平局概率偏低诊断 — 有赔率比赛")
    p("=" * 70)
    p(f"  有赔率比赛: {len(matches)}")

    # 分组: 模型预测平局概率区间
    dp_bins = defaultdict(lambda: {"n": 0, "actual_draw": 0, "avg_market_draw": 0.0,
                                    "avg_ah_draw": 0.0, "model_pred_draw": 0.0})

    # 按赔率隐含平局概率分
    market_draw_bins = defaultdict(lambda: {"n": 0, "actual_draw": 0, "model_pred_draw": 0.0})

    # 模型预测方向分布
    pred_direction = defaultdict(lambda: {"n": 0, "actual_home": 0, "actual_draw": 0, "actual_away": 0})

    total_draw_pred = 0
    total_draw_actual = 0

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
        pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

        # 赔率隐含概率
        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        market_draw = odds_data.get('raw', {}).get('draw_prob', 0)
        market_home = odds_data.get('home_value', 0)
        market_away = odds_data.get('away_value', 0)

        if actual == 'draw': total_draw_actual += 1
        if pred == 'draw': total_draw_pred += 1

        # 模型平局概率区间
        if dp < 0.10: dp_key = "<10%"
        elif dp < 0.15: dp_key = "10-15%"
        elif dp < 0.20: dp_key = "15-20%"
        elif dp < 0.25: dp_key = "20-25%"
        elif dp < 0.30: dp_key = "25-30%"
        elif dp < 0.35: dp_key = "30-35%"
        else: dp_key = ">35%"
        ds = dp_bins[dp_key]
        ds["n"] += 1
        ds["actual_draw"] += (1 if actual == 'draw' else 0)
        ds["avg_market_draw"] += market_draw
        ds["model_pred_draw"] += dp

        # 赔率平局概率区间
        if market_draw > 0:
            if market_draw < 0.20: mk_key = "<20%"
            elif market_draw < 0.25: mk_key = "20-25%"
            elif market_draw < 0.30: mk_key = "25-30%"
            elif market_draw < 0.35: mk_key = "30-35%"
            elif market_draw < 0.40: mk_key = "35-40%"
            else: mk_key = ">40%"
            ms = market_draw_bins[mk_key]
            ms["n"] += 1
            ms["actual_draw"] += (1 if actual == 'draw' else 0)
            ms["model_pred_draw"] += dp

        # 预测方向
        pred_direction[pred]["n"] += 1
        pred_direction[pred][f"actual_{actual}"] += 1

    total = len(matches)

    # === 1. 总体 ===
    p(f"\n  === 1. 总体 ===")
    p(f"  实际平局: {total_draw_actual}/{total}={total_draw_actual/total*100:.1f}%")
    p(f"  预测平局: {total_draw_pred}/{total}={total_draw_pred/total*100:.1f}%")
    p(f"  差距: {total_draw_actual - total_draw_pred}场 ({total_draw_actual/total*100 - total_draw_pred/total*100:.1f}pp)")

    # === 2. 预测方向分布 ===
    p(f"\n  === 2. 预测方向分布 ===")
    for d in ['home', 'draw', 'away']:
        ds = pred_direction[d]
        n = ds["n"]
        if n == 0: continue
        p(f"  预测{d}: {n}场({n/total*100:.1f}%) → 实际: home={ds['actual_home']}({ds['actual_home']/n*100:.0f}%) "
          f"draw={ds['actual_draw']}({ds['actual_draw']/n*100:.0f}%) away={ds['actual_away']}({ds['actual_away']/n*100:.0f}%)")

    # === 3. 模型平局概率 vs 实际 ===
    p(f"\n  === 3. 模型平局概率区间 vs 实际平局率 ===")
    dp_order = ["<10%", "10-15%", "15-20%", "20-25%", "25-30%", "30-35%", ">35%"]
    for dk in dp_order:
        ds = dp_bins[dk]
        n = ds["n"]
        if n < 10: continue
        actual_pct = ds["actual_draw"]/n*100
        model_pct = ds["model_pred_draw"]/n*100
        market_pct = ds["avg_market_draw"]/n*100 if n > 0 else 0
        p(f"  模型预测{dk}: n={n} 实际平局={actual_pct:.1f}% 赔率平局={market_pct:.1f}% 模型平均={model_pct:.1f}%")

    # === 4. 赔率平局概率 vs 实际 ===
    p(f"\n  === 4. 赔率平局概率区间 vs 实际平局率 ===")
    mk_order = ["<20%", "20-25%", "25-30%", "30-35%", "35-40%", ">40%"]
    for mk in mk_order:
        ms = market_draw_bins[mk]
        n = ms["n"]
        if n < 10: continue
        actual_pct = ms["actual_draw"]/n*100
        model_pct = ms["model_pred_draw"]/n*100
        p(f"  赔率{mk}: n={n} 实际平局={actual_pct:.1f}% 模型平均预测={model_pct:.1f}%")

    # === 5. 关键分析: 赔率平局概率30%+ 的比赛 ===
    p(f"\n  === 5. 赔率平局概率>=30%的比赛 ===")
    high_draw = [m for m in matches if True]
    n_high = 0
    n_high_actual_draw = 0
    n_high_pred_draw = 0
    n_high_pred_home = 0
    n_high_pred_away = 0

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        market_draw = odds_data.get('raw', {}).get('draw_prob', 0)

        if market_draw < 0.30: continue

        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        model_data = json.loads(model_row['data_json'])
        hp = model_data.get('home_win_prob', 0.33)
        dp = model_data.get('draw_prob', 0.33)
        ap = model_data.get('away_win_prob', 0.34)
        pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

        n_high += 1
        if actual == 'draw': n_high_actual_draw += 1
        if pred == 'draw': n_high_pred_draw += 1
        if pred == 'home': n_high_pred_home += 1
        if pred == 'away': n_high_pred_away += 1

    if n_high > 0:
        p(f"  n={n_high} 实际平局={n_high_actual_draw}({n_high_actual_draw/n_high*100:.1f}%) "
          f"模型预测平局={n_high_pred_draw}({n_high_pred_draw/n_high*100:.1f}%) "
          f"模型预测主胜={n_high_pred_home}({n_high_pred_home/n_high*100:.1f}%) "
          f"模型预测客胜={n_high_pred_away}({n_high_pred_away/n_high*100:.1f}%)")

    # === 6. 亚盘校准效果 ===
    p(f"\n  === 6. 亚盘校准效果 ===")
    ah_groups = {"有亚盘": defaultdict(lambda: {"n": 0, "actual_draw": 0, "model_draw": 0.0}),
                 "无亚盘": defaultdict(lambda: {"n": 0, "actual_draw": 0, "model_draw": 0.0})}

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        model_data = json.loads(model_row['data_json'])
        dp = model_data.get('draw_prob', 0.33)

        ah_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
            (mk,)).fetchone()
        has_ah = ah_row is not None

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        market_draw = odds_data.get('raw', {}).get('draw_prob', 0)

        group = "有亚盘" if has_ah else "无亚盘"
        draw_bin = f"{int(market_draw*20)*5}%"  # 5% bin
        ah_groups[group][draw_bin]["n"] += 1
        ah_groups[group][draw_bin]["actual_draw"] += (1 if actual == 'draw' else 0)
        ah_groups[group][draw_bin]["model_draw"] += dp

    for group_name in ["有亚盘", "无亚盘"]:
        p(f"\n  {group_name}:")
        for bin_key in sorted(ah_groups[group_name].keys()):
            gs = ah_groups[group_name][bin_key]
            n = gs["n"]
            if n < 10: continue
            actual_pct = gs["actual_draw"]/n*100
            model_pct = gs["model_draw"]/n*100
            p(f"    赔率平局~{bin_key}: n={n} 实际平局={actual_pct:.1f}% 模型预测={model_pct:.1f}%")

    p(f"\n{'=' * 70}")
    p("  诊断完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v36_draw_diagnosis.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

    conn.close()


if __name__ == "__main__":
    main()