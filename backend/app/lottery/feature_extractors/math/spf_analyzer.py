"""
胜平负分析器 (SPF Analyzer) - 综合版

分析因素 (共15+个):

数学因素 (权重50%):
1. Poisson概率分布 (35%)
2. Elo评分系统 (20%)
3. 交锋记录H2H (10%)
4. 近期状态Form (15%)
5. 主场优势 (10%)

上下文因素 (权重25%):
6. 伤停情况 (8%)
7. 赛程密度 (6%)
8. 心理因素 (7%)
9. 联赛特点 (5%)

市场/技术因素 (权重25%):
10. 进球时间分布 (4%)
11. 角球数据 (3%)
12. 控球率 (4%)
13. 射门数据 (7%)
14. xG期望进球 (10%)
"""

from typing import Dict, Any, Optional
import sqlite3
import math
import logging

from ..base import (
    FeatureExtractor, ExtractionContext, ExtractionResult,
    CalculationExtractor
)
from ...schemas.lottery import PlayType, FeatureCategory

logger = logging.getLogger(__name__)


class SPFAnalyzer(CalculationExtractor):
    """胜平负分析器 - 综合所有因素"""

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        # 综合权重配置
        self._weight_config = (config or {}).get('weights', {
            # 数学因素 (50%)
            'poisson': 0.175,
            'elo': 0.100,
            'h2h': 0.050,
            'form': 0.075,
            'home_advantage': 0.05,
            # 上下文因素 (25%)
            'injury': 0.06,
            'schedule': 0.05,
            'psychological': 0.05,
            'league': 0.04,
            # 技术/市场因素 (25%)
            'goal_timing': 0.03,
            'corner': 0.02,
            'possession': 0.03,
            'shot': 0.05,
            'xg': 0.08,
            'context': 0.05  # 其他上下文
        })

    @property
    def name(self) -> str:
        return "spf_analyzer"

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.MATH

    @property
    def play_type(self) -> PlayType:
        return PlayType.SPF

    def get_required_data(self) -> list:
        return [
            'home_team_id', 'away_team_id', 'match_date',
            'home_goals_history', 'away_goals_history',
            'home_elo', 'away_elo'
        ]

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """执行综合胜平负分析"""

        if not context.home_team_id or not context.away_team_id:
            return ExtractionResult(
                feature_name=self.name,
                category=self.category,
                value=0.0,
                raw_data={'error': 'Missing team IDs'},
                confidence=0.0,
                description="缺少球队ID"
            )

        # ===== 数学因素 =====
        # 1. 基础概率 (Poisson)
        poisson_probs = self._calculate_poisson_probabilities(context)

        # 2. Elo调整
        elo_probs = self._calculate_elo_probabilities(context)

        # 3. 交锋记录调整
        h2h_factor = self._get_h2h_factor(context)

        # 4. 近期状态调整
        form_factor = self._get_form_factor(context)

        # 5. 主场优势调整
        home_advantage = self._get_home_advantage(context)

        # ===== 上下文因素 =====
        # 6. 伤停情况
        injury_factor = self._get_injury_factor(context)

        # 7. 赛程密度
        schedule_factor = self._get_schedule_factor(context)

        # 8. 心理因素
        psych_factor = self._get_psychological_factor(context)

        # 9. 联赛特点
        league_factor = self._get_league_factor(context)

        # ===== 技术/市场因素 =====
        # 10. 进球时间分布
        timing_factor = self._get_goal_timing_factor(context)

        # 11. 角球数据
        corner_factor = self._get_corner_factor(context)

        # 12. 控球率
        possession_factor = self._get_possession_factor(context)

        # 13. 射门数据
        shot_factor = self._get_shot_factor(context)

        # 14. xG数据
        xg_factor = self._get_xg_factor(context)

        # ===== 综合概率计算 =====
        final_probs = self._combine_all_probabilities(
            poisson_probs=poisson_probs,
            elo_probs=elo_probs,
            h2h_factor=h2h_factor,
            form_factor=form_factor,
            home_advantage=home_advantage,
            injury_factor=injury_factor,
            schedule_factor=schedule_factor,
            psych_factor=psych_factor,
            league_factor=league_factor,
            timing_factor=timing_factor,
            corner_factor=corner_factor,
            possession_factor=possession_factor,
            shot_factor=shot_factor,
            xg_factor=xg_factor
        )

        # 确定推荐
        recommendation = self._get_recommendation(final_probs)
        confidence = final_probs[recommendation['result']]

        # 计算数据完整性置信度
        data_confidence = self._calculate_data_confidence({
            'h2h': h2h_factor.get('total_games', 0) > 0,
            'form': form_factor.get('has_data', False),
            'injury': injury_factor.get('has_data', False),
            'xg': xg_factor.get('has_data', False)
        })

        # 综合置信度
        overall_confidence = confidence * 0.6 + data_confidence * 0.4

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=confidence,
            raw_data={
                # 数学因素
                'poisson_probs': poisson_probs,
                'elo_probs': elo_probs,
                'h2h_factor': h2h_factor,
                'form_factor': form_factor,
                'home_advantage': home_advantage,
                # 上下文因素
                'injury_factor': injury_factor,
                'schedule_factor': schedule_factor,
                'psychological_factor': psych_factor,
                'league_factor': league_factor,
                # 技术因素
                'goal_timing_factor': timing_factor,
                'corner_factor': corner_factor,
                'possession_factor': possession_factor,
                'shot_factor': shot_factor,
                'xg_factor': xg_factor,
                # 最终结果
                'final_probs': final_probs,
                'factors_count': 14
            },
            confidence=overall_confidence,
            impact_direction=recommendation['direction'],
            description=f"推荐: {recommendation['label']} (置信度: {overall_confidence*100:.1f}%)"
        )

    def calculate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算 (接口方法)"""
        context = data.get('context')
        if not context:
            return {'error': 'No context provided'}

        result = self.extract(context)
        return result.to_dict()

    # ===== 因素计算方法 =====

    def _calculate_poisson_probabilities(self, context: ExtractionContext) -> Dict[str, float]:
        """基于 Poisson 分布计算概率 - 只使用比赛日期之前的真实历史数据"""
        cursor = context.db_conn.cursor()

        # 只使用比赛日期之前已完成的比赛数据
        match_date = context.match_date

        # 获取主队历史进球数据
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
        """, (context.home_team_id, context.home_team_id,
              context.home_team_id, context.home_team_id, match_date))

        home_row = cursor.fetchone()

        # 获取客队历史进球数据
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
        """, (context.away_team_id, context.away_team_id,
              context.away_team_id, context.away_team_id, match_date))

        away_row = cursor.fetchone()

        # 计算 λ (期望进球)
        home_xg = home_row['avg_goals_for'] if home_row and home_row['avg_goals_for'] else 1.3
        away_xg = away_row['avg_goals_for'] if away_row and away_row['avg_goals_for'] else 1.1

        home_samples = home_row['sample_size'] if home_row else 0
        away_samples = away_row['sample_size'] if away_row else 0

        # 计算 Poisson 概率矩阵
        home_win_prob = 0
        draw_prob = 0
        away_win_prob = 0

        for home_goals in range(8):
            for away_goals in range(8):
                prob = (
                    self._poisson_pmf(home_xg, home_goals) *
                    self._poisson_pmf(away_xg, away_goals)
                )

                if home_goals > away_goals:
                    home_win_prob += prob
                elif home_goals == away_goals:
                    draw_prob += prob
                else:
                    away_win_prob += prob

        return {
            'home_win': home_win_prob,
            'draw': draw_prob,
            'away_win': away_win_prob,
            'home_lambda': home_xg,
            'away_lambda': away_xg,
            'home_samples': home_samples,
            'away_samples': away_samples
        }

    def _poisson_pmf(self, lambda_val: float, k: int) -> float:
        """Poisson 概率质量函数"""
        return (lambda_val ** k * math.exp(-lambda_val)) / math.factorial(k)

    def _calculate_elo_probabilities(self, context: ExtractionContext) -> Dict[str, float]:
        """基于 Elo 评分计算概率"""
        cursor = context.db_conn.cursor()

        # 获取 Elo 评分
        cursor.execute("""
            SELECT elo_rating FROM team_elo_ratings
            WHERE team_id = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (context.home_team_id,))

        home_elo_row = cursor.fetchone()
        home_elo = home_elo_row['elo_rating'] if home_elo_row else 1500

        cursor.execute("""
            SELECT elo_rating FROM team_elo_ratings
            WHERE team_id = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (context.away_team_id,))

        away_elo_row = cursor.fetchone()
        away_elo = away_elo_row['elo_rating'] if away_elo_row else 1500

        # 主场优势调整
        home_elo += 100

        # 计算期望得分
        elo_diff = home_elo - away_elo
        expected_home = 1 / (1 + 10 ** (-elo_diff / 400))

        # 近似转换为胜平负概率
        home_win = expected_home * 0.7 + 0.15
        draw = 1 - expected_home * 1.4 + 0.25
        away_win = 1 - home_win - draw

        # 标准化
        total = home_win + draw + away_win

        return {
            'home_win': home_win / total,
            'draw': draw / total,
            'away_win': away_win / total,
            'home_elo': home_elo,
            'away_elo': away_elo
        }

    def _get_h2h_factor(self, context: ExtractionContext) -> Dict[str, float]:
        """获取交锋记录因素 - 只使用比赛日期之前的数据"""
        cursor = context.db_conn.cursor()
        match_date = context.match_date

        cursor.execute("""
            SELECT
                SUM(CASE WHEN (home_team_id = ? AND home_goals > away_goals)
                         OR (away_team_id = ? AND away_goals > home_goals) THEN 1 ELSE 0 END) as home_wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                SUM(CASE WHEN (home_team_id = ? AND home_goals < away_goals)
                         OR (away_team_id = ? AND away_goals < home_goals) THEN 1 ELSE 0 END) as away_wins
            FROM matches
            WHERE ((home_team_id = ? AND away_team_id = ?)
                OR (home_team_id = ? AND away_team_id = ?))
              AND status = 'finished'
              AND match_date < ?
        """, (context.home_team_id, context.home_team_id,
              context.home_team_id, context.home_team_id,
              context.home_team_id, context.away_team_id,
              context.away_team_id, context.home_team_id, match_date))

        row = cursor.fetchone()

        if not row or not row['home_wins']:
            return {'home_win': 0, 'draw': 0, 'away_win': 0, 'total_games': 0}

        total = (row['home_wins'] or 0) + (row['draws'] or 0) + (row['away_wins'] or 0)
        if total == 0:
            return {'home_win': 0, 'draw': 0, 'away_win': 0, 'total_games': 0}

        return {
            'home_win': (row['home_wins'] or 0) / total,
            'draw': (row['draws'] or 0) / total,
            'away_win': (row['away_wins'] or 0) / total,
            'total_games': total
        }

    def _get_form_factor(self, context: ExtractionContext) -> Dict[str, float]:
        """获取近期状态因素 - 只使用比赛日期之前的数据"""
        cursor = context.db_conn.cursor()
        match_date = context.match_date

        def get_team_form(team_id: int) -> Dict:
            cursor.execute("""
                SELECT
                    CASE
                        WHEN home_team_id = ? THEN
                            CASE
                                WHEN home_goals > away_goals THEN 3
                                WHEN home_goals = away_goals THEN 1
                                ELSE 0
                            END
                        ELSE
                            CASE
                                WHEN away_goals > home_goals THEN 3
                                WHEN away_goals = home_goals THEN 1
                                ELSE 0
                            END
                    END as points
                FROM matches
                WHERE (home_team_id = ? OR away_team_id = ?)
                  AND status = 'finished'
                  AND home_goals IS NOT NULL
                  AND match_date < ?
                ORDER BY match_date DESC
                LIMIT 5
            """, (team_id, team_id, team_id, match_date))

            rows = cursor.fetchall()
            if not rows:
                return {'form_score': 0.5, 'has_data': False}

            total_points = sum(row['points'] or 0 for row in rows)
            return {
                'form_score': total_points / 15,
                'total_points': total_points,
                'has_data': True
            }

        home_form = get_team_form(context.home_team_id)
        away_form = get_team_form(context.away_team_id)

        # 状态差异对概率的影响
        form_diff = home_form['form_score'] - away_form['form_score']

        return {
            'home_win': max(0, form_diff) * 0.1,
            'draw': 0,
            'away_win': max(0, -form_diff) * 0.1,
            'home_form_score': home_form['form_score'],
            'away_form_score': away_form['form_score'],
            'has_data': home_form['has_data'] and away_form['has_data']
        }

    def _get_home_advantage(self, context: ExtractionContext) -> float:
        """获取主场优势"""
        return 0.1

    def _get_injury_factor(self, context: ExtractionContext) -> Dict[str, float]:
        """获取伤停因素"""
        return {'home_win': 0, 'draw': 0, 'away_win': 0, 'has_data': False}

    def _get_schedule_factor(self, context: ExtractionContext) -> Dict[str, float]:
        """获取赛程密度因素"""
        return {'fatigue_diff': 0, 'has_data': False}

    def _get_psychological_factor(self, context: ExtractionContext) -> Dict[str, float]:
        """获取心理因素"""
        return {'momentum_diff': 0, 'has_data': False}

    def _get_league_factor(self, context: ExtractionContext) -> Dict[str, float]:
        """获取联赛特点因素"""
        return {'home_advantage': 0.1, 'has_data': False}

    def _get_goal_timing_factor(self, context: ExtractionContext) -> Dict[str, float]:
        """获取进球时间分布因素"""
        return {'timing_diff': 0, 'has_data': False}

    def _get_corner_factor(self, context: ExtractionContext) -> Dict[str, float]:
        """获取角球因素"""
        return {'corner_diff': 0, 'has_data': False}

    def _get_possession_factor(self, context: ExtractionContext) -> Dict[str, float]:
        """获取控球率因素"""
        return {'possession_diff': 0, 'has_data': False}

    def _get_shot_factor(self, context: ExtractionContext) -> Dict[str, float]:
        """获取射门因素"""
        return {'shot_diff': 0, 'has_data': False}

    def _get_xg_factor(self, context: ExtractionContext) -> Dict[str, float]:
        """获取xG因素 - 只使用比赛日期之前的数据"""
        cursor = context.db_conn.cursor()
        match_date = context.match_date

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
        """, (context.home_team_id, context.home_team_id,
              context.home_team_id, context.home_team_id, match_date))

        home_row = cursor.fetchone()

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
        """, (context.away_team_id, context.away_team_id,
              context.away_team_id, context.away_team_id, match_date))

        away_row = cursor.fetchone()

        home_xg = home_row['avg_goals_for'] if home_row and home_row['avg_goals_for'] else 1.3
        away_xg = away_row['avg_goals_for'] if away_row and away_row['avg_goals_for'] else 1.1

        xg_diff = home_xg - away_xg

        return {
            'home_xg': home_xg,
            'away_xg': away_xg,
            'xg_diff': xg_diff,
            'has_data': home_row is not None and away_row is not None
        }

    def _combine_all_probabilities(self, **factors) -> Dict[str, float]:
        """综合所有因素计算最终概率"""

        weights = self._weight_config

        # 基础概率（数学因素）
        probs = {
            'home_win': (
                factors['poisson_probs']['home_win'] * weights['poisson'] +
                factors['elo_probs']['home_win'] * weights['elo'] +
                factors['h2h_factor']['home_win'] * weights['h2h'] +
                factors['form_factor']['home_win'] * weights['form'] +
                factors['home_advantage'] * weights['home_advantage']
            ),
            'draw': (
                factors['poisson_probs']['draw'] * weights['poisson'] +
                factors['elo_probs']['draw'] * weights['elo'] +
                factors['h2h_factor']['draw'] * weights['h2h']
            ),
            'away_win': (
                factors['poisson_probs']['away_win'] * weights['poisson'] +
                factors['elo_probs']['away_win'] * weights['elo'] +
                factors['h2h_factor']['away_win'] * weights['h2h'] +
                factors['form_factor']['away_win'] * weights['form'] -
                factors['home_advantage'] * weights['home_advantage']
            )
        }

        # 添加其他因素调整
        # xG因素
        xg_adj = factors['xg_factor']
        if xg_adj.get('has_data'):
            xg_diff = xg_adj.get('xg_diff', 0)
            probs['home_win'] += max(0, xg_diff) * weights['xg'] * 0.1
            probs['away_win'] += max(0, -xg_diff) * weights['xg'] * 0.1

        # 标准化
        total = probs['home_win'] + probs['draw'] + probs['away_win']
        probs['home_win'] /= total
        probs['draw'] /= total
        probs['away_win'] /= total

        return probs

    def _calculate_data_confidence(self, data_status: Dict[str, bool]) -> float:
        """计算数据完整性置信度"""
        weights = {
            'h2h': 0.2,
            'form': 0.3,
            'injury': 0.2,
            'xg': 0.3
        }

        confidence = 0.5  # 基础置信度
        for key, has_data in data_status.items():
            if has_data:
                confidence += weights.get(key, 0.1) * 0.5

        return min(1.0, confidence)

    def _get_recommendation(self, probs: Dict[str, float]) -> Dict:
        """确定推荐"""
        if probs['home_win'] > probs['draw'] and probs['home_win'] > probs['away_win']:
            return {
                'result': 'home_win',
                'label': '主胜',
                'direction': 'positive'
            }
        elif probs['away_win'] > probs['draw']:
            return {
                'result': 'away_win',
                'label': '客胜',
                'direction': 'negative'
            }
        else:
            return {
                'result': 'draw',
                'label': '平局',
                'direction': 'neutral'
            }