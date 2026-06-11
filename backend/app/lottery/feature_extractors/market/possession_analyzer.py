"""
控球率分析器 (Possession Analyzer)

分析因素:
1. 平均控球率
2. 控球效率 (控球转化为进球的能力)
3. 被动控球 vs 主动控球
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


class PossessionAnalyzer(FeatureExtractor):
    """控球率分析器"""

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight = 0.04

    @property
    def name(self) -> str:
        return "possession_analyzer"

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
        """执行控球率分析"""

        cursor = context.db_conn.cursor()

        home_poss = self._get_team_possession(cursor, context.home_team_id)
        away_poss = self._get_team_possession(cursor, context.away_team_id)

        # 控球率差异
        poss_diff = home_poss.get('avg_possession', 50) - away_poss.get('avg_possession', 50)

        # 控球率优势不一定等于胜率，需要结合效率
        home_eff = home_poss.get('efficiency', 0.15)
        away_eff = away_poss.get('efficiency', 0.15)

        # 有效控球差异
        effective_diff = (poss_diff / 100) * (home_eff - away_eff) * 5

        prob_adjust = {
            'home_win': effective_diff,
            'draw': 0,
            'away_win': -effective_diff
        }

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=effective_diff,
            raw_data={
                'home_possession': home_poss,
                'away_possession': away_poss,
                'possession_diff': poss_diff,
                'prob_adjust': prob_adjust
            },
            confidence=0.55,
            impact_direction='positive' if effective_diff > 0.03 else 'negative' if effective_diff < -0.03 else 'neutral',
            description=f"控球率: 主队{home_poss.get('avg_possession', 50):.0f}%, 客队{away_poss.get('avg_possession', 50):.0f}%"
        )

    def _get_team_possession(self, cursor, team_id: int) -> Dict:
        """获取球队控球数据"""

        # 检查是否有控球数据
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='match_stats'
        """)

        if cursor.fetchone():
            cursor.execute("""
                SELECT
                    AVG(CASE WHEN home_team_id = ? THEN home_possession ELSE away_possession END) as avg_poss
                FROM match_stats
                WHERE home_team_id = ? OR away_team_id = ?
            """, (team_id, team_id, team_id))

            row = cursor.fetchone()
            if row and row[0]:
                return {
                    'avg_possession': row[0],
                    'efficiency': 0.15,  # 默认效率
                    'has_data': True
                }

        return {
            'avg_possession': 50.0,
            'efficiency': 0.15,
            'has_data': False
        }