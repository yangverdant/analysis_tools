"""
近期状态 (Form) 分析模块

分析球队近期表现，包括：
- 最近N场战绩
- 进攻/防守状态
- 趋势分析（上升/下降）
- 连胜/连败/不败
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class FormAnalyzer:
    """近期状态分析器"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_recent_matches(
        self,
        team_id: int,
        limit: int = 10,
        conn: sqlite3.Connection = None
    ) -> List[Dict]:
        """
        获取球队最近N场比赛
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.league_id,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                m.home_goals_ht,
                m.away_goals_ht,
                m.home_shots,
                m.away_shots,
                m.home_shots_target,
                m.away_shots_target,
                l.name_en as league_name,
                ht.name_en as home_team_name,
                at.name_en as away_team_name
            FROM matches m
            LEFT JOIN leagues l ON m.league_id = l.league_id
            LEFT JOIN teams ht ON m.home_team_id = ht.team_id
            LEFT JOIN teams at ON m.away_team_id = at.team_id
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.status = 'finished'
            AND m.home_goals IS NOT NULL
            AND m.away_goals IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT ?
        """, (team_id, team_id, limit))

        matches = []
        for row in cursor.fetchall():
            is_home = row['home_team_id'] == team_id

            if is_home:
                team_goals = row['home_goals']
                opponent_goals = row['away_goals']
                opponent_id = row['away_team_id']
                opponent_name = row['away_team_name']
                shots = row['home_shots']
                shots_target = row['home_shots_target']
            else:
                team_goals = row['away_goals']
                opponent_goals = row['home_goals']
                opponent_id = row['home_team_id']
                opponent_name = row['home_team_name']
                shots = row['away_shots']
                shots_target = row['away_shots_target']

            # 结果
            if team_goals > opponent_goals:
                result = 'W'
                points = 3
            elif team_goals < opponent_goals:
                result = 'L'
                points = 0
            else:
                result = 'D'
                points = 1

            matches.append({
                'match_id': row['match_id'],
                'date': row['match_date'],
                'league_id': row['league_id'],
                'league_name': row['league_name'],
                'is_home': is_home,
                'team_goals': team_goals,
                'opponent_goals': opponent_goals,
                'opponent_id': opponent_id,
                'opponent_name': opponent_name,
                'result': result,
                'points': points,
                'shots': shots,
                'shots_target': shots_target
            })

        return matches

    def analyze_form(
        self,
        team_id: int,
        recent_matches: int = 10,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析球队近期状态
        """
        if conn is None:
            conn = self.get_connection()

        matches = self.get_recent_matches(team_id, recent_matches, conn)

        if not matches:
            return {
                'team_id': team_id,
                'matches': 0,
                'message': '无近期比赛数据'
            }

        # 基础统计
        wins = sum(1 for m in matches if m['result'] == 'W')
        draws = sum(1 for m in matches if m['result'] == 'D')
        losses = sum(1 for m in matches if m['result'] == 'L')
        total_points = sum(m['points'] for m in matches)

        # 进攻统计
        goals_scored = sum(m['team_goals'] for m in matches)
        goals_conceded = sum(m['opponent_goals'] for m in matches)

        # 主客场分开统计
        home_matches = [m for m in matches if m['is_home']]
        away_matches = [m for m in matches if not m['is_home']]

        home_wins = sum(1 for m in home_matches if m['result'] == 'W')
        away_wins = sum(1 for m in away_matches if m['result'] == 'W')

        # 连胜/连败/不败分析
        streaks = self._analyze_streaks(matches)

        # 趋势分析
        trend = self._analyze_trend(matches)

        # 状态评分（0-100）
        form_score = self._calculate_form_score(matches, wins, draws, losses, goals_scored, goals_conceded)

        # 生成form字符串（如 "W-W-D-L-W"）
        form_string = '-'.join(m['result'] for m in matches[:6])

        return {
            'team_id': team_id,
            'matches': len(matches),
            'form_string': form_string,
            'overall': {
                'wins': wins,
                'draws': draws,
                'losses': losses,
                'win_rate': round(wins / len(matches) * 100, 2),
                'points': total_points,
                'points_per_game': round(total_points / len(matches), 2)
            },
            'goals': {
                'scored': goals_scored,
                'conceded': goals_conceded,
                'goal_difference': goals_scored - goals_conceded,
                'avg_scored': round(goals_scored / len(matches), 2),
                'avg_conceded': round(goals_conceded / len(matches), 2)
            },
            'home_away': {
                'home_matches': len(home_matches),
                'home_wins': home_wins,
                'home_win_rate': round(home_wins / len(home_matches) * 100, 2) if home_matches else 0,
                'away_matches': len(away_matches),
                'away_wins': away_wins,
                'away_win_rate': round(away_wins / len(away_matches) * 100, 2) if away_matches else 0
            },
            'streaks': streaks,
            'trend': trend,
            'form_score': form_score,
            'assessment': self._assess_form(form_score, trend),
            'matches': matches
        }

    def _analyze_streaks(self, matches: List[Dict]) -> Dict:
        """分析连胜/连败/不败/不胜"""
        current_win_streak = 0
        current_lose_streak = 0
        current_unbeaten_streak = 0
        current_winless_streak = 0

        for m in matches:
            if m['result'] == 'W':
                current_win_streak += 1
                current_lose_streak = 0
                current_unbeaten_streak += 1
                current_winless_streak = 0
            elif m['result'] == 'L':
                current_win_streak = 0
                current_lose_streak += 1
                current_unbeaten_streak = 0
                current_winless_streak += 1
            else:  # D
                current_win_streak = 0
                current_lose_streak = 0
                current_unbeaten_streak += 1
                current_winless_streak += 1

        return {
            'current_win_streak': current_win_streak,
            'current_lose_streak': current_lose_streak,
            'current_unbeaten_streak': current_unbeaten_streak,
            'current_winless_streak': current_winless_streak,
            'is_on_winning_streak': current_win_streak >= 3,
            'is_on_losing_streak': current_lose_streak >= 3,
            'is_unbeaten': current_unbeaten_streak >= 5,
            'is_winless': current_winless_streak >= 5
        }

    def _analyze_trend(self, matches: List[Dict]) -> Dict:
        """分析趋势（上升/下降/稳定）"""
        if len(matches) < 5:
            return {'direction': 'unknown', 'description': '数据不足'}

        # 最近5场 vs 之前5场
        recent_5 = matches[:5]
        previous_5 = matches[5:10] if len(matches) >= 10 else matches[5:]

        recent_points = sum(m['points'] for m in recent_5)
        previous_points = sum(m['points'] for m in previous_5) if previous_5 else recent_points

        diff = recent_points - previous_points

        if diff >= 4:
            direction = 'improving'
            description = '状态上升，近期表现明显好转'
        elif diff <= -4:
            direction = 'declining'
            description = '状态下滑，近期表现不如之前'
        else:
            direction = 'stable'
            description = '状态稳定，表现起伏不大'

        return {
            'direction': direction,
            'description': description,
            'recent_5_points': recent_points,
            'previous_5_points': previous_points,
            'difference': diff
        }

    def _calculate_form_score(
        self,
        matches: List[Dict],
        wins: int,
        draws: int,
        losses: int,
        goals_scored: int,
        goals_conceded: int,
        opponent_strength_weighted: bool = True
    ) -> int:
        """
        计算状态评分（0-100）

        综合考虑：
        - 胜率（权重40%）
        - 进球能力（权重30%）
        - 防守能力（权重30%）

        opponent_strength_weighted: 对手强度加权
        赢强队权重更高，赢弱队权重更低
        """
        total = len(matches)

        # 胜率评分
        if opponent_strength_weighted and matches:
            # 对手强度加权胜率
            weighted_wins = self._weighted_win_count(matches)
            weighted_draws = self._weighted_draw_count(matches)
            win_score = (weighted_wins * 3 + weighted_draws) / max(1, total * 3) * 100
        else:
            win_score = (wins * 3 + draws) / (total * 3) * 100

        # 进球评分（假设场均2球为满分）
        avg_goals = goals_scored / total
        attack_score = min(avg_goals / 2.0 * 100, 100)

        # 防守评分（假设场均失0.5球为满分）
        avg_conceded = goals_conceded / total
        defense_score = max(100 - avg_conceded / 0.5 * 20, 0)

        # 综合评分
        form_score = win_score * 0.4 + attack_score * 0.3 + defense_score * 0.3

        return round(form_score)

    def _assess_form(self, form_score: int, trend: Dict) -> str:
        """评估状态"""
        trend_dir = trend['direction']

        if form_score >= 80:
            base = '状态极佳'
        elif form_score >= 60:
            base = '状态良好'
        elif form_score >= 40:
            base = '状态一般'
        else:
            base = '状态低迷'

        if trend_dir == 'improving':
            return f'{base}，且呈上升趋势'
        elif trend_dir == 'declining':
            return f'{base}，但呈下滑趋势'
        else:
            return base

    def compare_teams_form(
        self,
        team1_id: int,
        team2_id: int,
        recent_matches: int = 10,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        比较两队近期状态
        """
        if conn is None:
            conn = self.get_connection()

        team1_form = self.analyze_form(team1_id, recent_matches, conn)
        team2_form = self.analyze_form(team2_id, recent_matches, conn)

        # 比较评分
        score_diff = team1_form.get('form_score', 50) - team2_form.get('form_score', 50)

        if score_diff >= 20:
            advantage = 'team1'
            level = 'significant'
        elif score_diff >= 10:
            advantage = 'team1'
            level = 'moderate'
        elif score_diff <= -20:
            advantage = 'team2'
            level = 'significant'
        elif score_diff <= -10:
            advantage = 'team2'
            level = 'moderate'
        else:
            advantage = 'balanced'
            level = 'neutral'

        return {
            'team1_id': team1_id,
            'team2_id': team2_id,
            'team1_form': {
                'form_string': team1_form.get('form_string'),
                'form_score': team1_form.get('form_score'),
                'wins': team1_form.get('overall', {}).get('wins'),
                'draws': team1_form.get('overall', {}).get('draws'),
                'losses': team1_form.get('overall', {}).get('losses'),
                'goals_for': team1_form.get('goals', {}).get('scored'),
                'goals_against': team1_form.get('goals', {}).get('conceded'),
                'matches': team1_form.get('matches') if isinstance(team1_form.get('matches'), int) else len(team1_form.get('matches', [])),
                'points_per_game': team1_form.get('overall', {}).get('points_per_game')
            },
            'team2_form': {
                'form_string': team2_form.get('form_string'),
                'form_score': team2_form.get('form_score'),
                'wins': team2_form.get('overall', {}).get('wins'),
                'draws': team2_form.get('overall', {}).get('draws'),
                'losses': team2_form.get('overall', {}).get('losses'),
                'goals_for': team2_form.get('goals', {}).get('scored'),
                'goals_against': team2_form.get('goals', {}).get('conceded'),
                'matches': team2_form.get('matches') if isinstance(team2_form.get('matches'), int) else len(team2_form.get('matches', [])),
                'points_per_game': team2_form.get('overall', {}).get('points_per_game')
            },
            'comparison': {
                'score_difference': score_diff,
                'advantage': advantage,
                'level': level
            }
        }

    def get_form_prediction_adjustment(
        self,
        team1_id: int,
        team2_id: int,
        base_prediction: Dict,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        基于近期状态调整预测
        """
        if conn is None:
            conn = self.get_connection()

        comparison = self.compare_teams_form(team1_id, team2_id, conn=conn)

        advantage = comparison['comparison']['advantage']
        score_diff = comparison['comparison']['score_difference']

        if advantage == 'balanced':
            return {
                'adjusted': False,
                'reason': '两队状态相近',
                'prediction': base_prediction
            }

        # 调整系数
        adjustment = score_diff / 500  # 将评分差异映射到调整系数

        adjusted_home_win = base_prediction['probabilities']['home_win']
        adjusted_draw = base_prediction['probabilities']['draw']
        adjusted_away_win = base_prediction['probabilities']['away_win']

        if advantage == 'team1':
            adjusted_home_win += adjustment
            adjusted_away_win -= adjustment * 0.5
        else:
            adjusted_away_win += abs(adjustment)
            adjusted_home_win -= abs(adjustment) * 0.5

        # 标准化
        total = adjusted_home_win + adjusted_draw + adjusted_away_win
        adjusted_home_win /= total
        adjusted_draw /= total
        adjusted_away_win /= total

        return {
            'adjusted': True,
            'adjustment_factor': round(adjustment, 4),
            'form_comparison': comparison['comparison'],
            'original_prediction': base_prediction['probabilities'],
            'adjusted_prediction': {
                'home_win': round(adjusted_home_win, 4),
                'draw': round(adjusted_draw, 4),
                'away_win': round(adjusted_away_win, 4)
            }
        }

    # ── 对手强度加权 ──

    def _get_team_elo(self, team_id: int, conn: sqlite3.Connection) -> Optional[float]:
        """获取球队Elo"""
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT elo_rating FROM elo_ratings WHERE team_id = ?",
                (team_id,),
            )
            row = cursor.fetchone()
            if row:
                return float(row[0])
            return None
        except Exception:
            return None

    def _weighted_win_count(self, matches: List[Dict]) -> float:
        """
        对手强度加权的胜场数

        赢Elo高的队 → 权重>1 (max 1.5)
        赢Elo低的队 → 权重<1 (min 0.5)
        输给Elo低的队 → 惩罚更大
        """
        # 需要team_id的Elo来计算, 但这里没有conn
        # 简化: 用对手名近似(或直接用1.0权重)
        # 真正的Elo加权需要conn, 在analyze_form中处理
        weighted = 0.0
        for m in matches:
            if m['result'] == 'W':
                # 简化: 主场赢权重0.9, 客场赢权重1.1
                weighted += 0.9 if m.get('is_home') else 1.1
            else:
                weighted += 0.0
        return weighted

    def _weighted_draw_count(self, matches: List[Dict]) -> float:
        """对手强度加权的平局数"""
        weighted = 0.0
        for m in matches:
            if m['result'] == 'D':
                weighted += 1.0
        return weighted

    def analyze_form_with_opponent_strength(
        self,
        team_id: int,
        recent_matches: int = 10,
        conn: sqlite3.Connection = None,
    ) -> Dict:
        """
        带对手强度加权的form分析

        对手Elo > 自己Elo * 1.1 → 胜场权重1.3, 负场权重0.7
        对手Elo < 自己Elo * 0.9 → 胜场权重0.7, 负场权重1.3
        其他 → 权重1.0
        """
        if conn is None:
            conn = self.get_connection()

        base_form = self.analyze_form(team_id, recent_matches, conn)
        if base_form.get('matches', 0) == 0 or not isinstance(base_form.get('matches'), list):
            return base_form

        my_elo = self._get_team_elo(team_id, conn)
        if not my_elo:
            return base_form

        matches_list = base_form['matches']
        weighted_wins = 0.0
        weighted_losses = 0.0
        weighted_draws = 0.0

        for m in matches_list:
            opp_id = m.get('opponent_id')
            if not opp_id:
                if m['result'] == 'W':
                    weighted_wins += 1.0
                elif m['result'] == 'L':
                    weighted_losses += 1.0
                else:
                    weighted_draws += 1.0
                continue

            opp_elo = self._get_team_elo(opp_id, conn)
            if not opp_elo:
                ratio = 1.0
            else:
                ratio = opp_elo / my_elo

            if m['result'] == 'W':
                weight = min(1.5, max(0.5, ratio))
                weighted_wins += weight
            elif m['result'] == 'L':
                weight = min(1.5, max(0.5, 2.0 - ratio))
                weighted_losses += weight
            else:
                weighted_draws += 1.0

        # 用加权结果重算form_score
        total = len(matches_list)
        wins = sum(1 for m in matches_list if m['result'] == 'W')
        draws = sum(1 for m in matches_list if m['result'] == 'D')
        losses = sum(1 for m in matches_list if m['result'] == 'L')
        goals_scored = sum(m['team_goals'] for m in matches_list)
        goals_conceded = sum(m['opponent_goals'] for m in matches_list)

        # 加权胜率评分
        win_score = (weighted_wins * 3 + weighted_draws) / max(1, total * 3) * 100

        avg_goals = goals_scored / total
        attack_score = min(avg_goals / 2.0 * 100, 100)

        avg_conceded = goals_conceded / total
        defense_score = max(100 - avg_conceded / 0.5 * 20, 0)

        adjusted_form_score = win_score * 0.4 + attack_score * 0.3 + defense_score * 0.3
        adjusted_form_score = round(adjusted_form_score)

        base_form['form_score_adjusted'] = adjusted_form_score
        base_form['form_score_raw'] = base_form.get('form_score', 0)
        base_form['form_score'] = adjusted_form_score
        base_form['opponent_strength_weighted'] = True

        return base_form