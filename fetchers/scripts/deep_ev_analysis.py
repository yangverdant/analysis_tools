"""
深度EV分析: 模型概率 vs 开盘/闭盘赔率

核心问题: 用开盘赔率算EV时，是否存在真正的信息差?
"""
import sys, io, json, sqlite3, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

DB_PATH = 'data/unified_football.db'
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

matches = conn.execute(
    "SELECT match_key, home_score, away_score FROM matches "
    "WHERE status='finished' AND home_score IS NOT NULL AND away_score IS NOT NULL"
).fetchall()

print(f"分析 {len(matches)} 场比赛...")

# 数据收集
open_ev_records = []
close_ev_records = []
clv_records = []

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

    eo_row = conn.execute(
        "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
        (mk,)
    ).fetchone()
    if not eo_row:
        continue
    eo = json.loads(eo_row['data_json'])
    raw = eo.get('raw', {})

    has_closing = raw.get('has_closing', False)
    clv_data = raw.get('clv', {})

    open_h = raw.get('avg_home_odds', 0)
    open_d = raw.get('avg_draw_odds', 0)
    open_a = raw.get('avg_away_odds', 0)
    close_h = raw.get('closing_avg_home_odds', 0)
    close_d = raw.get('closing_avg_draw_odds', 0)
    close_a = raw.get('closing_avg_away_odds', 0)

    hp = model.get('home_win_prob', 0)
    dp = model.get('draw_prob', 0)
    ap = model.get('away_win_prob', 0)

    model_pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

    # 开盘EV
    try:
        if open_h > 1 and open_d > 1 and open_a > 1:
            margin = 1/open_h + 1/open_d + 1/open_a
            fair_h = open_h * margin
            fair_d = open_d * margin
            fair_a = open_a * margin
            ev_h = hp * fair_h - 1
            ev_d = dp * fair_d - 1
            ev_a = ap * fair_a - 1

            best = max([('home', ev_h), ('draw', ev_d), ('away', ev_a)], key=lambda x: x[1])

            is_correct = (best[0] == actual)
            pnl = 1
            if is_correct:
                if best[0] == 'home': pnl = open_h - 1
                elif best[0] == 'draw': pnl = open_d - 1
                else: pnl = open_a - 1
            else:
                pnl = -1

            open_ev_records.append({
                'mk': mk, 'actual': actual,
                'best_dir': best[0], 'ev': best[1],
                'correct': is_correct, 'pnl': pnl,
            })
    except (ValueError, ZeroDivisionError):
        pass

    # 闭盘EV
    try:
        if close_h > 1 and close_d > 1 and close_a > 1:
            margin = 1/close_h + 1/close_d + 1/close_a
            fair_h = close_h * margin
            fair_d = close_d * margin
            fair_a = close_a * margin
            ev_h = hp * fair_h - 1
            ev_d = dp * fair_d - 1
            ev_a = ap * fair_a - 1

            best = max([('home', ev_h), ('draw', ev_d), ('away', ev_a)], key=lambda x: x[1])

            is_correct = (best[0] == actual)
            pnl = 1
            if is_correct:
                if best[0] == 'home': pnl = close_h - 1
                elif best[0] == 'draw': pnl = close_d - 1
                else: pnl = close_a - 1
            else:
                pnl = -1

            close_ev_records.append({
                'mk': mk, 'actual': actual,
                'best_dir': best[0], 'ev': best[1],
                'correct': is_correct, 'pnl': pnl,
            })
    except (ValueError, ZeroDivisionError):
        pass

    # CLV方向分析
    if clv_data:
        opening_home = clv_data.get('opening_home', 0)
        closing_home = clv_data.get('closing_home', 0)
        opening_away = clv_data.get('opening_away', 0)
        closing_away = clv_data.get('closing_away', 0)

        # 开盘预测方向
        open_pred = max(['home', 'draw', 'away'],
            key=lambda x: {'home': opening_home, 'draw': clv_data.get('opening_draw', 0), 'away': opening_away}[x])
        close_pred = max(['home', 'draw', 'away'],
            key=lambda x: {'home': closing_home, 'draw': clv_data.get('closing_draw', 0), 'away': closing_away}[x])

        # 闭盘是否向模型方向调整
        close_toward_model = False
        if model_pred != open_pred:
            model_prob_open = {'home': opening_home, 'draw': clv_data.get('opening_draw', 0), 'away': opening_away}[model_pred]
            model_prob_close = {'home': closing_home, 'draw': clv_data.get('closing_draw', 0), 'away': closing_away}[model_pred]
            if model_prob_close > model_prob_open + 0.005:
                close_toward_model = True

        clv_records.append({
            'mk': mk, 'actual': actual, 'model_pred': model_pred,
            'open_pred': open_pred, 'close_pred': close_pred,
            'close_toward_model': close_toward_model,
            'model_agree_open': model_pred == open_pred,
            'model_agree_close': model_pred == close_pred,
        })

conn.close()

# === 输出 ===
print("\n=== 开盘EV分析 (模型概率 vs 开盘赔率) ===")
for threshold in [0.02, 0.05, 0.08, 0.10, 0.15]:
    evs = [e for e in open_ev_records if e['ev'] > threshold]
    if not evs:
        continue
    correct = sum(1 for e in evs if e['correct'])
    pnl = sum(e['pnl'] for e in evs)
    print(f"  开盘EV>{threshold}: {len(evs)}场 正确率={correct/len(evs)*100:.1f}% ROI={pnl/len(evs)*100:.1f}%")
    for dir in ['home', 'draw', 'away']:
        dir_evs = [e for e in evs if e['best_dir'] == dir]
        if dir_evs:
            d_correct = sum(1 for e in dir_evs if e['correct'])
            d_pnl = sum(e['pnl'] for e in dir_evs)
            print(f"    {dir}: {len(dir_evs)}场 正确率={d_correct/len(dir_evs)*100:.1f}% ROI={d_pnl/len(dir_evs)*100:.1f}%")

print("\n=== 闭盘EV分析 (模型概率 vs 闭盘赔率) ===")
for threshold in [0.02, 0.05, 0.08, 0.10, 0.15]:
    evs = [e for e in close_ev_records if e['ev'] > threshold]
    if not evs:
        continue
    correct = sum(1 for e in evs if e['correct'])
    pnl = sum(e['pnl'] for e in evs)
    print(f"  闭盘EV>{threshold}: {len(evs)}场 正确率={correct/len(evs)*100:.1f}% ROI={pnl/len(evs)*100:.1f}%")

print("\n=== CLV方向性分析 ===")
if clv_records:
    total_clv = len(clv_records)
    agree_open = sum(1 for r in clv_records if r['model_agree_open'])
    agree_close = sum(1 for r in clv_records if r['model_agree_close'])
    toward_model = sum(1 for r in clv_records if r['close_toward_model'])

    print(f"  模型与开盘方向一致: {agree_open}/{total_clv} ({agree_open/total_clv*100:.1f}%)")
    print(f"  模型与闭盘方向一致: {agree_close}/{total_clv} ({agree_close/total_clv*100:.1f}%)")
    print(f"  闭盘向模型方向调整: {toward_model}/{total_clv} ({toward_model/total_clv*100:.1f}%)")

    # 模型逆开盘但闭盘向模型调整 → 信息差?
    reverse_and_adjusted = [r for r in clv_records if not r['model_agree_open'] and r['close_toward_model']]
    if reverse_and_adjusted:
        correct = sum(1 for r in reverse_and_adjusted if r['model_pred'] == r['actual'])
        print(f"  模型逆开盘+闭盘向模型调整: {len(reverse_and_adjusted)}场 模型正确率={correct/len(reverse_and_adjusted)*100:.1f}%")

    # 模型逆开盘但闭盘没调整 → 信号不强
    reverse_no_adjust = [r for r in clv_records if not r['model_agree_open'] and not r['close_toward_model']]
    if reverse_no_adjust:
        correct = sum(1 for r in reverse_no_adjust if r['model_pred'] == r['actual'])
        print(f"  模型逆开盘+闭盘未调整: {len(reverse_no_adjust)}场 模型正确率={correct/len(reverse_no_adjust)*100:.1f}%")

    # 模型与开盘一致 → 大多数情况
    agree_both = [r for r in clv_records if r['model_agree_open']]
    if agree_both:
        correct = sum(1 for r in agree_both if r['model_pred'] == r['actual'])
        print(f"  模型与开盘一致: {len(agree_both)}场 模型正确率={correct/len(agree_both)*100:.1f}%")

print("\n=== 核心结论 ===")
print("1. 用闭盘赔率算EV → 所有EV>0都是负收益 (和v3.0一样)")
print("2. 用开盘赔率算EV → 看开盘EV>0是否也是负收益?")
print("3. 如果开盘EV>0也是负收益 → 说明模型没有真正的信息差")
print("4. 如果开盘EV>0有正收益 → 说明模型在开盘时有信息差")
print("   但闭盘会吸收这些信息差 → 所以要早下注(用开盘赔率)")