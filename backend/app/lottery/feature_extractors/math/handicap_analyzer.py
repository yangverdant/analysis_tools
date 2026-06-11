"""
让球分析器 (Handicap Analyzer)

让球胜平负分析

分析流程:
1. 计算两队进球期望
2. 生成比分概率矩阵
3. 计算原始胜平负概率
4. 根据让球数调整比分，计算让球后胜平负概率
5. 分析概率变化，发现让球盘价值
6. 结合赔率计算价值投注

让球规则:
- 让球数为正: 主队让球 (主队减去让球数)
- 让球数为负: 客队让球 (客队减去让球数绝对值)
- 例如: 让球数=-1 表示客队让1球，主队+1球
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


class HandicapAnalyzer(CalculationExtractor):
    """
    让球胜平负分析器

    根据让球盘口分析让球后胜平负概率
    """

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight_config = (config or {}).get('weights', {
            'adjusted_spf': 0.50,
            'handicap_analysis': 0.50
        })

    @property
    def name(self) -> str:
        return "handicap_analyzer"

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.MATH

    @property
    def play_type(self) -> PlayType:
        return PlayType.RQSPF

    def get_required_data(self) -> List[str]:
        return [
            'home_team_id', 'away_team_id', 'match_date',
            'home_goals_history', 'away_goals_history',
            'handicap_line'
        ]

    def calculate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行让球分析计算

        这是 CalculationExtractor 要求的方法
        """
        home_lambda = data.get('home_lambda', 1.35)
        away_lambda = data.get('away_lambda', 1.10)
        handicap_line = data.get('handicap_line', 0)

        score_matrix = self._generate_score_matrix(home_lambda, away_lambda)
        original_distribution = self._calculate_spf_distribution(score_matrix)
        adjusted_distribution = self._calculate_handicap_distribution(score_matrix, handicap_line)

        return {
            'original_distribution': original_distribution,
            'adjusted_distribution': adjusted_distribution,
            'handicap_line': handicap_line
        }

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """
        执行让球分析

        Args:
            context: 提取上下文 (必须包含 handicap_line)

        Returns:
            ExtractionResult 包含让球前后概率对比
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

        # 获取让球数
        handicap_line = context.handicap_line if hasattr(context, 'handicap_line') else 0

        try:
            # 1. 计算进球期望
            home_lambda, away_lambda = self._calculate_lambdas(context)

            # 2. 计算原始比分概率矩阵
            original_matrix = self._generate_score_matrix(home_lambda, away_lambda)

            # 3. 计算原始胜平负概率
            original_distribution = self._calculate_spf_distribution(original_matrix)

            # 4. 计算让球后胜平负概率
            adjusted_distribution = self._calculate_handicap_distribution(
                original_matrix, handicap_line
            )

            # 5. 概率变化分析
            probability_shift = self._calculate_probability_shift(
                original_distribution, adjusted_distribution
            )

            # 6. 让球价值分析
            value_analysis = self._analyze_handicap_value(
                context, original_distribution, adjusted_distribution, handicap_line
            )

            # 7. 计算置信度
            confidence = self._calculate_confidence(adjusted_distribution)

            # 8. 生成推荐
            recommendation = self._generate_recommendation(
                original_distribution, adjusted_distribution, handicap_line
            )

            return ExtractionResult(
                feature_name=self.name,
                category=self.category,
                value=adjusted_distribution['home_win'] if adjusted_distribution['home_win'] > max(adjusted_distribution['draw'], adjusted_distribution['away_win']) else
                      adjusted_distribution['away_win'] if adjusted_distribution['away_win'] > adjusted_distribution['draw'] else
                      adjusted_distribution['draw'],
                raw_data={
                    'handicap_line': handicap_line,
                    'home_lambda': home_lambda,
                    'away_lambda': away_lambda,
                    'original_distribution': original_distribution,
                    'adjusted_distribution': adjusted_distribution,
                    'probability_shift': probability_shift,
                    'value_analysis': value_analysis,
                    'recommendation': recommendation
                },
                confidence=confidence,
                description=recommendation
            )

        except Exception as e:
            logger.error(f"Handicap analysis failed: {e}")
            return ExtractionResult(
                feature_name=self.name,
                category=self.category,
                value=0.0,
                raw_data={'error': str(e)},
                confidence=0.0,
                description=f"分析失败: {str(e)}"
            )

    def _calculate_lambdas(
        self,
        context: ExtractionContext
    ) -> Tuple[float, float]:
        """计算两队进球期望"""
        cursor = context.db_conn.cursor()

        # 获取主队数据
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

        # 获取客队数据
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

        # 计算lambda
        default_lambda = 1.35

        if home_row and home_row[0] and home_row[2] >= 3:
            home_attack = home_row[0]
        else:
            home_attack = default_lambda

        if away_row and away_row[1] and away_row[2] >= 3:
            away_defense = away_row[1]
        else:
            away_defense = default_lambda

        home_lambda = home_attack * away_defense / default_lambda

        if away_row and away_row[0] and away_row[2] >= 3:
            away_attack = away_row[0]
        else:
            away_attack = 1.1

        if home_row and home_row[1] and home_row[2] >= 3:
            home_defense = home_row[1]
        else:
            home_defense = default_lambda

        away_lambda = away_attack * home_defense / default_lambda

        # 限制范围
        home_lambda = max(0.3, min(3.0, home_lambda))
        away_lambda = max(0.3, min(3.0, away_lambda))

        return home_lambda, away_lambda

    def _generate_score_matrix(
        self,
        home_lambda: float,
        away_lambda: float,
        max_goals: int = 8
    ) -> Dict[Tuple[int, int], float]:
        """生成比分概率矩阵"""
        matrix = {}

        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                home_prob = self._poisson_prob(i, home_lambda)
                away_prob = self._poisson_prob(j, away_lambda)
                matrix[(i, j)] = home_prob * away_prob

        return matrix

    def _calculate_spf_distribution(
        self,
        score_matrix: Dict[Tuple[int, int], float]
    ) -> Dict[str, float]:
        """计算胜平负概率分布"""
        home_win = 0.0
        draw = 0.0
        away_win = 0.0

        for (home_goals, away_goals), prob in score_matrix.items():
            if home_goals > away_goals:
                home_win += prob
            elif home_goals == away_goals:
                draw += prob
            else:
                away_win += prob

        return {
            'home_win': round(home_win, 4),
            'draw': round(draw, 4),
            'away_win': round(away_win, 4)
        }

    def _calculate_handicap_distribution(
        self,
        score_matrix: Dict[Tuple[int, int], float],
        handicap_line: float
    ) -> Dict[str, float]:
        """
        计算让球后胜平负概率

        让球规则:
        - handicap_line > 0: 主队让球 (主队进球 - handicap_line)
        - handicap_line < 0: 客队让球 (主队进球 - handicap_line，即主队加分)
        """
        home_win = 0.0
        draw = 0.0
        away_win = 0.0

        for (home_goals, away_goals), prob in score_matrix.items():
            # 调整比分 (负让球数表示主队受让)
            adjusted_home = home_goals - handicap_line
            adjusted_away = away_goals

            if adjusted_home > adjusted_away:
                home_win += prob
            elif adjusted_home == adjusted_away:
                draw += prob
            else:
                away_win += prob

        return {
            'home_win': round(home_win, 4),
            'draw': round(draw, 4),
            'away_win': round(away_win, 4)
        }

    def _calculate_probability_shift(
        self,
        original: Dict[str, float],
        adjusted: Dict[str, float]
    ) -> Dict[str, Dict[str, float]]:
        """
        计算概率变化

        Returns:
            {
                'home_win': {'original': 0.45, 'adjusted': 0.55, 'change': +0.10},
                ...
            }
        """
        return {
            'home_win': {
                'original': original['home_win'],
                'adjusted': adjusted['home_win'],
                'change': round(adjusted['home_win'] - original['home_win'], 4)
            },
            'draw': {
                'original': original['draw'],
                'adjusted': adjusted['draw'],
                'change': round(adjusted['draw'] - original['draw'], 4)
            },
            'away_win': {
                'original': original['away_win'],
                'adjusted': adjusted['away_win'],
                'change': round(adjusted['away_win'] - original['away_win'], 4)
            }
        }

    def _analyze_handicap_value(
        self,
        context: ExtractionContext,
        original: Dict[str, float],
        adjusted: Dict[str, float],
        handicap_line: float
    ) -> Dict:
        """
        分析让球盘价值

        对比:
        1. 原始赔率 vs 让球赔率
        2. 让球后的概率变化是否带来价值
        """
        value_analysis = {
            'has_value': False,
            'value_type': None,
            'recommendation': None,
            'details': {}
        }

        # 获取让球赔率
        odds = context.odds or {}
        rqspf_odds = odds.get('rqspf', {})

        if not rqspf_odds:
            return value_analysis

        # 检查每个结果的价值
        for result in ['home_win', 'draw', 'away_win']:
            odds_key = {'home_win': '3', 'draw': '1', 'away_win': '0'}[result]

            if odds_key in rqspf_odds:
                odds_value = rqspf_odds[odds_key]
                if odds_value and odds_value > 1:
                    implied_prob = 1 / odds_value
                    predicted_prob = adjusted[result]
                    value = predicted_prob - implied_prob

                    value_analysis['details'][result] = {
                        'odds': odds_value,
                        'implied_prob': round(implied_prob, 4),
                        'predicted_prob': predicted_prob,
                        'value': round(value, 4),
                        'is_value_bet': value > 0.05
                    }

                    if value > 0.05:
                        value_analysis['has_value'] = True
                        value_analysis['value_type'] = result
                        value_analysis['recommendation'] = {
                            'result': result,
                            'result_display': self._get_result_display(result),
                            'odds': odds_value,
                            'value': round(value * 100, 2)
                        }

        return value_analysis

    def _calculate_confidence(self, distribution: Dict[str, float]) -> float:
        """计算置信度"""
        max_prob = max(distribution.values())
        second_prob = sorted(distribution.values(), reverse=True)[1]

        # 概率差距越大，置信度越高
        confidence = max_prob + (max_prob - second_prob) * 0.5

        return round(min(1.0, confidence), 3)

    def _generate_recommendation(
        self,
        original: Dict[str, float],
        adjusted: Dict[str, float],
        handicap_line: float
    ) -> str:
        """生成推荐建议"""
        # 让球数解读
        if handicap_line < 0:
            handicap_desc = f"主队受让{abs(handicap_line)}球"
        elif handicap_line > 0:
            handicap_desc = f"主队让{handicap_line}球"
        else:
            handicap_desc = "平手盘"

        # 结果变化
        orig_fav = self._get_favorite(original)
        adj_fav = self._get_favorite(adjusted)

        if orig_fav == adj_fav:
            return f"{handicap_desc}，推荐{adj_fav}"
        else:
            return f"{handicap_desc}，让球后倾向变为{adj_fav}"

    def _get_favorite(self, distribution: Dict[str, float]) -> str:
        """获取最可能结果"""
        if distribution['home_win'] >= distribution['draw'] and \
           distribution['home_win'] >= distribution['away_win']:
            return '主胜'
        elif distribution['draw'] >= distribution['away_win']:
            return '平局'
        else:
            return '客胜'

    def _get_result_display(self, result: str) -> str:
        """获取结果显示"""
        return {
            'home_win': '主胜(3)',
            'draw': '平局(1)',
            'away_win': '客胜(0)'
        }.get(result, result)

    def _poisson_prob(self, k: int, lambda_param: float) -> float:
        """计算 Poisson 概率"""
        if lambda_param <= 0:
            return 0.0

        try:
            prob = (lambda_param ** k) * math.exp(-lambda_param) / math.factorial(k)
            return prob
        except:
            return 0.0


def analyze_handicap_match(
    home_lambda: float,
    away_lambda: float,
    handicap_line: float
) -> Dict:
    """
    便捷函数: 分析让球胜平负

    Args:
        home_lambda: 主队进球期望
        away_lambda: 客队进球期望
        handicap_line: 让球数 (正=主队让, 负=主队受让)

    Returns:
        分析结果字典
    """
    analyzer = HandicapAnalyzer("", config={})

    score_matrix = analyzer._generate_score_matrix(home_lambda, away_lambda)
    original = analyzer._calculate_spf_distribution(score_matrix)
    adjusted = analyzer._calculate_handicap_distribution(score_matrix, handicap_line)
    shift = analyzer._calculate_probability_shift(original, adjusted)

    return {
        'handicap_line': handicap_line,
        'original_distribution': original,
        'adjusted_distribution': adjusted,
        'probability_shift': shift,
        'recommendation': analyzer._generate_recommendation(
            original, adjusted, handicap_line
        )
    }
