"""
价值投注分析模块

功能:
1. 计算预测概率 vs 市场赔率隐含概率
2. 识别价值投注机会
3. Kelly Criterion投注比例计算
4. 赔率变化追踪

价值投注定义:
当预测概率 > 市场隐含概率时，存在价值投注机会
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValueBet:
    """价值投注结果"""
    match_id: str
    market: str  # home_win, draw, away_win
    prediction_probability: float
    implied_probability: float
    odds: float
    edge: float  # 优势百分比
    value_rating: str  # high, medium, low
    kelly_fraction: float  # Kelly投注比例
    expected_value: float  # 期望值
    confidence: float


class ValueBetAnalyzer:
    """价值投注分析器"""

    # 价值投注阈值
    EDGE_THRESHOLD_HIGH = 0.08  # 8%以上优势 = 高价值
    EDGE_THRESHOLD_MEDIUM = 0.05  # 5%以上优势 = 中等价值
    EDGE_THRESHOLD_LOW = 0.03  # 3%以上优势 = 低价值

    # Kelly Criterion参数
    KELLY_FRACTION_MAX = 0.25  # 最大Kelly比例（保守策略）
    KELLY_FRACTION_HALF = 0.125  # 半Kelly（更保守）

    # 最小赔率要求
    MIN_ODDS = 1.5  # 低于此赔率不考虑
    MAX_ODDS = 10.0  # 高于此赔率风险过大

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def calculate_implied_probability(self, odds: float) -> float:
        """
        计算赔率隐含概率

        隐含概率 = 1 / 赔率
        例如: 赔率2.0 → 隐含概率50%
        """
        if odds <= 0:
            return 0
        return 1 / odds

    def calculate_edge(self, prediction_prob: float, odds: float) -> float:
        """
        计算优势 (Edge)

        Edge = 预测概率 - 隐含概率
        正值表示价值投注
        """
        implied_prob = self.calculate_implied_probability(odds)
        return prediction_prob - implied_prob

    def calculate_kelly_criterion(
        self,
        prediction_prob: float,
        odds: float,
        fractional: float = 0.5
    ) -> float:
        """
        Kelly Criterion投注比例计算

        Kelly公式: f = (bp - q) / b
        b = 赔率 - 1 (净赔率)
        p = 预测概率
        q = 1 - p (失败概率)

        fractional: Kelly比例系数 (0.5 = 半Kelly，更保守)
        """
        if odds <= 1:
            return 0

        b = odds - 1  # 净赔率
        p = prediction_prob
        q = 1 - p

        # Kelly公式
        kelly = (b * p - q) / b

        # 负值表示无价值
        if kelly <= 0:
            return 0

        # 应用fractional系数
        kelly *= fractional

        # 限制最大比例
        kelly = min(kelly, self.KELLY_FRACTION_MAX)

        return round(kelly, 4)

    def calculate_expected_value(
        self,
        prediction_prob: float,
        odds: float
    ) -> float:
        """
        计算期望值 (Expected Value)

        EV = (概率 × 赔率) - 1
        正值表示价值投注
        """
        return prediction_prob * odds - 1

    def assess_value_rating(self, edge: float) -> str:
        """评估价值等级"""
        if edge >= self.EDGE_THRESHOLD_HIGH:
            return 'high'
        elif edge >= self.EDGE_THRESHOLD_MEDIUM:
            return 'medium'
        elif edge >= self.EDGE_THRESHOLD_LOW:
            return 'low'
        return 'none'

    def find_value_bets(
        self,
        prediction: Dict,
        odds: Dict,
        match_id: str = None
    ) -> List[ValueBet]:
        """
        查找价值投注

        Args:
            prediction: 预测概率 {'home_win': 0.45, 'draw': 0.25, 'away_win': 0.30}
            odds: 市场赔率 {'home': 2.5, 'draw': 3.2, 'away': 2.8}

        Returns:
            价值投注列表
        """
        value_bets = []

        # 主胜
        if odds.get('home') and odds['home'] >= self.MIN_ODDS:
            home_win_prob = prediction.get('home_win', 0)
            home_odds = odds['home']

            edge = self.calculate_edge(home_win_prob, home_odds)
            if edge > 0:
                vb = ValueBet(
                    match_id=match_id,
                    market='home_win',
                    prediction_probability=home_win_prob,
                    implied_probability=self.calculate_implied_probability(home_odds),
                    odds=home_odds,
                    edge=edge,
                    value_rating=self.assess_value_rating(edge),
                    kelly_fraction=self.calculate_kelly_criterion(home_win_prob, home_odds),
                    expected_value=self.calculate_expected_value(home_win_prob, home_odds),
                    confidence=prediction.get('confidence', 0.5)
                )
                value_bets.append(vb)

        # 平局
        if odds.get('draw') and odds['draw'] >= self.MIN_ODDS:
            draw_prob = prediction.get('draw', 0)
            draw_odds = odds['draw']

            edge = self.calculate_edge(draw_prob, draw_odds)
            if edge > 0:
                vb = ValueBet(
                    match_id=match_id,
                    market='draw',
                    prediction_probability=draw_prob,
                    implied_probability=self.calculate_implied_probability(draw_odds),
                    odds=draw_odds,
                    edge=edge,
                    value_rating=self.assess_value_rating(edge),
                    kelly_fraction=self.calculate_kelly_criterion(draw_prob, draw_odds),
                    expected_value=self.calculate_expected_value(draw_prob, draw_odds),
                    confidence=prediction.get('confidence', 0.5)
                )
                value_bets.append(vb)

        # 客胜
        if odds.get('away') and odds['away'] >= self.MIN_ODDS:
            away_win_prob = prediction.get('away_win', 0)
            away_odds = odds['away']

            edge = self.calculate_edge(away_win_prob, away_odds)
            if edge > 0:
                vb = ValueBet(
                    match_id=match_id,
                    market='away_win',
                    prediction_probability=away_win_prob,
                    implied_probability=self.calculate_implied_probability(away_odds),
                    odds=away_odds,
                    edge=edge,
                    value_rating=self.assess_value_rating(edge),
                    kelly_fraction=self.calculate_kelly_criterion(away_win_prob, away_odds),
                    expected_value=self.calculate_expected_value(away_win_prob, away_odds),
                    confidence=prediction.get('confidence', 0.5)
                )
                value_bets.append(vb)

        # 按优势排序
        value_bets.sort(key=lambda x: x.edge, reverse=True)

        return value_bets

    def analyze_match_value_bets(
        self,
        match_id: str,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析比赛的价值投注机会

        整合预测和赔率数据
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取比赛预测和赔率
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                ht.name_en as home_team,
                at.name_en as away_team,
                mo.home as home_odds,
                mo.draw as draw_odds,
                mo.away as away_odds,
                mo.bookmaker
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            LEFT JOIN match_odds_normalized mo ON m.match_id = mo.match_id
                AND mo.bookmaker = 'PINNACLE' AND mo.snapshot_type = 'prematch' AND mo.market = '1X2'
            WHERE m.match_id = ?
            LIMIT 1
        """, (match_id,))

        match = cursor.fetchone()
        if not match:
            return {'error': '比赛不存在'}

        # 如果没有赔率数据，返回空
        if not match['home_odds']:
            return {
                'match_id': match_id,
                'home_team': match['home_team'],
                'away_team': match['away_team'],
                'has_odds': False,
                'message': '该比赛暂无赔率数据'
            }

        # 获取预测概率（从综合预测或简单计算）
        # 这里使用简单的基于赔率的预测作为示例
        # 实际应该调用comprehensive_prediction

        odds = {
            'home': match['home_odds'],
            'draw': match['draw_odds'],
            'away': match['away_odds']
        }

        # 计算预测概率（基于历史数据的简单估算）
        # 实际应该使用Elo/Poisson等预测模型
        prediction = self._estimate_prediction(match['home_team_id'], match['away_team_id'], conn)

        # 查找价值投注
        value_bets = self.find_value_bets(prediction, odds, match_id)

        return {
            'match_id': match_id,
            'match_date': match['match_date'],
            'home_team': match['home_team'],
            'away_team': match['away_team'],
            'bookmaker': match['bookmaker'],
            'odds': odds,
            'prediction': prediction,
            'has_odds': True,
            'value_bets': [
                {
                    'market': vb.market,
                    'prediction_prob': round(vb.prediction_probability * 100, 1),
                    'implied_prob': round(vb.implied_probability * 100, 1),
                    'odds': vb.odds,
                    'edge': round(vb.edge * 100, 1),
                    'value_rating': vb.value_rating,
                    'kelly_fraction': round(vb.kelly_fraction * 100, 1),
                    'expected_value': round(vb.expected_value * 100, 1),
                    'recommendation': self._generate_recommendation(vb)
                } for vb in value_bets
            ],
            'summary': self._generate_summary(value_bets)
        }

    def _estimate_prediction(
        self,
        home_team_id: int,
        away_team_id: int,
        conn: sqlite3.Connection
    ) -> Dict:
        """
        估算预测概率

        使用Elo评分进行简单估算
        """
        cursor = conn.cursor()

        # 获取Elo评分
        cursor.execute("""
            SELECT elo_rating FROM elo_ratings
            WHERE team_id = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (home_team_id,))
        home_elo = cursor.fetchone()
        home_elo = float(home_elo['elo_rating']) if home_elo else 1500

        cursor.execute("""
            SELECT elo_rating FROM elo_ratings
            WHERE team_id = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (away_team_id,))
        away_elo = cursor.fetchone()
        away_elo = float(away_elo['elo_rating']) if away_elo else 1500

        # Elo预测公式
        diff = home_elo - away_elo + 100  # 加主场优势

        # 简化的Elo概率计算
        home_win_prob = 1 / (1 + 10 ** (-diff / 400))

        # 估算平局和客胜概率
        # 简化模型：平局约25%，剩余为客胜
        draw_prob = 0.25
        away_win_prob = 1 - home_win_prob - draw_prob

        # 标准化
        total = home_win_prob + draw_prob + away_win_prob
        home_win_prob /= total
        draw_prob /= total
        away_win_prob /= total

        return {
            'home_win': round(home_win_prob, 4),
            'draw': round(draw_prob, 4),
            'away_win': round(away_win_prob, 4),
            'confidence': 0.6
        }

    def _generate_recommendation(self, vb: ValueBet) -> str:
        """生成投注建议"""
        if vb.value_rating == 'high':
            return f"强烈推荐: {vb.market} @ {vb.odds}，优势{vb.edge*100:.1f}%"
        elif vb.value_rating == 'medium':
            return f"推荐考虑: {vb.market} @ {vb.odds}，有一定价值"
        elif vb.value_rating == 'low':
            return f"谨慎考虑: {vb.market} @ {vb.odds}，价值较小"
        return "无价值投注"

    def _generate_summary(self, value_bets: List[ValueBet]) -> str:
        """生成分析摘要"""
        if not value_bets:
            return "当前赔率无明显价值投注机会"

        high_value = [vb for vb in value_bets if vb.value_rating == 'high']
        medium_value = [vb for vb in value_bets if vb.value_rating == 'medium']

        summary_parts = []
        if high_value:
            summary_parts.append(f"发现{len(high_value)}个高价值机会")
        if medium_value:
            summary_parts.append(f"发现{len(medium_value)}个中等价值机会")

        if summary_parts:
            return "，".join(summary_parts)

        return "仅有低价值机会，建议谨慎"

    def scan_upcoming_value_bets(
        self,
        days: int = 7,
        min_edge: float = 0.05,
        conn: sqlite3.Connection = None
    ) -> List[Dict]:
        """
        扫描未来比赛的价值投注机会

        Args:
            days: 扫描未来N天
            min_edge: 最小优势阈值

        Returns:
            价值投注列表
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取有赔率的未来比赛
        cursor.execute("""
            SELECT DISTINCT m.match_id
            FROM matches m
            JOIN match_odds_normalized o ON m.match_id = o.match_id
                AND o.bookmaker = 'PINNACLE' AND o.snapshot_type = 'prematch' AND o.market = '1X2'
            WHERE m.match_date >= date('now')
            AND m.match_date <= date('now', ?)
            AND m.home_goals IS NULL
            ORDER BY m.match_date
        """, (f'+{days} days',))

        matches = cursor.fetchall()

        all_value_bets = []

        for match in matches:
            analysis = self.analyze_match_value_bets(match['match_id'], conn)
            if analysis.get('value_bets'):
                # 只保留优势大于阈值的
                filtered = [
                    vb for vb in analysis['value_bets']
                    if vb['edge'] >= min_edge * 100
                ]
                if filtered:
                    all_value_bets.append({
                        'match_id': match['match_id'],
                        'match_date': analysis['match_date'],
                        'home_team': analysis['home_team'],
                        'away_team': analysis['away_team'],
                        'value_bets': filtered
                    })

        return all_value_bets

    def calculate_arbitrage_opportunity(
        self,
        odds_list: List[Dict]
    ) -> Optional[Dict]:
        """
        计算套利机会

        当不同庄家的赔率组合使得隐含概率总和<100%时存在套利

        Args:
            odds_list: 多个庄家的赔率列表
            [{'bookmaker': 'bet365', 'home': 2.5, 'draw': 3.2, 'away': 2.8}, ...]

        Returns:
            套利机会详情
        """
        # 找出每个市场的最高赔率
        best_home = max(odds_list, key=lambda x: x.get('home', 0))
        best_draw = max(odds_list, key=lambda x: x.get('draw', 0))
        best_away = max(odds_list, key=lambda x: x.get('away', 0))

        home_odds = best_home.get('home', 0)
        draw_odds = best_draw.get('draw', 0)
        away_odds = best_away.get('away', 0)

        if home_odds <= 0 or draw_odds <= 0 or away_odds <= 0:
            return None

        # 计算隐含概率总和
        implied_sum = (
            self.calculate_implied_probability(home_odds) +
            self.calculate_implied_probability(draw_odds) +
            self.calculate_implied_probability(away_odds)
        )

        # 套利条件: 隐含概率总和 < 1
        if implied_sum >= 1:
            return None

        # 计算套利利润率
        arbitrage_margin = 1 - implied_sum

        # 计算投注比例
        home_stake = self.calculate_implied_probability(home_odds) / implied_sum
        draw_stake = self.calculate_implied_probability(draw_odds) / implied_sum
        away_stake = self.calculate_implied_probability(away_odds) / implied_sum

        return {
            'has_arbitrage': True,
            'arbitrage_margin': round(arbitrage_margin * 100, 2),
            'best_odds': {
                'home': {'odds': home_odds, 'bookmaker': best_home['bookmaker']},
                'draw': {'odds': draw_odds, 'bookmaker': best_draw['bookmaker']},
                'away': {'odds': away_odds, 'bookmaker': best_away['bookmaker']}
            },
            'bet_allocation': {
                'home': round(home_stake * 100, 1),
                'draw': round(draw_stake * 100, 1),
                'away': round(away_stake * 100, 1)
            },
            'guaranteed_profit': round(arbitrage_margin * 100, 2)
        }


def main():
    """测试价值投注分析"""
    db_path = r"d:\football_tools\data\football_v2.db"
    analyzer = ValueBetAnalyzer(db_path)

    print("价值投注分析测试")
    print("=" * 60)

    # 测试Kelly Criterion
    print("\n[Kelly Criterion计算示例]")
    test_cases = [
        (0.5, 2.0),   # 50%概率，赔率2.0
        (0.4, 2.5),   # 40%概率，赔率2.5
        (0.3, 3.5),   # 30%概率，赔率3.5
    ]

    for prob, odds in test_cases:
        kelly = analyzer.calculate_kelly_criterion(prob, odds)
        edge = analyzer.calculate_edge(prob, odds)
        ev = analyzer.calculate_expected_value(prob, odds)
        print(f"  概率{prob*100}% + 赔率{odds}: Kelly={kelly*100:.1f}%, Edge={edge*100:.1f}%, EV={ev*100:.1f}%")

    # 测试价值投注查找
    print("\n[价值投注查找示例]")
    prediction = {'home_win': 0.45, 'draw': 0.25, 'away_win': 0.30}
    odds = {'home': 2.5, 'draw': 3.5, 'away': 2.8}

    value_bets = analyzer.find_value_bets(prediction, odds)
    for vb in value_bets:
        print(f"  {vb.market}: 预测{vb.prediction_probability*100:.1f}% vs 隐含{vb.implied_probability*100:.1f}%")
        print(f"    Edge={vb.edge*100:.1f}%, Kelly={vb.kelly_fraction*100:.1f}%")
        print(f"    评级: {vb.value_rating}")


if __name__ == "__main__":
    main()