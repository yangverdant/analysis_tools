"""
赛程密度分析器 (Schedule Density Analyzer)

分析因素:
1. 近7天比赛场次
2. 跨联赛/杯赛作战
3. 主客场旅途距离
4. 休息天数
5. 赛季阶段疲劳累积
"""

from typing import Dict, Any, Optional
import sqlite3
import logging
from datetime import datetime, timedelta

from ..base import (
    FeatureExtractor, ExtractionContext, ExtractionResult,
    FeatureCategory
)
from ...schemas.lottery import PlayType

logger = logging.getLogger(__name__)


class ScheduleAnalyzer(FeatureExtractor):
    """赛程密度分析器"""

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight = 0.06

    @property
    def name(self) -> str:
        return "schedule_analyzer"

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
        """执行赛程密度分析"""

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
        match_date = datetime.strptime(context.match_date, '%Y-%m-%d')

        # 分析主队赛程
        home_schedule = self._analyze_team_schedule(
            cursor, context.home_team_id, match_date, is_home=True
        )

        # 分析客队赛程
        away_schedule = self._analyze_team_schedule(
            cursor, context.away_team_id, match_date, is_home=False
        )

        # 计算疲劳差异
        home_fatigue = home_schedule['fatigue_score']
        away_fatigue = away_schedule['fatigue_score']

        # 客队旅途影响
        travel_impact = away_schedule.get('travel_distance', 0) * 0.02

        # 净影响 (正值对主队有利，客队疲劳更高时主队占优)
        net_fatigue = away_fatigue - home_fatigue + travel_impact

        prob_adjust = {
            'home_win': max(0, net_fatigue) * 0.10,
            'draw': 0,
            'away_win': max(0, -net_fatigue) * 0.10
        }

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=net_fatigue,
            raw_data={
                'home_schedule': home_schedule,
                'away_schedule': away_schedule,
                'prob_adjust': prob_adjust,
                'fatigue_diff': net_fatigue
            },
            confidence=0.8,
            impact_direction='positive' if net_fatigue > 0.1 else 'negative' if net_fatigue < -0.1 else 'neutral',
            description=f"赛程疲劳: 主队{home_fatigue:.1f} vs 客队{away_fatigue:.1f}"
        )

    def _analyze_team_schedule(
        self,
        cursor,
        team_id: int,
        match_date: datetime,
        is_home: bool
    ) -> Dict:
        """分析球队赛程密度"""

        # 计算7天内的比赛
        cursor.execute("""
            SELECT COUNT(*) as games,
                   MIN(match_date) as first_game,
                   MAX(match_date) as last_game
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND status = 'finished'
              AND match_date BETWEEN ? AND ?
        """, (
            team_id, team_id,
            (match_date - timedelta(days=7)).strftime('%Y-%m-%d'),
            (match_date - timedelta(days=1)).strftime('%Y-%m-%d')
        ))

        row = cursor.fetchone()

        games_last_7days = row[0] if row else 0

        # 计算休息天数
        cursor.execute("""
            SELECT match_date
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND status = 'finished'
              AND match_date < ?
            ORDER BY match_date DESC
            LIMIT 1
        """, (team_id, team_id, match_date.strftime('%Y-%m-%d')))

        last_match = cursor.fetchone()
        rest_days = 7  # 默认
        if last_match:
            last_date = datetime.strptime(last_match[0], '%Y-%m-%d')
            rest_days = (match_date - last_date).days

        # 疲劳评分 (0-1)
        fatigue = min(1.0, games_last_7days / 3) * 0.6
        fatigue += max(0, (4 - rest_days) / 4) * 0.4

        return {
            'games_last_7days': games_last_7days,
            'rest_days': rest_days,
            'fatigue_score': fatigue,
            'is_home_team': is_home
        }
