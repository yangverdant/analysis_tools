"""
AI预测增强模块

功能:
1. 基于历史数据的特征工程
2. 简单机器学习模型预测
3. 与传统预测结果融合
4. 模型评估和优化

使用方法:
- 不依赖复杂ML库，使用简单统计方法
- 可扩展为更复杂的模型
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import math


@dataclass
class MatchFeatures:
    """比赛特征"""
    home_elo: float
    away_elo: float
    elo_diff: float
    home_form_points: float  # 近10场场均积分
    away_form_points: float
    home_home_win_rate: float  # 主队主场胜率
    away_away_win_rate: float  # 客队客场胜率
    h2h_home_wins: int  # 交锋主胜数
    h2h_total: int
    home_avg_goals: float  # 主队场均进球
    away_avg_goals: float
    home_avg_conceded: float  # 主队场均失球
    away_avg_conceded: float
    rest_days_diff: int  # 休息天数差
    motivation_diff: float  # 动机差异


class MLPredictor:
    """机器学习预测器"""

    # 特征权重 (基于经验调优)
    FEATURE_WEIGHTS = {
        'elo_diff': 0.25,
        'form_diff': 0.15,
        'home_advantage': 0.12,
        'h2h_factor': 0.08,
        'attack_strength': 0.10,
        'defense_strength': 0.10,
        'rest_factor': 0.05,
        'motivation_factor': 0.05
    }

    # 历史数据统计 (用于特征标准化)
    ELO_MEAN = 1500
    ELO_STD = 200

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def extract_features(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        conn: sqlite3.Connection = None
    ) -> MatchFeatures:
        """
        提取比赛特征

        Args:
            home_team_id: 主队ID
            away_team_id: 客队ID
            match_date: 比赛日期

        Returns:
            比赛特征向量
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 1. Elo评分
        def get_elo(team_id):
            cursor.execute("""
                SELECT elo_rating FROM elo_ratings
                WHERE team_id = ?
                LIMIT 1
            """, (team_id,))
            result = cursor.fetchone()
            return float(result['elo_rating']) if result else 1500

        home_elo = get_elo(home_team_id)
        away_elo = get_elo(away_team_id)
        elo_diff = home_elo - away_elo

        # 2. 近期状态
        def get_form_points(team_id, limit=10):
            cursor.execute("""
                SELECT
                    SUM(CASE
                        WHEN (home_team_id = ? AND home_goals > away_goals) OR
                             (away_team_id = ? AND away_goals > home_goals) THEN 3
                        WHEN home_goals = away_goals THEN 1
                        ELSE 0
                    END) as points,
                    COUNT(*) as matches
                FROM (
                    SELECT * FROM matches
                    WHERE (home_team_id = ? OR away_team_id = ?)
                    AND home_goals IS NOT NULL
                    AND match_date < ?
                    ORDER BY match_date DESC
                    LIMIT ?
                )
            """, (team_id, team_id, team_id, team_id, match_date, limit))
            result = cursor.fetchone()
            return (result['points'] or 0) / (result['matches'] or 1)

        home_form_points = get_form_points(home_team_id)
        away_form_points = get_form_points(away_team_id)

        # 3. 主客场胜率
        def get_home_win_rate(team_id, limit=20):
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as wins,
                    COUNT(*) as matches
                FROM (
                    SELECT * FROM matches
                    WHERE home_team_id = ?
                    AND home_goals IS NOT NULL
                    AND match_date < ?
                    ORDER BY match_date DESC
                    LIMIT ?
                )
            """, (team_id, match_date, limit))
            result = cursor.fetchone()
            return (result['wins'] or 0) / (result['matches'] or 1)

        def get_away_win_rate(team_id, limit=20):
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN away_goals > home_goals THEN 1 ELSE 0 END) as wins,
                    COUNT(*) as matches
                FROM (
                    SELECT * FROM matches
                    WHERE away_team_id = ?
                    AND away_goals IS NOT NULL
                    AND match_date < ?
                    ORDER BY match_date DESC
                    LIMIT ?
                )
            """, (team_id, match_date, limit))
            result = cursor.fetchone()
            return (result['wins'] or 0) / (result['matches'] or 1)

        home_home_win_rate = get_home_win_rate(home_team_id)
        away_away_win_rate = get_away_win_rate(away_team_id)

        # 4. 交锋记录
        cursor.execute("""
            SELECT
                SUM(CASE WHEN home_goals > away_goals AND home_team_id = ? THEN 1
                         WHEN away_goals > home_goals AND away_team_id = ? THEN 1
                         ELSE 0 END) as home_wins,
                COUNT(*) as total
            FROM matches
            WHERE ((home_team_id = ? AND away_team_id = ?) OR
                   (home_team_id = ? AND away_team_id = ?))
            AND home_goals IS NOT NULL
            AND match_date < ?
            LIMIT 10
        """, (home_team_id, home_team_id, home_team_id, away_team_id, away_team_id, home_team_id, match_date))
        h2h = cursor.fetchone()
        h2h_home_wins = h2h['home_wins'] or 0
        h2h_total = h2h['total'] or 0

        # 5. 进球/失球统计
        def get_goals_stats(team_id, limit=20):
            cursor.execute("""
                SELECT
                    AVG(CASE WHEN home_team_id = ? THEN home_goals ELSE away_goals END) as avg_goals,
                    AVG(CASE WHEN home_team_id = ? THEN away_goals ELSE home_goals END) as avg_conceded
                FROM (
                    SELECT * FROM matches
                    WHERE (home_team_id = ? OR away_team_id = ?)
                    AND home_goals IS NOT NULL
                    AND match_date < ?
                    ORDER BY match_date DESC
                    LIMIT ?
                )
            """, (team_id, team_id, team_id, team_id, match_date, limit))
            result = cursor.fetchone()
            return result['avg_goals'] or 1.5, result['avg_conceded'] or 1.0

        home_avg_goals, home_avg_conceded = get_goals_stats(home_team_id)
        away_avg_goals, away_avg_conceded = get_goals_stats(away_team_id)

        # 6. 休息天数
        def get_rest_days(team_id, before_date):
            cursor.execute("""
                SELECT MAX(match_date) as last_match
                FROM matches
                WHERE (home_team_id = ? OR away_team_id = ?)
                AND match_date < ?
                AND home_goals IS NOT NULL
            """, (team_id, team_id, before_date))
            result = cursor.fetchone()
            if result and result['last_match']:
                last = datetime.strptime(result['last_match'], '%Y-%m-%d')
                target = datetime.strptime(before_date, '%Y-%m-%d')
                return (target - last).days
            return 7

        home_rest = get_rest_days(home_team_id, match_date)
        away_rest = get_rest_days(away_team_id, match_date)
        rest_days_diff = home_rest - away_rest

        # 7. 动机差异 (简化计算)
        motivation_diff = 0  # 需要motivation模块

        return MatchFeatures(
            home_elo=home_elo,
            away_elo=away_elo,
            elo_diff=elo_diff,
            home_form_points=home_form_points,
            away_form_points=away_form_points,
            home_home_win_rate=home_home_win_rate,
            away_away_win_rate=away_away_win_rate,
            h2h_home_wins=h2h_home_wins,
            h2h_total=h2h_total,
            home_avg_goals=home_avg_goals,
            away_avg_goals=away_avg_goals,
            home_avg_conceded=home_avg_conceded,
            away_avg_conceded=away_avg_conceded,
            rest_days_diff=rest_days_diff,
            motivation_diff=motivation_diff
        )

    def predict_with_features(self, features: MatchFeatures) -> Dict:
        """
        使用特征进行预测

        采用加权评分模型

        Args:
            features: 比赛特征

        Returns:
            预测结果
        """
        # 计算各维度得分

        # 1. Elo差异得分
        elo_score = features.elo_diff / self.ELO_STD  # 标准化
        elo_factor = self.FEATURE_WEIGHTS['elo_diff'] * elo_score

        # 2. 状态差异得分
        form_diff = features.home_form_points - features.away_form_points
        form_factor = self.FEATURE_WEIGHTS['form_diff'] * form_diff / 3  # 标准化到0-1

        # 3. 主场优势得分
        home_advantage = features.home_home_win_rate - features.away_away_win_rate + 0.1  # +10%主场优势
        home_factor = self.FEATURE_WEIGHTS['home_advantage'] * home_advantage

        # 4. 交锋得分
        if features.h2h_total > 0:
            h2h_rate = features.h2h_home_wins / features.h2h_total
            h2h_factor = self.FEATURE_WEIGHTS['h2h_factor'] * (h2h_rate - 0.5) * 2
        else:
            h2h_factor = 0

        # 5. 进攻强度得分
        attack_diff = features.home_avg_goals - features.away_avg_goals
        attack_factor = self.FEATURE_WEIGHTS['attack_strength'] * attack_diff / 2

        # 6. 防守强度得分
        defense_diff = features.away_avg_conceded - features.home_avg_conceded
        defense_factor = self.FEATURE_WEIGHTS['defense_strength'] * defense_diff / 2

        # 7. 休息得分
        if features.rest_days_diff > 2:
            rest_factor = self.FEATURE_WEIGHTS['rest_factor'] * 0.1
        elif features.rest_days_diff < -2:
            rest_factor = self.FEATURE_WEIGHTS['rest_factor'] * -0.1
        else:
            rest_factor = 0

        # 综合得分
        total_score = elo_factor + form_factor + home_factor + h2h_factor + attack_factor + defense_factor + rest_factor

        # 转换为概率
        # 使用sigmoid函数
        home_win_prob = 1 / (1 + math.exp(-total_score * 3))

        # 平局概率 (基础25%，根据实力差距调整)
        draw_base = 0.25
        draw_adjust = abs(total_score) * 0.1  # 实力差距大，平局概率低
        draw_prob = draw_base - draw_adjust

        # 客胜概率
        away_win_prob = 1 - home_win_prob - draw_prob

        # 标准化
        total = home_win_prob + draw_prob + away_win_prob
        home_win_prob /= total
        draw_prob /= total
        away_win_prob /= total

        return {
            'home_win_prob': round(home_win_prob * 100, 1),
            'draw_prob': round(draw_prob * 100, 1),
            'away_win_prob': round(away_win_prob * 100, 1),
            'features_used': {
                'elo_diff': round(features.elo_diff, 0),
                'form_diff': round(form_diff, 2),
                'home_win_rate': round(features.home_home_win_rate * 100, 1),
                'away_win_rate': round(features.away_away_win_rate * 100, 1),
                'h2h_home_wins': features.h2h_home_wins,
                'h2h_total': features.h2h_total,
                'home_avg_goals': round(features.home_avg_goals, 2),
                'away_avg_goals': round(features.away_avg_goals, 2),
                'rest_days_diff': features.rest_days_diff
            },
            'feature_scores': {
                'elo_factor': round(elo_factor * 100, 1),
                'form_factor': round(form_factor * 100, 1),
                'home_factor': round(home_factor * 100, 1),
                'h2h_factor': round(h2h_factor * 100, 1),
                'attack_factor': round(attack_factor * 100, 1),
                'defense_factor': round(defense_factor * 100, 1),
                'rest_factor': round(rest_factor * 100, 1)
            },
            'total_score': round(total_score, 3),
            'model_type': 'weighted_features'
        }

    def blend_predictions(
        self,
        ml_prediction: Dict,
        elo_prediction: Dict,
        poisson_prediction: Dict,
        weights: Dict = None
    ) -> Dict:
        """
        融合多个预测结果

        Args:
            ml_prediction: ML模型预测
            elo_prediction: Elo预测
            poisson_prediction: Poisson预测
            weights: 融合权重

        Returns:
            融合后的预测
        """
        if weights is None:
            weights = {
                'ml': 0.35,
                'elo': 0.35,
                'poisson': 0.30
            }

        # 融合概率
        home_win = (
            ml_prediction['home_win_prob'] * weights['ml'] +
            elo_prediction.get('home_win_prob', 50) * weights['elo'] +
            poisson_prediction.get('home_win_prob', 50) * weights['poisson']
        )

        draw = (
            ml_prediction['draw_prob'] * weights['ml'] +
            elo_prediction.get('draw_prob', 25) * weights['elo'] +
            poisson_prediction.get('draw_prob', 25) * weights['poisson']
        )

        away_win = (
            ml_prediction['away_win_prob'] * weights['ml'] +
            elo_prediction.get('away_win_prob', 50) * weights['elo'] +
            poisson_prediction.get('away_win_prob', 50) * weights['poisson']
        )

        # 标准化
        total = home_win + draw + away_win
        home_win /= total
        draw /= total
        away_win /= total

        return {
            'home_win_prob': round(home_win, 1),
            'draw_prob': round(draw, 1),
            'away_win_prob': round(away_win, 1),
            'blend_weights': weights,
            'source_predictions': {
                'ml': ml_prediction,
                'elo': elo_prediction,
                'poisson': poisson_prediction
            },
            'confidence': self._calculate_confidence(ml_prediction, elo_prediction, poisson_prediction)
        }

    def _calculate_confidence(self, ml_pred, elo_pred, poisson_pred) -> str:
        """计算预测置信度"""
        # 检查各模型预测的一致性
        ml_home = ml_pred['home_win_prob']
        elo_home = elo_pred.get('home_win_prob', 50)
        poisson_home = poisson_pred.get('home_win_prob', 50)

        # 计算差异
        diff_ml_elo = abs(ml_home - elo_home)
        diff_ml_poisson = abs(ml_home - poisson_home)

        avg_diff = (diff_ml_elo + diff_ml_poisson) / 2

        if avg_diff < 5:
            return 'high'
        elif avg_diff < 10:
            return 'medium'
        else:
            return 'low'

    def predict_match(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        预测比赛结果

        整合特征提取、ML预测、融合
        """
        if conn is None:
            conn = self.get_connection()

        # 提取特征
        features = self.extract_features(home_team_id, away_team_id, match_date, conn)

        # ML预测
        ml_prediction = self.predict_with_features(features)

        return {
            'match_date': match_date,
            'ml_prediction': ml_prediction,
            'features': features,
            'model_version': 'v1.0'
        }


def main():
    """测试ML预测"""
    db_path = r"d:\football_tools\data\football_v2.db"
    predictor = MLPredictor(db_path)

    print("ML预测测试")
    print("=" * 60)

    conn = predictor.get_connection()
    cursor = conn.cursor()

    # 获取一场比赛测试
    cursor.execute("""
        SELECT match_id, match_date, home_team_id, away_team_id
        FROM matches
        WHERE home_goals IS NULL
        LIMIT 1
    """)
    match = cursor.fetchone()

    if match:
        result = predictor.predict_match(
            match['home_team_id'],
            match['away_team_id'],
            match['match_date'],
            conn
        )

        print(f"\n比赛: {match['match_id']}")
        print(f"日期: {match['match_date']}")

        pred = result['ml_prediction']
        print(f"\nML预测:")
        print(f"  主胜: {pred['home_win_prob']}%")
        print(f"  平局: {pred['draw_prob']}%")
        print(f"  客胜: {pred['away_win_prob']}%")

        print(f"\n特征得分:")
        for k, v in pred['feature_scores'].items():
            print(f"  {k}: {v}%")

        print(f"\n综合得分: {pred['total_score']}")

    conn.close()


if __name__ == "__main__":
    main()