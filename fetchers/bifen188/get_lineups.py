"""
188比分数据获取

功能:
1. 获取比赛阵容预测/首发阵容

数据来源: bifen188.com (爬虫)

使用示例:
    from fetchers.bifen188.get_lineups import get_predicted_lineups
"""

import os
import logging
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from fetchers.bifen188.config import BASE_URL, REQUEST_TIMEOUT

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

def get_predicted_lineups(match_url: str = None) -> Dict:
    """获取比赛阵容预测

    Args:
        match_url: 比赛页面URL (可选)

    Returns:
        {"home_team", "away_team", "home_lineup", "away_lineup", "source"}
    """
    session = _get_session()

    if match_url:
        url = match_url
    else:
        url = BASE_URL

    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, 'html.parser')

        # 查找阵容预测区域
        result = {
            'match_url': match_url,
            'home_lineup': [],
            'away_lineup': [],
            'source': 'bifen188'
        }

        # 阵容通常在特定class的div中
        lineup_divs = soup.find_all('div', class_='lineup')
        for i, div in enumerate(lineup_divs):
            players = [p.get_text(strip=True) for p in div.find_all('span', class_='player')]
            if i == 0:
                result['home_lineup'] = players
            elif i == 1:
                result['away_lineup'] = players

        return result

    except Exception as e:
        logger.error(f"188比分请求失败: {e}")
        print(f"[错误] 188比分请求失败: {str(e)[:60]}")
        return {}


if __name__ == "__main__":
    print("188比分阵容预测工具")
    print("用法: 需提供比赛页面URL")