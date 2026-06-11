"""
联赛特点分析器 (League Characteristics Analyzer)

分析因素:
1. 联赛进球率特点
2. 主场优势强度
3. 平局频率
4. 大小球倾向
5. 联赛竞争激烈程度
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


class LeagueCharacteristicsAnalyzer(FeatureExtractor):
    """联赛特点分析器"""

    # 主要联赛特点预设
    LEAGUE_PROFILES = {
        # 英超: 高强度, 高进球, 主场优势明显
        'premier_league': {
            'avg_goals': 2.85,
            'home_win_rate': 0.43,
            'draw_rate': 0.24,
            'away_win_rate': 0.33,
            'home_advantage': 0.12
        },
        # 西甲: 技术流, 中等进球
        'la_liga': {
            'avg_goals': 2.65,
            'home_win_rate': 0.45,
            'draw_rate': 0.26,
            'away_win_rate': 0.29,
            'home_advantage': 0.15
        },
        # 德甲: 高进球, 主场优势强
        'bundesliga': {
            'avg_goals': 3.10,
            'home_win_rate': 0.46,
            'draw_rate': 0.22,
            'away_win_rate': 0.32,
            'home_advantage': 0.14
        },
        # 意甲: 防守为主, 低进球
        'serie_a': {
            'avg_goals': 2.55,
            'home_win_rate': 0.42,
            'draw_rate': 0.28,
            'away_win_rate': 0.30,
            'home_advantage': 0.12
        },
        # 法甲: 主场优势极强
        'ligue_1': {
            'avg_goals': 2.70,
            'home_win_rate': 0.48,
            'draw_rate': 0.24,
            'away_win_rate': 0.28,
            'home_advantage': 0.18
        },
        # 日职联: 主场优势弱
        'j_league': {
            'avg_goals': 2.80,
            'home_win_rate': 0.38,
            'draw_rate': 0.26,
            'away_win_rate': 0.36,
            'home_advantage': 0.05
        },
        # 瑞典超
        'allsvenskan': {
            'avg_goals': 2.75,
            'home_win_rate': 0.44,
            'draw_rate': 0.24,
            'away_win_rate': 0.32,
            'home_advantage': 0.10
        },
        # 挪威超
        'eliteserien': {
            'avg_goals': 2.90,
            'home_win_rate': 0.46,
            'draw_rate': 0.22,
            'away_win_rate': 0.32,
            'home_advantage': 0.12
        }
    }

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight = 0.05

    @property
    def name(self) -> str:
        return "league_characteristics_analyzer"

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.CONTEXT

    @property
    def play_type(self) -> PlayType:
        return PlayType.SPF

    def get_required_data(self) -> list:
        return ['home_team_id', 'away_team_id', 'league_id']

    def initialize(self):
        pass

    def validate_context(self, context: ExtractionContext) -> bool:
        return context.home_team_id is not None and context.away_team_id is not None

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """执行联赛特点分析"""

        cursor = context.db_conn.cursor()

        # 获取联赛信息
        league_profile = self._get_league_profile(cursor, context.league_id)

        # 计算联赛特点影响
        home_advantage = league_profile.get('home_advantage', 0.10)
        draw_tendency = league_profile.get('draw_rate', 0.25)

        # 根据联赛特点调整概率
        prob_adjust = {
            'home_win': home_advantage * 0.5,
            'draw': (draw_tendency - 0.25) * 0.3,  # 偏离平均平局率的影响
            'away_win': -home_advantage * 0.3
        }

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=home_advantage,
            raw_data={
                'league_profile': league_profile,
                'prob_adjust': prob_adjust,
                'league_id': context.league_id
            },
            confidence=0.85,
            impact_direction='positive' if home_advantage > 0.12 else 'neutral',
            description=f"联赛特点: 主胜率{league_profile.get('home_win_rate', 0.4)*100:.0f}%, 平局率{draw_tendency*100:.0f}%"
        )

    def _get_league_profile(self, cursor, league_id: int) -> Dict:
        """获取联赛特点"""

        # 尝试从数据库获取
        cursor.execute("""
            SELECT
                AVG(home_goals + away_goals) as avg_goals,
                SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as home_wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                SUM(CASE WHEN home_goals < away_goals THEN 1 ELSE 0 END) as away_wins,
                COUNT(*) as total
            FROM matches
            WHERE league_id = ? AND status = 'finished' AND home_goals IS NOT NULL
        """, (league_id,))

        row = cursor.fetchone()

        if row and row[4] and row[4] >= 30:  # 至少30场比赛数据
            total = row[4]
            return {
                'avg_goals': row[0] or 2.7,
                'home_win_rate': (row[1] or 0) / total,
                'draw_rate': (row[2] or 0) / total,
                'away_win_rate': (row[3] or 0) / total,
                'home_advantage': ((row[1] or 0) / total) - ((row[3] or 0) / total),
                'data_source': 'historical'
            }

        # 返回默认值
        return {
            'avg_goals': 2.7,
            'home_win_rate': 0.42,
            'draw_rate': 0.26,
            'away_win_rate': 0.32,
            'home_advantage': 0.10,
            'data_source': 'default'
        }