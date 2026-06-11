"""
Soccerway数据获取

功能:
1. 获取联赛比赛数据
2. 获取积分榜

数据来源: int.soccerway.com (免费爬虫, 需绕反爬)

使用示例:
    from fetchers.soccerway.get_matches import get_matches

    matches = get_matches("premier_league")
"""

import os
import re
import logging
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from fetchers.soccerway.config import BASE_URL, LEAGUE_URLS, LEAGUE_CN, REQUEST_TIMEOUT
from fetchers.common.league_names import normalize_league_name

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
        logger.error(f"Soccerway请求失败: {e}")
        print(f"[错误] Soccerway请求失败: {str(e)[:60]}")
    return None


def _resolve_league(league: str) -> str:
    if league in LEAGUE_URLS:
        return league
    return LEAGUE_CN.get(league, league)


# ==================== 核心接口 ====================

def get_matches(league: str) -> List[Dict]:
    """获取联赛比赛数据

    Returns:
        [{"home_team", "away_team", "home_score", "away_score",
          "league", "source"}]
    """
    league_key = _resolve_league(league)
    url = LEAGUE_URLS.get(league_key)
    if not url:
        print(f"[soccerway] 未知联赛: {league}")
        return []

    html = _fetch(url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    matches = []

    rows = soup.find_all('tr', class_='match')
    for row in rows:
        try:
            teams = row.find_all('td', class_='team')
            score_td = row.find('td', class_='score')

            if len(teams) >= 2 and score_td:
                home = teams[0].get_text(strip=True)
                away = teams[1].get_text(strip=True)
                score_text = score_td.get_text(strip=True)

                scores = re.findall(r'(\d+)\s*-\s*(\d+)', score_text)
                if scores:
                    matches.append({
                        'home_team': home,
                        'away_team': away,
                        'home_score': int(scores[0][0]),
                        'away_score': int(scores[0][1]),
                        'league': league_key,
                        'league_standard': normalize_league_name(league_key),
                        'source': 'soccerway'
                    })
        except Exception:
            continue

    print(f"[soccerway] {league}: {len(matches)}场")
    return matches


if __name__ == "__main__":
    import sys
    league = sys.argv[1] if len(sys.argv) > 1 else "premier_league"
    for m in get_matches(league):
        print(f"  {m['home_team']} {m['home_score']}-{m['away_score']} {m['away_team']}")