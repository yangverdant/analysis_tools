"""
api-sports.io数据获取

功能:
1. 通过RapidAPI代理访问api-football数据
2. 获取赔率/赛程/积分榜/阵容/转会/伤病

数据来源: api-sports.io / RapidAPI (需Key)

注意: 与fetchers.apifootball同源, 本模块提供RapidAPI接入方式

使用示例:
    from fetchers.api_sports.get_data import get_fixtures, get_odds

    # 通过RapidAPI获取赛程
    fixtures = get_fixtures(league=39, season=2025)
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.api_sports.config import RAPIDAPI_KEY, RAPIDAPI_URL, RAPIDAPI_HOST, REQUEST_TIMEOUT

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


def _request(endpoint: str, params: Dict = None) -> Optional[Dict]:
    """通过RapidAPI发送请求"""
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }

    session = _get_session()
    try:
        resp = session.get(f"{RAPIDAPI_URL}/{endpoint}", headers=headers,
                           params=params, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("errors"):
                logger.error(f"API错误: {data['errors']}")
            return data
    except Exception as e:
        logger.error(f"api-sports请求失败: {e}")
        print(f"[错误] api-sports请求失败: {str(e)[:60]}")
    return None


# ==================== 核心接口 ====================

def get_fixtures(league: int = None, season: int = None, date: str = None,
                 team: int = None, fixture_id: int = None) -> List[Dict]:
    """获取赛程 (RapidAPI)

    Args:
        league: 联赛ID (如 39=英超)
        season: 赛季年份
        date: 日期 (YYYY-MM-DD)
        team: 球队ID
        fixture_id: 比赛ID

    Returns:
        比赛列表
    """
    params = {}
    if league:
        params["league"] = league
    if season:
        params["season"] = season
    if date:
        params["date"] = date
    if team:
        params["team"] = team
    if fixture_id:
        params["id"] = fixture_id

    data = _request("fixtures", params)
    if not data:
        return []

    result = []
    for item in data.get("response", []):
        fixture = item.get("fixture", {})
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        score = item.get("score", {})

        result.append({
            'fixture_id': fixture.get("id"),
            'date': fixture.get("date", "")[:10],
            'time': fixture.get("date", "")[11:16] if fixture.get("date") else None,
            'status': fixture.get("status", {}).get("short", ""),
            'home_team': teams.get("home", {}).get("name", ""),
            'home_team_id': teams.get("home", {}).get("id"),
            'away_team': teams.get("away", {}).get("name", ""),
            'away_team_id': teams.get("away", {}).get("id"),
            'home_goals': goals.get("home"),
            'away_goals': goals.get("away"),
            'ht_home': score.get("halftime", {}).get("home"),
            'ht_away': score.get("halftime", {}).get("away"),
            'league': item.get("league", {}).get("name", ""),
            'league_id': item.get("league", {}).get("id"),
            'round': item.get("league", {}).get("round", ""),
            'source': 'api-sports'
        })

    print(f"[api-sports] 赛程: {len(result)}场")
    return result


def get_odds(fixture: int = None, league: int = None, season: int = None) -> List[Dict]:
    """获取赔率 (RapidAPI)

    Returns:
        赔率列表
    """
    params = {}
    if fixture:
        params["fixture"] = fixture
    if league:
        params["league"] = league
    if season:
        params["season"] = season

    data = _request("odds", params)
    if not data:
        return []

    result = []
    for item in data.get("response", []):
        result.append({
            'fixture_id': item.get("fixture", {}).get("id"),
            'bookmaker': item.get("bookmaker", {}).get("name", ""),
            'bookmaker_id': item.get("bookmaker", {}).get("id"),
            'bets': item.get("bets", []),
            'source': 'api-sports'
        })

    print(f"[api-sports] 赔率: {len(result)}条")
    return result


def get_injuries(league: int = None, season: int = None, team: int = None) -> List[Dict]:
    """获取伤病数据 (RapidAPI)

    Returns:
        伤病列表
    """
    params = {}
    if league:
        params["league"] = league
    if season:
        params["season"] = season
    if team:
        params["team"] = team

    data = _request("injuries", params)
    if not data:
        return []

    result = []
    for item in data.get("response", []):
        result.append({
            'player': item.get("player", {}).get("name", ""),
            'player_id': item.get("player", {}).get("id"),
            'team': item.get("team", {}).get("name", ""),
            'team_id': item.get("team", {}).get("id"),
            'reason': item.get("player", {}).get("reason", ""),
            'type': item.get("player", {}).get("type", ""),
            'source': 'api-sports'
        })

    print(f"[api-sports] 伤病: {len(result)}条")
    return result


if __name__ == "__main__":
    print("api-sports.io数据获取工具 (RapidAPI)")
    print("与fetchers.apifootball同源, 提供RapidAPI接入方式")