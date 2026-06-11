"""
角球分析器 (Corner Analyzer)

分析因素:
1. 平均角球数
2. 角球创造能力
3. 角球威胁度
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


class CornerAnalyzer(FeatureExtractor):
    """角球分析器"""

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight = 0.03

    @property
    def name(self) -> str:
        return "corner_analyzer"

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
        """执行角球分析"""

        cursor = context.db_conn.cursor()

        home_corners = self._get_team_corner_stats(cursor, context.home_team_id)
        away_corners = self._get_team_corner_stats(cursor, context.away_team_id)

        # 角球优势转化为进攻优势
        corner_diff = home_corners.get('avg_corners_for', 5) - away_corners.get('avg_corners_for', 5)

        # 角球多说明进攻能力强
        prob_adjust = {
            'home_win': max(0, corner_diff) * 0.01,
            'draw': 0,
            'away_win': max(0, -corner_diff) * 0.01
        }

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=corner_diff / 10,
            raw_data={
                'home_corners': home_corners,
                'away_corners': away_corners,
                'prob_adjust': prob_adjust
            },
            confidence=0.5,
            impact_direction='positive' if corner_diff > 2 else 'negative' if corner_diff < -2 else 'neutral',
            description=f"角球数据: 主队{home_corners.get('avg_corners_for', 5):.1f}/场, 客队{away_corners.get('avg_corners_for', 5):.1f}/场"
        )

    def _get_team_corner_stats(self, cursor, team_id: int) -> Dict:
        """获取球队角球统计"""

        # 检查是否有角球数据
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='match_stats'
        """)

        if cursor.fetchone():
            cursor.execute("""
                SELECT AVG(home_corners) as avg_home, AVG(away_corners) as avg_away
                FROM match_stats
                WHERE home_team_id = ? OR away_team_id = ?
            """, (team_id, team_id))

            row = cursor.fetchone()
            if row:
                return {
                    'avg_corners_for': (row[0] + row[1]) / 2 if row[0] and row[1] else 5,
                    'has_data': True
                }

        return {
            'avg_corners_for': 5.0,  # 默认值
            'avg_corners_against': 4.5,
            'has_data': False
        }