"""
核心对比: 模型 vs 赔率直接argmax — 按赔率区间细分
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
    p("  模型 vs 赔率直接argmax — 按赔率区间细分")
    p("=" * 70)
    p(f"  比赛数: {len(matches)}")

    # 按赔率区间
    odds_stats = defaultdict(lambda: {"n": 0,
                                       "model_correct": 0, "odds_correct": 0,
                                       "model_brier": 0.0, "odds_brier": 0.0,
                                       "model_pred_draw": 0, "odds_pred_draw": 0})

    # 总体
    total_model_correct = 0
    total_odds_correct = 0
    total_model_brier = 0.0
    total_odds_brier = 0.0

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

        # 赔率
        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        raw = odds_data.get('raw', {})
        hp_o = float(raw.get('home_prob', 0) or 0)
        dp_o = float(raw.get('draw_prob', 0) or 0)
        ap_o = float(raw.get('away_prob', 0) or 0)
        odds_h = float(raw.get('avg_home_odds', 0) or raw.get('closing_avg_home_odds', 0) or 0)

        if hp_o + dp_o + ap_o == 0: continue

        # 归一化赔率
        total_o = hp_o + dp_o + ap_o
        hp_o, dp_o, ap_o = hp_o/total_o, dp_o/total_o, ap_o/total_o

        pred_o = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

        # Brier
        if actual == 'home':
            bm = (hp_m-1)**2 + dp_m**2 + ap_m**2
            bo = (hp_o-1)**2 + dp_o**2 + ap_o**2
        elif actual == 'draw':
            bm = hp_m**2 + (dp_m-1)**2 + ap_m**2
            bo = hp_o**2 + (dp_o-1)**2 + ap_o**2
        else:
            bm = hp_m**2 + dp_m**2 + (ap_m-1)**2
            bo = hp_o**2 + dp_o**2 + (ap_o-1)**2

        if pred_m == actual: total_model_correct += 1
        if pred_o == actual: total_odds_correct += 1
        total_model_brier += bm
        total_odds_brier += bo

        # 赔率区间
        if odds_h > 0:
            if odds_h < 1.30: ok = "<1.30"
            elif odds_h < 1.50: ok = "1.30-1.50"
            elif odds_h < 2.00: ok = "1.50-2.00"
            elif odds_h < 3.00: ok = "2.00-3.00"
            elif odds_h < 5.00: ok = "3.00-5.00"
            else: ok = ">5.00"
        else:
            ok = "无赔率"

        os = odds_stats[ok]
        os["n"] += 1
        if pred_m == actual: os["model_correct"] += 1
        if pred_o == actual: os["odds_correct"] += 1
        os["model_brier"] += bm
        os["odds_brier"] += bo
        if pred_m == 'draw': os["model_pred_draw"] += 1
        if pred_o == 'draw': os["odds_pred_draw"] += 1

    n = len(matches)
    p(f"\n  === 总体 ===")
    p(f"  赔率直接argmax: {total_odds_correct}/{n}={total_odds_correct/n*100:.1f}% Brier={total_odds_brier/n:.4f}")
    p(f"  模型argmax:     {total_model_correct}/{n}={total_model_correct/n*100:.1f}% Brier={total_model_brier/n:.4f}")
    p(f"  差异: 赔率比模型好{(total_odds_correct-total_model_correct)/n*100:+.1f}pp Brier差{(total_odds_brier-total_model_brier)/n:+.4f}")

    p(f"\n  === 按赔率区间 ===")
    odds_order = ["<1.30", "1.30-1.50", "1.50-2.00", "2.00-3.00", "3.00-5.00", ">5.00"]
    for ok in odds_order:
        os = odds_stats[ok]
        n = os["n"]
        if n < 10: continue
        m_acc = os["model_correct"]/n*100
        o_acc = os["odds_correct"]/n*100
        m_brier = os["model_brier"]/n
        o_brier = os["odds_brier"]/n
        p(f"  {ok}: n={n}")
        p(f"    赔率: acc={o_acc:.1f}% Brier={o_brier:.4f} 预测draw={os['odds_pred_draw']}")
        p(f"    模型: acc={m_acc:.1f}% Brier={m_brier:.4f} 预测draw={os['model_pred_draw']}")
        p(f"    Δacc={m_acc-o_acc:+.1f}pp ΔBrier={m_brier-o_brier:+.4f}")

    # 关键: 模型在哪些区间好于赔率？
    p(f"\n  === 总结: 模型优于赔率的区间 ===")
    for ok in odds_order:
        os = odds_stats[ok]
        n = os["n"]
        if n < 10: continue
        m_acc = os["model_correct"]/n*100
        o_acc = os["odds_correct"]/n*100
        if m_acc > o_acc:
            p(f"  {ok}: 模型好 {m_acc-o_acc:+.1f}pp (n={n})")
        else:
            p(f"  {ok}: 赔率好 {o_acc-m_acc:+.1f}pp (n={n})")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v36_model_vs_odds.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

    conn.close()


if __name__ == "__main__":
    main()