"""
新闻聚合系统 - 多源新闻采集 + 情感分类 + 影响评估
采集源：
1. zhibo8 - 中文体育新闻
2. dongqiudi - 深度报道
3. hupu - 论坛讨论
4. weibo - 微博热搜
5. twitter - 英文爆料

新闻类型：
- injury: 伤病
- conflict: 球员矛盾/更衣室问题
- transfer: 转会
- negative: 负面新闻
- positive: 正面新闻
- tactical: 战术相关
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import sqlite3
import re
import time
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'football_v2.db')


class NewsClassifier:
    """新闻分类器 - 基于关键词的情感和类型分类"""

    # 类型关键词
    TYPE_KEYWORDS = {
        'injury': [
            '受伤', '伤病', '伤缺', '伤停', '缺席', '无法出战', '因伤',
            '拉伤', '扭伤', '骨折', '肌肉', '膝盖', '脚踝', '大腿',
            'injury', 'injured', 'ruled out', 'sidelined'
        ],
        'conflict': [
            '内讧', '矛盾', '冲突', '不和', '争执', '争吵', '分裂',
            '更衣室', '队长', '核心', '不满', '抱怨', '批评',
            'conflict', 'clash', 'dispute', 'unrest', 'dressing room'
        ],
        'transfer': [
            '转会', '签约', '加盟', '离队', '解约', '租借', '买断',
            '续约', '合同', '经纪人', '报价', '接触',
            'transfer', 'sign', 'join', 'leave', 'contract'
        ],
        'negative': [
            '丑闻', '争议', '处罚', '禁赛', '红牌', '暴力', '涉嫌',
            '被捕', '酒驾', '打架', '绯闻', '负面',
            'scandal', 'controversy', 'ban', 'suspended', 'arrest'
        ],
        'positive': [
            '续约', '获奖', '最佳', '突破', '纪录', '历史', '里程碑',
            '回归', '复出', '痊愈', '期待',
            'award', 'record', 'milestone', 'return', 'recovery'
        ],
        'tactical': [
            '战术', '阵型', '首发', '阵容', '位置', '调整', '轮换',
            'formation', 'lineup', 'tactical', 'starting xi', 'strategy'
        ]
    }

    # 情感关键词
    SENTIMENT_POSITIVE = [
        '利好', '振奋', '信心', '期待', '支持', '成功', '胜利',
        '出色', '精彩', '完美', '优秀', '稳定', 'good', 'great', 'excellent'
    ]

    SENTIMENT_NEGATIVE = [
        '担忧', '困扰', '打击', '危机', '困难', '压力', '失望',
        '糟糕', '崩溃', '下滑', '隐患', '风险', 'bad', 'worry', 'crisis', 'concern'
    ]

    # 影响级别关键词
    HIGH_IMPACT_KEYWORDS = [
        '核心', '主力', '队长', '头号', '球星', '最佳射手', '核心球员',
        'key player', 'captain', 'star', 'main', 'top scorer'
    ]

    def classify(self, text: str) -> Tuple[str, float, str]:
        """
        分类新闻
        Returns:
            (news_type, sentiment, impact_level)
        """
        text_lower = text.lower()

        # 1. 分类类型
        scores = {}
        for news_type, keywords in self.TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            scores[news_type] = score

        news_type = max(scores, key=scores.get) if max(scores.values()) > 0 else 'general'

        # 2. 计算情感
        sentiment = 0
        for kw in self.SENTIMENT_POSITIVE:
            if kw in text_lower:
                sentiment += 1
        for kw in self.SENTIMENT_NEGATIVE:
            if kw in text_lower:
                sentiment -= 1

        # 归一化到 -10 ~ 10
        sentiment = max(-10, min(10, sentiment * 2))

        # 3. 影响级别
        impact_level = 'low'
        for kw in self.HIGH_IMPACT_KEYWORDS:
            if kw in text_lower:
                impact_level = 'high'
                break
        if impact_level == 'low' and scores.get('injury', 0) > 0:
            impact_level = 'medium'

        return news_type, sentiment, impact_level


class NewsAggregator:
    """新闻聚合器"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.classifier = NewsClassifier()
        self._init_tables()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """初始化新闻相关表"""
        conn = self._get_conn()
        c = conn.cursor()

        # 综合新闻表
        c.execute('''
            CREATE TABLE IF NOT EXISTS news_aggregated (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                summary TEXT,
                source TEXT NOT NULL,
                url TEXT,
                author TEXT,
                news_type TEXT DEFAULT 'general',
                sentiment REAL DEFAULT 0,
                impact_level TEXT DEFAULT 'low',
                mentioned_teams TEXT,
                mentioned_players TEXT,
                published_at TIMESTAMP,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content_hash TEXT,
                UNIQUE(content_hash)
            )
        ''')

        # 球队新闻关联表
        c.execute('''
            CREATE TABLE IF NOT EXISTS team_news_relation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                news_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                team_name TEXT,
                relevance_score REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (news_id) REFERENCES news_aggregated(id),
                FOREIGN KEY (team_id) REFERENCES teams(team_id)
            )
        ''')

        # 舆论热度表
        c.execute('''
            CREATE TABLE IF NOT EXISTS public_sentiment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT NOT NULL,
                platform TEXT,
                hot_score REAL,
                sentiment_avg REAL,
                discussion_count INTEGER,
                trend_direction TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建索引
        c.execute('CREATE INDEX IF NOT EXISTS idx_news_type ON news_aggregated(news_type)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_news_published ON news_aggregated(published_at)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_news_team ON team_news_relation(team_id)')

        conn.commit()
        conn.close()
        logger.info("新闻表初始化完成")

    def _get_content_hash(self, title: str, source: str) -> str:
        """生成内容hash用于去重"""
        content = f"{source}:{title}"
        return hashlib.md5(content.encode()).hexdigest()

    def _extract_teams(self, text: str) -> List[str]:
        """从文本中提取球队名"""
        conn = self._get_conn()
        c = conn.cursor()

        c.execute('SELECT name_en, name_cn FROM teams WHERE team_type = "national" OR team_type = "club"')
        teams = c.fetchall()
        conn.close()

        mentioned = []
        text_lower = text.lower()

        for row in teams:
            if row[0] and row[0].lower() in text_lower:
                mentioned.append(row[0])
            elif row[1] and row[1] in text:
                mentioned.append(row[1])

        return list(set(mentioned))

    def save_news(self, title: str, content: str = None, source: str = 'unknown',
                  url: str = None, author: str = None, published_at: str = None) -> int:
        """保存新闻"""
        conn = self._get_conn()
        c = conn.cursor()

        content_hash = self._get_content_hash(title, source)

        # 检查是否已存在
        c.execute('SELECT id FROM news_aggregated WHERE content_hash = ?', (content_hash,))
        if c.fetchone():
            conn.close()
            return 0

        # 分类
        full_text = f"{title} {content or ''}"
        news_type, sentiment, impact_level = self.classifier.classify(full_text)

        # 提取球队
        mentioned_teams = self._extract_teams(full_text)

        # 保存
        c.execute('''
            INSERT INTO news_aggregated
            (title, content, source, url, author, news_type, sentiment, impact_level,
             mentioned_teams, published_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            title, content, source, url, author, news_type, sentiment, impact_level,
            json.dumps(mentioned_teams, ensure_ascii=False), published_at, content_hash
        ))

        news_id = c.lastrowid

        # 关联球队
        if mentioned_teams:
            self._link_teams(c, news_id, mentioned_teams)

        conn.commit()
        conn.close()

        logger.debug(f"保存新闻: [{news_type}] {title[:50]}...")
        return news_id

    def _link_teams(self, cursor, news_id: int, team_names: List[str]):
        """关联新闻和球队"""
        for team_name in team_names:
            cursor.execute('SELECT team_id FROM teams WHERE name_en = ? OR name_cn = ?', (team_name, team_name))
            row = cursor.fetchone()
            if row:
                cursor.execute('''
                    INSERT OR IGNORE INTO team_news_relation (news_id, team_id, team_name)
                    VALUES (?, ?, ?)
                ''', (news_id, row[0], team_name))

    # ==================== 数据源采集 ====================

    def collect_from_zhibo8(self, limit: int = 100):
        """从zhibo8采集新闻"""
        try:
            from fetchers.news.get_news import get_zhibo8_news
            news_list = get_zhibo8_news(limit=limit)

            saved = 0
            for item in news_list:
                news_id = self.save_news(
                    title=item.get('title'),
                    content=item.get('content'),
                    source='zhibo8',
                    url=item.get('url'),
                    published_at=item.get('date')
                )
                if news_id:
                    saved += 1

            logger.info(f"zhibo8采集: {saved}/{len(news_list)}条新新闻")
            return saved
        except Exception as e:
            logger.error(f"zhibo8采集失败: {e}")
            return 0

    def collect_from_dongqiudi(self, limit: int = 50):
        """从懂球帝采集新闻"""
        try:
            from fetchers.dongqiudi.get_news import get_news
            news_list = get_news(limit=limit)

            saved = 0
            for item in news_list:
                news_id = self.save_news(
                    title=item.get('title'),
                    content=item.get('summary'),
                    source='dongqiudi',
                    url=item.get('url'),
                    author=item.get('author'),
                    published_at=item.get('date')
                )
                if news_id:
                    saved += 1

            logger.info(f"dongqiudi采集: {saved}/{len(news_list)}条")
            return saved
        except Exception as e:
            logger.error(f"dongqiudi采集失败: {e}")
            return 0

    def collect_from_hupu(self, limit: int = 50):
        """从虎扑采集讨论"""
        try:
            from fetchers.hupu.get_news import get_news
            news_list = get_news(limit=limit)

            saved = 0
            for item in news_list:
                news_id = self.save_news(
                    title=item.get('title'),
                    content=item.get('content'),
                    source='hupu',
                    url=item.get('url'),
                    published_at=item.get('date')
                )
                if news_id:
                    saved += 1

            logger.info(f"hupu采集: {saved}/{len(news_list)}条")
            return saved
        except Exception as e:
            logger.error(f"hupu采集失败: {e}")
            return 0

    def collect_from_twitter(self, accounts: List[str] = None, limit: int = 50):
        """从Twitter采集新闻（需配置API）"""
        # TODO: 需要Twitter API配置
        logger.warning("Twitter采集需要配置API")
        return 0

    # ==================== 查询接口 ====================

    def get_team_news(self, team_name: str, days: int = 7, news_type: str = None) -> List[Dict]:
        """获取球队相关新闻"""
        conn = self._get_conn()
        c = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        query = '''
            SELECT n.* FROM news_aggregated n
            JOIN team_news_relation r ON n.id = r.news_id
            WHERE r.team_name = ?
            AND n.published_at >= ?
        '''
        params = [team_name, since]

        if news_type:
            query += ' AND n.news_type = ?'
            params.append(news_type)

        query += ' ORDER BY n.published_at DESC LIMIT 50'

        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_negative_news(self, days: int = 7) -> List[Dict]:
        """获取负面新闻"""
        conn = self._get_conn()
        c = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT * FROM news_aggregated
            WHERE sentiment <= -3
            OR news_type IN ('conflict', 'negative', 'injury')
            AND published_at >= ?
            ORDER BY sentiment ASC, published_at DESC
            LIMIT 100
        ''', (since,))

        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_team_sentiment(self, team_name: str, days: int = 30) -> Dict:
        """获取球队舆论情感趋势"""
        conn = self._get_conn()
        c = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT AVG(sentiment) as avg_sentiment,
                   COUNT(*) as news_count,
                   SUM(CASE WHEN sentiment < 0 THEN 1 ELSE 0 END) as negative_count
            FROM news_aggregated n
            JOIN team_news_relation r ON n.id = r.news_id
            WHERE r.team_name = ?
            AND n.published_at >= ?
        ''', (team_name, since))

        row = c.fetchone()
        conn.close()

        if row and row[0]:
            return {
                'team': team_name,
                'avg_sentiment': row[0],
                'news_count': row[1],
                'negative_count': row[2],
                'negative_ratio': row[2] / row[1] if row[1] > 0 else 0
            }
        return None

    # ==================== 定时采集 ====================

    def collect_all(self):
        """采集所有源"""
        total = 0
        total += self.collect_from_zhibo8()
        total += self.collect_from_dongqiudi()
        total += self.collect_from_hupu()

        logger.info(f"本轮采集完成: {total}条新新闻")
        return total


class SocialMonitor:
    """社交媒体监控 - 检测球员矛盾、更衣室问题等"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.aggregator = NewsAggregator(db_path)

    def detect_player_conflict(self, team_name: str) -> List[Dict]:
        """检测球员矛盾信号"""
        news = self.aggregator.get_team_news(team_name, days=14, news_type='conflict')

        signals = []
        for item in news:
            if item.get('sentiment', 0) < -5:
                signals.append({
                    'type': 'conflict',
                    'team': team_name,
                    'title': item['title'],
                    'sentiment': item['sentiment'],
                    'date': item['published_at']
                })

        return signals

    def detect_dressing_room_issue(self, team_name: str) -> List[Dict]:
        """检测更衣室问题"""
        keywords = ['更衣室', '内讧', '矛盾', '分裂', '不和']
        news = self.aggregator.get_team_news(team_name, days=14)

        issues = []
        for item in news:
            content = f"{item.get('title', '')} {item.get('content', '')}"
            if any(kw in content for kw in keywords):
                issues.append({
                    'type': 'dressing_room',
                    'team': team_name,
                    'title': item['title'],
                    'content': item.get('content', '')[:200],
                    'date': item['published_at']
                })

        return issues


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='新闻聚合系统')
    parser.add_argument('--collect', action='store_true', help='采集所有源')
    parser.add_argument('--team', type=str, help='查看球队新闻')
    parser.add_argument('--negative', action='store_true', help='查看负面新闻')

    args = parser.parse_args()

    aggregator = NewsAggregator()

    if args.collect:
        aggregator.collect_all()

    if args.team:
        news = aggregator.get_team_news(args.team)
        print(f"\n{args.team} 近期新闻:")
        for n in news[:10]:
            print(f"  [{n['news_type']}] {n['title']} (情感:{n['sentiment']})")

    if args.negative:
        news = aggregator.get_negative_news()
        print("\n近期负面新闻:")
        for n in news[:20]:
            print(f"  {n['title']} (情感:{n['sentiment']})")

    if not any([args.collect, args.team, args.negative]):
        print("新闻聚合系统")
        print("用法:")
        print("  python news_aggregator.py --collect           # 采集所有源")
        print("  python news_aggregator.py --team Brazil       # 查看球队新闻")
        print("  python news_aggregator.py --negative          # 查看负面新闻")
