"""
比分预测器 (Score Predictor)

基于 Poisson 分布预测比分概率矩阵

分析流程:
1. 计算两队进球期望 λ (基于历史数据)
2. 生成比分概率矩阵 (P(i,j) = P(X=i) * P(Y=j))
3. 过滤体彩支持的27种比分
4. 结合赔率计算价值投注
5. 返回TOP N推荐比分

体彩比分玩法:
- 主胜比分: 1:0, 2:0, 2:1, 3:0, 3:1, 3:2, 4:0, 4:1, 4:2, 5:0, 5:1, 5:2, 其他主胜
- 平局比分: 0:0, 1:1, 2:2, 3:3, 其他平局
- 客胜比分: 0:1, 0:2, 1:2, 0:3, 1:3, 2:3, 0:4, 1:4, 2:4, 0:5, 1:5, 2:5, 其他客胜
"""

from typing import Dict, Any, Optional, List, Tuple
import sqlite3
import math
import logging
from datetime import datetime

from ..base import (
    ExtractionContext, ExtractionResult, FeatureCategory,
    CalculationExtractor
)
from ...schemas.lottery import PlayType

logger = logging.getLogger(__name__)


class ScorePredictor(CalculationExtractor):
    """
    比分预测器

    基于 Poisson 分布和历史数据预测比分概率
    """

    # 体彩支持的比分选项 (不含"其他")
    SUPPORTED_SCORES = {
        # 主胜
        'home_win': ['10', '20', '21', '30', '31', '32', '40', '41', '42', '50', '51', '52'],
        # 平局
        'draw': ['00', '11', '22', '33'],
        # 客胜
        'away_win': ['01', '02', '12', '03', '13', '23', '04', '14', '24', '05', '15', '25']
    }

    # 所有支持的比分
    ALL_SCORES = (
        SUPPORTED_SCORES['home_win'] +
        SUPPORTED_SCORES['draw'] +
        SUPPORTED_SCORES['away_win']
    )

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight_config = (config or {}).get('weights', {
            'poisson': 0.50,
            'league_pattern': 0.30,
            'h2h': 0.20
        })

    @property
    def name(self) -> str:
        return "score_predictor"

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.MATH

    @property
    def play_type(self) -> PlayType:
        return PlayType.BF

    def get_required_data(self) -> List[str]:
        return [
            'home_team_id', 'away_team_id', 'match_date',
            'home_goals_history', 'away_goals_history',
            'league_id'
        ]

    def calculate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行比分计算

        这是 CalculationExtractor 要求的方法
        """
        home_lambda = data.get('home_lambda', 1.35)
        away_lambda = data.get('away_lambda', 1.10)

        score_matrix = self._generate_score_matrix(home_lambda, away_lambda)
        supported_probs = self._filter_supported_scores(score_matrix)
        top_scores = self._get_top_scores(supported_probs)

        return {
            'score_matrix': score_matrix,
            'supported_scores': supported_probs,
            'top_scores': top_scores,
            'spf_distribution': self._calculate_spf_distribution(score_matrix)
        }

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """
        执行比分预测

        Args:
            context: 提取上下文

        Returns:
            ExtractionResult 包含比分概率矩阵和推荐
        """
        if not context.home_team_id or not context.away_team_id:
            return ExtractionResult(
                feature_name=self.name,
                category=self.category,
                value=0.0,
                raw_data={'error': 'Missing team IDs'},
                confidence=0.0,
                description="缺少球队ID"
            )

        try:
            # 1. 计算进球期望 λ
            home_lambda, away_lambda = self._calculate_lambdas(context)

            # 2. 生成比分概率矩阵
            score_matrix = self._generate_score_matrix(home_lambda, away_lambda)

            # 3. 应用联赛比分模式调整
            adjusted_matrix = self._apply_league_pattern(context, score_matrix)

            # 4. 应用交锋记录调整
            final_matrix = self._apply_h2h_adjustment(context, adjusted_matrix)

            # 5. 过滤体彩支持的比分
            supported_probs = self._filter_supported_scores(final_matrix)

            # 6. 计算价值投注
            value_bets = self._calculate_value_bets(context, supported_probs)

            # 7. 生成推荐
            top_scores = self._get_top_scores(supported_probs, n=5)

            # 8. 计算置信度
            confidence = self._calculate_confidence(top_scores)

            # 将比分矩阵转换为可JSON序列化的格式
            score_matrix_json = {f"{h}_{a}": p for (h, a), p in score_matrix.items()}

            return ExtractionResult(
                feature_name=self.name,
                category=self.category,
                value=top_scores[0]['prob'] if top_scores else 0.0,
                raw_data={
                    'home_lambda': home_lambda,
                    'away_lambda': away_lambda,
                    'score_matrix': score_matrix_json,
                    'supported_scores': supported_probs,
                    'top_scores': top_scores,
                    'value_bets': value_bets,
                    'spf_distribution': self._calculate_spf_distribution(score_matrix)
                },
                confidence=confidence,
                description=f"最可能比分: {self._format_score(top_scores[0]['score']) if top_scores else '未知'}"
            )

        except Exception as e:
            logger.error(f"Score prediction failed: {e}")
            return ExtractionResult(
                feature_name=self.name,
                category=self.category,
                value=0.0,
                raw_data={'error': str(e)},
                confidence=0.0,
                description=f"预测失败: {str(e)}"
            )

    def _calculate_lambdas(self, context: ExtractionContext) -> Tuple[float, float]:
        """
        计算两队进球期望 λ

        方法:
        1. 获取历史进球数据 (主队主场、客队客场)
        2. 计算平均进球率
        3. 结合对手防守强度调整
        4. 考虑联赛平均进球数
        """
        cursor = context.db_conn.cursor()

        # 获取主队主场进球数据 (近10场)
        cursor.execute("""
            SELECT
                AVG(home_goals) as avg_home_goals,
                AVG(away_goals) as avg_home_conceded,
                COUNT(*) as sample_size
            FROM matches
            WHERE home_team_id = ?
            AND status = 'finished'
            ORDER BY match_time DESC
            LIMIT 10
        """, (context.home_team_id,))

        home_row = cursor.fetchone()

        # 获取客队客场进球数据
        cursor.execute("""
            SELECT
                AVG(away_goals) as avg_away_goals,
                AVG(home_goals) as avg_away_conceded,
                COUNT(*) as sample_size
            FROM matches
            WHERE away_team_id = ?
            AND status = 'finished'
            ORDER BY match_time DESC
            LIMIT 10
        """, (context.away_team_id,))

        away_row = cursor.fetchone()

        # 获取联赛平均进球 (用于归一化)
        league_avg = self._get_league_avg_goals(context)
        default_lambda = league_avg / 2  # 每队平均进球

        # 计算主队进球期望
        if home_row and home_row[0] and home_row[2] >= 3:
            home_attack = home_row[0]
        else:
            home_attack = default_lambda

        if away_row and away_row[1] and away_row[2] >= 3:
            away_defense = away_row[1]
        else:
            away_defense = default_lambda

        # 主队进球期望 = 主队主场进攻 × 客队客场防守 / 联赛平均
        home_lambda = home_attack * away_defense / default_lambda

        # 计算客队进球期望
        if away_row and away_row[0] and away_row[2] >= 3:
            away_attack = away_row[0]
        else:
            away_attack = default_lambda * 0.85  # 客场进球通常较少

        if home_row and home_row[1] and home_row[2] >= 3:
            home_defense = home_row[1]
        else:
            home_defense = default_lambda

        away_lambda = away_attack * home_defense / default_lambda

        # 限制范围 (避免极端值)
        home_lambda = max(0.3, min(3.5, home_lambda))
        away_lambda = max(0.3, min(3.5, away_lambda))

        return home_lambda, away_lambda

    def _get_league_avg_goals(self, context: ExtractionContext) -> float:
        """获取联赛平均进球数"""
        if not context.league_id:
            return 2.7  # 默认值

        cursor = context.db_conn.cursor()

        cursor.execute("""
            SELECT AVG(home_goals + away_goals) as avg_goals
            FROM matches
            WHERE league_id = ?
            AND status = 'finished'
            ORDER BY match_time DESC
            LIMIT 50
        """, (context.league_id,))

        row = cursor.fetchone()
        if row and row[0]:
            return row[0]

        return 2.7

    def _generate_score_matrix(
        self,
        home_lambda: float,
        away_lambda: float,
        max_goals: int = 7
    ) -> Dict[Tuple[int, int], float]:
        """
        生成比分概率矩阵

        使用 Poisson 分布:
        P(X=k) = (λ^k * e^-λ) / k!
        P(score=i:j) = P(home=i) * P(away=j)
        """
        matrix = {}

        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                # Poisson 概率
                home_prob = self._poisson_prob(i, home_lambda)
                away_prob = self._poisson_prob(j, away_lambda)

                # 联合概率 (假设独立)
                joint_prob = home_prob * away_prob

                matrix[(i, j)] = joint_prob

        return matrix

    def _poisson_prob(self, k: int, lambda_param: float) -> float:
        """计算 Poisson 概率"""
        if lambda_param <= 0:
            return 0.0

        try:
            prob = (lambda_param ** k) * math.exp(-lambda_param) / math.factorial(k)
            return prob
        except:
            return 0.0

    def _apply_league_pattern(
        self,
        context: ExtractionContext,
        score_matrix: Dict[Tuple[int, int], float]
    ) -> Dict[Tuple[int, int], float]:
        """
        应用联赛比分模式调整

        不同联赛有不同的比分分布特征:
        - 英超: 进球较多, 高比分常见
        - 意甲: 进球较少, 低比分常见
        """
        if not context.league_id:
            return score_matrix

        # 获取联赛比分模式
        cursor = context.db_conn.cursor()

        cursor.execute("""
            SELECT
                SUM(CASE WHEN home_goals + away_goals <= 2 THEN 1 ELSE 0 END) as low_scoring,
                SUM(CASE WHEN home_goals + away_goals >= 4 THEN 1 ELSE 0 END) as high_scoring,
                COUNT(*) as total
            FROM matches
            WHERE league_id = ?
            AND status = 'finished'
            ORDER BY match_time DESC
            LIMIT 100
        """, (context.league_id,))

        row = cursor.fetchone()
        if not row or not row[2] or row[2] < 20:
            return score_matrix

        low_ratio = row[0] / row[2]
        high_ratio = row[1] / row[2]

        # 调整矩阵
        adjusted = {}
        for (home, away), prob in score_matrix.items():
            total_goals = home + away

            # 根据联赛特征调整
            if total_goals <= 2 and low_ratio > 0.45:
                # 低进球联赛，增加低比分概率
                prob *= 1.1
            elif total_goals >= 4 and high_ratio > 0.25:
                # 高进球联赛，增加高比分概率
                prob *= 1.1

            adjusted[(home, away)] = prob

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    def _apply_h2h_adjustment(
        self,
        context: ExtractionContext,
        score_matrix: Dict[Tuple[int, int], float]
    ) -> Dict[Tuple[int, int], float]:
        """
        应用交锋记录调整

        历史交锋中常见的比分应该增加概率
        """
        cursor = context.db_conn.cursor()

        # 获取交锋记录
        cursor.execute("""
            SELECT home_goals, away_goals, COUNT(*) as count
            FROM matches
            WHERE (
                (home_team_id = ? AND away_team_id = ?)
                OR (home_team_id = ? AND away_team_id = ?)
            )
            AND status = 'finished'
            GROUP BY home_goals, away_goals
            ORDER BY count DESC
            LIMIT 10
        """, (context.home_team_id, context.away_team_id,
              context.away_team_id, context.home_team_id))

        h2h_scores = cursor.fetchall()

        if not h2h_scores:
            return score_matrix

        adjusted = score_matrix.copy()

        for row in h2h_scores:
            home_goals, away_goals, count = row

            # 检查是否是主队主场的数据
            cursor.execute("""
                SELECT COUNT(*) FROM matches
                WHERE home_team_id = ? AND away_team_id = ?
                AND home_goals = ? AND away_goals = ?
                AND status = 'finished'
            """, (context.home_team_id, context.away_team_id, home_goals, away_goals))

            is_home_match = cursor.fetchone()[0] > 0

            if is_home_match and (home_goals, away_goals) in adjusted:
                # 增加历史比分的概率
                boost = min(1.5, 1.0 + count * 0.05)
                adjusted[(home_goals, away_goals)] *= boost

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    def _filter_supported_scores(
        self,
        score_matrix: Dict[Tuple[int, int], float]
    ) -> Dict[str, Dict[str, float]]:
        """
        过滤出体彩支持的比分

        Returns:
            {
                'home_win': {'10': 0.12, '20': 0.08, ...},
                'draw': {'00': 0.10, '11': 0.12, ...},
                'away_win': {'01': 0.08, ...}
            }
        """
        result = {
            'home_win': {},
            'draw': {},
            'away_win': {}
        }

        for (home, away), prob in score_matrix.items():
            score_key = f"{home}{away}"

            if home > away:
                if score_key in self.SUPPORTED_SCORES['home_win']:
                    result['home_win'][score_key] = prob
            elif home == away:
                if score_key in self.SUPPORTED_SCORES['draw']:
                    result['draw'][score_key] = prob
            else:
                if score_key in self.SUPPORTED_SCORES['away_win']:
                    result['away_win'][score_key] = prob

        return result

    def _calculate_value_bets(
        self,
        context: ExtractionContext,
        supported_probs: Dict[str, Dict[str, float]]
    ) -> List[Dict]:
        """
        计算价值投注

        价值 = 预测概率 - 隐含概率(1/赔率)
        """
        value_bets = []

        # 获取赔率
        odds = context.odds or {}
        bf_odds = odds.get('bf', {})

        if not bf_odds:
            return value_bets

        # 遍历所有支持的比分
        for result_type, scores in supported_probs.items():
            for score, predicted_prob in scores.items():
                if score in bf_odds:
                    odds_value = bf_odds[score]
                    if odds_value and odds_value > 1:
                        implied_prob = 1 / odds_value
                        value = predicted_prob - implied_prob

                        if value > 0.05:  # 价值阈值 5%
                            value_bets.append({
                                'score': score,
                                'score_display': self._format_score(score),
                                'result_type': result_type,
                                'predicted_prob': round(predicted_prob, 4),
                                'implied_prob': round(implied_prob, 4),
                                'odds': odds_value,
                                'value': round(value, 4),
                                'value_rating': 'high' if value > 0.1 else 'medium'
                            })

        # 按价值排序
        value_bets.sort(key=lambda x: x['value'], reverse=True)

        return value_bets[:5]  # 返回TOP 5

    def _get_top_scores(
        self,
        supported_probs: Dict[str, Dict[str, float]],
        n: int = 5
    ) -> List[Dict]:
        """获取概率最高的 N 个比分"""
        all_scores = []

        for result_type, scores in supported_probs.items():
            for score, prob in scores.items():
                all_scores.append({
                    'score': score,
                    'prob': prob,
                    'result_type': result_type,
                    'display': self._format_score(score)
                })

        # 按概率排序
        all_scores.sort(key=lambda x: x['prob'], reverse=True)

        return all_scores[:n]

    def _calculate_confidence(self, top_scores: List[Dict]) -> float:
        """
        计算置信度

        基于最高概率与次高概率的差距
        """
        if len(top_scores) < 2:
            return 0.5

        top_prob = top_scores[0]['prob']
        second_prob = top_scores[1]['prob']

        # 差距越大，置信度越高
        gap = top_prob - second_prob
        confidence = min(1.0, top_prob + gap * 0.5)

        return round(confidence, 3)

    def _calculate_spf_distribution(
        self,
        score_matrix: Dict[Tuple[int, int], float]
    ) -> Dict[str, float]:
        """计算胜平负分布 (基于比分矩阵)"""
        home_win_prob = 0.0
        draw_prob = 0.0
        away_win_prob = 0.0

        for (home, away), prob in score_matrix.items():
            if home > away:
                home_win_prob += prob
            elif home == away:
                draw_prob += prob
            else:
                away_win_prob += prob

        return {
            'home_win': round(home_win_prob, 4),
            'draw': round(draw_prob, 4),
            'away_win': round(away_win_prob, 4)
        }

    def _format_score(self, score: str) -> str:
        """格式化比分显示 (10 -> 1:0)"""
        if len(score) == 2:
            return f"{score[0]}:{score[1]}"
        return score


def predict_score(home_lambda: float, away_lambda: float) -> Dict:
    """
    便捷函数: 根据进球期望预测比分

    Args:
        home_lambda: 主队进球期望
        away_lambda: 客队进球期望

    Returns:
        预测结果字典
    """
    predictor = ScorePredictor("", config={})

    score_matrix = predictor._generate_score_matrix(home_lambda, away_lambda)
    supported_probs = predictor._filter_supported_scores(score_matrix)
    top_scores = predictor._get_top_scores(supported_probs)

    return {
        'home_lambda': home_lambda,
        'away_lambda': away_lambda,
        'top_scores': top_scores,
        'spf_distribution': predictor._calculate_spf_distribution(score_matrix)
    }
