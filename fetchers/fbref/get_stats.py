"""
FBref数据获取

功能:
1. 获取联赛赛程/积分榜
2. 获取球队统计 (xG/射门/控球等)
3. 获取球员统计 (xG/xAG/渐进数据等)

数据来源: fbref.com (免费爬虫, 无需认证)

使用示例:
    from fetchers.fbref.get_stats import get_standings, get_fixtures

    # 积分榜
    standings = get_standings("premier_league")

    # 赛程
    fixtures = get_fixtures("premier_league")
"""

import os
import re
import time
import logging
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from fetchers.fbref.config import BASE_URL, LEAGUE_URLS, LEAGUE_CN, COMP_IDS, REQUEST_TIMEOUT

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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    return _session


def _fetch(url: str) -> Optional[str]:
    """获取页面HTML"""
    session = _get_session()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        logger.error(f"FBref请求失败: {e}")
        print(f"[错误] FBref请求失败: {str(e)[:60]}")
    return None


def _resolve_league(league: str) -> str:
    """将联赛名(中文或英文)解析为标准key"""
    if league in LEAGUE_URLS:
        return league
    return LEAGUE_CN.get(league, league)


# ==================== 核心接口 ====================

def get_standings(league: str) -> List[Dict]:
    """获取联赛积分榜

    Args:
        league: 联赛名 (中文或英文key)

    Returns:
        [{"position", "team", "played", "won", "drawn", "lost",
          "goals_for", "goals_against", "goal_difference", "points",
          "league", "source"}]
    """
    league_key = _resolve_league(league)
    url = LEAGUE_URLS.get(league_key)
    if not url:
        print(f"[fbref] 未知联赛: {league}")
        return []

    html = _fetch(url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    standings = []

    tables = soup.find_all('table')
    for table in tables:
        if 'stats' in table.get('id', '').lower():
            rows = table.find_all('tr')
            for row in rows[1:]:
                cols = row.find_all(['th', 'td'])
                if len(cols) >= 10:
                    try:
                        pos_text = cols[0].get_text(strip=True)
                        standings.append({
                            'position': int(pos_text) if pos_text.isdigit() else 0,
                            'team': cols[1].get_text(strip=True),
                            'played': int(cols[2].get_text(strip=True)) if cols[2].get_text(strip=True).isdigit() else 0,
                            'won': int(cols[3].get_text(strip=True)) if cols[3].get_text(strip=True).isdigit() else 0,
                            'drawn': int(cols[4].get_text(strip=True)) if cols[4].get_text(strip=True).isdigit() else 0,
                            'lost': int(cols[5].get_text(strip=True)) if cols[5].get_text(strip=True).isdigit() else 0,
                            'goals_for': int(cols[6].get_text(strip=True)) if cols[6].get_text(strip=True).isdigit() else 0,
                            'goals_against': int(cols[7].get_text(strip=True)) if cols[7].get_text(strip=True).isdigit() else 0,
                            'goal_difference': int(cols[8].get_text(strip=True)) if cols[8].get_text(strip=True).lstrip('-').isdigit() else 0,
                            'points': int(cols[9].get_text(strip=True)) if cols[9].get_text(strip=True).isdigit() else 0,
                            'league': league_key,
                            'source': 'fbref'
                        })
                    except Exception:
                        continue

    print(f"[fbref] 积分榜 {league}: {len(standings)}队")
    return standings


def get_fixtures(league: str) -> List[Dict]:
    """获取联赛赛程

    Returns:
        [{"date", "home_team", "away_team", "home_score", "away_score",
          "league", "source"}]
    """
    league_key = _resolve_league(league)
    url = LEAGUE_URLS.get(league_key)
    if not url:
        return []

    html = _fetch(url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    matches = []

    tables = soup.find_all('table')
    for table in tables:
        if 'schedule' in table.get('id', '').lower():
            rows = table.find_all('tr')
            for row in rows[1:]:
                cols = row.find_all('td')
                if len(cols) >= 6:
                    try:
                        date = cols[0].get_text(strip=True)
                        home = cols[2].get_text(strip=True)
                        away = cols[4].get_text(strip=True)
                        score = cols[3].get_text(strip=True)

                        home_score, away_score = None, None
                        if score:
                            parts = score.split('–')
                            if len(parts) == 2:
                                home_score = int(parts[0].strip())
                                away_score = int(parts[1].strip())

                        matches.append({
                            'date': date,
                            'home_team': home,
                            'away_team': away,
                            'home_score': home_score,
                            'away_score': away_score,
                            'league': league_key,
                            'source': 'fbref'
                        })
                    except Exception:
                        continue

    print(f"[fbref] 赛程 {league}: {len(matches)}场")
    return matches


def get_team_stats_url(team_name: str, league: str) -> Optional[str]:
    """获取球队详细统计页URL (需先从积分榜页面找到链接)"""
    league_key = _resolve_league(league)
    url = LEAGUE_URLS.get(league_key)
    if not url:
        return None

    html = _fetch(url)
    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a'):
        if team_name.lower() in a.get_text(strip=True).lower():
            href = a.get('href', '')
            if href and '/squads/' in href:
                return f"{BASE_URL}{href}"
    return None


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.fbref.get_stats standings premier_league")
        print("  python -m fetchers.fbref.get_stats fixtures premier_league")
        print("  python -m fetchers.fbref.get_stats standings 英超")
        sys.exit(0)

    cmd = sys.argv[1]
    league = sys.argv[2] if len(sys.argv) > 2 else "premier_league"

    if cmd == "standings":
        for s in get_standings(league):
            print(f"  {s['position']}. {s['team']} {s['points']}pts")
    elif cmd == "fixtures":
        for m in get_fixtures(league)[:20]:
            print(f"  {m['date']} {m['home_team']} vs {m['away_team']}")