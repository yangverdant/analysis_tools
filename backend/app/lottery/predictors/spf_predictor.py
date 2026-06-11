"""
SPF预测模型

整合多个特征提取器的结果，预测胜平负结果
"""

from typing import Dict, Any, Optional, List
import sqlite3
import logging

from .base import (
    BasePredictor, PredictionResult, PredictionType,
    FeatureContribution
)

logger = logging.getLogger(__name__)


class SPFPredictor(BasePredictor):
    """
    胜平负预测模型

    整合以下特征:
    1. Poisson概率 (基于进球期望)
    2. Elo评分差异
    3. 历史交锋记录
    4. 近期状态
    5. 主场优势
    """

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config)

    @property
    def name(self) -> str:
        return "spf_predictor"

    @property
    def prediction_type(self) -> PredictionType:
        return PredictionType.SPF

    def _get_default_weights(self) -> Dict[str, float]:
        """默认特征权重"""
        return {
            'poisson': 0.30,
            'elo': 0.25,
            'h2h': 0.15,
            'form': 0.15,
            'home_advantage': 0.15
        }

    def predict(self, context: Dict[str, Any]) -> PredictionResult:
        """
        执行胜平负预测

        Args:
            context: 包含 home_team_id, away_team_id, match_id 等

        Returns:
            PredictionResult: 预测结果
        """
        home_team_id = context.get('home_team_id')
        away_team_id = context.get('away_team_id')

        if not home_team_id or not away_team_id:
            return self._create_error_result("Missing team IDs")

        # 如果已有特征，直接使用
        features = context.get('features', {})

        # 否则提取特征
        if not features:
            features = self._extract_features(home_team_id, away_team_id, context)

        # 组合特征
        combined_probs = self._combine_features(
            {k: v for k, v in features.items() if isinstance(v, dict)},
            self._feature_weights
        )

        # 确定预测结果
        predicted_result = self._get_highest_prob_result(combined_probs)
        predicted_prob = combined_probs.get(predicted_result, 0.0)

        # 计算置信度
        confidence = self._calculate_confidence(combined_probs)
        confidence_level = self._calculate_confidence_level(confidence)

        # 检查价值投注
        odds = self._get_odds(context, predicted_result)
        is_value, value = self._check_value_bet(predicted_prob, odds)

        # 计算特征贡献
        feature_contributions = self._calculate_feature_contributions(
            features, predicted_result
        )

        return PredictionResult(
            prediction_type=self.prediction_type,
            predicted_result=predicted_result,
            predicted_prob=predicted_prob,
            confidence=confidence,
            confidence_level=confidence_level,
            all_probabilities=combined_probs,
            feature_contributions=feature_contributions,
            value_bet=is_value,
            value=value,
            odds=odds,
            raw_data={'features': features}
        )

    def _extract_features(
        self,
        home_team_id: int,
        away_team_id: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提取所有特征"""
        features = {}

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Poisson概率
            features['poisson'] = self._extract_poisson_probs(
                cursor, home_team_id, away_team_id
            )

            # 2. Elo概率
            features['elo'] = self._extract_elo_probs(
                cursor, home_team_id, away_team_id
            )

            # 3. 交锋记录
            features['h2h'] = self._extract_h2h_probs(
                cursor, home_team_id, away_team_id
            )

            # 4. 近期状态
            features['form'] = self._extract_form_probs(
                cursor, home_team_id, away_team_id
            )

            # 5. 主场优势
            features['home_advantage'] = self._get_home_advantage_probs()

        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
        finally:
            if conn:
                conn.close()

        return features

    def _extract_poisson_probs(
        self,
        cursor,
        home_team_id: int,
        away_team_id: int
    ) -> Dict[str, float]:
        """基于Poisson分布计算概率"""
        import math

        # 获取历史进球数据
        cursor.execute("""
            SELECT AVG(home_goals) as avg_home_goals
            FROM matches
            WHERE home_team_id = ? AND status = 'finished'
            LIMIT 10
        """, (home_team_id,))
        home_row = cursor.fetchone()

        cursor.execute("""
            SELECT AVG(away_goals) as avg_away_goals
            FROM matches
            WHERE away_team_id = ? AND status = 'finished'
            LIMIT 10
        """, (away_team_id,))
        away_row = cursor.fetchone()

        # 计算lambda
        home_lambda = home_row['avg_home_goals'] if home_row and home_row[0] else 1.35
        away_lambda = away_row['avg_away_goals'] if away_row and away_row[0] else 1.10

        # Poisson概率计算
        def poisson_prob(k, lam):
            return (lam ** k) * math.exp(-lam) / math.factorial(k)

        home_win = draw = away_win = 0.0
        for i in range(8):
            for j in range(8):
                prob = poisson_prob(i, home_lambda) * poisson_prob(j, away_lambda)
                if i > j:
                    home_win += prob
                elif i == j:
                    draw += prob
                else:
                    away_win += prob

        return {
            'home_win': home_win,
            'draw': draw,
            'away_win': away_win
        }

    def _extract_elo_probs(
        self,
        cursor,
        home_team_id: int,
        away_team_id: int
    ) -> Dict[str, float]:
        """基于Elo评分计算概率"""
        # 获取Elo评分
        cursor.execute("""
            SELECT elo_rating FROM team_elo_ratings
            WHERE team_id = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (home_team_id,))
        home_row = cursor.fetchone()

        cursor.execute("""
            SELECT elo_rating FROM team_elo_ratings
            WHERE team_id = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (away_team_id,))
        away_row = cursor.fetchone()

        home_elo = home_row['elo_rating'] if home_row else 1500
        away_elo = away_row['elo_rating'] if away_row else 1500

        # 主场优势加成
        home_elo += 100

        # 计算期望得分
        elo_diff = home_elo - away_elo
        expected_home = 1 / (1 + 10 ** (-elo_diff / 400))

        # 简化转换为胜平负概率
        home_win = expected_home * 0.7 + 0.15
        draw = 1 - expected_home * 1.4 + 0.25
        away_win = 1 - home_win - draw

        # 归一化
        total = home_win + draw + away_win
        return {
            'home_win': max(0, home_win / total),
            'draw': max(0, draw / total),
            'away_win': max(0, away_win / total)
        }

    def _extract_h2h_probs(
        self,
        cursor,
        home_team_id: int,
        away_team_id: int
    ) -> Dict[str, float]:
        """基于交锋记录计算概率"""
        cursor.execute("""
            SELECT
                SUM(CASE WHEN (home_team_id = ? AND home_goals > away_goals)
                         OR (away_team_id = ? AND away_goals > home_goals) THEN 1 ELSE 0 END) as home_wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                SUM(CASE WHEN (home_team_id = ? AND home_goals < away_goals)
                         OR (away_team_id = ? AND away_goals < home_goals) THEN 1 ELSE 0 END) as away_wins,
                COUNT(*) as total
            FROM matches
            WHERE ((home_team_id = ? AND away_team_id = ?)
                OR (home_team_id = ? AND away_team_id = ?))
              AND status = 'finished'
        """, (home_team_id, home_team_id, home_team_id, home_team_id,
              home_team_id, away_team_id, away_team_id, home_team_id))

        row = cursor.fetchone()
        if not row or not row['total'] or row['total'] == 0:
            return {'home_win': 0.33, 'draw': 0.34, 'away_win': 0.33}

        total = row['total']
        return {
            'home_win': (row['home_wins'] or 0) / total,
            'draw': (row['draws'] or 0) / total,
            'away_win': (row['away_wins'] or 0) / total
        }

    def _extract_form_probs(
        self,
        cursor,
        home_team_id: int,
        away_team_id: int
    ) -> Dict[str, float]:
        """基于近期状态计算概率"""
        def get_form_factor(team_id):
            cursor.execute("""
                SELECT
                    CASE
                        WHEN home_team_id = ? THEN
                            CASE
                                WHEN home_goals > away_goals THEN 3
                                WHEN home_goals = away_goals THEN 1
                                ELSE 0
                            END
                        ELSE
                            CASE
                                WHEN away_goals > home_goals THEN 3
                                WHEN away_goals = home_goals THEN 1
                                ELSE 0
                            END
                    END as points
                FROM matches
                WHERE (home_team_id = ? OR away_team_id = ?)
                  AND status = 'finished'
                ORDER BY match_time DESC
                LIMIT 5
            """, (team_id, team_id, team_id))

            rows = cursor.fetchall()
            if not rows:
                return 0.5

            total_points = sum(r['points'] or 0 for r in rows)
            return total_points / 15

        home_form = get_form_factor(home_team_id)
        away_form = get_form_factor(away_team_id)
        form_diff = home_form - away_form

        # 状态差异影响概率
        return {
            'home_win': max(0, 0.33 + form_diff * 0.3),
            'draw': 0.33,
            'away_win': max(0, 0.33 - form_diff * 0.3)
        }

    def _get_home_advantage_probs(self) -> Dict[str, float]:
        """主场优势概率调整"""
        return {
            'home_win': 0.10,  # 主胜概率增加10%
            'draw': 0.0,
            'away_win': -0.10  # 客胜概率减少10%
        }

    def _get_highest_prob_result(self, probs: Dict[str, float]) -> str:
        """获取最高概率的结果"""
        if not probs:
            return 'draw'
        return max(probs.keys(), key=lambda k: probs.get(k, 0))

    def _calculate_confidence(self, probs: Dict[str, float]) -> float:
        """计算置信度"""
        if not probs:
            return 0.0

        values = sorted(probs.values(), reverse=True)
        if len(values) < 2:
            return values[0] if values else 0.0

        # 最高概率与次高概率的差距
        return values[0] + (values[0] - values[1]) * 0.5

    def _get_odds(self, context: Dict[str, Any], result: str) -> Optional[float]:
        """获取赔率"""
        odds_data = context.get('odds', {})
        spf_odds = odds_data.get('spf', {})

        result_key = {'home_win': '3', 'draw': '1', 'away_win': '0'}.get(result)
        return spf_odds.get(result_key)

    def _calculate_feature_contributions(
        self,
        features: Dict[str, Any],
        predicted_result: str
    ) -> Dict[str, float]:
        """计算各特征的贡献度"""
        contributions = {}

        for feat_name, feat_value in features.items():
            if isinstance(feat_value, dict) and predicted_result in feat_value:
                weight = self._feature_weights.get(feat_name, 0)
                contributions[feat_name] = feat_value[predicted_result] * weight

        return contributions

    def _create_error_result(self, error_msg: str) -> PredictionResult:
        """创建错误结果"""
        return PredictionResult(
            prediction_type=self.prediction_type,
            predicted_result='unknown',
            predicted_prob=0.0,
            confidence=0.0,
            confidence_level='low',
            raw_data={'error': error_msg}
        )
