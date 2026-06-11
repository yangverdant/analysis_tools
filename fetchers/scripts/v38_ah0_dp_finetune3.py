"""
v3.8+精调v3: 三档dp reduce (flags判断dt30, 修复子群统计)
dt30+AH0 → base + ah0_extra reduce
dt30+AH≠0 或 dt30无AH → base reduce
"""
import sys, io, json, sqlite3, math
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

def normalize_probs(hp, dp, ap):
    total = hp + dp + ap
    if total <= 0:
        return 0.33, 0.33, 0.34
    return hp/total, dp/total, ap/total

DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}
DT_V38 = {0.30: 0.01, 0.28: 0.01, 0.26: 0.005}

def get_ah_type(conn, mk):
    ah_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:asian_handicap'",
        (mk,)).fetchone()
    if not ah_row:
        return 'no_data'
    ah_data = json.loads(ah_row['data_json'])
    raw = ah_data.get('raw', {})
    hc = raw.get('closing_handicap', None)
    if hc is None:
        hc = raw.get('handicap', None)
    if hc is None:
        hc = ah_data.get('handicap_value', None)
    if hc is None:
        return 'no_data'
    try:
        val = float(hc)
        if abs(val) < 0.01:
            return 'ah0'
        return 'ah_non0'
    except (ValueError, TypeError):
        return 'no_data'

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
    p("  v3.8+精调: 三档dp reduce (dt30+AH0 / dt30+AH≠0 / dt30无AH)")
    p("=" * 70)

    # 预加载AH数据
    ah_types = {}
    for m in matches:
        ah_types[m['match_key']] = get_ah_type(conn, m['match_key'])

    # dt30分布
    dt30_dist = defaultdict(int)
    for m in matches:
        mk = m['match_key']
        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)).fetchone()
        model_data = json.loads(model_row['data_json'])
        if 'draw_threshold_0.3' in model_data.get('scenario_flags', []):
            dt30_dist[ah_types[mk]] += 1
    p(f"\n  dt30子群: " + " | ".join(f"{k}={v}" for k, v in sorted(dt30_dist.items())))

    strategies = [
        {"name": "统一0.02",          "base": 0.02, "ah0": 0.00},
        {"name": "base0.01+ah0.01",  "base": 0.01, "ah0": 0.01},
        {"name": "base0.01+ah0.02",  "base": 0.01, "ah0": 0.02},
        {"name": "base0.01+ah0.03",  "base": 0.01, "ah0": 0.03},
        {"name": "base0.015+ah0.01", "base": 0.015, "ah0": 0.01},
        {"name": "base0.015+ah0.02", "base": 0.015, "ah0": 0.02},
        {"name": "base0.015+ah0.03", "base": 0.015, "ah0": 0.03},
        {"name": "base0.02+ah0.01",  "base": 0.02, "ah0": 0.01},
        {"name": "base0.02+ah0.02",  "base": 0.02, "ah0": 0.02},
        {"name": "base0.02+ah0.03",  "base": 0.02, "ah0": 0.03},
    ]

    for strat in strategies:
        base = strat['base']
        ah0_extra = strat['ah0']

        total_n = 0; correct = 0; brier = 0.0; net_gain = 0
        subgroups = defaultdict(lambda: {'n': 0, 'correct': 0})

        for m in matches:
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
            v34_flags = model_data.get('scenario_flags', [])
            pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

            odds_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
                (mk,)).fetchone()
            odds_data = json.loads(odds_row['data_json'])
            raw_odds = odds_data.get('raw', {})
            odds_h = float(raw_odds.get('avg_home_odds', 0) or raw_odds.get('closing_avg_home_odds', 0) or 0)

            hp_x = hp; dp_x = dp; ap_x = ap

            # 去掉v3.4 dt
            for dt_flag, old_boost in DT_V34.items():
                if dt_flag in v34_flags:
                    dp_x -= old_boost
                    hp_x += old_boost * (hp / (hp + ap))
                    ap_x += old_boost * (ap / (hp + ap))

            # v3.8 dt
            is_dt30 = 'draw_threshold_0.3' in v34_flags
            is_dt28 = 'draw_threshold_0.28' in v34_flags and not is_dt30
            is_dt26 = 'draw_threshold_0.26' in v34_flags and not is_dt30 and not is_dt28

            dt30_ah_type = None
            if is_dt30:
                dp_x += 0.01
                non_draw = hp_x + ap_x
                if non_draw > 0:
                    hp_x -= 0.01 * (hp_x / non_draw)
                    ap_x -= 0.01 * (ap_x / non_draw)
                hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
                # 分档reduce
                dt30_ah_type = ah_types.get(mk, 'no_data')
                if dt30_ah_type == 'ah0':
                    reduce_val = base + ah0_extra
                else:
                    reduce_val = base
                if reduce_val > 0:
                    dp_x -= reduce_val
                    non_draw = hp_x + ap_x
                    if non_draw > 0:
                        hp_x += reduce_val * (hp_x / non_draw)
                        ap_x += reduce_val * (ap_x / non_draw)
                    hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
            elif is_dt28:
                dp_x += 0.01
                non_draw = hp_x + ap_x
                if non_draw > 0:
                    hp_x -= 0.01 * (hp_x / non_draw)
                    ap_x -= 0.01 * (ap_x / non_draw)
                hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
            elif is_dt26:
                dp_x += 0.005
                non_draw = hp_x + ap_x
                if non_draw > 0:
                    hp_x -= 0.005 * (hp_x / non_draw)
                    ap_x -= 0.005 * (ap_x / non_draw)
                hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)

            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
            pred_x = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])

            correct += (1 if pred_x == actual else 0)
            if actual == 'home':   brier += (hp_x-1)**2 + dp_x**2 + ap_x**2
            elif actual == 'draw': brier += hp_x**2 + (dp_x-1)**2 + ap_x**2
            else:                  brier += hp_x**2 + dp_x**2 + (ap_x-1)**2
            total_n += 1

            if pred_x != pred_v34:
                if pred_x == actual: net_gain += 1
                elif pred_v34 == actual: net_gain -= 1

            # 子群(在pred_x之后)
            if is_dt30:
                sg_key = f"dt30_{dt30_ah_type}"
                subgroups[sg_key]['n'] += 1
                if pred_x == actual: subgroups[sg_key]['correct'] += 1

            if 2.0 <= odds_h < 3.0:
                subgroups['odds_2_3']['n'] += 1
                if pred_x == actual: subgroups['odds_2_3']['correct'] += 1

        sg_str = " | ".join(
            f"{k}={v['correct']}/{v['n']}={v['correct']/v['n']*100:.1f}%"
            for k, v in sorted(subgroups.items()) if v['n'] > 0
        )
        p(f"  {strat['name']:20s}: argmax={correct/total_n*100:.2f}% Brier={brier/total_n:.4f} net={net_gain:+d} | {sg_str}")

    p(f"\n{'=' * 70}")
    p("  实验完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_ah0_dp_finetune3.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

if __name__ == "__main__":
    main()
