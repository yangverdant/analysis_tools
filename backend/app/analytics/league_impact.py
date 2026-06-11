"""
连锁反应分析模块

功能:
1. 模拟比赛结果对积分榜的影响
2. 晋级/降级形势分析
3. 争冠/欧战资格影响
4. 对其他球队的连锁影响

应用场景:
- "如果本场获胜，将领先第二名X分"
- "如果输球，将跌入降级区"
- "本场比赛结果将影响Y支球队的排名"
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from copy import deepcopy


@dataclass
class StandingRow:
    """积分榜行"""
    team_id: int
    team_name: str
    matches: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    points: int
    goal_diff: int


class LeagueImpactAnalyzer:
    """联赛影响分析器"""

    # 降级区位置 (倒数3名)
    RELEGATION_ZONE = 3

    # 欧战资格位置
    CHAMPIONS_LEAGUE_SPOTS = 4  # 欧冠名额
    EUROPA_LEAGUE_SPOTS = 2  # 欧联名额
    CONFERENCE_LEAGUE_SPOTS = 1  # 欧会杯名额

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_current_standings(
        self,
        league_id: int,
        season_id: int,
        conn: sqlite3.Connection = None
    ) -> List[StandingRow]:
        """获取当前积分榜"""
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 计算积分榜
        cursor.execute("""
            WITH team_stats AS (
                SELECT
                    team_id,
                    COUNT(*) as matches,
                    SUM(CASE WHEN is_home = 1 AND goals_for > goals_against THEN 1
                             WHEN is_home = 0 AND goals_for > goals_against THEN 1
                             ELSE 0 END) as wins,
                    SUM(CASE WHEN goals_for = goals_against THEN 1 ELSE 0 END) as draws,
                    SUM(CASE WHEN is_home = 1 AND goals_for < goals_against THEN 1
                             WHEN is_home = 0 AND goals_for < goals_against THEN 1
                             ELSE 0 END) as losses,
                    SUM(goals_for) as goals_for,
                    SUM(goals_against) as goals_against
                FROM (
                    SELECT
                        home_team_id as team_id,
                        1 as is_home,
                        home_goals as goals_for,
                        away_goals as goals_against
                    FROM matches
                    WHERE league_id = ? AND season_id = ?
                    AND home_goals IS NOT NULL

                    UNION ALL

                    SELECT
                        away_team_id as team_id,
                        0 as is_home,
                        away_goals as goals_for,
                        home_goals as goals_against
                    FROM matches
                    WHERE league_id = ? AND season_id = ?
                    AND away_goals IS NOT NULL
                )
                GROUP BY team_id
            )
            SELECT
                ts.team_id,
                t.name_en as team_name,
                ts.matches,
                ts.wins,
                ts.draws,
                ts.losses,
                ts.goals_for,
                ts.goals_against,
                ts.wins * 3 + ts.draws as points,
                ts.goals_for - ts.goals_against as goal_diff
            FROM team_stats ts
            JOIN teams t ON ts.team_id = t.team_id
            ORDER BY points DESC, goal_diff DESC, ts.goals_for DESC
        """, (league_id, season_id, league_id, season_id))

        standings = []
        for row in cursor.fetchall():
            standings.append(StandingRow(
                team_id=row['team_id'],
                team_name=row['team_name'],
                matches=row['matches'],
                wins=row['wins'],
                draws=row['draws'],
                losses=row['losses'],
                goals_for=row['goals_for'],
                goals_against=row['goals_against'],
                points=row['points'],
                goal_diff=row['goal_diff']
            ))

        return standings

    def simulate_match_result(
        self,
        standings: List[StandingRow],
        home_team_id: int,
        away_team_id: int,
        home_goals: int,
        away_goals: int
    ) -> List[StandingRow]:
        """
        模拟比赛结果后的积分榜

        Args:
            standings: 当前积分榜
            home_team_id: 主队ID
            away_team_id: 客队ID
            home_goals: 主队进球
            away_goals: 客队进球

        Returns:
            模拟后的积分榜
        """
        # 深拷贝
        new_standings = deepcopy(standings)

        # 找到主队和客队
        home_team = None
        away_team = None
        for team in new_standings:
            if team.team_id == home_team_id:
                home_team = team
            elif team.team_id == away_team_id:
                away_team = team

        if not home_team or not away_team:
            return new_standings

        # 更新比赛场次
        home_team.matches += 1
        away_team.matches += 1

        # 更新进球
        home_team.goals_for += home_goals
        home_team.goals_against += away_goals
        away_team.goals_for += away_goals
        away_team.goals_against += home_goals

        # 更新结果
        if home_goals > away_goals:
            home_team.wins += 1
            home_team.points += 3
            away_team.losses += 1
        elif home_goals < away_goals:
            away_team.wins += 1
            away_team.points += 3
            home_team.losses += 1
        else:
            home_team.draws += 1
            away_team.draws += 1
            home_team.points += 1
            away_team.points += 1

        # 更新净胜球
        home_team.goal_diff = home_team.goals_for - home_team.goals_against
        away_team.goal_diff = away_team.goals_for - away_team.goals_against

        # 重新排序
        new_standings.sort(key=lambda x: (x.points, x.goal_diff, x.goals_for), reverse=True)

        return new_standings

    def analyze_match_impact(
        self,
        match_id: str,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析比赛结果的连锁影响

        Args:
            match_id: 比赛ID

        Returns:
            连锁影响分析
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取比赛信息
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.league_id,
                m.season_id,
                ht.name_en as home_team,
                at.name_en as away_team
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.match_id = ?
        """, (match_id,))

        match = cursor.fetchone()
        if not match:
            return {'error': '比赛不存在'}

        league_id = match['league_id']
        season_id = match['season_id']
        home_team_id = match['home_team_id']
        away_team_id = match['away_team_id']

        # 获取当前积分榜
        current_standings = self.get_current_standings(league_id, season_id, conn)

        if not current_standings:
            return {'error': '无法获取积分榜'}

        total_teams = len(current_standings)

        # 找到当前排名
        home_current_rank = next(
            (i + 1 for i, t in enumerate(current_standings) if t.team_id == home_team_id), None
        )
        away_current_rank = next(
            (i + 1 for i, t in enumerate(current_standings) if t.team_id == away_team_id), None
        )

        # 模拟三种结果
        scenarios = {}

        # 1. 主胜
        win_standings = self.simulate_match_result(
            current_standings, home_team_id, away_team_id, 2, 0
        )
        home_win_rank = next(
            (i + 1 for i, t in enumerate(win_standings) if t.team_id == home_team_id), None
        )
        away_lose_rank = next(
            (i + 1 for i, t in enumerate(win_standings) if t.team_id == away_team_id), None
        )

        scenarios['home_win'] = {
            'home_rank': home_win_rank,
            'away_rank': away_lose_rank,
            'home_rank_change': home_current_rank - home_win_rank if home_current_rank and home_win_rank else 0,
            'away_rank_change': away_current_rank - away_lose_rank if away_current_rank and away_lose_rank else 0,
            'home_points': next(t.points for t in win_standings if t.team_id == home_team_id),
            'away_points': next(t.points for t in win_standings if t.team_id == away_team_id),
        }

        # 2. 平局
        draw_standings = self.simulate_match_result(
            current_standings, home_team_id, away_team_id, 1, 1
        )
        home_draw_rank = next(
            (i + 1 for i, t in enumerate(draw_standings) if t.team_id == home_team_id), None
        )
        away_draw_rank = next(
            (i + 1 for i, t in enumerate(draw_standings) if t.team_id == away_team_id), None
        )

        scenarios['draw'] = {
            'home_rank': home_draw_rank,
            'away_rank': away_draw_rank,
            'home_rank_change': home_current_rank - home_draw_rank if home_current_rank and home_draw_rank else 0,
            'away_rank_change': away_current_rank - away_draw_rank if away_current_rank and away_draw_rank else 0,
            'home_points': next(t.points for t in draw_standings if t.team_id == home_team_id),
            'away_points': next(t.points for t in draw_standings if t.team_id == away_team_id),
        }

        # 3. 客胜
        lose_standings = self.simulate_match_result(
            current_standings, home_team_id, away_team_id, 0, 2
        )
        home_lose_rank = next(
            (i + 1 for i, t in enumerate(lose_standings) if t.team_id == home_team_id), None
        )
        away_win_rank = next(
            (i + 1 for i, t in enumerate(lose_standings) if t.team_id == away_team_id), None
        )

        scenarios['away_win'] = {
            'home_rank': home_lose_rank,
            'away_rank': away_win_rank,
            'home_rank_change': home_current_rank - home_lose_rank if home_current_rank and home_lose_rank else 0,
            'away_rank_change': away_current_rank - away_win_rank if away_current_rank and away_win_rank else 0,
            'home_points': next(t.points for t in lose_standings if t.team_id == home_team_id),
            'away_points': next(t.points for t in lose_standings if t.team_id == away_team_id),
        }

        # 分析关键形势
        impact_analysis = {
            'home_team': {
                'name': match['home_team'],
                'current_rank': home_current_rank,
                'current_points': next(t.points for t in current_standings if t.team_id == home_team_id),
                'relegation_risk': self._analyze_relegation_risk(home_current_rank, total_teams, scenarios, 'home'),
                'title_risk': self._analyze_title_risk(home_current_rank, scenarios, 'home'),
                'europe_risk': self._analyze_europe_risk(home_current_rank, total_teams, scenarios, 'home')
            },
            'away_team': {
                'name': match['away_team'],
                'current_rank': away_current_rank,
                'current_points': next(t.points for t in current_standings if t.team_id == away_team_id),
                'relegation_risk': self._analyze_relegation_risk(away_current_rank, total_teams, scenarios, 'away'),
                'title_risk': self._analyze_title_risk(away_current_rank, scenarios, 'away'),
                'europe_risk': self._analyze_europe_risk(away_current_rank, total_teams, scenarios, 'away')
            }
        }

        return {
            'match_id': match_id,
            'match_date': match['match_date'],
            'league_id': league_id,
            'total_teams': total_teams,
            'current_standings': [
                {
                    'rank': i + 1,
                    'team': t.team_name,
                    'points': t.points,
                    'matches': t.matches,
                    'goal_diff': t.goal_diff
                } for i, t in enumerate(current_standings)
            ],
            'scenarios': scenarios,
            'impact_analysis': impact_analysis,
            'summary': self._generate_summary(impact_analysis)
        }

    def _analyze_relegation_risk(
        self,
        current_rank: int,
        total_teams: int,
        scenarios: Dict,
        team_key: str
    ) -> Dict:
        """分析降级风险"""
        relegation_line = total_teams - self.RELEGATION_ZONE + 1

        # 检查各结果后的排名
        worst_rank = max(
            scenarios['home_win'][f'{team_key}_rank'] if team_key == 'away' else scenarios['away_win'][f'{team_key}_rank'],
            scenarios['draw'][f'{team_key}_rank'],
            scenarios['home_win'][f'{team_key}_rank'] if team_key == 'home' else scenarios['away_win'][f'{team_key}_rank']
        )

        best_rank = min(
            scenarios['home_win'][f'{team_key}_rank'] if team_key == 'home' else scenarios['away_win'][f'{team_key}_rank'],
            scenarios['draw'][f'{team_key}_rank'],
            scenarios['away_win'][f'{team_key}_rank'] if team_key == 'away' else scenarios['home_win'][f'{team_key}_rank']
        )

        if best_rank >= relegation_line:
            return {
                'level': 'critical',
                'description': f'已处于降级区，最乐观排名{best_rank}名'
            }
        elif worst_rank >= relegation_line:
            return {
                'level': 'high',
                'description': f'输球将跌入降级区(第{relegation_line}名后)'
            }
        elif worst_rank >= relegation_line - 2:
            return {
                'level': 'moderate',
                'description': f'接近降级区，需警惕'
            }
        else:
            return {
                'level': 'low',
                'description': '远离降级区'
            }

    def _analyze_title_risk(self, current_rank: int, scenarios: Dict, team_key: str) -> Dict:
        """分析争冠形势"""
        best_rank = min(
            scenarios['home_win'][f'{team_key}_rank'] if team_key == 'home' else scenarios['away_win'][f'{team_key}_rank'],
            scenarios['draw'][f'{team_key}_rank'],
            scenarios['away_win'][f'{team_key}_rank'] if team_key == 'away' else scenarios['home_win'][f'{team_key}_rank']
        )

        if current_rank == 1:
            return {
                'level': 'leading',
                'description': '目前领跑积分榜'
            }
        elif best_rank == 1:
            return {
                'level': 'contending',
                'description': '赢球可登顶'
            }
        elif current_rank <= 3:
            return {
                'level': 'close',
                'description': f'争冠集团，当前第{current_rank}名'
            }
        else:
            return {
                'level': 'none',
                'description': '争冠希望渺茫'
            }

    def _analyze_europe_risk(
        self,
        current_rank: int,
        total_teams: int,
        scenarios: Dict,
        team_key: str
    ) -> Dict:
        """分析欧战资格形势"""
        europe_spots = self.CHAMPIONS_LEAGUE_SPOTS + self.EUROPA_LEAGUE_SPOTS + self.CONFERENCE_LEAGUE_SPOTS

        worst_rank = max(
            scenarios['home_win'][f'{team_key}_rank'] if team_key == 'away' else scenarios['away_win'][f'{team_key}_rank'],
            scenarios['draw'][f'{team_key}_rank'],
            scenarios['home_win'][f'{team_key}_rank'] if team_key == 'home' else scenarios['away_win'][f'{team_key}_rank']
        )

        best_rank = min(
            scenarios['home_win'][f'{team_key}_rank'] if team_key == 'home' else scenarios['away_win'][f'{team_key}_rank'],
            scenarios['draw'][f'{team_key}_rank'],
            scenarios['away_win'][f'{team_key}_rank'] if team_key == 'away' else scenarios['home_win'][f'{team_key}_rank']
        )

        if current_rank <= europe_spots:
            return {
                'level': 'in_zone',
                'description': f'目前处于欧战区(前{europe_spots}名)'
            }
        elif best_rank <= europe_spots:
            return {
                'level': 'contending',
                'description': f'赢球可进入欧战区'
            }
        elif worst_rank <= europe_spots:
            return {
                'level': 'borderline',
                'description': f'输球可能跌出欧战区'
            }
        else:
            return {
                'level': 'none',
                'description': '远离欧战区'
            }

    def _generate_summary(self, impact_analysis: Dict) -> str:
        """生成摘要"""
        parts = []

        # 主队形势
        home = impact_analysis['home_team']
        if home['relegation_risk']['level'] in ['critical', 'high']:
            parts.append(f"{home['name']}面临降级压力")
        if home['title_risk']['level'] == 'leading':
            parts.append(f"{home['name']}领跑积分榜")
        elif home['title_risk']['level'] == 'contending':
            parts.append(f"{home['name']}争冠关键战")

        # 客队形势
        away = impact_analysis['away_team']
        if away['relegation_risk']['level'] in ['critical', 'high']:
            parts.append(f"{away['name']}面临降级压力")
        if away['title_risk']['level'] == 'leading':
            parts.append(f"{away['name']}领跑积分榜")
        elif away['title_risk']['level'] == 'contending':
            parts.append(f"{away['name']}争冠关键战")

        return '；'.join(parts) if parts else '常规比赛，无特殊形势'


def main():
    """测试连锁反应分析"""
    db_path = r"d:\football_tools\data\football_v2.db"
    analyzer = LeagueImpactAnalyzer(db_path)

    print("连锁反应分析测试")
    print("=" * 60)

    # 获取一场比赛测试
    conn = analyzer.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT match_id, home_team_id, away_team_id, league_id, season_id
        FROM matches
        WHERE home_goals IS NULL
        LIMIT 1
    """)
    match = cursor.fetchone()

    if match:
        result = analyzer.analyze_match_impact(match['match_id'], conn)
        print(f"\n比赛: {match['match_id']}")
        print(f"摘要: {result.get('summary', 'N/A')}")

        if 'impact_analysis' in result:
            home = result['impact_analysis']['home_team']
            away = result['impact_analysis']['away_team']
            print(f"\n主队 {home['name']}:")
            print(f"  当前排名: {home['current_rank']}")
            print(f"  降级风险: {home['relegation_risk']['description']}")
            print(f"  争冠形势: {home['title_risk']['description']}")

            print(f"\n客队 {away['name']}:")
            print(f"  当前排名: {away['current_rank']}")
            print(f"  降级风险: {away['relegation_risk']['description']}")
            print(f"  争冠形势: {away['title_risk']['description']}")

    conn.close()


if __name__ == "__main__":
    main()
