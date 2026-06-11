"""
英超官方数据获取

功能:
1. 获取英超伤病名单
2. 获取英超赛程/赛果

数据来源: premierleague.com (免费爬虫)

使用示例:
    from fetchers.premierleague.get_data import get_injuries, get_fixtures
"""

import os
import re
import logging
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from fetchers.premierleague.config import BASE_URL, PLAYER_STATUS_MAP, REQUEST_TIMEOUT
from fetchers.common.team_names import normalize_team_name

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
        logger.error(f"英超官网请求失败: {e}")
        print(f"[错误] 英超官网请求失败: {str(e)[:60]}")
    return None


# ==================== 核心接口 ====================

def get_injuries() -> List[Dict]:
    """获取英超伤病名单

    Returns:
        [{"player", "team", "status", "reason", "league", "source"}]
    """
    html = _fetch(f"{BASE_URL}/players")
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    injuries = []

    # 伤病列表通常在特定表格中
    rows = soup.find_all('tr', {'class': 'player'})
    for row in rows:
        try:
            name = row.find('td', class_='name')
            team = row.find('td', class_='team')
            status = row.find('td', class_='status')

            if name:
                status_text = status.get_text(strip=True) if status else ""
                injuries.append({
                    'player': name.get_text(strip=True),
                    'team': team.get_text(strip=True) if team else "",
                    'status': PLAYER_STATUS_MAP.get(status_text.lower()[0] if status_text else "", status_text),
                    'reason': status_text,
                    'league': 'Premier League',
                    'source': 'premierleague.com'
                })
        except Exception:
            continue

    print(f"[premierleague] 伤病名单: {len(injuries)}人")
    return injuries


def get_fixtures(season: str = None) -> List[Dict]:
    """获取英超赛程

    Args:
        season: 赛季 (如 "2025-26")

    Returns:
        [{"home_team", "away_team", "date", "time", "venue", "matchday", "source"}]
    """
    url = f"{BASE_URL}/fixtures"
    if season:
        url = f"{BASE_URL}/fixtures?season={season}"

    html = _fetch(url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    fixtures = []

    for match in soup.find_all('div', class_='fixture'):
        try:
            teams = match.find_all('span', class_='team-name')
            if len(teams) >= 2:
                fixtures.append({
                    'home_team': teams[0].get_text(strip=True),
                    'away_team': teams[1].get_text(strip=True),
                    'date': match.get('data-date', ''),
                    'league': 'Premier League',
                    'season': season,
                    'source': 'premierleague.com'
                })
        except Exception:
            continue

    print(f"[premierleague] 赛程: {len(fixtures)}场")
    return fixtures


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "injuries"

    if cmd == "injuries":
        for i in get_injuries()[:20]:
            print(f"  {i['player']} ({i['team']}) - {i['status']}")
    elif cmd == "fixtures":
        for f in get_fixtures()[:20]:
            print(f"  {f['home_team']} vs {f['away_team']}")