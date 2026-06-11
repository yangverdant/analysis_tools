"""
场景优势分析 v2: 找出模型在哪些子集有真正的信息差

核心思路:
1. 在全量数据中，模型argmax方向 = 实际结果的准确率约52-53%
2. 但在某些特定场景中，模型的准确率可能显著高于赔率
3. 找出这些场景 → 模型真正的信息差来源

分析维度:
- 动机差异: 争冠vs无欲无求、保级vs中游 → 战意差赔率可能低估
- CLV方向: 开盘→闭盘赔率调整方向 → 市场信息变化
- 信号覆盖: 模型信号反对赔率方向 → 潜在信息差
- 泊松比分: 小概率比分集中 → 模型捕捉到的微弱信号
- 赛程密度: 疲劳累积 → 赔率可能来不及反映
"""

import sys, io, json, sqlite3, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    matches = conn.execute(
        "SELECT match_key, home_score, away_score, league_standard, date "
        "FROM matches WHERE status='finished' AND home_score IS NOT NULL AND away_score IS NOT NULL"
    ).fetchall()

    print(f"分析 {len(matches)} 场比赛...")

    # 收集数据
    records = []
    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else 'draw' if m['home_score'] == m['away_score'] else 'away'

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
    n = len(records)
    print(f"有效数据: {n} 场")

    # === 基线 ===
    baseline_correct = sum(1 for r in records if r['model']['signal_direction'] == r['actual'])
    baseline_acc = baseline_correct / n * 100
    print(f"\n=== 基线 ===")
    print(f"信号方向准确率: {baseline_correct}/{n} = {baseline_acc:.1f}%")

    # === 场景1: 动机差异大 ===
    print(f"\n=== 场景1: 动机差异 ===")
    for label, check in [
        ("争冠vs无欲无求", lambda r: r['factors'].get('motivation', {}).get('raw', {}).get('home_category') == 'title_race' and r['factors'].get('motivation', {}).get('raw', {}).get('away_category') == 'dead_rubber'),
        ("保级vs中游", lambda r: r['factors'].get('motivation', {}).get('raw', {}).get('home_category') in ['relegation', 'relegation_battle'] and r['factors'].get('motivation', {}).get('raw', {}).get('away_category') == 'mid_table'),
        ("动机差>0.5", lambda r: r['factors'].get('motivation', {}).get('confidence', 0) > 0 and abs(r['factors'].get('motivation', {}).get('diff', 0)) > 0.5),
        ("动机差>1.0", lambda r: r['factors'].get('motivation', {}).get('confidence', 0) > 0 and abs(r['factors'].get('motivation', {}).get('diff', 0)) > 1.0),
    ]:
        subset = [r for r in records if check(r)]
        if len(subset) < 20:
            print(f"  {label}: {len(subset)}场 (太少)")
            continue
        correct = sum(1 for r in subset if r['model']['signal_direction'] == r['actual'])
        # 也看argmax
        hp = subset[0]['model'].get('home_win_prob', 0)
        argmax_correct = 0
        for r in subset:
            pred = max(['home', 'draw', 'away'], key=lambda x: r['model'].get(f'{x}_win_prob', r['model'].get('draw_prob', 0) if x == 'draw' else 0))
            if pred == r['actual']:
                argmax_correct += 1
        print(f"  {label}: {len(subset)}场 argmax={argmax_correct/len(subset)*100:.1f}% signal={correct/len(subset)*100:.1f}%")

    # === 场景2: CLV信号强 ===
    print(f"\n=== 场景2: CLV信号 ===")
    for label, check in [
        ("CLV>0.03", lambda r: r['factors'].get('odds_movement', {}).get('confidence', 0) > 0 and abs(r['factors'].get('odds_movement', {}).get('diff', 0)) > 0.03),
        ("CLV>0.05", lambda r: r['factors'].get('odds_movement', {}).get('confidence', 0) > 0 and abs(r['factors'].get('odds_movement', {}).get('diff', 0)) > 0.05),
        ("CLV反转(开盘→闭盘)", lambda r: r['factors'].get('odds_movement', {}).get('raw', {}).get('has_closing', False) and r['factors'].get('odds_movement', {}).get('diff', 0) != 0),
    ]:
        subset = [r for r in records if check(r)]
        if len(subset) < 20:
            print(f"  {label}: {len(subset)}场 (太少)")
            continue
        argmax_correct = 0
        for r in subset:
            hp = r['model'].get('home_win_prob', 0)
            dp = r['model'].get('draw_prob', 0)
            ap = r['model'].get('away_win_prob', 0)
            pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
            if pred == r['actual']:
                argmax_correct += 1
        print(f"  {label}: {len(subset)}场 argmax={argmax_correct/len(subset)*100:.1f}%")

    # === 场景3: 信号覆盖（模型反对赔率） ===
    print(f"\n=== 场景3: 信号覆盖（模型反对赔率方向） ===")
    for r in records:
        eo = r['factors'].get('euro_odds', {})
        if eo.get('confidence', 0) > 0:
            euro_pred = max(['home', 'draw', 'away'], key=lambda x: {'home': eo.get('home_value', 0), 'draw': eo.get('raw', {}).get('draw_prob', 0), 'away': eo.get('away_value', 0)}[x])
            model_pred = r['model']['signal_direction']
            r['euro_pred'] = euro_pred
            r['model_disagree'] = (model_pred != euro_pred)

    disagree = [r for r in records if r.get('model_disagree', False)]
    agree = [r for r in records if not r.get('model_disagree', True)]

    if disagree:
        correct = sum(1 for r in disagree if r['model']['signal_direction'] == r['actual'])
        print(f"  模型反对赔率: {len(disagree)}场 模型方向准确率={correct/len(disagree)*100:.1f}%")
        # 模型反对赔率但正确 → 信息差
        info_advantage = [r for r in disagree if r['model']['signal_direction'] == r['actual']]
        print(f"  模型反对赔率且正确: {len(info_advantage)}场 = 信息差")

    if agree:
        correct = sum(1 for r in agree if r['model']['signal_direction'] == r['actual'])
        print(f"  模型与赔率一致: {len(agree)}场 模型方向准确率={correct/len(agree)*100:.1f}%")

    # === 场景4: 赛程密度差异 ===
    print(f"\n=== 场景4: 赛程密度/疲劳 ===")
    for label, check in [
        ("疲劳差>0.3", lambda r: r['factors'].get('rest_days', {}).get('confidence', 0) > 0 and abs(r['factors'].get('rest_days', {}).get('raw', {}).get('density_diff', 0) or 0) > 0.3),
        ("休息<3天", lambda r: r['factors'].get('rest_days', {}).get('confidence', 0) > 0 and (r['factors'].get('rest_days', {}).get('home_value', 7) < 3 or r['factors'].get('rest_days', {}).get('away_value', 7) < 3)),
    ]:
        subset = [r for r in records if check(r)]
        if len(subset) < 20:
            print(f"  {label}: {len(subset)}场 (太少)")
            continue
        argmax_correct = 0
        for r in subset:
            hp = r['model'].get('home_win_prob', 0)
            dp = r['model'].get('draw_prob', 0)
            ap = r['model'].get('away_win_prob', 0)
            pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
            if pred == r['actual']:
                argmax_correct += 1
        print(f"  {label}: {len(subset)}场 argmax={argmax_correct/len(subset)*100:.1f}%")

    # === 场景5: EV正值子集 ===
    print(f"\n=== 场景5: EV正值 ===")
    for threshold in [0.02, 0.05, 0.08]:
        ev_pos = [r for r in records if any(v > threshold for v in r['model'].get('ev', {}).values())]
        if not ev_pos:
            continue
        # 用argmax预测
        argmax_correct = 0
        ev_pnl = 0
        for r in ev_pos:
            hp = r['model'].get('home_win_prob', 0)
            dp = r['model'].get('draw_prob', 0)
            ap = r['model'].get('away_win_prob', 0)
            pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
            if pred == r['actual']:
                argmax_correct += 1
        print(f"  EV>{threshold}: {len(ev_pos)}场 argmax={argmax_correct/len(ev_pos)*100:.1f}%")

    # === 联赛差异 ===
    print(f"\n=== 联赛准确率 ===")
    league_stats = {}
    for r in records:
        lg = r['league'] or 'unknown'
        if lg not in league_stats:
            league_stats[lg] = {'total': 0, 'correct': 0}
        hp = r['model'].get('home_win_prob', 0)
        dp = r['model'].get('draw_prob', 0)
        ap = r['model'].get('away_win_prob', 0)
        pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
        league_stats[lg]['total'] += 1
        if pred == r['actual']:
            league_stats[lg]['correct'] += 1

    for lg, s in sorted(league_stats.items(), key=lambda x: -x[1]['total']):
        if s['total'] >= 50:
            print(f"  {lg:25s}: {s['correct']}/{s['total']} = {s['correct']/s['total']*100:.1f}%")

    # === 结论 ===
    print(f"\n=== 核心结论 ===")
    print("1. 模型与赔率一致的场次占绝大多数，准确率≈赔率准确率")
    print("2. 模型反对赔率的场次 → 检查是否真的有信息差")
    print("3. 动机差异大的场景 → 可能是赔率来不及反映的领域")
    print("4. 赛程密度/疲劳 → 赔率开盘时可能未考虑的因素")


if __name__ == "__main__":
    main()