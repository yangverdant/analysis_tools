"""
v3.8诊断: 信号覆盖(SIGNAL_OVERRIDE)在2-3区间的问题
目标：找出模型在2-3区间改错的核心原因
1. 信号覆盖触发了多少场？改对/改错比例？
2. 信号偏draw触发了多少场？改对/改错比例？
3. 信号覆盖的flip_strength=0.15是否过大？
4. 不同信号强度下的实际翻转正确率
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
    p("  v3.8诊断: 信号覆盖在2-3区间的影响")
    p("=" * 70)
    p(f"  总比赛数: {len(matches)}")

    # 统计信号覆盖效果
    # 分类：
    # - SIGNAL_OVERRIDE: 赔率说主胜但信号<−0.15（或反之）→翻转主客方向
    # - SIGNAL_DRAW: 赔率说主胜但信号<−0.02且draw≥0.30 →偏draw
    # - 无覆盖: 其他

    override_stats = {
        "flip_home_to_away": {"n": 0, "model_ok": 0, "odds_ok": 0,
                               "model_correct": 0, "model_wrong": 0,
                               "examples": []},
        "flip_away_to_home": {"n": 0, "model_ok": 0, "odds_ok": 0,
                               "model_correct": 0, "model_wrong": 0,
                               "examples": []},
        "draw_boost": {"n": 0, "model_ok": 0, "odds_ok": 0,
                        "model_correct": 0, "model_wrong": 0,
                        "examples": []},
        "no_override": {"n": 0, "model_ok": 0, "odds_ok": 0,
                        "model_correct": 0, "model_wrong": 0},
    }

    # 按信号强度细分flip正确率
    flip_by_signal = defaultdict(lambda: {"n": 0, "model_ok": 0, "odds_ok": 0})

    # 按odds区间细分
    by_odds = defaultdict(lambda: {"n": 0, "flip_n": 0, "flip_ok": 0,
                                    "draw_n": 0, "draw_ok": 0,
                                    "model_ok": 0, "odds_ok": 0})

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

        pred_m = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_m, 'draw': dp_m, 'away': ap_m}[x])
        pred_o = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])
        euro_conf = max(hp_o, dp_o, ap_o)

        if odds_h <= 0: continue
        in_2_3 = 2.0 <= odds_h < 3.0

        if not in_2_3: continue

        # 判断信号覆盖类型
        # 需要推断: 赔率方向和信号方向
        if euro_conf < 0.45:  # 赔率信心低时才触发
            if pred_o == 'home' and signal < -0.15:
                # flip: 欧赔→主胜，信号→客胜
                cat = "flip_home_to_away"
            elif pred_o == 'away' and signal > 0.15:
                # flip: 欧赔→客胜，信号→主胜
                cat = "flip_away_to_home"
            elif pred_o == 'home' and signal < -0.02 and dp_o >= 0.30:
                # draw boost
                cat = "draw_boost"
            elif pred_o == 'away' and signal > 0.02 and dp_o >= 0.30:
                cat = "draw_boost"
            else:
                cat = "no_override"
        else:
            cat = "no_override"

        s = override_stats[cat]
        s["n"] += 1
        if pred_m == actual: s["model_ok"] += 1
        if pred_o == actual: s["odds_ok"] += 1
        if pred_o != pred_m:
            if pred_m == actual: s["model_correct"] += 1
            else: s["model_wrong"] += 1

        if cat != "no_override" and len(s["examples"]) < 20:
            s["examples"].append({
                'date': m['date'], 'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'], 'odds_h': odds_h,
                'score': f"{m['home_score']}-{m['away_score']}", 'actual': actual,
                'pred_o': pred_o, 'pred_m': pred_m,
                'signal': signal, 'euro_conf': euro_conf,
                'hp_m': hp_m, 'dp_m': dp_m, 'ap_m': ap_m,
            })

        # flip按信号强度
        if cat in ("flip_home_to_away", "flip_away_to_home"):
            sig_abs = abs(signal)
            if sig_abs < 0.2:
                sig_key = "<0.2"
            elif sig_abs < 0.3:
                sig_key = "0.2-0.3"
            elif sig_abs < 0.5:
                sig_key = "0.3-0.5"
            else:
                sig_key = ">0.5"
            fb = flip_by_signal[sig_key]
            fb["n"] += 1
            if pred_m == actual: fb["model_ok"] += 1
            if pred_o == actual: fb["odds_ok"] += 1

        # 按odds区间
        if odds_h < 2.2:
            rng = "2.0-2.2"
        elif odds_h < 2.5:
            rng = "2.2-2.5"
        else:
            rng = "2.5-3.0"

        bo = by_odds[rng]
        bo["n"] += 1
        if pred_m == actual: bo["model_ok"] += 1
        if pred_o == actual: bo["odds_ok"] += 1
        if cat in ("flip_home_to_away", "flip_away_to_home"):
            bo["flip_n"] += 1
            if pred_m == actual: bo["flip_ok"] += 1
        if cat == "draw_boost":
            bo["draw_n"] += 1
            if pred_m == actual: bo["draw_ok"] += 1

    conn.close()

    # 输出
    p(f"\n  === 信号覆盖类型统计 (2-3区间) ===")
    for cat in ["flip_home_to_away", "flip_away_to_home", "draw_boost", "no_override"]:
        s = override_stats[cat]
        n = s["n"]
        if n == 0: continue
        p(f"\n  {cat}: n={n}")
        p(f"  模型argmax: {s['model_ok']}/{n}={s['model_ok']/n*100:.1f}%")
        p(f"  赔率argmax: {s['odds_ok']}/{n}={s['odds_ok']/n*100:.1f}%")
        if s["model_correct"] + s["model_wrong"] > 0:
            p(f"  模型改赔率: 改对{s['model_correct']} 改错{s['model_wrong']} 净{s['model_correct']-s['model_wrong']:+d}")

        examples = s.get("examples", [])
        if examples:
            p(f"  示例:")
            for ex in examples[:10]:
                p(f"    {ex['date']} {ex['home']} vs {ex['away']} ({ex['league']}) odds_h={ex['odds_h']:.2f}")
                p(f"      score={ex['score']} actual={ex['actual']} 赔率→{ex['pred_o']} 模型→{ex['pred_m']}")
                p(f"      signal={ex['signal']:.4f} euro_conf={ex['euro_conf']:.2f}")
                p(f"      模型: h={ex['hp_m']*100:.1f}% d={ex['dp_m']*100:.1f}% a={ex['ap_m']*100:.1f}%")

    p(f"\n  === flip按信号强度 ===")
    for sig_key in ["<0.2", "0.2-0.3", "0.3-0.5", ">0.5"]:
        fb = flip_by_signal[sig_key]
        n = fb["n"]
        if n == 0: continue
        p(f"  |signal|{sig_key}: n={n} 模型={fb['model_ok']/n*100:.1f}% 赔率={fb['odds_ok']/n*100:.1f}%")

    p(f"\n  === 按odds子区间 ===")
    for rng in ["2.0-2.2", "2.2-2.5", "2.5-3.0"]:
        bo = by_odds[rng]
        n = bo["n"]
        if n == 0: continue
        p(f"  odds {rng}: n={n}")
        p(f"  模型={bo['model_ok']/n*100:.1f}% 赔率={bo['odds_ok']/n*100:.1f}%")
        if bo["flip_n"] > 0:
            p(f"  flip: n={bo['flip_n']} 改对{bo['flip_ok']} 改错{bo['flip_n']-bo['flip_ok']}")
        if bo["draw_n"] > 0:
            p(f"  draw_boost: n={bo['draw_n']} 改对{bo['draw_ok']} 改错{bo['draw_n']-bo['draw_ok']}")

    p(f"\n{'=' * 70}")
    p("  诊断完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_override_diagnosis.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()