"""
xG (Expected Goals) 预期进球分析模块

xG是衡量射门质量的指标，考虑射门位置、角度、防守压力等因素
本模块提供多种xG计算方法，从简单到复杂
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import math


class XGAnalyzer:
    """xG预期进球分析器"""

    # 联赛平均转化率（射正→进球）
    LEAGUE_CONVERSION_RATE = 0.30

    # 射门位置xG基准值（简化模型）
    # 实际xG需要更复杂的模型或从数据源获取
    SHOT_POSITION_XG = {
        'penalty': 0.76,        # 点球
        'close_range': 0.40,    # 近距离
        'inside_box': 0.15,     # 禁区内
        'outside_box': 0.05,    # 禁区外
        'header': 0.10,         # 头球
        'free_kick': 0.08,      # 任意球
    }

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_team_attack_stats(
        self,
        team_id: int,
        is_home: bool = True,
        recent_matches: int = 10,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        获取球队进攻统计数据

        Args:
            team_id: 球队ID
            is_home: 是否主场
            recent_matches: 最近N场比赛
            conn: 数据库连接
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        if is_home:
            cursor.execute("""
                SELECT
                    AVG(home_goals) as avg_goals,
                    AVG(home_shots) as avg_shots,
                    AVG(home_shots_target) as avg_shots_on_target,
                    AVG(home_corners) as avg_corners,
                    COUNT(*) as matches
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
                    AVG(away_goals) as avg_goals,
                    AVG(away_shots) as avg_shots,
                    AVG(away_shots_target) as avg_shots_on_target,
                    AVG(away_corners) as avg_corners,
                    COUNT(*) as matches
                FROM matches
                WHERE away_team_id = ?
                AND status = 'finished'
                AND away_goals IS NOT NULL
                ORDER BY match_date DESC
                LIMIT ?
            """, (team_id, recent_matches))

        result = cursor.fetchone()
        if result and result['matches'] > 0:
            return {
                'avg_goals': result['avg_goals'] or 0,
                'avg_shots': result['avg_shots'] or 0,
                'avg_shots_on_target': result['avg_shots_on_target'] or 0,
                'avg_corners': result['avg_corners'] or 0,
                'matches': result['matches']
            }
        return {
            'avg_goals': 0,
            'avg_shots': 0,
            'avg_shots_on_target': 0,
            'avg_corners': 0,
            'matches': 0
        }

    def get_team_defense_stats(
        self,
        team_id: int,
        is_home: bool = True,
        recent_matches: int = 10,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        获取球队防守统计数据（失球、被射门等）
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        if is_home:
            # 主场时，看对手（客队）的进攻数据 = 本队防守数据
            cursor.execute("""
                SELECT
                    AVG(away_goals) as avg_conceded,
                    AVG(away_shots) as avg_shots_conceded,
                    AVG(away_shots_target) as avg_shots_on_target_conceded,
                    COUNT(*) as matches
                FROM matches
                WHERE home_team_id = ?
                AND status = 'finished'
                ORDER BY match_date DESC
                LIMIT ?
            """, (team_id, recent_matches))
        else:
            cursor.execute("""
                SELECT
                    AVG(home_goals) as avg_conceded,
                    AVG(home_shots) as avg_shots_conceded,
                    AVG(home_shots_target) as avg_shots_on_target_conceded,
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
                'avg_conceded': result['avg_conceded'] or 0,
                'avg_shots_conceded': result['avg_shots_conceded'] or 0,
                'avg_shots_on_target_conceded': result['avg_shots_on_target_conceded'] or 0,
                'matches': result['matches']
            }
        return {
            'avg_conceded': 0,
            'avg_shots_conceded': 0,
            'avg_shots_on_target_conceded': 0,
            'matches': 0
        }

    def calculate_simple_xg(
        self,
        home_team_id: int,
        away_team_id: int,
        recent_matches: int = 10,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        简单xG计算方法

        基于最近比赛的：
        - 进球平均
        - 射正平均 × 转化率
        - 对手防守强度调整
        """
        if conn is None:
            conn = self.get_connection()

        # 主队主场进攻
        home_attack = self.get_team_attack_stats(home_team_id, is_home=True, recent_matches=recent_matches, conn=conn)
        # 主队主场防守
        home_defense = self.get_team_defense_stats(home_team_id, is_home=True, recent_matches=recent_matches, conn=conn)

        # 客队客场进攻
        away_attack = self.get_team_attack_stats(away_team_id, is_home=False, recent_matches=recent_matches, conn=conn)
        # 客队客场防守
        away_defense = self.get_team_defense_stats(away_team_id, is_home=False, recent_matches=recent_matches, conn=conn)

        # 计算xG
        # 方法1：基于进球平均
        home_xg_by_goals = home_attack['avg_goals']
        away_xg_by_goals = away_attack['avg_goals']

        # 方法2：基于射正 × 转化率
        home_xg_by_shots = home_attack['avg_shots_on_target'] * self.LEAGUE_CONVERSION_RATE
        away_xg_by_shots = away_attack['avg_shots_on_target'] * self.LEAGUE_CONVERSION_RATE

        # 方法3：进攻 vs 防守调整
        # 主队xG = 主队进攻 × 客队防守系数
        if away_defense['avg_conceded'] > 0:
            league_avg_conceded = 1.3  # 联赛平均失球
            away_defense_factor = away_defense['avg_conceded'] / league_avg_conceded
        else:
            away_defense_factor = 1.0

        if home_defense['avg_conceded'] > 0:
            league_avg_conceded = 1.1
            home_defense_factor = home_defense['avg_conceded'] / league_avg_conceded
        else:
            home_defense_factor = 1.0

        home_xg_adjusted = home_xg_by_goals * away_defense_factor
        away_xg_adjusted = away_xg_by_goals * home_defense_factor

        # 综合xG（加权平均）
        home_xg = (home_xg_by_goals * 0.4 + home_xg_by_shots * 0.3 + home_xg_adjusted * 0.3)
        away_xg = (away_xg_by_goals * 0.4 + away_xg_by_shots * 0.3 + away_xg_adjusted * 0.3)

        return {
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_xg': round(home_xg, 2),
            'away_xg': round(away_xg, 2),
            'details': {
                'home_attack': {
                    'avg_goals': round(home_attack['avg_goals'], 2),
                    'avg_shots_on_target': round(home_attack['avg_shots_on_target'], 2),
                    'matches': home_attack['matches']
                },
                'away_attack': {
                    'avg_goals': round(away_attack['avg_goals'], 2),
                    'avg_shots_on_target': round(away_attack['avg_shots_on_target'], 2),
                    'matches': away_attack['matches']
                },
                'home_defense': {
                    'avg_conceded': round(home_defense['avg_conceded'], 2),
                    'matches': home_defense['matches']
                },
                'away_defense': {
                    'avg_conceded': round(away_defense['avg_conceded'], 2),
                    'matches': away_defense['matches']
                }
            },
            'calculation_methods': {
                'by_goals': {
                    'home': round(home_xg_by_goals, 2),
                    'away': round(away_xg_by_goals, 2)
                },
                'by_shots': {
                    'home': round(home_xg_by_shots, 2),
                    'away': round(away_xg_by_shots, 2)
                },
                'adjusted': {
                    'home': round(home_xg_adjusted, 2),
                    'away': round(away_xg_adjusted, 2),
                    'away_defense_factor': round(away_defense_factor, 2),
                    'home_defense_factor': round(home_defense_factor, 2)
                }
            },
            'confidence': self._calculate_confidence(home_attack['matches'], away_attack['matches'])
        }

    def _calculate_confidence(self, home_matches: int, away_matches: int) -> str:
        """计算xG预测的置信度"""
        min_matches = min(home_matches, away_matches)
        if min_matches >= 10:
            return 'high'
        elif min_matches >= 5:
            return 'medium'
        else:
            return 'low'

    def get_statsbomb_xg(
        self,
        match_id: int,
        conn: sqlite3.Connection = None
    ) -> Optional[Dict]:
        """
        从StatsBomb射门数据计算真实xG

        如果有StatsBomb数据，使用更精确的xG模型
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 检查是否有StatsBomb射门数据
        cursor.execute("""
            SELECT
                team_id,
                shot_statsbomb_xg,
                shot_outcome
            FROM statsbomb_shots
            WHERE match_id = ?
        """, (match_id,))

        shots = cursor.fetchall()
        if not shots:
            return None

        home_xg = 0.0
        away_xg = 0.0

        # 需要知道哪个是主队
        cursor.execute("""
            SELECT home_team_id, away_team_id
            FROM matches
            WHERE match_id = ?
        """, (match_id,))
        match_info = cursor.fetchone()
        if not match_info:
            return None

        home_team_id = match_info['home_team_id']
        away_team_id = match_info['away_team_id']

        for shot in shots:
            if shot['shot_statsbomb_xg'] is not None:
                if shot['team_id'] == home_team_id:
                    home_xg += shot['shot_statsbomb_xg']
                elif shot['team_id'] == away_team_id:
                    away_xg += shot['shot_statsbomb_xg']

        return {
            'match_id': match_id,
            'home_xg': round(home_xg, 2),
            'away_xg': round(away_xg, 2),
            'source': 'statsbomb',
            'shots_count': len(shots)
        }

    def analyze_team_xg_performance(
        self,
        team_id: int,
        recent_matches: int = 20,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析球队xG表现

        对比实际进球 vs 预期进球，评估：
        - 是否超常发挥（实际 > xG）
        - 是否运气不佳（实际 < xG）
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取最近比赛的进球和射门数据
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                m.home_shots_target,
                m.away_shots_target,
                CASE WHEN m.home_team_id = ? THEN 'home' ELSE 'away' END as position
            FROM matches m
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.status = 'finished'
            AND m.home_goals IS NOT NULL
            AND m.away_goals IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT ?
        """, (team_id, team_id, team_id, recent_matches))

        matches = cursor.fetchall()
        if not matches:
            return {
                'team_id': team_id,
                'matches': 0,
                'message': '没有足够的比赛数据'
            }

        total_goals = 0
        total_xg = 0.0
        overperformance = 0
        underperformance = 0

        match_details = []

        for match in matches:
            if match['position'] == 'home':
                goals = match['home_goals']
                shots_on_target = match['home_shots_target'] or 0
            else:
                goals = match['away_goals']
                shots_on_target = match['away_shots_target'] or 0

            # 简单xG估算
            xg = shots_on_target * self.LEAGUE_CONVERSION_RATE

            total_goals += goals
            total_xg += xg

            diff = goals - xg
            if diff > 0.5:
                overperformance += 1
            elif diff < -0.5:
                underperformance += 1

            match_details.append({
                'match_id': match['match_id'],
                'date': match['match_date'],
                'position': match['position'],
                'goals': goals,
                'xg': round(xg, 2),
                'difference': round(diff, 2)
            })

        performance_ratio = total_goals / total_xg if total_xg > 0 else 1.0

        return {
            'team_id': team_id,
            'matches': len(matches),
            'total_goals': total_goals,
            'total_xg': round(total_xg, 2),
            'difference': round(total_goals - total_xg, 2),
            'performance_ratio': round(performance_ratio, 2),
            'overperformance_count': overperformance,
            'underperformance_count': underperformance,
            'assessment': self._assess_performance(performance_ratio),
            'match_details': match_details
        }

    def _assess_performance(self, ratio: float) -> str:
        """评估表现"""
        if ratio >= 1.2:
            return '超常发挥 - 实际进球显著高于预期'
        elif ratio >= 1.05:
            return '略高于预期 - 把握机会能力较强'
        elif ratio >= 0.95:
            return '正常发挥 - 符合预期水平'
        elif ratio >= 0.8:
            return '略低于预期 - 把握机会能力有待提高'
        else:
            return '运气不佳 - 实际进球显著低于预期'

    def compare_xg_sources(
        self,
        match_id: int,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        比较不同来源的xG数据
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取比赛基本信息
        cursor.execute("""
            SELECT
                match_id,
                home_team_id,
                away_team_id,
                home_goals,
                away_goals,
                home_shots_target,
                away_shots_target
            FROM matches
            WHERE match_id = ?
        """, (match_id,))
        match = cursor.fetchone()
        if not match:
            return {'error': '比赛不存在'}

        # 简单xG
        simple_home_xg = (match['home_shots_target'] or 0) * self.LEAGUE_CONVERSION_RATE
        simple_away_xg = (match['away_shots_target'] or 0) * self.LEAGUE_CONVERSION_RATE

        # StatsBomb xG
        statsbomb_xg = self.get_statsbomb_xg(match_id, conn)

        return {
            'match_id': match_id,
            'actual_score': {
                'home': match['home_goals'],
                'away': match['away_goals']
            },
            'simple_xg': {
                'home': round(simple_home_xg, 2),
                'away': round(simple_away_xg, 2),
                'source': 'shots_on_target × conversion_rate'
            },
            'statsbomb_xg': statsbomb_xg,
            'comparison': {
                'home_diff': round(match['home_goals'] - simple_home_xg, 2),
                'away_diff': round(match['away_goals'] - simple_away_xg, 2)
            }
        }