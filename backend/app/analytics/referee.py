"""
裁判分析模块

功能:
1. 裁判历史统计 (黄牌、红牌、点球)
2. 主队/客队执法差异
3. 裁判风格分析 (严厉/宽松)
4. 对比赛的影响评估

数据来源:
- matches.referee字段
- 历史比赛统计
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class RefereeStats:
    """裁判统计数据"""
    referee_name: str
    total_matches: int
    avg_yellow_cards: float
    avg_red_cards: float
    avg_penalties: float
    home_win_rate: float
    away_win_rate: float
    draw_rate: float
    strictness: str  # strict, moderate, lenient
    home_bias: float  # 主场偏向系数


class RefereeAnalyzer:
    """裁判分析器"""

    # 裁判风格阈值
    STRICT_THRESHOLD = 4.0  # 场均黄牌>4 = 严厉
    LENIENT_THRESHOLD = 2.5  # 场均黄牌<2.5 = 宽松

    # 主场偏向阈值
    HOME_BIAS_HIGH = 0.1  # 主胜率比客胜率高10%以上 = 明显主场偏向
    HOME_BIAS_LOW = -0.05  # 客胜率更高 = 客场偏向

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_referee_stats(self, referee_name: str, conn: sqlite3.Connection = None) -> Optional[RefereeStats]:
        """
        获取裁判统计数据

        Args:
            referee_name: 裁判姓名
            conn: 数据库连接

        Returns:
            裁判统计数据
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 查询裁判执法的所有比赛
        cursor.execute("""
            SELECT
                m.match_id,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                m.home_yellow,
                m.away_yellow,
                m.home_red,
                m.away_red
            FROM matches m
            WHERE m.referee = ?
            AND m.home_goals IS NOT NULL
        """, (referee_name,))

        matches = cursor.fetchall()

        if not matches:
            return None

        total_matches = len(matches)
        total_yellow = 0
        total_red = 0
        home_wins = 0
        away_wins = 0
        draws = 0

        for match in matches:
            # 黄牌
            home_yellow = match['home_yellow'] or 0
            away_yellow = match['away_yellow'] or 0
            total_yellow += home_yellow + away_yellow

            # 红牌
            home_red = match['home_red'] or 0
            away_red = match['away_red'] or 0
            total_red += home_red + away_red

            # 比赛结果
            if match['home_goals'] > match['away_goals']:
                home_wins += 1
            elif match['home_goals'] < match['away_goals']:
                away_wins += 1
            else:
                draws += 1

        # 计算平均值
        avg_yellow = total_yellow / total_matches
        avg_red = total_red / total_matches

        # 胜率
        home_win_rate = home_wins / total_matches
        away_win_rate = away_wins / total_matches
        draw_rate = draws / total_matches

        # 判断风格
        if avg_yellow >= self.STRICT_THRESHOLD:
            strictness = 'strict'
        elif avg_yellow <= self.LENIENT_THRESHOLD:
            strictness = 'lenient'
        else:
            strictness = 'moderate'

        # 主场偏向
        home_bias = home_win_rate - away_win_rate

        return RefereeStats(
            referee_name=referee_name,
            total_matches=total_matches,
            avg_yellow_cards=round(avg_yellow, 2),
            avg_red_cards=round(avg_red, 3),
            avg_penalties=0,  # 需要事件数据
            home_win_rate=round(home_win_rate, 3),
            away_win_rate=round(away_win_rate, 3),
            draw_rate=round(draw_rate, 3),
            strictness=strictness,
            home_bias=round(home_bias, 3)
        )

    def get_referee_list(self, limit: int = 50, conn: sqlite3.Connection = None) -> List[Dict]:
        """获取裁判列表及统计"""
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 按执法场次排序
        cursor.execute("""
            SELECT
                referee,
                COUNT(*) as match_count
            FROM matches
            WHERE referee IS NOT NULL
            AND referee != ''
            AND home_goals IS NOT NULL
            GROUP BY referee
            ORDER BY match_count DESC
            LIMIT ?
        """, (limit,))

        referees = []
        for row in cursor.fetchall():
            stats = self.get_referee_stats(row['referee'], conn)
            if stats:
                referees.append({
                    'name': stats.referee_name,
                    'matches': stats.total_matches,
                    'avg_yellow': stats.avg_yellow_cards,
                    'avg_red': stats.avg_red_cards,
                    'home_win_rate': stats.home_win_rate,
                    'strictness': stats.strictness,
                    'home_bias': stats.home_bias
                })

        return referees

    def analyze_referee_impact(
        self,
        referee_name: str,
        home_team_id: int,
        away_team_id: int,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析裁判对比赛的影响

        Args:
            referee_name: 裁判姓名
            home_team_id: 主队ID
            away_team_id: 客队ID

        Returns:
            裁判影响分析
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取裁判整体统计
        overall_stats = self.get_referee_stats(referee_name, conn)

        if not overall_stats:
            return {
                'referee': referee_name,
                'has_data': False,
                'message': '该裁判暂无历史执法数据'
            }

        # 获取裁判对主队的执法历史
        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                AVG(home_yellow) as avg_yellow_for,
                AVG(away_yellow) as avg_yellow_against
            FROM matches
            WHERE referee = ?
            AND home_team_id = ?
            AND home_goals IS NOT NULL
        """, (referee_name, home_team_id))

        home_history = cursor.fetchone()

        # 获取裁判对客队的执法历史
        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(CASE WHEN away_goals > home_goals THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                AVG(away_yellow) as avg_yellow_for,
                AVG(home_yellow) as avg_yellow_against
            FROM matches
            WHERE referee = ?
            AND away_team_id = ?
            AND home_goals IS NOT NULL
        """, (referee_name, away_team_id))

        away_history = cursor.fetchone()

        # 分析影响
        impact = {
            'strictness_impact': self._analyze_strictness_impact(overall_stats),
            'home_bias_impact': self._analyze_home_bias_impact(overall_stats),
            'team_history': {}
        }

        # 主队历史
        if home_history and home_history['matches'] > 0:
            home_win_rate = home_history['wins'] / home_history['matches']
            impact['team_history']['home'] = {
                'matches': home_history['matches'],
                'wins': home_history['wins'],
                'draws': home_history['draws'],
                'win_rate': round(home_win_rate, 3),
                'avg_yellow_for': round(home_history['avg_yellow_for'] or 0, 2),
                'avg_yellow_against': round(home_history['avg_yellow_against'] or 0, 2)
            }

        # 客队历史
        if away_history and away_history['matches'] > 0:
            away_win_rate = away_history['wins'] / away_history['matches']
            impact['team_history']['away'] = {
                'matches': away_history['matches'],
                'wins': away_history['wins'],
                'draws': away_history['draws'],
                'win_rate': round(away_win_rate, 3),
                'avg_yellow_for': round(away_history['avg_yellow_for'] or 0, 2),
                'avg_yellow_against': round(away_history['avg_yellow_against'] or 0, 2)
            }

        return {
            'referee': referee_name,
            'has_data': True,
            'overall_stats': {
                'matches': overall_stats.total_matches,
                'avg_yellow': overall_stats.avg_yellow_cards,
                'avg_red': overall_stats.avg_red_cards,
                'home_win_rate': overall_stats.home_win_rate,
                'away_win_rate': overall_stats.away_win_rate,
                'draw_rate': overall_stats.draw_rate,
                'strictness': overall_stats.strictness,
                'home_bias': overall_stats.home_bias
            },
            'impact': impact,
            'summary': self._generate_summary(overall_stats, impact)
        }

    def _analyze_strictness_impact(self, stats: RefereeStats) -> Dict:
        """分析裁判严厉程度的影响"""
        if stats.strictness == 'strict':
            return {
                'level': 'high',
                'description': f"严厉裁判: 场均{stats.avg_yellow_cards}张黄牌",
                'impact': "可能导致更多黄牌、红牌，影响比赛节奏",
                'factor': 0.95  # 进球可能略降
            }
        elif stats.strictness == 'lenient':
            return {
                'level': 'low',
                'description': f"宽松裁判: 场均{stats.avg_yellow_cards}张黄牌",
                'impact': "比赛流畅度高，对抗激烈",
                'factor': 1.02
            }
        else:
            return {
                'level': 'moderate',
                'description': f"适中裁判: 场均{stats.avg_yellow_cards}张黄牌",
                'impact': "执法平衡，影响中性",
                'factor': 1.0
            }

    def _analyze_home_bias_impact(self, stats: RefereeStats) -> Dict:
        """分析裁判主场偏向"""
        if stats.home_bias >= self.HOME_BIAS_HIGH:
            return {
                'level': 'home_favor',
                'description': f"主场偏向: 主胜率{stats.home_win_rate*100:.1f}%",
                'impact': "可能对主队有利",
                'factor': 1.02
            }
        elif stats.home_bias <= self.HOME_BIAS_LOW:
            return {
                'level': 'away_favor',
                'description': f"客场偏向: 客胜率{stats.away_win_rate*100:.1f}%",
                'impact': "可能对客队有利",
                'factor': 0.98
            }
        else:
            return {
                'level': 'neutral',
                'description': "执法公正",
                'impact': "无明显偏向",
                'factor': 1.0
            }

    def _generate_summary(self, stats: RefereeStats, impact: Dict) -> str:
        """生成分析摘要"""
        parts = []

        # 风格
        if stats.strictness == 'strict':
            parts.append("执法严厉")
        elif stats.strictness == 'lenient':
            parts.append("执法宽松")
        else:
            parts.append("执法适中")

        # 偏向
        if stats.home_bias >= self.HOME_BIAS_HIGH:
            parts.append("主场偏向明显")
        elif stats.home_bias <= self.HOME_BIAS_LOW:
            parts.append("客场偏向明显")

        # 历史数据
        if impact['team_history'].get('home') or impact['team_history'].get('away'):
            parts.append("有历史执法记录")

        return "，".join(parts) if parts else "数据不足"


def main():
    """测试裁判分析"""
    db_path = r"d:\football_tools\data\football_v2.db"
    analyzer = RefereeAnalyzer(db_path)

    print("裁判分析测试")
    print("=" * 60)

    # 获取裁判列表
    print("\n[执法场次最多的裁判]")
    referees = analyzer.get_referee_list(limit=10)
    for ref in referees:
        print(f"  {ref['name']}: {ref['matches']}场, 场均黄牌{ref['avg_yellow']}, {ref['strictness']}")

    # 分析具体裁判
    if referees:
        ref_name = referees[0]['name']
        print(f"\n[裁判详情: {ref_name}]")
        stats = analyzer.get_referee_stats(ref_name)
        if stats:
            print(f"  执法场次: {stats.total_matches}")
            print(f"  场均黄牌: {stats.avg_yellow_cards}")
            print(f"  场均红牌: {stats.avg_red_cards}")
            print(f"  主胜率: {stats.home_win_rate*100:.1f}%")
            print(f"  客胜率: {stats.away_win_rate*100:.1f}%")
            print(f"  风格: {stats.strictness}")
            print(f"  主场偏向: {stats.home_bias}")


if __name__ == "__main__":
    main()
