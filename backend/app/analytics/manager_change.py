"""
换帅效应分析模块

分析球队换帅后的表现变化
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class ManagerChangeAnalyzer:
    """换帅效应分析器"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def analyze_team_manager_change(
        self,
        team_id: int,
        change_date: str,
        matches_before: int = 10,
        matches_after: int = 10,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        分析球队换帅前后的表现变化

        Args:
            team_id: 球队 ID
            change_date: 换帅日期 (YYYY-MM-DD)
            matches_before: 换帅前比赛场次数
            matches_after: 换帅后比赛场次数
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取换帅前的比赛
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                m.result,
                ht.name_en as home_team,
                at.name_en as away_team
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.match_date < ?
            AND m.home_goals IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT ?
        """, (team_id, team_id, change_date, matches_before))

        before_matches = [dict(row) for row in cursor.fetchall()]

        # 获取换帅后的比赛
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                m.result,
                ht.name_en as home_team,
                at.name_en as away_team
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.match_date >= ?
            AND m.home_goals IS NOT NULL
            ORDER BY m.match_date ASC
            LIMIT ?
        """, (team_id, team_id, change_date, matches_after))

        after_matches = [dict(row) for row in cursor.fetchall()]

        # 分析换帅前数据
        before_stats = self._analyze_matches(before_matches, team_id)

        # 分析换帅后数据
        after_stats = self._analyze_matches(after_matches, team_id)

        # 计算变化
        improvement = self._calculate_improvement(before_stats, after_stats)

        return {
            'team_id': team_id,
            'change_date': change_date,
            'before': {
                'matches_count': len(before_matches),
                'stats': before_stats,
                'matches': before_matches
            },
            'after': {
                'matches_count': len(after_matches),
                'stats': after_stats,
                'matches': after_matches
            },
            'improvement': improvement,
            'manager_bounce': self._assess_manager_bounce(improvement)
        }

    def get_recent_manager_changes(
        self,
        limit: int = 20,
        conn: Optional[sqlite3.Connection] = None
    ) -> List[Dict]:
        """
        获取最近的换帅记录
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                c.change_id,
                c.team_id,
                c.change_date,
                c.old_coach_name,
                c.new_coach_name,
                c.change_type,
                t.name_en as team_name,
                t.name_cn as team_name_cn
            FROM coach_changes c
            JOIN teams t ON c.team_id = t.team_id
            ORDER BY c.change_date DESC
            LIMIT ?
        """, (limit,))

        changes = [dict(row) for row in cursor.fetchall()]

        # 为每个换帅记录添加效果分析
        for change in changes:
            analysis = self.analyze_team_manager_change(
                change['team_id'],
                change['change_date'],
                matches_before=5,
                matches_after=5,
                conn=conn
            )
            change['effect'] = analysis.get('improvement', {})
            change['manager_bounce'] = analysis.get('manager_bounce')

        return changes

    def analyze_league_manager_changes(
        self,
        league_id: int,
        season_id: int,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        分析联赛内所有换帅效果
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取该联赛该赛季的换帅记录
        cursor.execute("""
            SELECT DISTINCT
                c.team_id,
                c.change_date,
                c.new_coach_name,
                t.name_en as team_name
            FROM coach_changes c
            JOIN teams t ON c.team_id = t.team_id
            JOIN matches m ON c.team_id = m.home_team_id OR c.team_id = m.away_team_id
            WHERE m.league_id = ? AND m.season_id = ?
            ORDER BY c.change_date DESC
        """, (league_id, season_id))

        changes = [dict(row) for row in cursor.fetchall()]

        # 分析每个换帅的效果
        analyses = []
        for change in changes:
            analysis = self.analyze_team_manager_change(
                change['team_id'],
                change['change_date'],
                matches_before=5,
                matches_after=5,
                conn=conn
            )
            analyses.append({
                'team_id': change['team_id'],
                'team_name': change['team_name'],
                'change_date': change['change_date'],
                'new_coach_name': change['new_coach_name'],
                'analysis': analysis
            })

        # 统计整体换帅效果
        total_changes = len(analyses)
        positive_changes = sum(1 for a in analyses if a['analysis'].get('improvement', {}).get('points_per_match_change', 0) > 0)
        negative_changes = sum(1 for a in analyses if a['analysis'].get('improvement', {}).get('points_per_match_change', 0) < 0)

        return {
            'league_id': league_id,
            'season_id': season_id,
            'total_changes': total_changes,
            'positive_changes': positive_changes,
            'negative_changes': negative_changes,
            'neutral_changes': total_changes - positive_changes - negative_changes,
            'success_rate': round(positive_changes / total_changes * 100, 1) if total_changes > 0 else 0,
            'analyses': analyses
        }

    def predict_manager_bounce(
        self,
        team_id: int,
        change_date: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        预测换帅后的"新帅效应"
        基于历史数据分析新帅上任后的常见表现
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取换帅后前 3 场比赛
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                ht.name_en as home_team,
                at.name_en as away_team
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.match_date >= ?
            AND m.home_goals IS NOT NULL
            ORDER BY m.match_date ASC
            LIMIT 3
        """, (team_id, team_id, change_date))

        first_matches = [dict(row) for row in cursor.fetchall()]

        if not first_matches:
            return {
                'team_id': team_id,
                'prediction': '无换帅后比赛数据',
                'confidence': 'low'
            }

        # 分析前 3 场表现
        stats = self._analyze_matches(first_matches, team_id)

        # 判断是否有新帅效应
        if stats['win_rate'] >= 66:
            prediction = 'strong_bounce'
            description = '新帅效应明显，开局强势'
            confidence = 'high'
        elif stats['win_rate'] >= 50 or stats['points_per_match'] >= 2:
            prediction = 'moderate_bounce'
            description = '新帅效应中等，有所提升'
            confidence = 'medium'
        elif stats['points_per_match'] >= 1:
            prediction = 'slight_bounce'
            description = '新帅效应轻微，略有改善'
            confidence = 'low'
        else:
            prediction = 'no_bounce'
            description = '未见新帅效应'
            confidence = 'medium'

        return {
            'team_id': team_id,
            'change_date': change_date,
            'first_3_matches': first_matches,
            'stats': stats,
            'prediction': prediction,
            'description': description,
            'confidence': confidence
        }

    def _analyze_matches(self, matches: List[Dict], team_id: int) -> Dict:
        """分析比赛列表的统计数据"""
        if not matches:
            return {
                'wins': 0,
                'draws': 0,
                'losses': 0,
                'win_rate': 0,
                'points': 0,
                'points_per_match': 0,
                'goals_for': 0,
                'goals_against': 0,
                'goal_diff': 0,
                'goals_per_match': 0,
                'goals_conceded_per_match': 0,
                'clean_sheets': 0,
                'clean_sheet_rate': 0,
                'form': '',
                'form_list': []
            }

        wins = 0
        draws = 0
        losses = 0
        goals_for = 0
        goals_against = 0
        clean_sheets = 0
        form = []

        for match in matches:
            is_home = match['home_team_id'] == team_id

            if is_home:
                team_goals = match['home_goals'] or 0
                opp_goals = match['away_goals'] or 0
            else:
                team_goals = match['away_goals'] or 0
                opp_goals = match['home_goals'] or 0

            goals_for += team_goals
            goals_against += opp_goals

            if team_goals > opp_goals:
                wins += 1
                form.append('W')
            elif team_goals == opp_goals:
                draws += 1
                form.append('D')
            else:
                losses += 1
                form.append('L')

            if team_goals == 0:
                clean_sheets += 1

        total = len(matches)
        points = wins * 3 + draws

        return {
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'win_rate': round(wins / total * 100, 1) if total > 0 else 0,
            'points': points,
            'points_per_match': round(points / total, 2) if total > 0 else 0,
            'goals_for': goals_for,
            'goals_against': goals_against,
            'goal_diff': goals_for - goals_against,
            'goals_per_match': round(goals_for / total, 2) if total > 0 else 0,
            'goals_conceded_per_match': round(goals_against / total, 2) if total > 0 else 0,
            'clean_sheets': clean_sheets,
            'clean_sheet_rate': round(clean_sheets / total * 100, 1) if total > 0 else 0,
            'form': '-'.join(form),
            'form_list': form
        }

    def _calculate_improvement(self, before_stats: Dict, after_stats: Dict) -> Dict:
        """计算换帅前后的变化"""
        points_change = after_stats['points_per_match'] - before_stats['points_per_match']
        win_rate_change = after_stats['win_rate'] - before_stats['win_rate']
        goals_change = after_stats['goals_per_match'] - before_stats['goals_per_match']
        conceded_change = before_stats['goals_conceded_per_match'] - after_stats['goals_conceded_per_match']

        # 综合评分 (0-100)
        improvement_score = (
            points_change * 30 +      # 积分权重最高
            win_rate_change * 0.5 +   # 胜率
            goals_change * 10 +       # 进攻
            conceded_change * 10      # 防守
        )

        return {
            'points_per_match_change': round(points_change, 2),
            'win_rate_change': round(win_rate_change, 1),
            'goals_per_match_change': round(goals_change, 2),
            'goals_conceded_change': round(conceded_change, 2),
            'improvement_score': round(improvement_score, 1),
            'trend': self._get_trend(improvement_score)
        }

    def _get_trend(self, improvement_score: float) -> str:
        """获取趋势判断"""
        if improvement_score >= 15:
            return 'significant_improvement'    # 显著提升
        elif improvement_score >= 5:
            return 'moderate_improvement'       # 中等提升
        elif improvement_score >= -5:
            return 'stable'                     # 基本稳定
        elif improvement_score >= -15:
            return 'moderate_decline'           # 中等下滑
        else:
            return 'significant_decline'        # 显著下滑

    def _assess_manager_bounce(self, improvement: Dict) -> Dict:
        """评估新帅效应"""
        points_change = improvement.get('points_per_match_change', 0)
        trend = improvement.get('trend', 'stable')

        if points_change >= 1.0 or trend == 'significant_improvement':
            return {
                'has_bounce': True,
                'strength': 'strong',
                'description': '明显的新帅效应'
            }
        elif points_change >= 0.5 or trend == 'moderate_improvement':
            return {
                'has_bounce': True,
                'strength': 'moderate',
                'description': '中等新帅效应'
            }
        elif points_change > 0:
            return {
                'has_bounce': True,
                'strength': 'slight',
                'description': '轻微新帅效应'
            }
        else:
            return {
                'has_bounce': False,
                'strength': 'none',
                'description': '未见新帅效应'
            }
