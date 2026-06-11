"""
爆冷分析模块

分析比赛的冷门潜力，识别实力差距与预期结果
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class UpsetAnalyzer:
    """爆冷分析器"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def analyze_match_upset_potential(
        self,
        home_team_id: int,
        away_team_id: int,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        分析比赛的爆冷潜力

        评估：
        - 谁是纸面实力强队
        - 谁是纸面实力弱队
        - 爆冷可能性及因素
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 1. 获取两队 Elo 评分
        home_elo = self._get_team_elo(home_team_id, conn)
        away_elo = self._get_team_elo(away_team_id, conn)

        # 2. 获取联赛排名
        home_rank = self._get_league_position(home_team_id, league_id, season_id, conn)
        away_rank = self._get_league_position(away_team_id, league_id, season_id, conn)

        # 3. 获取近期状态
        home_form = self._get_team_form(home_team_id, conn)
        away_form = self._get_team_form(away_team_id, conn)

        # 4. 判断强弱
        elo_diff = home_elo - away_elo
        home_advantage = 100  # 主场优势加分

        adjusted_home_elo = home_elo + home_advantage
        elo_diff_adjusted = adjusted_home_elo - away_elo

        if elo_diff_adjusted > 50:
            favorite = 'home'
            underdog = 'away'
            strength_gap = elo_diff_adjusted
        elif elo_diff_adjusted < -50:
            favorite = 'away'
            underdog = 'home'
            strength_gap = abs(elo_diff_adjusted)
        else:
            favorite = 'none'
            underdog = 'none'
            strength_gap = 0

        # 5. 分析爆冷因素
        upset_factors = self._analyze_upset_factors(
            home_team_id, away_team_id,
            home_elo, away_elo,
            home_form, away_form,
            home_rank, away_rank,
            conn
        )

        # 6. 计算爆冷概率
        upset_probability = self._calculate_upset_probability(
            strength_gap, home_form, away_form, upset_factors
        )

        # 7. 判断是否具备爆冷条件
        is_upset_potential = upset_probability >= 25 and favorite != 'none'

        return {
            'match_info': {
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'league_id': league_id,
                'season_id': season_id
            },
            'strength_analysis': {
                'home_elo': home_elo,
                'away_elo': away_elo,
                'elo_diff': elo_diff,
                'home_advantage': home_advantage,
                'adjusted_elo_diff': elo_diff_adjusted,
                'favorite': favorite,
                'underdog': underdog,
                'strength_gap': round(strength_gap, 1)
            },
            'league_position': {
                'home_rank': home_rank,
                'away_rank': away_rank
            },
            'recent_form': {
                'home_form': home_form,
                'away_form': away_form
            },
            'upset_factors': upset_factors,
            'upset_probability': upset_probability,
            'is_upset_potential': is_upset_potential,
            'upset_level': self._get_upset_level(upset_probability)
        }

    def scan_upset_matches(
        self,
        league_id: Optional[int] = None,
        match_date: Optional[str] = None,
        min_probability: float = 25,
        conn: Optional[sqlite3.Connection] = None
    ) -> List[Dict]:
        """
        扫描具有爆冷潜力的比赛
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取指定日期或最近的比赛
        if match_date:
            date_condition = "m.match_date = ?"
        else:
            date_condition = "m.match_date >= date('now')"

        query = f"""
            SELECT DISTINCT
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
            WHERE {date_condition}
            AND m.home_goals IS NULL  -- 未进行的比赛
            ORDER BY m.match_date
            LIMIT 50
        """

        params = [match_date] if match_date else []
        cursor.execute(query, params)
        matches = cursor.fetchall()

        upset_matches = []

        for match in matches:
            if league_id and match['league_id'] != league_id:
                continue

            analysis = self.analyze_match_upset_potential(
                match['home_team_id'],
                match['away_team_id'],
                match['league_id'],
                match['season_id'],
                conn
            )

            if analysis['is_upset_potential'] and analysis['upset_probability'] >= min_probability:
                upset_matches.append({
                    'match_id': match['match_id'],
                    'match_date': match['match_date'],
                    'home_team': match['home_team'],
                    'away_team': match['away_team'],
                    'favorite': analysis['strength_analysis']['favorite'],
                    'underdog': analysis['strength_analysis']['underdog'],
                    'strength_gap': analysis['strength_analysis']['strength_gap'],
                    'upset_probability': analysis['upset_probability'],
                    'upset_level': analysis['upset_level'],
                    'key_factors': analysis['upset_factors']['key_factors']
                })

        # 按爆冷概率排序
        upset_matches.sort(key=lambda x: x['upset_probability'], reverse=True)

        return upset_matches

    def get_underdog_win_history(
        self,
        team_id: int,
        limit: int = 20,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict:
        """
        获取球队作为弱队赢球的历史记录 (爆冷记录)
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取球队比赛，并对比 Elo 判断是否为弱队
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                ht.name_en as home_team,
                at.name_en as away_team,
                hte.elo_rating as home_elo,
                ate.elo_rating as away_elo
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            LEFT JOIN elo_ratings hte ON m.home_team_id = hte.team_id
            LEFT JOIN elo_ratings ate ON m.away_team_id = ate.team_id
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.home_goals IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT ?
        """, (team_id, team_id, limit))

        matches = cursor.fetchall()

        upset_wins = []
        total_as_underdog = 0

        for match in matches:
            is_home = match['home_team_id'] == team_id
            home_elo = match['home_elo'] or 1500
            away_elo = match['away_elo'] or 1500

            # 判断是否为弱队
            if is_home:
                elo_diff = home_elo + 100 - away_elo  # 加主场优势
                team_goals = match['home_goals']
                opp_goals = match['away_goals']
            else:
                elo_diff = away_elo - (home_elo + 100)
                team_goals = match['away_goals']
                opp_goals = match['home_goals']

            # Elo 差距超过 50 为弱队
            if elo_diff < -50:
                total_as_underdog += 1
                if team_goals > opp_goals:
                    upset_wins.append({
                        'match_id': match['match_id'],
                        'date': match['match_date'],
                        'venue': 'H' if is_home else 'A',
                        'opponent': match['away_team'] if is_home else match['home_team'],
                        'score': f"{team_goals}-{opp_goals}",
                        'elo_diff': round(elo_diff, 1),
                        'upset_magnitude': abs(elo_diff)
                    })

        return {
            'team_id': team_id,
            'total_as_underdog': total_as_underdog,
            'upset_wins': upset_wins,
            'upset_win_rate': round(len(upset_wins) / total_as_underdog * 100, 1) if total_as_underdog > 0 else 0,
            'giant_killing_count': len(upset_wins)
        }

    def _get_team_elo(self, team_id: int, conn: sqlite3.Connection) -> float:
        """获取球队 Elo 评分"""
        cursor = conn.cursor()
        cursor.execute("SELECT elo_rating FROM elo_ratings WHERE team_id = ?", (team_id,))
        result = cursor.fetchone()
        return float(result['elo_rating']) if result else 1500

    def _get_league_position(
        self,
        team_id: int,
        league_id: Optional[int],
        season_id: Optional[int],
        conn: sqlite3.Connection
    ) -> Optional[Dict]:
        """获取联赛排名"""
        if not league_id or not season_id:
            return None

        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                s.position,
                s.points,
                s.played,
                s.won,
                s.drawn,
                s.lost,
                s.goal_diff
            FROM standings s
            WHERE s.team_id = ? AND s.league_id = ? AND s.season_id = ?
            LIMIT 1
        """, (team_id, league_id, season_id))

        result = cursor.fetchone()
        if result:
            return dict(result)
        return None

    def _get_team_form(self, team_id: int, conn: sqlite3.Connection) -> Dict:
        """获取球队近期状态"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                SUM(CASE
                    WHEN (m.home_team_id = ? AND m.home_goals > m.away_goals) OR
                         (m.away_team_id = ? AND m.away_goals > m.home_goals)
                    THEN 1 ELSE 0 END
                ) as wins,
                SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as draws,
                SUM(CASE
                    WHEN (m.home_team_id = ? AND m.home_goals < m.away_goals) OR
                         (m.away_team_id = ? AND m.away_goals < m.home_goals)
                    THEN 1 ELSE 0 END
                ) as losses,
                SUM(CASE
                    WHEN m.home_team_id = ? THEN m.home_goals
                    ELSE m.away_goals END
                ) as goals_for,
                SUM(CASE
                    WHEN m.home_team_id = ? THEN m.away_goals
                    ELSE m.home_goals END
                ) as goals_against
            FROM (
                SELECT home_goals, away_goals, home_team_id, away_team_id
                FROM matches
                WHERE (home_team_id = ? OR away_team_id = ?)
                AND home_goals IS NOT NULL
                ORDER BY match_date DESC
                LIMIT 5
            ) m
        """, (team_id, team_id, team_id, team_id, team_id, team_id, team_id, team_id))

        result = cursor.fetchone()
        if result:
            r = dict(result)
            wins = r['wins'] or 0
            draws = r['draws'] or 0
            losses = r['losses'] or 0
            points = wins * 3 + draws
            return {
                'wins': wins,
                'draws': draws,
                'losses': losses,
                'points': points,
                'points_per_match': round(points / 5, 2),
                'goals_for': r['goals_for'] or 0,
                'goals_against': r['goals_against'] or 0,
                'form_string': self._get_form_string(wins, draws, losses)
            }
        return {'wins': 0, 'draws': 0, 'losses': 0, 'points': 0, 'form_string': ''}

    def _get_form_string(self, wins: int, draws: int, losses: int) -> str:
        """生成状态字符串"""
        form = []
        for _ in range(wins):
            form.append('W')
        for _ in range(draws):
            form.append('D')
        for _ in range(losses):
            form.append('L')
        return '-'.join(form[:5])

    def _analyze_upset_factors(
        self,
        home_team_id: int,
        away_team_id: int,
        home_elo: float,
        away_elo: float,
        home_form: Dict,
        away_form: Dict,
        home_rank: Optional[Dict],
        away_rank: Optional[Dict],
        conn: sqlite3.Connection
    ) -> Dict:
        """分析可能导致爆冷的因素"""
        factors = []
        key_factors = []

        # 1. 状态差异
        home_form_points = home_form.get('points', 0)
        away_form_points = away_form.get('points', 0)

        if home_form_points > away_form_points + 6:
            factors.append({'factor': 'home_form', 'direction': 'upset', 'weight': 15,
                           'description': '主队状态远好于客队'})
            key_factors.append('主队状态火热')
        elif away_form_points > home_form_points + 6:
            factors.append({'factor': 'away_form', 'direction': 'favorite', 'weight': 15,
                           'description': '客队状态远好于主队'})

        # 2. 排名差异
        if home_rank and away_rank:
            home_pos = home_rank.get('position', 99)
            away_pos = away_rank.get('position', 99)

            if home_pos < away_pos - 5:
                factors.append({'factor': 'home_rank', 'direction': 'expected', 'weight': 10,
                               'description': '主队排名远高于客队'})
            elif away_pos < home_pos - 5:
                factors.append({'factor': 'away_rank', 'direction': 'upset', 'weight': 20,
                               'description': '客队排名远高于主队'})
                key_factors.append('客队排名占优')

        # 3. 主场优势
        home_record = self._get_home_record(home_team_id, conn)
        if home_record and home_record.get('win_rate', 0) >= 60:
            factors.append({'factor': 'home_advantage', 'direction': 'expected', 'weight': 10,
                           'description': '主队主场强势'})
        elif home_record and home_record.get('win_rate', 0) <= 30:
            factors.append({'factor': 'home_weak', 'direction': 'upset', 'weight': 15,
                           'description': '主队主场疲软'})
            key_factors.append('主队主场疲软')

        # 4. 客队客场表现
        away_away_record = self._get_away_record(away_team_id, conn)
        if away_away_record and away_away_record.get('win_rate', 0) >= 50:
            factors.append({'factor': 'away_strong', 'direction': 'upset', 'weight': 15,
                           'description': '客队客场强势'})
            key_factors.append('客队客场强势')

        # 5. 战意分析 (保级/争冠)
        motivation_factors = self._analyze_motivation_for_upset(home_rank, away_rank)
        factors.extend(motivation_factors)
        key_factors.extend([f['description'] for f in motivation_factors if f['direction'] == 'upset'])

        return {
            'all_factors': factors,
            'key_factors': key_factors[:5],  # 最多 5 个关键因素
            'upset_factor_count': sum(1 for f in factors if f['direction'] == 'upset'),
            'favorite_factor_count': sum(1 for f in factors if f['direction'] == 'favorite' or f['direction'] == 'expected')
        }

    def _calculate_upset_probability(
        self,
        strength_gap: float,
        home_form: Dict,
        away_form: Dict,
        upset_factors: Dict
    ) -> float:
        """计算爆冷概率"""
        # 基础概率：实力差距越大，爆冷概率越低
        base_probability = 50 - (strength_gap / 10)

        # 状态调整
        form_diff = away_form.get('points', 0) - home_form.get('points', 0)
        form_adjustment = form_diff * 2

        # 因素调整
        upset_count = upset_factors.get('upset_factor_count', 0)
        factor_adjustment = upset_count * 5

        # 最终概率
        probability = base_probability + form_adjustment + factor_adjustment

        # 限制在 0-100 之间
        return max(0, min(100, probability))

    def _get_upset_level(self, probability: float) -> str:
        """获取爆冷等级"""
        if probability >= 60:
            return 'very_high'      # 极高爆冷可能
        elif probability >= 45:
            return 'high'           # 高爆冷可能
        elif probability >= 30:
            return 'moderate'       # 中等爆冷可能
        elif probability >= 15:
            return 'low'            # 低爆冷可能
        else:
            return 'very_low'       # 极低爆冷可能

    def _get_home_record(self, team_id: int, conn: sqlite3.Connection) -> Optional[Dict]:
        """获取球队主场战绩"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                SUM(CASE WHEN home_goals < away_goals THEN 1 ELSE 0 END) as losses
            FROM matches
            WHERE home_team_id = ? AND home_goals IS NOT NULL
        """, (team_id,))
        result = cursor.fetchone()
        if result and result['matches'] > 0:
            r = dict(result)
            return {
                'matches': r['matches'],
                'wins': r['wins'] or 0,
                'draws': r['draws'] or 0,
                'losses': r['losses'] or 0,
                'win_rate': round((r['wins'] or 0) / r['matches'] * 100, 1)
            }
        return None

    def _get_away_record(self, team_id: int, conn: sqlite3.Connection) -> Optional[Dict]:
        """获取球队客场战绩"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(CASE WHEN away_goals > home_goals THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                SUM(CASE WHEN away_goals < home_goals THEN 1 ELSE 0 END) as losses
            FROM matches
            WHERE away_team_id = ? AND home_goals IS NOT NULL
        """, (team_id,))
        result = cursor.fetchone()
        if result and result['matches'] > 0:
            r = dict(result)
            return {
                'matches': r['matches'],
                'wins': r['wins'] or 0,
                'draws': r['draws'] or 0,
                'losses': r['losses'] or 0,
                'win_rate': round((r['wins'] or 0) / r['matches'] * 100, 1)
            }
        return None

    def _analyze_motivation_for_upset(
        self,
        home_rank: Optional[Dict],
        away_rank: Optional[Dict]
    ) -> List[Dict]:
        """分析战意对爆冷的影响"""
        factors = []

        if not home_rank or not away_rank:
            return factors

        home_pos = home_rank.get('position', 99)
        away_pos = away_rank.get('position', 99)

        # 假设联赛 20 队，前 6 欧战，后 3 降级
        # 保级队战意更强
        if home_pos >= 17:
            factors.append({
                'factor': 'home_relegation',
                'direction': 'upset',
                'weight': 20,
                'description': '主队保级战意强'
            })

        if away_pos >= 17:
            factors.append({
                'factor': 'away_relegation',
                'direction': 'upset',
                'weight': 20,
                'description': '客队保级战意强'
            })

        # 无欲无求的中游球队
        if 8 <= home_pos <= 12:
            factors.append({
                'factor': 'home_no_pressure',
                'direction': 'upset',
                'weight': 10,
                'description': '主队无欲无求'
            })

        return factors
