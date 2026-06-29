"""
Elo评分分析模块

Elo评分系统用于评估球队实力，基于比赛结果动态调整评分
核心公式：E(A) = 1 / (1 + 10^((R_B - R_A) / 400))
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import math


class EloAnalyzer:
    """Elo评分分析器"""

    # 默认参数
    DEFAULT_ELO = 1500
    K_FACTOR = 20  # 足球标准K值(32过大会导致评分波动过大)
    HOME_ADVANTAGE = 100  # 主场优势（Elo加分）
    SCALE_FACTOR = 400  # Elo尺度因子

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_team_elo(self, team_id: int, conn: sqlite3.Connection) -> float:
        """
        获取球队当前Elo评分
        从elo_ratings表读取，不存在则返回默认值
        """
        cursor = conn.cursor()
        cursor.execute("""
            SELECT elo_rating FROM elo_ratings WHERE team_id = ?
        """, (team_id,))
        result = cursor.fetchone()
        if result:
            return float(result['elo_rating'])
        return self.DEFAULT_ELO

    def calculate_expected_score(self, rating_a: float, rating_b: float) -> float:
        """
        计算预期胜率
        E(A) = 1 / (1 + 10^((R_B - R_A) / 400))
        """
        return 1 / (1 + 10 ** ((rating_b - rating_a) / self.SCALE_FACTOR))

    def calculate_elo_change(
        self,
        team_elo: float,
        opponent_elo: float,
        actual_score: float,
        is_home: bool = True
    ) -> Tuple[float, float]:
        """
        计算比赛后的Elo变化

        Args:
            team_elo: 球队当前Elo
            opponent_elo: 对手当前Elo
            actual_score: 实际结果 (1=胜, 0.5=平, 0=负)
            is_home: 是否主场

        Returns:
            (新Elo, Elo变化量)
        """
        # 主场优势调整
        adjusted_elo = team_elo + (self.HOME_ADVANTAGE if is_home else 0)

        # 计算预期胜率
        expected_score = self.calculate_expected_score(adjusted_elo, opponent_elo)

        # 计算新Elo
        elo_change = self.K_FACTOR * (actual_score - expected_score)
        new_elo = team_elo + elo_change

        return new_elo, elo_change

    def update_elo_after_match(
        self,
        home_team_id: int,
        away_team_id: int,
        home_goals: int,
        away_goals: int,
        match_date: str,
        conn: sqlite3.Connection
    ) -> Dict:
        """
        比赛后更新双方Elo评分

        Returns:
            包含更新前后评分的详细信息
        """
        # 获取当前评分
        home_elo_before = self.get_team_elo(home_team_id, conn)
        away_elo_before = self.get_team_elo(away_team_id, conn)

        # 计算实际结果
        if home_goals > away_goals:
            home_actual = 1.0
            away_actual = 0.0
        elif home_goals < away_goals:
            home_actual = 0.0
            away_actual = 1.0
        else:
            home_actual = 0.5
            away_actual = 0.5

        # 计算新评分
        home_elo_after, home_change = self.calculate_elo_change(
            home_elo_before, away_elo_before, home_actual, is_home=True
        )
        away_elo_after, away_change = self.calculate_elo_change(
            away_elo_before, home_elo_before, away_actual, is_home=False
        )

        # 更新数据库
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO elo_ratings (team_id, elo_rating, calculated_at)
            VALUES (?, ?, ?)
        """, (home_team_id, home_elo_after, datetime.now().isoformat()))
        cursor.execute("""
            INSERT OR REPLACE INTO elo_ratings (team_id, elo_rating, calculated_at)
            VALUES (?, ?, ?)
        """, (away_team_id, away_elo_after, datetime.now().isoformat()))

        # 记录历史
        cursor.execute("""
            INSERT INTO elo_history (team_id, elo_before, elo_after, change_amount, match_date, reason)
            VALUES (?, ?, ?, ?, ?, 'match_result')
        """, (home_team_id, home_elo_before, home_elo_after, home_change, match_date))
        cursor.execute("""
            INSERT INTO elo_history (team_id, elo_before, elo_after, change_amount, match_date, reason)
            VALUES (?, ?, ?, ?, ?, 'match_result')
        """, (away_team_id, away_elo_before, away_elo_after, away_change, match_date))

        conn.commit()

        return {
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_elo_before': round(home_elo_before, 2),
            'home_elo_after': round(home_elo_after, 2),
            'home_change': round(home_change, 2),
            'away_elo_before': round(away_elo_before, 2),
            'away_elo_after': round(away_elo_after, 2),
            'away_change': round(away_change, 2),
            'home_expected': round(self.calculate_expected_score(home_elo_before + self.HOME_ADVANTAGE, away_elo_before), 3),
            'away_expected': round(self.calculate_expected_score(away_elo_before, home_elo_before + self.HOME_ADVANTAGE), 3),
        }

    def get_elo_rankings(
        self,
        league_id: Optional[int] = None,
        limit: int = 50,
        conn: sqlite3.Connection = None
    ) -> List[Dict]:
        """
        获取Elo排名列表

        Args:
            league_id: 联赛ID（可选，不传则返回全部）
            limit: 返回数量限制
            conn: 数据库连接
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        if league_id:
            # 获取联赛内球队排名
            cursor.execute("""
                SELECT
                    t.team_id,
                    t.name_en,
                    t.name_cn,
                    e.elo_rating,
                    l.name_en as league_name
                FROM elo_ratings e
                JOIN teams t ON e.team_id = t.team_id
                JOIN leagues l ON t.primary_league_id = l.league_id
                WHERE t.primary_league_id = ?
                ORDER BY e.elo_rating DESC
                LIMIT ?
            """, (league_id, limit))
        else:
            # 全部球队排名
            cursor.execute("""
                SELECT
                    t.team_id,
                    t.name_en,
                    t.name_cn,
                    e.elo_rating,
                    l.name_en as league_name
                FROM elo_ratings e
                JOIN teams t ON e.team_id = t.team_id
                LEFT JOIN leagues l ON t.primary_league_id = l.league_id
                ORDER BY e.elo_rating DESC
                LIMIT ?
            """, (limit,))

        results = []
        for i, row in enumerate(cursor.fetchall(), 1):
            results.append({
                'rank': i,
                'team_id': row['team_id'],
                'name_en': row['name_en'],
                'name_cn': row['name_cn'],
                'elo_rating': round(row['elo_rating'], 2),
                'league_name': row['league_name']
            })

        return results

    def get_elo_history(
        self,
        team_id: int,
        days: int = 365,
        conn: sqlite3.Connection = None
    ) -> List[Dict]:
        """
        获取球队Elo历史变化
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                elo_before,
                elo_after,
                change_amount,
                match_date,
                reason
            FROM elo_history
            WHERE team_id = ?
            AND match_date >= date('now', ?)
            ORDER BY match_date DESC
        """, (team_id, f'-{days} days'))

        results = []
        for row in cursor.fetchall():
            results.append({
                'elo_before': round(row['elo_before'], 2),
                'elo_after': round(row['elo_after'], 2),
                'change': round(row['change_amount'], 2),
                'date': row['match_date'],
                'reason': row['reason']
            })

        return results

    def calculate_match_elo_prediction(
        self,
        home_team_id: int,
        away_team_id: int,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        基于Elo预测比赛结果概率

        使用Sigmoid模型计算draw概率: 差值小→draw概率高, 差值大→draw概率低
        """
        if conn is None:
            conn = self.get_connection()

        home_elo = self.get_team_elo(home_team_id, conn)
        away_elo = self.get_team_elo(away_team_id, conn)

        probs = self._elo_probabilities(home_elo, away_elo)

        return {
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_elo': round(home_elo, 2),
            'away_elo': round(away_elo, 2),
            'home_elo_adjusted': round(home_elo + self.HOME_ADVANTAGE, 2),
            'elo_diff': round(home_elo - away_elo, 2),
            'predictions': probs,
            'expected_home_score': round(probs['home_win'], 3),
            'expected_away_score': round(probs['away_win'], 3)
        }

    def _elo_probabilities(self, home_elo: float, away_elo: float, home_advantage: int = None) -> Dict:
        """Elo→三维概率(Sigmoid draw模型)

        draw概率 = draw_base × exp(-|rating_diff| / 600)
        差值0→draw≈26%, 差值200→draw≈14%, 差值400→draw≈7%
        """
        if home_advantage is None:
            home_advantage = self.HOME_ADVANTAGE
        rating_diff = (home_elo + home_advantage) - away_elo
        expected = 1 / (1 + 10 ** (-rating_diff / self.SCALE_FACTOR))

        draw_base = 0.26
        draw_factor = math.exp(-abs(rating_diff) / 600)
        draw_prob = draw_base * draw_factor

        home_prob = expected * (1 - draw_prob)
        away_prob = (1 - expected) * (1 - draw_prob)

        total = home_prob + draw_prob + away_prob
        return {
            'home_win': round(home_prob / total, 4),
            'draw': round(draw_prob / total, 4),
            'away_win': round(away_prob / total, 4),
        }

    def recalculate_all_elo(
        self,
        from_date: str = None,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        重新计算所有球队的Elo评分
        按时间顺序遍历所有比赛，逐步更新评分

        WARNING: 这是一个耗时操作，建议在后台运行
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 清空现有评分
        cursor.execute("DELETE FROM elo_ratings")
        cursor.execute("DELETE FROM elo_history")

        # 获取所有比赛（按时间排序）
        if from_date:
            cursor.execute("""
                SELECT
                    match_id,
                    match_date,
                    home_team_id,
                    away_team_id,
                    home_goals,
                    away_goals
                FROM matches
                WHERE match_date >= ?
                AND status = 'finished'
                AND home_goals IS NOT NULL
                AND away_goals IS NOT NULL
                ORDER BY match_date ASC
            """, (from_date,))
        else:
            cursor.execute("""
                SELECT
                    match_id,
                    match_date,
                    home_team_id,
                    away_team_id,
                    home_goals,
                    away_goals
                FROM matches
                WHERE status = 'finished'
                AND home_goals IS NOT NULL
                AND away_goals IS NOT NULL
                ORDER BY match_date ASC
            """)

        matches = cursor.fetchall()
        updated_count = 0

        for match in matches:
            try:
                self.update_elo_after_match(
                    match['home_team_id'],
                    match['away_team_id'],
                    match['home_goals'],
                    match['away_goals'],
                    match['match_date'],
                    conn
                )
                updated_count += 1
            except Exception as e:
                print(f"Error updating Elo for match {match['match_id']}: {e}")
                continue

        return {
            'total_matches': len(matches),
            'updated_count': updated_count,
            'message': f'已重新计算 {updated_count} 场比赛的Elo评分'
        }