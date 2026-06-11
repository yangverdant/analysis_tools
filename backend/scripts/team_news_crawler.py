"""
球队动态爬虫 - 获取利好/坏消息数据

数据来源:
1. 直播吧 (zhibo8.cc) - 足球新闻、赛前资讯
2. 懂球帝 (dongqiudi.com) - 球队动态、伤病消息

入库表: team_news, player_status
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import time


class TeamNewsCrawler:
    """球队动态爬虫"""

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

        # 新闻类型映射
        self.news_type_map = {
            'injury': ['伤', '受伤', '伤病', '伤缺', '伤停', '伤退', '受伤病'],
            'suspension': ['停赛', '红牌', '累计黄牌', '禁赛'],
            'transfer': ['转会', '签约', '加盟', '租借', '买断', '出售'],
            'return': ['复出', '回归', '伤愈', '恢复', '回归训练'],
            'coach': ['主帅', '教练', '主教练', '下课', '解雇', '辞职', '续约'],
            'form': ['连胜', '连败', '不败', '状态', '战绩'],
        }

        # 影响类型映射
        self.impact_type_map = {
            'key_player_injury': ['核心', '主力', '队长', '头号', '当家'],
            'star_player_return': ['核心', '主力', '当家', '头号'],
            'multiple_injuries': ['多人', '多名', '伤病潮'],
        }

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def parse_news_type(self, title: str, content: str = '') -> tuple:
        """解析新闻类型和影响类型"""
        text = f"{title} {content}"

        # 判断新闻类型
        news_type = 'other'
        for ntype, keywords in self.news_type_map.items():
            if any(kw in text for kw in keywords):
                news_type = ntype
                break

        # 判断影响类型
        impact_type = None
        if news_type == 'injury':
            for itype, keywords in self.impact_type_map.items():
                if any(kw in text for kw in keywords):
                    impact_type = itype
                    break
            if not impact_type:
                impact_type = 'player_injury'
        elif news_type == 'suspension':
            impact_type = 'suspension'
        elif news_type == 'return':
            impact_type = 'star_player_return'
        elif news_type == 'coach':
            impact_type = 'coach_change'
        elif news_type == 'transfer':
            impact_type = 'transfer'

        # 判断正负面
        positive_keywords = ['复出', '回归', '续约', '连胜', '签约', '加盟', '伤愈', '恢复']
        negative_keywords = ['伤', '停赛', '下课', '解雇', '连败', '缺阵', '缺席']

        if any(kw in text for kw in positive_keywords):
            category = 'positive'
        elif any(kw in text for kw in negative_keywords):
            category = 'negative'
        else:
            category = 'neutral'

        return news_type, impact_type, category

    def calculate_impact_level(self, title: str, content: str = '', category: str = 'neutral') -> int:
        """计算影响程度 (1-5)"""
        text = f"{title} {content}"

        # 高影响关键词
        high_impact = ['核心', '主力', '队长', '头号', '当家', '多人', '多名']
        # 中等影响关键词
        mid_impact = ['重要', '关键', '首发']

        if any(kw in text for kw in high_impact):
            return 4 if category == 'negative' else 3
        elif any(kw in text for kw in mid_impact):
            return 3 if category == 'negative' else 2
        else:
            return 2

    # ==================== 直播吧爬虫 ====================

    def crawl_zhibo8_news(self, pages: int = 3) -> List[Dict]:
        """爬取直播吧足球新闻"""
        news_list = []
        base_url = "https://news.zhibo8.com/zuqiu/more.htm"

        try:
            resp = self.session.get(base_url, timeout=15, proxies={'http': None, 'https': None})
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 查找 dataList 区域
            data_list = soup.select_one('.dataList')
            if not data_list:
                print("未找到 dataList 区域")
                return news_list

            # 查找所有新闻项
            items = data_list.select('li')
            print(f"找到 {len(items)} 条新闻项")

            for item in items[:100]:  # 限制数量
                try:
                    link = item.select_one('a')
                    if not link:
                        continue

                    title = link.get_text(strip=True)
                    href = link.get('href', '')

                    if not title or len(title) < 5:
                        continue

                    # 获取时间
                    time_span = item.select_one('span')
                    news_time = time_span.get_text(strip=True) if time_span else ''

                    # 解析日期
                    news_date = datetime.now().strftime('%Y-%m-%d')
                    if news_time:
                        # 尝试解析时间格式如 "05-21 10:30"
                        try:
                            time_match = re.search(r'(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})', news_time)
                            if time_match:
                                month, day = int(time_match.group(1)), int(time_match.group(2))
                                news_date = f"{datetime.now().year}-{month:02d}-{day:02d}"
                        except Exception:
                            pass

                    news_list.append({
                        'title': title,
                        'url': href if href.startswith('http') else f"https://news.zhibo8.com{href}",
                        'date': news_date,
                        'source': 'zhibo8'
                    })

                except Exception as e:
                    continue

        except Exception as e:
            print(f"爬取直播吧新闻失败: {e}")

        return news_list

    def crawl_zhibo8_team_news(self, team_name: str) -> List[Dict]:
        """爬取直播吧特定球队新闻"""
        news_list = []
        search_url = f"https://news.zhibo8.com/zuqiu/search.htm?keyword={team_name}"

        try:
            resp = self.session.get(search_url, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 查找搜索结果
            items = soup.select('.news_list li, .list li, .result li')

            for item in items[:20]:
                try:
                    link = item.select_one('a')
                    if not link:
                        continue

                    title = link.get_text(strip=True)
                    href = link.get('href', '')

                    if team_name not in title:
                        continue

                    news_list.append({
                        'title': title,
                        'url': href if href.startswith('http') else f"https://news.zhibo8.com{href}",
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'source': 'zhibo8'
                    })

                except Exception:
                    continue

        except Exception as e:
            print(f"爬取球队新闻失败: {e}")

        return news_list

    # ==================== 懂球帝爬虫 ====================

    def crawl_dongqiudi_news(self) -> List[Dict]:
        """爬取懂球帝新闻（通过网页版）"""
        news_list = []

        try:
            # 尝试获取懂球帝数据页
            resp = self.session.get('https://www.dongqiudi.com/', timeout=10)
            resp.encoding = 'utf-8'

            # 懂球帝是SPA应用，需要解析内嵌数据
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 查找新闻数据
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'window.__NUXT__' in script.string:
                    # 解析NUXT数据
                    try:
                        data_match = re.search(r'window\.__NUXT__\s*=\s*(\{.*?\});', script.string, re.DOTALL)
                        if data_match:
                            # 这里需要更复杂的JSON解析
                            pass
                    except Exception:
                        pass

        except Exception as e:
            print(f"爬取懂球帝新闻失败: {e}")

        return news_list

    # ==================== 伤病数据爬取 ====================

    def crawl_premier_league_injuries(self) -> List[Dict]:
        """爬取英超官网伤病名单"""
        injuries = []
        url = "https://www.premierleague.com/injuries"

        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 解析伤病表格
            rows = soup.select('.tableContainer tbody tr, .injuryTable tr')

            for row in rows:
                try:
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
                except Exception:
                    continue

        except Exception as e:
            print(f"爬取英超伤病名单失败: {e}")

        return injuries

    # ==================== 数据入库 ====================

    def extract_teams_from_news(self, title: str, conn) -> List[int]:
        """从新闻标题中提取球队ID"""
        cursor = conn.cursor()

        # 获取所有球队名称
        cursor.execute("SELECT team_id, name_en, name_cn FROM teams")
        teams = cursor.fetchall()

        team_ids = []
        for team in teams:
            # 检查球队名称是否在标题中
            if team['name_cn'] and team['name_cn'] in title:
                team_ids.append(team['team_id'])
            elif team['name_en'] and team['name_en'] in title:
                team_ids.append(team['team_id'])

        return team_ids

    def save_news_to_db(self, news_list: List[Dict], team_id: Optional[int] = None):
        """保存新闻到数据库"""
        conn = self.get_connection()
        cursor = conn.cursor()

        saved_count = 0
        for news in news_list:
            try:
                # 解析新闻类型
                news_type, impact_type, category = self.parse_news_type(news['title'], news.get('content', ''))
                impact_level = self.calculate_impact_level(news['title'], news.get('content', ''), category)

                # 检查是否已存在
                cursor.execute("""
                    SELECT news_id FROM team_news
                    WHERE title = ? AND news_date = ?
                """, (news['title'], news['date']))

                if cursor.fetchone():
                    continue

                # 提取球队ID
                team_ids = self.extract_teams_from_news(news['title'], conn) if not team_id else [team_id]

                if not team_ids:
                    # 如果没有匹配到球队，跳过该新闻
                    continue

                # 为每个匹配的球队插入新闻
                for tid in team_ids[:2]:  # 最多关联2个球队
                    cursor.execute("""
                        INSERT INTO team_news (
                            team_id, title, content, news_type, category,
                            impact_level, impact_type, news_date, source, verified
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """, (
                        tid,
                        news['title'],
                        news.get('content', ''),
                        news_type,
                        category,
                        impact_level,
                        impact_type,
                        news['date'],
                        news['source']
                    ))
                    saved_count += 1

            except Exception as e:
                print(f"保存新闻失败: {e}")
                continue

        conn.commit()
        conn.close()
        return saved_count

    def save_injuries_to_db(self, injuries: List[Dict]):
        """保存伤病数据到数据库"""
        conn = self.get_connection()
        cursor = conn.cursor()

        saved_count = 0
        for injury in injuries:
            try:
                # 查找球队ID
                cursor.execute("""
                    SELECT team_id FROM teams
                    WHERE name_en LIKE ? OR name_cn LIKE ?
                """, (f"%{injury['team']}%", f"%{injury['team']}%"))
                team_row = cursor.fetchone()

                if not team_row:
                    continue

                team_id = team_row['team_id']

                # 查找球员ID
                cursor.execute("""
                    SELECT player_id FROM players
                    WHERE team_id = ? AND (name_en LIKE ? OR name_cn LIKE ?)
                """, (team_id, f"%{injury['player']}%", f"%{injury['player']}%"))
                player_row = cursor.fetchone()

                player_id = player_row['player_id'] if player_row else None

                # 更新或插入球员状态
                if player_id:
                    cursor.execute("""
                        INSERT OR REPLACE INTO player_status (
                            player_id, team_id, status, injury_type,
                            source, updated_at
                        ) VALUES (?, ?, 'injured', ?, 'premier_league_official', CURRENT_TIMESTAMP)
                    """, (player_id, team_id, injury['injury_type']))

                # 同时插入team_news
                cursor.execute("""
                    INSERT INTO team_news (
                        team_id, title, news_type, category,
                        impact_level, impact_type, news_date, source, verified
                    ) VALUES (?, ?, 'injury', 'negative', 3, 'player_injury', ?, 'premier_league_official', 1)
                """, (
                    team_id,
                    f"{injury['player']}因{injury['injury_type']}缺阵",
                    injury['date']
                ))

                saved_count += 1

            except Exception as e:
                continue

        conn.commit()
        conn.close()
        return saved_count

    # ==================== 主运行函数 ====================

    def run(self, crawl_injuries: bool = True, crawl_news: bool = True):
        """运行爬虫"""
        print("=" * 50)
        print("球队动态爬虫启动")
        print("=" * 50)

        total_saved = 0

        # 1. 爬取直播吧新闻
        if crawl_news:
            print("\n[1] 爬取直播吧足球新闻...")
            news = self.crawl_zhibo8_news()
            print(f"  获取到 {len(news)} 条新闻")

            if news:
                saved = self.save_news_to_db(news)
                print(f"  保存 {saved} 条新闻到数据库")
                total_saved += saved

        # 2. 爬取英超伤病名单
        if crawl_injuries:
            print("\n[2] 爬取英超伤病名单...")
            injuries = self.crawl_premier_league_injuries()
            print(f"  获取到 {len(injuries)} 条伤病信息")

            if injuries:
                saved = self.save_injuries_to_db(injuries)
                print(f"  保存 {saved} 条伤病信息到数据库")
                total_saved += saved

        print(f"\n总计保存 {total_saved} 条数据")
        return total_saved


def main():
    """主函数"""
    db_path = r"d:\football_tools\data\football_v2.db"
    crawler = TeamNewsCrawler(db_path)

    # 运行爬虫
    crawler.run(crawl_injuries=True, crawl_news=True)


if __name__ == "__main__":
    main()
