"""
全局分析: signal方向的准确率 vs euro_conf
如果信号方向在任何euro_conf水平都比赔率更准确, 可以放宽flip阈值
"""
import sys, io, json, sqlite3
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

matches = conn.execute("""
    SELECT m.match_key, m.date, m.home_team, m.away_team,
           m.home_score, m.away_score
    FROM matches m
    WHERE m.status='finished' AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
    AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                AND md.source='model' AND md.data_type='model:enhanced_linear')
    AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                AND md.source='factor' AND md.data_type='factor:euro_odds')
    ORDER BY m.date
""").fetchall()

# 核心问题: 信号方向(home/away)在不同euro_conf水平下的准确率
# vs 赔率方向(home/away)的准确率

bins = defaultdict(lambda: {'n': 0, 'sig_dir_correct': 0, 'odds_dir_correct': 0',
                              'sig_home_n': 0, 'sig_home_correct': 0,
                              'sig_away_n': 0, 'sig_away_correct': 0,
                              'odds_home_n': 0, 'odds_home_correct': 0,
                              'odds_away_n': 0, 'odds_away_correct': 0})

for m in matches:
    mk = m['match_key']
    actual = 'home' if m['home_score'] > m['away_score'] else \
             'draw' if m['home_score'] == m['away_score'] else 'away'

    model_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
        (mk,)).fetchone()
    md = json.loads(model_row['data_json'])
    signal = md.get('signal_value', 0)
    euro_conf = md.get('euro_confidence', 0.5)

    odds_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
        (mk,)).fetchone()
    od = json.loads(odds_row['data_json'])
    hp_o = float(od.get('home_value', 0) or 0)
    dp_o = float(od.get('draw_value', 0) or 0)
    ap_o = float(od.get('away_value', 0) or 0)

    # 信号方向(只看非平局信号)
    sig_dir = 'home' if signal > 0.1 else ('away' if signal < -0.1 else 'neutral')
    # 赔率方向
    odds_dir = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_o, 'draw': dp_o, 'away': ap_o}[x])

    # euro_conf分桶
    if euro_conf < 0.40: bin = "conf<0.40"
    elif euro_conf < 0.50: bin = "conf0.40-0.50"
    elif euro_conf < 0.55: bin = "conf0.50-0.55"
    elif euro_conf < 0.60: bin = "conf0.55-0.60"
    elif euro_conf < 0.65: bin = "conf0.60-0.65"
    else: bin = "conf>=0.65"

    g = bins[bin]
    g['n'] += 1

    # 信号方向准确率(排除draw)
    if sig_dir == 'home':
        g['sig_home_n'] += 1
        if actual == 'home': g['sig_home_correct'] += 1
    elif sig_dir == 'away':
        g['sig_away_n'] += 1
        if actual == 'away': g['sig_away_correct'] += 1

    # 赔率方向准确率(排除draw)
    if odds_dir == 'home':
        g['odds_home_n'] += 1
        if actual == 'home': g['odds_home_correct'] += 1
    elif odds_dir == 'away':
        g['odds_away_n'] += 1
        if actual == 'away': g['odds_away_correct'] += 1

    # 信号和赔率方向不一致时
    if sig_dir != 'neutral' and sig_dir != odds_dir:
        g['sig_dir_correct'] += (1 if (sig_dir == 'home' and actual == 'home') or (sig_dir == 'away' and actual == 'away') else 0)
        g['odds_dir_correct'] += (1 if (odds_dir == 'home' and actual == 'home') or (odds_dir == 'away' and actual == 'away') else 0)

conn.close()

print("=" * 70)
print("  信号方向 vs 赔率方向 准确率对比(按euro_conf)")
print("=" * 70)

for bin_name in ["conf<0.40", "conf0.40-0.50", "conf0.50-0.55", "conf0.55-0.60", "conf0.60-0.65", "conf>=0.65"]:
    g = bins[bin_name]
    if g['n'] == 0: continue
    sig_h = g['sig_home_correct']/g['sig_home_n']*100 if g['sig_home_n'] > 0 else 0
    sig_a = g['sig_away_correct']/g['sig_away_n']*100 if g['sig_away_n'] > 0 else 0
    odds_h = g['odds_home_correct']/g['odds_home_n']*100 if g['odds_home_n'] > 0 else 0
    odds_a = g['odds_away_correct']/g['odds_away_n']*100 if g['odds_away_n'] > 0 else 0
    conflict_n = g['sig_dir_correct'] + g['odds_dir_correct']
    sig_win = g['sig_dir_correct']/conflict_n*100 if conflict_n > 0 else 0

    print(f"\n  {bin_name} (n={g['n']})")
    print(f"    信号home准确率: {sig_h:.1f}% ({g['sig_home_correct']}/{g['sig_home_n']})")
    print(f"    赔率home准确率: {odds_h:.1f}% ({g['odds_home_correct']}/{g['odds_home_n']})")
    print(f"    信号away准确率: {sig_a:.1f}% ({g['sig_away_correct']}/{g['sig_away_n']})")
    print(f"    赔率away准确率: {odds_a:.1f}% ({g['odds_away_correct']}/{g['odds_away_n']})")
    print(f"    冲突时信号赢: {sig_win:.1f}% ({g['sig_dir_correct']}/{conflict_n})")