"""
详细分析报告增强模块

为体彩分析报告添加:
1. 近期战绩详情 (6场/10场/20场)
2. 历史交锋详情
3. 进球时间分布
4. 球员进球统计
5. Elo实力对比
"""

from typing import Dict, List, Any, Optional
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DetailedReportEnhancer:
    """详细报告增强器"""

    def __init__(self, db_conn: sqlite3.Connection):
        self.conn = db_conn
        self.conn.row_factory = sqlite3.Row

    def enhance_report(self, report: Dict, match_info: Dict) -> Dict:
        """增强分析报告"""

        home_team_id = match_info.get('home_team_id')
        away_team_id = match_info.get('away_team_id')
        match_date = match_info.get('match_date')

        if not home_team_id or not away_team_id:
            return report

        # 添加详细数据
        report['detailed_analysis'] = {
            'recent_matches': {
                'home': self._get_recent_matches(home_team_id, match_date, [6, 10, 20]),
                'away': self._get_recent_matches(away_team_id, match_date, [6, 10, 20])
            },
            'h2h_detail': self._get_h2h_detail(home_team_id, away_team_id, match_date),
            'team_stats': {
                'home': self._get_team_statistics(home_team_id, match_date),
                'away': self._get_team_statistics(away_team_id, match_date)
            },
            'elo_comparison': self._get_elo_comparison(home_team_id, away_team_id),
            'league_standing': {
                'home': self._get_league_standing(home_team_id),
                'away': self._get_league_standing(away_team_id)
            },
            'fitness': {
                'home': self._get_team_fitness(home_team_id, match_date),
                'away': self._get_team_fitness(away_team_id, match_date)
            },
            'scorers': {
                'home': self._get_team_scorers(home_team_id, match_date),
                'away': self._get_team_scorers(away_team_id, match_date)
            },
            'goal_timing': {
                'home': self._get_goal_timing_distribution(home_team_id, match_date),
                'away': self._get_goal_timing_distribution(away_team_id, match_date)
            }
        }

        # 添加分析总结
        report['analysis_summary'] = self._generate_analysis_summary(report['detailed_analysis'])

        return report

    def _get_recent_matches(self, team_id: int, match_date: str, limits: List[int]) -> Dict:
        """获取近期战绩详情"""

        cursor = self.conn.cursor()

        def get_matches(limit: int) -> List[Dict]:
            cursor.execute("""
                SELECT
                    match_id,
                    match_date,
                    home_team_id,
                    away_team_id,
                    home_goals,
                    away_goals,
                    (SELECT name_en FROM teams WHERE team_id = m.home_team_id) as home_team_name,
                    (SELECT name_cn FROM teams WHERE team_id = m.home_team_id) as home_team_cn,
                    (SELECT name_en FROM teams WHERE team_id = m.away_team_id) as away_team_name,
                    (SELECT name_cn FROM teams WHERE team_id = m.away_team_id) as away_team_cn,
                    CASE
                        WHEN home_goals IS NULL OR away_goals IS NULL THEN '未知'
                        WHEN home_goals > away_goals THEN '主胜'
                        WHEN home_goals < away_goals THEN '客胜'
                        ELSE '平局'
                    END as result,
                    home_goals - away_goals as goal_diff
                FROM matches m
                WHERE (home_team_id = ? OR away_team_id = ?)
                  AND status = 'finished'
                  AND match_date < ?
                  AND (home_goals IS NOT NULL AND away_goals IS NOT NULL)
                  AND (home_goals > 0 OR away_goals > 0)
                ORDER BY match_date DESC
                LIMIT ?
            """, (team_id, team_id, match_date, limit))

            matches = []
            for row in cursor.fetchall():
                is_home = row['home_team_id'] == team_id
                team_goals = row['home_goals'] if is_home else row['away_goals']
                opponent_goals = row['away_goals'] if is_home else row['home_goals']

                # 计算比赛结果（从该队角度）
                if team_goals > opponent_goals:
                    team_result = '胜'
                elif team_goals < opponent_goals:
                    team_result = '负'
                else:
                    team_result = '平'

                opponent_name_en = row['away_team_name'] if is_home else row['home_team_name']
                opponent_name_cn = row.get('away_team_cn') if is_home else row.get('home_team_cn')
                opponent_name = opponent_name_cn or opponent_name_en

                matches.append({
                    'match_date': row['match_date'],
                    'is_home': is_home,
                    'opponent': opponent_name,
                    'team_goals': team_goals,
                    'opponent_goals': opponent_goals,
                    'result': team_result,
                    'venue': '主场' if is_home else '客场'
                })

            return matches

        # 获取各期限数据
        result = {}
        for limit in limits:
            matches = get_matches(limit)
            if matches:
                wins = sum(1 for m in matches if m['result'] == '胜')
                draws = sum(1 for m in matches if m['result'] == '平')
                losses = sum(1 for m in matches if m['result'] == '负')
                gf = sum(m['team_goals'] or 0 for m in matches)
                ga = sum(m['opponent_goals'] or 0 for m in matches)

                result[f'{limit}_matches'] = {
                    'matches': matches,
                    'summary': {
                        'wins': wins,
                        'draws': draws,
                        'losses': losses,
                        'goals_for': gf,
                        'goals_against': ga,
                        'goal_difference': gf - ga,
                        'win_rate': wins / len(matches) if matches else 0,
                        'points': wins * 3 + draws  # 积分
                    },
                    'form_string': ''.join(['W' if m['result'] == '胜' else ('D' if m['result'] == '平' else 'L') for m in matches[:5]])
                }
            else:
                result[f'{limit}_matches'] = {
                    'matches': [],
                    'summary': {'wins': 0, 'draws': 0, 'losses': 0, 'goals_for': 0, 'goals_against': 0},
                    'form_string': ''
                }

        return result

    def _get_h2h_detail(self, home_team_id: int, away_team_id: int, match_date: str) -> Dict:
        """获取历史交锋详情"""

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                match_id,
                match_date,
                home_team_id,
                away_team_id,
                home_goals,
                away_goals,
                (SELECT name_en FROM teams WHERE team_id = m.home_team_id) as home_team_name,
                (SELECT name_en FROM teams WHERE team_id = m.away_team_id) as away_team_name
            FROM matches m
            WHERE ((home_team_id = ? AND away_team_id = ?)
                OR (home_team_id = ? AND away_team_id = ?))
              AND status = 'finished'
              AND match_date < ?
              AND home_goals IS NOT NULL
              AND away_goals IS NOT NULL
            ORDER BY match_date DESC
            LIMIT 10
        """, (home_team_id, away_team_id, away_team_id, home_team_id, match_date))

        matches = []
        home_wins = 0
        draws = 0
        away_wins = 0

        for row in cursor.fetchall():
            # 计算结果（从home_team_id角度）
            if row['home_team_id'] == home_team_id:
                # 主队是第一队
                if row['home_goals'] > row['away_goals']:
                    result = '主胜'
                    home_wins += 1
                elif row['home_goals'] < row['away_goals']:
                    result = '客胜'
                    away_wins += 1
                else:
                    result = '平局'
                    draws += 1
            else:
                # 主队是第二队（即away_team_id），反转结果
                if row['home_goals'] > row['away_goals']:
                    result = '客胜'
                    away_wins += 1
                elif row['home_goals'] < row['away_goals']:
                    result = '主胜'
                    home_wins += 1
                else:
                    result = '平局'
                    draws += 1

            matches.append({
                'match_date': row['match_date'],
                'home_team': row.get('home_team_cn') or row['home_team_name'],
                'away_team': row.get('away_team_cn') or row['away_team_name'],
                'score': f"{row['home_goals']}-{row['away_goals']}",
                'result': result
            })

        total = home_wins + draws + away_wins

        return {
            'matches': matches,
            'summary': {
                'total': total,
                'home_wins': home_wins,
                'draws': draws,
                'away_wins': away_wins,
                'home_win_rate': home_wins / total if total > 0 else 0,
                'draw_rate': draws / total if total > 0 else 0,
                'away_win_rate': away_wins / total if total > 0 else 0
            }
        }

    def _get_team_statistics(self, team_id: int, match_date: str) -> Dict:
        """获取球队统计数据"""

        cursor = self.conn.cursor()

        # 获取最近20场有效比赛的统计
        cursor.execute("""
            SELECT
                AVG(CASE WHEN home_team_id = ? THEN home_goals ELSE away_goals END) as avg_goals_for,
                AVG(CASE WHEN home_team_id = ? THEN away_goals ELSE home_goals END) as avg_goals_against,
                SUM(CASE WHEN home_team_id = ? THEN home_goals ELSE away_goals END) as total_goals_for,
                SUM(CASE WHEN home_team_id = ? THEN away_goals ELSE home_goals END) as total_goals_against,
                COUNT(*) as total_matches,
                SUM(CASE WHEN
                    (home_team_id = ? AND home_goals > away_goals) OR
                    (away_team_id = ? AND away_goals > home_goals)
                THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND status = 'finished'
              AND match_date < ?
              AND home_goals IS NOT NULL
              AND away_goals IS NOT NULL
              AND (home_goals > 0 OR away_goals > 0)
            ORDER BY match_date DESC
            LIMIT 20
        """, (team_id, team_id, team_id, team_id, team_id, team_id, team_id, team_id, match_date))

        row = cursor.fetchone()

        if row and row['total_matches'] > 0:
            return {
                'avg_goals_for': row['avg_goals_for'] or 1.0,
                'avg_goals_against': row['avg_goals_against'] or 1.0,
                'total_matches': row['total_matches'],
                'wins': row['wins'] or 0,
                'draws': row['draws'] or 0,
                'losses': row['total_matches'] - (row['wins'] or 0) - (row['draws'] or 0),
                'attack_strength': row['avg_goals_for'] / 1.35 if row['avg_goals_for'] else 1.0,  # 相对联赛平均
                'defense_strength': 1.35 / row['avg_goals_against'] if row['avg_goals_against'] else 1.0
            }

        return {
            'avg_goals_for': 1.0,
            'avg_goals_against': 1.0,
            'total_matches': 0,
            'attack_strength': 1.0,
            'defense_strength': 1.0
        }

    def _get_league_standing(self, team_id: int) -> Dict:
        """获取联赛积分排名"""

        cursor = self.conn.cursor()

        # 获取球队在积分榜中的位置
        cursor.execute("""
            SELECT
                s.position,
                s.played,
                s.won,
                s.drawn,
                s.lost,
                s.goals_for,
                s.goals_against,
                s.goal_diff,
                s.points,
                s.form,
                s.home_played,
                s.home_won,
                s.home_drawn,
                s.home_lost,
                s.home_points,
                s.away_played,
                s.away_won,
                s.away_drawn,
                s.away_lost,
                s.away_points,
                l.name_en as league_name,
                l.name_cn as league_name_cn,
                (SELECT COUNT(*) FROM standings WHERE league_id = s.league_id AND season_id = s.season_id) as total_teams
            FROM standings s
            JOIN leagues l ON s.league_id = l.league_id
            WHERE s.team_id = ?
              AND s.standing_type = 'total'
            ORDER BY s.updated_at DESC
            LIMIT 1
        """, (team_id,))

        row = cursor.fetchone()

        if row and row['points']:
            total_teams = row['total_teams'] or 18

            # 如果position为空，根据points计算排名
            if row['position'] is None:
                cursor.execute("""
                    SELECT COUNT(*) + 1 FROM standings
                    WHERE league_id = (SELECT league_id FROM standings WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1)
                      AND season_id = (SELECT season_id FROM standings WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1)
                      AND standing_type = 'total'
                      AND points > ?
                """, (team_id, team_id, row['points']))
                position = cursor.fetchone()[0] or 1
            else:
                position = row['position']

            # 计算联赛影响
            position_factor = 1 - (position - 1) / total_teams  # 排名越高，因子越大

            return {
                'position': position,
                'total_teams': total_teams,
                'played': row['played'],
                'won': row['won'],
                'drawn': row['drawn'],
                'lost': row['lost'],
                'goals_for': row['goals_for'],
                'goals_against': row['goals_against'],
                'goal_diff': row['goal_diff'],
                'points': row['points'],
                'form': row['form'],
                'league_name': row.get('league_name_cn') or row['league_name'],
                'home_record': {
                    'played': row['home_played'],
                    'won': row['home_won'],
                    'drawn': row['home_drawn'],
                    'lost': row['home_lost'],
                    'points': row['home_points']
                },
                'away_record': {
                    'played': row['away_played'],
                    'won': row['away_won'],
                    'drawn': row['away_drawn'],
                    'lost': row['away_lost'],
                    'points': row['away_points']
                },
                'position_factor': position_factor,
                'description': f"联赛第{position}名，{row['points']}分"
            }

        return {
            'position': None,
            'has_data': False,
            'description': '暂无联赛排名数据'
        }

    def _get_team_fitness(self, team_id: int, match_date: str) -> Dict:
        """获取球队体能状况（休息天数、赛程密度）"""

        cursor = self.conn.cursor()

        # 获取最近30天的比赛数量
        cursor.execute("""
            SELECT
                COUNT(*) as match_count,
                MIN(match_date) as first_match,
                MAX(match_date) as last_match
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND status = 'finished'
              AND match_date >= date(?, '-30 days')
              AND match_date < ?
        """, (team_id, team_id, match_date, match_date))

        row = cursor.fetchone()

        # 获取最近一场比赛的日期
        cursor.execute("""
            SELECT match_date
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND status = 'finished'
              AND match_date < ?
            ORDER BY match_date DESC
            LIMIT 1
        """, (team_id, team_id, match_date))

        last_match = cursor.fetchone()

        # 计算休息天数
        rest_days = 7  # 默认7天
        if last_match:
            from datetime import datetime
            try:
                last_date = datetime.strptime(last_match['match_date'], '%Y-%m-%d')
                current_date = datetime.strptime(match_date, '%Y-%m-%d')
                rest_days = (current_date - last_date).days
            except:
                pass

        match_count_30d = row['match_count'] if row else 0

        # 体能评估
        if match_count_30d > 8:
            fatigue_level = 'high'
            fatigue_desc = '赛程密集，体能堪忧'
        elif match_count_30d > 6:
            fatigue_level = 'medium'
            fatigue_desc = '赛程较密，需注意体能'
        else:
            fatigue_level = 'low'
            fatigue_desc = '赛程适中，体能充沛'

        if rest_days < 3:
            rest_desc = f'休息仅{rest_days}天，疲劳度高'
            fatigue_level = 'high'
        elif rest_days < 5:
            rest_desc = f'休息{rest_days}天，恢复一般'
        else:
            rest_desc = f'休息{rest_days}天，恢复充分'

        return {
            'matches_30_days': match_count_30d,
            'rest_days': rest_days,
            'fatigue_level': fatigue_level,
            'fatigue_description': fatigue_desc,
            'rest_description': rest_desc,
            'has_data': match_count_30d > 0
        }

    def _get_elo_comparison(self, home_team_id: int, away_team_id: int) -> Dict:
        """获取Elo实力对比"""

        cursor = self.conn.cursor()

        def get_elo(team_id: int) -> int:
            cursor.execute("""
                SELECT elo_rating FROM team_elo_ratings
                WHERE team_id = ?
                ORDER BY updated_at DESC LIMIT 1
            """, (team_id,))
            row = cursor.fetchone()
            return row['elo_rating'] if row else 1500

        home_elo = get_elo(home_team_id)
        away_elo = get_elo(away_team_id)

        # 计算期望胜率
        home_elo_adj = home_elo + 100  # 主场优势
        diff = home_elo_adj - away_elo

        # Elo期望得分
        expected_home = 1 / (1 + 10 ** (-diff / 400))

        return {
            'home_elo': home_elo,
            'away_elo': away_elo,
            'home_elo_adjusted': home_elo_adj,
            'elo_difference': diff,
            'expected_home_win_rate': expected_home,
            'level_description': self._get_elo_level_description(home_elo, away_elo)
        }

    def _get_elo_level_description(self, home_elo: int, away_elo: int) -> str:
        """获取Elo等级描述"""
        diff = home_elo - away_elo

        if diff > 200:
            return '主队明显强于客队'
        elif diff > 100:
            return '主队略强于客队'
        elif diff > 50:
            return '两队实力接近，主队稍占优势'
        elif diff > -50:
            return '两队实力相当'
        elif diff > -100:
            return '两队实力接近，客队稍占优势'
        elif diff > -200:
            return '客队略强于主队'
        else:
            return '客队明显强于主队'

    def _get_team_scorers(self, team_id: int, match_date: str) -> List[Dict]:
        """获取球队进球球员统计"""

        cursor = self.conn.cursor()

        # 获取球队名称
        cursor.execute("SELECT name_en, name_cn FROM teams WHERE team_id = ?", (team_id,))
        team_row = cursor.fetchone()
        if not team_row:
            return []

        team_name_en = team_row['name_en']
        team_name_cn = team_row['name_cn'] or team_name_en

        # 尝试通过球队名称匹配球员数据
        # player_match_stats中team_name存储的是"home"或"away"，需要关联matches表获取真实球队名
        # 使用球队名称进行模糊匹配
        try:
            cursor.execute("""
                SELECT
                    pms.player_name,
                    SUM(pms.goals) as total_goals,
                    COUNT(*) as matches_played,
                    SUM(pms.assists) as total_assists
                FROM player_match_stats pms
                JOIN matches m ON (
                    (pms.team_name = 'home' AND m.home_team_id = ?)
                    OR (pms.team_name = 'away' AND m.away_team_id = ?)
                )
                WHERE m.status = 'finished'
                  AND m.match_date < ?
                  AND pms.goals > 0
                GROUP BY pms.player_name
                ORDER BY total_goals DESC
                LIMIT 5
            """, (team_id, team_id, match_date))

            scorers = []
            for row in cursor.fetchall():
                if row['total_goals'] > 0:
                    scorers.append({
                        'player_name': row['player_name'],
                        'goals': row['total_goals'],
                        'matches': row['matches_played'],
                        'assists': row['total_assists'],
                        'goals_per_match': row['total_goals'] / row['matches_played'] if row['matches_played'] > 0 else 0
                    })

            return scorers
        except:
            return []

    def _get_goal_timing_distribution(self, team_id: int, match_date: str) -> Dict:
        """获取进球时间分布"""

        cursor = self.conn.cursor()

        # 初始化时间段
        timing = {
            '0-15': 0,
            '15-30': 0,
            '30-45': 0,
            '45-60': 0,
            '60-75': 0,
            '75-90': 0,
            'total_goals': 0,
            'has_data': False
        }

        try:
            import json

            # 获取该队比赛的进球数据
            cursor.execute("""
                SELECT md.goalscorer_json, m.home_team_id, m.away_team_id
                FROM match_details md
                JOIN matches m ON md.match_id = m.match_id
                WHERE (m.home_team_id = ? OR m.away_team_id = ?)
                  AND m.status = 'finished'
                  AND m.match_date < ?
                  AND md.goalscorer_json IS NOT NULL
                  AND md.goalscorer_json != ''
                ORDER BY m.match_date DESC
                LIMIT 20
            """, (team_id, team_id, match_date))

            for row in cursor.fetchall():
                try:
                    goalscorer = json.loads(row['goalscorer_json'])
                    if not isinstance(goalscorer, list):
                        continue

                    for goal in goalscorer:
                        # 判断进球是否属于该队
                        is_home_team = row['home_team_id'] == team_id
                        is_team_goal = (is_home_team and goal.get('home_scorer')) or \
                                       (not is_home_team and goal.get('away_scorer'))

                        if not is_team_goal:
                            continue

                        # 解析进球时间
                        time_str = goal.get('time', '0')
                        try:
                            # 处理补时时间 (如 "45+2", "90+3")
                            if '+' in str(time_str):
                                base_time = int(str(time_str).split('+')[0])
                            else:
                                base_time = int(float(time_str))

                            # 分类到时间段
                            if base_time <= 15:
                                timing['0-15'] += 1
                            elif base_time <= 30:
                                timing['15-30'] += 1
                            elif base_time <= 45:
                                timing['30-45'] += 1
                            elif base_time <= 60:
                                timing['45-60'] += 1
                            elif base_time <= 75:
                                timing['60-75'] += 1
                            else:
                                timing['75-90'] += 1

                            timing['total_goals'] += 1
                            timing['has_data'] = True
                        except (ValueError, TypeError):
                            continue

                except (json.JSONDecodeError, TypeError):
                    continue

            # 计算百分比
            if timing['total_goals'] > 0:
                timing['percentages'] = {
                    k: round(v / timing['total_goals'] * 100, 1)
                    for k, v in timing.items()
                    if k.endswith(('15', '30', '45', '60', '75', '90'))
                }
            else:
                timing['percentages'] = {}

        except Exception as e:
            logger.warning(f"Error getting goal timing: {e}")

        return timing

    def _generate_analysis_summary(self, detailed_analysis: Dict) -> Dict:
        """生成分析总结"""

        # 近期状态对比
        home_recent = detailed_analysis['recent_matches']['home']
        away_recent = detailed_analysis['recent_matches']['away']

        # 使用10场数据作为基准
        home_10 = home_recent.get('10_matches', {}).get('summary', {})
        away_10 = away_recent.get('10_matches', {}).get('summary', {})

        # 状态对比
        form_comparison = {
            'home_form': home_recent.get('10_matches', {}).get('form_string', ''),
            'away_form': away_recent.get('10_matches', {}).get('form_string', ''),
            'home_points_rate': home_10.get('points', 0) / (home_10.get('wins', 0) + home_10.get('draws', 0) + home_10.get('losses', 0) or 1) * 3,
            'away_points_rate': away_10.get('points', 0) / (away_10.get('wins', 0) + away_10.get('draws', 0) + away_10.get('losses', 0) or 1) * 3,
            'home_attack': home_10.get('goals_for', 0) / (home_10.get('wins', 0) + home_10.get('draws', 0) + home_10.get('losses', 0) or 1),
            'away_attack': away_10.get('goals_for', 0) / (away_10.get('wins', 0) + away_10.get('draws', 0) + away_10.get('losses', 0) or 1)
        }

        # 历史交锋趋势
        h2h = detailed_analysis['h2h_detail']
        h2h_trend = {
            'dominant_team': 'home' if h2h['summary']['home_win_rate'] > 0.5 else ('away' if h2h['summary']['away_win_rate'] > 0.5 else 'balanced'),
            'recent_trend': h2h['matches'][0]['result'] if h2h['matches'] else '无交锋记录'
        }

        # Elo分析
        elo = detailed_analysis['elo_comparison']

        return {
            'form_comparison': form_comparison,
            'h2h_trend': h2h_trend,
            'elo_analysis': elo,
            'overall_assessment': self._generate_overall_assessment(form_comparison, h2h_trend, elo)
        }

    def _generate_overall_assessment(self, form_comparison: Dict, h2h_trend: Dict, elo: Dict) -> str:
        """生成整体评估描述"""

        lines = []

        # Elo评估
        lines.append(elo['level_description'])

        # 近期状态评估
        home_form = form_comparison['home_form']
        away_form = form_comparison['away_form']

        if home_form and away_form:
            if 'W' in home_form[:3] and 'L' not in home_form[:3]:
                lines.append('主队近期状态良好')
            elif 'L' in home_form[:3] and 'W' not in home_form[:3]:
                lines.append('主队近期状态不佳')

            if 'W' in away_form[:3] and 'L' not in away_form[:3]:
                lines.append('客队近期状态良好')
            elif 'L' in away_form[:3] and 'W' not in away_form[:3]:
                lines.append('客队近期状态不佳')

        # 交锋评估
        if h2h_trend['dominant_team'] == 'home':
            lines.append('历史交锋主队占优')
        elif h2h_trend['dominant_team'] == 'away':
            lines.append('历史交锋客队占优')

        return '；'.join(lines) if lines else '两队数据有限，建议谨慎参考'