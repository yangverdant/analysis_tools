"""
资讯与利好利空分析模块

分析球队相关资讯，量化利好利空因素对预测的影响
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class NewsFactorsAnalyzer:
    """资讯利好利空分析器"""

    # 利好利空影响权重配置
    FACTOR_WEIGHTS = {
        # 利好因素（正值）
        'star_player_return': 0.08,        # 核心球员复出
        'new_signing_success': 0.05,       # 新援表现出色
        'coach_contract_extension': 0.03,  # 主帅续约
        'winning_streak': 0.06,            # 连胜势头
        'home_support_boost': 0.04,        # 主场氛围好
        'rival_weakness': 0.03,            # 对手状态差

        # 利空因素（负值）
        'key_player_injury': -0.10,        # 核心球员受伤
        'multiple_injuries': -0.15,        # 多名主力受伤
        'suspension': -0.08,               # 重要球员停赛
        'coach_change': -0.12,             # 主帅变动
        'internal_conflict': -0.08,        # 内部矛盾
        'losing_streak': -0.06,            # 连败
        'transfer_saga': -0.05,            # 转会风波
        'financial_issues': -0.04,         # 财务问题
    }

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_team_news(
        self,
        team_id: int,
        days: int = 30,
        conn: sqlite3.Connection = None
    ) -> List[Dict]:
        """
        获取球队近期资讯
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                news_id,
                team_id,
                news_type,
                title,
                content,
                impact_type as factor_type,
                impact_level as impact_score,
                news_date,
                source,
                verified as is_verified
            FROM team_news
            WHERE team_id = ?
            AND news_date >= date('now', ?)
            ORDER BY news_date DESC, impact_level DESC
        """, (team_id, f'-{days} days'))

        news_list = []
        for row in cursor.fetchall():
            news_list.append({
                'news_id': row['news_id'],
                'news_type': row['news_type'],
                'title': row['title'],
                'content': row['content'],
                'factor_type': row['factor_type'],
                'impact_score': row['impact_score'],
                'news_date': row['news_date'],
                'source': row['source'],
                'is_verified': row['is_verified']
            })

        return news_list

    def get_player_status(
        self,
        team_id: int,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        获取球队球员状态汇总
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取球队状态汇总
        cursor.execute("""
            SELECT
                team_id,
                first_team_available as available_players,
                first_team_injured as injured_players,
                first_team_suspended as suspended_players,
                key_players_absent as key_player_absent,
                key_absent_names,
                squad_health_score,
                morale_score,
                updated_at
            FROM team_status_summary
            WHERE team_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
        """, (team_id,))

        result = cursor.fetchone()
        if result:
            return {
                'team_id': result['team_id'],
                'total_players': 25,  # 默认值
                'available_players': result['available_players'] or 0,
                'injured_players': result['injured_players'] or 0,
                'suspended_players': result['suspended_players'] or 0,
                'key_player_injured': result['key_player_absent'] > 0 if result['key_player_absent'] else False,
                'key_player_suspended': False,  # 从 key_absent_names 判断
                'injury_impact_score': self._calculate_injury_impact(result['injured_players'], result['key_player_absent']),
                'suspension_impact_score': 0,
                'overall_impact_score': 1 - (result['squad_health_score'] or 1),
                'updated_at': result['updated_at']
            }

        # 如果汇总表没有数据，从player_status表计算
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
                SUM(CASE WHEN status = 'injured' THEN 1 ELSE 0 END) as injured,
                SUM(CASE WHEN status = 'suspended' THEN 1 ELSE 0 END) as suspended,
                SUM(CASE WHEN status = 'injured' AND team_impact_score > 0.5 THEN 1 ELSE 0 END) as key_injured,
                SUM(CASE WHEN status = 'suspended' AND team_impact_score > 0.5 THEN 1 ELSE 0 END) as key_suspended
            FROM player_status
            WHERE team_id = ?
        """, (team_id,))

        result = cursor.fetchone()
        if result:
            key_injured = result['key_injured'] or 0
            key_suspended = result['key_suspended'] or 0
            return {
                'team_id': team_id,
                'total_players': result['total'] or 0,
                'available_players': result['available'] or 0,
                'injured_players': result['injured'] or 0,
                'suspended_players': result['suspended'] or 0,
                'key_player_injured': key_injured > 0,
                'key_player_suspended': key_suspended > 0,
                'injury_impact_score': self._calculate_injury_impact(result['injured'], key_injured),
                'suspension_impact_score': self._calculate_suspension_impact(result['suspended'], key_suspended),
                'overall_impact_score': 0,
                'updated_at': None
            }

        return {
            'team_id': team_id,
            'total_players': 0,
            'available_players': 0,
            'injured_players': 0,
            'suspended_players': 0,
            'key_player_injured': False,
            'key_player_suspended': False,
            'injury_impact_score': 0,
            'suspension_impact_score': 0,
            'overall_impact_score': 0,
            'updated_at': None
        }

    def _calculate_injury_impact(self, injured: int, key_injured: int) -> float:
        """计算伤病影响评分"""
        if injured is None:
            return 0
        base = injured * 0.02
        key_multiplier = key_injured * 0.05 if key_injured else 0
        return min(base + key_multiplier, 0.2)

    def _calculate_suspension_impact(self, suspended: int, key_suspended: int) -> float:
        """计算停赛影响评分"""
        if suspended is None:
            return 0
        base = suspended * 0.03
        key_multiplier = key_suspended * 0.05 if key_suspended else 0
        return min(base + key_multiplier, 0.15)

    def analyze_team_factors(
        self,
        team_id: int,
        days: int = 30,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析球队利好利空因素汇总
        """
        if conn is None:
            conn = self.get_connection()

        news_list = self.get_team_news(team_id, days, conn)
        player_status = self.get_player_status(team_id, conn)

        # 计算总影响评分
        positive_factors = []
        negative_factors = []
        total_positive_score = 0.0
        total_negative_score = 0.0

        for news in news_list:
            factor_type = news['factor_type']
            impact_score = news['impact_score'] or 0

            if factor_type in self.FACTOR_WEIGHTS:
                weight = self.FACTOR_WEIGHTS[factor_type]
                adjusted_score = impact_score * weight

                factor_info = {
                    'type': factor_type,
                    'title': news['title'],
                    'date': news['news_date'],
                    'base_impact': impact_score,
                    'weighted_impact': round(adjusted_score, 4),
                    'source': news['source'],
                    'is_verified': news['is_verified']
                }

                if weight > 0:
                    positive_factors.append(factor_info)
                    total_positive_score += adjusted_score
                else:
                    negative_factors.append(factor_info)
                    total_negative_score += abs(adjusted_score)

        # 加入球员状态影响
        if player_status['key_player_injured']:
            negative_factors.append({
                'type': 'key_player_injury',
                'title': '核心球员受伤',
                'date': None,
                'base_impact': 1,
                'weighted_impact': abs(self.FACTOR_WEIGHTS['key_player_injury']),
                'source': 'player_status',
                'is_verified': True
            })
            total_negative_score += abs(self.FACTOR_WEIGHTS['key_player_injury'])

        if player_status['key_player_suspended']:
            negative_factors.append({
                'type': 'suspension',
                'title': '核心球员停赛',
                'date': None,
                'base_impact': 1,
                'weighted_impact': abs(self.FACTOR_WEIGHTS['suspension']),
                'source': 'player_status',
                'is_verified': True
            })
            total_negative_score += abs(self.FACTOR_WEIGHTS['suspension'])

        # 计算净影响
        net_impact = total_positive_score - total_negative_score

        # 限制范围
        net_impact = max(-0.3, min(0.3, net_impact))

        return {
            'team_id': team_id,
            'analysis_period_days': days,
            'positive_factors': positive_factors,
            'negative_factors': negative_factors,
            'total_positive_score': round(total_positive_score, 4),
            'total_negative_score': round(total_negative_score, 4),
            'net_impact': round(net_impact, 4),
            'player_status': {
                'injured_players': player_status['injured_players'],
                'suspended_players': player_status['suspended_players'],
                'key_player_injured': player_status['key_player_injured'],
                'key_player_suspended': player_status['key_player_suspended']
            },
            'assessment': self._assess_factors(net_impact)
        }

    def _assess_factors(self, net_impact: float) -> str:
        """评估因素影响"""
        if net_impact >= 0.15:
            return '整体利好明显，球队状态向好'
        elif net_impact >= 0.05:
            return '略有利好，球队状态正常偏好'
        elif net_impact >= -0.05:
            return '因素影响平衡，球队状态正常'
        elif net_impact >= -0.15:
            return '略有利空，球队面临一些问题'
        else:
            return '利空明显，球队状态堪忧'

    def compare_teams_factors(
        self,
        home_team_id: int,
        away_team_id: int,
        days: int = 30,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        比较两队利好利空因素
        """
        if conn is None:
            conn = self.get_connection()

        home_factors = self.analyze_team_factors(home_team_id, days, conn)
        away_factors = self.analyze_team_factors(away_team_id, days, conn)

        home_net = home_factors['net_impact']
        away_net = away_factors['net_impact']

        diff = home_net - away_net

        if diff >= 0.1:
            advantage = 'home'
            level = 'significant'
            description = '主队整体利好明显优于客队'
        elif diff >= 0.05:
            advantage = 'home'
            level = 'moderate'
            description = '主队利好略优于客队'
        elif diff <= -0.1:
            advantage = 'away'
            level = 'significant'
            description = '客队整体利好明显优于主队'
        elif diff <= -0.05:
            advantage = 'away'
            level = 'moderate'
            description = '客队利好略优于主队'
        else:
            advantage = 'balanced'
            level = 'neutral'
            description = '两队利好利空因素相近'

        return {
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_factors': {
                'net_impact': home_net,
                'positive_count': len(home_factors['positive_factors']),
                'negative_count': len(home_factors['negative_factors']),
                'assessment': home_factors['assessment']
            },
            'away_factors': {
                'net_impact': away_net,
                'positive_count': len(away_factors['positive_factors']),
                'negative_count': len(away_factors['negative_factors']),
                'assessment': away_factors['assessment']
            },
            'comparison': {
                'impact_difference': round(diff, 4),
                'advantage': advantage,
                'level': level,
                'description': description
            }
        }

    def get_factors_adjustment(
        self,
        home_team_id: int,
        away_team_id: int,
        base_prediction: Dict,
        days: int = 30,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        基于利好利空因素调整预测
        """
        if conn is None:
            conn = self.get_connection()

        comparison = self.compare_teams_factors(home_team_id, away_team_id, days, conn)

        advantage = comparison['comparison']['advantage']
        diff = comparison['comparison']['impact_difference']

        if advantage == 'balanced':
            return {
                'adjusted': False,
                'reason': '两队利好利空因素相近',
                'prediction': base_prediction,
                'factors_comparison': comparison
            }

        # 调整
        adjusted_home_win = base_prediction['probabilities']['home_win']
        adjusted_draw = base_prediction['probabilities']['draw']
        adjusted_away_win = base_prediction['probabilities']['away_win']

        if advantage == 'home':
            adjusted_home_win += diff
            adjusted_away_win -= diff * 0.5
        else:
            adjusted_away_win += abs(diff)
            adjusted_home_win -= abs(diff) * 0.5

        # 标准化
        total = adjusted_home_win + adjusted_draw + adjusted_away_win
        adjusted_home_win /= total
        adjusted_draw /= total
        adjusted_away_win /= total

        return {
            'adjusted': True,
            'adjustment_factor': round(diff, 4),
            'factors_comparison': comparison,
            'original_prediction': base_prediction['probabilities'],
            'adjusted_prediction': {
                'home_win': round(adjusted_home_win, 4),
                'draw': round(adjusted_draw, 4),
                'away_win': round(adjusted_away_win, 4)
            }
        }

    def get_coach_change_impact(
        self,
        team_id: int,
        conn: sqlite3.Connection = None
    ) -> Optional[Dict]:
        """
        获取教练变动影响
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                change_id,
                team_id,
                old_coach,
                new_coach,
                change_type,
                change_date,
                impact_score,
                reason
            FROM coach_changes
            WHERE team_id = ?
            ORDER BY change_date DESC
            LIMIT 1
        """, (team_id,))

        result = cursor.fetchone()
        if result:
            return {
                'change_id': result['change_id'],
                'old_coach': result['old_coach'],
                'new_coach': result['new_coach'],
                'change_type': result['change_type'],
                'change_date': result['change_date'],
                'impact_score': result['impact_score'] or 0,
                'reason': result['reason']
            }

        return None

    def get_recent_transfers(
        self,
        team_id: int,
        days: int = 90,
        conn: sqlite3.Connection = None
    ) -> List[Dict]:
        """
        获取近期转会记录
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                transfer_id,
                player_name,
                from_team,
                to_team,
                transfer_type,
                transfer_date,
                transfer_value,
                impact_score
            FROM transfers
            WHERE (from_team_id = ? OR to_team_id = ?)
            AND transfer_date >= date('now', ?)
            ORDER BY transfer_date DESC
        """, (team_id, team_id, f'-{days} days'))

        transfers = []
        for row in cursor.fetchall():
            is_out = row['from_team_id'] == team_id if 'from_team_id' in row.keys() else False
            transfers.append({
                'transfer_id': row['transfer_id'],
                'player_name': row['player_name'],
                'transfer_type': row['transfer_type'],
                'transfer_date': row['transfer_date'],
                'transfer_value': row['transfer_value'],
                'impact_score': row['impact_score'] or 0,
                'is_outgoing': is_out
            })

        return transfers