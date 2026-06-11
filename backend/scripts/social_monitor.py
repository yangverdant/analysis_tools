"""
社交媒体监控模块
监控微博、Twitter等平台的球队/球员动态
检测矛盾信号、负面舆情、异常互动
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import sqlite3
import json
import time
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import hashlib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'football_v2.db')


class SocialSignalDetector:
    """社交信号检测器"""

    # 矛盾信号关键词
    CONFLICT_SIGNALS = [
        '取关', 'unfollow', '删除合影', '不再关注',
        '争吵', '争执', '冲突', 'argue', 'clash', 'dispute',
        '不满', '抱怨', '批评', 'complain', 'criticize',
        '分裂', '内讧', 'discord', 'rift', 'divide',
        '不和谐', '不和', 'feud', 'tension'
    ]

    # 消极情绪关键词
    NEGATIVE_EMOTION = [
        '失望', '沮丧', '绝望', 'disappointed', 'frustrated',
        '愤怒', '生气', 'angry', 'furious',
        '悲伤', '难过', 'sad', 'upset',
        '压力', '焦虑', 'stress', 'anxious',
        '想离开', '要走', 'want to leave', 'exit'
    ]

    # 异常行为关键词
    ABNORMAL_BEHAVIOR = [
        '神秘发言', '暗示', 'cryptic', 'hint',
        '沉默', '不回应', 'silent', 'no response',
        '删除动态', '删除帖子', 'delete post',
        '清空', '清空动态', 'clear posts',
        '换头像', '换简介', 'change profile'
    ]

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """初始化社交监控表"""
        conn = self._get_conn()
        c = conn.cursor()

        tables = [
            '''CREATE TABLE IF NOT EXISTS social_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                account_name TEXT,
                account_id TEXT,
                post_type TEXT,
                content TEXT,
                original_text TEXT,
                post_time TIMESTAMP,
                url TEXT,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                sentiment_score REAL DEFAULT 0,
                conflict_signal INTEGER DEFAULT 0,
                negative_signal INTEGER DEFAULT 0,
                abnormal_signal INTEGER DEFAULT 0,
                detected_signals TEXT,
                related_team TEXT,
                related_player TEXT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content_hash TEXT UNIQUE
            )''',
            '''CREATE TABLE IF NOT EXISTS social_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                team_name TEXT,
                player_name TEXT,
                signal_details TEXT,
                related_posts TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'new',
                notes TEXT
            )''',
            '''CREATE TABLE IF NOT EXISTS social_account_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                account_name TEXT NOT NULL,
                account_id TEXT,
                account_type TEXT,
                related_team TEXT,
                is_official INTEGER DEFAULT 0,
                follower_count INTEGER,
                last_post_time TIMESTAMP,
                interaction_pattern TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(platform, account_name)
            )''',
            '''CREATE TABLE IF NOT EXISTS interaction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                account_a TEXT,
                account_b TEXT,
                interaction_type TEXT,
                interaction_time TIMESTAMP,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )'''
        ]

        for sql in tables:
            c.execute(sql)

        # 创建索引
        c.execute('CREATE INDEX IF NOT EXISTS idx_social_time ON social_posts(post_time)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_social_team ON social_posts(related_team)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_alert_type ON social_alerts(alert_type)')

        conn.commit()
        conn.close()
        logger.info("社交监控表初始化完成")

    def _detect_signals(self, text: str) -> Dict:
        """检测文本中的信号"""
        text_lower = text.lower()

        signals = {
            'conflict': [],
            'negative': [],
            'abnormal': [],
            'sentiment': 0
        }

        # 检测矛盾信号
        for signal in self.CONFLICT_SIGNALS:
            if signal in text_lower:
                signals['conflict'].append(signal)
                signals['sentiment'] -= 3

        # 检测消极情绪
        for signal in self.NEGATIVE_EMOTION:
            if signal in text_lower:
                signals['negative'].append(signal)
                signals['sentiment'] -= 2

        # 检测异常行为
        for signal in self.ABNORMAL_BEHAVIOR:
            if signal in text_lower:
                signals['abnormal'].append(signal)
                signals['sentiment'] -= 1

        return signals

    def save_post(self, platform: str, account_name: str, content: str,
                  post_time: str = None, url: str = None,
                  likes: int = 0, comments: int = 0, shares: int = 0,
                  related_team: str = None, related_player: str = None) -> int:
        """保存社交动态"""
        conn = self._get_conn()
        c = conn.cursor()

        content_hash = hashlib.md5(f"{platform}:{account_name}:{content[:100]}".encode()).hexdigest()

        # 检测信号
        signals = self._detect_signals(content)

        c.execute('''
            INSERT OR IGNORE INTO social_posts
            (platform, account_name, content, post_time, url, likes, comments, shares,
             sentiment_score, conflict_signal, negative_signal, abnormal_signal,
             detected_signals, related_team, related_player, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            platform, account_name, content, post_time, url, likes, comments, shares,
            signals['sentiment'],
            len(signals['conflict']),
            len(signals['negative']),
            len(signals['abnormal']),
            json.dumps(signals, ensure_ascii=False),
            related_team, related_player, content_hash
        ))

        post_id = c.lastrowid

        # 如果有矛盾信号，创建警报
        if signals['conflict'] or signals['sentiment'] < -5:
            self._create_alert(c, 'conflict', related_team, related_player,
                              signals, content, post_id)

        conn.commit()
        conn.close()

        return post_id

    def _create_alert(self, cursor, alert_type: str, team: str, player: str,
                      signals: Dict, content: str, post_id: int):
        """创建警报"""
        severity = 'high' if signals['sentiment'] < -8 else 'medium' if signals['sentiment'] < -5 else 'low'

        cursor.execute('''
            INSERT INTO social_alerts
            (alert_type, severity, team_name, player_name, signal_details, related_posts)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            alert_type, severity, team, player,
            json.dumps(signals, ensure_ascii=False),
            json.dumps([post_id])
        ))

        logger.warning(f"社交警报: [{severity}] {team or player} - {signals}")

    def get_team_alerts(self, team_name: str, days: int = 7) -> List[Dict]:
        """获取球队社交警报"""
        conn = self._get_conn()
        c = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT * FROM social_alerts
            WHERE team_name = ? AND detected_at >= ?
            ORDER BY severity DESC, detected_at DESC
        ''', (team_name, since))

        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_team_social_sentiment(self, team_name: str, days: int = 7) -> Dict:
        """获取球队社交情感趋势"""
        conn = self._get_conn()
        c = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT
                AVG(sentiment_score) as avg_sentiment,
                COUNT(*) as post_count,
                SUM(conflict_signal) as conflict_count,
                SUM(negative_signal) as negative_count
            FROM social_posts
            WHERE related_team = ? AND post_time >= ?
        ''', (team_name, since))

        row = c.fetchone()
        conn.close()

        if row and row[0]:
            return {
                'team': team_name,
                'avg_sentiment': row[0],
                'post_count': row[1],
                'conflict_count': row[2] or 0,
                'negative_count': row[3] or 0
            }
        return None

    def check_interaction_drop(self, account_a: str, account_b: str,
                               platform: str = 'instagram') -> bool:
        """检测互动减少"""
        conn = self._get_conn()
        c = conn.cursor()

        # 查询过去30天的互动次数
        since = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT COUNT(*) FROM interaction_history
            WHERE platform = ?
            AND ((account_a = ? AND account_b = ?) OR (account_a = ? AND account_b = ?))
            AND interaction_time >= ?
        ''', (platform, account_a, account_b, account_b, account_a, since))

        current_count = c.fetchone()[0]

        # 查询前30天的互动次数
        prev_since = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        prev_to = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT COUNT(*) FROM interaction_history
            WHERE platform = ?
            AND ((account_a = ? AND account_b = ?) OR (account_a = ? AND account_b = ?))
            AND interaction_time >= ? AND interaction_time < ?
        ''', (platform, account_a, account_b, account_b, account_a, prev_since, prev_to))

        prev_count = c.fetchone()[0]
        conn.close()

        # 如果互动减少超过50%，返回True
        if prev_count > 5 and current_count < prev_count * 0.5:
            logger.warning(f"互动减少: {account_a} <-> {account_b} ({prev_count} -> {current_count})")
            return True

        return False

    def detect_team_internal_issues(self, team_name: str) -> List[Dict]:
        """检测球队内部问题"""
        issues = []

        # 1. 检查社交警报
        alerts = self.get_team_alerts(team_name, days=14)
        for alert in alerts:
            if alert['severity'] in ['high', 'medium']:
                issues.append({
                    'type': 'social_alert',
                    'severity': alert['severity'],
                    'details': json.loads(alert['signal_details'] or '{}'),
                    'detected_at': alert['detected_at']
                })

        # 2. 检查情感趋势
        sentiment = self.get_team_social_sentiment(team_name)
        if sentiment and sentiment['avg_sentiment'] < -3:
            issues.append({
                'type': 'negative_sentiment',
                'avg_sentiment': sentiment['avg_sentiment'],
                'conflict_count': sentiment['conflict_count']
            })

        # 3. 检查互动减少（需要跟踪账号）
        # TODO: 需要预先设置要跟踪的账号组合

        return issues


class WeiboMonitor:
    """微博监控器"""

    def __init__(self, db_path: str = DB_PATH):
        self.detector = SocialSignalDetector(db_path)
        # 微博足球相关账号（需要手动配置）
        self.target_accounts = [
            '梅西', 'C罗', '内马尔', '姆巴佩',
            '巴西队', '阿根廷队', '法国队',
            'FIFA世界杯', '懂球帝', '虎扑足球'
        ]

    def collect_hot_search(self):
        """采集微博热搜（足球相关）"""
        # TODO: 需要微博API或爬虫
        logger.warning("微博热搜采集需要配置API或爬虫")
        return []

    def collect_account_posts(self, account_name: str, limit: int = 20):
        """采集账号动态"""
        # TODO: 需要微博API或爬虫
        logger.warning(f"微博账号采集需要配置: {account_name}")
        return []


class TwitterMonitor:
    """Twitter监控器"""

    def __init__(self, db_path: str = DB_PATH):
        self.detector = SocialSignalDetector(db_path)
        # Twitter足球记者/球员账号
        self.reporters = [
            'FabrizioRomano',  # 转会专家
            'DiMarzio',        # 意大利记者
            'SkySportsNews',   # Sky体育
            'ESPNFC',          # ESPN足球
            'TheAthleticFC',   # The Athletic
        ]
        self.star_players = [
            'Messi', 'Cristiano', 'Neymar', 'Mbappe',
            'Benzema', 'Modric', 'DeBruyne'
        ]

    def collect_reporter_tweets(self, limit: int = 50):
        """采集记者推文"""
        # TODO: 需要Twitter API
        logger.warning("Twitter采集需要配置API")
        return []

    def detect_transfer_news(self) -> List[Dict]:
        """检测转会新闻"""
        # TODO: 从记者推文中提取转会信息
        return []


class SocialCollectorOrchestrator:
    """社交采集调度器"""

    def __init__(self):
        self.detector = SocialSignalDetector()
        self.weibo = WeiboMonitor()
        self.twitter = TwitterMonitor()

    def collect_team_social_data(self, team_name: str) -> Dict:
        """采集球队社交数据汇总"""
        result = {
            'team': team_name,
            'alerts': self.detector.get_team_alerts(team_name),
            'sentiment': self.detector.get_team_social_sentiment(team_name),
            'internal_issues': self.detector.detect_team_internal_issues(team_name)
        }

        return result

    def daily_collection(self):
        """每日社交采集"""
        # 1. 检查所有球队的警报
        conn = self.detector._get_conn()
        c = conn.cursor()
        c.execute('SELECT DISTINCT related_team FROM social_posts WHERE related_team IS NOT NULL')
        teams = [row[0] for row in c.fetchall()]
        conn.close()

        issues_summary = {}
        for team in teams:
            issues = self.detector.detect_team_internal_issues(team)
            if issues:
                issues_summary[team] = issues

        if issues_summary:
            logger.warning(f"检测到 {len(issues_summary)} 个球队有内部问题信号")

        return issues_summary


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='社交媒体监控')
    parser.add_argument('--alerts', type=str, help='查看球队警报')
    parser.add_argument('--sentiment', type=str, help='查看球队情感')
    parser.add_argument('--issues', type=str, help='检测球队内部问题')
    parser.add_argument('--test', action='store_true', help='测试保存动态')

    args = parser.parse_args()

    detector = SocialSignalDetector()

    if args.alerts:
        alerts = detector.get_team_alerts(args.alerts)
        print(f"\n{args.alerts} 警报:")
        for a in alerts:
            print(f"  [{a['severity']}] {a['alert_type']} - {a['detected_at']}")

    if args.sentiment:
        s = detector.get_team_social_sentiment(args.sentiment)
        print(f"\n{args.sentiment} 情感:")
        print(f"  平均情感: {s['avg_sentiment']}")
        print(f"  矛盾信号: {s['conflict_count']}")

    if args.issues:
        issues = detector.detect_team_internal_issues(args.issues)
        print(f"\n{args.issues} 内部问题:")
        for i in issues:
            print(f"  {i['type']}: {i}")

    if args.test:
        # 测试保存一条动态
        test_content = "梅西取关了巴黎官方账号，暗示可能离开"
        detector.save_post(
            platform='instagram',
            account_name='Messi',
            content=test_content,
            related_team='Argentina',
            related_player='Messi'
        )
        print("测试动态已保存")

    if not any([args.alerts, args.sentiment, args.issues, args.test]):
        print("社交媒体监控模块")
        print("用法:")
        print("  python social_monitor.py --alerts Argentina     # 查看警报")
        print("  python social_monitor.py --sentiment Brazil     # 查看情感")
        print("  python social_monitor.py --issues France        # 检测内部问题")
        print("  python social_monitor.py --test                 # 测试保存")