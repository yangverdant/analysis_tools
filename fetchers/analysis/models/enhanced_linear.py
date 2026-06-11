"""
增强线性模型 v3

核心改进（相比v2）：
1. 泊松进球建模 — draw_prob从物理模型推导，而非线性调整
2. 亚盘校准 — |AH|接近0时提升平局概率（AH包含独立平局信息）
3. 信号覆盖 — 当信号强烈反对欧赔方向时翻转
4. EV输出 — 模型概率×赔率-1，为凯利公式提供依据
"""

import math
from typing import Dict, Any
from fetchers.analysis.base_model import BaseModel


class EnhancedLinearModel(BaseModel):
    model_name = "enhanced_linear"
    model_version = "3.9.2"

    # 因素权重（逻辑回归从13993场历史数据学习，v3.2）
    WEIGHTS = {
        "standing":           0.02,
        "form":               0.01,
        "home_away":          0.03,
        "home_away_deep":     0.01,
        "euro_odds":          0.28,
        "asian_handicap":     0.04,
        "over_under":         0.02,
        "prediction":         0.10,
        "expected_goals":     0.04,
        "poisson":            0.03,
        "h2h":                0.04,
        "schedule_difficulty":0.01,
        "rest_days":          0.01,
        "elo_rating":         0.08,
        "possession_counter": 0.02,
        "odds_movement":      0.10,
        "injury":             0.03,
        "motivation":         0.04,
    }

    # 交互项: (因素A, 因素B, 交互强度)
    # 当两个因素的信号同向时，增强效果
    INTERACTIONS = [
        ("standing", "euro_odds", 0.04),
        ("standing", "form", 0.03),
        ("form", "home_away_deep", 0.02),
        ("euro_odds", "asian_handicap", 0.03),
        ("prediction", "poisson", 0.02),
        ("h2h", "form", 0.02),
        ("elo_rating", "euro_odds", 0.03),
        ("elo_rating", "form", 0.02),
        ("rest_days", "home_away", 0.02),
        ("odds_movement", "euro_odds", 0.05),   # CLV+赔率一致 → 最强信号
        ("odds_movement", "elo_rating", 0.03),  # CLV+Elo一致 → 市场验证实力
        ("injury", "odds_movement", 0.02),      # 伤病+赔率异动 → 信息确认
        ("motivation", "euro_odds", 0.03),      # 动机+赔率一致 → 战意验证
        ("motivation", "odds_movement", 0.02),  # 动机+赔率异动 → 信息差
    ]

    # 分类因素调整
    CATEGORICAL_ADJUST = {
        "rivalry": {("derby", "derby"): 0.0},
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
        "possession_counter": {
            ("possession", "counter_attack"): -0.02,
            ("counter_attack", "possession"): +0.02,
            ("possession", "balanced"):       +0.01,
            ("counter_attack", "counter_attack"): 0.0,
        },
    }

    # 主场先验 — 实际分布: home~43%, draw~25%, away~32%
    HOME_PRIOR = 0.43
    DRAW_PRIOR = 0.25
    AWAY_PRIOR = 0.32

    # 信号→概率映射参数
    SIGNAL_SCALE = 2.5        # signal放大系数
    DRAW_PEAK = 0.35          # signal=0时平局概率峰值
    DRAW_DECAY = 100.0        # 平局衰减速率（大值=平局概率更平滑）
    HOME_ADJ_SCALE = 0.15     # 主胜调整幅度

    # 信号覆盖参数（经回测优化）
    # 当信号强烈反对欧赔方向时，增大调整幅度
    SIGNAL_OVERRIDE_THRESHOLD = 0.15  # 信号翻转阈值（grid search最优）
    SIGNAL_OVERRIDE_CONF = 0.45      # 欧赔置信度阈值（grid search最优）
    SIGNAL_DRAW_THRESHOLD = 0.02     # 信号偏平局阈值（grid search最优）
    SIGNAL_DRAW_EURO = 0.30         # 欧赔平局概率阈值（grid search最优）

    # 赔率平局阈值规则（v3.8数据驱动修正）
    # 13993场完整验证: draw_threshold规则整体对argmax有负贡献
    # dt30(≥0.30): v3.4 boost=0.05→改错284场(净-292)。0.01为最优值(净+66场)
    #   但dt30触发时亚盘blend(0.50)和dt30叠加导致draw概率过高
    #   实验证明在dt30触发后额外减2pp draw概率 → 总体净+78场
    # dt28(≥0.28): 从0.03降至0.01: 减少对赔率方向的干扰
    # dt26(≥0.26): 从0.015降至0.005: 轻微补偿
    DRAW_PROB_THRESHOLDS = {
        0.30: 0.01,   # 从0.05大幅降低
        0.28: 0.01,   # 从0.03降低
        0.26: 0.005,  # 从0.015降低
    }
    # dt30触发后分档减draw概率(补偿亚盘blend过高)
    # AH=0(平手盘): 亚盘blend(0.50)+dt30叠加最严重 → base+ah0_extra
    # AH≠0或无AH:   叠加较轻 → 只用base
    # 实验(13993场): base0.01+ah0.02 → argmax=50.10% Brier=0.6042 net+67
    #   vs 统一0.02 → argmax=50.09% Brier=0.6043 net+65
    DT30_BASE_DP_REDUCE = 0.01
    DT30_AH0_EXTRA_DP_REDUCE = 0.02

    # 分赛事参数
    # 杯赛draw过度问题: 模型预测draw precision仅21%, 减0.02pp → +0.22pp argmax, +31 net
    CUP_DP_REDUCE = 0.02
    CUP_KEYWORDS = ["Champions League", "champions_league", "Europa League", "europa_league",
                    "Conference League", "conference_league", "Libertadores", "libertadores",
                    "Sudamericana", "sudamericana", "Copa Libertadores", "copa_libertadores",
                    "Copa Sudamericana", "copa_sudamericana", "ACL", "asian_champions",
                    "Asian Champions", "world_cup", "World Cup"]

    # 二级联赛dt30参数: draw率更高, dt30 boost更易出错
    DIV2_DT30_BOOST = 0.00       # 二级联赛dt30 boost=0(不给draw boost)
    DIV2_DT30_BASE_DP_REDUCE = 0.02  # 二级联赛dt30 base reduce更大
    DIV2_DT30_AH0_EXTRA_DP_REDUCE = 0.02
    DIV2_KEYWORDS = ["serie_b", "la_liga_2", "ligue_2", "2_bundesliga", "segunda",
                     "Serie B", "La Liga 2", "Ligue 2", "2. Bundesliga", "Segunda",
                     "efl_championship", "EFL Championship", "Championship"]

    # 分联赛draw修正: 数据验证, 140场draw预测仅17%精度
    LEAGUE_DP_REDUCE = {
        "primeira_liga": 0.02, "Primeira Liga": 0.02,
    }

    # 赛季末均衡draw回调（v3.9.2新增）
    # DB验证: 赛季末5轮+均衡(both<3.0)+draw隐含>=0.28 → 实际draw率比隐含高+4~9%
    # b365 14119场验证: +0.01% argmax, Brier持平
    # 回测6场解放者杯: 双方同需赢→2/2打出平局, 方向确认
    LATE_SEASON_DRAW_BOOST = 0.01          # draw概率回调量
    LATE_SEASON_DRAW_WINDOW = 5            # 赛季末最后N轮触发
    LATE_SEASON_BALANCED_THRESHOLD = 3.0   # 双方赔率都<此值视为均衡
    LATE_SEASON_DRAW_THRESHOLD = 0.28      # draw隐含概率>=此值才触发

    # 全球赔率冷门区（赔率1.25-1.35，仅5-6月赛季末生效）
    # 4月无动机数据时此区间冷门率仅15%，5月动机不对称时达88.9%
    # 全年不触发，5-6月结合动机不对称再触发
    GLOBAL_UPSET_ODDS_RANGE = (1.25, 1.35)
    GLOBAL_UPSET_ADJUST = 0.02
    GLOBAL_UPSET_MONTHS = [5, 6]  # 仅赛季末触发

    # 南美杯赛冷门区（赔率1.35-1.50，仅南美杯赛/解放者杯）
    SA_LEAGUE_KEYWORDS = ["Libertadores", "libertadores", "Sudamericana", "sudamericana",
                          "Copa Libertadores", "copa_libertadores"]

    # 动机不对称规则（v3.5数据驱动修正）
    # 低赔率区(odds<=1.50): dead_rubber vs relegation 主胜率80%
    #   — 不对称反而强化了主胜，不应削弱! 13场验证69%主胜
    # 高赔率区(odds>=2.0): dead_rubber vs relegation 主胜率23%/客胜49%
    #   — 模型本身已倾向客胜，不需要额外调整
    # 结论: 低赔率动机不对称 → 主胜+2pp（强化主胜而非削弱）
    MOTIVATION_MISMATCH_THRESHOLD = -1.0  # motivation diff阈值
    MOTIVATION_MISMATCH_MAX_ODDS = 1.50   # 赔率上限（低赔率区才触发）
    MOTIVATION_MISMATCH_ADJUST = 0.02     # 主胜+2pp（方向修正：不对称强化主胜）
    MOTIVATION_MISMATCH_END_MONTHS = [4, 5, 6]  # 4-6月赛季末段生效

    # 杯赛小组赛低赔率不安全规则
    # 触发条件: 杯赛+赔率<1.40 → 主胜-2pp
    # 放宽：1.25→1.40，杯赛赔率1.25-1.40区间冷门率也较高
    # 帕尔梅拉斯1.17解放者杯→客胜, 弗鲁米嫩塞1.16→差点爆冷
    CUP_LEAGUE_KEYWORDS = ["Champions League", "champions_league", "Europa League", "europa_league",
                           "Conference League", "conference_league", "Libertadores", "libertadores",
                           "Sudamericana", "sudamericana", "Copa Libertadores", "copa_libertadores",
                           "Copa Sudamericana", "copa_sudamericana", "ACL", "asian_champions",
                           "Asian Champions"]
    CUP_LOW_ODDS_THRESHOLD = 1.40
    CUP_LOW_ODDS_ADJUST = 0.02

    # 高海拔主场规则
    # 玻利维亚(拉巴斯3600m)/秘鲁(库斯科3400m)/厄瓜多尔(基多2850m)
    # 物理优势: 高原反应→客队体能快速下降，赔率无法完全反映
    ALTITUDE_TEAMS = [
        "Always Ready", "Bolivar", "The Strongest", "Jorge Wilstermann",
        "Real Potosi", "Oriente Petrolero",  # 玻利维亚
        "Cienciano", "Cusco FC", "Universidad San Martin",  # 秘鲁
        "LDU Quito", "Universidad Catolica Ecuador", "Aucas",  # 厄瓜多尔
        "Deportivo Cali", "Atletico Nacional",  # 哥伦比亚高地
    ]
    ALTITUDE_ADJUST = 0.05  # 主队赔率>2.0时，主胜+5pp

    # 亚盘盘口→经验平局概率（实测数据）
    AH_DRAW_RATES = {
        0.00:  0.315,   # 平手盘
        0.25:  0.301,   # 平手/平半
        0.50:  0.268,   # 半球
        0.75:  0.250,   # 半一
        1.00:  0.239,   # 一球
        1.50:  0.191,   # 球半
        2.00:  0.128,   # 两球+
    }
    # draw_prob校准策略:
    # 有亚盘 → AH经验校准(blend=0.50，保守于0.65最优，兼顾准确率)
    # 有泊松 → 泊松进球模型校准(blend=0.30)
    # 都有 → 取两者平均
    AH_DRAW_BLEND = 0.50
    POISSON_DRAW_BLEND = 0.30

    def _ah_draw_rate(self, abs_handicap):
        """根据|AH|查表获取经验平局概率（线性插值）"""
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

    def predict(self, match_key: str, factors: Dict[str, Dict],
                storage) -> Dict[str, Any]:

        # ---- 场景检测（提前，用于调整基本面权重） ----
        clv_f = factors.get("odds_movement")
        mot_f = factors.get("motivation")
        rest_f = factors.get("rest_days")

        # 基本面场景增强倍率
        fundamental_boost = 1.0
        scenario_flags = []

        if clv_f and mot_f and clv_f.get("confidence", 0) > 0 and mot_f.get("confidence", 0) > 0:
            clv_diff = clv_f.get("diff", 0)
            mot_diff = mot_f.get("diff", 0)
            if abs(clv_diff) > 0.03 and abs(mot_diff) > 0.3 and clv_diff * mot_diff > 0:
                fundamental_boost = 2.5  # CLV+动机同向 → 基本面信号放大2.5倍
                scenario_flags.append("clv_motivation_aligned")

        if rest_f and rest_f.get("confidence", 0) > 0:
            home_rest = rest_f.get("home_value", 7)
            away_rest = rest_f.get("away_value", 7)
            if min(home_rest, away_rest) < 4:
                fundamental_boost = max(fundamental_boost, 1.8)  # 疲劳场景
                scenario_flags.append("fatigue")

        # 基本面因素列表（非赔率/市场因素）
        FUNDAMENTAL_FACTORS = {"standing", "form", "home_away", "home_away_deep",
                               "h2h", "schedule_difficulty", "rest_days",
                               "elo_rating", "possession_counter", "injury",
                               "motivation"}

        # ---- 数值因素 ----
        weighted_signal = 0.0
        total_weight = 0.0
        contributions = {}
        used_weights = {}
        factor_signals = {}  # 记录每个因素的信号方向，用于交互计算

        for fname, weight in self.WEIGHTS.items():
            f = factors.get(fname)
            if not f or f.get("confidence", 0) <= 0:
                continue
            if f.get("type") != "numeric":
                continue

            diff = f.get("diff", 0)
            conf = f.get("confidence", 1.0)
            # 场景增强：基本面因素在优势场景中放大
            eff_weight = weight * conf
            if fname in FUNDAMENTAL_FACTORS:
                eff_weight *= fundamental_boost
            contribution = diff * eff_weight
            weighted_signal += contribution
            total_weight += eff_weight
            contributions[fname] = round(contribution, 4)
            used_weights[fname] = round(eff_weight, 4)
            factor_signals[fname] = 1 if diff > 0 else -1 if diff < 0 else 0

        # ---- 交互项 ----
        interaction_total = 0.0
        for fa, fb, strength in self.INTERACTIONS:
            sa = factor_signals.get(fa, 0)
            sb = factor_signals.get(fb, 0)
            # 同向增强，反向削弱
            if sa != 0 and sb != 0 and sa == sb:
                boost = strength * sa  # +strength if both positive, -strength if both negative
                # 只在有数据时生效
                if factors.get(fa, {}).get("confidence", 0) > 0 and factors.get(fb, {}).get("confidence", 0) > 0:
                    interaction_total += boost
                    contributions[f"{fa}*{fb}"] = round(boost, 4)

        weighted_signal += interaction_total

        # ---- 分类因素 ----
        for fname, adjustments in self.CATEGORICAL_ADJUST.items():
            f = factors.get(fname)
            if not f or f.get("confidence", 0) <= 0:
                continue
            hc = f.get("home_category", "")
            ac = f.get("away_category", "")
            adj = adjustments.get((hc, ac), 0)
            weighted_signal += adj
            contributions[fname] = round(adj, 4)

        # ---- 映射到概率 ----
        if total_weight > 0:
            signal = weighted_signal / total_weight
        else:
            signal = 0

        # 优先使用欧赔隐含概率作为基础
        euro_odds_f = factors.get("euro_odds")
        has_market = False

        if euro_odds_f and euro_odds_f.get("confidence", 0) > 0:
            market_draw = euro_odds_f.get("raw", {}).get("draw_prob", 0)
            market_home = euro_odds_f.get("home_value", 0)
            market_away = euro_odds_f.get("away_value", 0)
            if market_draw > 0 and market_home > 0 and market_away > 0:
                has_market = True

        if has_market:
            # 以欧赔为基础，根据信号强度做调整
            # 1. 基础：欧赔隐含概率
            home_prob = market_home
            away_prob = market_away
            draw_prob = market_draw

            # 2. 信号覆盖：当欧赔信心低且信号强烈反对时，更大幅度调整
            euro_pred = max([('home',market_home),('draw',market_draw),('away',market_away)],key=lambda x:x[1])[0]
            euro_conf = max(market_home, market_draw, market_away)

            if euro_conf < self.SIGNAL_OVERRIDE_CONF:
                # 信号翻转：强烈反对欧赔方向
                if euro_pred == 'home' and signal < -self.SIGNAL_OVERRIDE_THRESHOLD:
                    # 欧赔说主胜但信号说客胜 → 大幅降低主胜，提高客胜
                    flip_strength = min(abs(signal) / 0.5, 1.0) * 0.15
                    home_prob -= flip_strength
                    away_prob += flip_strength
                elif euro_pred == 'away' and signal > self.SIGNAL_OVERRIDE_THRESHOLD:
                    flip_strength = min(abs(signal) / 0.5, 1.0) * 0.15
                    away_prob -= flip_strength
                    home_prob += flip_strength

                # 信号偏向平局：信号方向与欧赔相反 + 欧赔平局概率高
                if euro_pred == 'home' and signal < -self.SIGNAL_DRAW_THRESHOLD and market_draw >= self.SIGNAL_DRAW_EURO:
                    draw_boost = min(abs(signal) / 0.3, 1.0) * 0.08
                    home_prob -= draw_boost
                    draw_prob += draw_boost
                elif euro_pred == 'away' and signal > self.SIGNAL_DRAW_THRESHOLD and market_draw >= self.SIGNAL_DRAW_EURO:
                    draw_boost = min(abs(signal) / 0.3, 1.0) * 0.08
                    away_prob -= draw_boost
                    draw_prob += draw_boost

            # 归一化
            total_p = home_prob + draw_prob + away_prob
            home_prob /= total_p
            draw_prob /= total_p
            away_prob /= total_p

            # 3. 平局概率校准
            # 欧赔draw_prob几乎不随盘口变化(~0.26)，缺乏平局信息
            # 亚盘和泊松模型都包含独立的平局信号
            draw_calibrated = False

            # 3a. 亚盘校准（优先：最直接的平局信号）
            ah_f = factors.get("asian_handicap")
            if ah_f and ah_f.get("confidence", 0) > 0:
                ah_handicap = ah_f.get("raw", {}).get("closing_handicap", None)
                if ah_handicap is not None:
                    abs_hc = abs(float(ah_handicap))
                    ah_draw = self._ah_draw_rate(abs_hc)
                    draw_prob_new = (1 - self.AH_DRAW_BLEND) * draw_prob + self.AH_DRAW_BLEND * ah_draw
                    diff = draw_prob_new - draw_prob
                    non_draw = home_prob + away_prob
                    if non_draw > 0 and abs(diff) > 0.001:
                        home_prob -= diff * (home_prob / non_draw)
                        away_prob -= diff * (away_prob / non_draw)
                        draw_prob = draw_prob_new
                        total_p = home_prob + draw_prob + away_prob
                        home_prob /= total_p; draw_prob /= total_p; away_prob /= total_p
                        draw_calibrated = True

            # 3b. 泊松校准（次选：物理模型推导）
            poisson_f = factors.get("poisson")
            if poisson_f and poisson_f.get("confidence", 0) > 0 and not draw_calibrated:
                pd = poisson_f.get("raw", {}).get("draw_prob", 0)
                if pd > 0 and pd != draw_prob:
                    draw_prob_new = (1 - self.POISSON_DRAW_BLEND) * draw_prob + self.POISSON_DRAW_BLEND * pd
                    diff = draw_prob_new - draw_prob
                    non_draw = home_prob + away_prob
                    if non_draw > 0 and abs(diff) > 0.001:
                        home_prob -= diff * (home_prob / non_draw)
                        away_prob -= diff * (away_prob / non_draw)
                        draw_prob = draw_prob_new
                        total_p = home_prob + draw_prob + away_prob
                        home_prob /= total_p; draw_prob /= total_p; away_prob /= total_p
        else:
            # 无欧赔时用传统模型
            home_adj = self.HOME_ADJ_SCALE * math.tanh(signal * self.SIGNAL_SCALE)
            draw_prob = self.DRAW_PEAK * math.exp(-abs(signal) / self.DRAW_DECAY)
            remaining = 1.0 - draw_prob
            home_base = self.HOME_PRIOR + home_adj
            away_base = self.AWAY_PRIOR - home_adj * 0.6
            base_total = home_base + away_base
            home_prob = remaining * (home_base / base_total)
            away_prob = remaining * (away_base / base_total)

        hp, dp, ap = self._normalize_probs(home_prob, draw_prob, away_prob)

        # ---- 查询联赛信息（杯赛/div2共用） ----
        league = ""
        if storage:
            try:
                conn = storage._conn()
                row = conn.execute("SELECT league_standard FROM matches WHERE match_key=?", (match_key,)).fetchone()
                if row: league = row["league_standard"] or ""
                conn.close()
            except Exception:
                pass

        # ---- 杯赛draw过度修正 ----
        # 杯赛中模型draw precision仅21%, 减0.02pp → 总体+0.22pp argmax, +31 net
        if self.CUP_DP_REDUCE > 0:
            is_cup = any(kw in league for kw in self.CUP_KEYWORDS)
            if is_cup:
                dp -= self.CUP_DP_REDUCE
                non_draw = hp + ap
                if non_draw > 0:
                    hp += self.CUP_DP_REDUCE * (hp / non_draw)
                    ap += self.CUP_DP_REDUCE * (ap / non_draw)
                hp, dp, ap = self._normalize_probs(hp, dp, ap)
                scenario_flags.append("cup_draw_reduce")

        # ---- 分联赛draw修正 ----
        # prima_liga: 140场draw预测仅17%精度, 减0.02pp → 45.2%
        if self.LEAGUE_DP_REDUCE and league:
            for lk, reduce_val in self.LEAGUE_DP_REDUCE.items():
                if lk.lower() in league.lower():
                    dp -= reduce_val
                    non_draw = hp + ap
                    if non_draw > 0:
                        hp += reduce_val * (hp / non_draw)
                        ap += reduce_val * (ap / non_draw)
                    hp, dp, ap = self._normalize_probs(hp, dp, ap)
                    scenario_flags.append(f"league_draw_reduce_{lk}")
                    break

        # ---- 赔率平局阈值规则 (13993场验证) ----
        # 赔率平局隐含概率越高→实际平局率越高，模型需要补偿
        if has_market and market_draw > 0:
            is_div2 = any(kw.lower() in league.lower() for kw in self.DIV2_KEYWORDS)
            for threshold, boost in sorted(self.DRAW_PROB_THRESHOLDS.items(), reverse=True):
                if market_draw >= threshold:
                    # 二级联赛dt30用不同boost
                    actual_boost = self.DIV2_DT30_BOOST if (is_div2 and threshold == 0.30) else boost
                    if actual_boost > 0:
                        dp += actual_boost
                        non_draw = hp + ap
                        if non_draw > 0:
                            hp -= actual_boost * (hp / non_draw)
                            ap -= actual_boost * (ap / non_draw)
                        hp, dp, ap = self._normalize_probs(hp, dp, ap)
                        scenario_flags.append(f"draw_threshold_{threshold}")
                    # dt30触发后分档减draw概率(补偿亚盘blend过高)
                    if threshold == 0.30 and self.DT30_BASE_DP_REDUCE > 0:
                        if is_div2:
                            boost_val = self.DIV2_DT30_BOOST
                            base_reduce = self.DIV2_DT30_BASE_DP_REDUCE
                            ah0_extra = self.DIV2_DT30_AH0_EXTRA_DP_REDUCE
                        else:
                            boost_val = 0  # boost已在外层循环加了
                            base_reduce = self.DT30_BASE_DP_REDUCE
                            ah0_extra = self.DT30_AH0_EXTRA_DP_REDUCE
                        # AH=0(平手盘): 亚盘blend叠加最严重 → 额外减
                        is_ah0 = False
                        if ah_f and ah_f.get("confidence", 0) > 0:
                            ah_hc = ah_f.get("raw", {}).get("closing_handicap", None)
                            if ah_hc is not None and abs(float(ah_hc)) < 0.01:
                                is_ah0 = True
                        reduce_val = base_reduce + (ah0_extra if is_ah0 else 0)
                        dp -= reduce_val
                        non_draw = hp + ap
                        if non_draw > 0:
                            hp += reduce_val * (hp / non_draw)
                            ap += reduce_val * (ap / non_draw)
                        hp, dp, ap = self._normalize_probs(hp, dp, ap)
                        if is_div2:
                            scenario_flags.append("div2_dt30_reduce")
                    break

        # ---- 全球赔率冷门区规则 (5-6月赛季末才触发) ----
        # 4月数据: 1.25-1.35区间冷门率仅15%，5月动机不对称时达88.9%
        # 非赛季末不加调整，赛季末才触发
        match_date = ""
        if storage:
            try:
                conn = storage._conn()
                row = conn.execute("SELECT date FROM matches WHERE match_key=?", (match_key,)).fetchone()
                if row: match_date = row["date"] or ""
                conn.close()
            except Exception:
                pass
        odds_h = None
        if euro_odds_f:
            raw = euro_odds_f.get("raw", {})
            odds_h = float(raw.get("avg_home_odds", 0) or raw.get("closing_avg_home_odds", 0) or 0)

        match_month = int(match_date[5:7]) if len(match_date) >= 7 else 0

        # Rule: 全球赔率冷门区（仅5-6月触发）
        if odds_h and self.GLOBAL_UPSET_ODDS_RANGE[0] <= odds_h <= self.GLOBAL_UPSET_ODDS_RANGE[1]:
            if match_month in self.GLOBAL_UPSET_MONTHS:
                adjust = self.GLOBAL_UPSET_ADJUST
                hp -= adjust
                dp += adjust * 0.5
                ap += adjust * 0.5
                hp, dp, ap = self._normalize_probs(hp, dp, ap)
                scenario_flags.append("global_upset_zone")

        # ---- 南美杯赛冷门区 (赔率1.35-1.50) ----
        is_sa = any(kw in league for kw in self.SA_LEAGUE_KEYWORDS)
        if is_sa and odds_h and 1.35 <= odds_h <= 1.50:
            adjust = 0.02
            hp -= adjust
            dp += adjust * 0.6
            ap += adjust * 0.4
            hp, dp, ap = self._normalize_probs(hp, dp, ap)
            scenario_flags.append("sa_upset_zone")

        # ---- 赛季末均衡draw回调 (v3.9.2新增) ----
        # DB验证: 赛季末最后5轮+双方赔率均衡(both<3)+draw隐含>=28%
        # → 实际draw率比市场隐含高+4~9% (双方动机强→保守对抗→平局)
        # b365 14119场验证: +0.01pp argmax, Brier持平, 影响239场
        # 解放者杯回测: 博卡1-1克鲁塞罗, 天主大学0-0克鲁塞罗 (双方同需赢→平局)
        odds_a_val = None
        odds_d_val = None
        if euro_odds_f:
            raw = euro_odds_f.get("raw", {})
            odds_a_val = float(raw.get("avg_away_odds", 0) or raw.get("closing_avg_away_odds", 0) or 0)
            odds_d_val = float(raw.get("avg_draw_odds", 0) or raw.get("closing_avg_draw_odds", 0) or 0)

        if odds_h and odds_a_val and odds_d_val and match_month in [4, 5, 6]:
            is_balanced = odds_h < self.LATE_SEASON_BALANCED_THRESHOLD and odds_a_val < self.LATE_SEASON_BALANCED_THRESHOLD
            implied_draw = 1.0 / odds_d_val if odds_d_val > 1 else 0
            is_high_draw = implied_draw >= self.LATE_SEASON_DRAW_THRESHOLD
            if is_balanced and is_high_draw:
                boost = self.LATE_SEASON_DRAW_BOOST
                dp += boost
                non_draw = hp + ap
                if non_draw > 0:
                    hp -= boost * (hp / non_draw)
                    ap -= boost * (ap / non_draw)
                hp, dp, ap = self._normalize_probs(hp, dp, ap)
                scenario_flags.append("late_season_balanced_draw")

        # ---- 动机不对称规则 (v3.5数据驱动修正) ----
        # 低赔率+不对称(dead_rubber vs relegation): 主胜率80%(13场验证69%)
        # 不对称反而强化了主胜！保级队客战强队拼命反而更容易输
        # 规则方向: 强化主胜而非削弱（与直觉相反，但数据支持）
        if mot_f and mot_f.get("confidence", 0) > 0:
            mot_diff = mot_f.get("diff", 0)
            mot_raw = mot_f.get("raw", {})
            home_cat = mot_raw.get("home_category", "") or mot_f.get("home_category", "")
            away_cat = mot_raw.get("away_category", "") or mot_f.get("away_category", "")

            # 动机不对称: 主队无欲(dead_rubber/mid_table) vs 客队拼命(relegation/title/european)
            is_home_dead = home_cat in ("dead_rubber", "mid_table")
            is_away_desperate = away_cat in ("relegation", "relegation_battle", "title_race", "european")

            if is_home_dead and is_away_desperate and mot_diff < self.MOTIVATION_MISMATCH_THRESHOLD:
                if odds_h and odds_h <= self.MOTIVATION_MISMATCH_MAX_ODDS:
                    if match_month in self.MOTIVATION_MISMATCH_END_MONTHS:
                        # 强化主胜（不对称反而让主队更赢）
                        adjust = self.MOTIVATION_MISMATCH_ADJUST
                        hp += adjust
                        dp -= adjust * 0.5
                        ap -= adjust * 0.5
                        hp, dp, ap = self._normalize_probs(hp, dp, ap)
                        scenario_flags.append("motivation_mismatch")
                    else:
                        # 非赛季末轻微强化主胜
                        adjust = self.MOTIVATION_MISMATCH_ADJUST / 3
                        hp += adjust
                        dp -= adjust * 0.5
                        ap -= adjust * 0.5
                        hp, dp, ap = self._normalize_probs(hp, dp, ap)
                        scenario_flags.append("motivation_mismatch_light")

        # ---- 杯赛低赔率不安全规则 ----
        # 杯赛小组赛弱队更拼命抢分，低赔率1.15-1.25尤其危险
        is_cup = any(kw in league for kw in self.CUP_LEAGUE_KEYWORDS)
        if is_cup and odds_h and odds_h <= self.CUP_LOW_ODDS_THRESHOLD:
            adjust = self.CUP_LOW_ODDS_ADJUST
            hp -= adjust
            dp += adjust * 0.4
            ap += adjust * 0.6
            hp, dp, ap = self._normalize_probs(hp, dp, ap)
            scenario_flags.append("cup_low_odds_risk")

        # ---- 高海拔主场规则 ----
        # 玻利维亚/秘鲁/厄瓜多尔高原主场: 客队体能快速下降
        # 当主队赔率>2.0(客队更强)时，高海拔大幅削弱客队优势
        home_team_raw = ""
        if storage:
            try:
                conn = storage._conn()
                row = conn.execute("SELECT home_team FROM matches WHERE match_key=?", (match_key,)).fetchone()
                if row:
                    home_team_raw = row["home_team"] or ""
                conn.close()
            except Exception:
                pass

        # 匹配高海拔球队（精确匹配+部分匹配，避免Nacional误匹配）
        is_altitude = False
        if home_team_raw:
            for team in self.ALTITUDE_TEAMS:
                if home_team_raw == team:
                    is_altitude = True
                    break
                # 部分匹配：team关键词在home_team_raw中（如"The Strongest"包含"Strongest"）
                if len(team) > 5 and team.lower() in home_team_raw.lower():
                    is_altitude = True
                    break
        if is_altitude and odds_h and odds_h >= 2.0:
            adjust = self.ALTITUDE_ADJUST
            hp += adjust
            ap -= adjust * 0.7
            dp -= adjust * 0.3
            hp, dp, ap = self._normalize_probs(hp, dp, ap)
            scenario_flags.append("altitude_home")

        # ---- 泊松平局概率补充（仅无欧赔时） ----
        poisson_f = factors.get("poisson")
        if poisson_f and poisson_f.get("confidence", 0) > 0 and not has_market:
            pd = poisson_f.get("raw", {}).get("draw_prob", 0)
            if pd > 0:
                dp = dp * (1 - self.POISSON_DRAW_BLEND) + pd * self.POISSON_DRAW_BLEND
                hp, dp, ap = self._normalize_probs(hp, dp, ap)

        # ---- 大小球 ----
        over_signal = 0.0
        over_weight = 0.0
        for fname in ["over_under", "poisson", "expected_goals"]:
            f = factors.get(fname)
            if not f or f.get("confidence", 0) <= 0 or f.get("type") != "numeric":
                continue
            w = self.WEIGHTS.get(fname, 0)
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

        # ---- 置信度 ----
        active_count = len(used_weights)
        coverage = min(1.0, active_count / len(self.WEIGHTS))
        confidence = round(coverage * 0.7 + (total_weight / sum(self.WEIGHTS.values())) * 0.3, 2)

        # ---- 信号方向 ----
        if signal > 0.03:
            signal_dir = "home"
        elif signal < -0.03:
            signal_dir = "away"
        else:
            signal_dir = "draw"

        # 交互项数量
        interaction_count = len([k for k in contributions if "*" in k])

        # ---- 期望价值(EV) ----
        # EV = model_prob × fair_odds - 1
        # 优先使用闭盘赔率(更准确的市场定价)，其次开盘赔率
        ev = {}
        if euro_odds_f:
            raw = euro_odds_f.get("raw", {})
            # 优先闭盘赔率
            ev_h = raw.get("closing_avg_home_odds") or raw.get("avg_home_odds", 0)
            ev_d = raw.get("closing_avg_draw_odds") or raw.get("avg_draw_odds", 0)
            ev_a = raw.get("closing_avg_away_odds") or raw.get("avg_away_odds", 0)
            try:
                ev_h = float(ev_h); ev_d = float(ev_d); ev_a = float(ev_a)
                if ev_h > 1 and ev_d > 1 and ev_a > 1:
                    margin = 1/ev_h + 1/ev_d + 1/ev_a
                    fair_h = ev_h * margin
                    fair_d = ev_d * margin
                    fair_a = ev_a * margin
                    ev["home"] = round(hp * fair_h - 1, 4)
                    ev["draw"] = round(dp * fair_d - 1, 4)
                    ev["away"] = round(ap * fair_a - 1, 4)
            except (ValueError, ZeroDivisionError, TypeError):
                pass

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
            "factor_weights_used": used_weights,
            "factor_contributions": contributions,
            "active_factors": active_count,
            "interaction_count": interaction_count,
            "scenario_flags": scenario_flags,
        }
