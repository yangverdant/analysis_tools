"""
半全场分析器 (BQC Analyzer)

预测半场和全场结果，生成9种半全场概率

分析流程:
1. 计算半场进球期望和全场进球期望
2. 计算半场结果概率分布
3. 计算全场结果概率分布
4. 计算半场→全场转移概率矩阵
5. 生成9种半全场联合概率
6. 结合赔率计算价值投注

半全场玩法说明:
- 第一个数字: 半场结果 (3=主胜, 1=平局, 0=客胜)
- 第二个数字: 全场结果 (3=主胜, 1=平局, 0=客胜)
- 例如: 33 表示半场主胜+全场主胜
"""

from typing import Dict, Any, Optional, List, Tuple
import sqlite3
import math
import logging
from datetime import datetime

from ..base import (
    ExtractionContext, ExtractionResult, FeatureCategory,
    CalculationExtractor
)
from ...schemas.lottery import PlayType

logger = logging.getLogger(__name__)


class BQCAnalyzer(CalculationExtractor):
    """
    半全场分析器 (BQC = Ban Quan Chang)

    基于半场和全场概率分布及转移矩阵预测半全场结果
    """

    # 半全场9种选项
    BQC_RESULTS = ['33', '31', '30', '13', '11', '10', '03', '01', '00']

    # 结果编码
    RESULT_MAP = {
        'home_win': '3',
        'draw': '1',
        'away_win': '0'
    }

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight_config = (config or {}).get('weights', {
            'ht_distribution': 0.35,
            'transition': 0.35,
            'form': 0.30
        })

    @property
    def name(self) -> str:
        return "bqc_analyzer"

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.MATH

    @property
    def play_type(self) -> PlayType:
        return PlayType.BQC

    def get_required_data(self) -> List[str]:
        return [
            'home_team_id', 'away_team_id', 'match_date',
            'home_ht_goals_history', 'away_ht_goals_history',
            'home_ft_goals_history', 'away_ft_goals_history'
        ]

    def calculate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行半全场计算

        这是 CalculationExtractor 要求的方法
        """
        ht_home_lambda = data.get('ht_home_lambda', 0.55)
        ht_away_lambda = data.get('ht_away_lambda', 0.45)
        ft_home_lambda = data.get('ft_home_lambda', 1.35)
        ft_away_lambda = data.get('ft_away_lambda', 1.10)

        ht_distribution = self._calculate_result_distribution(ht_home_lambda, ht_away_lambda)
        ft_distribution = self._calculate_result_distribution(ft_home_lambda, ft_away_lambda)
        transition_matrix = self._calculate_transition_matrix(
            ht_home_lambda, ht_away_lambda, ft_home_lambda, ft_away_lambda
        )
        bqc_probabilities = self._calculate_bqc_probabilities(
            ht_distribution, ft_distribution, transition_matrix
        )

        return {
            'ht_distribution': ht_distribution,
            'ft_distribution': ft_distribution,
            'transition_matrix': transition_matrix,
            'bqc_probabilities': bqc_probabilities
        }

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """
        执行半全场分析

        Args:
            context: 提取上下文

        Returns:
            ExtractionResult 包含半全场概率和推荐
        """
        if not context.home_team_id or not context.away_team_id:
            return ExtractionResult(
                feature_name=self.name,
                category=self.category,
                value=0.0,
                raw_data={'error': 'Missing team IDs'},
                confidence=0.0,
                description="缺少球队ID"
            )

        try:
            # 1. 计算半场和全场的进球期望
            ht_home_lambda, ht_away_lambda, ft_home_lambda, ft_away_lambda = \
                self._calculate_all_lambdas(context)

            # 2. 计算半场结果分布
            ht_distribution = self._calculate_result_distribution(
                ht_home_lambda, ht_away_lambda
            )

            # 3. 计算全场结果分布
            ft_distribution = self._calculate_result_distribution(
                ft_home_lambda, ft_away_lambda
            )

            # 4. 计算转移概率矩阵 (半场→全场)
            transition_matrix = self._calculate_transition_matrix(
                ht_home_lambda, ht_away_lambda,
                ft_home_lambda, ft_away_lambda
            )

            # 5. 应用近期状态调整
            ht_distribution, ft_distribution = self._apply_form_adjustment(
                context, ht_distribution, ft_distribution
            )

            # 6. 计算半全场联合概率
            bqc_probabilities = self._calculate_bqc_probabilities(
                ht_distribution, ft_distribution, transition_matrix
            )

            # 7. 计算价值投注
            value_bets = self._calculate_value_bets(context, bqc_probabilities)

            # 8. 生成推荐
            top_bqc = self._get_top_bqc(bqc_probabilities, n=3)

            # 9. 计算置信度
            confidence = self._calculate_confidence(top_bqc)

            return ExtractionResult(
                feature_name=self.name,
                category=self.category,
                value=top_bqc[0]['prob'] if top_bqc else 0.0,
                raw_data={
                    'ht_home_lambda': ht_home_lambda,
                    'ht_away_lambda': ht_away_lambda,
                    'ft_home_lambda': ft_home_lambda,
                    'ft_away_lambda': ft_away_lambda,
                    'ht_distribution': ht_distribution,
                    'ft_distribution': ft_distribution,
                    'transition_matrix': transition_matrix,
                    'bqc_probabilities': bqc_probabilities,
                    'top_bqc': top_bqc,
                    'value_bets': value_bets
                },
                confidence=confidence,
                description=f"最可能半全场: {self._format_bqc(top_bqc[0]['bqc']) if top_bqc else '未知'}"
            )

        except Exception as e:
            logger.error(f"BQC analysis failed: {e}")
            return ExtractionResult(
                feature_name=self.name,
                category=self.category,
                value=0.0,
                raw_data={'error': str(e)},
                confidence=0.0,
                description=f"分析失败: {str(e)}"
            )

    def _calculate_all_lambdas(
        self,
        context: ExtractionContext
    ) -> Tuple[float, float, float, float]:
        """
        计算半场和全场的进球期望

        Returns:
            (ht_home_lambda, ht_away_lambda, ft_home_lambda, ft_away_lambda)
        """
        cursor = context.db_conn.cursor()

        # 获取主队半场和全场数据
        cursor.execute("""
            SELECT
                AVG(home_goals_ht) as avg_ht_home_goals,
                AVG(away_goals_ht) as avg_ht_away_goals,
                AVG(home_goals) as avg_ft_home_goals,
                AVG(away_goals) as avg_ft_away_goals,
                COUNT(*) as sample_size
            FROM matches
            WHERE home_team_id = ?
            AND status = 'finished'
            AND home_goals_ht IS NOT NULL
            ORDER BY match_time DESC
            LIMIT 10
        """, (context.home_team_id,))

        home_row = cursor.fetchone()

        # 获取客队数据
        cursor.execute("""
            SELECT
                AVG(away_goals_ht) as avg_ht_away_goals,
                AVG(home_goals_ht) as avg_ht_home_conceded,
                AVG(away_goals) as avg_ft_away_goals,
                AVG(home_goals) as avg_ft_home_conceded,
                COUNT(*) as sample_size
            FROM matches
            WHERE away_team_id = ?
            AND status = 'finished'
            AND away_goals_ht IS NOT NULL
            ORDER BY match_time DESC
            LIMIT 10
        """, (context.away_team_id,))

        away_row = cursor.fetchone()

        # 默认值
        default_ht = 0.55  # 半场进球较少
        default_ft = 1.35

        # 半场主队进球期望
        if home_row and home_row[0] and home_row[4] >= 3:
            ht_home_attack = home_row[0]
        else:
            ht_home_attack = default_ht

        if away_row and away_row[1] and away_row[4] >= 3:
            ht_away_defense = away_row[1]
        else:
            ht_away_defense = default_ht

        ht_home_lambda = ht_home_attack * ht_away_defense / default_ht

        # 半场客队进球期望
        if away_row and away_row[0] and away_row[4] >= 3:
            ht_away_attack = away_row[0]
        else:
            ht_away_attack = default_ht * 0.85

        if home_row and home_row[1] and home_row[4] >= 3:
            ht_home_defense = home_row[1]
        else:
            ht_home_defense = default_ht

        ht_away_lambda = ht_away_attack * ht_home_defense / default_ht

        # 全场主队进球期望
        if home_row and home_row[2] and home_row[4] >= 3:
            ft_home_attack = home_row[2]
        else:
            ft_home_attack = default_ft

        if away_row and away_row[3] and away_row[4] >= 3:
            ft_away_defense = away_row[3]
        else:
            ft_away_defense = default_ft

        ft_home_lambda = ft_home_attack * ft_away_defense / default_ft

        # 全场客队进球期望
        if away_row and away_row[2] and away_row[4] >= 3:
            ft_away_attack = away_row[2]
        else:
            ft_away_attack = 1.1

        if home_row and home_row[3] and home_row[4] >= 3:
            ft_home_defense = home_row[3]
        else:
            ft_home_defense = default_ft

        ft_away_lambda = ft_away_attack * ft_home_defense / default_ft

        # 限制范围
        ht_home_lambda = max(0.15, min(1.2, ht_home_lambda))
        ht_away_lambda = max(0.15, min(1.2, ht_away_lambda))
        ft_home_lambda = max(0.4, min(2.8, ft_home_lambda))
        ft_away_lambda = max(0.4, min(2.8, ft_away_lambda))

        return ht_home_lambda, ht_away_lambda, ft_home_lambda, ft_away_lambda

    def _calculate_result_distribution(
        self,
        home_lambda: float,
        away_lambda: float
    ) -> Dict[str, float]:
        """计算比赛结果概率分布"""
        home_win_prob = 0.0
        draw_prob = 0.0
        away_win_prob = 0.0

        # 计算各种比分概率
        for i in range(6):
            for j in range(6):
                prob = self._poisson_prob(i, home_lambda) * self._poisson_prob(j, away_lambda)

                if i > j:
                    home_win_prob += prob
                elif i == j:
                    draw_prob += prob
                else:
                    away_win_prob += prob

        return {
            'home_win': round(home_win_prob, 4),
            'draw': round(draw_prob, 4),
            'away_win': round(away_win_prob, 4)
        }

    def _calculate_transition_matrix(
        self,
        ht_home_lambda: float,
        ht_away_lambda: float,
        ft_home_lambda: float,
        ft_away_lambda: float
    ) -> Dict[str, Dict[str, float]]:
        """
        计算转移概率矩阵 P(FT结果 | HT结果)

        例如: P(全场主胜 | 半场主胜)
        """
        # 计算下半场进球期望
        st_home_lambda = max(0.1, ft_home_lambda - ht_home_lambda)
        st_away_lambda = max(0.1, ft_away_lambda - ht_away_lambda)

        transition = {}

        # 半场主胜时，全场结果概率 (假设半场主队领先1球)
        transition['ht_home_win'] = self._calculate_st_distribution(
            1, 0, st_home_lambda, st_away_lambda
        )

        # 半场平局时，全场结果概率
        transition['ht_draw'] = self._calculate_st_distribution(
            0, 0, st_home_lambda, st_away_lambda
        )

        # 半场客胜时，全场结果概率 (假设半场客队领先1球)
        transition['ht_away_win'] = self._calculate_st_distribution(
            0, 1, st_home_lambda, st_away_lambda
        )

        return transition

    def _calculate_st_distribution(
        self,
        ht_home_goals: int,
        ht_away_goals: int,
        st_home_lambda: float,
        st_away_lambda: float
    ) -> Dict[str, float]:
        """计算给定半场比分后的全场结果概率"""
        home_win_prob = 0.0
        draw_prob = 0.0
        away_win_prob = 0.0

        for i in range(5):
            for j in range(5):
                prob = self._poisson_prob(i, st_home_lambda) * self._poisson_prob(j, st_away_lambda)

                final_home = ht_home_goals + i
                final_away = ht_away_goals + j

                if final_home > final_away:
                    home_win_prob += prob
                elif final_home == final_away:
                    draw_prob += prob
                else:
                    away_win_prob += prob

        return {
            'home_win': round(home_win_prob, 4),
            'draw': round(draw_prob, 4),
            'away_win': round(away_win_prob, 4)
        }

    def _apply_form_adjustment(
        self,
        context: ExtractionContext,
        ht_distribution: Dict[str, float],
        ft_distribution: Dict[str, float]
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """应用近期状态调整"""
        cursor = context.db_conn.cursor()

        # 获取主队近期状态 (近5场)
        cursor.execute("""
            SELECT
                SUM(CASE WHEN (home_team_id = ? AND home_goals > away_goals)
                         OR (away_team_id = ? AND away_goals > home_goals) THEN 1 ELSE 0 END) as wins,
                COUNT(*) as total
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
            AND status = 'finished'
            ORDER BY match_time DESC
            LIMIT 5
        """, (context.home_team_id, context.home_team_id,
              context.home_team_id, context.home_team_id))

        home_form = cursor.fetchone()

        # 获取客队近期状态
        cursor.execute("""
            SELECT
                SUM(CASE WHEN (home_team_id = ? AND home_goals > away_goals)
                         OR (away_team_id = ? AND away_goals > home_goals) THEN 1 ELSE 0 END) as wins,
                COUNT(*) as total
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
            AND status = 'finished'
            ORDER BY match_time DESC
            LIMIT 5
        """, (context.away_team_id, context.away_team_id,
              context.away_team_id, context.away_team_id))

        away_form = cursor.fetchone()

        # 计算状态调整因子
        home_form_factor = 1.0
        away_form_factor = 1.0

        if home_form and home_form[1] >= 3:
            home_form_factor = 1.0 + (home_form[0] / home_form[1] - 0.5) * 0.1

        if away_form and away_form[1] >= 3:
            away_form_factor = 1.0 + (away_form[0] / away_form[1] - 0.5) * 0.1

        # 调整分布
        adjusted_ht = {
            'home_win': min(0.9, ht_distribution['home_win'] * home_form_factor),
            'draw': ht_distribution['draw'],
            'away_win': min(0.9, ht_distribution['away_win'] * away_form_factor)
        }

        adjusted_ft = {
            'home_win': min(0.9, ft_distribution['home_win'] * home_form_factor),
            'draw': ft_distribution['draw'],
            'away_win': min(0.9, ft_distribution['away_win'] * away_form_factor)
        }

        # 归一化
        for dist in [adjusted_ht, adjusted_ft]:
            total = sum(dist.values())
            if total > 0:
                for k in dist:
                    dist[k] = round(dist[k] / total, 4)

        return adjusted_ht, adjusted_ft

    def _calculate_bqc_probabilities(
        self,
        ht_distribution: Dict[str, float],
        ft_distribution: Dict[str, float],
        transition_matrix: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """
        计算半全场联合概率

        P(HT=r1, FT=r2) = P(HT=r1) * P(FT=r2 | HT=r1)
        """
        bqc_prob = {}

        # 半场结果概率
        ht_home = ht_distribution['home_win']
        ht_draw = ht_distribution['draw']
        ht_away = ht_distribution['away_win']

        # 全场结果转移概率
        trans_ht_home = transition_matrix['ht_home_win']
        trans_ht_draw = transition_matrix['ht_draw']
        trans_ht_away = transition_matrix['ht_away_win']

        # 33: 半场主胜 + 全场主胜
        bqc_prob['33'] = round(ht_home * trans_ht_home['home_win'], 4)

        # 31: 半场主胜 + 全场平局
        bqc_prob['31'] = round(ht_home * trans_ht_home['draw'], 4)

        # 30: 半场主胜 + 全场客胜
        bqc_prob['30'] = round(ht_home * trans_ht_home['away_win'], 4)

        # 13: 半场平局 + 全场主胜
        bqc_prob['13'] = round(ht_draw * trans_ht_draw['home_win'], 4)

        # 11: 半场平局 + 全场平局
        bqc_prob['11'] = round(ht_draw * trans_ht_draw['draw'], 4)

        # 10: 半场平局 + 全场客胜
        bqc_prob['10'] = round(ht_draw * trans_ht_draw['away_win'], 4)

        # 03: 半场客胜 + 全场主胜
        bqc_prob['03'] = round(ht_away * trans_ht_away['home_win'], 4)

        # 01: 半场客胜 + 全场平局
        bqc_prob['01'] = round(ht_away * trans_ht_away['draw'], 4)

        # 00: 半场客胜 + 全场客胜
        bqc_prob['00'] = round(ht_away * trans_ht_away['away_win'], 4)

        # 归一化
        total = sum(bqc_prob.values())
        if total > 0:
            for k in bqc_prob:
                bqc_prob[k] = round(bqc_prob[k] / total, 4)

        return bqc_prob

    def _calculate_value_bets(
        self,
        context: ExtractionContext,
        bqc_probabilities: Dict[str, float]
    ) -> List[Dict]:
        """计算价值投注"""
        value_bets = []

        odds = context.odds or {}
        bqc_odds = odds.get('bqc', {})

        if not bqc_odds:
            return value_bets

        for bqc, predicted_prob in bqc_probabilities.items():
            if bqc in bqc_odds:
                odds_value = bqc_odds[bqc]
                if odds_value and odds_value > 1:
                    implied_prob = 1 / odds_value
                    value = predicted_prob - implied_prob

                    if value > 0.05:
                        value_bets.append({
                            'bqc': bqc,
                            'bqc_display': self._format_bqc(bqc),
                            'predicted_prob': round(predicted_prob, 4),
                            'implied_prob': round(implied_prob, 4),
                            'odds': odds_value,
                            'value': round(value, 4),
                            'value_rating': 'high' if value > 0.1 else 'medium'
                        })

        value_bets.sort(key=lambda x: x['value'], reverse=True)
        return value_bets[:3]

    def _get_top_bqc(
        self,
        bqc_probabilities: Dict[str, float],
        n: int = 3
    ) -> List[Dict]:
        """获取概率最高的半全场选项"""
        sorted_bqc = sorted(
            bqc_probabilities.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [
            {
                'bqc': bqc,
                'prob': prob,
                'display': self._format_bqc(bqc)
            }
            for bqc, prob in sorted_bqc[:n]
        ]

    def _calculate_confidence(self, top_bqc: List[Dict]) -> float:
        """计算置信度"""
        if len(top_bqc) < 2:
            return 0.5

        top_prob = top_bqc[0]['prob']
        second_prob = top_bqc[1]['prob']

        # 半全场概率通常较低，需要调整计算方式
        confidence = min(1.0, top_prob * 3 + (top_prob - second_prob))

        return round(confidence, 3)

    def _format_bqc(self, bqc: str) -> str:
        """格式化半全场显示"""
        if len(bqc) == 2:
            ht_result = {'3': '主胜', '1': '平局', '0': '客胜'}.get(bqc[0], '')
            ft_result = {'3': '主胜', '1': '平局', '0': '客胜'}.get(bqc[1], '')
            return f"半场{ht_result}+全场{ft_result}"
        return bqc

    def _poisson_prob(self, k: int, lambda_param: float) -> float:
        """计算 Poisson 概率"""
        if lambda_param <= 0:
            return 0.0

        try:
            prob = (lambda_param ** k) * math.exp(-lambda_param) / math.factorial(k)
            return prob
        except:
            return 0.0
