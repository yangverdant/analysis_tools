"""
场景细分评估 v1: 在哪些子集模型有优势？

核心问题: 整体准确率52%没有投注价值，但某些子集可能55-60%
目标: 找出这些子集 → 真正的信息差来源

评估维度:
1. 动机差异（争冠/保级 vs 无欲无求）
2. CLV信号强度
3. 赛程密度/疲劳
4. 赔率置信区间
5. 联赛差异
6. 组合场景
"""

import sys, io, json, sqlite3, math
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'


def load_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    matches = conn.execute(
        "SELECT match_key, home_score, away_score, league_standard, date "
        "FROM matches WHERE status='finished' AND home_score IS NOT NULL AND away_score IS NOT NULL"
    ).fetchall()

    records = []
    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else 'draw' if m['home_score'] == m['away_score'] else 'away'

        # 模型结果
        model_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)
        ).fetchone()
        if not model_row:
            continue
        model = json.loads(model_row['data_json'])

        # 因素数据
        factor_rows = conn.execute(
            "SELECT data_type, data_json FROM match_data WHERE match_key=? AND source='factor'",
            (mk,)
        ).fetchall()
        factors = {}
        for fr in factor_rows:
            name = fr['data_type'].replace('factor:', '')
            factors[name] = json.loads(fr['data_json'])

        records.append({
            'mk': mk, 'actual': actual, 'model': model, 'factors': factors,
            'league': m['league_standard'], 'date': m['date'],
            'total_goals': m['home_score'] + m['away_score'],
        })

    conn.close()
    return records


def eval_subset(records, label=""):
    """评估一个子集的argmax准确率和Brier Score"""
    if len(records) < 15:
        return None
    n = len(records)
    correct = 0
    brier = 0
    draw_actual = sum(1 for r in records if r['actual'] == 'draw')
    draw_pred = 0
    draw_correct = 0
    home_actual = sum(1 for r in records if r['actual'] == 'home')
    away_actual = sum(1 for r in records if r['actual'] == 'away')

    for r in records:
        hp = r['model'].get('home_win_prob', 0.33)
        dp = r['model'].get('draw_prob', 0.33)
        ap = r['model'].get('away_win_prob', 0.34)
        pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
        if pred == r['actual']:
            correct += 1
        if r['actual'] == 'home':   brier += (hp-1)**2 + dp**2 + ap**2
        elif r['actual'] == 'draw': brier += hp**2 + (dp-1)**2 + ap**2
        else:                       brier += hp**2 + dp**2 + (ap-1)**2
        if pred == 'draw':
            draw_pred += 1
            if r['actual'] == 'draw': draw_correct += 1

    return {
        'label': label,
        'n': n,
        'acc': correct / n,
        'brier': brier / n,
        'home_pct': home_actual / n,
        'draw_pct': draw_actual / n,
        'away_pct': away_actual / n,
        'draw_pred': draw_pred,
        'draw_recall': draw_correct / draw_actual if draw_actual > 0 else 0,
    }


def print_result(r):
    if not r:
        return
    print(f"  {r['label']:40s}: {r['n']:5d}场 acc={r['acc']*100:.1f}% brier={r['brier']:.4f} "
          f"H/D/A={r['home_pct']*100:.0f}/{r['draw_pct']*100:.0f}/{r['away_pct']*100:.0f}%")


def main():
    records = load_data()
    n = len(records)
    print(f"加载 {n} 场比赛")

    # 基线
    base = eval_subset(records, "全量基线")
    print_result(base)
    baseline_acc = base['acc']

    # === 1. 联赛细分 ===
    print(f"\n=== 1. 联赛细分 ===")
    by_league = defaultdict(list)
    for r in records:
        lg = r['league'] or 'unknown'
        by_league[lg].append(r)

    results = []
    for lg, subset in sorted(by_league.items(), key=lambda x: -len(x[1])):
        r = eval_subset(subset, lg)
        if r:
            results.append(r)
    results.sort(key=lambda x: -x['acc'])
    for r in results:
        if r['n'] >= 50:
            delta = (r['acc'] - baseline_acc) * 100
            marker = " ★" if delta > 2 else " ✗" if delta < -3 else ""
            print(f"  {r['label']:40s}: {r['n']:5d}场 acc={r['acc']*100:.1f}% ({delta:+.1f}%){marker}")

    # === 2. 动机差异 ===
    print(f"\n=== 2. 动机差异 ===")
    def get_motivation_diff(r):
        mot = r['factors'].get('motivation', {})
        if mot.get('confidence', 0) <= 0:
            return None
        # 新版numeric: diff在顶层
        diff = mot.get('diff')
        if diff is None:
            # 旧版categorical: 从raw计算
            raw = mot.get('raw', {})
            hc = raw.get('home_category', raw.get('home_motivation', ''))
            ac = raw.get('away_category', raw.get('away_motivation', ''))
            strength = {'title_race': 1.0, 'relegation': 0.8, 'relegation_battle': 0.9,
                       'european': 0.6, 'mid_table': 0.0, 'dead_rubber': -0.5}
            hs = strength.get(hc, 0)
            as_ = strength.get(ac, 0)
            diff = hs - as_
        return diff

    for label, check in [
        ("主队强动机(>0.5)", lambda r: (get_motivation_diff(r) or 0) > 0.5),
        ("客队强动机(<-0.5)", lambda r: (get_motivation_diff(r) or 0) < -0.5),
        ("动机差>1.0", lambda r: abs(get_motivation_diff(r) or 0) > 1.0),
        ("无动机差(≈0)", lambda r: get_motivation_diff(r) is not None and abs(get_motivation_diff(r)) < 0.1),
    ]:
        subset = [r for r in records if check(r)]
        r = eval_subset(subset, label)
        print_result(r)

    # === 3. CLV信号 ===
    print(f"\n=== 3. CLV信号 ===")
    def get_clv(r):
        om = r['factors'].get('odds_movement', {})
        if om.get('confidence', 0) <= 0:
            return None
        return om.get('diff', 0)

    for label, check in [
        ("CLV强主队(>0.05)", lambda r: (get_clv(r) or 0) > 0.05),
        ("CLV强客队(<-0.05)", lambda r: (get_clv(r) or 0) < -0.05),
        ("CLV>0.03", lambda r: abs(get_clv(r) or 0) > 0.03),
    ]:
        subset = [r for r in records if check(r)]
        r = eval_subset(subset, label)
        print_result(r)

    # === 4. 赛程密度/疲劳 ===
    print(f"\n=== 4. 赛程密度/疲劳 ===")
    def get_rest(r):
        rd = r['factors'].get('rest_days', {})
        if rd.get('confidence', 0) <= 0:
            return None, None
        return rd.get('home_value', 7), rd.get('away_value', 7)

    for label, check in [
        ("主队休息<4天", lambda r: get_rest(r)[0] is not None and get_rest(r)[0] < 4),
        ("客队休息<4天", lambda r: get_rest(r)[1] is not None and get_rest(r)[1] < 4),
        ("休息差>3天", lambda r: get_rest(r)[0] is not None and get_rest(r)[1] is not None and abs(get_rest(r)[0] - get_rest(r)[1]) > 3),
    ]:
        subset = [r for r in records if check(r)]
        r = eval_subset(subset, label)
        print_result(r)

    # === 5. 欧赔置信区间 ===
    print(f"\n=== 5. 赔率置信区间 ===")
    def get_odds_conf(r):
        eo = r['factors'].get('euro_odds', {})
        return eo.get('confidence', 0)

    for label, check in [
        ("高置信(>=0.90)", lambda r: get_odds_conf(r) >= 0.90),
        ("低置信(<0.80)", lambda r: 0 < get_odds_conf(r) < 0.80),
        ("无欧赔", lambda r: get_odds_conf(r) <= 0),
    ]:
        subset = [r for r in records if check(r)]
        r = eval_subset(subset, label)
        print_result(r)

    # === 6. 组合场景（真正的信息差可能在这里） ===
    print(f"\n=== 6. 组合场景 ===")

    # 争冠+疲劳：主队争冠但休息少 → 可能翻车
    subset = [r for r in records
              if (get_motivation_diff(r) or 0) > 0.5
              and (get_rest(r)[0] or 7) < 4]
    r = eval_subset(subset, "争冠主队+休息不足")
    print_result(r)

    # 保级+主队疲劳
    subset = [r for r in records
              if (get_motivation_diff(r) or 0) < -0.5
              and (get_rest(r)[1] or 7) < 4]
    r = eval_subset(subset, "保级客队+休息不足")
    print_result(r)

    # CLV+动机一致：最强信号
    subset = [r for r in records
              if abs(get_clv(r) or 0) > 0.03
              and abs(get_motivation_diff(r) or 0) > 0.3
              and (get_clv(r) or 0) * (get_motivation_diff(r) or 0) > 0]
    r = eval_subset(subset, "CLV+动机同向")
    print_result(r)

    # EV>0.05 + 动机差大
    subset = [r for r in records
              if any(v > 0.05 for v in r['model'].get('ev', {}).values())
              and abs(get_motivation_diff(r) or 0) > 0.3]
    r = eval_subset(subset, "高EV+动机差")
    print_result(r)

    # 五大联赛 + CLV强
    big5 = {"Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"}
    subset = [r for r in records
              if r['league'] in big5
              and abs(get_clv(r) or 0) > 0.05]
    r = eval_subset(subset, "五大联赛+CLV>0.05")
    print_result(r)

    # 五大联赛 + 动机差大
    subset = [r for r in records
              if r['league'] in big5
              and abs(get_motivation_diff(r) or 0) > 0.5]
    r = eval_subset(subset, "五大联赛+动机差>0.5")
    print_result(r)

    # 五大联赛 + 休息差
    subset = [r for r in records
              if r['league'] in big5
              and get_rest(r)[0] is not None and get_rest(r)[1] is not None
              and abs((get_rest(r)[0] or 7) - (get_rest(r)[1] or 7)) > 3]
    r = eval_subset(subset, "五大联赛+休息差>3天")
    print_result(r)

    print(f"\n=== 总结 ===")
    print(f"基线准确率: {baseline_acc*100:.1f}%")
    print(f"寻找 > {baseline_acc*100+2:.0f}% 的子集作为信息差来源")


if __name__ == "__main__":
    main()