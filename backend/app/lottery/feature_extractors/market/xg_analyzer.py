"""
期望进球分析器 (Expected Goals Analyzer)

分析因素:
1. xG (期望进球) 值
2. xGA (期望失球) 值
3. xG vs 实际进球差异 (运气因素)
4. xG效率评分
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


class XGAnalyzer(FeatureExtractor):
    """期望进球分析器"""

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight = 0.10  # xG是重要指标

    @property
    def name(self) -> str:
        return "xg_analyzer"

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
        """执行xG分析"""

        cursor = context.db_conn.cursor()

        home_xg = self._get_team_xg_stats(cursor, context.home_team_id)
        away_xg = self._get_team_xg_stats(cursor, context.away_team_id)

        # xG差异
        home_attack = home_xg.get('avg_xg_for', 1.35)
        home_defense = home_xg.get('avg_xg_against', 1.20)

        away_attack = away_xg.get('avg_xg_for', 1.10)
        away_defense = away_xg.get('avg_xg_against', 1.25)

        # 预期比分
        expected_home_goals = home_attack * (away_defense / 1.5)  # 考虑对手防守
        expected_away_goals = away_attack * (home_defense / 1.5)

        # xG优势
        xg_diff = expected_home_goals - expected_away_goals

        # 转化为概率调整
        prob_adjust = {
            'home_win': max(0, xg_diff) * 0.08,
            'draw': 0,
            'away_win': max(0, -xg_diff) * 0.08
        }

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=xg_diff,
            raw_data={
                'home_xg': home_xg,
                'away_xg': away_xg,
                'expected_home_goals': expected_home_goals,
                'expected_away_goals': expected_away_goals,
                'prob_adjust': prob_adjust
            },
            confidence=0.85 if home_xg['has_data'] and away_xg['has_data'] else 0.50,
            impact_direction='positive' if xg_diff > 0.3 else 'negative' if xg_diff < -0.3 else 'neutral',
            description=f"xG: 主队{home_attack:.2f}/防守{home_defense:.2f}, 客队{away_attack:.2f}/防守{away_defense:.2f}"
        )

    def _get_team_xg_stats(self, cursor, team_id: int) -> Dict:
        """获取球队xG统计"""

        # 检查是否有xG数据
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='match_xg'
        """)

        if cursor.fetchone():
            cursor.execute("""
                SELECT
                    AVG(CASE WHEN home_team_id = ? THEN home_xg ELSE away_xg END) as avg_xg_for,
                    AVG(CASE WHEN home_team_id = ? THEN away_xg ELSE home_xg END) as avg_xg_against
                FROM match_xg
                WHERE home_team_id = ? OR away_team_id = ?
            """, (team_id, team_id, team_id, team_id))

            row = cursor.fetchone()
            if row and row[0]:
                return {
                    'avg_xg_for': row[0] or 1.35,
                    'avg_xg_against': row[1] or 1.20,
                    'has_data': True
                }

        # 检查matches表是否有xg数据
        cursor.execute("""
            SELECT
                AVG(CASE WHEN home_team_id = ? THEN home_xg ELSE away_xg END) as avg_xg_for,
                AVG(CASE WHEN home_team_id = ? THEN away_xg ELSE home_xg END) as avg_xg_against
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND status = 'finished'
        """, (team_id, team_id, team_id, team_id))

        row = cursor.fetchone()
        if row and row[0]:
            return {
                'avg_xg_for': row[0] or 1.35,
                'avg_xg_against': row[1] or 1.20,
                'has_data': True
            }

        # 返回默认值（基于历史进球推算）
        cursor.execute("""
            SELECT
                AVG(CASE WHEN home_team_id = ? THEN home_goals ELSE away_goals END) as avg_goals_for,
                AVG(CASE WHEN home_team_id = ? THEN away_goals ELSE home_goals END) as avg_goals_against
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND status = 'finished'
              AND home_goals IS NOT NULL
        """, (team_id, team_id, team_id, team_id))

        row = cursor.fetchone()
        if row and row[0]:
            return {
                'avg_xg_for': row[0] or 1.35,
                'avg_xg_against': row[1] or 1.20,
                'has_data': False,
                'data_source': 'goals_approx'
            }

        return {
            'avg_xg_for': 1.35,
            'avg_xg_against': 1.20,
            'has_data': False,
            'data_source': 'default'
        }