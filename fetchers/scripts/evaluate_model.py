"""
模型评估脚本 v4

评估指标:
1. argmax准确率（每个模型）
2. Brier Score
3. Log Loss
4. 场景细分（CLV+动机、联赛等）
5. EV投注ROI
"""

import sys, io, json, sqlite3, math
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'


def evaluate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    matches = conn.execute(
        "SELECT match_key, home_score, away_score, league_standard, date "
        "FROM matches WHERE status='finished' AND home_score IS NOT NULL AND away_score IS NOT NULL"
    ).fetchall()

    # 按模型评估
    models = ['enhanced_linear', 'chain']
    results = {}

    for model_name in models:
        data_type = f'model:{model_name}'
        n = 0
        correct = 0
        brier_total = 0
        log_loss_total = 0
        draw_actual = 0
        draw_pred = 0
        draw_correct = 0

        for m in matches:
            mk = m['match_key']
            actual = 'home' if m['home_score'] > m['away_score'] else 'draw' if m['home_score'] == m['away_score'] else 'away'

            model_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type=?",
                (mk, data_type)
            ).fetchone()
            if not model_row:
                continue

            model = json.loads(model_row['data_json'])
            hp = model.get('home_win_prob', 0.33)
            dp = model.get('draw_prob', 0.33)
            ap = model.get('away_win_prob', 0.34)

            # argmax
            pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
            if pred == actual:
                correct += 1

            # Brier
            if actual == 'home':
                brier_total += (hp - 1)**2 + dp**2 + ap**2
            elif actual == 'draw':
                brier_total += hp**2 + (dp - 1)**2 + ap**2
            else:
                brier_total += hp**2 + dp**2 + (ap - 1)**2

            # Log Loss
            p = {'home': hp, 'draw': dp, 'away': ap}[actual]
            p = max(p, 1e-10)
            log_loss_total -= math.log(p)

            # Draw stats
            if actual == 'draw':
                draw_actual += 1
            if pred == 'draw':
                draw_pred += 1
                if actual == 'draw':
                    draw_correct += 1

            n += 1

        if n > 0:
            results[model_name] = {
                'n': n,
                'accuracy': correct / n,
                'brier': brier_total / n,
                'logloss': log_loss_total / n,
                'draw_actual': draw_actual,
                'draw_pred': draw_pred,
                'draw_correct': draw_correct,
            }

    conn.close()

    # 输出
    print("=" * 70)
    print("  模型评估 v4 (Enhanced Linear v3.2 vs Chain v1.0)")
    print("=" * 70)

    for name, r in results.items():
        print(f"\n--- {name} ---")
        print(f"  比赛数: {r['n']}")
        print(f"  argmax准确率: {r['accuracy']*100:.1f}%")
        print(f"  Brier Score: {r['brier']:.4f}")
        print(f"  Log Loss: {r['logloss']:.4f}")
        n = r['n']
        da = r['draw_actual']
        dp = r['draw_pred']
        dc = r['draw_correct']
        print(f"  Draw: 实际={da}({da/n*100:.1f}%) 预测={dp} 正确={dc}")
        if dp > 0:
            print(f"  Draw precision: {dc/dp*100:.1f}%")
        if da > 0:
            print(f"  Draw recall: {dc/da*100:.1f}%")

    # 综合概率 (EL 60% + Chain 40%)
    print(f"\n--- 综合概率 (EL×0.6 + Chain×0.4) ---")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    n = 0
    correct = 0
    brier_total = 0

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else 'draw' if m['home_score'] == m['away_score'] else 'away'

        el_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)
        ).fetchone()
        ch_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:chain'",
            (mk,)
        ).fetchone()

        if not el_row or not ch_row:
            continue

        el = json.loads(el_row['data_json'])
        ch = json.loads(ch_row['data_json'])

        hp = el['home_win_prob'] * 0.6 + ch['home_win_prob'] * 0.4
        dp = el['draw_prob'] * 0.6 + ch['draw_prob'] * 0.4
        ap = el['away_win_prob'] * 0.6 + ch['away_win_prob'] * 0.4
        total = hp + dp + ap
        hp /= total; dp /= total; ap /= total

        pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
        if pred == actual:
            correct += 1

        if actual == 'home':   brier_total += (hp-1)**2 + dp**2 + ap**2
        elif actual == 'draw': brier_total += hp**2 + (dp-1)**2 + ap**2
        else:                  brier_total += hp**2 + dp**2 + (ap-1)**2

        n += 1

    conn.close()

    if n > 0:
        print(f"  比赛数: {n}")
        print(f"  argmax准确率: {correct/n*100:.1f}%")
        print(f"  Brier Score: {brier_total/n:.4f}")


if __name__ == "__main__":
    evaluate()