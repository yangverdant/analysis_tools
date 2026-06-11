"""
懂球帝数据获取

功能:
1. 获取足球新闻
2. 获取比赛数据

数据来源: dongqiudi.com (爬虫, 无公开API)

注意: 懂球帝无公开API, 本模块提供基础爬虫框架
建议优先使用 fetchers.news (直播吧) 获取中文足球新闻

使用示例:
    from fetchers.dongqiudi.get_news import get_news
"""

import os
import logging
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from fetchers.dongqiudi.config import BASE_URL, REQUEST_TIMEOUT
from datetime import date as _date

os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'

logger = logging.getLogger(__name__)

_session = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.trust_env = False
        _session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
    return _session


# ==================== 核心接口 ====================

def get_news(limit: int = 20) -> List[Dict]:
    """获取懂球帝足球新闻

    Returns:
        [{"title", "url", "summary", "source"}]
    """
    fetch_date = str(_date.today())

    session = _get_session()
    try:
        resp = session.get(f"{BASE_URL}/news", timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        news = []

        articles = soup.find_all('a', class_='news-item')
        for article in articles[:limit]:
            title = article.get_text(strip=True)
            url = article.get('href', '')
            if url and not url.startswith('http'):
                url = f"{BASE_URL}{url}"

            news.append({
                'title': title,
                'url': url,
                'date': fetch_date,
                'source': 'dongqiudi'
            })

        print(f"[dongqiudi] 新闻: {len(news)}条")
        return news

    except Exception as e:
        logger.error(f"懂球帝请求失败: {e}")
        print(f"[错误] 懂球帝请求失败: {str(e)[:60]}")
        return []


if __name__ == "__main__":
    for n in get_news():
        print(f"  {n['title'][:50]}")