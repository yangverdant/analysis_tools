"""
动机分析模块

分析球队比赛动机，包括：
- 联赛排名位置（争冠、争欧战、保级）
- 赛季阶段（赛季末关键战）
- 比赛重要性（杯赛决赛、关键轮次）
- 休息天数影响
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class MotivationAnalyzer:
    """动机分析器"""

    # 联赛规则默认值（可从league_rules表获取）
    DEFAULT_RULES = {
        'champions_league_slots': 4,      # 欧冠名额
        'europa_league_slots': 2,         # 欧联名额
        'conference_league_slots': 1,     # 欧协联名额
        'relegation_slots': 3,            # 降级名额
        'total_teams': 20                 # 总球队数
    }

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_team_position(
        self,
        team_id: int,
        league_id: int,
        season_id: int,
        conn: sqlite3.Connection = None
    ) -> Optional[Dict]:
        """
        获取球队当前排名位置
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                position,
                played,
                won,
                drawn,
                lost,
                goals_for,
                goals_against,
                goal_diff as goal_difference,
                points
            FROM standings
            WHERE team_id = ?
            AND league_id = ?
            AND season_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
        """, (team_id, league_id, season_id))

        result = cursor.fetchone()
        if result:
            return {
                'position': result['position'],
                'played': result['played'],
                'won': result['won'],
                'drawn': result['drawn'],
                'lost': result['lost'],
                'goals_for': result['goals_for'],
                'goals_against': result['goals_against'],
                'goal_difference': result['goal_difference'],
                'points': result['points']
            }
        return None

    def _calculate_position_from_points(
        self,
        team_id: int,
        league_id: int,
        season_id: int,
        team_points: int,
        conn: sqlite3.Connection
    ) -> Optional[int]:
        """基于积分计算排名位置"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT team_id, points
            FROM standings
            WHERE league_id = ? AND season_id = ?
            ORDER BY points DESC, goal_diff DESC
        """, (league_id, season_id))

        teams = cursor.fetchall()
        for i, team in enumerate(teams):
            if team['team_id'] == team_id:
                return i + 1
        return None

    def get_league_rules(
        self,
        league_id: int,
        season_id: int = None,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        获取联赛规则（欧战名额、降级名额等）
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                champions_league_spots as champions_league_slots,
                europa_league_spots as europa_league_slots,
                conference_league_spots as conference_league_slots,
                relegation_spots as relegation_slots,
                teams_count as total_teams,
                promotion_spots
            FROM league_rules
            WHERE league_id = ?
            ORDER BY season DESC
            LIMIT 1
        """, (league_id,))

        result = cursor.fetchone()
        if result:
            return {
                'champions_league_slots': result['champions_league_slots'] or self.DEFAULT_RULES['champions_league_slots'],
                'europa_league_slots': result['europa_league_slots'] or self.DEFAULT_RULES['europa_league_slots'],
                'conference_league_slots': result['conference_league_slots'] or self.DEFAULT_RULES['conference_league_slots'],
                'relegation_slots': result['relegation_slots'] or self.DEFAULT_RULES['relegation_slots'],
                'total_teams': result['total_teams'] or self.DEFAULT_RULES['total_teams']
            }
        return self.DEFAULT_RULES

    def analyze_motivation(
        self,
        team_id: int,
        league_id: int,
        season_id: int,
        match_date: str = None,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析球队比赛动机

        返回：
        - motivation_level: 动机等级（high/medium/low）
        - motivation_type: 动机类型（title_race/european_race/relegation_battle/mid_table）
        - description: 描述
        - urgency: 紧迫程度
        """
        if conn is None:
            conn = self.get_connection()

        position = self.get_team_position(team_id, league_id, season_id, conn)
        if not position:
            return {
                'team_id': team_id,
                'motivation_level': 'unknown',
                'motivation_type': 'unknown',
                'description': '无法获取排名数据',
                'urgency': 0
            }

        rules = self.get_league_rules(league_id, season_id, conn)

        pos = position['position']
        points = position['points']
        played = position['played']
        total_teams = rules['total_teams']

        # 如果 position 为 None，基于 points 计算排名
        if pos is None:
            pos = self._calculate_position_from_points(team_id, league_id, season_id, points, conn)
            if pos is None:
                pos = total_teams // 2  # 默认中游位置

        # 计算赛季进度
        total_matches = (total_teams - 1) * 2  # 双循环
        season_progress = played / total_matches if total_matches > 0 else 0

        # 判断动机类型
        motivation_type, motivation_level, urgency = self._determine_motivation(
            pos, points, played, season_progress, rules, total_teams
        )

        # 生成描述
        description = self._generate_description(
            motivation_type, pos, points, played, total_teams, rules
        )

        return {
            'team_id': team_id,
            'league_id': league_id,
            'season_id': season_id,
            'position': pos,
            'points': points,
            'played': played,
            'season_progress': round(season_progress * 100, 1),
            'motivation_type': motivation_type,
            'motivation_level': motivation_level,
            'urgency': urgency,
            'description': description,
            'rules': rules
        }

    def _determine_motivation(
        self,
        position: int,
        points: int,
        played: int,
        season_progress: float,
        rules: Dict,
        total_teams: int
    ) -> Tuple[str, str, int]:
        """
        判断动机类型和等级

        Returns:
            (motivation_type, motivation_level, urgency)
        """
        cl_slots = rules['champions_league_slots']
        el_slots = rules['europa_league_slots']
        conf_slots = rules['conference_league_slots']
        relegation_slots = rules['relegation_slots']

        # 欧战区边界
        european_boundary = cl_slots + el_slots + conf_slots
        # 保级区边界
        relegation_boundary = total_teams - relegation_slots

        # 紧迫程度（赛季末更高）
        urgency_multiplier = 1 + (season_progress - 0.7) * 2 if season_progress > 0.7 else 1

        # 争冠
        if position <= 2:
            return 'title_race', 'high', int(100 * urgency_multiplier)

        # 欧战区
        if position <= european_boundary:
            if position <= cl_slots:
                return 'champions_league_race', 'high', int(90 * urgency_multiplier)
            elif position <= cl_slots + el_slots:
                return 'europa_league_race', 'high', int(80 * urgency_multiplier)
            else:
                return 'conference_league_race', 'medium', int(70 * urgency_multiplier)

        # 保级区
        if position >= relegation_boundary:
            return 'relegation_battle', 'high', int(100 * urgency_multiplier)

        # 中游球队
        if european_boundary + 1 <= position <= relegation_boundary - 1:
            # 距离欧战区的距离
            distance_to_european = position - european_boundary
            # 距离保级区的距离
            distance_to_relegation = relegation_boundary - position

            if distance_to_european <= 3 and season_progress > 0.6:
                # 还有机会冲击欧战
                return 'european_hope', 'medium', int(50 * urgency_multiplier)
            elif distance_to_relegation <= 3 and season_progress > 0.6:
                # 需要警惕保级
                return 'relegation_warning', 'medium', int(60 * urgency_multiplier)
            else:
                # 真正的中游
                return 'mid_table', 'low', int(20 * urgency_multiplier)

        # 默认
        return 'mid_table', 'low', 30

    def _generate_description(
        self,
        motivation_type: str,
        position: int,
        points: int,
        played: int,
        total_teams: int,
        rules: Dict
    ) -> str:
        """生成动机描述"""
        remaining = (total_teams - 1) * 2 - played

        descriptions = {
            'title_race': f'争冠关键战！目前第{position}位，{points}分，剩余{remaining}场，每场必争。',
            'champions_league_race': f'欧冠名额争夺！目前第{position}位，处于欧冠区，需要保持位置。',
            'europa_league_race': f'欧联名额争夺！目前第{position}位，处于欧联区，需要稳固排名。',
            'conference_league_race': f'欧协联名额争夺！目前第{position}位，处于欧协联区边缘。',
            'relegation_battle': f'保级生死战！目前第{position}位，处于降级区，必须全力抢分！',
            'european_hope': f'冲击欧战！目前第{position}位，距离欧战区不远，仍有希望。',
            'relegation_warning': f'警惕保级！目前第{position}位，距离降级区较近，需要小心。',
            'mid_table': f'中游位置，目前第{position}位，无太大压力，但也缺乏明确目标。'
        }

        return descriptions.get(motivation_type, f'目前第{position}位，{points}分。')

    def compare_teams_motivation(
        self,
        home_team_id: int,
        away_team_id: int,
        league_id: int,
        season_id: int,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        比较两队动机差异
        """
        if conn is None:
            conn = self.get_connection()

        home_motivation = self.analyze_motivation(home_team_id, league_id, season_id, conn=conn)
        away_motivation = self.analyze_motivation(away_team_id, league_id, season_id, conn=conn)

        # 动机差异评分
        home_urgency = home_motivation.get('urgency', 50)
        away_urgency = away_motivation.get('urgency', 50)

        urgency_diff = home_urgency - away_urgency

        # 判断优势
        if urgency_diff >= 30:
            advantage = 'home'
            level = 'significant'
            description = '主队动机明显更强，有更强的取胜动力'
        elif urgency_diff >= 15:
            advantage = 'home'
            level = 'moderate'
            description = '主队动机略强于客队'
        elif urgency_diff <= -30:
            advantage = 'away'
            level = 'significant'
            description = '客队动机明显更强，有更强的取胜动力'
        elif urgency_diff <= -15:
            advantage = 'away'
            level = 'moderate'
            description = '客队动机略强于主队'
        else:
            advantage = 'balanced'
            level = 'neutral'
            description = '两队动机相近'

        return {
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_motivation': {
                'type': home_motivation.get('motivation_type'),
                'level': home_motivation.get('motivation_level'),
                'urgency': home_urgency,
                'position': home_motivation.get('position'),
                'description': home_motivation.get('description')
            },
            'away_motivation': {
                'type': away_motivation.get('motivation_type'),
                'level': away_motivation.get('motivation_level'),
                'urgency': away_urgency,
                'position': away_motivation.get('position'),
                'description': away_motivation.get('description')
            },
            'comparison': {
                'urgency_difference': urgency_diff,
                'advantage': advantage,
                'level': level,
                'description': description
            }
        }

    def get_motivation_adjustment(
        self,
        home_team_id: int,
        away_team_id: int,
        league_id: int,
        season_id: int,
        base_prediction: Dict,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        基于动机差异调整预测
        """
        if conn is None:
            conn = self.get_connection()

        comparison = self.compare_teams_motivation(
            home_team_id, away_team_id, league_id, season_id, conn
        )

        advantage = comparison['comparison']['advantage']
        urgency_diff = comparison['comparison']['urgency_difference']

        if advantage == 'balanced':
            return {
                'adjusted': False,
                'reason': '两队动机相近',
                'prediction': base_prediction
            }

        # 调整系数
        adjustment = urgency_diff / 500

        adjusted_home_win = base_prediction['probabilities']['home_win']
        adjusted_draw = base_prediction['probabilities']['draw']
        adjusted_away_win = base_prediction['probabilities']['away_win']

        if advantage == 'home':
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
            'motivation_comparison': comparison['comparison'],
            'adjustment_factor': round(adjustment, 4),
            'original_prediction': base_prediction['probabilities'],
            'adjusted_prediction': {
                'home_win': round(adjusted_home_win, 4),
                'draw': round(adjusted_draw, 4),
                'away_win': round(adjusted_away_win, 4)
            }
        }

    def calculate_rest_days(
        self,
        team_id: int,
        match_date: str,
        conn: sqlite3.Connection = None
    ) -> int:
        """
        计算球队上一场比赛到本场比赛的休息天数
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        cursor.execute("""
            SELECT match_date
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
            AND match_date < ?
            AND status = 'finished'
            ORDER BY match_date DESC
            LIMIT 1
        """, (team_id, team_id, match_date))

        result = cursor.fetchone()
        if result:
            last_date = datetime.strptime(result['match_date'], '%Y-%m-%d')
            current_date = datetime.strptime(match_date, '%Y-%m-%d')
            return (current_date - last_date).days

        return 7  # 默认7天

    def get_upcoming_fixtures(
        self,
        team_id: int,
        match_date: str,
        days: int = 14,
        conn: sqlite3.Connection = None
    ) -> List[Dict]:
        """
        获取球队未来N天内的赛程

        Returns:
            未来比赛列表，包含对手、日期、联赛等信息
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 计算未来日期范围
        current_date = datetime.strptime(match_date, '%Y-%m-%d')
        end_date = current_date + timedelta(days=days)

        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.league_id,
                m.season_id,
                l.name_en as league_name,
                l.name_cn as league_name_cn,
                ht.name_en as home_team,
                ht.name_cn as home_team_cn,
                at.name_en as away_team,
                at.name_cn as away_team_cn
            FROM matches m
            LEFT JOIN leagues l ON m.league_id = l.league_id
            LEFT JOIN teams ht ON m.home_team_id = ht.team_id
            LEFT JOIN teams at ON m.away_team_id = at.team_id
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.match_date > ?
            AND m.match_date <= ?
            AND m.status != 'finished'
            ORDER BY m.match_date ASC
        """, (team_id, team_id, match_date, end_date.strftime('%Y-%m-%d')))

        fixtures = []
        for row in cursor.fetchall():
            is_home = row['home_team_id'] == team_id
            opponent_id = row['away_team_id'] if is_home else row['home_team_id']
            opponent_name = row['away_team_cn'] or row['away_team'] if is_home else row['home_team_cn'] or row['home_team']

            # 计算距离当前比赛的天数
            fixture_date = datetime.strptime(row['match_date'], '%Y-%m-%d')
            days_until = (fixture_date - current_date).days

            fixtures.append({
                'match_id': row['match_id'],
                'match_date': row['match_date'],
                'days_until': days_until,
                'is_home': is_home,
                'opponent_id': opponent_id,
                'opponent_name': opponent_name,
                'league_id': row['league_id'],
                'league_name': row['league_name_cn'] or row['league_name'],
                'season_id': row['season_id']
            })

        return fixtures

    def analyze_upcoming_impact(
        self,
        team_id: int,
        team_pos: int,
        match_date: str,
        rules: Dict,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析未来赛程对当前比赛的影响

        考虑因素：
        1. 赛程密集度 - 是否有连续重要比赛
        2. 重要比赛临近 - 是否需要为后续关键战留力
        3. 杯赛影响 - 是否有杯赛比赛
        4. 客场奔波 - 连续客场的影响
        """
        if conn is None:
            conn = self.get_connection()

        # 获取未来14天赛程
        fixtures = self.get_upcoming_fixtures(team_id, match_date, 14, conn)

        if not fixtures:
            return {
                'has_upcoming': False,
                'fixtures_count': 0,
                'intensity': 'low',
                'important_fixtures': [],
                'rotation_risk': 'low',
                'focus_impact': None
            }

        # 分析赛程密集度
        fixtures_count = len(fixtures)
        if fixtures_count >= 5:
            intensity = 'very_high'
        elif fixtures_count >= 4:
            intensity = 'high'
        elif fixtures_count >= 3:
            intensity = 'medium'
        else:
            intensity = 'low'

        # 分析重要比赛
        important_fixtures = []
        european_boundary = rules['champions_league_slots'] + rules['europa_league_slots'] + rules['conference_league_slots']
        relegation_boundary = rules['total_teams'] - rules['relegation_slots']

        for fixture in fixtures:
            is_important = False
            importance_reason = []

            # 获取对手排名
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.position, s.points,
                       (SELECT COUNT(*) + 1 FROM standings s2
                        WHERE s2.league_id = s.league_id AND s2.season_id = s.season_id
                        AND s2.points > s.points) as calculated_position
                FROM standings s
                WHERE s.team_id = ? AND s.league_id = ? AND s.season_id = ?
                ORDER BY s.updated_at DESC LIMIT 1
            """, (fixture['opponent_id'], fixture['league_id'], fixture['season_id']))
            opponent_pos = cursor.fetchone()

            if opponent_pos:
                # 使用position字段，如果为None则使用计算的排名
                opp_pos = opponent_pos['position'] if opponent_pos['position'] is not None else opponent_pos['calculated_position']
                if opp_pos is not None:
                    # 判断是否为重要对手
                    if opp_pos <= 3:
                        is_important = True
                        importance_reason.append(f'争冠球队（第{opp_pos}位）')
                    elif opp_pos <= european_boundary:
                        is_important = True
                        importance_reason.append(f'欧战区球队（第{opp_pos}位）')
                    elif opp_pos >= relegation_boundary:
                        is_important = True
                        importance_reason.append(f'保级区球队（第{opp_pos}位）')
                    elif abs(opp_pos - team_pos) <= 3:
                        is_important = True
                        importance_reason.append(f'直接竞争对手（第{opp_pos}位）')

            # 判断是否为杯赛
            cursor.execute("""
                SELECT competition_type FROM leagues WHERE league_id = ?
            """, (fixture['league_id'],))
            league_info = cursor.fetchone()
            if league_info and league_info['competition_type'] in ('cup', 'international'):
                is_important = True
                importance_reason.append('杯赛比赛')

            if is_important:
                fixture['importance_reason'] = importance_reason
                important_fixtures.append(fixture)

        # 分析轮换风险
        rotation_risk = 'low'
        rotation_reasons = []

        if intensity in ['high', 'very_high']:
            rotation_risk = 'medium'
            rotation_reasons.append(f'{fixtures_count}天内{fixtures_count}场比赛，赛程密集')

        if len(important_fixtures) >= 2:
            rotation_risk = 'high' if rotation_risk != 'low' else 'medium'
            rotation_reasons.append(f'未来有{len(important_fixtures)}场重要比赛')

        # 3天内有关键比赛
        critical_soon = [f for f in important_fixtures if f['days_until'] <= 3]
        if critical_soon:
            rotation_risk = 'high'
            for f in critical_soon:
                rotation_reasons.append(f"{f['days_until']}天后vs {f['opponent_name']}（{', '.join(f.get('importance_reason', []))}）")

        # 分析专注度影响
        focus_impact = None
        if important_fixtures:
            next_important = important_fixtures[0]
            if next_important['days_until'] <= 3:
                focus_impact = {
                    'type': 'distraction',
                    'description': f"可能为{next_important['days_until']}天后vs {next_important['opponent_name']}留力",
                    'impact_level': 'high' if next_important['days_until'] <= 2 else 'medium'
                }

        return {
            'has_upcoming': True,
            'fixtures_count': fixtures_count,
            'intensity': intensity,
            'important_fixtures': important_fixtures[:5],  # 最多返回5场
            'rotation_risk': rotation_risk,
            'rotation_reasons': rotation_reasons,
            'focus_impact': focus_impact
        }

    def analyze_fatigue_factor(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析疲劳因素

        休息天数少的球队可能疲劳，影响表现
        """
        if conn is None:
            conn = self.get_connection()

        home_rest = self.calculate_rest_days(home_team_id, match_date, conn)
        away_rest = self.calculate_rest_days(away_team_id, match_date, conn)

        # 疲劳评分
        home_fatigue = self._calculate_fatigue_score(home_rest)
        away_fatigue = self._calculate_fatigue_score(away_rest)

        # 疲劳差异
        fatigue_diff = away_fatigue - home_fatigue  # 正值表示客队更疲劳

        if fatigue_diff >= 2:
            advantage = 'home'
            description = '客队休息时间较短，可能疲劳，利好主队'
        elif fatigue_diff <= -2:
            advantage = 'away'
            description = '主队休息时间较短，可能疲劳，利好客队'
        else:
            advantage = 'balanced'
            description = '两队休息时间相近，无明显疲劳差异'

        return {
            'home_rest_days': home_rest,
            'away_rest_days': away_rest,
            'home_fatigue_level': home_fatigue,
            'away_fatigue_level': away_fatigue,
            'fatigue_difference': fatigue_diff,
            'advantage': advantage,
            'description': description
        }

    def _calculate_fatigue_score(self, rest_days: int) -> int:
        """
        计算疲劳评分（0-5）

        休息天数越少，疲劳评分越高
        """
        if rest_days >= 7:
            return 0  # 充足休息
        elif rest_days >= 5:
            return 1  # 正常
        elif rest_days >= 3:
            return 2  # 略有疲劳
        elif rest_days >= 2:
            return 3  # 较疲劳
        else:
            return 5  # 极度疲劳

    def analyze_match_importance(
        self,
        home_team_id: int,
        away_team_id: int,
        league_id: int,
        season_id: int,
        match_date: str = None,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析比赛重要性：为什么需要赢、不能输的理由

        从两队角度分析：
        - 争冠形势
        - 欧战资格争夺
        - 保级压力
        - 直接竞争对手对决
        - 赛季关键阶段
        """
        if conn is None:
            conn = self.get_connection()

        # 获取两队排名和积分情况
        home_position = self.get_team_position(home_team_id, league_id, season_id, conn)
        away_position = self.get_team_position(away_team_id, league_id, season_id, conn)

        if not home_position or not away_position:
            return {
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'error': '无法获取排名数据'
            }

        # 获取联赛规则
        rules = self.get_league_rules(league_id, season_id, conn)

        # 计算排名（如果 position 为 None）
        home_pos = home_position['position']
        away_pos = away_position['position']

        if home_pos is None:
            home_pos = self._calculate_position_from_points(home_team_id, league_id, season_id, home_position['points'], conn) or rules['total_teams'] // 2
        if away_pos is None:
            away_pos = self._calculate_position_from_points(away_team_id, league_id, season_id, away_position['points'], conn) or rules['total_teams'] // 2

        # 获取联赛其他球队积分情况
        cursor = conn.cursor()
        cursor.execute("""
            SELECT team_id, points, played, goals_for, goals_against, goal_diff as goal_difference
            FROM standings
            WHERE league_id = ? AND season_id = ?
            ORDER BY points DESC, goal_diff DESC
        """, (league_id, season_id))

        all_standings = cursor.fetchall()

        # 分析两队情况
        home_analysis = self._analyze_team_match_importance(
            home_team_id, home_pos, home_position, away_team_id, away_pos,
            rules, all_standings, match_date, is_home=True, conn=conn
        )
        away_analysis = self._analyze_team_match_importance(
            away_team_id, away_pos, away_position, home_team_id, home_pos,
            rules, all_standings, match_date, is_home=False, conn=conn
        )

        # 判断是否为直接竞争对手对决
        is_direct_competition = self._check_direct_competition(home_pos, away_pos, rules)

        # 比赛重要性等级
        importance_level = self._calculate_match_importance_level(
            home_analysis, away_analysis, is_direct_competition
        )

        return {
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'league_id': league_id,
            'season_id': season_id,
            'match_date': match_date,
            'is_direct_competition': is_direct_competition,
            'importance_level': importance_level,
            'home_analysis': home_analysis,
            'away_analysis': away_analysis,
            'summary': self._generate_importance_summary(home_analysis, away_analysis, is_direct_competition)
        }

    def _analyze_team_match_importance(
        self,
        team_id: int,
        team_pos: int,
        team_position: Dict,
        opponent_id: int,
        opponent_pos: int,
        rules: Dict,
        all_standings: List,
        match_date: str,
        is_home: bool,
        conn: sqlite3.Connection
    ) -> Dict:
        """分析单队的比赛重要性"""
        points = team_position['points']
        played = team_position['played']
        total_teams = rules['total_teams']

        # 计算剩余比赛
        total_matches = (total_teams - 1) * 2
        remaining = total_matches - played

        # 获取边界位置
        cl_slots = rules['champions_league_slots']
        el_slots = rules['europa_league_slots']
        conf_slots = rules['conference_league_slots']
        relegation_slots = rules['relegation_slots']

        european_boundary = cl_slots + el_slots + conf_slots
        relegation_boundary = total_teams - relegation_slots

        # 分析各维度
        reasons_to_win = []
        reasons_not_to_lose = []
        pressure_level = 'normal'
        pressure_score = 50

        # 1. 争冠形势分析
        if team_pos <= 3:
            # 获取第一名积分
            top_points = all_standings[0]['points'] if all_standings else 0
            gap_to_top = top_points - points

            if team_pos == 1:
                reasons_to_win.append({
                    'type': 'title_defense',
                    'description': '领头羊位置，必须赢球巩固榜首优势',
                    'urgency': 'high'
                })
                pressure_score = 90
            elif gap_to_top <= remaining * 3:
                can_catch = gap_to_top <= remaining * 3 * 0.5  # 还有一半赛程能追上
                reasons_to_win.append({
                    'type': 'title_race',
                    'description': f'争冠集团，落后榜首{gap_to_top}分，赢球缩小差距',
                    'urgency': 'high' if can_catch else 'medium'
                })
                if can_catch:
                    pressure_score = 85

        # 2. 欧战资格分析
        if team_pos <= european_boundary + 3:
            if team_pos <= cl_slots:
                reasons_to_win.append({
                    'type': 'champions_league',
                    'description': '处于欧冠区，赢球稳固欧冠资格',
                    'urgency': 'high'
                })
                reasons_not_to_lose.append({
                    'type': 'champions_league_defense',
                    'description': '不能输，否则可能跌出欧冠区',
                    'urgency': 'high'
                })
                pressure_score = max(pressure_score, 80)
            elif team_pos <= cl_slots + el_slots:
                reasons_to_win.append({
                    'type': 'europa_league',
                    'description': '处于欧联区，赢球稳固欧联资格',
                    'urgency': 'medium'
                })
                reasons_not_to_lose.append({
                    'type': 'europa_league_defense',
                    'description': '不能输，否则可能跌出欧战区',
                    'urgency': 'medium'
                })
                pressure_score = max(pressure_score, 70)
            elif team_pos <= european_boundary:
                reasons_to_win.append({
                    'type': 'conference_league',
                    'description': '处于欧协联区边缘，赢球稳固资格',
                    'urgency': 'medium'
                })
                reasons_not_to_lose.append({
                    'type': 'european_defense',
                    'description': '不能输，否则可能跌出欧战区',
                    'urgency': 'medium'
                })
                pressure_score = max(pressure_score, 65)
            else:
                # 在欧战区边缘附近
                gap_to_european = team_pos - european_boundary
                if gap_to_european <= 3:
                    reasons_to_win.append({
                        'type': 'european_hope',
                        'description': f'距离欧战区{gap_to_european}位，赢球冲击欧战资格',
                        'urgency': 'medium'
                    })
                    pressure_score = max(pressure_score, 60)

        # 3. 保级形势分析
        if team_pos >= relegation_boundary - 3:
            if team_pos >= relegation_boundary:
                reasons_to_win.append({
                    'type': 'relegation_battle',
                    'description': '处于降级区，必须赢球逃离',
                    'urgency': 'critical'
                })
                reasons_not_to_lose.append({
                    'type': 'relegation_critical',
                    'description': '绝对不能输，输球将深陷降级区',
                    'urgency': 'critical'
                })
                pressure_score = max(pressure_score, 100)
            elif team_pos >= relegation_boundary - 2:
                reasons_to_win.append({
                    'type': 'relegation_warning',
                    'description': f'距离降级区仅{relegation_boundary - team_pos}位，赢球远离危险',
                    'urgency': 'high'
                })
                reasons_not_to_lose.append({
                    'type': 'relegation_close',
                    'description': '不能输，输球可能跌入降级区',
                    'urgency': 'high'
                })
                pressure_score = max(pressure_score, 90)
            else:
                reasons_to_win.append({
                    'type': 'safety_buffer',
                    'description': '赢球增加保级安全系数',
                    'urgency': 'medium'
                })
                pressure_score = max(pressure_score, 70)

        # 4. 直接竞争对手对决
        pos_diff = abs(team_pos - opponent_pos)
        if pos_diff <= 3 and team_pos < opponent_pos:
            reasons_to_win.append({
                'type': 'direct_competition',
                'description': f'直接竞争对手（排名第{opponent_pos}），赢球拉开差距',
                'urgency': 'high'
            })
            pressure_score = max(pressure_score, 85)
        elif pos_diff <= 3 and team_pos > opponent_pos:
            reasons_to_win.append({
                'type': 'catch_up',
                'description': f'追赶直接竞争对手（排名第{opponent_pos}），赢球缩小差距',
                'urgency': 'high'
            })
            reasons_not_to_lose.append({
                'type': 'competition_defense',
                'description': '不能输，输球将被对手拉开差距',
                'urgency': 'high'
            })
            pressure_score = max(pressure_score, 80)

        # 5. 赛季阶段分析
        season_progress = played / total_matches if total_matches > 0 else 0
        if season_progress > 0.75:
            # 赛季末关键阶段
            if reasons_to_win:
                for reason in reasons_to_win:
                    reason['urgency'] = 'critical' if reason['urgency'] == 'high' else 'high'
                pressure_score = min(pressure_score + 10, 100)

        # 确定压力等级
        if pressure_score >= 90:
            pressure_level = 'critical'
        elif pressure_score >= 75:
            pressure_level = 'high'
        elif pressure_score >= 50:
            pressure_level = 'medium'
        else:
            pressure_level = 'low'

        # 6. 未来赛程影响分析
        upcoming_impact = None
        if match_date:
            upcoming_impact = self.analyze_upcoming_impact(team_id, team_pos, match_date, rules, conn)

            # 如果有重要比赛临近，可能影响当前比赛专注度
            if upcoming_impact and upcoming_impact.get('focus_impact'):
                focus = upcoming_impact['focus_impact']
                if focus['impact_level'] == 'high':
                    reasons_not_to_lose.append({
                        'type': 'upcoming_important',
                        'description': focus['description'],
                        'urgency': 'medium'
                    })

            # 如果赛程密集，需要考虑轮换
            if upcoming_impact and upcoming_impact.get('rotation_risk') == 'high':
                reasons_not_to_lose.append({
                    'type': 'schedule_congestion',
                    'description': f"赛程密集，{', '.join(upcoming_impact.get('rotation_reasons', []))}",
                    'urgency': 'low'
                })

        return {
            'team_id': team_id,
            'position': team_pos,
            'points': points,
            'played': played,
            'remaining': remaining,
            'season_progress': round(season_progress * 100, 1),
            'reasons_to_win': reasons_to_win,
            'reasons_not_to_lose': reasons_not_to_lose,
            'pressure_level': pressure_level,
            'pressure_score': pressure_score,
            'position_context': {
                'total_teams': total_teams,
                'european_boundary': european_boundary,
                'relegation_boundary': relegation_boundary
            },
            'upcoming_impact': upcoming_impact
        }

    def _check_direct_competition(self, home_pos: int, away_pos: int, rules: Dict) -> Dict:
        """检查是否为直接竞争对手对决"""
        pos_diff = abs(home_pos - away_pos)

        cl_slots = rules['champions_league_slots']
        el_slots = rules['europa_league_slots']
        conf_slots = rules['conference_league_slots']
        european_boundary = cl_slots + el_slots + conf_slots
        relegation_boundary = rules['total_teams'] - rules['relegation_slots']

        is_competition = False
        competition_type = None

        # 检查是否都在争冠区
        if home_pos <= 3 and away_pos <= 3:
            is_competition = True
            competition_type = 'title_race'

        # 检查是否都在欧战区争夺
        elif home_pos <= european_boundary + 2 and away_pos <= european_boundary + 2 and pos_diff <= 3:
            is_competition = True
            competition_type = 'european_race'

        # 检查是否都在保级区
        elif home_pos >= relegation_boundary - 2 and away_pos >= relegation_boundary - 2:
            is_competition = True
            competition_type = 'relegation_battle'

        # 检查是否位置相近
        elif pos_diff <= 2:
            is_competition = True
            competition_type = 'position_race'

        return {
            'is_direct_competition': is_competition,
            'position_difference': pos_diff,
            'competition_type': competition_type
        }

    def _calculate_match_importance_level(self, home_analysis: Dict, away_analysis: Dict, is_direct: Dict) -> str:
        """计算比赛重要性等级"""
        home_pressure = home_analysis['pressure_score']
        away_pressure = away_analysis['pressure_score']

        # 综合压力
        combined_pressure = (home_pressure + away_pressure) / 2

        # 直接竞争加成
        if is_direct['is_direct_competition']:
            combined_pressure += 15

        if combined_pressure >= 85:
            return 'critical'
        elif combined_pressure >= 70:
            return 'high'
        elif combined_pressure >= 50:
            return 'medium'
        else:
            return 'low'

    def _generate_importance_summary(self, home_analysis: Dict, away_analysis: Dict, is_direct: Dict) -> str:
        """生成比赛重要性摘要"""
        summary_lines = []

        # 比赛性质
        if is_direct['is_direct_competition']:
            comp_type = is_direct['competition_type']
            if comp_type == 'title_race':
                summary_lines.append('🔥 争冠关键战！两队都在争冠集团，胜负直接影响冠军归属。')
            elif comp_type == 'european_race':
                summary_lines.append('⚡ 欧战资格争夺战！两队都在欧战区附近，胜负决定欧战席位。')
            elif comp_type == 'relegation_battle':
                summary_lines.append('⚠️ 保级生死战！两队都在保级区，胜负决定谁能留在联赛。')
            else:
                summary_lines.append('📊 排名争夺战！两队位置相近，胜负直接影响排名。')

        # 主队分析
        home_reasons = home_analysis['reasons_to_win']
        if home_reasons:
            top_reason = home_reasons[0]
            summary_lines.append(f'\n主队必须赢的理由：{top_reason["description"]}')

        home_not_lose = home_analysis['reasons_not_to_lose']
        if home_not_lose:
            top_reason = home_not_lose[0]
            summary_lines.append(f'主队不能输的理由：{top_reason["description"]}')

        # 客队分析
        away_reasons = away_analysis['reasons_to_win']
        if away_reasons:
            top_reason = away_reasons[0]
            summary_lines.append(f'\n客队必须赢的理由：{top_reason["description"]}')

        away_not_lose = away_analysis['reasons_not_to_lose']
        if away_not_lose:
            top_reason = away_not_lose[0]
            summary_lines.append(f'客队不能输的理由：{top_reason["description"]}')

        # 压力对比
        home_pressure = home_analysis['pressure_level']
        away_pressure = away_analysis['pressure_level']

        summary_lines.append(f'\n主队压力等级：{home_pressure}')
        summary_lines.append(f'客队压力等级：{away_pressure}')

        if home_analysis['pressure_score'] > away_analysis['pressure_score'] + 15:
            summary_lines.append('\n💡 主队压力更大，取胜欲望更强。')
        elif away_analysis['pressure_score'] > home_analysis['pressure_score'] + 15:
            summary_lines.append('\n💡 客队压力更大，取胜欲望更强。')
        else:
            summary_lines.append('\n💡 两队压力相近，比赛可能更加激烈。')

        return '\n'.join(summary_lines)