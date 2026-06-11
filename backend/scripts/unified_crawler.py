"""
统一爬虫服务 - 整合所有数据采集功能
包含：新闻资讯、伤病名单、阵容预测、比赛数据同步
"""

import asyncio
import sqlite3
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import re
import os
import sys

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.data_sources.manager import DataSourceManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedCrawlerService:
    """统一爬虫服务"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.manager = DataSourceManager()

        # 禁用代理
        os.environ['HTTP_PROXY'] = ''
        os.environ['HTTPS_PROXY'] = ''

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })

        # 新闻类型映射
        self.news_type_map = {
            'injury': ['伤', '受伤', '伤病', '伤缺', '伤停', '伤退'],
            'suspension': ['停赛', '红牌', '累计黄牌', '禁赛'],
            'transfer': ['转会', '签约', '加盟', '租借', '买断'],
            'return': ['复出', '回归', '伤愈', '恢复'],
            'coach': ['主帅', '教练', '主教练', '下课', '解雇', '辞职'],
            'form': ['连胜', '连败', '不败', '状态', '战绩'],
        }

    # ==================== 新闻资讯爬虫 ====================

    def crawl_news(self) -> Dict:
        """爬取新闻资讯"""
        logger.info("Crawling news from zhibo8...")
        news_list = []

        try:
            resp = self.session.get(
                "https://news.zhibo8.com/zuqiu/more.htm",
                timeout=15,
                proxies={'http': None, 'https': None}
            )
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            data_list = soup.select_one('.dataList')
            if not data_list:
                return {'error': 'No data found'}

            items = data_list.select('li')[:100]

            for item in items:
                link = item.select_one('a')
                if not link:
                    continue

                title = link.get_text(strip=True)
                href = link.get('href', '')

                if len(title) < 5:
                    continue

                time_span = item.select_one('span')
                news_time = time_span.get_text(strip=True) if time_span else ''

                news_date = datetime.now().strftime('%Y-%m-%d')
                if news_time:
                    try:
                        match = re.search(r'(\d{1,2})-(\d{1,2})', news_time)
                        if match:
                            month, day = int(match.group(1)), int(match.group(2))
                            news_date = f"{datetime.now().year}-{month:02d}-{day:02d}"
                    except:
                        pass

                news_list.append({
                    'title': title,
                    'url': href if href.startswith('http') else f"https://news.zhibo8.com{href}",
                    'date': news_date,
                    'source': 'zhibo8'
                })

        except Exception as e:
            logger.error(f"News crawl error: {e}")
            return {'error': str(e)}

        # 保存到数据库
        saved = self._save_news_to_db(news_list)
        logger.info(f"News crawled: {len(news_list)}, saved: {saved}")
        return {'crawled': len(news_list), 'saved': saved}

    def _save_news_to_db(self, news_list: List[Dict]) -> int:
        """保存新闻到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        saved = 0

        for news in news_list:
            try:
                # 检查是否已存在
                cursor.execute(
                    "SELECT news_id FROM team_news WHERE title = ? AND news_date = ?",
                    (news['title'], news['date'])
                )
                if cursor.fetchone():
                    continue

                # 解析新闻类型
                news_type, category, impact = self._parse_news(news['title'])

                # 提取球队
                team_ids = self._extract_teams(news['title'], cursor)
                if not team_ids:
                    continue

                for tid in team_ids[:2]:
                    cursor.execute("""
                        INSERT INTO team_news (
                            team_id, title, news_type, category,
                            impact_level, news_date, source, verified
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """, (tid, news['title'], news_type, category, impact,
                          news['date'], news['source']))
                    saved += 1

            except Exception as e:
                continue

        conn.commit()
        conn.close()
        return saved

    def _parse_news(self, title: str) -> tuple:
        """解析新闻类型"""
        news_type = 'other'
        for ntype, keywords in self.news_type_map.items():
            if any(kw in title for kw in keywords):
                news_type = ntype
                break

        positive = ['复出', '回归', '续约', '连胜', '签约', '加盟', '伤愈']
        negative = ['伤', '停赛', '下课', '解雇', '连败', '缺阵']

        if any(kw in title for kw in positive):
            category = 'positive'
        elif any(kw in title for kw in negative):
            category = 'negative'
        else:
            category = 'neutral'

        high_impact = ['核心', '主力', '队长', '头号', '当家']
        impact = 4 if any(kw in title for kw in high_impact) else 2

        return news_type, category, impact

    def _extract_teams(self, title: str, cursor) -> List[int]:
        """从标题提取球队ID"""
        cursor.execute("SELECT team_id, name_en, name_cn FROM teams")
        teams = cursor.fetchall()

        team_ids = []
        for team in teams:
            if team[2] and team[2] in title:
                team_ids.append(team[0])
            elif team[1] and team[1] in title:
                team_ids.append(team[0])

        return team_ids

    # ==================== 伤病名单爬虫 ====================

    def crawl_injuries(self) -> Dict:
        """爬取伤病名单"""
        logger.info("Crawling injury list...")
        injuries = []

        # 英超官方伤病名单
        try:
            resp = self.session.get(
                "https://www.premierleague.com/injuries",
                timeout=15,
                proxies={'http': None, 'https': None}
            )
            soup = BeautifulSoup(resp.text, 'html.parser')

            rows = soup.select('.tableContainer tbody tr, .injuryTable tr')

            for row in rows[:50]:
                cols = row.select('td')
                if len(cols) >= 3:
                    player_name = cols[0].get_text(strip=True)
                    team_name = cols[1].get_text(strip=True)
                    injury_type = cols[2].get_text(strip=True) if len(cols) > 2 else ''

                    injuries.append({
                        'player': player_name,
                        'team': team_name,
                        'injury_type': injury_type,
                        'source': 'premier_league_official',
                        'date': datetime.now().strftime('%Y-%m-%d')
                    })

        except Exception as e:
            logger.error(f"Injury crawl error: {e}")

        # 保存到数据库
        saved = self._save_injuries_to_db(injuries)
        logger.info(f"Injuries crawled: {len(injuries)}, saved: {saved}")
        return {'crawled': len(injuries), 'saved': saved}

    def _save_injuries_to_db(self, injuries: List[Dict]) -> int:
        """保存伤病数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        saved = 0

        for injury in injuries:
            try:
                # 查找球队ID
                cursor.execute(
                    "SELECT team_id FROM teams WHERE name_en LIKE ? OR name_cn LIKE ?",
                    (f'%{injury["team"]}%', f'%{injury["team"]}%')
                )
                team = cursor.fetchone()
                if not team:
                    continue

                # 查找球员ID
                cursor.execute(
                    "SELECT player_id FROM players WHERE name LIKE ? AND team_id = ?",
                    (f'%{injury["player"]}%', team[0])
                )
                player = cursor.fetchone()

                if player:
                    cursor.execute("""
                        INSERT OR REPLACE INTO player_status (
                            player_id, team_id, status, injury_type,
                            source, updated_at
                        ) VALUES (?, ?, 'injured', ?, ?, CURRENT_TIMESTAMP)
                    """, (player[0], team[0], injury['injury_type'], injury['source']))
                    saved += 1

            except Exception as e:
                continue

        conn.commit()
        conn.close()
        return saved

    # ==================== 阵容预测爬虫 ====================

    def crawl_lineups(self) -> Dict:
        """爬取阵容预测"""
        logger.info("Crawling lineup predictions...")
        lineups = []

        # 188比分阵容预测
        try:
            resp = self.session.get(
                "https://www.188bifen.com/lineup/",
                timeout=15,
                proxies={'http': None, 'https': None}
            )
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            matches = soup.select('.match-item, .lineup-match')

            for match in matches[:20]:
                try:
                    home_team = match.select_one('.home-team')
                    away_team = match.select_one('.away-team')
                    match_time = match.select_one('.match-time')

                    if home_team and away_team:
                        lineups.append({
                            'home_team': home_team.get_text(strip=True),
                            'away_team': away_team.get_text(strip=True),
                            'match_time': match_time.get_text(strip=True) if match_time else '',
                            'source': '188bifen',
                            'date': datetime.now().strftime('%Y-%m-%d')
                        })

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Lineup crawl error: {e}")

        logger.info(f"Lineups crawled: {len(lineups)}")
        return {'crawled': len(lineups), 'data': lineups[:5]}

    # ==================== 比赛数据同步 ====================

    async def sync_match_data(self) -> Dict:
        """同步比赛数据"""
        logger.info("Syncing match data...")
        return await self.manager.full_sync(self.db_path)

    # ==================== 统一入口 ====================

    async def run_all(self) -> Dict:
        """运行所有爬虫"""
        logger.info("=" * 60)
        logger.info("Starting unified crawler service")
        logger.info("=" * 60)

        results = {
            'timestamp': datetime.now().isoformat(),
            'news': {},
            'injuries': {},
            'lineups': {},
            'match_sync': {}
        }

        # 1. 新闻资讯
        print("\n[1/4] Crawling news...")
        results['news'] = self.crawl_news()

        # 2. 伤病名单
        print("\n[2/4] Crawling injuries...")
        results['injuries'] = self.crawl_injuries()

        # 3. 阵容预测
        print("\n[3/4] Crawling lineups...")
        results['lineups'] = self.crawl_lineups()

        # 4. 比赛数据同步
        print("\n[4/4] Syncing match data...")
        results['match_sync'] = await self.sync_match_data()

        # 汇总
        print("\n" + "=" * 60)
        print("Summary:")
        print(f"  News: {results['news'].get('saved', 0)} saved")
        print(f"  Injuries: {results['injuries'].get('saved', 0)} saved")
        print(f"  Lineups: {results['lineups'].get('crawled', 0)} crawled")
        print(f"  Match sync: {results['match_sync'].get('future', {}).get('synced', 0)} matches")
        print("=" * 60)

        return results

    def run_news_only(self) -> Dict:
        """只运行新闻爬虫"""
        return self.crawl_news()

    def run_injuries_only(self) -> Dict:
        """只运行伤病爬虫"""
        return self.crawl_injuries()

    def run_lineups_only(self) -> Dict:
        """只运行阵容爬虫"""
        return self.crawl_lineups()


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='Unified Crawler Service')
    parser.add_argument('--type', type=str, default='all',
                       choices=['all', 'news', 'injuries', 'lineups', 'sync'],
                       help='Crawler type to run')
    args = parser.parse_args()

    db_path = 'D:/football_tools/data/football_v2.db'
    crawler = UnifiedCrawlerService(db_path)

    if args.type == 'all':
        await crawler.run_all()
    elif args.type == 'news':
        result = crawler.run_news_only()
        print(f"News: {result}")
    elif args.type == 'injuries':
        result = crawler.run_injuries_only()
        print(f"Injuries: {result}")
    elif args.type == 'lineups':
        result = crawler.run_lineups_only()
        print(f"Lineups: {result}")
    elif args.type == 'sync':
        result = await crawler.sync_match_data()
        print(f"Sync: {result}")


if __name__ == '__main__':
    asyncio.run(main())
