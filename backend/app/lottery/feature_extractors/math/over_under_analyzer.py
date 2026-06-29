"""
大小球分析器 (Over/Under Analyzer)

预测比赛总进球数:
- 大于2.5球
- 小于2.5球
- 常见比分总进球分布
"""

from typing import Dict, Any
import sqlite3
import math
import logging

from ..base import (
    FeatureExtractor, ExtractionContext, ExtractionResult,
    FeatureCategory
)
from ...schemas.lottery import PlayType

logger = logging.getLogger(__name__)


class OverUnderAnalyzer(FeatureExtractor):
    """大小球分析器"""

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight = 0.08

    @property
    def name(self) -> str:
        return "over_under_analyzer"

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.MATH

    @property
    def play_type(self) -> PlayType:
        return PlayType.OVER_UNDER

    def get_required_data(self) -> list:
        return ['home_team_id', 'away_team_id', 'match_date']

    def initialize(self):
        pass

    def validate_context(self, context: ExtractionContext) -> bool:
        return context.home_team_id is not None and context.away_team_id is not None

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """执行大小球分析"""

        cursor = context.db_conn.cursor()
        match_date = context.match_date

        # 获取两队历史进球数据
        home_goals_data = self._get_team_goals_data(cursor, context.home_team_id, match_date)
        away_goals_data = self._get_team_goals_data(cursor, context.away_team_id, match_date)

        # 计算期望总进球
        home_expected = home_goals_data['avg_goals_for'] * (away_goals_data['avg_goals_against'] / 1.35)
        away_expected = away_goals_data['avg_goals_for'] * (home_goals_data['avg_goals_against'] / 1.35)

        total_expected = home_expected + away_expected

        # 使用泊松分布计算大小球概率
        over_under_probs = self._calculate_over_under_probabilities(total_expected)

        # 计算常见总进球数分布
        total_goals_dist = self._calculate_total_goals_distribution(total_expected)

        # 推荐结果
        if total_expected > 2.5:
            recommendation = "大2.5球"
            prob = over_under_probs['over_2.5']
        elif total_expected > 2.0:
            recommendation = "倾向大球"
            prob = over_under_probs['over_2.5']
        elif total_expected < 2.0:
            recommendation = "小2.5球"
            prob = over_under_probs['under_2.5']
        else:
            recommendation = "大小球胶着"
            prob = 0.5

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=total_expected,
            raw_data={
                'home_expected_goals': home_expected,
                'away_expected_goals': away_expected,
                'total_expected_goals': total_expected,
                'over_under_probs': over_under_probs,
                'total_goals_distribution': total_goals_dist,
                'home_goals_data': home_goals_data,
                'away_goals_data': away_goals_data,
                'recommendation': recommendation,
                'confidence': prob
            },
            confidence=0.75 if home_goals_data['sample_size'] > 10 and away_goals_data['sample_size'] > 10 else 0.55,
            impact_direction='positive' if total_expected > 2.5 else 'negative',
            description=f"大小球: 预期{total_expected:.1f}球, {recommendation} ({prob*100:.1f}%)"
        )

    def _get_team_goals_data(self, cursor, team_id: int, match_date: str) -> Dict:
        """获取球队进球数据"""

        cursor.execute("""
            SELECT
                AVG(CASE WHEN home_team_id = ? THEN home_goals ELSE away_goals END) as avg_goals_for,
                AVG(CASE WHEN home_team_id = ? THEN away_goals ELSE home_goals END) as avg_goals_against,
                COUNT(*) as sample_size
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND status = 'finished'
              AND home_goals IS NOT NULL
              AND match_date < ?
              AND (home_goals > 0 OR away_goals > 0)
        """, (team_id, team_id, team_id, team_id, match_date))

        row = cursor.fetchone()

        if row and row['sample_size'] > 0:
            return {
                'avg_goals_for': row['avg_goals_for'] or 1.2,
                'avg_goals_against': row['avg_goals_against'] or 1.2,
                'sample_size': row['sample_size']
            }

        return {
            'avg_goals_for': 1.2,
            'avg_goals_against': 1.2,
            'sample_size': 0
        }

    def _calculate_over_under_probabilities(self, expected_total: float) -> Dict:
        """计算大小球概率（泊松分布）"""

        # 计算不同进球数的概率
        probs = {}
        for goals in range(10):
            probs[goals] = self._poisson_pmf(goals, expected_total)

        # 大小球概率
        over_2_5 = sum(probs[g] for g in range(3, 10))
        under_2_5 = sum(probs[g] for g in range(0, 3))

        over_3_5 = sum(probs[g] for g in range(4, 10))
        under_3_5 = sum(probs[g] for g in range(0, 4))

        over_1_5 = sum(probs[g] for g in range(2, 10))
        under_1_5 = probs[0] + probs[1]

        return {
            'over_2.5': over_2_5,
            'under_2.5': under_2_5,
            'over_3.5': over_3_5,
            'under_3.5': under_3_5,
            'over_1.5': over_1_5,
            'under_1.5': under_1_5,
            'goal_probs': probs
        }

    def _calculate_total_goals_distribution(self, expected_total: float) -> list:
        """计算总进球数分布"""

        distribution = []
        for goals in range(8):
            prob = self._poisson_pmf(goals, expected_total)
            if prob > 0.01:  # 只显示概率大于1%的
                distribution.append({
                    'total_goals': goals,
                    'probability': prob,
                    'label': f"{goals}球"
                })

        return sorted(distribution, key=lambda x: -x['probability'])

    def _poisson_pmf(self, k: int, lambda_param: float) -> float:
        """泊松分布概率质量函数"""

        if k < 0 or lambda_param <= 0:
            return 0.0

        try:
            return (math.exp(-lambda_param) * (lambda_param ** k)) / math.factorial(k)
        except:
            return 0.0
