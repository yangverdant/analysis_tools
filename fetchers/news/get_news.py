"""
足球新闻获取

功能:
1. 从直播吧获取足球新闻
2. 自动分类 (伤病/转会/停赛/复出/教练)
3. 自动影响评估 (利好/利空/中性)

使用示例:
    from fetchers.news.get_news import get_zhibo8_news

    news = get_zhibo8_news(limit=20)
    for n in news:
        print(f"  [{n['category']}] {n['title']}")
"""

import re
import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from fetchers.news.config import Zhibo8_DOMAINS, REQUEST_TIMEOUT

os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'

logger = logging.getLogger(__name__)

# 新闻类型映射
NEWS_TYPE_MAP = {
    'injury':     ['伤', '受伤', '伤病', '伤缺', '伤停', '伤退'],
    'suspension': ['停赛', '红牌', '累计黄牌', '禁赛'],
    'transfer':   ['转会', '签约', '加盟', '租借', '买断', '出售'],
    'return':     ['复出', '回归', '伤愈', '恢复'],
    'coach':      ['主帅', '教练', '下课', '解雇', '辞职', '续约'],
    'form':       ['连胜', '连败', '不败', '状态'],
}

# 影响等级
IMPACT_KEYWORDS = {
    'high':   ['核心', '主力', '队长', '头号', '当家'],
    'medium': ['重要', '关键', '首发'],
    'low':    ['替补', '边缘', '小将'],
}


def _create_session() -> requests.Session:
    """创建HTTP会话"""
    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    })
    return session


def classify_news_type(title: str) -> str:
    """自动分类新闻类型"""
    for ntype, keywords in NEWS_TYPE_MAP.items():
        if any(kw in title for kw in keywords):
            return ntype
    return 'other'


def classify_impact(title: str) -> str:
    """评估新闻影响等级"""
    for level, keywords in IMPACT_KEYWORDS.items():
        if any(kw in title for kw in keywords):
            return level
    return 'low'


def classify_sentiment(title: str) -> str:
    """评估新闻倾向 (利好/利空/中性)"""
    positive = ['复出', '回归', '续约', '连胜', '签约', '加盟', '不败']
    negative = ['伤', '停赛', '下课', '解雇', '连败', '红牌', '禁赛']
    if any(kw in title for kw in positive):
        return 'positive'
    if any(kw in title for kw in negative):
        return 'negative'
    return 'neutral'


# ==================== 核心接口 ====================

def get_zhibo8_news(limit: int = 50) -> List[Dict]:
    """从直播吧获取足球新闻

    Args:
        limit: 最大新闻数量

    Returns:
        [{
            "title": "...",
            "url": "...",
            "date": "2025-05-25",
            "news_type": "injury",
            "impact_level": "high",
            "sentiment": "negative",
            "source": "zhibo8"
        }, ...]
    """
    session = _create_session()
    news_list = []

    try:
        resp = session.get(
            "https://news.zhibo8.com/zuqiu/more.htm",
            timeout=REQUEST_TIMEOUT,
            proxies={'http': None, 'https': None}
        )
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')

        data_list = soup.select_one('.dataList')
        if not data_list:
            print("[news] 直播吧: 无数据")
            return []

        items = data_list.select('li')[:limit]

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
                date_match = re.search(r'(\d{1,2})-(\d{1,2})', news_time)
                if date_match:
                    month, day = int(date_match.group(1)), int(date_match.group(2))
                    news_date = f"{datetime.now().year}-{month:02d}-{day:02d}"

            news_list.append({
                'title': title,
                'url': href if href.startswith('http') else f"https://news.zhibo8.com{href}",
                'date': news_date,
                'news_type': classify_news_type(title),
                'impact_level': classify_impact(title),
                'sentiment': classify_sentiment(title),
                'source': 'zhibo8'
            })

    except Exception as e:
        logger.error(f"直播吧爬取失败: {e}")
        print(f"[错误] 直播吧: {str(e)[:60]}")
        return []

    print(f"[news] 直播吧: {len(news_list)} 条新闻")
    return news_list


def get_zhibo8_today_matches() -> List[Dict]:
    """获取直播吧今日比赛列表 (zhibo8.cc域名)

    Returns:
        [{"match_id", "home_team", "away_team", "time", "league", "url", "source"}]
    """
    session = _create_session()
    matches = []

    for domain in Zhibo8_DOMAINS:
        try:
            resp = session.get(
                f"{domain}/zuqiu/",
                timeout=REQUEST_TIMEOUT,
                proxies={'http': None, 'https': None}
            )
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                title = link.get('title', '') or link.get_text(strip=True)

                id_match = re.search(r'/match/(\d+)', href)
                if not id_match or not title or len(title) < 5:
                    continue

                vs_match = re.search(r'(.+?)\s*(?:vs|VS|对阵|迎战)\s*(.+)', title)
                if vs_match:
                    full_url = href if href.startswith('http') else f"{domain}{href}"
                    matches.append({
                        'match_id': id_match.group(1),
                        'home_team': vs_match.group(1).strip(),
                        'away_team': vs_match.group(2).strip(),
                        'time': '',
                        'league': '',
                        'url': full_url,
                        'source': 'zhibo8'
                    })

            if matches:
                break

        except Exception:
            continue

    print(f"[news] 直播吧今日比赛: {len(matches)}场")
    return matches


def get_zhibo8_match_preview(match_id: str) -> Dict:
    """获取直播吧比赛前瞻 (zhibo8.cc域名)

    Args:
        match_id: 比赛ID

    Returns:
        {"match_id", "home_injuries", "away_injuries", "home_lineup", "away_lineup",
         "analysis", "source"}
    """
    session = _create_session()
    preview = {
        'match_id': match_id,
        'home_injuries': [],
        'away_injuries': [],
        'home_lineup': [],
        'away_lineup': [],
        'analysis': '',
        'source': 'zhibo8'
    }

    for domain in Zhibo8_DOMAINS:
        try:
            url = f"{domain}/match/{match_id}.htm"
            resp = session.get(url, timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            injury_section = soup.select_one('.injury-list, .伤病名单')
            if injury_section:
                for item in injury_section.select('li'):
                    player_name = item.select_one('.player-name')
                    injury_type = item.select_one('.injury-type')
                    if player_name:
                        preview['home_injuries'].append({
                            'player': player_name.get_text(strip=True),
                            'type': injury_type.get_text(strip=True) if injury_type else ''
                        })

            lineup_section = soup.select_one('.lineup-prediction, .阵容预测')
            if lineup_section:
                for side, cls in [('home', '.home-lineup'), ('away', '.away-lineup')]:
                    lineup_el = lineup_section.select_one(cls)
                    if lineup_el:
                        for p in lineup_el.select('.player'):
                            preview[f'{side}_lineup'].append(p.get_text(strip=True))

            analysis_section = soup.select_one('.match-analysis, .比赛分析')
            if analysis_section:
                preview['analysis'] = analysis_section.get_text(strip=True)

            break

        except Exception:
            continue

    return preview


def filter_by_type(news_list: List[Dict], news_type: str) -> List[Dict]:
    """按类型过滤新闻

    Args:
        news_type: "injury", "transfer", "coach", "suspension", "return"

    Returns:
        过滤后的新闻列表
    """
    return [n for n in news_list if n['news_type'] == news_type]


def filter_by_team(news_list: List[Dict], team_names: List[str]) -> List[Dict]:
    """按球队名过滤新闻

    Args:
        team_names: 球队名列表 (中文或英文)

    Returns:
        匹配的新闻列表
    """
    result = []
    for news in news_list:
        for name in team_names:
            if name in news['title']:
                result.append(news)
                break
    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.news.get_news zhibo8")
        print("  python -m fetchers.news.get_news zhibo8 injury")
        print("  python -m fetchers.news.get_news zhibo8 阿森纳")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "zhibo8":
        news = get_zhibo8_news(50)
        filter_type = sys.argv[2] if len(sys.argv) > 2 else None

        if filter_type and filter_type in NEWS_TYPE_MAP:
            news = filter_by_type(news, filter_type)
        elif filter_type:
            news = filter_by_team(news, [filter_type])

        for n in news[:20]:
            print(f"  [{n['sentiment']:3s}/{n['news_type']:8s}] {n['title'][:60]}")