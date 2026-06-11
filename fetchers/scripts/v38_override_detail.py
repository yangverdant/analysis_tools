"""
v3.8诊断: 信号覆盖在2-3区间的触发频率和效果
1. flip(主→客或客→主)的触发条件: euro_conf<0.45 且 |signal|>0.15
2. draw_boost触发条件: euro_conf<0.45 且 |signal|>0.02 且 draw_prob>=0.30
3. 这些条件在2-3区间分别触发了多少场？改对/改错比例？
4. 按odds子区间细分
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
    p("  v3.8诊断: 信号覆盖在2-3区间触发频率和效果")
    p("=" * 70)

    # 分类统计
    categories = {
        "flip_H_to_A": {"n": 0, "model_ok": 0, "odds_ok": 0, "examples": []},
        "flip_A_to_H": {"n": 0, "model_ok": 0, "odds_ok": 0, "examples": []},
        "draw_boost_H": {"n": 0, "model_ok": 0, "odds_ok": 0, "examples": []},
        "draw_boost_A": {"n": 0, "model_ok": 0, "odds_ok": 0, "examples": []},
        "no_override": {"n": 0, "model_ok": 0, "odds_ok": 0},
    }

    # 按odds子区间
    odds_cat = defaultdict(lambda: {"n": 0, "model_ok": 0, "odds_ok": 0,
                                      "flip_n": 0, "flip_model_ok": 0, "flip_odds_ok": 0,
                                      "draw_n": 0, "draw_model_ok": 0, "draw_odds_ok": 0})

    # 按信号强度细分flip效果
    flip_by_sig = defaultdict(lambda: {"n": 0, "model_ok": 0, "odds_ok": 0})

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
        signal = model_data.get('signal_value', 0)
        pred_m = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_m, 'draw': dp_m, 'away': ap_m}[x])

        # 赔率
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
        euro_conf = max(hp_o, dp_o, ap_o)

        # 判断信号覆盖类型
        cat = "no_override"
        if euro_conf < 0.45:
            if pred_o == 'home' and signal < -0.15:
                cat = "flip_H_to_A"
            elif pred_o == 'away' and signal > 0.15:
                cat = "flip_A_to_H"
            elif pred_o == 'home' and signal < -0.02 and dp_o >= 0.30:
                cat = "draw_boost_H"
            elif pred_o == 'away' and signal > 0.02 and dp_o >= 0.30:
                cat = "draw_boost_A"

        s = categories[cat]
        s["n"] += 1
        if pred_m == actual: s["model_ok"] += 1
        if pred_o == actual: s["odds_ok"] += 1
        if cat != "no_override" and len(s["examples"]) < 15:
            s["examples"].append({
                'date': m['date'], 'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'], 'odds_h': odds_h,
                'score': f"{m['home_score']}-{m['away_score']}", 'actual': actual,
                'pred_o': pred_o, 'pred_m': pred_m, 'signal': signal,
                'euro_conf': euro_conf, 'dp_o': dp_o,
            })

        # 按odds子区间
        if odds_h < 2.2:
            rng = "2.0-2.2"
        elif odds_h < 2.5:
            rng = "2.2-2.5"
        else:
            rng = "2.5-3.0"

        oc = odds_cat[rng]
        oc["n"] += 1
        if pred_m == actual: oc["model_ok"] += 1
        if pred_o == actual: oc["odds_ok"] += 1
        if cat in ("flip_H_to_A", "flip_A_to_H"):
            oc["flip_n"] += 1
            if pred_m == actual: oc["flip_model_ok"] += 1
            if pred_o == actual: oc["flip_odds_ok"] += 1
        if cat in ("draw_boost_H", "draw_boost_A"):
            oc["draw_n"] += 1
            if pred_m == actual: oc["draw_model_ok"] += 1
            if pred_o == actual: oc["draw_odds_ok"] += 1

        # flip按信号强度
        if cat in ("flip_H_to_A", "flip_A_to_H"):
            sig_abs = abs(signal)
            if sig_abs < 0.2:
                sig_key = "0.15-0.20"
            elif sig_abs < 0.3:
                sig_key = "0.20-0.30"
            elif sig_abs < 0.5:
                sig_key = "0.30-0.50"
            else:
                sig_key = ">0.50"
            fb = flip_by_sig[sig_key]
            fb["n"] += 1
            if pred_m == actual: fb["model_ok"] += 1
            if pred_o == actual: fb["odds_ok"] += 1

    conn.close()

    # 输出
    p(f"\n  === 信号覆盖类型统计 (2-3区间) ===")
    for cat in ["flip_H_to_A", "flip_A_to_H", "draw_boost_H", "draw_boost_A", "no_override"]:
        s = categories[cat]
        n = s["n"]
        if n == 0: continue
        p(f"\n  {cat}: n={n}")
        p(f"  模型argmax: {s['model_ok']}/{n}={s['model_ok']/n*100:.1f}%")
        p(f"  赔率argmax: {s['odds_ok']}/{n}={s['odds_ok']/n*100:.1f}%")
        p(f"  差: {(s['model_ok']-s['odds_ok'])/n*100:+.1f}pp")

        if s.get("examples"):
            p(f"  示例:")
            for ex in s["examples"][:10]:
                p(f"    {ex['date']} {ex['home']} vs {ex['away']} ({ex['league']}) odds_h={ex['odds_h']:.2f}")
                p(f"      score={ex['score']} actual={ex['actual']} 赔率→{ex['pred_o']} 模型→{ex['pred_m']}")
                p(f"      signal={ex['signal']:.4f} euro_conf={ex['euro_conf']:.2f} draw_prob={ex['dp_o']:.3f}")

    p(f"\n  === flip按信号强度 ===")
    for sig_key in ["0.15-0.20", "0.20-0.30", "0.30-0.50", ">0.50"]:
        fb = flip_by_sig[sig_key]
        n = fb["n"]
        if n == 0: continue
        p(f"  |signal|{sig_key}: n={n} 模型={fb['model_ok']/n*100:.1f}% 赔率={fb['odds_ok']/n*100:.1f}%")

    p(f"\n  === 按odds子区间 ===")
    for rng in ["2.0-2.2", "2.2-2.5", "2.5-3.0"]:
        oc = odds_cat[rng]
        n = oc["n"]
        if n == 0: continue
        p(f"  odds {rng}: n={n} 模型={oc['model_ok']/n*100:.1f}% 赔率={oc['odds_ok']/n*100:.1f}%")
        if oc["flip_n"] > 0:
            p(f"    flip: n={oc['flip_n']} 模型={oc['flip_model_ok']/oc['flip_n']*100:.1f}% 赔率={oc['flip_odds_ok']/oc['flip_n']*100:.1f}%")
        if oc["draw_n"] > 0:
            p(f"    draw_boost: n={oc['draw_n']} 模型={oc['draw_model_ok']/oc['draw_n']*100:.1f}% 赔率={oc['draw_odds_ok']/oc['draw_n']*100:.1f}%")

    p(f"\n{'=' * 70}")
    p("  诊断完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_override_detail.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()