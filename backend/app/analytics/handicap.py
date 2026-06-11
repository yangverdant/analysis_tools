"""
盘路分析模块

分析球队赢盘率 (ATS)、大小球趋势等博彩相关数据
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class HandicapAnalyzer:
    """盘路分析器"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def analyze_team_ats(
        self,
        team_id: int,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        limit: int = 20,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        分析球队赢盘率 (ATS - Against The Spread)

        基于亚洲盘口分析球队赢盘表现
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 构建查询条件
        conditions = ["(m.home_team_id = ? OR m.away_team_id = ?)"]
        params = [team_id, team_id]

        if league_id:
            conditions.append("m.league_id = ?")
            params.append(league_id)

        if season_id:
            conditions.append("m.season_id = ?")
            params.append(season_id)

        conditions.append("m.home_goals IS NOT NULL")
        conditions.append("o.asian_handicap IS NOT NULL")

        query = f"""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                o.line as asian_handicap,
                o.home as b365_ah_home,
                o.away as b365_ah_away,
                ht.name_en as home_team,
                at.name_en as away_team
            FROM matches m
            JOIN match_odds_normalized o ON m.match_id = o.match_id
                AND o.market = 'ASIAN_HANDICAP' AND o.bookmaker = 'BET365' AND o.snapshot_type = 'prematch'
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
                'ats_summary': None,
                'matches': [],
                'message': '无盘口数据'
            }

        # 计算 ATS 统计
        ats_stats = {
            'total': 0,
            'wins': 0,      # 赢盘
            'losses': 0,    # 输盘
            'pushes': 0,    # 走水
            'home': {'total': 0, 'wins': 0, 'losses': 0, 'pushes': 0},
            'away': {'total': 0, 'wins': 0, 'losses': 0, 'pushes': 0},
            'by_handicap_type': {}
        }

        match_results = []

        for match in matches:
            match_dict = dict(match)
            is_home = match['home_team_id'] == team_id

            # 计算让球后的结果
            handicap = match['asian_handicap']
            if is_home:
                team_goals = match['home_goals']
                opp_goals = match['away_goals']
            else:
                team_goals = match['away_goals']
                opp_goals = match['home_goals']
                handicap = -handicap  # 客队让球取反

            # 让球后净胜球
            adjusted_diff = (team_goals - opp_goals) - handicap

            if adjusted_diff > 0:
                result = 'W'  # 赢盘
                ats_stats['wins'] += 1
                if is_home:
                    ats_stats['home']['wins'] += 1
                else:
                    ats_stats['away']['wins'] += 1
            elif adjusted_diff < 0:
                result = 'L'  # 输盘
                ats_stats['losses'] += 1
                if is_home:
                    ats_stats['home']['losses'] += 1
                else:
                    ats_stats['away']['losses'] += 1
            else:
                result = 'P'  # 走水
                ats_stats['pushes'] += 1
                if is_home:
                    ats_stats['home']['pushes'] += 1
                else:
                    ats_stats['away']['pushes'] += 1

            ats_stats['total'] += 1
            if is_home:
                ats_stats['home']['total'] += 1
            else:
                ats_stats['away']['total'] += 1

            # 按让球类型分类
            handicap_type = self._categorize_handicap(handicap)
            if handicap_type not in ats_stats['by_handicap_type']:
                ats_stats['by_handicap_type'][handicap_type] = {'total': 0, 'wins': 0, 'losses': 0, 'pushes': 0}

            ats_stats['by_handicap_type'][handicap_type]['total'] += 1
            if result == 'W':
                ats_stats['by_handicap_type'][handicap_type]['wins'] += 1
            elif result == 'L':
                ats_stats['by_handicap_type'][handicap_type]['losses'] += 1
            else:
                ats_stats['by_handicap_type'][handicap_type]['pushes'] += 1

            match_results.append({
                'match_id': match['match_id'],
                'date': match['match_date'],
                'venue': 'H' if is_home else 'A',
                'opponent': match['away_team'] if is_home else match['home_team'],
                'handicap': handicap,
                'team_goals': team_goals,
                'opp_goals': opp_goals,
                'result': result,
                'actual_score': f"{team_goals}-{opp_goals}"
            })

        # 计算赢盘率
        ats_rate = ats_stats['wins'] / ats_stats['total'] * 100 if ats_stats['total'] > 0 else 0
        home_ats_rate = ats_stats['home']['wins'] / ats_stats['home']['total'] * 100 if ats_stats['home']['total'] > 0 else 0
        away_ats_rate = ats_stats['away']['wins'] / ats_stats['away']['total'] * 100 if ats_stats['away']['total'] > 0 else 0

        return {
            'team_id': team_id,
            'ats_summary': {
                'total_matches': ats_stats['total'],
                'ats_wins': ats_stats['wins'],
                'ats_losses': ats_stats['losses'],
                'ats_pushes': ats_stats['pushes'],
                'ats_rate': round(ats_rate, 1),
                'home_ats': {
                    'total': ats_stats['home']['total'],
                    'wins': ats_stats['home']['wins'],
                    'losses': ats_stats['home']['losses'],
                    'rate': round(home_ats_rate, 1)
                },
                'away_ats': {
                    'total': ats_stats['away']['total'],
                    'wins': ats_stats['away']['wins'],
                    'losses': ats_stats['away']['losses'],
                    'rate': round(away_ats_rate, 1)
                },
                'by_handicap_type': {
                    k: {
                        'total': v['total'],
                        'wins': v['wins'],
                        'losses': v['losses'],
                        'rate': round(v['wins'] / v['total'] * 100, 1) if v['total'] > 0 else 0
                    }
                    for k, v in ats_stats['by_handicap_type'].items()
                }
            },
            'recent_matches': match_results[:10],
            'all_matches': match_results
        }

    def analyze_over_under(
        self,
        team_id: int,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        limit: int = 20,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        分析大小球趋势 (Over/Under)
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
        conditions.append("o.b365_over_2_5 IS NOT NULL")

        query = f"""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                o.home as b365_over_2_5,
                o.home as over_odds,
                o.away as under_odds,
                ht.name_en as home_team,
                at.name_en as away_team
            FROM matches m
            JOIN match_odds_normalized o ON m.match_id = o.match_id
                AND o.market = 'OVER_UNDER' AND o.bookmaker = 'BET365' AND o.snapshot_type = 'prematch' AND o.line = 2.5
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
                'over_under_summary': None,
                'matches': [],
                'message': '无大小球盘口数据'
            }

        ou_stats = {
            'total': 0,
            'over': 0,
            'under': 0,
            'home': {'total': 0, 'over': 0, 'under': 0},
            'away': {'total': 0, 'over': 0, 'under': 0}
        }

        match_results = []

        for match in matches:
            match_dict = dict(match)
            is_home = match['home_team_id'] == team_id

            total_goals = match['home_goals'] + match['away_goals']
            over_line = match['b365_over_2_5']

            if total_goals > over_line:
                result = 'Over'
                ou_stats['over'] += 1
                if is_home:
                    ou_stats['home']['over'] += 1
                else:
                    ou_stats['away']['over'] += 1
            elif total_goals < over_line:
                result = 'Under'
                ou_stats['under'] += 1
                if is_home:
                    ou_stats['home']['under'] += 1
                else:
                    ou_stats['away']['under'] += 1
            else:
                result = 'Push'

            ou_stats['total'] += 1
            if is_home:
                ou_stats['home']['total'] += 1
            else:
                ou_stats['away']['total'] += 1

            match_results.append({
                'match_id': match['match_id'],
                'date': match['match_date'],
                'venue': 'H' if is_home else 'A',
                'opponent': match['away_team'] if is_home else match['home_team'],
                'over_line': over_line,
                'total_goals': total_goals,
                'result': result,
                'score': f"{match['home_goals']}-{match['away_goals']}"
            })

        over_rate = ou_stats['over'] / ou_stats['total'] * 100 if ou_stats['total'] > 0 else 0
        home_over_rate = ou_stats['home']['over'] / ou_stats['home']['total'] * 100 if ou_stats['home']['total'] > 0 else 0
        away_over_rate = ou_stats['away']['over'] / ou_stats['away']['total'] * 100 if ou_stats['away']['total'] > 0 else 0

        return {
            'team_id': team_id,
            'over_under_summary': {
                'total_matches': ou_stats['total'],
                'over_count': ou_stats['over'],
                'under_count': ou_stats['under'],
                'over_rate': round(over_rate, 1),
                'home_over': {
                    'total': ou_stats['home']['total'],
                    'over': ou_stats['home']['over'],
                    'rate': round(home_over_rate, 1)
                },
                'away_over': {
                    'total': ou_stats['away']['total'],
                    'over': ou_stats['away']['over'],
                    'rate': round(away_over_rate, 1)
                },
                'avg_goals_per_match': round(
                    sum(m['total_goals'] for m in match_results) / len(match_results), 2
                ) if match_results else 0
            },
            'recent_matches': match_results[:10]
        }

    def get_team_handicap_trends(
        self,
        team_id: int,
        last_n: int = 10,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        获取球队盘路趋势
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取最近 N 场比赛的 ATS 结果
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.home_goals,
                m.away_goals,
                o.asian_handicap
            FROM matches m
            JOIN match_odds_normalized o ON m.match_id = o.match_id
                AND o.market = 'ASIAN_HANDICAP' AND o.bookmaker = 'BET365' AND o.snapshot_type = 'prematch'
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.home_goals IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT ?
        """, (team_id, team_id, last_n))

        matches = cursor.fetchall()

        if not matches:
            return {'trend': [], 'current_streak': None}

        trend = []
        current_streak = 0
        streak_type = None

        for match in matches:
            is_home = match['home_team_id'] == team_id
            handicap = match['asian_handicap']

            if is_home:
                team_goals = match['home_goals']
                opp_goals = match['away_goals']
            else:
                team_goals = match['away_goals']
                opp_goals = match['home_goals']
                handicap = -handicap

            adjusted_diff = (team_goals - opp_goals) - handicap

            if adjusted_diff > 0:
                result = 'W'
            elif adjusted_diff < 0:
                result = 'L'
            else:
                result = 'P'

            trend.append(result)

            # 计算当前连胜/连败
            if result == 'P':
                continue

            if streak_type is None:
                streak_type = result
                current_streak = 1
            elif result == streak_type:
                current_streak += 1
            else:
                streak_type = result
                current_streak = 1

        return {
            'team_id': team_id,
            'trend': trend,
            'trend_string': '-'.join(trend),
            'current_streak': {
                'type': streak_type,
                'count': current_streak
            } if streak_type else None
        }

    def compare_teams_handicap(
        self,
        home_team_id: int,
        away_team_id: int,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        比较两队盘路表现
        """
        home_ats = self.analyze_team_ats(home_team_id, conn=conn, limit=20)
        away_ats = self.analyze_team_ats(away_team_id, conn=conn, limit=20)

        return {
            'home_team': {
                'team_id': home_team_id,
                'ats_rate': home_ats.get('ats_summary', {}).get('ats_rate', 0),
                'home_ats_rate': home_ats.get('ats_summary', {}).get('home_ats', {}).get('rate', 0),
                'trend': home_ats.get('recent_matches', [])
            },
            'away_team': {
                'team_id': away_team_id,
                'ats_rate': away_ats.get('ats_summary', {}).get('ats_rate', 0),
                'away_ats_rate': away_ats.get('ats_summary', {}).get('away_ats', {}).get('rate', 0),
                'trend': away_ats.get('recent_matches', [])
            }
        }

    def _categorize_handicap(self, handicap: float) -> str:
        """将让球盘口分类"""
        if handicap == 0:
            return '平手'
        elif 0 < handicap <= 0.5:
            return '让平半'
        elif 0.5 < handicap <= 1:
            return '让半球'
        elif 1 < handicap <= 1.5:
            return '让半一'
        elif 1.5 < handicap <= 2:
            return '让一球'
        elif handicap > 2:
            return '深盘'
        elif -0.5 <= handicap < 0:
            return '受让平半'
        elif -1 <= handicap < -0.5:
            return '受让半球'
        elif -1.5 <= handicap < -1:
            return '受让半一'
        elif -2 <= handicap < -1.5:
            return '受让一球'
        else:
            return '深受让'
