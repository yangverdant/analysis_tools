"""
v3.8核心分析: 模型概率 vs 赔率概率 逐因素偏差
关键问题: 模型改错赔率不是因为单一规则, 而是多个规则叠加
找出最大的draw概率偏差来源

方法: 从DB中找出亚盘数据, 计算AH draw校准的效果
"""
import sys, io, json, sqlite3, math
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

AH_DRAW_RATES = {
    0.00:  0.315, 0.25:  0.301, 0.50:  0.268,
    0.75:  0.250, 1.00:  0.239, 1.50:  0.191, 2.00:  0.128,
}

def ah_draw_rate(abs_hc):
    breakpoints = sorted(AH_DRAW_RATES.keys())
    if abs_hc <= breakpoints[0]: return AH_DRAW_RATES[breakpoints[0]]
    if abs_hc >= breakpoints[-1]: return AH_DRAW_RATES[breakpoints[-1]]
    for i in range(len(breakpoints) - 1):
        lo, hi = breakpoints[i], breakpoints[i + 1]
        if lo <= abs_hc <= hi:
            t = (abs_hc - lo) / (hi - lo)
            return AH_DRAW_RATES[lo] + t * (AH_DRAW_RATES[hi] - AH_DRAW_RATES[lo])
    return 0.26

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
    p("  v3.8: 亚盘数据覆盖和draw校准效果")
    p("=" * 70)

    # 统计
    has_ah_2_3 = 0  # 2-3区间有亚盘的
    no_ah_2_3 = 0   # 2-3区间没有亚盘的

    ah_stats = {"n": 0, "model_ok": 0, "odds_ok": 0, "actual_draw": 0,
               "pred_draw": 0, "avg_ah_draw": 0.0, "avg_dp_model": 0.0}

    no_ah_stats = {"n": 0, "model_ok": 0, "odds_ok": 0, "actual_draw": 0, "pred_draw": 0}

    # 按AH handicap大小
    ah_by_handicap = defaultdict(lambda: {"n": 0, "model_ok": 0, "odds_ok": 0,
                                            "actual_draw": 0, "avg_ah_draw": 0.0})

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        model_data = json.loads(model_row['data_json'])
        dp_m = model_data.get('draw_prob', 0.33)
        pred_m_data = {'home': model_data.get('home_win_prob', 0.33),
                       'draw': dp_m, 'away': model_data.get('away_win_prob', 0.34)}
        pred_m = max(['home', 'draw', 'away'], key=lambda x: pred_m_data[x])

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        hp_o = float(odds_data.get('home_value', 0) or 0)
        dp_o = float(odds_data.get('draw_value', 0) or 0)
        ap_o = float(odds_data.get('away_value', 0) or 0)
        odds_h = float(odds_data.get('raw', {}).get('avg_home_odds', 0) or odds_data.get('raw', {}).get('closing_avg_home_odds', 0) or 0)

        pred_o = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

        if not (2.0 <= odds_h < 3.0): continue

        # 亚盘数据
        ah_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
            (mk,)).fetchone()

        if ah_row and odds_h >= 2.0 and odds_h < 3.0:
            ah_data = json.loads(ah_row['data_json'])
            ah_handicap = ah_data.get('raw', {}).get('closing_handicap', None)
            if ah_handicap is not None and ah_data.get('confidence', 0) > 0:
                abs_hc = abs(float(ah_handicap))
                ah_draw = ah_draw_rate(abs_hc)
                has_ah_2_3 += 1

                ah_stats["n"] += 1
                if pred_m == actual: ah_stats["model_ok"] += 1
                if pred_o == actual: ah_stats["odds_ok"] += 1
                if actual == 'draw': ah_stats["actual_draw"] += 1
                if pred_m == 'draw': ah_stats["pred_draw"] += 1
                ah_stats["avg_ah_draw"] += ah_draw
                ah_stats["avg_dp_model"] += dp_m

                hc_bin = f"|AH|={abs_hc:.2f}" if abs_hc < 1 else f"|AH|={abs_hc:.1f}"
                ahb = ah_by_handicap[hc_bin]
                ahb["n"] += 1
                if pred_m == actual: ahb["model_ok"] += 1
                if pred_o == actual: ahb["odds_ok"] += 1
                if actual == 'draw': ahb["actual_draw"] += 1
                ahb["avg_ah_draw"] += ah_draw
            else:
                no_ah_2_3 += 1
                no_ah_stats["n"] += 1
                if pred_m == actual: no_ah_stats["model_ok"] += 1
                if pred_o == actual: no_ah_stats["odds_ok"] += 1
                if actual == 'draw': no_ah_stats["actual_draw"] += 1
                if pred_m == 'draw': no_ah_stats["pred_draw"] += 1
        else:
            no_ah_2_3 += 1
            no_ah_stats["n"] += 1
            if pred_m == actual: no_ah_stats["model_ok"] += 1
            if pred_o == actual: no_ah_stats["odds_ok"] += 1
            if actual == 'draw': no_ah_stats["actual_draw"] += 1
            if pred_m == 'draw': no_ah_stats["pred_draw"] += 1

    conn.close()

    p(f"\n  === 亚盘数据覆盖率(2-3区间) ===")
    p(f"  有亚盘数据: {has_ah_2_3}场 ({has_ah_2_3/(has_ah_2_3+no_ah_2_3)*100:.1f}%)")
    p(f"  无亚盘数据: {no_ah_2_3}场 ({no_ah_2_3/(has_ah_2_3+no_ah_2_3)*100:.1f}%)")

    if ah_stats["n"] > 0:
        p(f"\n  === 有亚盘的比赛 ===")
        n = ah_stats["n"]
        p(f"  n={n}")
        p(f"  模型argmax: {ah_stats['model_ok']/n*100:.1f}%")
        p(f"  赔率argmax: {ah_stats['odds_ok']/n*100:.1f}%")
        p(f"  差: {(ah_stats['model_ok']-ah_stats['odds_ok'])/n*100:+.1f}pp")
        p(f"  实际draw: {ah_stats['actual_draw']/n*100:.1f}%")
        p(f"  模型预测draw: {ah_stats['pred_draw']/n*100:.1f}%")
        p(f"  平均AH经验draw: {ah_stats['avg_ah_draw']/n*100:.1f}%")
        p(f"  平均模型draw: {ah_stats['avg_dp_model']/n*100:.1f}%")

    if no_ah_stats["n"] > 0:
        p(f"\n  === 无亚盘的比赛 ===")
        n = no_ah_stats["n"]
        p(f"  n={n}")
        p(f"  模型argmax: {no_ah_stats['model_ok']/n*100:.1f}%")
        p(f"  赔率argmax: {no_ah_stats['odds_ok']/n*100:.1f}%")
        p(f"  差: {(no_ah_stats['model_ok']-no_ah_stats['odds_ok'])/n*100:+.1f}pp")
        p(f"  实际draw: {no_ah_stats['actual_draw']/n*100:.1f}%")
        p(f"  模型预测draw: {no_ah_stats['pred_draw']/n*100:.1f}%")

    p(f"\n  === 按亚盘盘口大小 ===")
    for hc_bin in sorted(ah_by_handicap.keys()):
        ahb = ah_by_handicap[hc_bin]
        n = ahb["n"]
        if n < 10: continue
        p(f"  {hc_bin}: n={n} 模型={ahb['model_ok']/n*100:.1f}% 赔率={ahb['odds_ok']/n*100:.1f}% "
          f"实际draw={ahb['actual_draw']/n*100:.1f}% AH经验draw={ahb['avg_ah_draw']/n*100:.1f}%")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_ah_coverage.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()