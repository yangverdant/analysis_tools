"""
FlashScore数据获取

功能:
1. 获取实时比分
2. 获取比赛统计

数据来源: flashscore.com (爬虫, 需绕反爬, 建议使用其他免费源作为主源)

注意: FlashScore有较强的反爬机制, 建议优先使用API-Football或365Scores获取实时数据

使用示例:
    from fetchers.flashscore.get_live import get_livescores
"""

import os
import re
import logging
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from fetchers.flashscore.config import BASE_URL, LEAGUE_IDS, LEAGUE_CN, REQUEST_TIMEOUT

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


def _fetch(url: str) -> Optional[str]:
    session = _get_session()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        logger.error(f"FlashScore请求失败: {e}")
        print(f"[错误] FlashScore请求失败: {str(e)[:60]}")
    return None


# ==================== 核心接口 ====================

def get_livescores(league: str = None) -> List[Dict]:
    """获取实时比分

    注意: FlashScore使用WebSocket推送数据, HTTP爬虫可能获取不到实时数据

    Args:
        league: 联赛名 (可选)

    Returns:
        [{"home_team", "away_team", "home_score", "away_score",
          "status", "minute", "league", "source"}]
    """
    league_key = LEAGUE_CN.get(league, league) if league else None

    if league_key and league_key in LEAGUE_IDS:
        url = f"{BASE_URL}{LEAGUE_IDS[league_key]}"
    else:
        url = f"{BASE_URL}/football/"

    html = _fetch(url)
    if not html:
        print("[flashscore] 无法获取数据 (反爬机制), 建议使用API-Football或365Scores")
        return []

    # FlashScore使用JavaScript渲染, 直接HTTP请求可能无法获取比赛数据
    # 返回空列表, 建议用户使用其他数据源
    print("[flashscore] 数据需JavaScript渲染, 建议使用API-Football/365Scores作为替代")
    return []


def get_match_detail(match_id: str) -> Dict:
    """获取比赛详情 (统计数据)

    注意: FlashScore使用JavaScript渲染, HTTP爬虫可能无法获取

    Returns:
        比赛详情
    """
    url = f"{BASE_URL}/match/{match_id}/"
    html = _fetch(url)
    if not html:
        return {}

    return {
        'match_id': match_id,
        'note': 'FlashScore使用JS渲染, 建议使用API-Football获取比赛详情',
        'source': 'flashscore'
    }


if __name__ == "__main__":
    print("FlashScore数据获取工具")
    print("注意: FlashScore有JS渲染+反爬机制, 建议优先使用API-Football/365Scores")