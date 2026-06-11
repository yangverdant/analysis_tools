"""
v3.5模型全量验证 — 动机不对称+杯赛低赔率+高海拔主场

对比v3.4 (Brier 0.5747, argmax 53.4%) vs v3.5
核心改动:
1. 全球冷门区改为仅5-6月触发
2. 新增动机不对称规则 (4-6月, odds≤1.35)
3. 新增杯赛低赔率规则 (odds≤1.25)
4. 新增高海拔主场规则 (odds≥2.0)
"""
import sys, io, json, sqlite3, math, time
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

from fetchers.storage.crud import UnifiedStorage
from fetchers.analysis.models.enhanced_linear import EnhancedLinearModel

DB_PATH = 'd:/football_tools/data/unified_football.db'


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 获取所有finished比赛
    matches = conn.execute(
        "SELECT match_key, date, home_team, away_team, league_standard, "
        "home_score, away_score "
        "FROM matches WHERE status='finished' AND home_score IS NOT NULL AND away_score IS NOT NULL "
        "ORDER BY date"
    ).fetchall()
    conn.close()

    print("=" * 70)
    print("  v3.5 全量验证 — 13993场比赛")
    print("=" * 70)
    print(f"  总比赛数: {len(matches)}")

    storage = UnifiedStorage()
    model = EnhancedLinearModel()

    # ---- 统计 ----
    total_n = 0
    correct_new = 0
    brier_new = 0.0
    draw_actual = 0
    draw_pred_new = 0
    draw_correct_new = 0

    # 旧模型结果对比
    correct_old = 0
    brier_old = 0.0
    draw_pred_old = 0
    draw_correct_old = 0

    # 场景统计
    flag_counts = defaultdict(int)
    flag_correct = defaultdict(int)
    flag_brier_new = defaultdict(float)
    flag_n = defaultdict(int)

    # 月度统计
    monthly_stats = defaultdict(lambda: {"n": 0, "correct_new": 0, "correct_old": 0,
                                          "brier_new": 0.0, "brier_old": 0.0})

    # 赔率区间统计
    odds_range_stats = defaultdict(lambda: {"n": 0, "correct_new": 0, "correct_old": 0,
                                              "brier_new": 0.0, "brier_old": 0.0})

    # 动机不对称触发统计
    mismatch_stats = {"triggered": 0, "triggered_correct": 0,
                      "triggered_brier_new": 0.0, "triggered_brier_old": 0.0,
                      "home_actual": 0, "draw_actual": 0, "away_actual": 0}

    t0 = time.time()
    errors = 0

    for i, m in enumerate(matches):
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'
        match_month = int(m['date'][5:7]) if len(m['date']) >= 7 else 0

        # 加载旧模型结果 (v3.4)
        conn2 = storage._conn()
        old_row = conn2.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
            (mk,)
        ).fetchone()
        conn2.close()

        if not old_row:
            errors += 1
            continue

        old_model = json.loads(old_row['data_json'])
        old_version = old_model.get('model_version', 'unknown')
        hp_old = old_model.get('home_win_prob', 0.33)
        dp_old = old_model.get('draw_prob', 0.33)
        ap_old = old_model.get('away_win_prob', 0.34)

        pred_old = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_old, 'draw': dp_old, 'away': ap_old}[x])
        if pred_old == actual:
            correct_old += 1
        if actual == 'draw':
            draw_actual += 1
        if pred_old == 'draw':
            draw_pred_old += 1
            if actual == 'draw':
                draw_correct_old += 1

        # Brier old
        if actual == 'home':   brier_old += (hp_old-1)**2 + dp_old**2 + ap_old**2
        elif actual == 'draw': brier_old += hp_old**2 + (dp_old-1)**2 + ap_old**2
        else:                  brier_old += hp_old**2 + dp_old**2 + (ap_old-1)**2

        # 运行新模型 (v3.5, force=True)
        try:
            new_result = model.run(mk, storage, force=True)
            hp_new = new_result.get('home_win_prob', 0.33)
            dp_new = new_result.get('draw_prob', 0.33)
            ap_new = new_result.get('away_win_prob', 0.34)

            pred_new = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_new, 'draw': dp_new, 'away': ap_new}[x])

            if pred_new == actual:
                correct_new += 1
            if pred_new == 'draw':
                draw_pred_new += 1
                if actual == 'draw':
                    draw_correct_new += 1

            # Brier new
            if actual == 'home':   brier_new += (hp_new-1)**2 + dp_new**2 + ap_new**2
            elif actual == 'draw': brier_new += hp_new**2 + (dp_new-1)**2 + ap_new**2
            else:                  brier_new += hp_new**2 + dp_new**2 + (ap_new-1)**2

            # 场景flag统计
            flags = new_result.get('scenario_flags', [])
            for flag in flags:
                flag_counts[flag] += 1
                if pred_new == actual:
                    flag_correct[flag] += 1
                flag_n[flag] += 1
                if actual == 'home':   flag_brier_new[flag] += (hp_new-1)**2 + dp_new**2 + ap_new**2
                elif actual == 'draw': flag_brier_new[flag] += hp_new**2 + (dp_new-1)**2 + ap_new**2
                else:                  flag_brier_new[flag] += hp_new**2 + dp_new**2 + (ap_new-1)**2

            # 动机不对称详细统计
            if 'motivation_mismatch' in flags or 'motivation_mismatch_light' in flags:
                mismatch_stats["triggered"] += 1
                if pred_new == actual:
                    mismatch_stats["triggered_correct"] += 1
                mismatch_stats["triggered_brier_new"] += \
                    ((hp_new-1)**2 + dp_new**2 + ap_new**2 if actual == 'home' else
                     hp_new**2 + (dp_new-1)**2 + ap_new**2 if actual == 'draw' else
                     hp_new**2 + dp_new**2 + (ap_new-1)**2)
                mismatch_stats["triggered_brier_old"] += \
                    ((hp_old-1)**2 + dp_old**2 + ap_old**2 if actual == 'home' else
                     hp_old**2 + (dp_old-1)**2 + ap_old**2 if actual == 'draw' else
                     hp_old**2 + dp_old**2 + (ap_old-1)**2)
                if actual == 'home':   mismatch_stats["home_actual"] += 1
                elif actual == 'draw': mismatch_stats["draw_actual"] += 1
                else:                  mismatch_stats["away_actual"] += 1

            # 月度统计
            month_key = match_month
            monthly_stats[month_key]["n"] += 1
            monthly_stats[month_key]["correct_new"] += (1 if pred_new == actual else 0)
            monthly_stats[month_key]["correct_old"] += (1 if pred_old == actual else 0)
            monthly_stats[month_key]["brier_new"] += \
                ((hp_new-1)**2 + dp_new**2 + ap_new**2 if actual == 'home' else
                 hp_new**2 + (dp_new-1)**2 + ap_new**2 if actual == 'draw' else
                 hp_new**2 + dp_new**2 + (ap_new-1)**2)
            monthly_stats[month_key]["brier_old"] += \
                ((hp_old-1)**2 + dp_old**2 + ap_old**2 if actual == 'home' else
                 hp_old**2 + (dp_old-1)**2 + ap_old**2 if actual == 'draw' else
                 hp_old**2 + dp_old**2 + (ap_old-1)**2)

            # 赔率区间统计
            odds_h = hp_old  # 用欧赔隐含概率估算
            # 从factor数据获取赔率
            conn3 = storage._conn()
            odds_row = conn3.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
                (mk,)
            ).fetchone()
            conn3.close()

            raw_odds_h = 0
            if odds_row:
                odds_data = json.loads(odds_row['data_json'])
                raw_odds_h = float(odds_data.get('raw', {}).get('avg_home_odds', 0) or
                                   odds_data.get('raw', {}).get('closing_avg_home_odds', 0) or 0)

            if raw_odds_h > 0:
                if raw_odds_h < 1.25:
                    odds_key = "<1.25"
                elif raw_odds_h < 1.50:
                    odds_key = "1.25-1.50"
                elif raw_odds_h < 2.50:
                    odds_key = "1.50-2.50"
                elif raw_odds_h < 5.0:
                    odds_key = "2.50-5.00"
                else:
                    odds_key = ">5.00"
                odds_range_stats[odds_key]["n"] += 1
                odds_range_stats[odds_key]["correct_new"] += (1 if pred_new == actual else 0)
                odds_range_stats[odds_key]["correct_old"] += (1 if pred_old == actual else 0)
                odds_range_stats[odds_key]["brier_new"] += \
                    ((hp_new-1)**2 + dp_new**2 + ap_new**2 if actual == 'home' else
                     hp_new**2 + (dp_new-1)**2 + ap_new**2 if actual == 'draw' else
                     hp_new**2 + dp_new**2 + (ap_new-1)**2)
                odds_range_stats[odds_key]["brier_old"] += \
                    ((hp_old-1)**2 + dp_old**2 + ap_old**2 if actual == 'home' else
                     hp_old**2 + (dp_old-1)**2 + ap_old**2 if actual == 'draw' else
                     hp_old**2 + dp_old**2 + (ap_old-1)**2)

            total_n += 1

        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"  ERR {mk}: {str(e)[:80]}")

        # 进度
        if (i + 1) % 2000 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(matches) - i - 1) / rate
            print(f"  [{i+1}/{len(matches)}] n={total_n} err={errors} "
                  f"rate={rate:.1f}/s ETA={eta:.0f}s", flush=True)

    elapsed = time.time() - t0
    print(f"\n  完成! 耗时={elapsed:.1f}s, 有效={total_n}, 错误={errors}")

    # ============================================================
    # 输出结果
    # ============================================================
    print("\n" + "=" * 70)
    print("  v3.5 vs v3.4 全量对比 (13993场)")
    print("=" * 70)

    print(f"\n  === 总体指标 ===")
    print(f"  v3.4: argmax={correct_old}/{total_n}={correct_old/total_n*100:.1f}%  Brier={brier_old/total_n:.4f}")
    print(f"  v3.5: argmax={correct_new}/{total_n}={correct_new/total_n*100:.1f}%  Brier={brier_new/total_n:.4f}")
    print(f"  变化: argmax {(correct_new-correct_old)/total_n*100:+.2f}pp  Brier {(brier_new-brier_old)/total_n:+.4f}")

    print(f"\n  === Draw统计 ===")
    da = draw_actual
    print(f"  实际平局: {da}/{total_n}={da/total_n*100:.1f}%")
    print(f"  v3.4: 预测draw={draw_pred_old} 正确={draw_correct_old} "
          f"precision={draw_correct_old/draw_pred_old*100:.1f}% "
          f"recall={draw_correct_old/da*100:.1f}%")
    print(f"  v3.5: 预测draw={draw_pred_new} 正确={draw_correct_new} "
          f"precision={draw_correct_new/draw_pred_new*100:.1f}% "
          f"recall={draw_correct_new/da*100:.1f}%")

    print(f"\n  === 场景Flag触发统计 ===")
    for flag, cnt in sorted(flag_counts.items(), key=lambda x: x[1], reverse=True):
        n = flag_n[flag]
        acc = flag_correct[flag] / n * 100 if n > 0 else 0
        bs = flag_brier_new[flag] / n if n > 0 else 0
        print(f"  {flag}: 触发{cnt}场({cnt/total_n*100:.2f}%) 准确率={acc:.1f}% Brier={bs:.4f}")

    print(f"\n  === 动机不对称详细分析 ===")
    mm = mismatch_stats
    if mm["triggered"] > 0:
        n = mm["triggered"]
        print(f"  触发场次: {n}")
        print(f"  实际结果: 主胜={mm['home_actual']} 平局={mm['draw_actual']} 客胜={mm['away_actual']}")
        print(f"  v3.5准确率: {mm['triggered_correct']}/{n}={mm['triggered_correct']/n*100:.1f}%")
        print(f"  v3.5 Brier: {mm['triggered_brier_new']/n:.4f}")
        print(f"  v3.4 Brier: {mm['triggered_brier_old']/n:.4f}")
        print(f"  Brier变化: {(mm['triggered_brier_new']-mm['triggered_brier_old'])/n:+.4f}")

    print(f"\n  === 月度统计 (关键月份) ===")
    for month in sorted(monthly_stats.keys()):
        ms = monthly_stats[month]
        n = ms["n"]
        if n < 100:
            continue
        acc_new = ms["correct_new"] / n * 100
        acc_old = ms["correct_old"] / n * 100
        bs_new = ms["brier_new"] / n
        bs_old = ms["brier_old"] / n
        month_name = f"{month}月"
        print(f"  {month_name}: n={n} "
              f"v3.4={acc_old:.1f}%/B{bs_old:.4f} "
              f"v3.5={acc_new:.1f}%/B{bs_new:.4f} "
              f"Δacc={acc_new-acc_old:+.1f}pp ΔB={bs_new-bs_old:+.4f}")

    print(f"\n  === 赔率区间统计 ===")
    odds_order = ["<1.25", "1.25-1.50", "1.50-2.50", "2.50-5.00", ">5.00"]
    for odds_key in odds_order:
        if odds_key in odds_range_stats:
            os = odds_range_stats[odds_key]
            n = os["n"]
            if n == 0:
                continue
            acc_new = os["correct_new"] / n * 100
            acc_old = os["correct_old"] / n * 100
            bs_new = os["brier_new"] / n
            bs_old = os["brier_old"] / n
            print(f"  {odds_key}: n={n} "
                  f"v3.4={acc_old:.1f}%/B{bs_old:.4f} "
                  f"v3.5={acc_new:.1f}%/B{bs_new:.4f} "
                  f"Δacc={acc_new-acc_old:+.1f}pp ΔB={bs_new-bs_old:+.4f}")

    print(f"\n{'=' * 70}")
    print("  验证完成")
    print("=" * 70)


if __name__ == "__main__":
    main()