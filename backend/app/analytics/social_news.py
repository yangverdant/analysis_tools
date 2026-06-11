"""
社交媒体新闻聚合模块

功能:
1. 微博足球新闻抓取
2. Twitter足球资讯
3. Facebook球队动态
4. 多源新闻整合和去重

支持平台:
- 微博 (weibo.com)
- Twitter/X (x.com)
- Facebook (facebook.com)
- 虎扑 (hupu.com)
- 直播吧 (zhibo8.cc)
"""

import requests
import sqlite3
import os
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
import time


@dataclass
class NewsItem:
    """新闻条目"""
    title: str
    content: str
    source: str
    url: str
    published_at: str
    team_mentioned: List[str]
    sentiment: str  # positive, negative, neutral


class SocialMediaNewsAggregator:
    """社交媒体新闻聚合器"""

    def __init__(self, db_path: str):
        self.db_path = db_path

        # 禁用代理
        os.environ['HTTP_PROXY'] = ''
        os.environ['HTTPS_PROXY'] = ''
        os.environ['http_proxy'] = ''
        os.environ['https_proxy'] = ''

        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        # 球队名称映射
        self.team_keywords = {
            '曼城': ['曼城', 'Man City', 'Manchester City', 'MCFC'],
            '曼联': ['曼联', 'Man United', 'Manchester United', 'MUFC'],
            '利物浦': ['利物浦', 'Liverpool', 'LFC'],
            '切尔西': ['切尔西', 'Chelsea', 'CFC'],
            '阿森纳': ['阿森纳', 'Arsenal', 'AFC'],
            '热刺': ['热刺', 'Tottenham', 'Spurs'],
            '皇马': ['皇马', 'Real Madrid', 'RealMadrid'],
            '巴萨': ['巴萨', 'Barcelona', 'Barca'],
            '拜仁': ['拜仁', 'Bayern', 'FC Bayern'],
            '巴黎': ['巴黎', 'PSG', 'Paris Saint-Germain'],
            '尤文': ['尤文', 'Juventus', 'Juve'],
            '国米': ['国米', 'Inter', 'Inter Milan'],
            '米兰': ['米兰', 'AC Milan', 'Milan'],
        }

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ==================== 微博 ====================

    def get_weibo_football_news(self, keyword: str = '足球') -> List[NewsItem]:
        """
        获取微博足球新闻

        Args:
            keyword: 搜索关键词

        Returns:
            新闻列表
        """
        news_list = []

        try:
            # 微博搜索API（公开接口）
            url = "https://m.weibo.cn/api/container/getIndex"
            params = {
                'containerid': f'100103type=1&q={keyword}',
                'page_type': 'searchall'
            }

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                cards = data.get('data', {}).get('cards', [])

                for card in cards:
                    if card.get('card_type') == 9:  # 微博卡片
                        mblog = card.get('mblog', {})
                        if mblog:
                            news_list.append(NewsItem(
                                title=self._clean_text(mblog.get('text', ''))[:100],
                                content=self._clean_text(mblog.get('text', '')),
                                source='weibo',
                                url=f"https://m.weibo.cn/detail/{card.get('id')}",
                                published_at=self._parse_weibo_time(mblog.get('created_at')),
                                team_mentioned=self._extract_teams(mblog.get('text', '')),
                                sentiment=self._analyze_sentiment(mblog.get('text', ''))
                            ))

        except Exception as e:
            print(f"获取微博新闻失败: {e}")

        return news_list

    def get_weibo_team_news(self, team_name: str) -> List[NewsItem]:
        """获取特定球队的微博新闻"""
        return self.get_weibo_football_news(team_name)

    # ==================== Twitter/X ====================

    def get_twitter_football_news(self, accounts: List[str] = None) -> List[NewsItem]:
        """
        获取Twitter足球新闻

        注意：Twitter API需要认证，这里使用公开RSS或Nitter

        Args:
            accounts: Twitter账号列表

        Returns:
            新闻列表
        """
        news_list = []

        # 推荐足球账号
        default_accounts = [
            'FabrizioRomano',  # 转会专家
            'SkySportsNews',
            'BBCSport',
            'ESPNFC',
            'TheAthleticFC'
        ]

        accounts = accounts or default_accounts

        for account in accounts[:3]:  # 限制请求数
            try:
                # 使用Nitter（Twitter开源前端）
                url = f"https://nitter.net/{account}/rss"

                response = self.session.get(url, timeout=10)

                if response.status_code == 200:
                    # 解析RSS
                    items = self._parse_rss(response.text)
                    for item in items:
                        news_list.append(NewsItem(
                            title=item.get('title', ''),
                            content=item.get('description', ''),
                            source='twitter',
                            url=item.get('link', ''),
                            published_at=item.get('pubDate', ''),
                            team_mentioned=self._extract_teams(item.get('title', '') + ' ' + item.get('description', '')),
                            sentiment=self._analyze_sentiment(item.get('title', ''))
                        ))

            except Exception as e:
                print(f"获取Twitter @{account} 失败: {e}")
                continue

        return news_list

    # ==================== Facebook ====================

    def get_facebook_team_news(self, team_name: str) -> List[NewsItem]:
        """
        获取Facebook球队动态

        注意：Facebook需要登录，这里使用公开页面RSS
        """
        news_list = []

        # Facebook公开页面通常有RSS
        # 这里返回空，实际使用需要配置RSS源
        return news_list

    # ==================== 虎扑 ====================

    def get_hupu_football_news(self) -> List[NewsItem]:
        """获取虎扑足球新闻"""
        news_list = []

        try:
            url = "https://m.hupu.com/api/soccer/news"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()
                articles = data.get('data', {}).get('list', [])

                for article in articles[:10]:
                    news_list.append(NewsItem(
                        title=article.get('title', ''),
                        content=article.get('summary', ''),
                        source='hupu',
                        url=f"https://m.hupu.com/soccer/{article.get('id')}.html",
                        published_at=article.get('ptime', ''),
                        team_mentioned=self._extract_teams(article.get('title', '')),
                        sentiment=self._analyze_sentiment(article.get('title', ''))
                    ))

        except Exception as e:
            print(f"获取虎扑新闻失败: {e}")

        return news_list

    # ==================== 直播吧 ====================

    def get_zhibo8_news(self) -> List[NewsItem]:
        """获取直播吧新闻"""
        news_list = []

        try:
            url = "https://news.zhibo8.cc/api/news/list"

            params = {
                'category': '足球',
                'page': 1,
                'size': 20
            }

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                articles = data.get('data', {}).get('list', [])

                for article in articles[:10]:
                    news_list.append(NewsItem(
                        title=article.get('title', ''),
                        content=article.get('summary', ''),
                        source='zhibo8',
                        url=f"https://news.zhibo8.cc/article/{article.get('id')}",
                        published_at=article.get('publishTime', ''),
                        team_mentioned=self._extract_teams(article.get('title', '')),
                        sentiment=self._analyze_sentiment(article.get('title', ''))
                    ))

        except Exception as e:
            print(f"获取直播吧新闻失败: {e}")

        return news_list

    # ==================== 综合聚合 ====================

    def aggregate_all_news(self, team_name: str = None) -> List[NewsItem]:
        """
        聚合所有来源的新闻

        Args:
            team_name: 可选，指定球队

        Returns:
            去重后的新闻列表
        """
        all_news = []

        # 微博
        if team_name:
            all_news.extend(self.get_weibo_team_news(team_name))
        else:
            all_news.extend(self.get_weibo_football_news())

        # Twitter
        all_news.extend(self.get_twitter_football_news())

        # 虎扑
        all_news.extend(self.get_hupu_football_news())

        # 直播吧
        all_news.extend(self.get_zhibo8_news())

        # TheSportsDB（新增）
        all_news.extend(self.get_thesportsdb_news(team_name))

        # ScoreBat（新增）
        all_news.extend(self.get_scorebat_news())

        # 去重（基于标题相似度）
        unique_news = self._deduplicate_news(all_news)

        # 按时间排序
        unique_news.sort(key=lambda x: x.published_at, reverse=True)

        return unique_news

    # ==================== TheSportsDB ====================

    def get_thesportsdb_news(self, team_name: str = None) -> List[NewsItem]:
        """
        从TheSportsDB获取足球新闻/事件

        使用V1 API（免费用户可用）

        Args:
            team_name: 可选，指定球队

        Returns:
            新闻列表
        """
        news_list = []

        try:
            # V1 API基础URL（免费用户）
            base_url = "https://www.thesportsdb.com/api/v1/json/3"

            if team_name:
                # 搜索球队
                search_url = f"{base_url}/searchteams.php"
                params = {'t': team_name}
                response = self.session.get(search_url, params=params, timeout=15)

                if response.status_code == 200 and response.text:
                    data = response.json()
                    teams = data.get('teams', [])
                    if teams:
                        team_id = teams[0].get('idTeam')

                        # 获取球队最近比赛
                        events_url = f"{base_url}/eventslast.php"
                        events_response = self.session.get(events_url, params={'id': team_id}, timeout=15)

                        if events_response.status_code == 200 and events_response.text:
                            events_data = events_response.json()
                            events = events_data.get('results', [])

                            for event in events[:10]:
                                home_score = event.get('intHomeScore', '-')
                                away_score = event.get('intAwayScore', '-')

                                news_list.append(NewsItem(
                                    title=f"{event.get('strEvent', '')}",
                                    content=f"{event.get('strHomeTeam', '')} {home_score} - {away_score} {event.get('strAwayTeam', '')}",
                                    source='thesportsdb',
                                    url=f"https://www.thesportsdb.com/event/{event.get('idEvent')}",
                                    published_at=event.get('dateEvent', ''),
                                    team_mentioned=self._extract_teams(event.get('strEvent', '')),
                                    sentiment='neutral'
                                ))

                        # 获取球队即将开始的比赛
                        next_url = f"{base_url}/eventsnext.php"
                        next_response = self.session.get(next_url, params={'id': team_id}, timeout=15)

                        if next_response.status_code == 200 and next_response.text:
                            next_data = next_response.json()
                            events = next_data.get('events', [])

                            for event in events[:5]:
                                news_list.append(NewsItem(
                                    title=f"[即将开始] {event.get('strEvent', '')}",
                                    content=f"{event.get('strHomeTeam', '')} vs {event.get('strAwayTeam', '')} - {event.get('strLeague', '')}",
                                    source='thesportsdb',
                                    url=f"https://www.thesportsdb.com/event/{event.get('idEvent')}",
                                    published_at=event.get('dateEvent', ''),
                                    team_mentioned=self._extract_teams(event.get('strEvent', '')),
                                    sentiment='neutral'
                                ))
            else:
                # 获取热门联赛的最近比赛
                # 英超 (idLeague: 4328)
                leagues = [
                    ('4328', '英超'),
                    ('4331', '德甲'),
                    ('4332', '意甲'),
                    ('4334', '法甲'),
                    ('4335', '西甲'),
                ]

                for league_id, league_name in leagues[:3]:
                    try:
                        url = f"{base_url}/eventspastleague.php"
                        response = self.session.get(url, params={'id': league_id}, timeout=15)

                        if response.status_code == 200 and response.text:
                            data = response.json()
                            events = data.get('events', [])

                            for event in events[:5]:
                                news_list.append(NewsItem(
                                    title=f"[{league_name}] {event.get('strEvent', '')}",
                                    content=f"{event.get('strHomeTeam', '')} {event.get('intHomeScore', '-')} - {event.get('intAwayScore', '-')} {event.get('strAwayTeam', '')}",
                                    source='thesportsdb',
                                    url=f"https://www.thesportsdb.com/event/{event.get('idEvent')}",
                                    published_at=event.get('dateEvent', ''),
                                    team_mentioned=self._extract_teams(event.get('strEvent', '')),
                                    sentiment='neutral'
                                ))
                    except Exception as e:
                        continue

        except Exception as e:
            print(f"获取TheSportsDB新闻失败: {e}")

        return news_list

    # ==================== ScoreBat ====================

    def get_scorebat_news(self) -> List[NewsItem]:
        """
        从ScoreBat获取比赛视频/集锦

        Returns:
            新闻列表
        """
        news_list = []

        try:
            url = "https://www.scorebat.com/video-api/v3/"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()
                videos = data.get('response', [])

                for video in videos[:20]:
                    try:
                        # 从标题解析比分（格式: "Team1 2-1 Team2"）
                        title = video.get('title', '')
                        competition = video.get('competition', '')
                        if isinstance(competition, dict):
                            competition = competition.get('name', '')

                        home_team = video.get('homeTeam', '')
                        away_team = video.get('awayTeam', '')

                        news_list.append(NewsItem(
                            title=f"[{competition}] {title}",
                            content=f"比赛集锦: {home_team} vs {away_team}",
                            source='scorebat',
                            url=video.get('matchviewUrl', ''),
                            published_at=video.get('date', ''),
                            team_mentioned=self._extract_teams(f"{home_team} {away_team}"),
                            sentiment='neutral'
                        ))
                    except Exception as e:
                        continue

        except Exception as e:
            print(f"获取ScoreBat新闻失败: {e}")

        return news_list

    # ==================== 辅助方法 ====================

    def _clean_text(self, text: str) -> str:
        """清理HTML标签"""
        if not text:
            return ''
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除多余空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _parse_weibo_time(self, time_str: str) -> str:
        """解析微博时间格式"""
        if not time_str:
            return ''
        try:
            # 微博时间格式: "Mon Jan 01 00:00:00 +0800 2024"
            dt = datetime.strptime(time_str, '%a %b %d %H:%M:%S %z %Y')
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return time_str

    def _extract_teams(self, text: str) -> List[str]:
        """从文本中提取提到的球队"""
        mentioned = []
        text_lower = text.lower()

        for team, keywords in self.team_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    mentioned.append(team)
                    break

        return mentioned

    def _analyze_sentiment(self, text: str) -> str:
        """简单情感分析"""
        positive_words = ['签约', '加盟', '续约', '夺冠', '胜利', '进球', '出色', '精彩', '恭喜', '欢迎']
        negative_words = ['受伤', '缺席', '输球', '失利', '解约', '下课', '争议', '冲突', '禁赛', '罚款']

        text_lower = text.lower()

        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)

        if pos_count > neg_count:
            return 'positive'
        elif neg_count > pos_count:
            return 'negative'
        else:
            return 'neutral'

    def _parse_rss(self, rss_text: str) -> List[Dict]:
        """解析RSS XML"""
        items = []

        # 简单的RSS解析
        item_pattern = r'<item>(.*?)</item>'
        title_pattern = r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>'
        link_pattern = r'<link>(.*?)</link>'
        desc_pattern = r'<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>'
        date_pattern = r'<pubDate>(.*?)</pubDate>'

        for match in re.finditer(item_pattern, rss_text, re.DOTALL):
            item_text = match.group(1)

            title_match = re.search(title_pattern, item_text)
            link_match = re.search(link_pattern, item_text)
            desc_match = re.search(desc_pattern, item_text)
            date_match = re.search(date_pattern, item_text)

            items.append({
                'title': title_match.group(1) or title_match.group(2) if title_match else '',
                'link': link_match.group(1) if link_match else '',
                'description': desc_match.group(1) or desc_match.group(2) if desc_match else '',
                'pubDate': date_match.group(1) if date_match else ''
            })

        return items

    def _deduplicate_news(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """去重新闻"""
        seen_titles = set()
        unique_news = []

        for news in news_list:
            # 标准化标题用于比较
            normalized_title = news.title.lower()[:50]

            if normalized_title not in seen_titles:
                seen_titles.add(normalized_title)
                unique_news.append(news)

        return unique_news

    def save_news_to_db(self, news_list: List[NewsItem], conn: sqlite3.Connection = None):
        """保存新闻到数据库"""
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        for news in news_list:
            try:
                # 查找team_id
                team_ids = []
                for team_name in news.team_mentioned:
                    cursor.execute("""
                        SELECT team_id FROM teams
                        WHERE name_en LIKE ? OR name_cn LIKE ?
                    """, (f'%{team_name}%', f'%{team_name}%'))
                    result = cursor.fetchone()
                    if result:
                        team_ids.append(result['team_id'])

                # 保存新闻
                for team_id in team_ids:
                    cursor.execute("""
                        INSERT OR IGNORE INTO team_news
                        (team_id, title, content, source, url, impact, published_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        team_id,
                        news.title,
                        news.content,
                        news.source,
                        news.url,
                        news.sentiment,
                        news.published_at
                    ))

            except Exception as e:
                continue

        conn.commit()


def main():
    """测试社交媒体新闻聚合"""
    db_path = r"d:\football_tools\data\football_v2.db"
    aggregator = SocialMediaNewsAggregator(db_path)

    print("社交媒体新闻聚合测试")
    print("=" * 60)

    # 测试各平台
    print("\n[微博足球新闻]")
    weibo_news = aggregator.get_weibo_football_news()
    print(f"获取到 {len(weibo_news)} 条微博新闻")

    print("\n[虎扑足球新闻]")
    hupu_news = aggregator.get_hupu_football_news()
    print(f"获取到 {len(hupu_news)} 条虎扑新闻")

    print("\n[直播吧新闻]")
    zhibo8_news = aggregator.get_zhibo8_news()
    print(f"获取到 {len(zhibo8_news)} 条直播吧新闻")

    # 综合聚合
    print("\n[综合聚合]")
    all_news = aggregator.aggregate_all_news()
    print(f"聚合后共 {len(all_news)} 条新闻（去重后）")

    for news in all_news[:5]:
        print(f"  [{news.source}] {news.title[:50]}...")
        if news.team_mentioned:
            print(f"    提到球队: {', '.join(news.team_mentioned)}")


if __name__ == "__main__":
    main()