"""
关键赛事因素分析器 (Key Match Factors Analyzer)

分析因素:
1. 赛事重要性 - 是否是最后一轮、涉及淘汰、降级、资格赛
2. 球员动态 - 球员转会、退役、告别赛
3. 教练动态 - 教练更换、离职
4. 新闻资讯 - 相关新闻、舆论热点
5. 历史恩怨 - 两队历史交锋故事
6. 里程碑事件 - 球队/球员即将达成的里程碑
"""

from typing import Dict, Any, Optional
import sqlite3
import logging
from datetime import datetime

from ..base import (
    FeatureExtractor, ExtractionContext, ExtractionResult,
    FeatureCategory
)
from ...schemas.lottery import PlayType

logger = logging.getLogger(__name__)


class KeyMatchFactorsAnalyzer(FeatureExtractor):
    """
    关键赛事因素分析器

    分析比赛的特殊背景和重要性
    """

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight = 0.08  # 关键因素权重

    @property
    def name(self) -> str:
        return "key_match_factors_analyzer"

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.CONTEXT

    @property
    def play_type(self) -> PlayType:
        return PlayType.SPF

    def get_required_data(self) -> list:
        return ['home_team_id', 'away_team_id', 'match_date', 'league_id']

    def initialize(self):
        pass

    def validate_context(self, context: ExtractionContext) -> bool:
        return context.home_team_id is not None and context.away_team_id is not None

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """执行关键因素分析"""

        cursor = context.db_conn.cursor()

        # 1. 分析赛事重要性
        match_importance = self._analyze_match_importance(cursor, context)

        # 2. 分析球员动态
        player_factors = self._analyze_player_factors(cursor, context)

        # 3. 分析教练动态
        coach_factors = self._analyze_coach_factors(cursor, context)

        # 4. 分析新闻资讯
        news_factors = self._analyze_news_factors(cursor, context)

        # 5. 分析历史恩怨
        rivalry_factors = self._analyze_rivalry(cursor, context)

        # 6. 分析里程碑
        milestone_factors = self._analyze_milestones(cursor, context)

        # 综合影响
        overall_impact = self._calculate_overall_impact(
            match_importance, player_factors, coach_factors,
            news_factors, rivalry_factors, milestone_factors
        )

        # 生成描述
        description = self._generate_description(
            match_importance, player_factors, coach_factors,
            news_factors, rivalry_factors, milestone_factors
        )

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=overall_impact['value'],
            raw_data={
                'match_importance': match_importance,
                'player_factors': player_factors,
                'coach_factors': coach_factors,
                'news_factors': news_factors,
                'rivalry_factors': rivalry_factors,
                'milestone_factors': milestone_factors,
                'summary': overall_impact['summary']
            },
            confidence=overall_impact['confidence'],
            impact_direction=overall_impact['direction'],
            description=description
        )

    def _analyze_match_importance(self, cursor, context: ExtractionContext) -> Dict:
        """分析赛事重要性"""

        result = {
            'is_last_match': False,
            'involves_relegation': False,
            'involves_qualification': False,
            'involves_knockout': False,
            'involves_title_race': False,
            'champion_decided': False,
            'champion_team': None,
            'league_position_context': {},
            'description': ''
        }

        # 获取联赛积分榜信息
        try:
            # 先获取两队所在的league_id
            cursor.execute("""
                SELECT DISTINCT s.league_id
                FROM standings s
                WHERE s.team_id IN (?, ?)
                  AND s.season_id LIKE '2025%'
            """, (context.home_team_id, context.away_team_id))

            league_row = cursor.fetchone()
            league_id = league_row['league_id'] if league_row else None

            if not league_id:
                # 如果找不到league_id，尝试获取主队的league_id
                cursor.execute("""
                    SELECT league_id FROM standings
                    WHERE team_id = ? AND season_id LIKE '2025%'
                    LIMIT 1
                """, (context.home_team_id,))
                row = cursor.fetchone()
                if row:
                    league_id = row['league_id']

            # 直接查询两队的积分榜数据
            cursor.execute("""
                SELECT s.team_id, s.position, s.points, s.played,
                       s.won, s.drawn, s.lost, s.goals_for, s.goals_against, s.goal_diff,
                       t.name_cn
                FROM standings s
                LEFT JOIN teams t ON s.team_id = t.team_id
                WHERE s.team_id IN (?, ?)
                  AND s.season_id LIKE '2025%'
            """, (context.home_team_id, context.away_team_id))

            team_standings = {}
            for row in cursor.fetchall():
                team_standings[row['team_id']] = {
                    'position': row['position'],
                    'points': row['points'],
                    'played': row['played'],
                    'won': row['won'],
                    'drawn': row['drawn'],
                    'lost': row['lost'],
                    'goals_for': row['goals_for'],
                    'goals_against': row['goals_against'],
                    'goal_diff': row['goal_diff'],
                    'name': row['name_cn']
                }

            # 如果找到了数据，进行分析
            if team_standings:
                home_data = team_standings.get(context.home_team_id, {})
                away_data = team_standings.get(context.away_team_id, {})

                home_pos = home_data.get('position', 0)
                home_points = home_data.get('points', 0)
                home_played = home_data.get('played', 0)
                away_pos = away_data.get('position', 0)
                away_points = away_data.get('points', 0)
                away_played = away_data.get('played', 0)

                result['league_position_context'] = {
                    'home_position': home_pos,
                    'home_points': home_points,
                    'away_position': away_pos,
                    'away_points': away_points
                }

                # 获取该联赛的完整积分榜
                if league_id:
                    cursor.execute("""
                        SELECT s.team_id, s.position, s.points, s.played, t.name_cn
                        FROM standings s
                        LEFT JOIN teams t ON s.team_id = t.team_id
                        WHERE s.league_id = ? AND s.season_id LIKE '2025%'
                        ORDER BY s.position
                    """, (league_id,))
                else:
                    # 如果没有league_id，按积分排序取前20
                    cursor.execute("""
                        SELECT s.team_id, s.position, s.points, s.played, t.name_cn
                        FROM standings s
                        LEFT JOIN teams t ON s.team_id = t.team_id
                        WHERE s.season_id LIKE '2025%'
                        ORDER BY s.points DESC
                        LIMIT 20
                    """)

                all_standings = cursor.fetchall()
                total_teams = len(all_standings)

                if all_standings and home_pos > 0:
                    # 获取领头羊信息
                    leader = all_standings[0]
                    leader_points = leader['points']
                    leader_played = leader['played']
                    leader_team = leader['name_cn']
                    leader_team_id = leader['team_id']

                    result['league_position_context']['leader_points'] = leader_points
                    result['league_position_context']['leader_team'] = leader_team

                    # 计算联赛总轮次（双循环）
                    total_rounds = (total_teams - 1) * 2 if total_teams >= 10 else 38

                    # 判断冠军是否已定
                    if len(all_standings) >= 2:
                        first = all_standings[0]
                        second = all_standings[1]

                        first_points = first['points']
                        second_points = second['points']
                        second_played = second['played']
                        second_remaining = total_rounds - second_played
                        second_possible_max = second_points + second_remaining * 3

                        # 如果第一名积分 > 第二名最大可能积分，则冠军已定
                        if first_points > second_possible_max:
                            result['champion_decided'] = True
                            result['champion_team'] = first['name_cn']
                            result['description'] += f'冠军已定({first["name_cn"]}); '
                        else:
                            # 冠军未定，判断是否涉及冠军争夺
                            home_remaining = total_rounds - home_played
                            away_remaining = total_rounds - away_played

                            # 检查是否还能追上领头羊
                            home_max = home_points + home_remaining * 3
                            away_max = away_points + away_remaining * 3

                            # 只有两队中有一队是领头羊或还能追上领头羊时，才是冠军争夺
                            if leader_team_id in (context.home_team_id, context.away_team_id):
                                # 这场比赛有领头羊参与
                                other_team = context.away_team_id if leader_team_id == context.home_team_id else context.home_team_id
                                other_data = team_standings.get(other_team, {})
                                other_points = other_data.get('points', 0)
                                other_remaining = total_rounds - other_data.get('played', total_rounds)
                                other_max = other_points + other_remaining * 3

                                if other_max >= leader_points - 3:  # 3分差距内算争冠
                                    result['involves_title_race'] = True
                                    result['description'] += '涉及冠军争夺; '
                            elif home_max >= leader_points or away_max >= leader_points:
                                # 两队都还有机会追赶
                                result['involves_title_race'] = True
                                result['description'] += '涉及冠军争夺; '

                    # 判断是否涉及降级
                    # 降级区通常是倒数3名（18队以上联赛）
                    relegation_line = total_teams - 2 if total_teams >= 18 else total_teams - 1

                    if home_pos >= relegation_line or away_pos >= relegation_line:
                        result['involves_relegation'] = True
                        result['description'] += '涉及降级争夺; '

                    # 判断是否涉及欧战资格
                    # 欧战资格通常是前4名
                    qualification_zone = 4 if total_teams >= 18 else 2

                    # 只有两队排名在资格区附近才有争夺
                    home_near_qual = 1 <= home_pos <= qualification_zone + 2
                    away_near_qual = 1 <= away_pos <= qualification_zone + 2

                    if home_near_qual or away_near_qual:
                        result['involves_qualification'] = True
                        result['description'] += '涉及欧战资格; '

            # 检查是否是赛季最后一轮（通过比赛日期判断）
            if context.match_date:
                match_month = str(context.match_date)[5:7]
                if match_month in ['05', '06']:
                    result['is_last_match'] = True
                    result['description'] += '赛季关键轮次; '

        except Exception as e:
            logger.debug(f"Match importance analysis error: {e}")

        return result

    def _analyze_player_factors(self, cursor, context: ExtractionContext) -> Dict:
        """分析球员动态 - 转会、退役、告别赛"""

        result = {
            'transfers_out': [],
            'retiring_players': [],
            'farewell_match': False,
            'key_injuries': [],
            'description': ''
        }

        try:
            # 查询即将转会的球员
            cursor.execute("""
                SELECT player_name, transfer_type, destination, transfer_date
                FROM transfers
                WHERE team_id IN (?, ?)
                  AND transfer_date >= ?
                  AND transfer_type IN ('out', 'loan_out')
                ORDER BY transfer_date
            """, (context.home_team_id, context.away_team_id, context.match_date))

            for row in cursor.fetchall():
                result['transfers_out'].append({
                    'player': row[0],
                    'type': row[1],
                    'destination': row[2],
                    'date': row[3]
                })
                result['description'] += f'{row[0]}即将离队; '

            # 查询退役球员（如果有退役标记）
            cursor.execute("""
                SELECT player_name, status_type, notes
                FROM player_status
                WHERE team_id IN (?, ?)
                  AND status_type = 'retiring'
                  AND effective_date >= ?
            """, (context.home_team_id, context.away_team_id, context.match_date))

            for row in cursor.fetchall():
                result['retiring_players'].append({
                    'player': row[0],
                    'notes': row[2]
                })
                result['farewell_match'] = True
                result['description'] += f'{row[0]}告别赛; '

            # 查询关键伤停
            cursor.execute("""
                SELECT player_name, injury_type, expected_return
                FROM player_status
                WHERE team_id IN (?, ?)
                  AND status_type = 'injured'
                  AND expected_return > ?
            """, (context.home_team_id, context.away_team_id, context.match_date))

            for row in cursor.fetchall():
                result['key_injuries'].append({
                    'player': row[0],
                    'injury': row[1],
                    'return_date': row[2]
                })

        except Exception as e:
            logger.debug(f"Player factors analysis error: {e}")

        # 如果没有实际数据，提供模拟分析
        if not result['transfers_out'] and not result['retiring_players']:
            # 根据赛季末期特点推测
            result['description'] = '赛季末期，部分球员可能有转会动向'

        return result

    def _analyze_coach_factors(self, cursor, context: ExtractionContext) -> Dict:
        """分析教练动态"""

        result = {
            'recent_change': False,
            'coach_status': {},
            'description': ''
        }

        try:
            # 查询近期教练更换
            cursor.execute("""
                SELECT team_id, old_coach, new_coach, change_type, change_date
                FROM coach_changes
                WHERE team_id IN (?, ?)
                  AND change_date >= date(?, '-30 days')
                ORDER BY change_date DESC
            """, (context.home_team_id, context.away_team_id, context.match_date))

            for row in cursor.fetchall():
                result['recent_change'] = True
                result['coach_status'][row[0]] = {
                    'old_coach': row[1],
                    'new_coach': row[2],
                    'change_type': row[3],
                    'date': row[4]
                }
                result['description'] += f'教练更换: {row[2]}上任; '

        except Exception as e:
            logger.debug(f"Coach factors analysis error: {e}")

        return result

    def _analyze_news_factors(self, cursor, context: ExtractionContext) -> Dict:
        """分析新闻资讯"""

        result = {
            'recent_news': [],
            'positive_news': [],
            'negative_news': [],
            'hot_topics': [],
            'description': ''
        }

        try:
            # 查询相关新闻（使用实际的team_news表）
            cursor.execute("""
                SELECT title, news_type, impact_type, source, news_date, content
                FROM team_news
                WHERE team_id IN (?, ?)
                  AND news_date >= date(?, '-7 days')
                ORDER BY news_date DESC
                LIMIT 10
            """, (context.home_team_id, context.away_team_id, context.match_date))

            for row in cursor.fetchall():
                news = {
                    'title': row[0],
                    'type': row[1],
                    'sentiment': row[2],
                    'source': row[3],
                    'date': row[4],
                    'summary': row[5] or ''
                }
                result['recent_news'].append(news)

                if row[2] == 'positive':
                    result['positive_news'].append(news)
                elif row[2] == 'negative':
                    result['negative_news'].append(news)

                result['hot_topics'].append(row[0])

            if result['recent_news']:
                result['description'] = f'近期{len(result["recent_news"])}条相关新闻'

                # 如果有重要新闻，添加具体描述
                for news in result['recent_news'][:3]:
                    result['description'] += f'; {news["title"][:30]}'

        except Exception as e:
            logger.debug(f"News factors analysis error: {e}")

        # 如果没有新闻数据，提供默认分析
        if not result['recent_news']:
            # 检查是否有通用新闻
            try:
                cursor.execute("""
                    SELECT title, news_type, impact_type, source, news_date
                    FROM team_news
                    WHERE team_id IS NULL
                      AND news_date >= date(?, '-7 days')
                    ORDER BY news_date DESC
                    LIMIT 5
                """, (context.match_date,))

                for row in cursor.fetchall():
                    result['recent_news'].append({
                        'title': row[0],
                        'type': row[1],
                        'sentiment': row[2],
                        'source': row[3],
                        'date': row[4]
                    })

                if result['recent_news']:
                    result['description'] = f'近期足球资讯{len(result["recent_news"])}条'
            except:
                pass

        return result

    def _analyze_rivalry(self, cursor, context: ExtractionContext) -> Dict:
        """分析历史恩怨"""

        result = {
            'is_rivalry': False,
            'rivalry_type': '',
            'historical_events': [],
            'description': ''
        }

        try:
            # 获取两队历史交锋
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN home_team_id = ? AND home_goals > away_goals THEN 1 ELSE 0 END) as home_wins,
                       SUM(CASE WHEN away_team_id = ? AND away_goals > home_goals THEN 1 ELSE 0 END) as away_wins
                FROM matches
                WHERE (home_team_id = ? AND away_team_id = ?)
                   OR (home_team_id = ? AND away_team_id = ?)
                  AND status = 'finished'
            """, (context.home_team_id, context.away_team_id,
                  context.home_team_id, context.away_team_id,
                  context.away_team_id, context.home_team_id))

            row = cursor.fetchone()
            if row and row[0] >= 10:
                total = row[0]
                result['historical_events'].append({
                    'type': '历史交锋',
                    'total_matches': total,
                    'home_team_wins': row[1],
                    'away_team_wins': row[2]
                })

                # 检测是否存在宿敌关系
                win_ratio = abs(row[1] - row[2]) / total if total > 0 else 0
                if win_ratio < 0.3:  # 胜负接近，竞争激烈
                    result['is_rivalry'] = True
                    result['rivalry_type'] = 'competitive'
                    result['description'] = f'历史交锋{total}场，胜负接近，竞争激烈'
                elif total >= 20:
                    result['is_rivalry'] = True
                    result['rivalry_type'] = 'frequent'
                    result['description'] = f'两队交战频繁，历史{total}场对决'

        except Exception as e:
            logger.debug(f"Rivalry analysis error: {e}")

        return result

    def _analyze_milestones(self, cursor, context: ExtractionContext) -> Dict:
        """分析里程碑事件"""

        result = {
            'team_milestones': [],
            'player_milestones': [],
            'description': ''
        }

        try:
            # 检查球队即将达成的里程碑（如百胜、千球等）
            cursor.execute("""
                SELECT team_id, name_en,
                       (SELECT COUNT(*) FROM matches WHERE (home_team_id = team_id OR away_team_id = team_id) AND status = 'finished') as total_matches,
                       (SELECT SUM(home_goals) FROM matches WHERE home_team_id = team_id AND status = 'finished') +
                       (SELECT SUM(away_goals) FROM matches WHERE away_team_id = team_id AND status = 'finished') as total_goals
                FROM teams
                WHERE team_id IN (?, ?)
            """, (context.home_team_id, context.away_team_id))

            for row in cursor.fetchall():
                team_id, name, matches, goals = row

                # 检查接近里程碑
                if matches and matches % 1000 in range(990, 1000):
                    result['team_milestones'].append({
                        'team': name,
                        'milestone': '千场比赛里程碑',
                        'current': matches
                    })
                    result['description'] += f'{name}即将达成千场里程碑; '

                if goals and goals % 1000 in range(990, 1000):
                    result['team_milestones'].append({
                        'team': name,
                        'milestone': '千球里程碑',
                        'current': goals
                    })
                    result['description'] += f'{name}即将达成千球里程碑; '

            # 检查球员里程碑（进球数接近整数）
            cursor.execute("""
                SELECT player_name, team_id, total_goals
                FROM players
                WHERE team_id IN (?, ?)
                  AND total_goals IS NOT NULL
                  AND total_goals > 50
            """, (context.home_team_id, context.away_team_id))

            for row in cursor.fetchall():
                player, team_id, goals = row
                if goals % 100 in range(95, 100):
                    result['player_milestones'].append({
                        'player': player,
                        'milestone': f'{goals + (100 - goals % 100)}球里程碑',
                        'current': goals
                    })
                    result['description'] += f'{player}即将达成百球里程碑; '

        except Exception as e:
            logger.debug(f"Milestones analysis error: {e}")

        return result

    def _calculate_overall_impact(self, *factors) -> Dict:
        """计算综合影响"""

        match_imp = factors[0]
        player_imp = factors[1]
        coach_imp = factors[2]
        news_imp = factors[3]
        rivalry_imp = factors[4]
        milestone_imp = factors[5]

        value = 0.0
        confidence = 0.5
        direction = 'neutral'
        summary_parts = []

        # 赛事重要性影响
        if match_imp.get('involves_relegation'):
            value += 0.15
            confidence += 0.1
            summary_parts.append('降级争夺战')
        if match_imp.get('involves_qualification'):
            value += 0.10
            confidence += 0.05
            summary_parts.append('资格赛关键战')
        if match_imp.get('involves_title_race'):
            value += 0.12
            confidence += 0.08
            summary_parts.append('冠军争夺战')
        if match_imp.get('is_last_match'):
            value += 0.08
            summary_parts.append('赛季收官战')

        # 球员动态影响
        if player_imp.get('farewell_match'):
            value += 0.10
            summary_parts.append('告别赛')
        if player_imp.get('transfers_out'):
            value -= 0.05 * len(player_imp['transfers_out'])
            summary_parts.append(f'{len(player_imp["transfers_out"])}人即将离队')

        # 教练动态影响
        if coach_imp.get('recent_change'):
            value -= 0.08  # 教练更换通常带来不稳定
            confidence -= 0.05
            summary_parts.append('教练更换')

        # 恩怨情仇影响
        if rivalry_imp.get('is_rivalry'):
            value += 0.05
            confidence += 0.05
            summary_parts.append('宿敌对决')

        # 里程碑影响
        if milestone_imp.get('team_milestones') or milestone_imp.get('player_milestones'):
            value += 0.05
            summary_parts.append('里程碑之战')

        # 确定方向
        if value > 0.1:
            direction = 'positive'
        elif value < -0.05:
            direction = 'negative'

        # 置信度上限
        confidence = min(confidence, 0.85)

        return {
            'value': value,
            'confidence': confidence,
            'direction': direction,
            'summary': '; '.join(summary_parts) if summary_parts else '常规比赛'
        }

    def _generate_description(self, *factors) -> str:
        """生成描述"""

        descriptions = []

        # 赛事重要性
        if factors[0].get('description'):
            descriptions.append(factors[0]['description'])

        # 球员动态
        if factors[1].get('description'):
            descriptions.append(factors[1]['description'])

        # 教练动态
        if factors[2].get('description'):
            descriptions.append(factors[2]['description'])

        # 恩怨
        if factors[4].get('description'):
            descriptions.append(factors[4]['description'])

        # 里程碑
        if factors[5].get('description'):
            descriptions.append(factors[5]['description'])

        return ' | '.join(descriptions) if descriptions else '关键因素分析完成'