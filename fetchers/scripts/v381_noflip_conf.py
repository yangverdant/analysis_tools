"""
v3.8.1+分析: noflip+中强信号(0.3-0.5)的euro_conf分布
如果euro_conf在0.40-0.50之间, 放宽flip阈值可能有帮助
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
    p("  noflip+中强信号的euro_conf分布和改善空间")
    p("=" * 70)

    # 收集noflip+sig>=0.3的比赛
    conf_bins = defaultdict(lambda: {'n': 0, 'correct': 0, 'odds_correct': 0,
                                      'signal_home_correct': 0, 'signal_home_n': 0,
                                      'signal_away_correct': 0, 'signal_away_n': 0})

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

        # v3.8.1概率
        hp_x = hp; dp_x = dp; ap_x = ap
        for dt_flag, old_boost in DT_V34.items():
            if dt_flag in v34_flags:
                dp_x -= old_boost; hp_x += old_boost*(hp/(hp+ap)); ap_x += old_boost*(ap/(hp+ap))

        is_dt30 = 'draw_threshold_0.3' in v34_flags
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
        elif 'draw_threshold_0.28' in v34_flags:
            dp_x += 0.01; nd = hp_x + ap_x
            if nd > 0: hp_x -= 0.01*(hp_x/nd); ap_x -= 0.01*(ap_x/nd)
            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
        elif 'draw_threshold_0.26' in v34_flags:
            dp_x += 0.005; nd = hp_x + ap_x
            if nd > 0: hp_x -= 0.005*(hp_x/nd); ap_x -= 0.005*(ap_x/nd)
            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
        pred_x = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])

        # 只看noflip + sig >= 0.2
        sig_abs = abs(signal)
        if pred_x == pred_odds or sig_abs < 0.2: continue

        # euro_conf分桶
        if euro_conf < 0.35: conf_bin = "<0.35"
        elif euro_conf < 0.40: conf_bin = "0.35-0.40"
        elif euro_conf < 0.45: conf_bin = "0.40-0.45"
        elif euro_conf < 0.50: conf_bin = "0.45-0.50"
        elif euro_conf < 0.55: conf_bin = "0.50-0.55"
        elif euro_conf < 0.60: conf_bin = "0.55-0.60"
        else: conf_bin = ">=0.60"

        g = conf_bins[conf_bin]
        g['n'] += 1
        g['correct'] += (1 if pred_x == actual else 0)
        g['odds_correct'] += (1 if pred_odds == actual else 0)

        # 信号方向效果
        if signal > 0:  # 信号支持home
            g['signal_home_n'] += 1
            if actual == 'home': g['signal_home_correct'] += 1
        else:  # 信号支持away
            g['signal_away_n'] += 1
            if actual == 'away': g['signal_away_correct'] += 1

    conn.close()

    p(f"\n  === noflip + sig>=0.2 按euro_conf分布 ===")
    for bin_name in ["<0.35", "0.35-0.40", "0.40-0.45", "0.45-0.50", "0.50-0.55", "0.55-0.60", ">=0.60"]:
        g = conf_bins.get(bin_name)
        if not g or g['n'] == 0: continue
        acc = g['correct']/g['n']*100
        oacc = g['odds_correct']/g['n']*100
        gap = acc - oacc
        sh = f"home_sig={g['signal_home_correct']}/{g['signal_home_n']}={g['signal_home_correct']/g['signal_home_n']*100:.0f}%" if g['signal_home_n'] > 0 else ""
        sa = f"away_sig={g['signal_away_correct']}/{g['signal_away_n']}={g['signal_away_correct']/g['signal_away_n']*100:.0f}%" if g['signal_away_n'] > 0 else ""
        p(f"  conf {bin_name}: n={g['n']} model={acc:.1f}% odds={oacc:.1f}% gap={gap:+.1f}pp | {sh} {sa}")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v381_noflip_conf.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

if __name__ == "__main__":
    main()