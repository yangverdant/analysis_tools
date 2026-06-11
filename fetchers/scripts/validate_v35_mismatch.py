"""
v3.5动机不对称规则深入分析
关键问题: 16场动机不对称比赛中，13场主胜，但规则是削弱主胜概率的
需要按月份/赔率/动机类别细分，找到真正需要调整的子集
"""
import sys, io, json, sqlite3
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 获取所有有动机数据的比赛
    matches = conn.execute("""
        SELECT m.match_key, m.date, m.home_team, m.away_team,
               m.league_standard, m.home_score, m.away_score
        FROM matches m
        WHERE m.status='finished' AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='factor' AND md.data_type='factor:motivation'
                    AND json_extract(md.data_json, '$.confidence') > 0)
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='factor' AND md.data_type='factor:euro_odds')
        ORDER BY m.date
    """).fetchall()

    lines = []
    def p(s=""):
        lines.append(s)

    p("=" * 70)
    p("  动机不对称深入分析 — 按类别/赔率/月份交叉验证")
    p("=" * 70)
    p(f"  有动机+赔率数据的比赛: {len(matches)}")

    # 按(home_cat, away_cat)组合统计所有比赛
    combo_stats = defaultdict(lambda: {"n": 0, "home": 0, "draw": 0, "away": 0,
                                        "odds_list": [], "month_list": []})

    # 低赔率+动机不对称组合的详细分析
    mismatch_candidates = []

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'
        match_month = int(m['date'][5:7]) if len(m['date']) >= 7 else 0

        # 加载动机
        mot_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:motivation'",
            (mk,)
        ).fetchone()
        mot_f = json.loads(mot_row['data_json'])
        mot_diff = mot_f.get('diff', 0)
        mot_raw = mot_f.get('raw', {})
        home_cat = mot_raw.get('home_category', '') or mot_f.get('home_category', '')
        away_cat = mot_raw.get('away_category', '') or mot_f.get('away_category', '')

        # 加载赔率
        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)
        ).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        raw_odds = odds_data.get('raw', {})
        odds_h = float(raw_odds.get('avg_home_odds', 0) or raw_odds.get('closing_avg_home_odds', 0) or 0)

        if not home_cat or not away_cat:
            continue

        # 统计所有组合
        combo = (home_cat, away_cat)
        combo_stats[combo]["n"] += 1
        combo_stats[combo][actual] += 1
        if odds_h > 0:
            combo_stats[combo]["odds_list"].append(odds_h)
        combo_stats[combo]["month_list"].append(match_month)

        # 动机不对称候选: home_dead/mid + away_desperate + diff<-1.0 + odds<=1.50
        is_home_dead = home_cat in ("dead_rubber", "mid_table")
        is_away_desperate = away_cat in ("relegation", "relegation_battle", "title_race", "european")

        if is_home_dead and is_away_desperate and mot_diff < -1.0:
            mismatch_candidates.append({
                'mk': mk, 'date': m['date'],
                'home': m['home_team'], 'away': m['away_team'],
                'league': m['league_standard'],
                'odds_h': odds_h, 'actual': actual,
                'score': f"{m['home_score']}-{m['away_score']}",
                'home_cat': home_cat, 'away_cat': away_cat,
                'mot_diff': mot_diff, 'month': match_month,
            })

    # === 1. 所有动机类别组合的胜率 ===
    p(f"\n  === 1. 动机类别组合胜率(所有赔率) ===")
    interesting_combos = []
    for (hc, ac), stats in sorted(combo_stats.items()):
        n = stats["n"]
        if n < 5:
            continue
        home_pct = stats["home"] / n * 100
        away_pct = stats["away"] / n * 100
        draw_pct = stats["draw"] / n * 100
        is_mismatch_type = hc in ("dead_rubber", "mid_table") and ac in ("relegation", "relegation_battle", "title_race", "european")
        marker = " ***MISMATCH***" if is_mismatch_type else ""
        p(f"  {hc:20s} vs {ac:20s}: n={n:3d} 主={home_pct:5.1f}% 平={draw_pct:5.1f}% 客={away_pct:5.1f}%{marker}")
        if is_mismatch_type:
            interesting_combos.append((hc, ac, stats))

    # === 2. 动机不对称候选 — 按赔率区间细分 ===
    p(f"\n  === 2. 动机不对称候选(所有赔率, diff<-1.0) ===")
    p(f"  总计: {len(mismatch_candidates)}场")

    # 按赔率区间分
    odds_bins = {"<1.25": [], "1.25-1.35": [], "1.35-1.50": [], "1.50-2.00": [], ">2.00": []}
    for mc in mismatch_candidates:
        oh = mc['odds_h']
        if oh <= 0:
            continue
        if oh < 1.25:
            odds_bins["<1.25"].append(mc)
        elif oh < 1.35:
            odds_bins["1.25-1.35"].append(mc)
        elif oh < 1.50:
            odds_bins["1.35-1.50"].append(mc)
        elif oh < 2.00:
            odds_bins["1.50-2.00"].append(mc)
        else:
            odds_bins[">2.00"].append(mc)

    p(f"\n  按赔率区间:")
    for bin_name, matches_in_bin in odds_bins.items():
        n = len(matches_in_bin)
        if n == 0:
            p(f"  {bin_name}: 0场")
            continue
        home = sum(1 for m in matches_in_bin if m['actual'] == 'home')
        draw = sum(1 for m in matches_in_bin if m['actual'] == 'draw')
        away = sum(1 for m in matches_in_bin if m['actual'] == 'away')
        p(f"  {bin_name}: {n}场 主={home}({home/n*100:.0f}%) 平={draw}({draw/n*100:.0f}%) 客={away}({away/n*100:.0f}%)")

    # 按月份分
    p(f"\n  按月份:")
    month_stats = defaultdict(lambda: {"n": 0, "home": 0, "draw": 0, "away": 0})
    for mc in mismatch_candidates:
        month_stats[mc['month']]["n"] += 1
        month_stats[mc['month']][mc['actual']] += 1

    for month in sorted(month_stats.keys()):
        ms = month_stats[month]
        n = ms["n"]
        p(f"  {month}月: {n}场 主={ms['home']}({ms['home']/n*100:.0f}%) 平={ms['draw']}({ms['draw']/n*100:.0f}%) 客={ms['away']}({ms['away']/n*100:.0f}%)")

    # === 3. 关键交叉: 月份 × 赔率区间 ===
    p(f"\n  === 3. 关键交叉: 月份×赔率(动机不对称候选) ===")
    cross_stats = defaultdict(lambda: {"n": 0, "home": 0, "draw": 0, "away": 0})
    for mc in mismatch_candidates:
        oh = mc['odds_h']
        month = mc['month']
        if oh <= 0:
            continue
        if oh < 1.35:
            odds_key = "odds<1.35"
        elif oh < 1.50:
            odds_key = "1.35-1.50"
        else:
            odds_key = "odds>=1.50"

        is_end_season = month in [4, 5, 6]
        season_key = "4-6月" if is_end_season else "其他月"
        cross_key = f"{season_key}|{odds_key}"
        cross_stats[cross_key]["n"] += 1
        cross_stats[cross_key][mc['actual']] += 1

    for key in sorted(cross_stats.keys()):
        cs = cross_stats[key]
        n = cs["n"]
        p(f"  {key}: {n}场 主={cs['home']}({cs['home']/n*100:.0f}%) 平={cs['draw']}({cs['draw']/n*100:.0f}%) 客={cs['away']}({cs['away']/n*100:.0f}%)")

    # === 4. 对比组: 非动机不对称的低赔率比赛 ===
    p(f"\n  === 4. 对比组: 非不对称的低赔率比赛(odds<1.35) ===")
    non_mismatch_low = []
    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'
        match_month = int(m['date'][5:7]) if len(m['date']) >= 7 else 0

        mot_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:motivation'",
            (mk,)
        ).fetchone()
        mot_f = json.loads(mot_row['data_json'])
        mot_raw = mot_f.get('raw', {})
        home_cat = mot_raw.get('home_category', '') or mot_f.get('home_category', '')
        away_cat = mot_raw.get('away_category', '') or mot_f.get('away_category', '')

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)
        ).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        raw_odds = odds_data.get('raw', {})
        odds_h = float(raw_odds.get('avg_home_odds', 0) or raw_odds.get('closing_avg_home_odds', 0) or 0)

        if odds_h <= 0 or odds_h > 1.35:
            continue

        is_home_dead = home_cat in ("dead_rubber", "mid_table")
        is_away_desperate = away_cat in ("relegation", "relegation_battle", "title_race", "european")

        if not (is_home_dead and is_away_desperate):
            is_end = match_month in [4, 5, 6]
            non_mismatch_low.append({'actual': actual, 'month': match_month, 'is_end': is_end,
                                     'home_cat': home_cat, 'away_cat': away_cat, 'odds_h': odds_h})

    # 非不对称低赔率 — 总体
    n_all = len(non_mismatch_low)
    home_all = sum(1 for m in non_mismatch_low if m['actual'] == 'home')
    draw_all = sum(1 for m in non_mismatch_low if m['actual'] == 'draw')
    away_all = sum(1 for m in non_mismatch_low if m['actual'] == 'away')
    p(f"  总体: {n_all}场 主={home_all}({home_all/n_all*100:.1f}%) 平={draw_all}({draw_all/n_all*100:.1f}%) 客={away_all}({away_all/n_all*100:.1f}%)")

    # 非不对称低赔率 — 4-6月
    end_matches = [m for m in non_mismatch_low if m['is_end']]
    n_end = len(end_matches)
    home_end = sum(1 for m in end_matches if m['actual'] == 'home')
    draw_end = sum(1 for m in end_matches if m['actual'] == 'draw')
    away_end = sum(1 for m in end_matches if m['actual'] == 'away')
    if n_end > 0:
        p(f"  4-6月: {n_end}场 主={home_end}({home_end/n_end*100:.1f}%) 平={draw_end}({draw_end/n_end*100:.1f}%) 客={away_end}({away_end/n_end*100:.1f}%)")

    # 非不对称低赔率 — 其他月
    other_matches = [m for m in non_mismatch_low if not m['is_end']]
    n_other = len(other_matches)
    home_other = sum(1 for m in other_matches if m['actual'] == 'home')
    draw_other = sum(1 for m in other_matches if m['actual'] == 'draw')
    away_other = sum(1 for m in other_matches if m['actual'] == 'away')
    if n_other > 0:
        p(f"  其他月: {n_other}场 主={home_other}({home_other/n_other*100:.1f}%) 平={draw_other}({draw_other/n_other*100:.1f}%) 客={away_other}({away_other/n_other*100:.1f}%)")

    # === 5. 核心对比 ===
    p(f"\n  === 5. 核心对比: 动机不对称 vs 非不对称(4-6月, odds<1.35) ===")
    mismatch_end_low = [mc for mc in mismatch_candidates
                        if mc['month'] in [4,5,6] and mc['odds_h'] > 0 and mc['odds_h'] <= 1.35]
    n_mm = len(mismatch_end_low)
    if n_mm > 0:
        mm_home = sum(1 for m in mismatch_end_low if m['actual'] == 'home')
        mm_draw = sum(1 for m in mismatch_end_low if m['actual'] == 'draw')
        mm_away = sum(1 for m in mismatch_end_low if m['actual'] == 'away')
        p(f"  动机不对称(4-6月,odds<1.35): {n_mm}场 主={mm_home}({mm_home/n_mm*100:.0f}%) 平={mm_draw}({mm_draw/n_mm*100:.0f}%) 客={mm_away}({mm_away/n_mm*100:.0f}%)")
    else:
        p(f"  动机不对称(4-6月,odds<1.35): 0场")

    if n_end > 0:
        p(f"  非不对称(4-6月,odds<1.35):    {n_end}场 主={home_end}({home_end/n_end*100:.1f}%) 平={draw_end}({draw_end/n_end*100:.1f}%) 客={away_end}({away_end/n_end*100:.1f}%)")

    # 关键指标: 冷门率对比
    if n_mm > 0 and n_end > 0:
        mm_upset = n_mm - mm_home  # 非主胜=冷门
        other_upset = n_end - home_end
        p(f"\n  冷门率: 不对称={mm_upset}/{n_mm}={mm_upset/n_mm*100:.1f}%  非不对称={other_upset}/{n_end}={other_upset/n_end*100:.1f}%")
        p(f"  差异: {mm_upset/n_mm*100 - other_upset/n_end*100:+.1f}pp")

    # === 6. 所有不对称候选的详情 ===
    p(f"\n  === 6. 全部动机不对称候选详情(odds<=1.50, diff<-1.0) ===")
    for mc in sorted(mismatch_candidates, key=lambda x: x['date']):
        if mc['odds_h'] <= 0 or mc['odds_h'] > 1.50:
            continue
        p(f"  {mc['date']} {mc['home']} vs {mc['away']} ({mc['league']})")
        p(f"    odds={mc['odds_h']:.2f} score={mc['score']} actual={mc['actual']}")
        p(f"    {mc['home_cat']} vs {mc['away_cat']} diff={mc['mot_diff']:.1f} month={mc['month']}")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v35_mismatch_deep.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


if __name__ == "__main__":
    main()