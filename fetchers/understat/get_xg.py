"""
Understat xG数据获取

功能:
1. 获取联赛球员xG/xA数据
2. 获取球队xG数据
3. 获取比赛xG数据

数据来源: understat.com (免费, 需解析JS数据)

使用示例:
    from fetchers.understat.get_xg import get_league_players_xg

    # 英超球员xG
    players = get_league_players_xg("EPL", season="2025")
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from fetchers.understat.config import BASE_URL, LEAGUE_CODES, REQUEST_TIMEOUT

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
        logger.error(f"Understat请求失败: {e}")
        print(f"[错误] Understat请求失败: {str(e)[:60]}")
    return None


def _parse_understat_json(html: str, var_name: str) -> Optional[Dict]:
    """解析Understat页面中嵌入的JSON数据

    Understat在页面中用 var xxx = JSON.parse('...') 格式嵌入数据
    """
    pattern = rf"var\s+{var_name}\s*=\s*JSON\.parse\('([^']+)'\)"
    match = re.search(pattern, html)
    if not match:
        return None

    encoded = match.group(1)
    try:
        # Understat使用简单的XOR编码
        # 这里直接尝试解析已解码的JSON
        decoded = encoded.encode('utf-8').decode('unicode_escape')
        return json.loads(decoded)
    except:
        # 如果直接解码失败, 尝试其他方式
        try:
            return json.loads(encoded)
        except:
            logger.error(f"Understat JSON解析失败: {var_name}")
            return None


def _resolve_league(league: str) -> str:
    if league in LEAGUE_CODES:
        return LEAGUE_CODES[league]
    return league


# ==================== 核心接口 ====================

def get_league_players_xg(league: str = "EPL", season: str = None) -> List[Dict]:
    """获取联赛球员xG/xA数据

    Args:
        league: 联赛代码 (如 "EPL", "La_liga")
        season: 赛季起始年 (如 "2025")

    Returns:
        [{"player_id", "player_name", "team", "position", "games",
          "goals", "assists", "xg", "xa", "shots", "key_passes",
          "npg", "npxg", "xg_chain", "xg_buildup", "source"}]
    """
    league_code = _resolve_league(league)
    url = f"{BASE_URL}/league/{league_code}"
    if season:
        url = f"{BASE_URL}/league/{league_code}/{season}"

    html = _fetch(url)
    if not html:
        return []

    data = _parse_understat_json(html, "playersData")
    if not data:
        print(f"[understat] 解析球员数据失败, 可能页面结构变化")
        return []

    players = []
    for pid, p in data.items() if isinstance(data, dict) else enumerate(data):
        if isinstance(p, dict):
            players.append({
                'player_id': p.get("id"),
                'player_name': p.get("player_name", ""),
                'team': p.get("team_title", ""),
                'league': league,
                'season': season,
                'position': p.get("position", ""),
                'games': p.get("games"),
                'goals': p.get("goals"),
                'assists': p.get("assists"),
                'xg': p.get("xG"),
                'xa': p.get("xA"),
                'shots': p.get("shots"),
                'key_passes': p.get("key_passes"),
                'npg': p.get("npg"),          # 非点球进球
                'npxg': p.get("npxG"),        # 非点球xG
                'xg_chain': p.get("xG_chain"),
                'xg_buildup': p.get("xG_buildup"),
                'source': 'understat'
            })

    print(f"[understat] 球员xG {league}: {len(players)}人")
    return players


def get_league_teams_xg(league: str = "EPL", season: str = None) -> List[Dict]:
    """获取联赛球队xG数据

    Returns:
        [{"team_id", "team", "games", "goals", "xg", "xa",
          "xga", "npxg", "npxga", "source"}]
    """
    league_code = _resolve_league(league)
    url = f"{BASE_URL}/league/{league_code}"
    if season:
        url = f"{BASE_URL}/league/{league_code}/{season}"

    html = _fetch(url)
    if not html:
        return []

    data = _parse_understat_json(html, "teamsData")
    if not data:
        return []

    teams = []
    for tid, t in data.items() if isinstance(data, dict) else enumerate(data):
        if isinstance(t, dict):
            history = t.get("history", [])
            # 从history聚合赛季数据
            games = len(history)
            goals = sum(h.get("goals", 0) for h in history if isinstance(h, dict))
            xg = round(sum(float(h.get("xG", 0)) for h in history if isinstance(h, dict)), 2)
            xa = round(sum(float(h.get("xA", 0)) for h in history if isinstance(h, dict)), 2)
            xga = round(sum(float(h.get("xGA", 0)) for h in history if isinstance(h, dict)), 2)
            npg = sum(h.get("npg", 0) for h in history if isinstance(h, dict))
            npxg = round(sum(float(h.get("npxG", 0)) for h in history if isinstance(h, dict)), 2)
            npxga = round(sum(float(h.get("npxGA", 0)) for h in history if isinstance(h, dict)), 2)
            pts = sum(h.get("pts", 0) for h in history if isinstance(h, dict))

            teams.append({
                'team_id': t.get("id"),
                'team': t.get("title", ""),
                'league': league,
                'season': season,
                'games': games,
                'goals': goals,
                'xg': xg,
                'xa': xa,
                'xga': xga,
                'npg': npg,
                'npxg': npxg,
                'npxga': npxga,
                'pts': pts,
                'source': 'understat'
            })

    print(f"[understat] 球队xG {league}: {len(teams)}队")
    return teams


def get_match_xg(match_id: str) -> Dict:
    """获取比赛xG数据

    Returns:
        {"match_id", "home_team", "away_team", "home_goals", "away_goals",
         "home_xg", "away_xg", "shots_home", "shots_away", "source"}
    """
    url = f"{BASE_URL}/match/{match_id}"
    html = _fetch(url)
    if not html:
        return {}

    data = _parse_understat_json(html, "matchData")
    if not data:
        return {}

    result = {'match_id': match_id, 'source': 'understat'}

    if isinstance(data, dict):
        result['home_team'] = data.get('h', {}).get('title', '') if isinstance(data.get('h'), dict) else ''
        result['away_team'] = data.get('a', {}).get('title', '') if isinstance(data.get('a'), dict) else ''
        result['home_goals'] = data.get('h', {}).get('goals', '') if isinstance(data.get('h'), dict) else ''
        result['away_goals'] = data.get('a', {}).get('goals', '') if isinstance(data.get('a'), dict) else ''
        result['home_xg'] = data.get('h', {}).get('xG', '') if isinstance(data.get('h'), dict) else ''
        result['away_xg'] = data.get('a', {}).get('xG', '') if isinstance(data.get('a'), dict) else ''
    else:
        result['data'] = data

    return result


if __name__ == "__main__":
    print("Understat xG数据获取工具")
    print("注意: understat使用JS编码嵌入数据, 解析可能随网站更新而失效")