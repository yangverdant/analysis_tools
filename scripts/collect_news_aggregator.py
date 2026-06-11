"""
新闻资讯采集服务

从多个来源采集足球相关新闻:
1. 球队官方新闻
2. 转会市场动态
3. 伤病更新
4. 教练动态
5. 球员合同/退役信息

数据来源:
- RSS feeds
- 新闻API
- 社交媒体
"""

import asyncio
import aiohttp
import sqlite3
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'football_v2.db')

# 新闻关键词映射
NEWS_KEYWORDS = {
    # 转会相关
    'transfer': ['转会', '签约', '加盟', '引进', '出售', '租借', '买断', '续约', '解约', '自由身'],
    # 伤病相关
    'injury': ['受伤', '伤病', '伤缺', '赛季报销', '恢复训练', '复出', '伤愈'],
    # 教练相关
    'coach': ['主帅', '主教练', '教练', '执教', '下课', '辞职', '续约'],
    # 退役/告别
    'retirement': ['退役', '告别', '最后一场', '告别赛', '挂靴'],
    # 合同相关
    'contract': ['合同', '续约', '到期', '解约'],
    # 赛事相关
    'match': ['德比', '关键战', '生死战', '决战', '争冠', '保级'],
}

# 情感分析关键词
POSITIVE_WORDS = ['签约', '续约', '复出', '夺冠', '晋级', '破纪录', '里程碑', '百场', '连胜', '大胜']
NEGATIVE_WORDS = ['受伤', '伤病', '退役', '离队', '解约', '停赛', '禁赛', '连败', '降级', '下课']


class NewsAggregator:
    """新闻资讯聚合器"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.session: Optional[aiohttp.ClientSession] = None

    async def init_session(self):
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    def get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def classify_news(self, title: str, content: str = '') -> Dict:
        """分类新闻并判断情感"""
        text = (title + ' ' + content).lower()

        # 判断新闻类型
        news_type = 'general'
        type_scores = {}
        for ntype, keywords in NEWS_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                type_scores[ntype] = score

        if type_scores:
            news_type = max(type_scores.keys(), key=lambda k: type_scores[k])

        # 判断情感
        pos_count = sum(1 for w in POSITIVE_WORDS if w in text)
        neg_count = sum(1 for w in NEGATIVE_WORDS if w in text)

        if pos_count > neg_count:
            sentiment = 'positive'
        elif neg_count > pos_count:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        return {
            'news_type': news_type,
            'sentiment': sentiment,
            'type_scores': type_scores
        }

    def extract_entities(self, title: str, teams: Dict[str, int]) -> List[int]:
        """从标题中提取涉及的球队ID"""
        involved_teams = []
        for team_name, team_id in teams.items():
            if team_name in title:
                involved_teams.append(team_id)
        return list(set(involved_teams))

    async def fetch_football_news(self) -> List[Dict]:
        """
        从足球新闻源获取新闻

        实际应用中可接入:
        - BBC Sport Football RSS
        - Sky Sports RSS
        - ESPN FC
        - Goal.com
        - 国内: 虎扑、懂球帝、直播吧
        """
        news_items = []

        # 模拟新闻数据 - 实际应用中替换为真实API调用
        # 这里提供一些基于当前赛程的模拟新闻
        mock_news = [
            # 英超新闻
            {
                'title': '利物浦争冠关键战，克洛普赛前发布会表态',
                'summary': '利物浦主帅克洛普表示球队将全力以赴争取胜利',
                'source': 'BBC Sport',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'teams': ['利物浦'],
            },
            {
                'title': '曼城面临争冠压力，瓜迪奥拉调整战术',
                'summary': '曼城主帅瓜迪奥拉表示将根据对手调整首发阵容',
                'source': 'Sky Sports',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'teams': ['曼城'],
            },
            {
                'title': '阿森纳客场挑战水晶宫，争冠不容有失',
                'summary': '阿森纳必须客场取胜才能保持争冠希望',
                'source': 'ESPN',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'teams': ['阿森纳', '水晶宫'],
            },
            # 意甲新闻
            {
                'title': '那不勒斯争冠希望，主场迎战乌迪内斯',
                'summary': '那不勒斯需要全取三分保持争冠希望',
                'source': '意大利足球',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'teams': ['那不勒斯', '乌迪内斯'],
            },
            {
                'title': 'AC米兰赛季末战，欧战资格待定',
                'summary': 'AC米兰需要在最后几轮全力争胜确保欧战资格',
                'source': '米兰体育报',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'teams': ['AC米兰'],
            },
            {
                'title': '尤文图斯争四关键战，客场挑战都灵',
                'summary': '尤文图斯必须取胜才能确保下赛季欧冠资格',
                'source': '都灵体育报',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'teams': ['尤文', '都灵'],
            },
            # 转会传闻
            {
                'title': '夏季转会窗口即将开启，多队酝酿大手笔',
                'summary': '英超多支球队准备在夏季转会窗口进行补强',
                'source': '转会市场',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'teams': [],
            },
            # 伤病更新
            {
                'title': '赛季末期多队面临伤病困扰',
                'summary': '赛季末期密集赛程导致多支球队出现伤病情况',
                'source': '体育资讯',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'teams': [],
            },
        ]

        return mock_news

    async def fetch_transfer_news(self) -> List[Dict]:
        """获取转会市场动态"""
        # 模拟转会数据
        transfers = [
            # 这里可以接入TransferMarkt等数据源
        ]
        return transfers

    async def fetch_injury_news(self) -> List[Dict]:
        """获取伤病更新"""
        injuries = [
            # 可以接入伤病数据库
        ]
        return injuries

    def save_news(self, conn: sqlite3.Connection, news_list: List[Dict], team_mapping: Dict[str, int]):
        """保存新闻到数据库"""
        cursor = conn.cursor()

        saved = 0
        for news in news_list:
            try:
                classification = self.classify_news(news['title'], news.get('summary', ''))

                # 提取涉及的球队
                team_ids = self.extract_entities(news['title'], team_mapping)
                if not team_ids and news.get('teams'):
                    for team_name in news['teams']:
                        if team_name in team_mapping:
                            team_ids.append(team_mapping[team_name])

                # 如果有涉及的球队，为每个球队保存一条记录
                if team_ids:
                    for team_id in team_ids:
                        cursor.execute("""
                            INSERT INTO team_news
                            (team_id, title, content, news_type, category, impact_level, impact_type, news_date, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            team_id,
                            news['title'],
                            news.get('summary', ''),
                            classification['news_type'],
                            classification['news_type'],
                            2 if classification['sentiment'] != 'neutral' else 1,
                            classification['sentiment'],
                            news.get('date', datetime.now().strftime('%Y-%m-%d')),
                            news.get('source', '未知')
                        ))
                        saved += 1
                else:
                    # 没有明确球队的新闻保存为通用新闻
                    cursor.execute("""
                        INSERT INTO team_news
                        (team_id, title, content, news_type, category, impact_level, impact_type, news_date, source)
                        VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        news['title'],
                        news.get('summary', ''),
                        classification['news_type'],
                        classification['news_type'],
                        2 if classification['sentiment'] != 'neutral' else 1,
                        classification['sentiment'],
                        news.get('date', datetime.now().strftime('%Y-%m-%d')),
                        news.get('source', '未知')
                    ))
                    saved += 1

            except Exception as e:
                logger.error(f"Save news error: {e}")

        conn.commit()
        return saved

    def ensure_tables(self):
        """确保必要的表存在"""
        conn = self.get_db()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER,
                news_title TEXT NOT NULL,
                news_type TEXT DEFAULT 'general',
                sentiment TEXT DEFAULT 'neutral',
                source TEXT,
                published_date DATE,
                summary TEXT,
                url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    async def collect_all_news(self):
        """采集所有新闻"""

        await self.init_session()
        self.ensure_tables()
        conn = self.get_db()
        cursor = conn.cursor()

        try:
            # 获取球队名称映射
            cursor.execute("SELECT team_id, name_cn, name_en FROM teams")
            team_mapping = {}
            for row in cursor.fetchall():
                if row[1]:
                    team_mapping[row[1]] = row[0]
                if row[2]:
                    team_mapping[row[2]] = row[0]

            print("开始采集新闻资讯...")
            print("=" * 60)

            # 采集足球新闻
            print("\n1. 采集足球新闻...")
            news = await self.fetch_football_news()
            saved = self.save_news(conn, news, team_mapping)
            print(f"   保存 {saved} 条新闻")

            # 采集转会新闻
            print("\n2. 采集转会动态...")
            transfers = await self.fetch_transfer_news()
            # 保存转会信息
            for t in transfers:
                cursor.execute("""
                    INSERT OR REPLACE INTO transfers
                    (player_name, team_id, transfer_type, destination, transfer_date, fee)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (t.get('player'), t.get('team_id'), t.get('type'),
                      t.get('destination'), t.get('date'), t.get('fee')))
            conn.commit()
            print(f"   保存 {len(transfers)} 条转会信息")

            # 采集伤病信息
            print("\n3. 采集伤病更新...")
            injuries = await self.fetch_injury_news()
            for injury in injuries:
                cursor.execute("""
                    INSERT INTO player_status
                    (player_name, team_id, status_type, injury_type, expected_return, notes)
                    VALUES (?, ?, 'injured', ?, ?, ?)
                """, (injury.get('player'), injury.get('team_id'),
                      injury.get('injury_type'), injury.get('return_date'), injury.get('notes')))
            conn.commit()
            print(f"   保存 {len(injuries)} 条伤病信息")

            print("\n" + "=" * 60)
            print("新闻资讯采集完成!")

        finally:
            conn.close()
            await self.close_session()


async def main():
    aggregator = NewsAggregator()
    await aggregator.collect_all_news()


if __name__ == '__main__':
    asyncio.run(main())
