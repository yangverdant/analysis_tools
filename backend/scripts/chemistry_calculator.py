"""
阵容磨合度计算模块
基于历史首发阵容数据计算：
1. 首发11人一起出场次数
2. 关键位置组合默契度
3. 新援融入程度
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'football_v2.db')


class ChemistryCalculator:
    """阵容磨合度计算器"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """初始化磨合度相关表"""
        conn = self._get_conn()
        c = conn.cursor()

        # 阵容组合记录表
        c.execute('''
            CREATE TABLE IF NOT EXISTS lineup_combinations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                team_name TEXT,
                match_id TEXT,
                match_date DATE,
                lineup_hash TEXT,
                starting_xi TEXT,
                together_count INTEGER DEFAULT 1,
                chemistry_score REAL,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team_id, match_id)
            )
        ''')

        # 球员组合默契度表
        c.execute('''
            CREATE TABLE IF NOT EXISTS player_combination (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                player_a TEXT NOT NULL,
                player_b TEXT NOT NULL,
                position_a TEXT,
                position_b TEXT,
                together_matches INTEGER DEFAULT 0,
                successful_actions INTEGER DEFAULT 0,
                avg_rating REAL,
                source TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team_id, player_a, player_b)
            )
        ''')

        # 磨合度历史趋势表
        c.execute('''
            CREATE TABLE IF NOT EXISTS chemistry_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                team_name TEXT,
                match_date DATE,
                chemistry_score REAL,
                new_players_count INTEGER,
                core_players_count INTEGER,
                avg_together_matches REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def _generate_lineup_hash(self, starting_xi: List[str]) -> str:
        """生成阵容hash"""
        sorted_players = sorted([p.lower().strip() for p in starting_xi])
        return '|'.join(sorted_players)

    def calculate_chemistry(self, team_id: int, starting_xi: List[str],
                           match_date: str, match_id: str = None) -> Dict:
        """
        计算阵容磨合度

        Args:
            team_id: 球队ID
            starting_xi: 首发11人名单
            match_date: 比赛日期
            match_id: 比赛ID

        Returns:
            {
                'chemistry_score': 0-1分数,
                'together_matches': 一起出场次数,
                'pair_scores': 两两组合分数,
                'new_players': 新加入球员,
                'core_group': 核心组合
            }
        """
        conn = self._get_conn()
        c = conn.cursor()

        if len(starting_xi) < 11:
            logger.warning(f"首发人数不足11: {len(starting_xi)}")
            return {'chemistry_score': 0, 'together_matches': 0}

        lineup_hash = self._generate_lineup_hash(starting_xi)

        # 1. 查询这个阵容组合出现过几次
        c.execute('''
            SELECT COUNT(*) as count, MIN(match_date) as first_match
            FROM lineup_combinations
            WHERE team_id = ? AND lineup_hash = ? AND match_date < ?
        ''', (team_id, lineup_hash, match_date))

        row = c.fetchone()
        together_matches = row[0] if row else 0

        # 2. 计算两两组合默契度
        pair_scores = {}
        for i in range(len(starting_xi)):
            for j in range(i + 1, len(starting_xi)):
                player_a, player_b = starting_xi[i], starting_xi[j]

                c.execute('''
                    SELECT together_matches, avg_rating
                    FROM player_combination
                    WHERE team_id = ? AND player_a = ? AND player_b = ?
                ''', (team_id, player_a, player_b))

                pair_row = c.fetchone()
                if pair_row:
                    pair_scores[f"{player_a}-{player_b}"] = {
                        'matches': pair_row[0],
                        'rating': pair_row[1] or 0
                    }
                else:
                    pair_scores[f"{player_a}-{player_b}"] = {'matches': 0, 'rating': 0}

        # 3. 计算磨合度分数
        # 公式: 一起出场次数权重 + 两两配合次数权重
        total_pairs = 11 * 10 / 2  # 55对组合

        # 两两配合超过10次的组合数
        good_pairs = sum(1 for p in pair_scores.values() if p['matches'] >= 10)
        excellent_pairs = sum(1 for p in pair_scores.values() if p['matches'] >= 20)

        # 磨合度 = (好组合数/总组合数)*0.5 + (优秀组合数/总组合数)*0.3 + (一起出场次数权重)*0.2
        pair_score = (good_pairs / total_pairs) * 0.5 + (excellent_pairs / total_pairs) * 0.3
        together_score = min(together_matches / 30, 1) * 0.2  # 30场为满分

        chemistry_score = pair_score + together_score

        # 4. 识别新球员（与其他人配合<5场）
        new_players = []
        for player in starting_xi:
            partner_matches = []
            for other in starting_xi:
                if other != player:
                    key = f"{player}-{other}" if f"{player}-{other}" in pair_scores else f"{other}-{player}"
                    partner_matches.append(pair_scores.get(key, {}).get('matches', 0))

            avg_matches = sum(partner_matches) / len(partner_matches) if partner_matches else 0
            if avg_matches < 5:
                new_players.append({
                    'player': player,
                    'avg_matches': avg_matches
                })

        # 5. 识别核心组合（配合超过30场）
        core_groups = []
        for pair_name, info in pair_scores.items():
            if info['matches'] >= 30:
                core_groups.append(pair_name)

        conn.close()

        return {
            'chemistry_score': round(chemistry_score, 3),
            'together_matches': together_matches,
            'good_pairs': good_pairs,
            'excellent_pairs': excellent_pairs,
            'new_players': new_players,
            'core_groups': core_groups,
            'pair_scores': pair_scores
        }

    def save_lineup(self, team_id: int, team_name: str, match_id: str,
                    match_date: str, starting_xi: List[str], source: str = 'unknown'):
        """保存首发阵容并更新磨合度"""
        conn = self._get_conn()
        c = conn.cursor()

        lineup_hash = self._generate_lineup_hash(starting_xi)

        # 计算磨合度
        chemistry = self.calculate_chemistry(team_id, starting_xi, match_date, match_id)

        # 保存阵容记录
        c.execute('''
            INSERT OR REPLACE INTO lineup_combinations
            (team_id, team_name, match_id, match_date, lineup_hash, starting_xi,
             together_count, chemistry_score, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            team_id, team_name, match_id, match_date, lineup_hash,
            json.dumps(starting_xi, ensure_ascii=False),
            chemistry['together_matches'] + 1,
            chemistry['chemistry_score'],
            source
        ))

        # 更新两两组合记录
        for i in range(len(starting_xi)):
            for j in range(i + 1, len(starting_xi)):
                player_a, player_b = starting_xi[i], starting_xi[j]

                c.execute('''
                    INSERT INTO player_combination (team_id, player_a, player_b, together_matches)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(team_id, player_a, player_b)
                    DO UPDATE SET together_matches = together_matches + 1, updated_at = CURRENT_TIMESTAMP
                ''', (team_id, player_a, player_b))

        # 保存历史趋势
        c.execute('''
            INSERT INTO chemistry_history
            (team_id, team_name, match_date, chemistry_score, new_players_count, avg_together_matches)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            team_id, team_name, match_date, chemistry['chemistry_score'],
            len(chemistry['new_players']),
            sum(p['matches'] for p in chemistry['pair_scores'].values()) / len(chemistry['pair_scores'])
        ))

        conn.commit()
        conn.close()

        logger.info(f"保存阵容: {team_name} {match_date} 磨合度={chemistry['chemistry_score']:.2f}")
        return chemistry

    def get_team_chemistry_trend(self, team_id: int, days: int = 90) -> List[Dict]:
        """获取球队磨合度趋势"""
        conn = self._get_conn()
        c = conn.cursor()

        since = (datetime.now() - __import__('datetime').timedelta(days=days)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT match_date, chemistry_score, new_players_count, avg_together_matches
            FROM chemistry_history
            WHERE team_id = ? AND match_date >= ?
            ORDER BY match_date ASC
        ''', (team_id, since))

        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_best_combination(self, team_id: int) -> Dict:
        """获取球队最佳组合"""
        conn = self._get_conn()
        c = conn.cursor()

        c.execute('''
            SELECT player_a, player_b, together_matches, avg_rating
            FROM player_combination
            WHERE team_id = ?
            ORDER BY together_matches DESC
            LIMIT 10
        ''', (team_id,))

        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def calculate_lineup_impact(self, team_id: int, starting_xi: List[str]) -> Dict:
        """
        计算阵容对比赛的影响
        返回磨合度对比赛表现的预期影响
        """
        chemistry = self.calculate_chemistry(team_id, starting_xi,
                                            datetime.now().strftime('%Y-%m-%d'))

        # 磨合度影响评估
        impact = {}

        # 低磨合度 → 配合失误风险↑
        if chemistry['chemistry_score'] < 0.3:
            impact['coordination_risk'] = 'high'
            impact['expected_errors'] = 3  # 预期配合失误次数
        elif chemistry['chemistry_score'] < 0.6:
            impact['coordination_risk'] = 'medium'
            impact['expected_errors'] = 1
        else:
            impact['coordination_risk'] = 'low'
            impact['expected_errors'] = 0

        # 新球员多 → 战术执行打折
        if len(chemistry['new_players']) >= 3:
            impact['tactical_penalty'] = -10  # 战术执行效率下降10%
        elif len(chemistry['new_players']) >= 1:
            impact['tactical_penalty'] = -5
        else:
            impact['tactical_penalty'] = 0

        # 核心组合多 → 关键时刻稳定
        if len(chemistry['core_groups']) >= 5:
            impact['关键时刻_bonus'] = 5  # 关键时刻表现+5%
        elif len(chemistry['core_groups']) >= 3:
            impact['关键时刻_bonus'] = 3
        else:
            impact['关键时刻_bonus'] = 0

        impact['chemistry'] = chemistry
        return impact


class MatchLineupAnalyzer:
    """比赛阵容分析器"""

    def __init__(self, db_path: str = DB_PATH):
        self.calculator = ChemistryCalculator(db_path)

    def compare_lineups(self, home_team_id: int, home_lineup: List[str],
                        away_team_id: int, away_lineup: List[str]) -> Dict:
        """对比两队阵容磨合度"""
        home_chemistry = self.calculator.calculate_chemistry(home_team_id, home_lineup,
                                                             datetime.now().strftime('%Y-%m-%d'))
        away_chemistry = self.calculator.calculate_chemistry(away_team_id, away_lineup,
                                                             datetime.now().strftime('%Y-%m-%d'))

        return {
            'home': {
                'chemistry_score': home_chemistry['chemistry_score'],
                'new_players': len(home_chemistry['new_players']),
                'core_groups': len(home_chemistry['core_groups'])
            },
            'away': {
                'chemistry_score': away_chemistry['chemistry_score'],
                'new_players': len(away_chemistry['new_players']),
                'core_groups': len(away_chemistry['core_groups'])
            },
            'comparison': {
                'chemistry_diff': home_chemistry['chemistry_score'] - away_chemistry['chemistry_score'],
                'advantage': 'home' if home_chemistry['chemistry_score'] > away_chemistry['chemistry_score'] else 'away',
                'impact_on_result': round((home_chemistry['chemistry_score'] - away_chemistry['chemistry_score']) * 10, 1)
            }
        }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='阵容磨合度计算')
    parser.add_argument('--team', type=str, help='球队名')
    parser.add_argument('--lineup', type=str, help='首发11人(逗号分隔)')
    parser.add_argument('--trend', type=int, help='查看趋势(天数)')
    parser.add_argument('--best', type=str, help='最佳组合')

    args = parser.parse_args()

    calculator = ChemistryCalculator()

    if args.team and args.lineup:
        lineup = args.lineup.split(',')
        # 需要team_id
        print(f"计算磨合度: {args.team}")
        print(f"首发: {lineup}")
        # chemistry = calculator.calculate_chemistry(team_id, lineup, '2026-01-01')
        # print(f"结果: {chemistry}")

    if args.trend and args.team:
        print(f"查看趋势需要team_id")

    if args.best:
        print(f"最佳组合需要team_id")

    if not any([args.team, args.lineup, args.trend, args.best]):
        print("阵容磨合度计算模块")
        print("用法:")
        print("  python chemistry_calculator.py --team Brazil --lineup 'Player1,Player2,...'")
        print("  python chemistry_calculator.py --team Brazil --trend 90")
        print("  python chemistry_calculator.py --best Brazil")