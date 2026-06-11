"""
Wikipedia数据获取

功能:
1. 搜索足球相关词条
2. 获取词条摘要
3. 获取联赛/球队/球员历史数据

数据来源: Wikipedia MediaWiki API (免费, 无需认证)

使用示例:
    from fetchers.wikipedia.get_data import search, get_summary

    # 搜索
    results = search("2026 FIFA World Cup")

    # 获取摘要
    summary = get_summary("Premier League")
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.wikipedia.config import BASE_URL_ZH, BASE_URL_EN, REQUEST_TIMEOUT

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
            'User-Agent': 'FootballTools/1.0 (data research)',
        })
    return _session


def _request(base_url: str, params: Dict) -> Optional[Dict]:
    session = _get_session()
    try:
        resp = session.get(base_url, params=params, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"Wikipedia请求失败: {e}")
        print(f"[错误] Wikipedia请求失败: {str(e)[:60]}")
    return None


# ==================== 核心接口 ====================

def search(query: str, lang: str = "zh", limit: int = 10) -> List[Dict]:
    """搜索Wikipedia

    Args:
        query: 搜索关键词
        lang: 语言 ("zh" 或 "en")
        limit: 返回数量

    Returns:
        [{"title", "snippet", "page_id", "source"}]
    """
    base_url = BASE_URL_ZH if lang == "zh" else BASE_URL_EN
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }

    data = _request(base_url, params)
    if not data or "query" not in data:
        return []

    results = []
    for item in data["query"].get("search", []):
        results.append({
            'title': item.get("title", ""),
            'snippet': item.get("snippet", ""),
            'page_id': item.get("pageid"),
            'source': f'wikipedia_{lang}'
        })

    print(f"[wikipedia] 搜索 '{query}': {len(results)}条")
    return results


def get_summary(title: str, lang: str = "zh") -> Dict:
    """获取词条摘要

    Args:
        title: 词条标题
        lang: 语言

    Returns:
        {"title", "extract", "page_id", "url", "source"}
    """
    base_url = BASE_URL_ZH if lang == "zh" else BASE_URL_EN
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "exintro": True,
        "explaintext": True,
        "format": "json",
    }

    data = _request(base_url, params)
    if not data or "query" not in data:
        return {}

    pages = data["query"].get("pages", {})
    for page_id, page in pages.items():
        if page_id == "-1":
            continue

        lang_prefix = "zh" if base_url == BASE_URL_ZH else "en"
        return {
            'title': page.get("title", ""),
            'extract': page.get("extract", ""),
            'page_id': page.get("pageid"),
            'url': f"https://{lang_prefix}.wikipedia.org/wiki/{page.get('title', '').replace(' ', '_')}",
            'source': f'wikipedia_{lang}'
        }

    return {}


def get_page_links(title: str, lang: str = "zh") -> List[str]:
    """获取词条的链接列表"""
    base_url = BASE_URL_ZH if lang == "zh" else BASE_URL_EN
    params = {
        "action": "query",
        "titles": title,
        "prop": "links",
        "pllimit": 50,
        "format": "json",
    }

    data = _request(base_url, params)
    if not data or "query" not in data:
        return []

    pages = data["query"].get("pages", {})
    links = []
    for page_id, page in pages.items():
        for link in page.get("links", []):
            links.append(link.get("title", ""))

    return links


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.wikipedia.get_data search '2026世界杯'")
        print("  python -m fetchers.wikipedia.get_data summary '英超'")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else "Premier League"
        for r in search(query):
            print(f"  {r['title']}: {r['snippet'][:60]}")
    elif cmd == "summary":
        title = sys.argv[2] if len(sys.argv) > 2 else "Premier League"
        s = get_summary(title)
        if s:
            print(f"  {s['title']}: {s['extract'][:100]}...")