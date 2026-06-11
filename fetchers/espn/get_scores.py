"""
ESPN Soccer数据获取

功能:
1. 获取实时比分

数据来源: espn.com/soccer (免费爬虫, JS渲染可能受限)

使用示例:
    from fetchers.espn.get_scores import get_livescores
"""

import os
import logging
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from fetchers.espn.config import BASE_URL, REQUEST_TIMEOUT
from fetchers.common.date_utils import normalize_date

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

def get_livescores() -> List[Dict]:
    """获取ESPN实时比分

    注意: ESPN页面可能需要JS渲染, HTTP爬虫可能获取不到比赛数据

    Returns:
        [{"home_team", "away_team", "home_score", "away_score",
          "status", "source"}]
    """
    from datetime import date as today_date
    fetch_date = str(today_date.today())

    session = _get_session()
    try:
        resp = session.get(BASE_URL, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        matches = []

        containers = soup.find_all('div', class_='game-score-container')
        for container in containers:
            try:
                teams = container.find_all('span', class_='team-name')
                scores = container.find_all('span', class_='score')

                if len(teams) >= 2 and len(scores) >= 2:
                    hs = scores[0].get_text(strip=True)
                    as_ = scores[1].get_text(strip=True)
                    matches.append({
                        'home_team': teams[0].get_text(strip=True),
                        'away_team': teams[1].get_text(strip=True),
                        'home_score': int(hs) if hs.isdigit() else None,
                        'away_score': int(as_) if as_.isdigit() else None,
                        'date': fetch_date,
                        'source': 'espn'
                    })
            except Exception:
                continue

        print(f"[espn] 实时比分: {len(matches)}场")
        return matches

    except Exception as e:
        logger.error(f"ESPN请求失败: {e}")
        print(f"[错误] ESPN请求失败: {str(e)[:60]}")
        return []


if __name__ == "__main__":
    for m in get_livescores():
        score = f"{m['home_score']}-{m['away_score']}" if m['home_score'] else "vs"
        print(f"  {m['home_team']} {score} {m['away_team']}")