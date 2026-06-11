"""
交锋记录 (Head-to-Head) 分析模块

分析两队历史交锋数据，包括：
- 历史战绩统计
- 心理优势分析
- 大比分/小比分倾向
- 进球规律
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class H2HAnalyzer:
    """交锋记录分析器"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_h2h_matches(
        self,
        team1_id: int,
        team2_id: int,
        limit: int = 20,
        conn: sqlite3.Connection = None
    ) -> List[Dict]:
        """
        获取两队历史交锋记录
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取所有交锋比赛（无论主客场）
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.season_id,
                m.league_id,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                m.home_goals_ht,
                m.away_goals_ht,
                m.venue,
                ht.name_en as home_team_name,
                at.name_en as away_team_name,
                ht.name_cn as home_team_cn,
                at.name_cn as away_team_cn
            FROM matches m
            LEFT JOIN teams ht ON m.home_team_id = ht.team_id
            LEFT JOIN teams at ON m.away_team_id = at.team_id
            WHERE (m.home_team_id = ? AND m.away_team_id = ?)
               OR (m.home_team_id = ? AND m.away_team_id = ?)
            AND m.status = 'finished'
            AND m.home_goals IS NOT NULL
            AND m.away_goals IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT ?
        """, (team1_id, team2_id, team2_id, team1_id, limit))

        matches = []
        for row in cursor.fetchall():
            # 判断team1在比赛中的角色
            if row['home_team_id'] == team1_id:
                team1_role = 'home'
                team1_goals = row['home_goals']
                team2_goals = row['away_goals']
            else:
                team1_role = 'away'
                team1_goals = row['away_goals']
                team2_goals = row['home_goals']

            # 判断结果（从team1角度）
            if team1_goals is not None and team2_goals is not None:
                if team1_goals > team2_goals:
                    result_for_team1 = 'win'
                elif team1_goals < team2_goals:
                    result_for_team1 = 'loss'
                else:
                    result_for_team1 = 'draw'
                total_goals = team1_goals + team2_goals
            else:
                result_for_team1 = 'unknown'
                total_goals = 0

            matches.append({
                'match_id': row['match_id'],
                'match_date': row['match_date'],
                'season_id': row['season_id'],
                'league_id': row['league_id'],
                'home_team_id': row['home_team_id'],
                'away_team_id': row['away_team_id'],
                'home_team': row['home_team_name'],
                'away_team': row['away_team_name'],
                'home_team_cn': row['home_team_cn'],
                'away_team_cn': row['away_team_cn'],
                'home_goals': row['home_goals'],
                'away_goals': row['away_goals'],
                'team1_role': team1_role,
                'team1_goals': team1_goals,
                'team2_goals': team2_goals,
                'total_goals': total_goals,
                'result_for_team1': result_for_team1,
                'venue': row['venue']
            })

        return matches

    def analyze_h2h(
        self,
        team1_id: int,
        team2_id: int,
        limit: int = 20,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        综合分析两队交锋记录
        """
        if conn is None:
            conn = self.get_connection()

        matches = self.get_h2h_matches(team1_id, team2_id, limit, conn)

        if not matches:
            return {
                'team1_id': team1_id,
                'team2_id': team2_id,
                'total_matches': 0,
                'message': '无历史交锋记录'
            }

        # 统计战绩
        team1_wins = sum(1 for m in matches if m['result_for_team1'] == 'win')
        team2_wins = sum(1 for m in matches if m['result_for_team1'] == 'loss')
        draws = sum(1 for m in matches if m['result_for_team1'] == 'draw')

        # 统计进球
        team1_total_goals = sum(m['team1_goals'] or 0 for m in matches)
        team2_total_goals = sum(m['team2_goals'] or 0 for m in matches)

        # 主客场分析
        team1_home_matches = [m for m in matches if m['team1_role'] == 'home']
        team1_away_matches = [m for m in matches if m['team1_role'] == 'away']

        team1_home_wins = sum(1 for m in team1_home_matches if m['result_for_team1'] == 'win')
        team1_away_wins = sum(1 for m in team1_away_matches if m['result_for_team1'] == 'win')

        # 大小球分析
        high_score_matches = sum(1 for m in matches if (m['total_goals'] or 0) >= 3)
        low_score_matches = sum(1 for m in matches if (m['total_goals'] or 0) <= 1)

        # 零封分析
        team1_clean_sheets = sum(1 for m in matches if (m['team2_goals'] or 0) == 0)
        team2_clean_sheets = sum(1 for m in matches if (m['team1_goals'] or 0) == 0)

        # 计算心理优势
        psychological_advantage = self._calculate_psychological_advantage(
            matches, team1_wins, team2_wins, draws
        )

        # 最近交锋趋势
        recent_matches = matches[:5]
        recent_team1_wins = sum(1 for m in recent_matches if m['result_for_team1'] == 'win')

        return {
            'team1_id': team1_id,
            'team2_id': team2_id,
            'total_matches': len(matches),
            'overall_record': {
                'team1_wins': team1_wins,
                'team2_wins': team2_wins,
                'draws': draws,
                'team1_win_rate': round(team1_wins / len(matches) * 100, 2),
                'team2_win_rate': round(team2_wins / len(matches) * 100, 2),
                'draw_rate': round(draws / len(matches) * 100, 2)
            },
            'goals_analysis': {
                'team1_total_goals': team1_total_goals,
                'team2_total_goals': team2_total_goals,
                'team1_avg_goals': round(team1_total_goals / len(matches), 2),
                'team2_avg_goals': round(team2_total_goals / len(matches), 2),
                'avg_total_goals': round((team1_total_goals + team2_total_goals) / len(matches), 2)
            },
            'home_away_analysis': {
                'team1_home_matches': len(team1_home_matches),
                'team1_home_wins': team1_home_wins,
                'team1_home_win_rate': round(team1_home_wins / len(team1_home_matches) * 100, 2) if team1_home_matches else 0,
                'team1_away_matches': len(team1_away_matches),
                'team1_away_wins': team1_away_wins,
                'team1_away_win_rate': round(team1_away_wins / len(team1_away_matches) * 100, 2) if team1_away_matches else 0
            },
            'score_patterns': {
                'high_score_matches': high_score_matches,
                'high_score_rate': round(high_score_matches / len(matches) * 100, 2),
                'low_score_matches': low_score_matches,
                'low_score_rate': round(low_score_matches / len(matches) * 100, 2),
                'team1_clean_sheets': team1_clean_sheets,
                'team2_clean_sheets': team2_clean_sheets
            },
            'psychological_advantage': psychological_advantage,
            'recent_trend': {
                'last_5_matches': len(recent_matches),
                'team1_recent_wins': recent_team1_wins,
                'team1_recent_win_rate': round(recent_team1_wins / len(recent_matches) * 100, 2) if recent_matches else 0
            },
            'matches': matches
        }

    def _calculate_psychological_advantage(
        self,
        matches: List[Dict],
        team1_wins: int,
        team2_wins: int,
        draws: int
    ) -> Dict:
        """
        计算心理优势

        考虑因素：
        - 总战绩差异
        - 连胜/连败
        - 最近交锋结果
        """
        total = len(matches)

        # 基于战绩的心理优势评分（-100 到 100）
        # team1优势为正，team2优势为负
        base_score = (team1_wins - team2_wins) / total * 100

        # 连胜/连败分析
        streak = self._analyze_streak(matches)

        # 最近5场权重更高
        recent_matches = matches[:5]
        recent_team1_wins = sum(1 for m in recent_matches if m['result_for_team1'] == 'win')
        recent_team2_wins = sum(1 for m in recent_matches if m['result_for_team1'] == 'loss')
        recent_score = (recent_team1_wins - recent_team2_wins) / len(recent_matches) * 50

        # 综合评分
        psychological_score = base_score * 0.5 + recent_score * 0.5

        # 连胜加成
        if streak['team1_current_streak'] >= 3:
            psychological_score += 20
        elif streak['team2_current_streak'] >= 3:
            psychological_score -= 20

        # 判断优势方
        if psychological_score >= 30:
            advantage = 'team1'
            level = 'strong'
        elif psychological_score >= 15:
            advantage = 'team1'
            level = 'moderate'
        elif psychological_score <= -30:
            advantage = 'team2'
            level = 'strong'
        elif psychological_score <= -15:
            advantage = 'team2'
            level = 'moderate'
        else:
            advantage = 'balanced'
            level = 'neutral'

        return {
            'score': round(psychological_score, 2),
            'advantage': advantage,
            'level': level,
            'description': self._describe_advantage(advantage, level, team1_wins, team2_wins),
            'streak': streak
        }

    def _analyze_streak(self, matches: List[Dict]) -> Dict:
        """分析连胜/连败"""
        # 从team1角度分析
        team1_streak = 0
        team2_streak = 0

        for m in matches:
            if m['result_for_team1'] == 'win':
                if team1_streak >= 0:
                    team1_streak += 1
                else:
                    team1_streak = 1
                    team2_streak = 0
            elif m['result_for_team1'] == 'loss':
                if team2_streak >= 0:
                    team2_streak += 1
                else:
                    team2_streak = 1
                    team1_streak = 0
            else:
                # 平局打断连胜
                team1_streak = 0
                team2_streak = 0

        return {
            'team1_current_streak': max(0, team1_streak),
            'team2_current_streak': max(0, team2_streak),
            'team1_max_streak': self._max_streak(matches, 'win'),
            'team2_max_streak': self._max_streak(matches, 'loss')
        }

    def _max_streak(self, matches: List[Dict], result_type: str) -> int:
        """计算最大连胜"""
        max_streak = 0
        current_streak = 0

        for m in matches:
            if m['result_for_team1'] == result_type:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        return max_streak

    def _describe_advantage(
        self,
        advantage: str,
        level: str,
        team1_wins: int,
        team2_wins: int
    ) -> str:
        """生成心理优势描述"""
        if advantage == 'balanced':
            return '两队交锋势均力敌，无明显心理优势'

        if advantage == 'team1':
            if level == 'strong':
                return f'主队有显著心理优势，历史交锋{team1_wins}胜领先'
            else:
                return f'主队有一定心理优势，交锋战绩略占上风'
        else:
            if level == 'strong':
                return f'客队有显著心理优势，历史交锋{team2_wins}胜领先'
            else:
                return f'客队有一定心理优势，交锋战绩略占上风'

    def get_h2h_prediction_adjustment(
        self,
        team1_id: int,
        team2_id: int,
        base_prediction: Dict,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        基于交锋记录调整预测结果

        Args:
            base_prediction: 基础预测结果（来自Elo或Poisson）

        Returns:
            调整后的预测结果
        """
        if conn is None:
            conn = self.get_connection()

        h2h_analysis = self.analyze_h2h(team1_id, team2_id, limit=20, conn=conn)

        if h2h_analysis['total_matches'] == 0:
            return {
                'adjusted': False,
                'reason': '无历史交锋数据',
                'prediction': base_prediction
            }

        # 获取心理优势评分
        psych_score = h2h_analysis['psychological_advantage']['score']

        # 调整系数（心理优势影响）
        adjustment_factor = psych_score / 200  # 将评分映射到调整系数

        # 调整基础预测
        adjusted_home_win = base_prediction['probabilities']['home_win']
        adjusted_draw = base_prediction['probabilities']['draw']
        adjusted_away_win = base_prediction['probabilities']['away_win']

        # 根据心理优势调整
        if psych_score > 0:
            # team1有优势，增加主胜概率
            adjusted_home_win += adjustment_factor * 0.1
            adjusted_away_win -= adjustment_factor * 0.05
        elif psych_score < 0:
            # team2有优势，增加客胜概率
            adjusted_away_win += abs(adjustment_factor) * 0.1
            adjusted_home_win -= abs(adjustment_factor) * 0.05

        # 标准化
        total = adjusted_home_win + adjusted_draw + adjusted_away_win
        adjusted_home_win /= total
        adjusted_draw /= total
        adjusted_away_win /= total

        return {
            'adjusted': True,
            'adjustment_factor': round(adjustment_factor, 3),
            'psychological_score': psych_score,
            'h2h_matches': h2h_analysis['total_matches'],
            'original_prediction': base_prediction['probabilities'],
            'adjusted_prediction': {
                'home_win': round(adjusted_home_win, 4),
                'draw': round(adjusted_draw, 4),
                'away_win': round(adjusted_away_win, 4)
            },
            'h2h_summary': {
                'team1_wins': h2h_analysis['overall_record']['team1_wins'],
                'team2_wins': h2h_analysis['overall_record']['team2_wins'],
                'draws': h2h_analysis['overall_record']['draws']
            }
        }

    def get_common_score_patterns(
        self,
        team1_id: int,
        team2_id: int,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析两队交锋的常见比分模式
        """
        if conn is None:
            conn = self.get_connection()

        matches = self.get_h2h_matches(team1_id, team2_id, limit=30, conn=conn)

        if not matches:
            return {'patterns': [], 'message': '无历史交锋数据'}

        # 统计比分频率
        score_counts = {}
        for m in matches:
            score = f'{m["team1_goals"]}-{m["team2_goals"]}'
            score_counts[score] = score_counts.get(score, 0) + 1

        # 排序
        patterns = [
            {
                'score': score,
                'count': count,
                'percentage': round(count / len(matches) * 100, 2)
            }
            for score, count in score_counts.items()
        ]
        patterns.sort(key=lambda x: x['count'], reverse=True)

        return {
            'patterns': patterns[:10],
            'total_matches': len(matches),
            'most_common': patterns[0] if patterns else None
        }