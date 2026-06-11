"""
回测+权重优化

从DB读取已完赛比赛的因素+实际结果，
用简单网格搜索找到最优权重组合。
"""

import json
import math
from itertools import product
from fetchers.storage.database import get_connection, get_db_path


def load_backtest_data():
    """加载所有已完赛比赛的因素+实际结果"""
    conn = get_connection(get_db_path())

    model_mks = conn.execute(
        "SELECT DISTINCT match_key FROM match_data WHERE source='model'"
    ).fetchall()

    records = []
    for r in model_mks:
        mk = r[0]

        # 实际比分
        sr = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND data_type='match'",
            (mk,)
        ).fetchone()
        if not sr:
            continue
        sd = json.loads(sr[0])
        hs = sd.get('home_score', '')
        aws = sd.get('away_score', '')
        try:
            hs, aws = int(hs), int(aws)
        except (ValueError, TypeError):
            continue

        actual = 1 if hs > aws else 0 if hs == aws else -1  # 1=home, 0=draw, -1=away

        # 因素数据
        factor_rows = conn.execute(
            "SELECT data_type, data_json FROM match_data "
            "WHERE match_key=? AND source='factor'",
            (mk,)
        ).fetchall()

        factors = {}
        for fr in factor_rows:
            name = fr[0].replace("factor:", "")
            factors[name] = json.loads(fr[1])

        records.append({
            "match_key": mk,
            "actual": actual,
            "factors": factors,
        })

    conn.close()
    return records


def predict_with_weights(factors, weights, categorical_adjust):
    """用给定权重计算预测信号"""
    weighted_signal = 0.0
    total_weight = 0.0

    for fname, weight in weights.items():
        f = factors.get(fname)
        if not f or f.get("confidence", 0) <= 0:
            continue
        if f.get("type") != "numeric":
            continue
        diff = f.get("diff", 0)
        conf = f.get("confidence", 1.0)
        eff_weight = weight * conf
        weighted_signal += diff * eff_weight
        total_weight += eff_weight

    # 分类因素
    for fname, adjustments in categorical_adjust.items():
        f = factors.get(fname)
        if not f or f.get("confidence", 0) <= 0:
            continue
        hc = f.get("home_category", "")
        ac = f.get("away_category", "")
        adj = adjustments.get((hc, ac), 0)
        weighted_signal += adj

    if total_weight > 0:
        return weighted_signal / total_weight
    return 0


def signal_to_pred(signal):
    """信号 → 预测方向"""
    if signal > 0.03:
        return 1  # home
    elif signal < -0.03:
        return -1  # away
    else:
        return 0  # draw


def accuracy(records, weights, categorical_adjust):
    """计算给定权重的准确率"""
    correct = 0
    total = 0
    for rec in records:
        pred = signal_to_pred(predict_with_weights(rec["factors"], weights, categorical_adjust))
        if pred == rec["actual"]:
            correct += 1
        total += 1
    return correct / total if total else 0


def grid_search(records):
    """网格搜索最优权重"""
    # 可调权重及其搜索范围
    weight_ranges = {
        "standing":    [0.08, 0.12, 0.16, 0.20],
        "form":        [0.06, 0.10, 0.14, 0.18],
        "home_away":   [0.03, 0.06, 0.09],
        "euro_odds":   [0.12, 0.16, 0.20, 0.24],
        "asian_handicap": [0.06, 0.10, 0.14],
        "prediction":  [0.04, 0.08, 0.12],
        "h2h":         [0.02, 0.05, 0.08],
        "poisson":     [0.02, 0.04, 0.06],
        "expected_goals": [0.02, 0.04, 0.06],
    }

    # 固定权重（数据少的因素）
    fixed = {
        "home_away_deep": 0.06,
        "over_under": 0.02,
        "schedule_difficulty": 0.04,
    }

    categorical_adjust = {
        "motivation": {
            ("title_race", "mid_table"): +0.03,
            ("title_race", "dead_rubber"): +0.04,
            ("title_race", "relegation"): +0.02,
            ("relegation", "mid_table"): -0.02,
            ("relegation_battle", "mid_table"): -0.03,
            ("dead_rubber", "title_race"): -0.04,
            ("dead_rubber", "relegation"): -0.03,
        },
        "rivalry": {("derby", "derby"): 0.0},
        "giant_killer": {
            ("giant_killer", "normal"): +0.02,
            ("flat_track_bully", "normal"): -0.02,
        },
        "rotation": {
            ("likely", "unlikely"): -0.03,
            ("unlikely", "likely"): +0.03,
            ("likely", "likely"): 0.0,
        },
        "lineup": {
            ("attacking", "defensive"): +0.01,
            ("defensive", "attacking"): -0.01,
        },
    }

    # 只搜索最重要的4个因素（全搜索太慢）
    search_keys = ["standing", "form", "euro_odds", "asian_handicap"]
    best_acc = 0
    best_weights = None

    print(f"Grid search on {len(records)} matches...")
    print(f"Searching: {search_keys}")

    combos = list(product(*[weight_ranges[k] for k in search_keys]))
    print(f"Total combinations: {len(combos)}")

    for i, vals in enumerate(combos):
        weights = dict(fixed)
        for j, k in enumerate(search_keys):
            weights[k] = vals[j]
        # 补充剩余权重
        for k in weight_ranges:
            if k not in search_keys:
                weights[k] = weight_ranges[k][1]  # 取中间值

        acc = accuracy(records, weights, categorical_adjust)
        if acc > best_acc:
            best_acc = acc
            best_weights = dict(weights)
            print(f"  New best: {acc:.4f} with {dict(zip(search_keys, vals))}")

    return best_acc, best_weights


if __name__ == "__main__":
    records = load_backtest_data()
    print(f"Loaded {len(records)} finished matches for backtesting")

    # 基线
    baseline = sum(1 for r in records if r["actual"] == 1) / len(records)
    print(f"Always-home baseline: {baseline:.4f}")

    # 当前权重
    current_weights = {
        "standing": 0.15, "form": 0.12, "home_away": 0.06,
        "home_away_deep": 0.06, "euro_odds": 0.18, "asian_handicap": 0.10,
        "over_under": 0.02, "prediction": 0.08, "expected_goals": 0.04,
        "poisson": 0.04, "h2h": 0.05, "schedule_difficulty": 0.04,
    }
    current_cat = {
        "motivation": {
            ("title_race", "mid_table"): +0.03,
            ("title_race", "dead_rubber"): +0.04,
            ("title_race", "relegation"): +0.02,
            ("relegation", "mid_table"): -0.02,
            ("relegation_battle", "mid_table"): -0.03,
            ("dead_rubber", "title_race"): -0.04,
            ("dead_rubber", "relegation"): -0.03,
        },
        "rivalry": {("derby", "derby"): 0.0},
        "giant_killer": {
            ("giant_killer", "normal"): +0.02,
            ("flat_track_bully", "normal"): -0.02,
        },
        "rotation": {
            ("likely", "unlikely"): -0.03,
            ("unlikely", "likely"): +0.03,
        },
        "lineup": {("attacking", "defensive"): +0.01, ("defensive", "attacking"): -0.01},
    }
    cur_acc = accuracy(records, current_weights, current_cat)
    print(f"Current weights accuracy: {cur_acc:.4f}")

    # Grid search
    best_acc, best_weights = grid_search(records)
    print(f"\nBest accuracy: {best_acc:.4f}")
    print(f"Best weights: {best_weights}")

    # Apply best weights and re-run model
    if best_weights and best_acc > cur_acc:
        print("\nUpdating model weights...")
        from fetchers.analysis.models.basic_linear import BasicLinearModel
        BasicLinearModel.WEIGHTS = best_weights
        print("Weights updated. Run analyze_all to re-model.")
