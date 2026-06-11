"""
基础线性概率模型

拿所有数值型因素的 diff 做加权求和，映射到概率。
权重可调，存在模型参数里，后续可回测优化。
"""

from typing import Dict, Any
from fetchers.analysis.base_model import BaseModel


class BasicLinearModel(BaseModel):
    model_name = "basic_linear"
    model_version = "1.0"

    # 因素权重（经回测优化）
    WEIGHTS = {
        "standing":           0.16,
        "form":               0.10,
        "home_away":          0.06,
        "home_away_deep":     0.06,
        "euro_odds":          0.24,
        "asian_handicap":     0.06,
        "over_under":         0.02,
        "prediction":         0.08,
        "expected_goals":     0.04,
        "poisson":            0.04,
        "h2h":                0.05,
        "schedule_difficulty":0.04,
    }

    # 分类因素的额外调整
    CATEGORICAL_ADJUST = {
        "motivation": {
            ("title_race", "mid_table"):      +0.03,
            ("title_race", "dead_rubber"):    +0.04,
            ("title_race", "relegation"):     +0.02,
            ("relegation", "mid_table"):      -0.02,
            ("relegation_battle", "mid_table"):-0.03,
            ("dead_rubber", "title_race"):    -0.04,
            ("dead_rubber", "relegation"):    -0.03,
        },
        "rivalry": {
            ("derby", "derby"): 0.0,
        },
        "giant_killer": {
            ("giant_killer", "normal"):       +0.02,
            ("flat_track_bully", "normal"):   -0.02,
        },
        "rotation": {
            ("likely", "unlikely"):           -0.03,
            ("unlikely", "likely"):           +0.03,
            ("likely", "likely"):             0.0,
        },
        "lineup": {
            ("attacking", "defensive"):       +0.01,
            ("defensive", "attacking"):       -0.01,
        },
    }

    # 基础概率（主场优势先验）
    HOME_PRIOR = 0.42
    DRAW_PRIOR = 0.28
    AWAY_PRIOR = 0.30

    def predict(self, match_key: str, factors: Dict[str, Dict],
                storage) -> Dict[str, Any]:

        weighted_signal = 0.0
        total_weight = 0.0
        contributions = {}
        used_weights = {}
        over_signal = 0.0
        over_weight = 0.0

        for fname, weight in self.WEIGHTS.items():
            f = factors.get(fname)
            if not f or f.get("confidence", 0) <= 0:
                continue
            if f.get("type") != "numeric":
                continue

            diff = f.get("diff", 0)
            conf = f.get("confidence", 1.0)

            eff_weight = weight * conf
            contribution = diff * eff_weight
            weighted_signal += contribution
            total_weight += eff_weight
            contributions[fname] = round(contribution, 4)
            used_weights[fname] = round(eff_weight, 4)

            # 大小球信号
            if fname == "over_under":
                wd = f.get("raw", {}).get("water_diff", 0)
                over_signal += wd * eff_weight
                over_weight += eff_weight
            if fname == "poisson":
                o25 = f.get("raw", {}).get("over_2_5_prob", 0)
                if o25:
                    over_signal += (o25 - 0.5) * eff_weight
                    over_weight += eff_weight

        # 分类因素调整
        for fname, adjustments in self.CATEGORICAL_ADJUST.items():
            f = factors.get(fname)
            if not f or f.get("confidence", 0) <= 0:
                continue
            hc = f.get("home_category", "")
            ac = f.get("away_category", "")
            adj = adjustments.get((hc, ac), 0)
            weighted_signal += adj
            contributions[fname] = round(adj, 4)

        # 映射到概率
        if total_weight > 0:
            signal = weighted_signal / total_weight
        else:
            signal = 0

        # 用 sigmoid 映射 signal 到概率调整
        import math
        home_adj = 0.15 * math.tanh(signal * 3)
        home_prob = self.HOME_PRIOR + home_adj
        away_prob = self.AWAY_PRIOR - home_adj * 0.7
        draw_prob = self.DRAW_PRIOR - home_adj * 0.3

        hp, dp, ap = self._normalize_probs(home_prob, draw_prob, away_prob)

        # 大小球
        if over_weight > 0:
            over_2_5 = 0.5 + 0.2 * math.tanh((over_signal / over_weight) * 3)
        else:
            over_2_5 = 0.5
        over_2_5 = round(max(0.1, min(0.9, over_2_5)), 4)

        # 置信度
        active_count = len(used_weights)
        coverage = min(1.0, active_count / len(self.WEIGHTS))
        confidence = round(coverage * 0.7 + (total_weight / sum(self.WEIGHTS.values())) * 0.3, 2)

        # 信号汇总
        if signal > 0.05:
            signal_dir = "home"
        elif signal < -0.05:
            signal_dir = "away"
        else:
            signal_dir = "draw"

        return {
            "home_win_prob": hp,
            "draw_prob": dp,
            "away_win_prob": ap,
            "over_2_5_prob": over_2_5,
            "under_2_5_prob": round(1 - over_2_5, 4),
            "confidence": confidence,
            "signal_direction": signal_dir,
            "signal_value": round(signal, 4),
            "factor_weights_used": used_weights,
            "factor_contributions": contributions,
            "active_factors": active_count,
        }