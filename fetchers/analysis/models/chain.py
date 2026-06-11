"""
串联预测模型 v1 (Chain Model)

预测链: 赔率→泊松进球λ→比分概率矩阵→1X2基础概率→基本面增量调整→最终概率

与enhanced_linear的区别:
1. enhanced_linear: 各因素加权→信号→映射概率 (平行结构)
2. chain: 赔率→泊松→1X2基础概率→基本面调整 (串联结构)

串联优势:
- 泊松模型从赔率O/U推算，物理上更合理
- 基本面只做增量调整，不重复赔率已包含的信息
- 调整幅度有物理约束（不会大幅偏离泊松基础）
"""

import math
from typing import Dict, Any
from fetchers.analysis.base_model import BaseModel


class ChainModel(BaseModel):
    model_name = "chain"
    model_version = "1.0"

    # 基本面调整系数
    FUNDAMENTAL_SCALE = 0.08  # 基本面最大调整幅度（单因素）

    # 泊松平局校准
    POISSON_DRAW_BLEND = 0.35  # 泊松平局概率的权重

    # 基本面因素权重（归一化后使用）
    FUNDAMENTAL_WEIGHTS = {
        "motivation":         1.0,   # 动机差异 → 最强基本面信号
        "rest_days":          0.7,   # 赛程密度/疲劳
        "injury":             0.6,   # 伤病影响
        "elo_rating":         0.5,   # Elo差异（补充泊松未覆盖的实力差）
        "h2h":                0.4,   # 历史交锋
        "schedule_difficulty":0.3,   # 赛程难度
        "form":               0.2,   # 近期状态（弱信号）
        "home_away_deep":     0.2,   # 主客场深度
        "possession_counter": 0.1,   # 控球反击
    }

    def predict(self, match_key: str, factors: Dict[str, Dict],
                storage) -> Dict[str, Any]:

        # === Step 1: 从泊松模型获取基础概率 ===
        poisson_f = factors.get("poisson")
        if poisson_f and poisson_f.get("confidence", 0) > 0:
            base_home = poisson_f.get("home_value", 0.43)
            base_draw = poisson_f.get("draw_prob", 0.25)
            base_away = poisson_f.get("away_value", 0.32)
            poisson_source = poisson_f.get("raw", {}).get("lambda_source", "standings")
            home_lambda = poisson_f.get("raw", {}).get("home_lambda", 1.3)
            away_lambda = poisson_f.get("raw", {}).get("away_lambda", 1.1)
        else:
            # 无泊松数据，用先验
            base_home = 0.43
            base_draw = 0.25
            base_away = 0.32
            poisson_source = "prior"
            home_lambda = 1.3
            away_lambda = 1.1

        # === Step 2: 用欧赔修正基础概率 ===
        euro_f = factors.get("euro_odds")
        if euro_f and euro_f.get("confidence", 0) > 0:
            market_home = euro_f.get("home_value", 0)
            market_away = euro_f.get("away_value", 0)
            market_draw = euro_f.get("raw", {}).get("draw_prob", 0)
            if market_home > 0 and market_away > 0 and market_draw > 0:
                # 赔率概率优先（0.7权重），泊松做补充（0.3权重）
                base_home = 0.7 * market_home + 0.3 * base_home
                base_draw = 0.7 * market_draw + 0.3 * base_draw
                base_away = 0.7 * market_away + 0.3 * base_away
                # 归一化
                total = base_home + base_draw + base_away
                base_home /= total
                base_draw /= total
                base_away /= total

        # === Step 3: 亚盘平局校准 ===
        ah_f = factors.get("asian_handicap")
        if ah_f and ah_f.get("confidence", 0) > 0:
            ah_hc = ah_f.get("raw", {}).get("closing_handicap", None)
            if ah_hc is not None:
                abs_hc = abs(float(ah_hc))
                ah_draw = self._ah_draw_rate(abs_hc)
                # 亚盘平局概率 blend 0.4
                base_draw = 0.6 * base_draw + 0.4 * ah_draw
                # 调整胜负以保持总和=1
                non_draw = 1 - base_draw
                ratio = base_home / (base_home + base_away) if (base_home + base_away) > 0 else 0.57
                base_home = non_draw * ratio
                base_away = non_draw * (1 - ratio)

        # === Step 4: 基本面增量调整 ===
        adjustments = {}
        total_adjust_h = 0
        total_adjust_d = 0
        total_adjust_a = 0

        for fname, weight in self.FUNDAMENTAL_WEIGHTS.items():
            f = factors.get(fname)
            if not f or f.get("confidence", 0) <= 0:
                continue
            if f.get("type") != "numeric":
                continue

            diff = f.get("diff", 0)
            conf = f.get("confidence", 1.0)
            eff = diff * conf * weight * self.FUNDAMENTAL_SCALE

            # diff > 0: 主队优势 → home↑ away↓
            # diff < 0: 客队优势 → away↑ home↓
            # 平局: 当双方实力差变化大时，平局概率下降
            total_adjust_h += eff
            total_adjust_a -= eff
            # 平局调整：强信号偏离 → 平局下降
            total_adjust_d -= abs(eff) * 0.3

            adjustments[fname] = round(eff, 4)

        # 应用调整
        home_prob = base_home + total_adjust_h
        away_prob = base_away + total_adjust_a
        draw_prob = base_draw + total_adjust_d

        # Clamp before normalize to avoid negative probs
        home_prob = max(0.001, home_prob)
        draw_prob = max(0.001, draw_prob)
        away_prob = max(0.001, away_prob)

        # 归一化
        hp, dp, ap = self._normalize_probs(home_prob, draw_prob, away_prob)

        # === Step 5: 大小球 ===
        over_signal = 0.0
        over_weight = 0.0
        for fname in ["over_under", "poisson", "expected_goals"]:
            f = factors.get(fname)
            if not f or f.get("confidence", 0) <= 0 or f.get("type") != "numeric":
                continue
            w = 0.33
            c = f.get("confidence", 1.0)
            if fname == "over_under":
                wd = f.get("raw", {}).get("water_diff", 0)
                over_signal += wd * w * c
            if fname == "poisson":
                o25 = f.get("raw", {}).get("over_2_5_prob", 0)
                if o25:
                    over_signal += (o25 - 0.5) * w * c
            if fname == "expected_goals":
                hv = f.get("home_value", 0)
                av = f.get("away_value", 0)
                if hv and av:
                    over_signal += (hv + av - 2.5) * 0.1 * w * c
            over_weight += w * c

        if over_weight > 0:
            over_2_5 = 0.5 + 0.2 * math.tanh((over_signal / over_weight) * 3)
        else:
            over_2_5 = 0.5
        over_2_5 = round(max(0.1, min(0.9, over_2_5)), 4)

        # === Step 6: 置信度 & EV ===
        active_factors = len(adjustments)
        coverage = min(1.0, active_factors / len(self.FUNDAMENTAL_WEIGHTS))
        confidence = round(0.3 + coverage * 0.4 + (0.3 if poisson_source == "odds" else 0.1), 2)
        confidence = min(0.95, confidence)

        # 信号方向
        signal = hp - ap
        if signal > 0.03:
            signal_dir = "home"
        elif signal < -0.03:
            signal_dir = "away"
        else:
            signal_dir = "draw"

        # EV
        ev = {}
        if euro_f:
            raw = euro_f.get("raw", {})
            ev_h = raw.get("closing_avg_home_odds") or raw.get("avg_home_odds", 0)
            ev_d = raw.get("closing_avg_draw_odds") or raw.get("avg_draw_odds", 0)
            ev_a = raw.get("closing_avg_away_odds") or raw.get("avg_away_odds", 0)
            try:
                ev_h = float(ev_h); ev_d = float(ev_d); ev_a = float(ev_a)
                if ev_h > 1 and ev_d > 1 and ev_a > 1:
                    margin = 1/ev_h + 1/ev_d + 1/ev_a
                    ev["home"] = round(hp * ev_h * margin - 1, 4)
                    ev["draw"] = round(dp * ev_d * margin - 1, 4)
                    ev["away"] = round(ap * ev_a * margin - 1, 4)
            except (ValueError, ZeroDivisionError, TypeError):
                pass

        # 最可能比分
        top_scores = poisson_f.get("raw", {}).get("top5_scores", []) if poisson_f else []
        most_likely = poisson_f.get("raw", {}).get("most_likely_score", "") if poisson_f else ""

        return {
            "home_win_prob": hp,
            "draw_prob": dp,
            "away_win_prob": ap,
            "over_2_5_prob": over_2_5,
            "under_2_5_prob": round(1 - over_2_5, 4),
            "confidence": confidence,
            "signal_direction": signal_dir,
            "signal_value": round(signal, 4),
            "ev": ev,
            "active_factors": active_factors,
            "adjustments": adjustments,
            "base_probs": {
                "home": round(base_home, 4),
                "draw": round(base_draw, 4),
                "away": round(base_away, 4),
            },
            "poisson_source": poisson_source,
            "home_lambda": round(home_lambda, 3),
            "away_lambda": round(away_lambda, 3),
            "most_likely_score": most_likely,
            "top5_scores": top_scores[:5],
        }

    # 亚盘平局概率表
    AH_DRAW_RATES = {
        0.00: 0.315, 0.25: 0.301, 0.50: 0.268,
        0.75: 0.250, 1.00: 0.239, 1.50: 0.191, 2.00: 0.128,
    }

    def _ah_draw_rate(self, abs_handicap):
        hc = abs_handicap
        breakpoints = sorted(self.AH_DRAW_RATES.keys())
        if hc <= breakpoints[0]:
            return self.AH_DRAW_RATES[breakpoints[0]]
        if hc >= breakpoints[-1]:
            return self.AH_DRAW_RATES[breakpoints[-1]]
        for i in range(len(breakpoints) - 1):
            lo, hi = breakpoints[i], breakpoints[i + 1]
            if lo <= hc <= hi:
                t = (hc - lo) / (hi - lo)
                return self.AH_DRAW_RATES[lo] + t * (self.AH_DRAW_RATES[hi] - self.AH_DRAW_RATES[lo])
        return 0.26