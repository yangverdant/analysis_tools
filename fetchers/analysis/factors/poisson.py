"""Poisson比分预测因素 v2

核心改进:
1. 从赔率O/U推算总进球期望lambda_total（比积分榜更准确）
2. 从赔率主胜概率推算两队进球比例
3. 无赔率时仍用积分榜攻防强度（fallback）
4. 输出完整的比分概率矩阵（0-0到5-5）
"""

import json, math
from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class PoissonFactor(BaseFactor):
    factor = "poisson"
    title = "Poisson比分预测"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        league = match.get("league_standard", "")

        # 优先从赔率获取进球期望
        odds_lambda = self._get_lambda_from_odds(match_key, storage)

        if odds_lambda:
            home_lambda, away_lambda = odds_lambda
            source = "odds"
            conf = 0.85
        else:
            # Fallback: 积分榜攻防强度
            standings = self._get_standings_map(league, storage) if league else {}
            hs = standings.get(home)
            as_ = standings.get(away)

            if not hs or not as_:
                return self._no_data("无积分榜数据")

            hp = int(hs.get("played", 1))
            ap = int(as_.get("played", 1))
            if hp == 0 or ap == 0:
                return self._no_data("比赛场次为0")

            hgf = int(hs.get("goals_for", 0))
            hga = int(hs.get("goals_against", 0))
            agf = int(as_.get("goals_for", 0))
            aga = int(as_.get("goals_against", 0))

            all_gf = sum(int(s.get("goals_for", 0)) for s in standings.values())
            all_played = sum(int(s.get("played", 0)) for s in standings.values())
            league_avg = all_gf / all_played / 2 if all_played > 0 else 1.3

            home_attack = (hgf / hp) / league_avg if league_avg > 0 else 1
            home_defense = (hga / hp) / league_avg if league_avg > 0 else 1
            away_attack = (agf / ap) / league_avg if league_avg > 0 else 1
            away_defense = (aga / ap) / league_avg if league_avg > 0 else 1

            home_lambda = home_attack * away_defense * league_avg * 1.1  # 主场加成
            away_lambda = away_attack * home_defense * league_avg
            source = "standings"
            conf = 0.5

        # Poisson概率矩阵
        home_win = draw = away_win = 0
        over_2_5 = 0
        over_1_5 = 0
        btts_yes = 0
        top_scores = []
        score_matrix = {}

        for i in range(7):
            for j in range(7):
                p = self._poisson(home_lambda, i) * self._poisson(away_lambda, j)
                if i > j:   home_win += p
                elif i == j: draw += p
                else:        away_win += p
                if i + j > 2.5: over_2_5 += p
                if i + j > 1.5: over_1_5 += p
                if i > 0 and j > 0: btts_yes += p
                score_matrix[f"{i}-{j}"] = round(p, 4)
                top_scores.append((f"{i}-{j}", round(p, 4)))

        top_scores.sort(key=lambda x: -x[1])
        top5 = top_scores[:5]

        # 最可能比分
        most_likely = top5[0][0] if top5 else "1-1"

        # 0-0概率（对平局预测有参考价值）
        p_00 = round(self._poisson(home_lambda, 0) * self._poisson(away_lambda, 0), 4)

        # 1-0和0-1概率（对主胜/客胜预测有参考价值）
        p_10 = round(self._poisson(home_lambda, 1) * self._poisson(away_lambda, 0), 4)
        p_01 = round(self._poisson(home_lambda, 0) * self._poisson(away_lambda, 1), 4)

        return self._numeric(
            home_value=round(home_win, 4),
            away_value=round(away_win, 4),
            unit="Poisson胜率",
            higher_is_better=True,
            confidence=conf,
            draw_prob=round(draw, 4),
            over_2_5_prob=round(over_2_5, 4),
            over_1_5_prob=round(over_1_5, 4),
            btts_yes_prob=round(btts_yes, 4),
            home_lambda=round(home_lambda, 3),
            away_lambda=round(away_lambda, 3),
            total_lambda=round(home_lambda + away_lambda, 3),
            lambda_source=source,
            most_likely_score=most_likely,
            top5_scores=top5,
            p_00=p_00,
            p_10=p_10,
            p_01=p_01,
        )

    def _get_lambda_from_odds(self, match_key: str, storage) -> tuple:
        """从赔率数据推算进球lambda"""
        conn = storage._conn()

        # 获取欧赔因素（含closing和O/U数据）
        odds_row = conn.execute(
            "SELECT data_json FROM match_data "
            "WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (match_key,)
        ).fetchone()

        # 获取O/U因素
        ou_row = conn.execute(
            "SELECT data_json FROM match_data "
            "WHERE match_key=? AND source='factor' AND data_type='factor:over_under'",
            (match_key,)
        ).fetchone()

        conn.close()

        total_lambda = None
        home_ratio = None

        # 从O/U赔率推算总进球期望
        if ou_row:
            try:
                ou = json.loads(ou_row["data_json"])
                raw = ou.get("raw", {})
                # 从O/U赔率推算expected total goals
                # P(over 2.5) = 0.52 → lambda_total ≈ 2.7
                o25_prob = ou.get("home_value", 0)  # over_2_5_prob stored as home_value
                if o25_prob > 0:
                    # 反推lambda: P(over 2.5) = 1 - sum(Poisson(lambda, k) for k=0,1,2)
                    total_lambda = self._lambda_from_over_prob(o25_prob)
            except:
                pass

        # 从欧赔推算两队进球比例
        if odds_row:
            try:
                eo = json.loads(odds_row["data_json"])
                home_prob = eo.get("home_value", 0)
                away_prob = eo.get("away_value", 0)
                draw_prob = eo.get("raw", {}).get("draw_prob", 0)
                if home_prob > 0 and away_prob > 0:
                    # 主胜概率越高 → home_lambda占总lambda比例越大
                    # 简化模型: ratio = home_prob / (home_prob + away_prob)
                    # 但要修正：如果draw_prob高，说明两队实力接近
                    non_draw = home_prob + away_prob
                    if non_draw > 0:
                        home_ratio = home_prob / non_draw
                    # 主场加成修正：统计上主场进球约占55%
                    home_ratio = home_ratio * 0.55 + 0.45 * 0.55  # blend with prior
                    # 但如果赔率差距很大，主要跟着赔率走
                    ratio_diff = abs(home_prob - away_prob)
                    home_ratio = home_prob / non_draw  # 直接用赔率比例更准
                    # 加上主场加成
                    home_ratio = min(0.70, home_ratio + 0.05)
            except:
                pass

        if total_lambda and home_ratio:
            home_lambda = total_lambda * home_ratio
            away_lambda = total_lambda * (1 - home_ratio)
            return (home_lambda, away_lambda)

        return None

    def _lambda_from_over_prob(self, over_prob: float) -> float:
        """从O2.5概率反推lambda_total"""
        # P(X<=2) = 1 - over_prob, 其中X ~ Poisson(lambda)
        # 尝试几个lambda值，找最接近的
        target = 1.0 - over_prob
        for lam in [x * 0.1 for x in range(10, 50)]:
            cum = 0
            for k in range(3):
                cum += self._poisson(lam, k)
            if cum < target:
                return lam
        return 2.5  # default

    @staticmethod
    def _poisson(lam: float, k: int) -> float:
        if lam <= 0:
            return 1.0 if k == 0 else 0.0
        return (lam ** k) * math.exp(-lam) / math.factorial(k)