"""
进攻/防守效率分析模块

分析球队进攻效率 (射门转化率)、防守效率、控球效率等
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class EfficiencyAnalyzer:
    """效率分析器"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def analyze_attacking_efficiency(
        self,
        team_id: int,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        limit: int = 20,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        分析球队进攻效率

        指标包括：
        - 射门转化率 (进球/射门)
        - 射正率 (射正/射门)
        - 进球效率 (进球/绝对机会)
        - 进攻三区传球
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        conditions = ["(m.home_team_id = ? OR m.away_team_id = ?)"]
        params = [team_id, team_id]

        if league_id:
            conditions.append("m.league_id = ?")
            params.append(league_id)

        if season_id:
            conditions.append("m.season_id = ?")
            params.append(season_id)

        conditions.append("m.home_goals IS NOT NULL")

        query = f"""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                m.home_shots,
                m.away_shots,
                m.home_shots_target,
                m.away_shots_target,
                m.home_possession,
                m.away_possession,
                m.home_corners,
                m.away_corners,
                ht.name_en as home_team,
                at.name_en as away_team
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE {' AND '.join(conditions)}
            ORDER BY m.match_date DESC
            LIMIT ?
        """
        params.append(limit)

        cursor.execute(query, params)
        matches = cursor.fetchall()

        if not matches:
            return {
                'team_id': team_id,
                'attacking_summary': None,
                'matches': [],
                'message': '无比赛数据'
            }

        # 累积统计
        total_stats = {
            'goals': 0,
            'shots': 0,
            'shots_target': 0,
            'possession': 0,
            'corners': 0,
            'matches': 0
        }

        match_details = []

        for match in matches:
            is_home = match['home_team_id'] == team_id

            if is_home:
                goals = match['home_goals'] or 0
                shots = match['home_shots'] or 0
                shots_target = match['home_shots_target'] or 0
                possession = match['home_possession'] or 0
                corners = match['home_corners'] or 0
            else:
                goals = match['away_goals'] or 0
                shots = match['away_shots'] or 0
                shots_target = match['away_shots_target'] or 0
                possession = match['away_possession'] or 0
                corners = match['away_corners'] or 0

            total_stats['goals'] += goals
            total_stats['shots'] += shots
            total_stats['shots_target'] += shots_target
            total_stats['possession'] += possession
            total_stats['corners'] += corners
            total_stats['matches'] += 1

            # 计算本场效率
            shot_conversion = (goals / shots * 100) if shots > 0 else 0
            shot_accuracy = (shots_target / shots * 100) if shots > 0 else 0

            match_details.append({
                'match_id': match['match_id'],
                'date': match['match_date'],
                'venue': 'H' if is_home else 'A',
                'opponent': match['away_team'] if is_home else match['home_team'],
                'goals': goals,
                'shots': shots,
                'shots_target': shots_target,
                'possession': possession,
                'corners': corners,
                'shot_conversion': round(shot_conversion, 1),
                'shot_accuracy': round(shot_accuracy, 1),
                'result': 'W' if (is_home and goals > (match['away_goals'] or 0)) or
                                   (not is_home and goals > (match['home_goals'] or 0)) else 'L'
            })

        # 计算平均效率
        avg_stats = {
            'goals_per_match': round(total_stats['goals'] / total_stats['matches'], 2) if total_stats['matches'] > 0 else 0,
            'shots_per_match': round(total_stats['shots'] / total_stats['matches'], 2) if total_stats['matches'] > 0 else 0,
            'shots_target_per_match': round(total_stats['shots_target'] / total_stats['matches'], 2) if total_stats['matches'] > 0 else 0,
            'avg_possession': round(total_stats['possession'] / total_stats['matches'], 1) if total_stats['matches'] > 0 else 0,
            'corners_per_match': round(total_stats['corners'] / total_stats['matches'], 2) if total_stats['matches'] > 0 else 0,
            'shot_conversion_rate': round(total_stats['goals'] / total_stats['shots'] * 100, 1) if total_stats['shots'] > 0 else 0,
            'shot_accuracy': round(total_stats['shots_target'] / total_stats['shots'] * 100, 1) if total_stats['shots'] > 0 else 0,
            'goals_per_shot_target': round(total_stats['goals'] / total_stats['shots_target'], 2) if total_stats['shots_target'] > 0 else 0
        }

        # 联赛排名比较
        league_rank = self._get_attacking_rank_in_league(
            team_id, league_id, season_id, avg_stats, conn
        ) if league_id and season_id else None

        return {
            'team_id': team_id,
            'attacking_summary': {
                'matches_analyzed': total_stats['matches'],
                'avg_stats': avg_stats,
                'league_rank': league_rank,
                'efficiency_rating': self._rate_attacking_efficiency(avg_stats['shot_conversion_rate'])
            },
            'recent_matches': match_details[:10]
        }

    def analyze_defensive_efficiency(
        self,
        team_id: int,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        limit: int = 20,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        分析球队防守效率

        指标包括：
        - 零封率
        - 场均失球
        - 扑救率 (基于对手射正)
        - 防守稳定性
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        conditions = ["(m.home_team_id = ? OR m.away_team_id = ?)"]
        params = [team_id, team_id]

        if league_id:
            conditions.append("m.league_id = ?")
            params.append(league_id)

        if season_id:
            conditions.append("m.season_id = ?")
            params.append(season_id)

        conditions.append("m.home_goals IS NOT NULL")

        query = f"""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                m.home_shots,
                m.away_shots,
                m.home_shots_target,
                m.away_shots_target,
                ht.name_en as home_team,
                at.name_en as away_team
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE {' AND '.join(conditions)}
            ORDER BY m.match_date DESC
            LIMIT ?
        """
        params.append(limit)

        cursor.execute(query, params)
        matches = cursor.fetchall()

        if not matches:
            return {
                'team_id': team_id,
                'defensive_summary': None,
                'matches': [],
                'message': '无比赛数据'
            }

        # 累积统计
        total_stats = {
            'goals_conceded': 0,
            'clean_sheets': 0,
            'opponent_shots': 0,
            'opponent_shots_target': 0,
            'matches': 0
        }

        match_details = []

        for match in matches:
            is_home = match['home_team_id'] == team_id

            if is_home:
                goals_conceded = match['away_goals'] or 0
                opponent_shots = match['away_shots'] or 0
                opponent_shots_target = match['away_shots_target'] or 0
            else:
                goals_conceded = match['home_goals'] or 0
                opponent_shots = match['home_shots'] or 0
                opponent_shots_target = match['home_shots_target'] or 0

            total_stats['goals_conceded'] += goals_conceded
            total_stats['opponent_shots'] += opponent_shots
            total_stats['opponent_shots_target'] += opponent_shots_target
            total_stats['matches'] += 1

            if goals_conceded == 0:
                total_stats['clean_sheets'] += 1

            # 计算防守效率
            save_rate = ((opponent_shots_target - goals_conceded) / opponent_shots_target * 100) if opponent_shots_target > 0 else 0

            match_details.append({
                'match_id': match['match_id'],
                'date': match['match_date'],
                'venue': 'H' if is_home else 'A',
                'opponent': match['away_team'] if is_home else match['home_team'],
                'goals_conceded': goals_conceded,
                'opponent_shots': opponent_shots,
                'opponent_shots_target': opponent_shots_target,
                'save_rate': round(save_rate, 1) if opponent_shots_target > 0 else None,
                'clean_sheet': goals_conceded == 0
            })

        # 计算平均效率
        avg_stats = {
            'goals_conceded_per_match': round(total_stats['goals_conceded'] / total_stats['matches'], 2) if total_stats['matches'] > 0 else 0,
            'clean_sheet_rate': round(total_stats['clean_sheets'] / total_stats['matches'] * 100, 1) if total_stats['matches'] > 0 else 0,
            'opponent_shots_per_match': round(total_stats['opponent_shots'] / total_stats['matches'], 2) if total_stats['matches'] > 0 else 0,
            'opponent_shots_target_per_match': round(total_stats['opponent_shots_target'] / total_stats['matches'], 2) if total_stats['matches'] > 0 else 0,
            'avg_save_rate': round(
                (total_stats['opponent_shots_target'] - total_stats['goals_conceded']) /
                total_stats['opponent_shots_target'] * 100, 1
            ) if total_stats['opponent_shots_target'] > 0 else 0
        }

        # 联赛排名比较
        league_rank = self._get_defensive_rank_in_league(
            team_id, league_id, season_id, avg_stats, conn
        ) if league_id and season_id else None

        return {
            'team_id': team_id,
            'defensive_summary': {
                'matches_analyzed': total_stats['matches'],
                'avg_stats': avg_stats,
                'league_rank': league_rank,
                'efficiency_rating': self._rate_defensive_efficiency(
                    avg_stats['goals_conceded_per_match'],
                    avg_stats['clean_sheet_rate']
                )
            },
            'recent_matches': match_details[:10]
        }

    def analyze_possession_efficiency(
        self,
        team_id: int,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        limit: int = 20,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        分析控球效率

        指标包括：
        - 控球率 vs 进球相关性
        - 有效控球 (进攻三区)
        - 无效控球识别
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        conditions = ["(m.home_team_id = ? OR m.away_team_id = ?)"]
        params = [team_id, team_id]

        if league_id:
            conditions.append("m.league_id = ?")
            params.append(league_id)

        if season_id:
            conditions.append("m.season_id = ?")
            params.append(season_id)

        conditions.append("m.home_goals IS NOT NULL")
        conditions.append("m.home_possession IS NOT NULL")

        query = f"""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.home_goals,
                m.away_goals,
                m.home_possession,
                m.away_possession,
                m.home_shots,
                m.away_shots,
                ht.name_en as home_team,
                at.name_en as away_team
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE {' AND '.join(conditions)}
            ORDER BY m.match_date DESC
            LIMIT ?
        """
        params.append(limit)

        cursor.execute(query, params)
        matches = cursor.fetchall()

        if not matches:
            return {
                'team_id': team_id,
                'possession_summary': None,
                'matches': [],
                'message': '无控球数据'
            }

        total_possession = 0
        total_goals = 0
        total_shots = 0
        matches_count = 0

        match_details = []

        for match in matches:
            is_home = match['home_team_id'] == team_id

            if is_home:
                possession = match['home_possession'] or 0
                goals = match['home_goals'] or 0
                shots = match['home_shots'] or 0
            else:
                possession = match['away_possession'] or 0
                goals = match['away_goals'] or 0
                shots = match['away_shots'] or 0

            total_possession += possession
            total_goals += goals
            total_shots += shots
            matches_count += 1

            # 控球效率 = 进球/控球率
            possession_efficiency = (goals / possession * 100) if possession > 0 else 0
            # 射门转化率
            shot_conversion = (goals / shots * 100) if shots > 0 else 0

            match_details.append({
                'match_id': match['match_id'],
                'date': match['match_date'],
                'venue': 'H' if is_home else 'A',
                'opponent': match['away_team'] if is_home else match['home_team'],
                'possession': possession,
                'goals': goals,
                'shots': shots,
                'possession_efficiency': round(possession_efficiency, 2),
                'shot_conversion': round(shot_conversion, 1),
                'result': 'W' if (is_home and goals > (match['away_goals'] or 0)) or
                                   (not is_home and goals > (match['home_goals'] or 0)) else
                            ('D' if (match['away_goals'] or 0) == goals else 'L')
            })

        avg_possession = total_possession / matches_count if matches_count > 0 else 0
        avg_goals = total_goals / matches_count if matches_count > 0 else 0
        avg_possession_efficiency = (avg_goals / avg_possession * 100) if avg_possession > 0 else 0

        # 分析控球风格
        style = self._analyze_possession_style(avg_possession, avg_possession_efficiency)

        return {
            'team_id': team_id,
            'possession_summary': {
                'matches_analyzed': matches_count,
                'avg_possession': round(avg_possession, 1),
                'avg_goals': round(avg_goals, 2),
                'possession_efficiency': round(avg_possession_efficiency, 3),
                'style': style,
                'style_description': self._get_style_description(style)
            },
            'recent_matches': match_details[:10]
        }

    def compare_efficiency(
        self,
        home_team_id: int,
        away_team_id: int,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        比较两队效率
        """
        home_attacking = self.analyze_attacking_efficiency(home_team_id, league_id, season_id, conn=conn)
        home_defensive = self.analyze_defensive_efficiency(home_team_id, league_id, season_id, conn=conn)
        away_attacking = self.analyze_attacking_efficiency(away_team_id, league_id, season_id, conn=conn)
        away_defensive = self.analyze_defensive_efficiency(away_team_id, league_id, season_id, conn=conn)

        return {
            'home_team': {
                'team_id': home_team_id,
                'attacking': home_attacking.get('attacking_summary'),
                'defensive': home_defensive.get('defensive_summary')
            },
            'away_team': {
                'team_id': away_team_id,
                'attacking': away_attacking.get('attacking_summary'),
                'defensive': away_defensive.get('defensive_summary')
            },
            'comparison': {
                'attacking_edge': self._compare_attacking(
                    home_attacking.get('attacking_summary'),
                    away_attacking.get('attacking_summary')
                ),
                'defensive_edge': self._compare_defensive(
                    home_defensive.get('defensive_summary'),
                    away_defensive.get('defensive_summary')
                )
            }
        }

    def _get_attacking_rank_in_league(
        self,
        team_id: int,
        league_id: int,
        season_id: int,
        team_stats: Dict,
        conn: sqlite3.Connection
    ) -> Optional[Dict]:
        """获取球队在联赛中的进攻排名"""
        cursor = conn.cursor()

        # 简化版：获取联赛平均射门转化率
        cursor.execute("""
            SELECT
                AVG(
                    CASE WHEN (m.home_shots + m.away_shots) > 0
                    THEN (m.home_goals + m.away_goals) * 1.0 / (m.home_shots + m.away_shots)
                    ELSE 0 END
                ) as league_avg_conversion
            FROM matches m
            WHERE m.league_id = ? AND m.season_id = ?
            AND m.home_goals IS NOT NULL
            AND m.home_shots IS NOT NULL
        """, (league_id, season_id))

        result = cursor.fetchone()
        if result and result['league_avg_conversion']:
            league_avg = result['league_avg_conversion'] * 100
            return {
                'league_avg_conversion': round(league_avg, 1),
                'team_conversion': team_stats.get('shot_conversion_rate', 0),
                'vs_average': round(team_stats.get('shot_conversion_rate', 0) - league_avg, 1)
            }
        return None

    def _get_defensive_rank_in_league(
        self,
        team_id: int,
        league_id: int,
        season_id: int,
        team_stats: Dict,
        conn: sqlite3.Connection
    ) -> Optional[Dict]:
        """获取球队在联赛中的防守排名"""
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                AVG(m.home_goals + m.away_goals) * 1.0 / 2 as league_avg_goals
            FROM matches m
            WHERE m.league_id = ? AND m.season_id = ?
            AND m.home_goals IS NOT NULL
        """, (league_id, season_id))

        result = cursor.fetchone()
        if result and result['league_avg_goals']:
            league_avg = result['league_avg_goals']
            return {
                'league_avg_goals': round(league_avg, 2),
                'team_conceded': team_stats.get('goals_conceded_per_match', 0),
                'vs_average': round(team_stats.get('goals_conceded_per_match', 0) - league_avg, 2)
            }
        return None

    def _rate_attacking_efficiency(self, conversion_rate: float) -> str:
        """评级进攻效率"""
        if conversion_rate >= 15:
            return 'elite'       # 顶级
        elif conversion_rate >= 12:
            return 'excellent'   # 优秀
        elif conversion_rate >= 9:
            return 'good'        # 良好
        elif conversion_rate >= 6:
            return 'average'     # 一般
        else:
            return 'poor'        # 较差

    def _rate_defensive_efficiency(
        self,
        goals_conceded: float,
        clean_sheet_rate: float
    ) -> str:
        """评级防守效率"""
        if goals_conceded <= 0.5 and clean_sheet_rate >= 50:
            return 'elite'
        elif goals_conceded <= 0.8 and clean_sheet_rate >= 40:
            return 'excellent'
        elif goals_conceded <= 1.2 and clean_sheet_rate >= 25:
            return 'good'
        elif goals_conceded <= 1.5:
            return 'average'
        else:
            return 'poor'

    def _analyze_possession_style(
        self,
        avg_possession: float,
        possession_efficiency: float
    ) -> str:
        """分析控球风格"""
        if avg_possession >= 60:
            if possession_efficiency >= 0.15:
                return 'dominant_efficient'    # 高效控球
            else:
                return 'dominant_inefficient'  # 无效控球
        elif avg_possession >= 45:
            if possession_efficiency >= 0.15:
                return 'balanced_efficient'    # 平衡高效
            else:
                return 'balanced'              # 平衡型
        else:
            if possession_efficiency >= 0.2:
                return 'counter_efficient'     # 高效反击
            else:
                return 'counter'               # 防守反击

    def _get_style_description(self, style: str) -> str:
        """获取风格描述"""
        descriptions = {
            'dominant_efficient': '控球主导型，进攻效率高',
            'dominant_inefficient': '控球主导型，但进攻效率待提高',
            'balanced_efficient': '平衡型打法，效率出色',
            'balanced': '平衡型打法',
            'counter_efficient': '防守反击，效率极高',
            'counter': '防守反击型'
        }
        return descriptions.get(style, '未知风格')

    def _compare_attacking(self, home_stats: Optional[Dict], away_stats: Optional[Dict]) -> Dict:
        """比较进攻能力"""
        if not home_stats or not away_stats:
            return {'edge': 'unknown'}

        home_conversion = home_stats.get('avg_stats', {}).get('shot_conversion_rate', 0)
        away_conversion = away_stats.get('avg_stats', {}).get('shot_conversion_rate', 0)

        if home_conversion > away_conversion + 2:
            return {'edge': 'home', 'reason': f'射门转化率高 {home_conversion - away_conversion:.1f}%'}
        elif away_conversion > home_conversion + 2:
            return {'edge': 'away', 'reason': f'射门转化率高 {away_conversion - home_conversion:.1f}%'}
        else:
            return {'edge': 'even', 'reason': '进攻效率接近'}

    def _compare_defensive(self, home_stats: Optional[Dict], away_stats: Optional[Dict]) -> Dict:
        """比较防守能力"""
        if not home_stats or not away_stats:
            return {'edge': 'unknown'}

        home_conceded = home_stats.get('avg_stats', {}).get('goals_conceded_per_match', 0)
        away_conceded = away_stats.get('avg_stats', {}).get('goals_conceded_per_match', 0)

        if home_conceded < away_conceded - 0.2:
            return {'edge': 'home', 'reason': f'场均失球少 {away_conceded - home_conceded:.2f}'}
        elif away_conceded < home_conceded - 0.2:
            return {'edge': 'away', 'reason': f'场均失球少 {home_conceded - away_conceded:.2f}'}
        else:
            return {'edge': 'even', 'reason': '防守水平接近'}
