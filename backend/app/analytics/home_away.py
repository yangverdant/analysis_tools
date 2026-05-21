"""
主客场优势分析模块

分析球队主客场表现差异，包括：
- 主场优势强度
- 客场表现
- 主客场进球差异
- 主客场积分差异
"""

import sqlite3
from typing import Dict, List, Optional, Tuple


class HomeAwayAnalyzer:
    """主客场优势分析器"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def analyze_home_away_performance(
        self,
        team_id: int,
        recent_matches: int = 20,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析球队主客场表现
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 主场比赛统计
        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                SUM(CASE WHEN home_goals < away_goals THEN 1 ELSE 0 END) as losses,
                SUM(home_goals) as goals_scored,
                SUM(away_goals) as goals_conceded,
                AVG(home_goals) as avg_goals_scored,
                AVG(away_goals) as avg_goals_conceded,
                SUM(home_shots) as total_shots,
                SUM(home_shots_target) as total_shots_target
            FROM matches
            WHERE home_team_id = ?
            AND status = 'finished'
            AND home_goals IS NOT NULL
            ORDER BY match_date DESC
            LIMIT ?
        """, (team_id, recent_matches))
        home_stats = cursor.fetchone()

        # 客场比赛统计
        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(CASE WHEN away_goals > home_goals THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN away_goals = home_goals THEN 1 ELSE 0 END) as draws,
                SUM(CASE WHEN away_goals < home_goals THEN 1 ELSE 0 END) as losses,
                SUM(away_goals) as goals_scored,
                SUM(home_goals) as goals_conceded,
                AVG(away_goals) as avg_goals_scored,
                AVG(home_goals) as avg_goals_conceded,
                SUM(away_shots) as total_shots,
                SUM(away_shots_target) as total_shots_target
            FROM matches
            WHERE away_team_id = ?
            AND status = 'finished'
            AND away_goals IS NOT NULL
            ORDER BY match_date DESC
            LIMIT ?
        """, (team_id, recent_matches))
        away_stats = cursor.fetchone()

        # 计算主场优势
        home_points = (home_stats['wins'] or 0) * 3 + (home_stats['draws'] or 0)
        away_points = (away_stats['wins'] or 0) * 3 + (away_stats['draws'] or 0)

        home_matches = home_stats['matches'] or 0
        away_matches = away_stats['matches'] or 0

        home_ppg = home_points / home_matches if home_matches > 0 else 0
        away_ppg = away_points / away_matches if away_matches > 0 else 0

        # 主场优势评分
        home_advantage_score = self._calculate_home_advantage(
            home_stats, away_stats, home_matches, away_matches
        )

        return {
            'team_id': team_id,
            'home': {
                'matches': home_matches,
                'wins': home_stats['wins'] or 0,
                'draws': home_stats['draws'] or 0,
                'losses': home_stats['losses'] or 0,
                'win_rate': round((home_stats['wins'] or 0) / home_matches * 100, 2) if home_matches > 0 else 0,
                'goals_scored': home_stats['goals_scored'] or 0,
                'goals_conceded': home_stats['goals_conceded'] or 0,
                'avg_goals_scored': round(home_stats['avg_goals_scored'] or 0, 2),
                'avg_goals_conceded': round(home_stats['avg_goals_conceded'] or 0, 2),
                'points': home_points,
                'points_per_game': round(home_ppg, 2)
            },
            'away': {
                'matches': away_matches,
                'wins': away_stats['wins'] or 0,
                'draws': away_stats['draws'] or 0,
                'losses': away_stats['losses'] or 0,
                'win_rate': round((away_stats['wins'] or 0) / away_matches * 100, 2) if away_matches > 0 else 0,
                'goals_scored': away_stats['goals_scored'] or 0,
                'goals_conceded': away_stats['goals_conceded'] or 0,
                'avg_goals_scored': round(away_stats['avg_goals_scored'] or 0, 2),
                'avg_goals_conceded': round(away_stats['avg_goals_conceded'] or 0, 2),
                'points': away_points,
                'points_per_game': round(away_ppg, 2)
            },
            'comparison': {
                'ppg_difference': round(home_ppg - away_ppg, 2),
                'win_rate_difference': round(
                    ((home_stats['wins'] or 0) / home_matches * 100 if home_matches > 0 else 0) -
                    ((away_stats['wins'] or 0) / away_matches * 100 if away_matches > 0 else 0),
                    2
                ),
                'goal_difference_home': (home_stats['goals_scored'] or 0) - (home_stats['goals_conceded'] or 0),
                'goal_difference_away': (away_stats['goals_scored'] or 0) - (away_stats['goals_conceded'] or 0)
            },
            'home_advantage': home_advantage_score
        }

    def _calculate_home_advantage(
        self,
        home_stats,
        away_stats,
        home_matches: int,
        away_matches: int
    ) -> Dict:
        """
        计算主场优势强度

        返回：
        - score: 主场优势评分（0-100）
        - level: 优势等级
        - description: 描述
        """
        if home_matches == 0 or away_matches == 0:
            return {
                'score': 50,
                'level': 'unknown',
                'description': '数据不足，无法评估主场优势'
            }

        # 主场积分率
        home_points = (home_stats['wins'] or 0) * 3 + (home_stats['draws'] or 0)
        home_point_rate = home_points / (home_matches * 3)

        # 客场积分率
        away_points = (away_stats['wins'] or 0) * 3 + (away_stats['draws'] or 0)
        away_point_rate = away_points / (away_matches * 3)

        # 主场优势 = 主场积分率 - 客场积分率
        advantage_diff = home_point_rate - away_point_rate

        # 映射到0-100评分
        # advantage_diff 范围大约在 -0.5 到 0.5
        score = 50 + advantage_diff * 100
        score = max(0, min(100, score))

        # 等级判断
        if score >= 70:
            level = 'strong'
            description = '主场优势明显，主场战绩显著优于客场'
        elif score >= 60:
            level = 'moderate'
            description = '有一定主场优势，主场表现略好于客场'
        elif score >= 40:
            level = 'neutral'
            description = '主客场表现接近，无明显主场优势'
        elif score >= 30:
            level = 'weak'
            description = '主场优势较弱，客场表现反而更好'
        else:
            level = 'reverse'
            description = '主场劣势，客场表现明显优于主场'

        return {
            'score': round(score),
            'level': level,
            'description': description,
            'home_point_rate': round(home_point_rate, 3),
            'away_point_rate': round(away_point_rate, 3),
            'advantage_diff': round(advantage_diff, 3)
        }

    def get_home_advantage_adjustment(
        self,
        home_team_id: int,
        away_team_id: int,
        base_prediction: Dict,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        基于主客场优势调整预测
        """
        if conn is None:
            conn = self.get_connection()

        home_performance = self.analyze_home_away_performance(home_team_id, conn=conn)
        away_performance = self.analyze_home_away_performance(away_team_id, conn=conn)

        home_adv = home_performance['home_advantage']['score']
        away_adv = away_performance['home_advantage']['score']

        # 客队在客场的表现（反向看客场优势）
        away_away_performance = away_performance['away']
        away_away_ppg = away_away_performance['points_per_game']

        # 主场优势调整系数
        # 主队主场优势强 + 客队客场表现差 = 主队优势大
        home_factor = (home_adv - 50) / 200  # -0.25 到 0.25

        # 客队客场表现调整
        if away_away_ppg < 1.0:
            away_factor = 0.05  # 客队客场表现差，利好主队
        elif away_away_ppg > 1.5:
            away_factor = -0.03  # 客队客场表现好，利好客队
        else:
            away_factor = 0

        total_adjustment = home_factor + away_factor

        adjusted_home_win = base_prediction['probabilities']['home_win'] + total_adjustment
        adjusted_draw = base_prediction['probabilities']['draw']
        adjusted_away_win = base_prediction['probabilities']['away_win'] - total_adjustment

        # 标准化
        total = adjusted_home_win + adjusted_draw + adjusted_away_win
        adjusted_home_win /= total
        adjusted_draw /= total
        adjusted_away_win /= total

        return {
            'adjusted': True,
            'home_team_home_advantage': home_performance['home_advantage'],
            'away_team_away_performance': {
                'matches': away_away_performance['matches'],
                'wins': away_away_performance['wins'],
                'points_per_game': away_away_performance['points_per_game']
            },
            'adjustment': {
                'home_factor': round(home_factor, 4),
                'away_factor': round(away_factor, 4),
                'total': round(total_adjustment, 4)
            },
            'original_prediction': base_prediction['probabilities'],
            'adjusted_prediction': {
                'home_win': round(adjusted_home_win, 4),
                'draw': round(adjusted_draw, 4),
                'away_win': round(adjusted_away_win, 4)
            }
        }

    def get_league_home_advantage(
        self,
        league_id: int,
        season_id: int = None,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        获取联赛整体主场优势统计
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        if season_id:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as home_wins,
                    SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                    SUM(CASE WHEN home_goals < away_goals THEN 1 ELSE 0 END) as away_wins,
                    SUM(home_goals) as total_home_goals,
                    SUM(away_goals) as total_away_goals
                FROM matches
                WHERE league_id = ?
                AND season_id = ?
                AND status = 'finished'
                AND home_goals IS NOT NULL
            """, (league_id, season_id))
        else:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as home_wins,
                    SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                    SUM(CASE WHEN home_goals < away_goals THEN 1 ELSE 0 END) as away_wins,
                    SUM(home_goals) as total_home_goals,
                    SUM(away_goals) as total_away_goals
                FROM matches
                WHERE league_id = ?
                AND status = 'finished'
                AND home_goals IS NOT NULL
            """, (league_id,))

        result = cursor.fetchone()
        total = result['total_matches'] or 0

        if total == 0:
            return {'league_id': league_id, 'message': '无比赛数据'}

        home_win_rate = (result['home_wins'] or 0) / total
        draw_rate = (result['draws'] or 0) / total
        away_win_rate = (result['away_wins'] or 0) / total

        return {
            'league_id': league_id,
            'total_matches': total,
            'home_wins': result['home_wins'] or 0,
            'draws': result['draws'] or 0,
            'away_wins': result['away_wins'] or 0,
            'home_win_rate': round(home_win_rate * 100, 2),
            'draw_rate': round(draw_rate * 100, 2),
            'away_win_rate': round(away_win_rate * 100, 2),
            'avg_home_goals': round((result['total_home_goals'] or 0) / total, 2),
            'avg_away_goals': round((result['total_away_goals'] or 0) / total, 2),
            'home_advantage_strength': round((home_win_rate - away_win_rate) * 100, 2)
        }