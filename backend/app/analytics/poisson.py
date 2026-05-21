"""
Poisson分布预测模块

基于Poisson分布模型预测比赛比分概率
假设进球数服从Poisson分布，参数λ为预期进球数
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
import math


class PoissonPredictor:
    """Poisson分布预测器"""

    # 最大预测进球数
    MAX_GOALS = 7

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def poisson_probability(self, k: int, lambda_param: float) -> float:
        """
        Poisson分布概率质量函数
        P(X = k) = (λ^k * e^-λ) / k!
        """
        return (lambda_param ** k) * math.exp(-lambda_param) / math.factorial(k)

    def get_team_scoring_stats(
        self,
        team_id: int,
        is_home: bool = True,
        recent_matches: int = 20,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        获取球队得分能力统计
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # SQLite不支持STDDEV，改用Python计算
        if is_home:
            cursor.execute("""
                SELECT
                    home_goals
                FROM matches
                WHERE home_team_id = ?
                AND status = 'finished'
                AND home_goals IS NOT NULL
                ORDER BY match_date DESC
                LIMIT ?
            """, (team_id, recent_matches))
        else:
            cursor.execute("""
                SELECT
                    away_goals
                FROM matches
                WHERE away_team_id = ?
                AND status = 'finished'
                AND away_goals IS NOT NULL
                ORDER BY match_date DESC
                LIMIT ?
            """, (team_id, recent_matches))

        goals_list = [row[0] for row in cursor.fetchall()]

        if goals_list:
            avg_goals = sum(goals_list) / len(goals_list)
            max_goals = max(goals_list)
            min_goals = min(goals_list)
            matches = len(goals_list)
            # 计算标准差
            if len(goals_list) > 1:
                variance = sum((g - avg_goals) ** 2 for g in goals_list) / len(goals_list)
                std_goals = variance ** 0.5
            else:
                std_goals = 0
        else:
            # 默认值
            avg_goals = 1.3 if is_home else 1.0
            std_goals = 1.0
            max_goals = 4
            min_goals = 0
            matches = 0

        return {
            'avg_goals': avg_goals,
            'std_goals': std_goals,
            'max_goals': max_goals,
            'min_goals': min_goals,
            'matches': matches
        }

    def get_team_conceding_stats(
        self,
        team_id: int,
        is_home: bool = True,
        recent_matches: int = 20,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        获取球队失球统计
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        if is_home:
            # 主场失球 = 客队进球
            cursor.execute("""
                SELECT
                    AVG(away_goals) as avg_conceded,
                    COUNT(*) as matches
                FROM matches
                WHERE home_team_id = ?
                AND status = 'finished'
                ORDER BY match_date DESC
                LIMIT ?
            """, (team_id, recent_matches))
        else:
            # 客场失球 = 主队进球
            cursor.execute("""
                SELECT
                    AVG(home_goals) as avg_conceded,
                    COUNT(*) as matches
                FROM matches
                WHERE away_team_id = ?
                AND status = 'finished'
                ORDER BY match_date DESC
                LIMIT ?
            """, (team_id, recent_matches))

        result = cursor.fetchone()
        if result and result['matches'] > 0:
            return {
                'avg_conceded': result['avg_conceded'] or 1.0,
                'matches': result['matches']
            }

        return {
            'avg_conceded': 1.0,
            'matches': 0
        }

    def calculate_expected_goals(
        self,
        home_team_id: int,
        away_team_id: int,
        recent_matches: int = 20,
        conn: sqlite3.Connection = None
    ) -> Tuple[float, float]:
        """
        计算双方预期进球数

        综合考虑：
        - 主队主场进攻能力
        - 客队客场防守能力
        - 客队客场进攻能力
        - 主队主场防守能力
        """
        if conn is None:
            conn = self.get_connection()

        # 主队主场进攻
        home_attack = self.get_team_scoring_stats(home_team_id, is_home=True, recent_matches=recent_matches, conn=conn)
        # 客队客场防守
        away_defense = self.get_team_conceding_stats(away_team_id, is_home=False, recent_matches=recent_matches, conn=conn)

        # 客队客场进攻
        away_attack = self.get_team_scoring_stats(away_team_id, is_home=False, recent_matches=recent_matches, conn=conn)
        # 主队主场防守
        home_defense = self.get_team_conceding_stats(home_team_id, is_home=True, recent_matches=recent_matches, conn=conn)

        # 主队预期进球 = 主队进攻 × 客队防守 / 联赛平均
        league_avg_home_goals = 1.5
        league_avg_away_goals = 1.1

        home_xg = home_attack['avg_goals'] * (away_defense['avg_conceded'] / league_avg_away_goals)
        away_xg = away_attack['avg_goals'] * (home_defense['avg_conceded'] / league_avg_home_goals)

        # 限制范围
        home_xg = max(0.3, min(home_xg, 4.0))
        away_xg = max(0.2, min(away_xg, 3.0))

        return home_xg, away_xg

    def predict_match(
        self,
        home_team_id: int,
        away_team_id: int,
        recent_matches: int = 20,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        预测比赛结果

        Returns:
            包含比分概率矩阵、胜平负概率、最可能比分等
        """
        if conn is None:
            conn = self.get_connection()

        # 计算预期进球
        home_xg, away_xg = self.calculate_expected_goals(
            home_team_id, away_team_id, recent_matches, conn
        )

        # 计算比分概率矩阵
        score_matrix = self._calculate_score_matrix(home_xg, away_xg)

        # 计算胜平负概率
        home_win_prob = 0.0
        draw_prob = 0.0
        away_win_prob = 0.0

        for home_goals in range(self.MAX_GOALS + 1):
            for away_goals in range(self.MAX_GOALS + 1):
                prob = score_matrix[home_goals][away_goals]
                if home_goals > away_goals:
                    home_win_prob += prob
                elif home_goals == away_goals:
                    draw_prob += prob
                else:
                    away_win_prob += prob

        # 找出最可能的比分
        most_likely_scores = self._get_most_likely_scores(score_matrix, top_n=5)

        # 计算预期比分
        expected_home_goals = sum(
            home_goals * score_matrix[home_goals][away_goals]
            for home_goals in range(self.MAX_GOALS + 1)
            for away_goals in range(self.MAX_GOALS + 1)
        )
        expected_away_goals = sum(
            away_goals * score_matrix[home_goals][away_goals]
            for home_goals in range(self.MAX_GOALS + 1)
            for away_goals in range(self.MAX_GOALS + 1)
        )

        return {
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_xg': round(home_xg, 3),
            'away_xg': round(away_xg, 3),
            'probabilities': {
                'home_win': round(home_win_prob, 4),
                'draw': round(draw_prob, 4),
                'away_win': round(away_win_prob, 4)
            },
            'most_likely_scores': most_likely_scores,
            'expected_score': {
                'home': round(expected_home_goals, 2),
                'away': round(expected_away_goals, 2)
            },
            'score_matrix': self._format_score_matrix(score_matrix),
            'over_under_2_5': self._calculate_over_under(score_matrix, 2.5),
            'both_teams_to_score': self._calculate_btts(score_matrix)
        }

    def _calculate_score_matrix(self, home_xg: float, away_xg: float) -> Dict[int, Dict[int, float]]:
        """计算比分概率矩阵"""
        matrix = {}
        for home_goals in range(self.MAX_GOALS + 1):
            matrix[home_goals] = {}
            for away_goals in range(self.MAX_GOALS + 1):
                home_prob = self.poisson_probability(home_goals, home_xg)
                away_prob = self.poisson_probability(away_goals, away_xg)
                matrix[home_goals][away_goals] = home_prob * away_prob
        return matrix

    def _format_score_matrix(self, matrix: Dict[int, Dict[int, float]]) -> List[List[float]]:
        """格式化比分矩阵为列表"""
        result = []
        for home_goals in range(self.MAX_GOALS + 1):
            row = []
            for away_goals in range(self.MAX_GOALS + 1):
                row.append(round(matrix[home_goals][away_goals] * 100, 2))
            result.append(row)
        return result

    def _get_most_likely_scores(self, matrix: Dict[int, Dict[int, float]], top_n: int = 5) -> List[Dict]:
        """获取最可能的比分"""
        scores = []
        for home_goals in range(self.MAX_GOALS + 1):
            for away_goals in range(self.MAX_GOALS + 1):
                scores.append({
                    'score': f'{home_goals}-{away_goals}',
                    'home_goals': home_goals,
                    'away_goals': away_goals,
                    'probability': round(matrix[home_goals][away_goals] * 100, 2)
                })

        scores.sort(key=lambda x: x['probability'], reverse=True)
        return scores[:top_n]

    def _calculate_over_under(self, matrix: Dict[int, Dict[int, float]], threshold: float) -> Dict:
        """计算大小球概率"""
        over_prob = 0.0
        under_prob = 0.0

        for home_goals in range(self.MAX_GOALS + 1):
            for away_goals in range(self.MAX_GOALS + 1):
                total = home_goals + away_goals
                prob = matrix[home_goals][away_goals]
                if total > threshold:
                    over_prob += prob
                else:
                    under_prob += prob

        return {
            'over': round(over_prob, 4),
            'under': round(under_prob, 4)
        }

    def _calculate_btts(self, matrix: Dict[int, Dict[int, float]]) -> Dict:
        """计算双方进球概率"""
        both_score = 0.0
        both_not_score = 0.0

        for home_goals in range(self.MAX_GOALS + 1):
            for away_goals in range(self.MAX_GOALS + 1):
                prob = matrix[home_goals][away_goals]
                if home_goals > 0 and away_goals > 0:
                    both_score += prob
                else:
                    both_not_score += prob

        return {
            'yes': round(both_score, 4),
            'no': round(both_not_score, 4)
        }

    def predict_correct_score(
        self,
        home_team_id: int,
        away_team_id: int,
        target_home: int,
        target_away: int,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        预测特定比分的概率
        """
        if conn is None:
            conn = self.get_connection()

        home_xg, away_xg = self.calculate_expected_goals(
            home_team_id, away_team_id, conn=conn
        )

        home_prob = self.poisson_probability(target_home, home_xg)
        away_prob = self.poisson_probability(target_away, away_xg)
        combined_prob = home_prob * away_prob

        return {
            'score': f'{target_home}-{target_away}',
            'probability': round(combined_prob * 100, 2),
            'home_xg': round(home_xg, 3),
            'away_xg': round(away_xg, 3)
        }

    def get_team_goal_distribution(
        self,
        team_id: int,
        is_home: bool = True,
        recent_matches: int = 30,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        获取球队进球分布统计
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        if is_home:
            cursor.execute("""
                SELECT home_goals as goals, COUNT(*) as count
                FROM matches
                WHERE home_team_id = ?
                AND status = 'finished'
                AND home_goals IS NOT NULL
                GROUP BY home_goals
                ORDER BY home_goals
            """, (team_id,))
        else:
            cursor.execute("""
                SELECT away_goals as goals, COUNT(*) as count
                FROM matches
                WHERE away_team_id = ?
                AND status = 'finished'
                AND away_goals IS NOT NULL
                GROUP BY away_goals
                ORDER BY away_goals
            """, (team_id,))

        results = cursor.fetchall()
        total = sum(r['count'] for r in results)

        distribution = {}
        for r in results:
            distribution[r['goals']] = {
                'count': r['count'],
                'percentage': round(r['count'] / total * 100, 2) if total > 0 else 0
            }

        # 计算统计量
        stats = self.get_team_scoring_stats(team_id, is_home, recent_matches, conn)

        return {
            'team_id': team_id,
            'is_home': is_home,
            'total_matches': total,
            'distribution': distribution,
            'statistics': {
                'avg_goals': round(stats['avg_goals'], 2),
                'std_goals': round(stats['std_goals'], 2) if stats['std_goals'] else None,
                'max_goals': stats['max_goals'],
                'min_goals': stats['min_goals']
            }
        }