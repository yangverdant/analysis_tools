"""
综合资讯爬虫 - 多数据源获取球队动态

数据来源:
1. 直播吧 (zhibo8.cc) - 足球新闻、赛前资讯
2. 188比分 (188bifen.com) - 比分、阵容预测
3. 足球数据API - 伤病、停赛数据

入库表: team_news, player_status
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import os
import json
from datetime import datetime
from typing import List, Dict, Optional
import time


class ComprehensiveNewsCrawler:
    """综合资讯爬虫"""

    def __init__(self, db_path: str):
        self.db_path = db_path

        # 禁用代理
        os.environ['HTTP_PROXY'] = ''
        os.environ['HTTPS_PROXY'] = ''

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })

        # 新闻类型关键词
        self.news_keywords = {
            'injury': ['伤', '受伤', '伤病', '伤缺', '伤停', '伤退', '受伤病', '缺阵', '缺席'],
            'suspension': ['停赛', '红牌', '累计黄牌', '禁赛', '罚下'],
            'transfer': ['转会', '签约', '加盟', '租借', '买断', '出售', '引进'],
            'return': ['复出', '回归', '伤愈', '恢复', '回归训练', '重返'],
            'coach': ['主帅', '教练', '主教练', '下课', '解雇', '辞职', '续约', '任命'],
            'form': ['连胜', '连败', '不败', '状态', '战绩', '连胜纪录'],
        }

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ==================== 直播吧爬虫 ====================

    def crawl_zhibo8_news(self) -> List[Dict]:
        """爬取直播吧足球新闻"""
        news_list = []
        url = "https://news.zhibo8.com/zuqiu/more.htm"

        try:
            resp = self.session.get(url, timeout=15, proxies={'http': None, 'https': None})
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            data_list = soup.select_one('.dataList')
            if not data_list:
                return news_list

            items = data_list.select('li')
            print(f"直播吧: 找到 {len(items)} 条新闻")

            for item in items[:100]:
                link = item.select_one('a')
                if not link:
                    continue

                title = link.get_text(strip=True)
                href = link.get('href', '')

                if not title or len(title) < 5:
                    continue

                time_span = item.select_one('span')
                news_time = time_span.get_text(strip=True) if time_span else ''

                news_date = datetime.now().strftime('%Y-%m-%d')
                if news_time:
                    try:
                        time_match = re.search(r'(\d{1,2})-(\d{1,2})', news_time)
                        if time_match:
                            month, day = int(time_match.group(1)), int(time_match.group(2))
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
            print(f"直播吧爬取失败: {e}")

        return news_list

    def crawl_zhibo8_team_news(self, team_name: str) -> List[Dict]:
        """爬取直播吧特定球队新闻"""
        news_list = []
        url = f"https://news.zhibo8.com/zuqiu/search.htm?keyword={team_name}"

        try:
            resp = self.session.get(url, timeout=15, proxies={'http': None, 'https': None})
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            data_list = soup.select_one('.dataList')
            if data_list:
                items = data_list.select('li')
                for item in items[:30]:
                    link = item.select_one('a')
                    if link:
                        title = link.get_text(strip=True)
                        href = link.get('href', '')
                        if team_name in title:
                            news_list.append({
                                'title': title,
                                'url': href if href.startswith('http') else f"https://news.zhibo8.com{href}",
                                'date': datetime.now().strftime('%Y-%m-%d'),
                                'source': 'zhibo8_search'
                            })

        except Exception as e:
            print(f"球队新闻爬取失败: {e}")

        return news_list

    # ==================== 188比分爬虫 ====================

    def crawl_188bifen_lineups(self) -> List[Dict]:
        """爬取188比分阵容预测"""
        lineups = []
        url = "https://www.188bifen.com"

        try:
            resp = self.session.get(url, timeout=15, proxies={'http': None, 'https': None})
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 查找比赛列表
            matches = soup.select('.match-item, .game-item, tr[data-match]')
            print(f"188比分: 找到 {len(matches)} 场比赛")

            for match in matches[:20]:
                try:
                    # 解析比赛信息
                    home_team = match.select_one('.home-team, .team-home')
                    away_team = match.select_one('.away-team, .team-away')
                    match_time = match.select_one('.time, .match-time')

                    if home_team and away_team:
                        lineups.append({
                            'home_team': home_team.get_text(strip=True),
                            'away_team': away_team.get_text(strip=True),
                            'time': match_time.get_text(strip=True) if match_time else '',
                            'source': '188bifen'
                        })
                except:
                    continue

        except Exception as e:
            print(f"188比分爬取失败: {e}")

        return lineups

    # ==================== apifootball 伤病数据 ====================

    def crawl_apifootball_injuries(self, api_key: str) -> List[Dict]:
        """通过apifootball API获取伤病数据"""
        injuries = []
        url = "https://apifootball.com/api/"

        try:
            # 获取当前赛季的伤病列表
            params = {
                'action': 'get_injuries',
                'APIkey': api_key,
                'league_id': '148',  # 英超
                'from': datetime.now().strftime('%Y-%m-%d'),
                'to': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            }

            resp = self.session.get(url, params=params, timeout=15, proxies={'http': None, 'https': None})
            data = resp.json()

            if isinstance(data, list):
                print(f"apifootball: 找到 {len(data)} 条伤病信息")
                for item in data:
                    injuries.append({
                        'player': item.get('player_name', ''),
                        'team': item.get('team_name', ''),
                        'injury_type': item.get('injury_type', ''),
                        'match_missed': item.get('match_missed', ''),
                        'source': 'apifootball',
                        'date': datetime.now().strftime('%Y-%m-%d')
                    })

        except Exception as e:
            print(f"apifootball伤病爬取失败: {e}")

        return injuries

    # ==================== 数据处理 ====================

    def parse_news_type(self, title: str) -> tuple:
        """解析新闻类型"""
        for news_type, keywords in self.news_keywords.items():
            if any(kw in title for kw in keywords):
                # 判断正负面
                positive_kw = ['复出', '回归', '续约', '连胜', '签约', '加盟', '伤愈']
                negative_kw = ['伤', '停赛', '下课', '解雇', '连败', '缺阵', '缺席']

                if any(kw in title for kw in positive_kw):
                    category = 'positive'
                elif any(kw in title for kw in negative_kw):
                    category = 'negative'
                else:
                    category = 'neutral'

                return news_type, category

        return 'other', 'neutral'

    def calculate_impact_level(self, title: str, category: str) -> int:
        """计算影响程度"""
        high_kw = ['核心', '主力', '队长', '头号', '当家', '多人', '多名']
        mid_kw = ['重要', '关键', '首发']

        if any(kw in title for kw in high_kw):
            return 4 if category == 'negative' else 3
        elif any(kw in title for kw in mid_kw):
            return 3 if category == 'negative' else 2
        return 2

    def extract_teams_from_news(self, title: str, conn) -> List[int]:
        """从新闻标题提取球队ID"""
        cursor = conn.cursor()
        cursor.execute("SELECT team_id, name_en, name_cn FROM teams")
        teams = cursor.fetchall()

        team_ids = []
        for team in teams:
            if team['name_cn'] and team['name_cn'] in title:
                team_ids.append(team['team_id'])
            elif team['name_en'] and team['name_en'] in title:
                team_ids.append(team['team_id'])

        return team_ids

    def save_news_to_db(self, news_list: List[Dict]) -> int:
        """保存新闻到数据库"""
        conn = self.get_connection()
        cursor = conn.cursor()

        saved_count = 0
        for news in news_list:
            try:
                news_type, category = self.parse_news_type(news['title'])
                impact_level = self.calculate_impact_level(news['title'], category)

                # 检查是否已存在
                cursor.execute("SELECT news_id FROM team_news WHERE title = ? AND news_date = ?",
                              (news['title'], news['date']))
                if cursor.fetchone():
                    continue

                # 提取球队ID
                team_ids = self.extract_teams_from_news(news['title'], conn)
                if not team_ids:
                    continue

                for tid in team_ids[:2]:
                    cursor.execute("""
                        INSERT INTO team_news (team_id, title, news_type, category, impact_level, news_date, source, verified)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """, (tid, news['title'], news_type, category, impact_level, news['date'], news['source']))
                    saved_count += 1

            except Exception as e:
                continue

        conn.commit()
        conn.close()
        return saved_count

    # ==================== 主运行函数 ====================

    def run(self):
        """运行所有爬虫"""
        print("=" * 60)
        print("综合资讯爬虫启动")
        print("=" * 60)

        total_saved = 0

        # 1. 直播吧新闻
        print("\n[1] 爬取直播吧足球新闻...")
        news = self.crawl_zhibo8_news()
        if news:
            saved = self.save_news_to_db(news)
            print(f"    保存 {saved} 条新闻")
            total_saved += saved

        # 2. 188比分阵容
        print("\n[2] 爬取188比分阵容预测...")
        lineups = self.crawl_188bifen_lineups()
        print(f"    获取 {len(lineups)} 场比赛阵容信息")

        print(f"\n总计保存 {total_saved} 条数据")
        return total_saved


def main():
    db_path = r"d:\football_tools\data\football_v2.db"
    crawler = ComprehensiveNewsCrawler(db_path)
    crawler.run()


if __name__ == "__main__":
    main()