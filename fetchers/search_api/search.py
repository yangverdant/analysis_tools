"""
搜索API数据获取

功能:
1. Tavily搜索 (AI增强搜索)
2. Brave搜索 (隐私搜索)

数据来源: Tavily / Brave Search (需API Key)

使用示例:
    from fetchers.search_api.search import tavily_search, brave_search

    # Tavily搜索
    results = tavily_search("Arsenal injury news today")

    # Brave搜索
    results = brave_search("Premier League standings 2026")
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.search_api.config import (
    TAVILY_API_KEY, TAVILY_URL,
    BRAVE_API_KEY, BRAVE_URL,
    REQUEST_TIMEOUT
)

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
    return _session


# ==================== 核心接口 ====================

def tavily_search(query: str, max_results: int = 5, search_depth: str = "basic") -> List[Dict]:
    """Tavily搜索 (AI增强搜索)

    Args:
        query: 搜索关键词
        max_results: 最大结果数
        search_depth: "basic" 或 "advanced"

    Returns:
        [{"title", "url", "content", "score", "source"}]
    """
    if not TAVILY_API_KEY:
        print("[错误] Tavily API Key未配置, 请在config.py中设置")
        return []

    session = _get_session()
    try:
        resp = session.post(TAVILY_URL, json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
        }, timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})

        if resp.status_code == 200:
            data = resp.json()
            results = []
            for item in data.get("results", []):
                results.append({
                    'title': item.get("title", ""),
                    'url': item.get("url", ""),
                    'content': item.get("content", ""),
                    'score': item.get("score"),
                    'source': 'tavily'
                })
            print(f"[tavily] 搜索 '{query}': {len(results)}条")
            return results
    except Exception as e:
        logger.error(f"Tavily搜索失败: {e}")
        print(f"[错误] Tavily搜索失败: {str(e)[:60]}")

    return []


def brave_search(query: str, count: int = 5) -> List[Dict]:
    """Brave搜索

    Args:
        query: 搜索关键词
        count: 结果数量

    Returns:
        [{"title", "url", "description", "source"}]
    """
    if not BRAVE_API_KEY:
        print("[错误] Brave Search API Key未配置, 请在config.py中设置")
        return []

    session = _get_session()
    try:
        resp = session.get(BRAVE_URL, params={
            "q": query,
            "count": count,
        }, headers={
            "X-Subscription-Token": BRAVE_API_KEY,
        }, timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})

        if resp.status_code == 200:
            data = resp.json()
            results = []
            for item in data.get("web", {}).get("results", []):
                results.append({
                    'title': item.get("title", ""),
                    'url': item.get("url", ""),
                    'description': item.get("description", ""),
                    'source': 'brave_search'
                })
            print(f"[brave] 搜索 '{query}': {len(results)}条")
            return results
    except Exception as e:
        logger.error(f"Brave搜索失败: {e}")
        print(f"[错误] Brave搜索失败: {str(e)[:60]}")

    return []


if __name__ == "__main__":
    print("搜索API数据获取工具")
    print("数据源: Tavily / Brave Search (需API Key)")