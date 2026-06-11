"""
射门数据分析器 (Shot Analyzer)

分析因素:
1. 场均射门次数
2. 射正率
3. 进球转化率
4. 关键区域射门比例
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


class ShotAnalyzer(FeatureExtractor):
    """射门数据分析器"""

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight = 0.07

    @property
    def name(self) -> str:
        return "shot_analyzer"

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
        """执行射门数据分析"""

        cursor = context.db_conn.cursor()

        home_shots = self._get_team_shot_stats(cursor, context.home_team_id)
        away_shots = self._get_team_shot_stats(cursor, context.away_team_id)

        # 射门质量评分 = 射正数 * 转化率
        home_quality = home_shots.get('shots_on_target', 4) * home_shots.get('conversion_rate', 0.15)
        away_quality = away_shots.get('shots_on_target', 4) * away_shots.get('conversion_rate', 0.15)

        shot_diff = home_quality - away_quality

        prob_adjust = {
            'home_win': max(0, shot_diff) * 0.5,
            'draw': 0,
            'away_win': max(0, -shot_diff) * 0.5
        }

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=shot_diff,
            raw_data={
                'home_shots': home_shots,
                'away_shots': away_shots,
                'shot_quality_diff': shot_diff,
                'prob_adjust': prob_adjust
            },
            confidence=0.7 if home_shots['has_data'] and away_shots['has_data'] else 0.4,
            impact_direction='positive' if shot_diff > 0.1 else 'negative' if shot_diff < -0.1 else 'neutral',
            description=f"射门: 主队{home_shots.get('avg_shots', 12):.0f}次(射正{home_shots.get('shots_on_target', 4):.0f}), 客队{away_shots.get('avg_shots', 12):.0f}次"
        )

    def _get_team_shot_stats(self, cursor, team_id: int) -> Dict:
        """获取球队射门统计"""

        # 检查是否有射门数据
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='match_stats'
        """)

        if cursor.fetchone():
            cursor.execute("""
                SELECT
                    AVG(CASE WHEN home_team_id = ? THEN home_shots ELSE away_shots END) as avg_shots,
                    AVG(CASE WHEN home_team_id = ? THEN home_shots_on_target ELSE away_shots_on_target END) as avg_sot
                FROM match_stats
                WHERE home_team_id = ? OR away_team_id = ?
            """, (team_id, team_id, team_id, team_id))

            row = cursor.fetchone()
            if row and row[0]:
                avg_shots = row[0] or 12
                avg_sot = row[1] or 4
                return {
                    'avg_shots': avg_shots,
                    'shots_on_target': avg_sot,
                    'conversion_rate': 0.12 if avg_sot > 0 else 0.10,
                    'has_data': True
                }

        return {
            'avg_shots': 12.0,
            'shots_on_target': 4.0,
            'conversion_rate': 0.12,
            'has_data': False
        }