"""
v3.8.1+分析: 按联赛的模型表现差异
找出模型在哪些联赛特别好/特别差, 寻找优化方向
"""
import sys, io, json, sqlite3
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

def normalize_probs(hp, dp, ap):
    total = hp + dp + ap
    if total <= 0: return 0.33, 0.33, 0.34
    return hp/total, dp/total, ap/total

DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}

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
    p("  v3.8.1 按联赛模型表现 (model vs odds)")
    p("=" * 70)

    league_stats = defaultdict(lambda: {'n': 0, 'model_correct': 0, 'odds_correct': 0})

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
        pred_model = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        od = json.loads(odds_row['data_json'])
        hp_o = float(od.get('home_value', 0) or 0)
        dp_o = float(od.get('draw_value', 0) or 0)
        ap_o = float(od.get('away_value', 0) or 0)
        pred_odds = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

        league = m['league_standard'] or 'unknown'

        # 简化联赛名
        lg = league
        if 'Premier League' in lg or 'premier_league' in lg.lower(): lg = 'EPL'
        elif 'La Liga' in lg or 'la_liga' in lg.lower(): lg = 'LaLiga'
        elif 'Serie A' in lg or 'serie_a' in lg.lower(): lg = 'SerieA'
        elif 'Bundesliga' in lg or 'bundesliga' in lg.lower(): lg = 'Buli'
        elif 'Ligue 1' in lg or 'ligue_1' in lg.lower(): lg = 'Ligue1'
        elif 'Champions League' in lg or 'champions_league' in lg.lower(): lg = 'UCL'
        elif 'Europa League' in lg or 'europa_league' in lg.lower(): lg = 'UEL'
        elif 'liga_2' in lg.lower() or 'La Liga 2' in lg: lg = 'LaLiga2'
        elif 'serie_b' in lg.lower(): lg = 'SerieB'
        elif 'ligue_2' in lg.lower(): lg = 'Ligue2'
        elif '2_bundesliga' in lg.lower(): lg = 'Buli2'
        elif 'Libertadores' in lg or 'libertadores' in lg.lower(): lg = 'Libert'
        elif 'EFL' in lg or 'championship' in lg.lower(): lg = 'EFL'

        league_stats[lg]['n'] += 1
        league_stats[lg]['model_correct'] += (1 if pred_model == actual else 0)
        league_stats[lg]['odds_correct'] += (1 if pred_odds == actual else 0)

    conn.close()

    # 排序: 按gap(model-odds)
    results = []
    for lg, g in league_stats.items():
        if g['n'] < 50: continue
        m_acc = g['model_correct'] / g['n'] * 100
        o_acc = g['odds_correct'] / g['n'] * 100
        gap = m_acc - o_acc
        results.append((lg, g['n'], m_acc, o_acc, gap))

    results.sort(key=lambda x: x[4])

    p(f"\n  === 模型最差的联赛 (gap最小) ===")
    for lg, n, m_acc, o_acc, gap in results[:10]:
        p(f"  {lg:12s} n={n:4d} model={m_acc:.1f}% odds={o_acc:.1f}% gap={gap:+.1f}pp")

    p(f"\n  === 模型最好的联赛 (gap最大) ===")
    for lg, n, m_acc, o_acc, gap in results[-10:]:
        p(f"  {lg:12s} n={n:4d} model={m_acc:.1f}% odds={o_acc:.1f}% gap={gap:+.1f}pp")

    OUTPUT = 'd:/football_tools/fetchers/scripts/v381_league_analysis.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

if __name__ == "__main__":
    main()
