"""
v3.8诊断: 亚盘/泊松draw校准在2-3区间的效果
这些校准也会增加draw概率，可能和draw_threshold一样导致改错
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
        ORDER BY m.date
    """).fetchall()

    lines = []
    def p(s=""):
        lines.append(s)

    p("=" * 70)
    p("  v3.8诊断: 亚盘/泊松draw校准在2-3区间的效果")
    p("=" * 70)

    # 统计: 模型draw概率 vs 赔率draw概率的偏差
    # 按draw_prob来源分组

    dp_diff_stats = defaultdict(lambda: {"n": 0, "model_ok": 0, "odds_ok": 0,
                                          "actual_draw": 0, "pred_draw": 0, "odds_pred_draw": 0,
                                          "avg_dp_diff": 0.0})

    # 按draw_threshold flag分组
    flag_stats = defaultdict(lambda: {"n": 0, "model_ok": 0, "odds_ok": 0,
                                       "actual_draw": 0, "pred_draw": 0})

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
        pred_m = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_m, 'draw': dp_m, 'away': ap_m}[x])

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        hp_o = float(odds_data.get('home_value', 0) or 0)
        dp_o = float(odds_data.get('draw_value', 0) or 0)
        ap_o = float(odds_data.get('away_value', 0) or 0)
        odds_h = float(odds_data.get('raw', {}).get('avg_home_odds', 0) or odds_data.get('raw', {}).get('closing_avg_home_odds', 0) or 0)

        if not (2.0 <= odds_h < 3.0): continue

        pred_o = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

        # draw概率偏差: 模型draw - 赔率draw
        dp_diff = dp_m - dp_o

        # 按偏差大小分组
        if dp_diff < -0.05:
            diff_key = "模型draw<<赔率(<-5pp)"
        elif dp_diff < -0.01:
            diff_key = "模型draw<赔率(-5~-1pp)"
        elif dp_diff < 0.01:
            diff_key = "模型draw≈赔率(±1pp)"
        elif dp_diff < 0.05:
            diff_key = "模型draw>赔率(+1~+5pp)"
        elif dp_diff < 0.10:
            diff_key = "模型draw>>赔率(+5~+10pp)"
        else:
            diff_key = "模型draw>>>赔率(>+10pp)"

        ds = dp_diff_stats[diff_key]
        ds["n"] += 1
        if pred_m == actual: ds["model_ok"] += 1
        if pred_o == actual: ds["odds_ok"] += 1
        if actual == 'draw': ds["actual_draw"] += 1
        if pred_m == 'draw': ds["pred_draw"] += 1
        if pred_o == 'draw': ds["odds_pred_draw"] += 1
        ds["avg_dp_diff"] += dp_diff

        # flag统计
        for f in flags:
            fs = flag_stats[f]
            fs["n"] += 1
            if pred_m == actual: fs["model_ok"] += 1
            if pred_o == actual: fs["odds_ok"] += 1
            if actual == 'draw': fs["actual_draw"] += 1
            if pred_m == 'draw': fs["pred_draw"] += 1

    conn.close()

    # 输出
    p(f"\n  === draw概率偏差 vs argmax效果 ===")
    for diff_key in sorted(dp_diff_stats.keys()):
        ds = dp_diff_stats[diff_key]
        n = ds["n"]
        if n == 0: continue
        p(f"\n  {diff_key}: n={n}")
        p(f"  模型argmax: {ds['model_ok']/n*100:.1f}%  赔率argmax: {ds['odds_ok']/n*100:.1f}%  差: {(ds['model_ok']-ds['odds_ok'])/n*100:+.1f}pp")
        p(f"  实际draw: {ds['actual_draw']/n*100:.1f}%  模型预测draw: {ds['pred_draw']/n*100:.1f}%  赔率预测draw: {ds['odds_pred_draw']/n*100:.1f}%")
        p(f"  平均dp_diff: {ds['avg_dp_diff']/n*100:+.1f}pp")

    p(f"\n  === flag在2-3区间 ===")
    for f in sorted(flag_stats.keys(), key=lambda x: flag_stats[x]["n"], reverse=True):
        fs = flag_stats[f]
        n = fs["n"]
        if n < 20: continue
        p(f"  {f}: n={n} 模型={fs['model_ok']/n*100:.1f}% 赔率={fs['odds_ok']/n*100:.1f}% "
          f"实际draw={fs['actual_draw']/n*100:.1f}% 模型预测draw={fs['pred_draw']/n*100:.1f}%")

    p(f"\n{'=' * 70}")
    p("  诊断完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_draw_calibration.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()