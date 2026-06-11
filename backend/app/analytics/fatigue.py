"""
球员疲劳度分析模块

功能:
1. 近期出场时间统计
2. 国际比赛日影响
3. 连续首发场次分析
4. 年龄因素考虑
5. 位置差异分析

数据来源:
- matches表 (比赛间隔)
- 球员出场数据 (如有)
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class FatigueInfo:
    """疲劳度信息"""
    team_id: int
    rest_days: int  # 休息天数
    matches_last_7days: int  # 近7天比赛数
    matches_last_14days: int  # 近14天比赛数
    consecutive_starts: int  # 连续首发场次
    international_travel: bool  # 是否有国际比赛
    fatigue_level: str  # low, moderate, high, extreme
    fatigue_factor: float  # 影响系数


class FatigueAnalyzer:
    """疲劳度分析器"""

    # 疲劳阈值
    REST_DAYS_LOW = 3  # 休息<3天 = 高疲劳
    REST_DAYS_MODERATE = 5  # 休息<5天 = 中等疲劳
    MATCHES_HIGH_7DAYS = 2  # 7天内>2场 = 高疲劳
    MATCHES_MODERATE_14DAYS = 4  # 14天内>4场 = 中等疲劳

    # 疲劳影响系数
    FATIGUE_FACTORS = {
        'low': 1.0,  # 无影响
        'moderate': 0.95,  # -5%
        'high': 0.90,  # -10%
        'extreme': 0.85  # -15%
    }

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def calculate_team_fatigue(
        self,
        team_id: int,
        match_date: str,
        conn: sqlite3.Connection = None
    ) -> FatigueInfo:
        """
        计算球队疲劳度

        Args:
            team_id: 球队ID
            match_date: 比赛日期 (YYYY-MM-DD)

        Returns:
            疲劳度信息
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 解析日期
        try:
            target_date = datetime.strptime(match_date, '%Y-%m-%d')
        except:
            return FatigueInfo(
                team_id=team_id,
                rest_days=7,
                matches_last_7days=0,
                matches_last_14days=0,
                consecutive_starts=0,
                international_travel=False,
                fatigue_level='low',
                fatigue_factor=1.0
            )

        # 获取近期比赛
        cursor.execute("""
            SELECT
                match_date,
                home_team_id,
                away_team_id
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
            AND match_date < ?
            AND home_goals IS NOT NULL
            ORDER BY match_date DESC
            LIMIT 10
        """, (team_id, team_id, match_date))

        recent_matches = cursor.fetchall()

        if not recent_matches:
            return FatigueInfo(
                team_id=team_id,
                rest_days=7,
                matches_last_7days=0,
                matches_last_14days=0,
                consecutive_starts=0,
                international_travel=False,
                fatigue_level='low',
                fatigue_factor=1.0
            )

        # 计算休息天数
        last_match_date = datetime.strptime(recent_matches[0]['match_date'], '%Y-%m-%d')
        rest_days = (target_date - last_match_date).days

        # 计算近7天和14天比赛数
        matches_7days = 0
        matches_14days = 0
        for match in recent_matches:
            match_dt = datetime.strptime(match['match_date'], '%Y-%m-%d')
            days_diff = (target_date - match_dt).days
            if days_diff <= 7:
                matches_7days += 1
            if days_diff <= 14:
                matches_14days += 1

        # 计算连续首发 (简化：连续比赛场次)
        consecutive_starts = 0
        for match in recent_matches:
            consecutive_starts += 1
            # 如果间隔>7天，中断
            if consecutive_starts > 1:
                prev_dt = datetime.strptime(recent_matches[consecutive_starts-2]['match_date'], '%Y-%m-%d')
                curr_dt = datetime.strptime(match['match_date'], '%Y-%m-%d')
                if (prev_dt - curr_dt).days > 7:
                    break

        # 判断疲劳等级
        fatigue_level = 'low'
        if rest_days < self.REST_DAYS_LOW or matches_7days >= self.MATCHES_HIGH_7DAYS:
            fatigue_level = 'extreme'
        elif rest_days < self.REST_DAYS_MODERATE or matches_14days >= self.MATCHES_MODERATE_14DAYS:
            fatigue_level = 'high'
        elif matches_7days >= 1 or matches_14days >= 3:
            fatigue_level = 'moderate'

        fatigue_factor = self.FATIGUE_FACTORS[fatigue_level]

        return FatigueInfo(
            team_id=team_id,
            rest_days=rest_days,
            matches_last_7days=matches_7days,
            matches_last_14days=matches_14days,
            consecutive_starts=consecutive_starts,
            international_travel=False,  # 需要额外数据
            fatigue_level=fatigue_level,
            fatigue_factor=fatigue_factor
        )

    def compare_teams_fatigue(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        比较两队疲劳度

        Returns:
            疲劳度对比分析
        """
        if conn is None:
            conn = self.get_connection()

        home_fatigue = self.calculate_team_fatigue(home_team_id, match_date, conn)
        away_fatigue = self.calculate_team_fatigue(away_team_id, match_date, conn)

        # 计算疲劳差异
        rest_diff = home_fatigue.rest_days - away_fatigue.rest_days
        fatigue_diff = home_fatigue.fatigue_factor - away_fatigue.fatigue_factor

        # 判断优势
        if fatigue_diff > 0.05:
            advantage = 'home'
            advantage_desc = '主队体能优势明显'
        elif fatigue_diff < -0.05:
            advantage = 'away'
            advantage_desc = '客队体能优势明显'
        else:
            advantage = 'neutral'
            advantage_desc = '两队体能相当'

        return {
            'home_team': {
                'rest_days': home_fatigue.rest_days,
                'matches_7days': home_fatigue.matches_last_7days,
                'matches_14days': home_fatigue.matches_last_14days,
                'fatigue_level': home_fatigue.fatigue_level,
                'fatigue_factor': home_fatigue.fatigue_factor
            },
            'away_team': {
                'rest_days': away_fatigue.rest_days,
                'matches_7days': away_fatigue.matches_last_7days,
                'matches_14days': away_fatigue.matches_last_14days,
                'fatigue_level': away_fatigue.fatigue_level,
                'fatigue_factor': away_fatigue.fatigue_factor
            },
            'comparison': {
                'rest_days_diff': rest_diff,
                'fatigue_factor_diff': round(fatigue_diff, 3),
                'advantage': advantage,
                'description': advantage_desc
            },
            'impact_on_prediction': {
                'home_adjustment': home_fatigue.fatigue_factor,
                'away_adjustment': away_fatigue.fatigue_factor,
                'net_effect': round(fatigue_diff, 3)
            }
        }

    def get_fatigue_description(self, fatigue: FatigueInfo) -> str:
        """生成疲劳度描述"""
        parts = []

        if fatigue.rest_days <= 2:
            parts.append(f"仅休息{fatigue.rest_days}天")
        elif fatigue.rest_days <= 4:
            parts.append(f"休息{fatigue.rest_days}天")
        else:
            parts.append(f"休息{fatigue.rest_days}天(充足)")

        if fatigue.matches_last_7days >= 2:
            parts.append(f"7天内{fatigue.matches_last_7days}场比赛")
        elif fatigue.matches_last_14days >= 4:
            parts.append(f"14天内{fatigue.matches_last_14days}场比赛")

        if fatigue.fatigue_level == 'extreme':
            parts.append("极度疲劳")
        elif fatigue.fatigue_level == 'high':
            parts.append("疲劳明显")
        elif fatigue.fatigue_level == 'moderate':
            parts.append("轻微疲劳")

        return '，'.join(parts) if parts else '体能充沛'


def main():
    """测试疲劳度分析"""
    db_path = r"d:\football_tools\data\football_v2.db"
    analyzer = FatigueAnalyzer(db_path)

    print("疲劳度分析测试")
    print("=" * 60)

    # 测试疲劳度计算
    conn = analyzer.get_connection()
    cursor = conn.cursor()

    # 获取一个有比赛的球队
    cursor.execute("""
        SELECT DISTINCT home_team_id
        FROM matches
        WHERE home_goals IS NOT NULL
        LIMIT 1
    """)
    team = cursor.fetchone()
    if team:
        fatigue = analyzer.calculate_team_fatigue(team['home_team_id'], '2025-05-20', conn)
        print(f"\n球队{team['home_team_id']}疲劳度:")
        print(f"  休息天数: {fatigue.rest_days}")
        print(f"  7天内比赛: {fatigue.matches_last_7days}")
        print(f"  14天内比赛: {fatigue.matches_last_14days}")
        print(f"  疲劳等级: {fatigue.fatigue_level}")
        print(f"  影响系数: {fatigue.fatigue_factor}")
        print(f"  描述: {analyzer.get_fatigue_description(fatigue)}")

    conn.close()


if __name__ == "__main__":
    main()