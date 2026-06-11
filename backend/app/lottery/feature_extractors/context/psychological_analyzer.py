"""
心理因素分析器 (Psychological Analyzer)

分析因素:
1. 连胜/连败状态
2. 关键比赛压力 (争冠、保级)
3. 逆转能力/抗压性
4. 历史关键时刻表现
5. 主场连胜信心
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


class PsychologicalAnalyzer(FeatureExtractor):
    """心理因素分析器"""

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight = 0.07

    @property
    def name(self) -> str:
        return "psychological_analyzer"

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.CONTEXT

    @property
    def play_type(self) -> PlayType:
        return PlayType.SPF

    def get_required_data(self) -> list:
        return ['home_team_id', 'away_team_id', 'match_date']

    def initialize(self):
        pass

    def validate_context(self, context: ExtractionContext) -> bool:
        return context.home_team_id is not None and context.away_team_id is not None

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """执行心理因素分析"""

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

        # 分析主队心理状态
        home_psych = self._analyze_team_psychology(
            cursor, context.home_team_id, context.match_date, is_home=True
        )

        # 分析客队心理状态
        away_psych = self._analyze_team_psychology(
            cursor, context.away_team_id, context.match_date, is_home=False
        )

        # 计算心理优势
        home_momentum = home_psych['momentum_score']
        away_momentum = away_psych['momentum_score']

        net_psych = home_momentum - away_momentum

        # 连胜额外加成
        if home_psych['streak_type'] == 'win' and home_psych['streak_count'] >= 3:
            net_psych += 0.15
        if away_psych['streak_type'] == 'loss' and away_psych['streak_count'] >= 3:
            net_psych += 0.10

        prob_adjust = {
            'home_win': max(0, net_psych) * 0.12,
            'draw': 0,
            'away_win': max(0, -net_psych) * 0.12
        }

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=net_psych,
            raw_data={
                'home_psychology': home_psych,
                'away_psychology': away_psych,
                'prob_adjust': prob_adjust,
                'momentum_diff': net_psych
            },
            confidence=0.75,
            impact_direction='positive' if net_psych > 0.1 else 'negative' if net_psych < -0.1 else 'neutral',
            description=f"心理状态: 主队{home_psych['streak_type']}{home_psych['streak_count']}场 vs 客队{away_psych['streak_type']}{away_psych['streak_count']}场"
        )

    def _analyze_team_psychology(
        self,
        cursor,
        team_id: int,
        match_date: str,
        is_home: bool
    ) -> Dict:
        """分析球队心理状态"""

        # 获取最近5场比赛结果
        cursor.execute("""
            SELECT
                CASE
                    WHEN home_team_id = ? THEN
                        CASE WHEN home_goals > away_goals THEN 'W'
                             WHEN home_goals = away_goals THEN 'D'
                             ELSE 'L' END
                    ELSE
                        CASE WHEN away_goals > home_goals THEN 'W'
                             WHEN away_goals = home_goals THEN 'D'
                             ELSE 'L' END
                END as result
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND status = 'finished'
              AND home_goals IS NOT NULL
              AND match_date < ?
            ORDER BY match_date DESC
            LIMIT 5
        """, (team_id, team_id, team_id, match_date))

        results = [row[0] for row in cursor.fetchall()]

        # 计算连胜/连败
        streak_type = 'none'
        streak_count = 0

        if results:
            # 找当前连续状态
            current = results[0]
            count = 0
            for r in results:
                if r == current:
                    count += 1
                else:
                    break

            if current == 'W':
                streak_type = 'win'
                streak_count = count
            elif current == 'L':
                streak_type = 'loss'
                streak_count = count

        # 计算势头评分
        momentum = 0
        for r in results:
            if r == 'W':
                momentum += 0.2
            elif r == 'L':
                momentum -= 0.15

        return {
            'recent_results': results,
            'streak_type': streak_type,
            'streak_count': streak_count,
            'momentum_score': momentum,
            'wins': len([r for r in results if r == 'W']),
            'losses': len([r for r in results if r == 'L'])
        }