"""
赛季积分推理分析模块

分析：
- 积分形势：争冠/欧战/保级区距离
- 剩余赛程推演：理论最高/最低积分
- 关键比赛识别：6分战、生死战
- 提前夺冠/提前降级判定
- 轮换预判：下一场是否更关键
- 双线作战影响：联赛 vs 杯赛取舍
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class SeasonScenarioAnalyzer:
    """赛季积分推理分析器"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ==================== 核心分析 ====================

    def analyze_team_season_scenario(
        self,
        team_id: int,
        league_id: int,
        season_id: int,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        综合分析球队赛季积分形势

        返回：当前排名、距离各区域差距、剩余赛程、理论极值、关键比赛
        """
        if conn is None:
            conn = self.get_connection()

        # 1. 获取联赛规则
        rules = self._get_league_rules(league_id, conn)

        # 2. 获取积分榜
        standings = self._get_full_standings(league_id, season_id, conn)
        if not standings:
            return {'error': '无积分榜数据', 'team_id': team_id}

        # 3. 获取当前球队排名
        team_standing = None
        for s in standings:
            if s['team_id'] == team_id:
                team_standing = s
                break

        if not team_standing:
            return {'error': '球队不在积分榜中', 'team_id': team_id}

        # 4. 计算总轮次和剩余轮次
        total_rounds = self._get_total_rounds(league_id, season_id, conn)
        played = team_standing['played']
        remaining = total_rounds - played if total_rounds else 0

        # 5. 计算理论极值
        current_pts = team_standing['points']
        max_possible = current_pts + remaining * 3
        min_possible = current_pts

        # 6. 分析距离各区域差距
        zone_gaps = self._calculate_zone_gaps(team_standing, standings, rules, remaining)

        # 7. 获取剩余赛程
        remaining_fixtures = self._get_remaining_fixtures(team_id, league_id, season_id, conn)

        # 8. 分析剩余赛程难度
        schedule_difficulty = self._analyze_schedule_difficulty(
            team_id, remaining_fixtures, standings, conn
        )

        # 9. 判定提前夺冠/提前降级
        clinch_analysis = self._analyze_clinch_scenarios(
            team_standing, standings, remaining, rules
        )

        # 10. 识别关键比赛
        key_matches = self._identify_key_matches(
            team_id, remaining_fixtures, standings, zone_gaps, rules
        )

        return {
            'team_id': team_id,
            'league_id': league_id,
            'season_id': season_id,
            'current_status': {
                'position': team_standing['position'],
                'points': current_pts,
                'played': played,
                'won': team_standing['won'],
                'drawn': team_standing['drawn'],
                'lost': team_standing['lost'],
                'goal_diff': team_standing['goal_diff'],
                'form': team_standing.get('form', ''),
                'team_name': team_standing.get('team_name', '')
            },
            'season_progress': {
                'total_rounds': total_rounds,
                'played': played,
                'remaining': remaining,
                'progress_pct': round(played / total_rounds * 100, 1) if total_rounds else 0
            },
            'points_projection': {
                'current': current_pts,
                'max_possible': max_possible,
                'min_possible': min_possible,
                'realistic_max': self._project_realistic_points(
                    current_pts, schedule_difficulty
                ),
                'realistic_min': self._project_realistic_min(
                    current_pts, schedule_difficulty
                ),
                'avg_projection': self._project_avg_points(
                    current_pts, remaining, standings, team_id
                )
            },
            'zone_gaps': zone_gaps,
            'schedule_difficulty': schedule_difficulty,
            'remaining_fixtures': remaining_fixtures[:10],
            'clinch_analysis': clinch_analysis,
            'key_matches': key_matches,
            'motivation_assessment': self._assess_motivation(
                team_standing, zone_gaps, remaining, clinch_analysis
            )
        }

    def analyze_rotation_risk(
        self,
        team_id: int,
        league_id: int,
        season_id: int,
        next_match_date: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        分析球队轮换风险

        判断下一场联赛是否可能轮换：
        - 联赛形势是否已定（无欲无求）
        - 下一场是否是更关键的比赛（杯赛决赛/欧战淘汰赛）
        - 赛程密集度
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 1. 获取联赛形势
        scenario = self.analyze_team_season_scenario(
            team_id, league_id, season_id, conn
        )

        if 'error' in scenario:
            return scenario

        motivation = scenario.get('motivation_assessment', {})

        # 2. 获取近期赛程（所有赛事）
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.league_id,
                m.home_goals,
                m.away_goals,
                l.name_en as league_name,
                l.competition_type,
                ht.name_en as home_team,
                at.name_en as away_team
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.match_date >= date('now')
            ORDER BY m.match_date
            LIMIT 10
        """, (team_id, team_id))

        upcoming = [dict(row) for row in cursor.fetchall()]

        # 3. 分析赛程重要性排序
        match_importance = []
        for match in upcoming:
            importance = self._rate_match_importance(
                team_id, match, scenario, conn
            )
            match_importance.append({
                'match_id': match['match_id'],
                'date': match['match_date'],
                'league': match['league_name'],
                'competition_type': match['competition_type'],
                'opponent': match['away_team'] if match['home_team_id'] == team_id else match['home_team'],
                'venue': 'H' if match['home_team_id'] == team_id else 'A',
                'importance': importance['level'],
                'importance_score': importance['score'],
                'reason': importance['reason']
            })

        # 4. 判断轮换可能性
        rotation_analysis = self._assess_rotation_probability(
            motivation, match_importance, upcoming
        )

        return {
            'team_id': team_id,
            'league_id': league_id,
            'motivation': motivation,
            'upcoming_matches': match_importance,
            'rotation_analysis': rotation_analysis
        }

    def analyze_six_pointer(
        self,
        home_team_id: int,
        away_team_id: int,
        league_id: int,
        season_id: int,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        分析 6 分战（直接竞争对手对决）

        判断：
        - 两队是否处于同一竞争区域
        - 本场结果对排名的影响
        - 赢/平/输后各队的形势变化
        """
        if conn is None:
            conn = self.get_connection()

        # 获取两队排名
        standings = self._get_full_standings(league_id, season_id, conn)

        home_standing = None
        away_standing = None
        for s in standings:
            if s['team_id'] == home_team_id:
                home_standing = s
            elif s['team_id'] == away_team_id:
                away_standing = s

        if not home_standing or not away_standing:
            return {'error': '球队不在积分榜中'}

        rules = self._get_league_rules(league_id, conn)

        # 判断是否为直接竞争关系
        competition_type = self._determine_competition_type(
            home_standing, away_standing, rules
        )

        # 模拟三种结果
        simulations = self._simulate_match_outcomes(
            home_standing, away_standing, standings, rules
        )

        # 判定是否为 6 分战
        is_six_pointer = (
            competition_type in ['title_race', 'european_race', 'relegation_battle']
            and abs(home_standing['position'] - away_standing['position']) <= 5
        )

        return {
            'home_team': {
                'team_id': home_team_id,
                'team_name': home_standing.get('team_name', ''),
                'position': home_standing['position'],
                'points': home_standing['points'],
                'played': home_standing['played']
            },
            'away_team': {
                'team_id': away_team_id,
                'team_name': away_standing.get('team_name', ''),
                'position': away_standing['position'],
                'points': away_standing['points'],
                'played': away_standing['played']
            },
            'competition_type': competition_type,
            'competition_description': self._get_competition_description(competition_type),
            'is_six_pointer': is_six_pointer,
            'points_gap': abs(home_standing['points'] - away_standing['points']),
            'simulations': simulations,
            'match_significance': self._rate_match_significance(
                is_six_pointer, competition_type,
                home_standing, away_standing
            )
        }

    def analyze_title_race(
        self,
        league_id: int,
        season_id: int,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """分析争冠形势"""
        if conn is None:
            conn = self.get_connection()

        standings = self._get_full_standings(league_id, season_id, conn)
        if not standings:
            return {'error': '无积分榜数据'}

        rules = self._get_league_rules(league_id, conn)
        total_rounds = self._get_total_rounds(league_id, season_id, conn)

        # 取前 6 名
        top_teams = standings[:6]

        leader = top_teams[0]
        title_race_teams = []

        for team in top_teams:
            gap = leader['points'] - team['points']
            remaining = total_rounds - team['played'] if total_rounds else 0
            max_pts = team['points'] + remaining * 3

            # 能否追上领头羊
            can_catch = max_pts >= leader['points']

            # 需要的追赶条件
            catch_condition = None
            if gap > 0 and can_catch:
                catch_condition = self._calculate_catch_condition(
                    gap, remaining, leader, team
                )

            title_race_teams.append({
                'team_id': team['team_id'],
                'team_name': team.get('team_name', ''),
                'position': team['position'],
                'points': team['points'],
                'played': team['played'],
                'gap_to_leader': gap,
                'remaining': remaining,
                'max_possible': max_pts,
                'can_catch_leader': can_catch,
                'catch_condition': catch_condition,
                'title_probability': self._estimate_title_probability(
                    gap, remaining
                )
            })

        # 判断是否已提前夺冠
        leader_remaining = total_rounds - leader['played'] if total_rounds else 0
        second_max = title_race_teams[1]['max_possible'] if len(title_race_teams) > 1 else 0
        clinched = leader['points'] > second_max

        return {
            'league_id': league_id,
            'season_id': season_id,
            'leader': {
                'team_id': leader['team_id'],
                'team_name': leader.get('team_name', ''),
                'points': leader['points'],
                'remaining': leader_remaining
            },
            'title_race_teams': title_race_teams,
            'is_clinched': clinched,
            'is_race_over': gap > leader_remaining * 3 if leader_remaining else False,
            'race_intensity': self._assess_race_intensity(title_race_teams)
        }

    def analyze_relegation_battle(
        self,
        league_id: int,
        season_id: int,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """分析保级形势"""
        if conn is None:
            conn = self.get_connection()

        standings = self._get_full_standings(league_id, season_id, conn)
        if not standings:
            return {'error': '无积分榜数据'}

        rules = self._get_league_rules(league_id, conn)
        total_rounds = self._get_total_rounds(league_id, season_id, conn)

        # 降级线
        relegation_start = rules.get('relegation_start', len(standings) - 2)
        safety_line_pos = relegation_start - 1

        # 找安全线分数
        safety_points = 0
        for s in standings:
            if s['position'] == safety_line_pos:
                safety_points = s['points']
                break

        # 分析保级区及附近球队
        relegation_teams = []
        for team in standings:
            if team['position'] >= relegation_start - 3:
                remaining = total_rounds - team['played'] if total_rounds else 0
                max_pts = team['points'] + remaining * 3
                gap_to_safety = safety_points - team['points']

                # 能否逃脱
                can_escape = max_pts > safety_points

                # 需要什么条件
                escape_condition = None
                if gap_to_safety > 0 and can_escape:
                    escape_condition = self._calculate_escape_condition(
                        gap_to_safety, remaining
                    )

                relegation_teams.append({
                    'team_id': team['team_id'],
                    'team_name': team.get('team_name', ''),
                    'position': team['position'],
                    'points': team['points'],
                    'played': team['played'],
                    'remaining': remaining,
                    'max_possible': max_pts,
                    'gap_to_safety': gap_to_safety,
                    'in_relegation_zone': team['position'] >= relegation_start,
                    'can_escape': can_escape,
                    'escape_condition': escape_condition,
                    'survival_probability': self._estimate_survival_probability(
                        gap_to_safety, remaining
                    )
                })

        # 判断是否有球队已提前降级
        for team in relegation_teams:
            if team['in_relegation_zone']:
                # 最高分也无法超过安全线
                safety_team_max = 0
                for s in standings:
                    if s['position'] == safety_line_pos:
                        sr = total_rounds - s['played'] if total_rounds else 0
                        safety_team_max = s['points'] + sr * 3
                        break
                team['is_relegated'] = team['max_possible'] < safety_points

        return {
            'league_id': league_id,
            'season_id': season_id,
            'safety_line': {
                'position': safety_line_pos,
                'points': safety_points
            },
            'relegation_start': relegation_start,
            'relegation_teams': relegation_teams,
            'battle_intensity': self._assess_relegation_intensity(relegation_teams)
        }

    # ==================== 内部计算方法 ====================

    def _get_league_rules(self, league_id: int, conn: sqlite3.Connection) -> Dict:
        """获取联赛规则"""
        cursor = conn.cursor()

        # league_rules uses league_code, so join via leagues table
        cursor.execute("""
            SELECT lr.* FROM league_rules lr
            JOIN leagues l ON lr.league_code = l.league_code
            WHERE l.league_id = ?
        """, (league_id,))
        row = cursor.fetchone()

        if row:
            cols = [desc[0] for desc in cursor.description]
            d = dict(zip(cols, row))
            total_teams = d.get('teams_count') or 20
            rel_spots = d.get('relegation_spots') or 3
            rel_start = d.get('relegation_playoff_spots')
            if rel_start is None:
                rel_start = total_teams - rel_spots + 1
            return {
                'champion_spots': 1,
                'promotion_spots': d.get('promotion_spots') or 0,
                'champions_league_spots': d.get('champions_league_spots') or 4,
                'europa_league_spots': d.get('europa_league_spots') or 2,
                'conference_league_spots': d.get('conference_league_spots') or 1,
                'relegation_spots': rel_spots,
                'relegation_start': rel_start,
                'total_teams': total_teams,
                'playoff_spots': d.get('playoff_teams') or 0,
            }

        # Fallback: derive from standings count
        cursor.execute("""
            SELECT COUNT(DISTINCT team_id) as cnt FROM standings
            WHERE league_id = ? AND season_id = (SELECT MIN(season_id) FROM standings WHERE league_id = ?)
        """, (league_id, league_id))
        count_row = cursor.fetchone()
        total_teams = count_row['cnt'] if count_row and count_row['cnt'] else 20
        rel_spots = 3 if total_teams == 20 else 2

        return {
            'champion_spots': 1,
            'champions_league_spots': 4,
            'europa_league_spots': 2,
            'conference_league_spots': 1,
            'relegation_spots': rel_spots,
            'relegation_start': total_teams - rel_spots + 1,
            'total_teams': total_teams,
            'playoff_spots': 0,
        }

    def _get_full_standings(
        self,
        league_id: int,
        season_id: int,
        conn: sqlite3.Connection
    ) -> List[Dict]:
        """获取完整积分榜"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                s.position,
                s.team_id,
                s.played,
                s.won,
                s.drawn,
                s.lost,
                s.goals_for,
                s.goals_against,
                s.goal_diff,
                s.points,
                s.form,
                t.name_en as team_name
            FROM standings s
            JOIN teams t ON s.team_id = t.team_id
            WHERE s.league_id = ? AND s.season_id = ?
            ORDER BY s.points DESC, s.goal_diff DESC, s.goals_for DESC
        """, (league_id, season_id))

        standings = [dict(row) for row in cursor.fetchall()]

        # If position is NULL, compute from sort order
        for i, s in enumerate(standings):
            if s['position'] is None:
                s['position'] = i + 1

        return standings

    def _get_total_rounds(
        self,
        league_id: int,
        season_id: int,
        conn: sqlite3.Connection
    ) -> Optional[int]:
        """获取联赛总轮次"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(CAST(round_num AS INTEGER)) as max_round
            FROM matches
            WHERE league_id = ? AND season_id = ?
        """, (league_id, season_id))
        result = cursor.fetchone()
        if result and result['max_round']:
            return result['max_round']

        # 从球队数推算
        rules = self._get_league_rules(league_id, conn)
        teams = rules.get('total_teams', 20)
        return (teams - 1) * 2  # 主客场双循环

    def _calculate_zone_gaps(
        self,
        team_standing: Dict,
        standings: List[Dict],
        rules: Dict,
        remaining: int
    ) -> Dict:
        """计算距离各区域的差距"""
        current_pos = team_standing['position']
        current_pts = team_standing['points']
        total_teams = len(standings)

        cl_spots = rules.get('champions_league_spots', 4)
        el_spots = cl_spots + rules.get('europa_league_spots', 2)
        conf_spots = el_spots + rules.get('conference_league_spots', 1)
        rel_start = rules.get('relegation_start') or (total_teams - rules.get('relegation_spots', 3) + 1)

        zones = {}

        # 争冠区
        if current_pos <= cl_spots:
            zones['champion_league'] = {
                'status': 'in_zone',
                'gap': 0,
                'description': '处于欧冠区'
            }
        else:
            cl_line_pts = 0
            for s in standings:
                if s['position'] == cl_spots:
                    cl_line_pts = s['points']
                    break
            gap = cl_line_pts - current_pts
            zones['champion_league'] = {
                'status': 'below' if gap > 0 else 'above',
                'gap': gap,
                'gap_in_wins': -(-gap // 3),  # 向上取整
                'can_reach': remaining * 3 >= gap,
                'description': f'距欧冠区 {gap} 分' if gap > 0 else '处于欧冠区'
            }

        # 欧联区
        if current_pos <= el_spots:
            zones['europa_league'] = {
                'status': 'in_zone' if current_pos > cl_spots else 'above',
                'gap': 0,
                'description': '处于欧联区' if current_pos > cl_spots else '已超欧联区'
            }
        else:
            el_line_pts = 0
            for s in standings:
                if s['position'] == el_spots:
                    el_line_pts = s['points']
                    break
            gap = el_line_pts - current_pts
            zones['europa_league'] = {
                'status': 'below',
                'gap': gap,
                'gap_in_wins': -(-gap // 3),
                'can_reach': remaining * 3 >= gap,
                'description': f'距欧联区 {gap} 分'
            }

        # 降级区
        if current_pos >= rel_start:
            zones['relegation'] = {
                'status': 'in_zone',
                'gap': 0,
                'description': '处于降级区'
            }
        else:
            rel_line_pts = 0
            for s in standings:
                if s['position'] == rel_start:
                    rel_line_pts = s['points']
                    break
            gap = current_pts - rel_line_pts
            zones['relegation'] = {
                'status': 'above',
                'gap': gap,
                'gap_in_wins': gap // 3 + (1 if gap % 3 else 0),
                'safe': gap > remaining * 3 - 3,
                'description': f'领先降级区 {gap} 分'
            }

        # 无欲无求区
        mid_start = conf_spots + 1
        mid_end = rel_start - 1
        if mid_start <= current_pos <= mid_end:
            zones['mid_table'] = {
                'status': 'in_zone',
                'gap_to_europe': zones.get('europa_league', {}).get('gap', 0)
                    if 'europa_league' in zones else 0,
                'gap_to_relegation': zones.get('relegation', {}).get('gap', 0)
                    if 'relegation' in zones else 0,
                'description': '中游无欲无求'
            }

        return zones

    def _get_remaining_fixtures(
        self,
        team_id: int,
        league_id: int,
        season_id: int,
        conn: sqlite3.Connection
    ) -> List[Dict]:
        """获取剩余赛程"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.round_num,
                m.home_team_id,
                m.away_team_id,
                ht.name_en as home_team,
                at.name_en as away_team
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.league_id = ? AND m.season_id = ?
            AND m.home_goals IS NULL
            ORDER BY m.match_date
        """, (team_id, team_id, league_id, season_id))

        return [dict(row) for row in cursor.fetchall()]

    def _analyze_schedule_difficulty(
        self,
        team_id: int,
        fixtures: List[Dict],
        standings: List[Dict],
        conn: sqlite3.Connection
    ) -> Dict:
        """分析赛程难度"""
        if not fixtures:
            return {
                'difficulty_rating': 'unknown',
                'difficulty_score': 0,
                'easy_matches': 0,
                'medium_matches': 0,
                'hard_matches': 0,
                'home_matches': 0,
                'away_matches': 0
            }

        # 构建排名映射
        position_map = {}
        for s in standings:
            position_map[s['team_id']] = s['position']

        easy = 0
        medium = 0
        hard = 0
        home = 0
        away = 0
        difficulty_scores = []

        for fixture in fixtures:
            is_home = fixture['home_team_id'] == team_id
            opp_id = fixture['away_team_id'] if is_home else fixture['home_team_id']

            if is_home:
                home += 1
            else:
                away += 1

            opp_pos = position_map.get(opp_id, 10)
            total_teams = len(standings) or 20

            # 难度评分 (1-10)
            score = 10 - (opp_pos / total_teams * 8)
            if not is_home:
                score += 0.5  # 客场加难度

            difficulty_scores.append(score)

            if opp_pos <= total_teams * 0.3:
                hard += 1
            elif opp_pos <= total_teams * 0.7:
                medium += 1
            else:
                easy += 1

        avg_difficulty = sum(difficulty_scores) / len(difficulty_scores) if difficulty_scores else 5

        if avg_difficulty >= 6:
            rating = 'hard'
        elif avg_difficulty >= 4:
            rating = 'medium'
        else:
            rating = 'easy'

        return {
            'difficulty_rating': rating,
            'difficulty_score': round(avg_difficulty, 1),
            'total_remaining': len(fixtures),
            'easy_matches': easy,
            'medium_matches': medium,
            'hard_matches': hard,
            'home_matches': home,
            'away_matches': away
        }

    def _analyze_clinch_scenarios(
        self,
        team_standing: Dict,
        standings: List[Dict],
        remaining: int,
        rules: Dict
    ) -> Dict:
        """分析提前夺冠/提前降级场景"""
        current_pos = team_standing['position']
        current_pts = team_standing['points']
        total_teams = len(standings)

        result = {
            'can_clinch_title': False,
            'title_clinch_condition': None,
            'can_be_relegated': False,
            'relegation_condition': None,
            'can_clinch_europe': False,
            'europe_clinch_condition': None
        }

        # 提前夺冠
        if current_pos == 1 and remaining > 0:
            second_pts = standings[1]['points'] if len(standings) > 1 else 0
            second_remaining = remaining  # 简化
            gap = current_pts - second_pts
            if gap > second_remaining * 3:
                result['can_clinch_title'] = True
                result['title_clinch_condition'] = '已提前夺冠'
            elif gap == second_remaining * 3:
                result['can_clinch_title'] = True
                result['title_clinch_condition'] = '本场不败即夺冠'
            elif gap + 3 > second_remaining * 3:
                result['title_clinch_condition'] = f'再赢 {remaining - (gap // 3)} 场即夺冠'

        # 提前降级
        rel_start = rules.get('relegation_start') or (total_teams - rules.get('relegation_spots', 3) + 1)
        if current_pos >= rel_start - 2:
            safety_pts = 0
            for s in standings:
                if s['position'] == rel_start - 1:
                    safety_pts = s['points']
                    break

            gap_to_safety = safety_pts - current_pts
            if gap_to_safety > remaining * 3:
                result['can_be_relegated'] = True
                result['relegation_condition'] = '已提前降级'
            elif gap_to_safety == remaining * 3:
                result['relegation_condition'] = '本场不胜即降级'

        # 提前锁定欧战
        cl_spots = rules.get('champions_league_spots', 4)
        el_spots = cl_spots + rules.get('europa_league_spots', 2)
        if current_pos <= el_spots:
            # 检查是否已锁定
            first_below_pts = 0
            for s in standings:
                if s['position'] == el_spots + 1:
                    first_below_pts = s['points']
                    break

            gap_below = current_pts - first_below_pts
            if gap_below > remaining * 3:
                result['can_clinch_europe'] = True
                result['europe_clinch_condition'] = '已锁定欧战资格'

        return result

    def _identify_key_matches(
        self,
        team_id: int,
        fixtures: List[Dict],
        standings: List[Dict],
        zone_gaps: Dict,
        rules: Dict
    ) -> List[Dict]:
        """识别关键比赛"""
        if not fixtures:
            return []

        position_map = {}
        points_map = {}
        for s in standings:
            position_map[s['team_id']] = s['position']
            points_map[s['team_id']] = s['points']

        key_matches = []

        for fixture in fixtures[:10]:
            is_home = fixture['home_team_id'] == team_id
            opp_id = fixture['away_team_id'] if is_home else fixture['home_team_id']
            opp_pos = position_map.get(opp_id, 10)
            team_pos = position_map.get(team_id, 10)

            importance = 'normal'
            reason = ''

            # 6 分战（同区域直接竞争）
            pts_gap = abs(points_map.get(team_id, 0) - points_map.get(opp_id, 0))
            same_zone = abs(team_pos - opp_pos) <= 4

            if same_zone and pts_gap <= 6:
                importance = 'six_pointer'
                reason = f'6分战：对手第{opp_pos}名，仅差{pts_gap}分'
            elif same_zone and pts_gap <= 9:
                importance = 'important'
                reason = f'关键战：对手第{opp_pos}名，差{pts_gap}分'

            # 保级 6 分战
            rel_start = rules.get('relegation_start') or (len(standings) - rules.get('relegation_spots', 3) + 1)
            if team_pos >= rel_start - 2 and opp_pos >= rel_start - 2:
                importance = 'relegation_six_pointer'
                reason = f'保级生死战：对手第{opp_pos}名'

            # 争冠战
            if team_pos <= 2 and opp_pos <= 3:
                importance = 'title_decider'
                reason = '争冠关键战'

            if importance != 'normal':
                key_matches.append({
                    'match_id': fixture['match_id'],
                    'date': fixture['match_date'],
                    'round': fixture.get('round'),
                    'opponent': fixture['away_team'] if is_home else fixture['home_team'],
                    'venue': 'H' if is_home else 'A',
                    'opponent_position': opp_pos,
                    'importance': importance,
                    'reason': reason
                })

        return key_matches

    def _assess_motivation(
        self,
        team_standing: Dict,
        zone_gaps: Dict,
        remaining: int,
        clinch_analysis: Dict
    ) -> Dict:
        """评估球队战意"""
        current_pos = team_standing['position']

        # 已提前夺冠
        if clinch_analysis.get('can_clinch_title') and clinch_analysis.get('title_clinch_condition') == '已提前夺冠':
            return {
                'level': 'very_low',
                'description': '已提前夺冠，可能轮换',
                'rotation_risk': 'high',
                'key_factor': 'title_clinched'
            }

        # 已提前降级
        if clinch_analysis.get('can_be_relegated') and clinch_analysis.get('relegation_condition') == '已提前降级':
            return {
                'level': 'very_low',
                'description': '已提前降级，士气低落',
                'rotation_risk': 'medium',
                'key_factor': 'relegated'
            }

        # 已锁定欧战
        if clinch_analysis.get('can_clinch_europe') and clinch_analysis.get('europe_clinch_condition') == '已锁定欧战资格':
            return {
                'level': 'low',
                'description': '已锁定欧战资格，可能轮换',
                'rotation_risk': 'medium',
                'key_factor': 'europe_clinched'
            }

        # 争冠
        if current_pos <= 2:
            return {
                'level': 'very_high',
                'description': '争冠关键期，全力以赴',
                'rotation_risk': 'very_low',
                'key_factor': 'title_race'
            }

        # 争欧战
        if 'champion_league' in zone_gaps and zone_gaps['champion_league'].get('gap', 999) <= 6:
            return {
                'level': 'very_high',
                'description': '距欧冠区仅差几分，全力冲刺',
                'rotation_risk': 'very_low',
                'key_factor': 'cl_race'
            }

        if 'europa_league' in zone_gaps and zone_gaps['europa_league'].get('gap', 999) <= 6:
            return {
                'level': 'high',
                'description': '距欧战区仅差几分，战意强',
                'rotation_risk': 'low',
                'key_factor': 'europe_race'
            }

        # 保级
        if 'relegation' in zone_gaps:
            rel_gap = zone_gaps['relegation'].get('gap', 999)
            if rel_gap <= 3:
                return {
                    'level': 'very_high',
                    'description': '保级生死关头，拼命一战',
                    'rotation_risk': 'very_low',
                    'key_factor': 'relegation_battle'
                }
            elif rel_gap <= 6:
                return {
                    'level': 'high',
                    'description': '保级压力大，不敢松懈',
                    'rotation_risk': 'low',
                    'key_factor': 'relegation_pressure'
                }

        # 无欲无求
        if 'mid_table' in zone_gaps:
            mid = zone_gaps['mid_table']
            gap_europe = mid.get('gap_to_europe', 99)
            gap_relegation = mid.get('gap_to_relegation', 99)
            if gap_europe > 9 and gap_relegation > 9:
                return {
                    'level': 'low',
                    'description': '中游无欲无求，可能轮换',
                    'rotation_risk': 'high',
                    'key_factor': 'mid_table_comfort'
                }

        return {
            'level': 'normal',
            'description': '正常战意',
            'rotation_risk': 'low',
            'key_factor': 'normal'
        }

    def _rate_match_importance(
        self,
        team_id: int,
        match: Dict,
        league_scenario: Dict,
        conn: sqlite3.Connection
    ) -> Dict:
        """评估单场比赛重要性"""
        league_id = match['league_id']
        comp_type = match.get('competition_type', 'league')

        # 杯赛决赛/半决赛
        if comp_type == 'cup':
            # 简化判断：杯赛淘汰赛都很重要
            return {
                'level': 'very_high',
                'score': 9,
                'reason': '杯赛淘汰赛'
            }

        # 联赛
        motivation = league_scenario.get('motivation_assessment', {})
        motivation_level = motivation.get('level', 'normal')

        score_map = {
            'very_high': 9,
            'high': 7,
            'normal': 5,
            'low': 3,
            'very_low': 1
        }

        score = score_map.get(motivation_level, 5)

        # 如果是德比战，加分
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name_en FROM teams WHERE team_id = ?
        """, (team_id,))
        team = cursor.fetchone()

        return {
            'level': 'very_high' if score >= 8 else ('high' if score >= 6 else ('normal' if score >= 4 else 'low')),
            'score': score,
            'reason': motivation.get('description', '联赛')
        }

    def _assess_rotation_probability(
        self,
        motivation: Dict,
        match_importance: List[Dict],
        upcoming: List[Dict]
    ) -> Dict:
        """评估轮换概率"""
        rotation_risk = motivation.get('rotation_risk', 'low')

        # 检查是否有更重要的比赛在后面
        if len(match_importance) >= 2:
            next_match = match_importance[0]
            following_match = match_importance[1]

            # 下一场比本场更重要
            if following_match['importance_score'] > next_match['importance_score'] + 2:
                return {
                    'rotation_probability': 'high',
                    'reason': f'下一场({following_match["league"]})更重要，本场可能轮换',
                    'rotation_risk_level': rotation_risk,
                    'save_for_next': True,
                    'next_key_match': following_match
                }

        # 赛程密集度
        if len(upcoming) >= 3:
            dates = [m['match_date'] for m in upcoming[:3] if m.get('match_date')]
            if len(dates) >= 2:
                try:
                    d1 = datetime.strptime(dates[0], '%Y-%m-%d')
                    d2 = datetime.strptime(dates[1], '%Y-%m-%d')
                    if (d2 - d1).days <= 3:
                        return {
                            'rotation_probability': 'medium',
                            'reason': '赛程密集，可能部分轮换',
                            'rotation_risk_level': rotation_risk,
                            'save_for_next': False,
                            'schedule_congestion': True
                        }
                except (ValueError, TypeError):
                    pass

        prob_map = {
            'very_low': 'very_low',
            'low': 'low',
            'medium': 'medium',
            'high': 'high'
        }

        return {
            'rotation_probability': prob_map.get(rotation_risk, 'low'),
            'reason': motivation.get('description', ''),
            'rotation_risk_level': rotation_risk,
            'save_for_next': False,
            'schedule_congestion': False
        }

    def _determine_competition_type(
        self,
        home_standing: Dict,
        away_standing: Dict,
        rules: Dict
    ) -> str:
        """判定两队竞争关系类型"""
        h_pos = home_standing['position']
        a_pos = away_standing['position']

        cl_spots = rules.get('champions_league_spots', 4)
        el_spots = cl_spots + rules.get('europa_league_spots', 2)
        total_teams = rules.get('total_teams', 20)
        rel_start = rules.get('relegation_start') or (total_teams - rules.get('relegation_spots', 3) + 1)

        # 争冠对手
        if h_pos <= 2 and a_pos <= 3:
            return 'title_race'

        # 欧战竞争
        if h_pos <= el_spots + 2 and a_pos <= el_spots + 2:
            return 'european_race'

        # 保级对手
        if h_pos >= rel_start - 2 and a_pos >= rel_start - 2:
            return 'relegation_battle'

        # 中游对决
        if abs(h_pos - a_pos) <= 3:
            return 'mid_table_clash'

        return 'regular'

    def _simulate_match_outcomes(
        self,
        home_standing: Dict,
        away_standing: Dict,
        standings: List[Dict],
        rules: Dict
    ) -> Dict:
        """模拟比赛三种结果对排名的影响"""
        h_pts = home_standing['points']
        a_pts = away_standing['points']
        h_pos = home_standing['position']
        a_pos = away_standing['position']

        # 主胜
        home_win = {
            'home_points': h_pts + 3,
            'away_points': a_pts,
            'home_change': f'+3 ({h_pos}→可能上升)',
            'away_change': f'+0 ({a_pos}→可能下降)',
            'impact': '主队拉开差距' if h_pos < a_pos else '主队反超'
        }

        # 平局
        draw = {
            'home_points': h_pts + 1,
            'away_points': a_pts + 1,
            'home_change': f'+1',
            'away_change': f'+1',
            'impact': '维持现状，各取1分'
        }

        # 客胜
        away_win = {
            'home_points': h_pts,
            'away_points': a_pts + 3,
            'home_change': f'+0 ({h_pos}→可能下降)',
            'away_change': f'+3 ({a_pos}→可能上升)',
            'impact': '客队拉近差距' if a_pos > h_pos else '客队反超'
        }

        return {
            'home_win': home_win,
            'draw': draw,
            'away_win': away_win
        }

    def _get_competition_description(self, comp_type: str) -> str:
        descriptions = {
            'title_race': '争冠对手直接对话',
            'european_race': '欧战资格竞争',
            'relegation_battle': '保级对手直接对话',
            'mid_table_clash': '中游球队对决',
            'regular': '常规比赛'
        }
        return descriptions.get(comp_type, '常规比赛')

    def _rate_match_significance(
        self,
        is_six_pointer: bool,
        comp_type: str,
        home_standing: Dict,
        away_standing: Dict
    ) -> Dict:
        """评估比赛重要性"""
        if is_six_pointer:
            if comp_type == 'title_race':
                return {'level': 'season_defining', 'score': 10, 'description': '赛季决定性比赛'}
            elif comp_type == 'relegation_battle':
                return {'level': 'survival_decider', 'score': 9, 'description': '保级生死战'}
            else:
                return {'level': 'six_pointer', 'score': 8, 'description': '6分关键战'}

        if comp_type in ['title_race', 'european_race']:
            return {'level': 'important', 'score': 7, 'description': '重要比赛'}

        return {'level': 'normal', 'score': 5, 'description': '常规比赛'}

    def _project_realistic_points(self, current_pts: int, difficulty: Dict) -> int:
        """预测现实最高积分"""
        remaining = difficulty.get('total_remaining', 0)
        if remaining == 0:
            return current_pts

        # 根据赛程难度预估胜率
        diff_score = difficulty.get('difficulty_score', 5)
        if diff_score >= 6:
            win_rate = 0.3
        elif diff_score >= 4:
            win_rate = 0.5
        else:
            win_rate = 0.7

        expected_pts = remaining * win_rate * 3 + remaining * (1 - win_rate) * 0.5
        return round(current_pts + expected_pts)

    def _project_realistic_min(self, current_pts: int, difficulty: Dict) -> int:
        """预测现实最低积分"""
        remaining = difficulty.get('total_remaining', 0)
        if remaining == 0:
            return current_pts

        diff_score = difficulty.get('difficulty_score', 5)
        if diff_score >= 6:
            loss_rate = 0.6
        elif diff_score >= 4:
            loss_rate = 0.4
        else:
            loss_rate = 0.2

        expected_pts = remaining * (1 - loss_rate) * 1.0
        return round(current_pts + expected_pts)

    def _project_avg_points(
        self,
        current_pts: int,
        remaining: int,
        standings: List[Dict],
        team_id: int
    ) -> int:
        """基于历史场均积分预测"""
        for s in standings:
            if s['team_id'] == team_id:
                if s['played'] > 0:
                    ppg = s['points'] / s['played']
                    return round(current_pts + ppg * remaining)
        return current_pts

    def _calculate_catch_condition(
        self,
        gap: int,
        remaining: int,
        leader: Dict,
        chaser: Dict
    ) -> str:
        """计算追赶条件"""
        wins_needed = gap // 3 + (1 if gap % 3 else 0)
        if wins_needed <= remaining:
            return f'剩余{remaining}场需赢{wins_needed}场且领头羊最多得{remaining * 3 - gap - 1}分'
        return '理论无法追上'

    def _calculate_escape_condition(self, gap: int, remaining: int) -> str:
        """计算保级逃脱条件"""
        wins_needed = gap // 3 + (1 if gap % 3 else 0)
        if wins_needed <= remaining:
            return f'剩余{remaining}场需赢{wins_needed}场'
        return '理论无法保级'

    def _estimate_title_probability(self, gap: int, remaining: int) -> float:
        """估算夺冠概率（简化模型）"""
        if gap <= 0:
            return 50.0
        if remaining <= 0:
            return 0.0
        max_catch = remaining * 3
        if gap > max_catch:
            return 0.0
        prob = max(0, (1 - gap / max_catch) * 50)
        return round(prob, 1)

    def _estimate_survival_probability(self, gap: int, remaining: int) -> float:
        """估算保级概率"""
        if gap <= 0:
            return 80.0
        if remaining <= 0:
            return 0.0
        max_catch = remaining * 3
        if gap > max_catch:
            return 0.0
        prob = max(0, (1 - gap / max_catch) * 70)
        return round(prob, 1)

    def _assess_race_intensity(self, teams: List[Dict]) -> str:
        """评估争冠激烈程度"""
        if len(teams) < 2:
            return 'no_race'
        gap = teams[0].get('gap_to_leader', 0)
        if gap <= 3:
            return 'white_hot'
        elif gap <= 6:
            return 'intense'
        elif gap <= 9:
            return 'moderate'
        else:
            return 'one_horse'

    def _assess_relegation_intensity(self, teams: List[Dict]) -> str:
        """评估保级激烈程度"""
        in_zone = [t for t in teams if t.get('in_relegation_zone')]
        near_zone = [t for t in teams if not t.get('in_relegation_zone') and t.get('gap_to_safety', 99) <= 6]

        total_involved = len(in_zone) + len(near_zone)
        if total_involved >= 5:
            return 'white_hot'
        elif total_involved >= 3:
            return 'intense'
        elif total_involved >= 1:
            return 'moderate'
        else:
            return 'settled'
