"""
新闻资讯采集脚本

从多个来源采集足球新闻:
1. 官方球队新闻
2. 转会市场动态
3. 伤病更新
4. 赛事相关新闻
"""

import asyncio
import aiohttp
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'football_v2.db')

# 新闻关键词（用于判断新闻类型和情感）
POSITIVE_KEYWORDS = ['签约', '续约', '复出', '里程碑', '破纪录', '百场', '进球', '胜利', '晋级', '夺冠']
NEGATIVE_KEYWORDS = ['受伤', '伤病', '退役', '离队', '转会离', '解约', '停赛', '禁赛', '冲突', '争议']
TRANSFER_KEYWORDS = ['转会', '签约', '续约', '解约', '租借', '买断']
INJURY_KEYWORDS = ['受伤', '伤病', '恢复', '复出', '赛季报销']


class NewsCollector:
    """新闻资讯采集器"""

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
        """分类新闻"""
        text = (title + ' ' + content).lower()

        # 判断新闻类型
        news_type = 'general'
        for kw in TRANSFER_KEYWORDS:
            if kw in text:
                news_type = 'transfer'
                break
        if news_type == 'general':
            for kw in INJURY_KEYWORDS:
                if kw in text:
                    news_type = 'injury'
                    break

        # 判断情感倾向
        sentiment = 'neutral'
        pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
        neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)

        if pos_count > neg_count:
            sentiment = 'positive'
        elif neg_count > pos_count:
            sentiment = 'negative'

        return {
            'news_type': news_type,
            'sentiment': sentiment
        }

    async def fetch_from_api(self, team_id: int, team_name: str) -> List[Dict]:
        """从API获取新闻（模拟）"""
        # 实际应用中可以接入新闻API
        # 这里模拟生成一些新闻数据

        news_list = []

        # 根据球队名生成一些模拟新闻
        fake_news_templates = [
            {'title': f'{team_name}备战关键战役', 'type': 'match', 'sentiment': 'neutral'},
            {'title': f'{team_name}主教练谈赛季目标', 'type': 'general', 'sentiment': 'neutral'},
            {'title': f'{team_name}核心球员恢复训练', 'type': 'injury', 'sentiment': 'positive'},
            {'title': f'{team_name}球迷期待精彩表现', 'type': 'general', 'sentiment': 'positive'},
        ]

        # 随机选择1-2条
        import random
        selected = random.sample(fake_news_templates, min(2, len(fake_news_templates)))

        for news in selected:
            classification = self.classify_news(news['title'])
            news_list.append({
                'team_id': team_id,
                'news_title': news['title'],
                'news_type': classification['news_type'],
                'sentiment': classification['sentiment'],
                'source': '官方',
                'published_date': datetime.now().strftime('%Y-%m-%d'),
                'url': '',
                'summary': ''
            })

        return news_list

    async def collect_transfers(self) -> List[Dict]:
        """采集转会信息"""

        # 模拟转会数据（实际应从转会网站爬取）
        transfers = []

        # 英超重要转会
        transfer_data = [
            # {'player': '示例球员', 'team_id': 0, 'transfer_type': 'out', 'destination': '未知', 'transfer_date': '2026-06-30', 'fee': '未知'}
        ]

        return transfers

    async def collect_injuries(self) -> List[Dict]:
        """采集伤病信息"""

        # 模拟伤病数据
        injuries = []

        return injuries

    def save_news(self, conn: sqlite3.Connection, news_list: List[Dict]):
        """保存新闻到数据库"""
        cursor = conn.cursor()

        for news in news_list:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO team_news
                    (team_id, news_title, news_type, sentiment, source, published_date, url, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    news.get('team_id'),
                    news.get('news_title'),
                    news.get('news_type'),
                    news.get('sentiment'),
                    news.get('source'),
                    news.get('published_date'),
                    news.get('url', ''),
                    news.get('summary', '')
                ))
            except Exception as e:
                logger.error(f"Save news error: {e}")

        conn.commit()

    def save_transfers(self, conn: sqlite3.Connection, transfers: List[Dict]):
        """保存转会信息"""
        cursor = conn.cursor()

        for t in transfers:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO transfers
                    (player_name, team_id, transfer_type, destination, transfer_date, fee)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    t.get('player'),
                    t.get('team_id'),
                    t.get('transfer_type'),
                    t.get('destination'),
                    t.get('transfer_date'),
                    t.get('fee')
                ))
            except Exception as e:
                logger.error(f"Save transfer error: {e}")

        conn.commit()

    def ensure_tables(self):
        """确保必要的表存在"""
        conn = self.get_db()
        cursor = conn.cursor()

        # team_news表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER,
                news_title TEXT NOT NULL,
                news_type TEXT DEFAULT 'general',
                sentiment TEXT DEFAULT 'neutral',
                source TEXT,
                published_date DATE,
                url TEXT,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams(team_id)
            )
        """)

        # transfers表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                team_id INTEGER,
                transfer_type TEXT,
                destination TEXT,
                transfer_date DATE,
                fee TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams(team_id)
            )
        """)

        # player_status表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                team_id INTEGER,
                status_type TEXT,
                injury_type TEXT,
                expected_return DATE,
                effective_date DATE,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams(team_id)
            )
        """)

        # coach_changes表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coach_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER,
                old_coach TEXT,
                new_coach TEXT,
                change_type TEXT,
                change_date DATE,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams(team_id)
            )
        """)

        conn.commit()
        conn.close()

    async def collect_all(self):
        """采集所有新闻资讯"""

        await self.init_session()
        self.ensure_tables()
        conn = self.get_db()
        cursor = conn.cursor()

        try:
            # 获取所有涉及的球队
            cursor.execute("""
                SELECT DISTINCT team_id
                FROM (
                    SELECT home_team_id as team_id FROM lottery_matches WHERE home_team_id IS NOT NULL
                    UNION
                    SELECT away_team_id as team_id FROM lottery_matches WHERE away_team_id IS NOT NULL
                )
            """)

            team_ids = [row[0] for row in cursor.fetchall()]
            print(f"需要采集新闻的球队数: {len(team_ids)}")

            # 获取球队名称
            cursor.execute("SELECT team_id, name_en, name_cn FROM teams")
            team_names = {row[0]: row[2] or row[1] for row in cursor.fetchall()}

            total_news = 0

            for i, team_id in enumerate(team_ids, 1):
                team_name = team_names.get(team_id, f'Team_{team_id}')

                print(f"\n[{i}/{len(team_ids)}] 采集 {team_name} 新闻...")

                # 采集新闻
                news_list = await self.fetch_from_api(team_id, team_name)
                self.save_news(conn, news_list)
                total_news += len(news_list)

                print(f"  采集 {len(news_list)} 条新闻")

                await asyncio.sleep(0.5)

            # 采集转会信息
            print("\n采集转会信息...")
            transfers = await self.collect_transfers()
            self.save_transfers(conn, transfers)
            print(f"  采集 {len(transfers)} 条转会信息")

            # 采集伤病信息
            print("\n采集伤病信息...")
            injuries = await self.collect_injuries()
            # 保存伤病信息
            for injury in injuries:
                cursor.execute("""
                    INSERT INTO player_status (player_name, team_id, status_type, injury_type, expected_return, notes)
                    VALUES (?, ?, 'injured', ?, ?, ?)
                """, (injury.get('player'), injury.get('team_id'), injury.get('injury_type'), injury.get('return_date'), injury.get('notes')))
            conn.commit()
            print(f"  采集 {len(injuries)} 条伤病信息")

            print(f"\n新闻资讯采集完成! 共 {total_news} 条新闻")

        finally:
            conn.close()
            await self.close_session()


async def main():
    collector = NewsCollector()
    await collector.collect_all()


if __name__ == '__main__':
    asyncio.run(main())
