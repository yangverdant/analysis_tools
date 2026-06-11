"""
虎扑足球数据获取

功能:
1. 获取足球新闻

数据来源: soccer.hupu.com (爬虫)

使用示例:
    from fetchers.hupu.get_news import get_news
"""

import os
import logging
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from fetchers.hupu.config import BASE_URL, REQUEST_TIMEOUT
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
    """获取虎扑足球新闻

    Returns:
        [{"title", "url", "source"}]
    """
    fetch_date = str(_date.today())

    session = _get_session()
    try:
        resp = session.get(BASE_URL, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        news = []

        for a in soup.find_all('a', href=True):
            href = a['href']
            title = a.get_text(strip=True)
            if title and len(title) > 10 and '/news/' in href:
                url = href if href.startswith('http') else f"https:{href}"
                news.append({
                    'title': title,
                    'url': url,
                    'date': fetch_date,
                    'source': 'hupu'
                })
                if len(news) >= limit:
                    break

        print(f"[hupu] 新闻: {len(news)}条")
        return news

    except Exception as e:
        logger.error(f"虎扑请求失败: {e}")
        print(f"[错误] 虎扑请求失败: {str(e)[:60]}")
        return []


if __name__ == "__main__":
    for n in get_news():
        print(f"  {n['title'][:50]}")