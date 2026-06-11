"""
世界杯比赛情报采集器
采集单场比赛的完整情报，输出分析报告
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import sqlite3
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'football_v2.db')
FIFA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'fetchers', 'fifa_ranking', 'data', 'fifa_ranking_current.json')


class MatchIntelligenceCollector:
    """比赛情报采集器"""

    def __init__(self):
        self.db_path = DB_PATH
        self.fifa_path = FIFA_PATH
        self._load_fifa_rankings()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _load_fifa_rankings(self):
        """加载FIFA排名"""
        if os.path.exists(self.fifa_path):
            with open(self.fifa_path, 'r', encoding='utf-8') as f:
                self.fifa_data = json.load(f)
        else:
            self.fifa_data = {}

    def _get_team_id(self, team_name: str) -> Optional[int]:
        """获取球队ID"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute('SELECT team_id FROM teams WHERE name_en = ? OR name_cn = ?', (team_name, team_name))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def collect_intelligence(self, home_team: str, away_team: str,
                            match_date: str, match_time: str = None) -> Dict:
        """
        采集单场比赛完整情报

        Args:
            home_team: 主队名称
            away_team: 客队名称
            match_date: 比赛日期 YYYY-MM-DD
            match_time: 比赛时间 HH:MM

        Returns:
            完整情报字典
        """
        intel = {
            'match': {
                'home_team': home_team,
                'away_team': away_team,
                'date': match_date,
                'time': match_time,
                'collected_at': datetime.now().isoformat()
            },
            'fifa_ranking': {},
            'team_value': {},
            'elo_rating': {},
            'h2h': {'matches': [], 'summary': {}},
            'form': {'home': {}, 'away': {}},
            'injuries': {'home': [], 'away': []},
            'news': {'home': [], 'away': [], 'negative': []},
            'social': {'home': {}, 'away': {}},
            'chemistry': {'home': {}, 'away': {}},
            'predictions': {},
            'summary': {}
        }

        logger.info(f"采集情报: {home_team} vs {away_team} ({match_date})")

        # 1. FIFA排名
        intel['fifa_ranking'] = self._get_fifa_comparison(home_team, away_team)

        # 2. Elo评分
        intel['elo_rating'] = self._get_elo_comparison(home_team, away_team)

        # 3. H2H记录
        intel['h2h'] = self._get_h2h_analysis(home_team, away_team)

        # 4. 近期form
        intel['form'] = {
            'home': self._get_team_form(home_team),
            'away': self._get_team_form(away_team)
        }

        # 5. 伤病信息
        intel['injuries'] = {
            'home': self._get_team_injuries(home_team),
            'away': self._get_team_injuries(away_team)
        }

        # 6. 新闻情报
        intel['news'] = {
            'home': self._get_team_news(home_team),
            'away': self._get_team_news(away_team),
            'negative': self._get_negative_news(home_team, away_team)
        }

        # 7. 社交情感
        intel['social'] = {
            'home': self._get_social_sentiment(home_team),
            'away': self._get_social_sentiment(away_team)
        }

        # 8. 生成综合摘要
        intel['summary'] = self._generate_summary(intel)

        return intel

    def _get_fifa_comparison(self, home_team: str, away_team: str) -> Dict:
        """获取FIFA排名对比"""
        home_info = self.fifa_data.get(home_team, {})
        away_info = self.fifa_data.get(away_team, {})

        home_rank = home_info.get('rank', 999)
        away_rank = away_info.get('rank', 999)

        return {
            'home': {
                'rank': home_rank,
                'points': home_info.get('points', 0),
                'confederation': home_info.get('confederation', 'Unknown')
            },
            'away': {
                'rank': away_rank,
                'points': away_info.get('points', 0),
                'confederation': away_info.get('confederation', 'Unknown')
            },
            'rank_diff': home_rank - away_rank,
            'points_diff': home_info.get('points', 0) - away_info.get('points', 0)
        }

    def _get_elo_comparison(self, home_team: str, away_team: str) -> Dict:
        """获取Elo评分对比"""
        conn = self._get_conn()
        c = conn.cursor()

        home_id = self._get_team_id(home_team)
        away_id = self._get_team_id(away_team)

        home_elo = 1500  # 默认值
        away_elo = 1500

        if home_id:
            c.execute('SELECT elo_rating FROM elo_ratings WHERE team_id = ?', (home_id,))
            row = c.fetchone()
            if row:
                home_elo = row[0]

        if away_id:
            c.execute('SELECT elo_rating FROM elo_ratings WHERE team_id = ?', (away_id,))
            row = c.fetchone()
            if row:
                away_elo = row[0]

        conn.close()

        return {
            'home': home_elo,
            'away': away_elo,
            'diff': home_elo - away_elo,
            'expected_home_win': self._elo_to_probability(home_elo, away_elo, 100)  # 主场+100
        }

    def _elo_to_probability(self, elo_a: float, elo_b: float, home_advantage: int = 0) -> float:
        """Elo转胜率"""
        elo_a += home_advantage
        return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))

    def _get_h2h_analysis(self, home_team: str, away_team: str) -> Dict:
        """获取H2H分析"""
        conn = self._get_conn()
        c = conn.cursor()

        home_id = self._get_team_id(home_team)
        away_id = self._get_team_id(away_team)

        matches = []
        summary = {'home_wins': 0, 'away_wins': 0, 'draws': 0, 'total': 0}

        if home_id and away_id:
            c.execute('''
                SELECT * FROM h2h_records
                WHERE (team_a_id = ? AND team_b_id = ?) OR (team_a_id = ? AND team_b_id = ?)
                ORDER BY match_date DESC LIMIT 10
            ''', (home_id, away_id, away_id, home_id))

            rows = c.fetchall()
            matches = [dict(row) for row in rows]

            for m in matches:
                summary['total'] += 1
                if m['home_team'] == home_team:
                    if m['home_score'] > m['away_score']:
                        summary['home_wins'] += 1
                    elif m['home_score'] < m['away_score']:
                        summary['away_wins'] += 1
                    else:
                        summary['draws'] += 1
                else:
                    if m['home_score'] > m['away_score']:
                        summary['away_wins'] += 1
                    elif m['home_score'] < m['away_score']:
                        summary['home_wins'] += 1
                    else:
                        summary['draws'] += 1

        conn.close()

        return {
            'matches': matches,
            'summary': summary,
            'home_advantage_pct': summary['home_wins'] / summary['total'] * 100 if summary['total'] > 0 else 0
        }

    def _get_team_form(self, team_name: str, limit: int = 10) -> Dict:
        """获取球队近期form"""
        conn = self._get_conn()
        c = conn.cursor()

        team_id = self._get_team_id(team_name)

        form_matches = []
        form_summary = {
            'played': 0, 'wins': 0, 'draws': 0, 'losses': 0,
            'goals_for': 0, 'goals_against': 0,
            'avg_goals': 0, 'form_points': 0
        }

        if team_id:
            c.execute('''
                SELECT * FROM team_form
                WHERE team_id = ?
                ORDER BY match_date DESC LIMIT ?
            ''', (team_id, limit))

            rows = c.fetchall()
            form_matches = [dict(row) for row in rows]

            for m in form_matches:
                form_summary['played'] += 1
                form_summary['goals_for'] += m['goals_for'] or 0
                form_summary['goals_against'] += m['goals_against'] or 0

                if m['result'] == 'W':
                    form_summary['wins'] += 1
                    form_summary['form_points'] += 3
                elif m['result'] == 'D':
                    form_summary['draws'] += 1
                    form_summary['form_points'] += 1
                else:
                    form_summary['losses'] += 1

            if form_summary['played'] > 0:
                form_summary['avg_goals'] = form_summary['goals_for'] / form_summary['played']

        conn.close()

        return {
            'matches': form_matches,
            'summary': form_summary,
            'form_rating': form_summary['form_points'] / (form_summary['played'] * 3) * 100 if form_summary['played'] > 0 else 0
        }

    def _get_team_injuries(self, team_name: str) -> List[Dict]:
        """获取球队伤病"""
        conn = self._get_conn()
        c = conn.cursor()

        try:
            c.execute('''
                SELECT player_name, status_type, status_reason, expected_return, updated_at
                FROM player_status
                WHERE team_name = ? AND status_type = 'injury'
                ORDER BY updated_at DESC
            ''', (team_name,))
            rows = c.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            # 表可能不存在或字段不匹配
            conn.close()
            return []

    def _get_team_news(self, team_name: str, days: int = 7) -> List[Dict]:
        """获取球队新闻"""
        conn = self._get_conn()
        c = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT n.* FROM news_aggregated n
            JOIN team_news_relation r ON n.id = r.news_id
            WHERE r.team_name = ? AND n.published_at >= ?
            ORDER BY n.published_at DESC LIMIT 10
        ''', (team_name, since))

        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def _get_negative_news(self, home_team: str, away_team: str) -> List[Dict]:
        """获取负面新闻"""
        conn = self._get_conn()
        c = conn.cursor()

        since = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT * FROM news_aggregated
            WHERE (mentioned_teams LIKE ? OR mentioned_teams LIKE ?)
            AND sentiment < -3
            AND published_at >= ?
            ORDER BY sentiment ASC LIMIT 10
        ''', (f'%{home_team}%', f'%{away_team}%', since))

        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def _get_social_sentiment(self, team_name: str) -> Dict:
        """获取社交情感"""
        conn = self._get_conn()
        c = conn.cursor()

        since = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT
                AVG(sentiment_score) as avg_sentiment,
                COUNT(*) as post_count,
                SUM(conflict_signal) as conflict_count
            FROM social_posts
            WHERE related_team = ? AND post_time >= ?
        ''', (team_name, since))

        row = c.fetchone()
        conn.close()

        if row and row[0]:
            return {
                'avg_sentiment': row[0],
                'post_count': row[1],
                'conflict_count': row[2] or 0,
                'has_issues': row[2] > 0 or row[0] < -3
            }

        return {'avg_sentiment': 0, 'post_count': 0, 'conflict_count': 0, 'has_issues': False}

    def _generate_summary(self, intel: Dict) -> Dict:
        """生成综合摘要"""
        summary = {
            'strength_comparison': {},
            'key_factors': [],
            'warnings': [],
            'prediction_trend': ''
        }

        # 实力对比
        fifa_diff = intel['fifa_ranking'].get('rank_diff', 0)
        elo_diff = intel['elo_rating'].get('diff', 0)
        form_diff = intel['form']['home'].get('form_rating', 0) - intel['form']['away'].get('form_rating', 0)

        # 综合实力差
        strength_score = (elo_diff * 0.4) + (form_diff * 0.3) - (fifa_diff * 0.3)

        if strength_score > 50:
            summary['strength_comparison'] = {'advantage': 'home', 'margin': '明显'}
            summary['prediction_trend'] = f"{intel['match']['home_team']} 占优"
        elif strength_score < -50:
            summary['strength_comparison'] = {'advantage': 'away', 'margin': '明显'}
            summary['prediction_trend'] = f"{intel['match']['away_team']} 占优"
        elif strength_score > 20:
            summary['strength_comparison'] = {'advantage': 'home', 'margin': '轻微'}
            summary['prediction_trend'] = f"{intel['match']['home_team']} 稍优"
        elif strength_score < -20:
            summary['strength_comparison'] = {'advantage': 'away', 'margin': '轻微'}
            summary['prediction_trend'] = f"{intel['match']['away_team']} 稍优"
        else:
            summary['strength_comparison'] = {'advantage': 'none', 'margin': '均衡'}
            summary['prediction_trend'] = "势均力敌"

        # 关键因素
        # H2H
        h2h_summary = intel['h2h'].get('summary', {})
        if h2h_summary.get('total', 0) > 0:
            home_pct = h2h_summary.get('home_wins', 0) / h2h_summary['total'] * 100
            if home_pct > 60:
                summary['key_factors'].append(f"H2H优势: {intel['match']['home_team']} {home_pct:.0f}%胜率")
            elif home_pct < 40:
                summary['key_factors'].append(f"H2H劣势: {intel['match']['away_team']} {100-home_pct:.0f}%胜率")

        # Form
        home_form = intel['form']['home'].get('form_rating', 0)
        away_form = intel['form']['away'].get('form_rating', 0)
        if home_form > 70:
            summary['key_factors'].append(f"{intel['match']['home_team']} 状态出色({home_form:.0f}%)")
        if away_form > 70:
            summary['key_factors'].append(f"{intel['match']['away_team']} 状态出色({away_form:.0f}%)")

        # 警告信号
        # 伤病
        home_injuries = intel['injuries']['home']
        away_injuries = intel['injuries']['away']
        if len(home_injuries) > 2:
            summary['warnings'].append(f"{intel['match']['home_team']} 伤病较多({len(home_injuries)}人)")
        if len(away_injuries) > 2:
            summary['warnings'].append(f"{intel['match']['away_team']} 伤病较多({len(away_injuries)}人)")

        # 负面新闻
        if intel['news']['negative']:
            summary['warnings'].append(f"近期负面新闻: {len(intel['news']['negative'])}条")

        # 社交问题
        if intel['social']['home'].get('has_issues'):
            summary['warnings'].append(f"{intel['match']['home_team']} 社交异常信号")
        if intel['social']['away'].get('has_issues'):
            summary['warnings'].append(f"{intel['match']['away_team']} 社交异常信号")

        return summary

    def generate_report(self, intel: Dict) -> str:
        """生成文字报告"""
        match = intel['match']
        lines = []

        lines.append("=" * 60)
        lines.append(f"比赛情报报告: {match['home_team']} vs {match['away_team']}")
        lines.append(f"日期: {match['date']} {match['time'] or ''}")
        lines.append("=" * 60)

        # FIFA排名
        fifa = intel['fifa_ranking']
        lines.append(f"\n【FIFA排名】")
        lines.append(f"  {match['home_team']}: 第{fifa['home']['rank']}位 ({fifa['home']['points']}分)")
        lines.append(f"  {match['away_team']}: 第{fifa['away']['rank']}位 ({fifa['away']['points']}分)")
        lines.append(f"  排名差: {abs(fifa['rank_diff'])}位")

        # Elo评分
        elo = intel['elo_rating']
        lines.append(f"\n【Elo评分】")
        lines.append(f"  {match['home_team']}: {elo['home']:.0f}")
        lines.append(f"  {match['away_team']}: {elo['away']:.0f}")
        lines.append(f"  主胜概率: {elo['expected_home_win']*100:.1f}%")

        # H2H
        h2h = intel['h2h']['summary']
        if h2h['total'] > 0:
            lines.append(f"\n【历史交锋】")
            lines.append(f"  近{h2h['total']}场: {match['home_team']} {h2h['home_wins']}胜 {h2h['draws']}平 {h2h['away_wins']}负")
            lines.append(f"  主胜率: {h2h['home_advantage_pct']:.1f}%")

        # 近期状态
        lines.append(f"\n【近期状态】")
        for team_key in ['home', 'away']:
            team_name = match[team_key + '_team']
            form = intel['form'][team_key]['summary']
            lines.append(f"  {team_name}: 近{form['played']}场 {form['wins']}胜{form['draws']}平{form['losses']}负")
            lines.append(f"    进{form['goals_for']}失{form['goals_against']} 状态{intel['form'][team_key]['form_rating']:.0f}%")

        # 伤病
        lines.append(f"\n【伤病情况】")
        for team_key in ['home', 'away']:
            team_name = match[team_key + '_team']
            injuries = intel['injuries'][team_key]
            if injuries:
                lines.append(f"  {team_name}: {len(injuries)}人伤缺")
                for inj in injuries[:3]:
                    lines.append(f"    - {inj['player_name']}: {inj['status_reason']}")
            else:
                lines.append(f"  {team_name}: 无伤病")

        # 警告
        if intel['summary']['warnings']:
            lines.append(f"\n【警告信号】")
            for w in intel['summary']['warnings']:
                lines.append(f"  ! {w}")

        # 综合判断
        lines.append(f"\n【综合判断】")
        lines.append(f"  实力对比: {intel['summary']['strength_comparison']['advantage']}方{intel['summary']['strength_comparison']['margin']}优势")
        if intel['summary']['key_factors']:
            for f in intel['summary']['key_factors']:
                lines.append(f"  + {f}")
        lines.append(f"  预测倾向: {intel['summary']['prediction_trend']}")

        lines.append("=" * 60)

        return '\n'.join(lines)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='比赛情报采集')
    parser.add_argument('--match', type=str, help='比赛(格式: 主队,客队,日期)')
    parser.add_argument('--report', action='store_true', help='生成报告')

    args = parser.parse_args()

    collector = MatchIntelligenceCollector()

    if args.match:
        parts = args.match.split(',')
        if len(parts) >= 3:
            intel = collector.collect_intelligence(parts[0], parts[1], parts[2])

            if args.report:
                report = collector.generate_report(intel)
                print(report)
            else:
                print(json.dumps(intel, ensure_ascii=False, indent=2, default=str))

    if not args.match:
        print("比赛情报采集器")
        print("用法:")
        print("  python match_intelligence.py --match 'Argentina,France,2026-06-15'")
        print("  python match_intelligence.py --match 'Argentina,France,2026-06-15' --report")