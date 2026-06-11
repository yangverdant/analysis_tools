"""
伤停情况分析器 (Injury/Suspension Analyzer)

分析因素:
1. 主力球员伤停影响
2. 关键位置缺失 (门将、中卫、中场核心、前锋)
3. 替补深度评估
4. 伤停球员重要性评分
"""

from typing import Dict, Any, Optional, List
import sqlite3
import logging

from ..base import (
    FeatureExtractor, ExtractionContext, ExtractionResult,
    FeatureCategory
)
from ...schemas.lottery import PlayType

logger = logging.getLogger(__name__)


class InjuryAnalyzer(FeatureExtractor):
    """
    伤停情况分析器

    评估球队伤停对比赛结果的影响
    """

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight = 0.08  # 伤停因素权重

    @property
    def name(self) -> str:
        return "injury_analyzer"

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.CONTEXT

    @property
    def play_type(self) -> PlayType:
        return PlayType.SPF

    def get_required_data(self) -> list:
        return ['home_team_id', 'away_team_id', 'match_date']

    def initialize(self):
        """初始化"""
        pass

    def validate_context(self, context: ExtractionContext) -> bool:
        return context.home_team_id is not None and context.away_team_id is not None

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """执行伤停分析"""

        if not context.home_team_id or not context.away_team_id:
            return ExtractionResult(
                feature_name=self.name,
                category=self.category,
                value=0.0,
                raw_data={'error': 'Missing team IDs'},
                confidence=0.0,
                description="缺少球队ID"
            )

        cursor = context.db_conn.cursor()

        # 获取主队伤停情况
        home_injury = self._get_team_injuries(cursor, context.home_team_id)

        # 获取客队伤停情况
        away_injury = self._get_team_injuries(cursor, context.away_team_id)

        # 计算影响
        home_impact = self._calculate_injury_impact(home_injury)
        away_impact = self._calculate_injury_impact(away_injury)

        # 计算净影响 (正值对主队有利)
        net_impact = away_impact - home_impact

        # 转换为概率调整
        prob_adjust = {
            'home_win': max(0, net_impact) * 0.15,  # 最多调整15%
            'draw': 0,
            'away_win': max(0, -net_impact) * 0.15
        }

        # 置信度基于数据完整性
        confidence = 0.7 if home_injury['has_data'] and away_injury['has_data'] else 0.3

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=net_impact,
            raw_data={
                'home_injury': home_injury,
                'away_injury': away_injury,
                'home_impact': home_impact,
                'away_impact': away_impact,
                'prob_adjust': prob_adjust
            },
            confidence=confidence,
            impact_direction='positive' if net_impact > 0 else 'negative' if net_impact < 0 else 'neutral',
            description=f"伤停影响: 主队-{home_impact:.2f}, 客队-{away_impact:.2f}"
        )

    def _get_team_injuries(self, cursor, team_id: int) -> Dict:
        """获取球队伤停情况"""

        # 检查是否有伤停数据表
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='team_injuries'
        """)

        if not cursor.fetchone():
            return {
                'has_data': False,
                'injured_players': [],
                'total_impact': 0,
                'key_positions_missing': []
            }

        cursor.execute("""
            SELECT player_name, position, importance_rating, injury_type, expected_return
            FROM team_injuries
            WHERE team_id = ? AND status = 'injured'
        """, (team_id,))

        injuries = []
        for row in cursor.fetchall():
            injuries.append({
                'player_name': row[0],
                'position': row[1],
                'importance': row[2] if row[2] else 5,
                'injury_type': row[3],
                'expected_return': row[4]
            })

        return {
            'has_data': True,
            'injured_players': injuries,
            'count': len(injuries)
        }

    def _calculate_injury_impact(self, injury_data: Dict) -> float:
        """计算伤停影响评分 (0-1)"""

        if not injury_data.get('has_data') or not injury_data.get('injured_players'):
            return 0.0

        impact = 0.0
        position_weights = {
            'GK': 0.25,    # 门将
            'CB': 0.20,   # 中卫
            'CM': 0.18,   # 中场
            'ST': 0.15,   # 前锋
            'FB': 0.12,   # 边后卫
            'WM': 0.10    # 边锋
        }

        for player in injury_data['injured_players']:
            position = player.get('position', 'CM')
            importance = player.get('importance', 5) / 10  # 归一化
            weight = position_weights.get(position[:2], 0.10)

            impact += weight * importance

        return min(1.0, impact)  # 最大为1
