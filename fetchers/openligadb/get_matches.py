"""
OpenLigaDB数据获取

功能:
1. 获取联赛当前轮次比赛
2. 获取特定轮次比赛
3. 获取比赛详情

数据来源: api.openligadb.de (免费, 无需认证)

使用示例:
    from fetchers.openligadb.get_matches import get_current_matches

    # 当前轮次比赛
    matches = get_current_matches("bundesliga")
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.openligadb.config import BASE_URL, REQUEST_TIMEOUT, LEAGUE_CODES

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


def _request(endpoint: str) -> Optional[List]:
    url = f"{BASE_URL}/{endpoint}"
    session = _get_session()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"OpenLigaDB请求失败: {e}")
        print(f"[错误] OpenLigaDB请求失败: {str(e)[:60]}")
    return None


def _resolve_code(league: str) -> str:
    if league in LEAGUE_CODES:
        return LEAGUE_CODES[league]
    return league


# ==================== 核心接口 ====================

def get_current_matches(league: str = "bundesliga") -> List[Dict]:
    """获取联赛当前轮次比赛

    Args:
        league: 联赛名 (如 "bundesliga" 或 "bl1")

    Returns:
        [{"match_id", "home_team", "away_team", "home_score", "away_score",
          "date", "time", "is_finished", "matchday", "source"}]
    """
    code = _resolve_code(league)
    data = _request(f"getmatchdata/{code}")
    if not data or not isinstance(data, list):
        return []

    matches = []
    for item in data:
        results = item.get("matchResults", [])
        ft_score = results[-1] if results else {}

        matches.append({
            'match_id': str(item.get("matchID", "")),
            'home_team': item.get("team1", {}).get("teamName", ""),
            'home_team_id': item.get("team1", {}).get("teamId"),
            'away_team': item.get("team2", {}).get("teamName", ""),
            'away_team_id': item.get("team2", {}).get("teamId"),
            'home_score': ft_score.get("pointsTeam1"),
            'away_score': ft_score.get("pointsTeam2"),
            'date': item.get("matchDateTime", "")[:10],
            'time': item.get("matchDateTime", "")[11:16] if item.get("matchDateTime") else None,
            'is_finished': item.get("matchIsFinished", False),
            'matchday': item.get("group", {}).get("groupName", ""),
            'league': code,
            'source': 'openligadb'
        })

    print(f"[openligadb] {league} 当前轮次: {len(matches)}场")
    return matches


def get_matchday_matches(league: str, season: str = None, matchday: int = None) -> List[Dict]:
    """获取特定轮次比赛

    Args:
        league: 联赛名或代码
        season: 赛季 (如 "2026", 默认当前赛季)
        matchday: 轮次号

    Returns:
        同 get_current_matches 格式
    """
    code = _resolve_code(league)
    if season and matchday:
        endpoint = f"getmatchdata/{code}/{season}/{matchday}"
    elif matchday:
        endpoint = f"getmatchdata/{code}/{matchday}"
    else:
        endpoint = f"getmatchdata/{code}"

    data = _request(endpoint)
    if not data or not isinstance(data, list):
        return []

    matches = []
    for item in data:
        results = item.get("matchResults", [])
        ft_score = results[-1] if results else {}

        matches.append({
            'match_id': str(item.get("matchID", "")),
            'home_team': item.get("team1", {}).get("teamName", ""),
            'away_team': item.get("team2", {}).get("teamName", ""),
            'home_score': ft_score.get("pointsTeam1"),
            'away_score': ft_score.get("pointsTeam2"),
            'date': item.get("matchDateTime", "")[:10],
            'time': item.get("matchDateTime", "")[11:16] if item.get("matchDateTime") else None,
            'is_finished': item.get("matchIsFinished", False),
            'league': code,
            'source': 'openligadb'
        })

    print(f"[openligadb] {league} 赛程: {len(matches)}场")
    return matches


def get_match_detail(match_id: str) -> Dict:
    """获取比赛详情

    Returns:
        {"match_id", "home_team", "away_team", "date", "goals", "results", "source"}
    """
    data = _request(f"getmatchdata/{match_id}")
    if not data or not isinstance(data, list) or len(data) == 0:
        return {}

    item = data[0]
    return {
        'match_id': str(item.get("matchID", "")),
        'home_team': item.get("team1", {}).get("teamName", ""),
        'away_team': item.get("team2", {}).get("teamName", ""),
        'date': item.get("matchDateTime", ""),
        'is_finished': item.get("matchIsFinished", False),
        'results': item.get("matchResults", []),
        'goals': item.get("goals", []),
        'source': 'openligadb'
    }


def get_available_matchdays(league: str, season: str = None) -> List[Dict]:
    """获取可用轮次列表"""
    code = _resolve_code(league)
    if season:
        endpoint = f"getavailablegroups/{code}/{season}"
    else:
        endpoint = f"getavailablegroups/{code}"

    data = _request(endpoint)
    return data if isinstance(data, list) else []


if __name__ == "__main__":
    import sys

    league = sys.argv[1] if len(sys.argv) > 1 else "bundesliga"
    for m in get_current_matches(league):
        score = f"{m['home_score']}-{m['away_score']}" if m['home_score'] else "vs"
        fin = "完" if m['is_finished'] else "未"
        print(f"  {m['home_team']} {score} {m['away_team']} [{fin}]")