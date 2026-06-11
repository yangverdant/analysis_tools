"""
进球时间分布分析器 (Goal Timing Analyzer)

分析因素:
1. 上半场进球概率
2. 下半场进球概率
3. 补时阶段进球倾向
4. 开场/结尾时段特点
"""

from typing import Dict, Any
import sqlite3
import logging

from ..base import (
    FeatureExtractor, ExtractionContext, ExtractionResult,
    FeatureCategory
)
from ...schemas.lottery import PlayType

logger = logging.getLogger(__name__)


class GoalTimingAnalyzer(FeatureExtractor):
    """进球时间分布分析器"""

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight = 0.04

    @property
    def name(self) -> str:
        return "goal_timing_analyzer"

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.MARKET

    @property
    def play_type(self) -> PlayType:
        return PlayType.SPF

    def get_required_data(self) -> list:
        return ['home_team_id', 'away_team_id']

    def initialize(self):
        pass

    def validate_context(self, context: ExtractionContext) -> bool:
        return context.home_team_id is not None and context.away_team_id is not None

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """执行进球时间分析"""

        cursor = context.db_conn.cursor()

        # 获取主队进球时间分布
        home_timing = self._get_team_goal_timing(cursor, context.home_team_id)

        # 获取客队进球时间分布
        away_timing = self._get_team_goal_timing(cursor, context.away_team_id)

        # 分析上半场/下半场特点
        home_ht_rate = home_timing.get('first_half_rate', 0.45)
        away_ht_rate = away_timing.get('first_half_rate', 0.45)

        # 晚进球倾向 (下半场进球多的球队可能在比赛后期发力)
        home_late = home_timing.get('late_goal_rate', 0.35)
        away_late = away_timing.get('late_goal_rate', 0.35)

        # 计算影响
        # 如果主队倾向于下半场进球，可能意味着比赛会更胶着
        timing_factor = (home_ht_rate - away_ht_rate) * 0.05

        prob_adjust = {
            'home_win': timing_factor,
            'draw': 0,
            'away_win': -timing_factor
        }

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=timing_factor,
            raw_data={
                'home_timing': home_timing,
                'away_timing': away_timing,
                'prob_adjust': prob_adjust
            },
            confidence=0.6,
            impact_direction='neutral',
            description=f"进球时段: 主队上半场{home_ht_rate*100:.0f}%, 客队{away_ht_rate*100:.0f}%"
        )

    def _get_team_goal_timing(self, cursor, team_id: int) -> Dict:
        """获取球队进球时间分布"""

        # 由于数据库可能没有进球时间数据，返回默认值
        # 实际应用中应该从事件表查询

        return {
            'first_half_rate': 0.45,
            'second_half_rate': 0.55,
            'late_goal_rate': 0.35,  # 75分钟后进球率
            'early_goal_rate': 0.20  # 15分钟前进球率
        }
