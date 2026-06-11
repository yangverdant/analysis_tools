"""
v3.8.1+分析: signal override的实际效果和改进空间
flip(信号翻转) vs no_flip(无翻转)的详细对比
重点: 哪些signal flip是对的？哪些是错的？
"""
import sys, io, json, sqlite3, math
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

def normalize_probs(hp, dp, ap):
    total = hp + dp + ap
    if total <= 0: return 0.33, 0.33, 0.34
    return hp/total, dp/total, ap/total

DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}
DT_V38 = {0.30: 0.01, 0.28: 0.01, 0.26: 0.005}
DT30_BASE_DP_REDUCE = 0.01
DT30_AH0_EXTRA_DP_REDUCE = 0.02

def get_ah_type(conn, mk):
    ah_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
        (mk,)).fetchone()
    if not ah_row: return 'no_data'
    ah_data = json.loads(ah_row['data_json'])
    raw = ah_data.get('raw', {})
    hc = raw.get('closing_handicap', None) or raw.get('handicap', None) or ah_data.get('handicap_value', None)
    if hc is None: return 'no_data'
    try:
        val = float(hc)
        return 'ah0' if abs(val) < 0.01 else 'ah_non0'
    except: return 'no_data'

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
    def p(s=""): lines.append(s)

    p("=" * 70)
    p("  v3.8.1 signal override效果分析")
    p("=" * 70)

    # 分6组: signal方向 × 是否触发signal override
    # signal override: 当euro_conf<0.45且signal足够强时翻转或boost
    groups = defaultdict(lambda: {'n': 0, 'correct': 0, 'odds_correct': 0})

    # 也收集改错案例
    override_patterns = defaultdict(int)  # "override类型 → 实际结果"
    no_override_patterns = defaultdict(int)

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        md = json.loads(model_row['data_json'])
        hp = md.get('home_win_prob', 0.33); dp = md.get('draw_prob', 0.33); ap = md.get('away_win_prob', 0.34)
        v34_flags = md.get('scenario_flags', [])
        signal = md.get('signal_value', 0)
        euro_conf = md.get('euro_confidence', 0.5)
        signal_strength = md.get('signal_strength', 'none')
        pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        od = json.loads(odds_row['data_json'])
        hp_o = float(od.get('home_value', 0) or 0)
        dp_o = float(od.get('draw_value', 0) or 0)
        ap_o = float(od.get('away_value', 0) or 0)
        raw = od.get('raw', {})
        odds_h = float(raw.get('avg_home_odds', 0) or raw.get('closing_avg_home_odds', 0) or 0)
        pred_odds = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

        # v3.8.1概率(简化: 只做dt调整)
        hp_x = hp; dp_x = dp; ap_x = ap
        for dt_flag, old_boost in DT_V34.items():
            if dt_flag in v34_flags:
                dp_x -= old_boost; hp_x += old_boost*(hp/(hp+ap)); ap_x += old_boost*(ap/(hp+ap))

        is_dt30 = 'draw_threshold_0.3' in v34_flags
        is_dt28 = 'draw_threshold_0.28' in v34_flags and not is_dt30
        is_dt26 = 'draw_threshold_0.26' in v34_flags and not is_dt30 and not is_dt28

        if is_dt30:
            dp_x += 0.01; nd = hp_x + ap_x
            if nd > 0: hp_x -= 0.01*(hp_x/nd); ap_x -= 0.01*(ap_x/nd)
            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
            ah_type = get_ah_type(conn, mk)
            rv = DT30_BASE_DP_REDUCE + (DT30_AH0_EXTRA_DP_REDUCE if ah_type == 'ah0' else 0)
            if rv > 0:
                dp_x -= rv; nd = hp_x + ap_x
                if nd > 0: hp_x += rv*(hp_x/nd); ap_x += rv*(ap_x/nd)
                hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
        elif is_dt28:
            dp_x += 0.01; nd = hp_x + ap_x
            if nd > 0: hp_x -= 0.01*(hp_x/nd); ap_x -= 0.01*(ap_x/nd)
            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
        elif is_dt26:
            dp_x += 0.005; nd = hp_x + ap_x
            if nd > 0: hp_x -= 0.005*(hp_x/nd); ap_x -= 0.005*(ap_x/nd)
            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
        pred_x = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])

        # 分类: 是否触发signal override?
        # v3.4中signal override的标志: 当pred_v34和pred_odds不同时(模型翻转了赔率方向)
        is_flipped = pred_x != pred_odds

        # 信号方向
        sig_dir = 'home' if signal > 0.1 else ('away' if signal < -0.1 else 'neutral')
        sig_abs = abs(signal)

        # 翻转类型
        if is_flipped:
            override_type = f"{pred_odds}→{pred_x}"
            override_patterns[f"{override_type}|{actual}"] += 1
            key = f"flip_{sig_dir}"
        else:
            no_override_patterns[f"{pred_x}|{actual}"] += 1
            key = f"noflip_{sig_dir}"

        groups[key]['n'] += 1
        groups[key]['correct'] += (1 if pred_x == actual else 0)
        groups[key]['odds_correct'] += (1 if pred_odds == actual else 0)

        # 也按signal强度分组
        for sig_level in [
            (f"sig<0.1", sig_abs < 0.1),
            (f"sig0.1-0.3", 0.1 <= sig_abs < 0.3),
            (f"sig0.3-0.5", 0.3 <= sig_abs < 0.5),
            (f"sig>=0.5", sig_abs >= 0.5),
        ]:
            if sig_level[1]:
                groups[f"{'flip' if is_flipped else 'noflip'}_{sig_level[0]}"]['n'] += 1
                groups[f"{'flip' if is_flipped else 'noflip'}_{sig_level[0]}"]['correct'] += (1 if pred_x == actual else 0)
                groups[f"{'flip' if is_flipped else 'noflip'}_{sig_level[0]}"]['odds_correct'] += (1 if pred_odds == actual else 0)

    conn.close()

    p(f"\n  === 按signal方向 × flip分类 ===")
    for key, g in sorted(groups.items()):
        if g['n'] == 0: continue
        acc = g['correct']/g['n']*100
        oacc = g['odds_correct']/g['n']*100
        gap = acc - oacc
        p(f"  [{key}] n={g['n']} model={acc:.1f}% odds={oacc:.1f}% gap={gap:+.1f}pp")

    p(f"\n  === flip改错模式 ===")
    for pat, cnt in sorted(override_patterns.items(), key=lambda x: x[1], reverse=True)[:20]:
        p(f"  {pat}: {cnt}")

    p(f"\n  === noflip改错模式 ===")
    for pat, cnt in sorted(no_override_patterns.items(), key=lambda x: x[1], reverse=True)[:10]:
        p(f"  {pat}: {cnt}")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v381_signal_override.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

if __name__ == "__main__":
    main()
