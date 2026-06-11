"""
Sportmonks数据获取

功能:
1. 获取赛程/实时比分
2. 获取积分榜
3. 获取阵容
4. 获取xG数据 (特色)
5. 获取预测

数据来源: api.sportmonks.com/v3 (需API Key)

使用示例:
    from fetchers.sportmonks.get_data import get_fixtures, get_standings

    # 某日赛程
    fixtures = get_fixtures(date="2026-01-15")

    # 积分榜
    standings = get_standings("premier_league")
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.sportmonks.config import (
    API_KEY, BASE_URL, REQUEST_TIMEOUT,
    LEAGUE_IDS, INCLUDES
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


def _request(endpoint: str, params: Dict = None) -> Optional[Dict]:
    """发送API请求"""
    if not API_KEY:
        print("[错误] Sportmonks API Key未配置, 请在config.py中设置")
        return None

    url = f"{BASE_URL}/{endpoint}"
    query = {"api_token": API_KEY}
    if params:
        query.update(params)

    session = _get_session()
    try:
        resp = session.get(url, params=query, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"API错误 {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"请求失败: {e}")
        print(f"[错误] Sportmonks请求失败: {str(e)[:60]}")
    return None


def _resolve_league(league: str) -> int:
    """解析联赛ID"""
    if league in LEAGUE_IDS:
        return LEAGUE_IDS[league]
    try:
        return int(league)
    except:
        return 0


# ==================== 核心接口 ====================

def get_fixtures(date: str = None, league: str = None, season_id: int = None) -> List[Dict]:
    """获取赛程

    Args:
        date: 日期 (YYYY-MM-DD)
        league: 联赛名称或ID
        season_id: 赛季ID

    Returns:
        [{"fixture_id", "home_team", "away_team", "home_score", "away_score",
          "date", "time", "status", "league", "round", "source"}]
    """
    params = {"include": INCLUDES["fixtures"]}

    if date:
        endpoint = "fixtures/date/" + date
    elif league:
        league_id = _resolve_league(league)
        endpoint = f"leagues/{league_id}/fixtures"
        if season_id:
            params["seasons"] = str(season_id)
    else:
        endpoint = "fixtures"

    data = _request(endpoint, params)
    if not data or "data" not in data:
        return []

    matches = []
    for item in data["data"]:
        participants = item.get("participants", [])
        home, away = None, None
        for p in participants:
            if p.get("meta", {}).get("location") == "home":
                home = p.get("name")
            else:
                away = p.get("name")

        scores = item.get("scores", [])
        home_score, away_score = None, None
        for s in scores:
            if s.get("score", {}).get("location") == "home":
                home_score = s.get("score", {}).get("goals")
            else:
                away_score = s.get("score", {}).get("goals")

        matches.append({
            'fixture_id': item.get("id"),
            'home_team': home,
            'away_team': away,
            'home_score': home_score,
            'away_score': away_score,
            'date': item.get("starting_at", "")[:10],
            'time': item.get("starting_at", "")[11:16] if item.get("starting_at") else None,
            'status': item.get("state", {}).get("short_name", ""),
            'league': item.get("league", {}).get("name", "") if item.get("league") else "",
            'round': item.get("round", {}).get("name") if item.get("round") else None,
            'source': 'sportmonks'
        })

    print(f"[sportmonks] 赛程: {len(matches)}场")
    return matches


def get_standings(league: str, season_id: int = None) -> List[Dict]:
    """获取积分榜

    Returns:
        [{"position", "team", "team_id", "played", "won", "drawn", "lost",
          "goals_for", "goals_against", "goal_difference", "points",
          "league", "source"}]
    """
    league_id = _resolve_league(league)
    params = {"include": INCLUDES["standings"]}
    if season_id:
        params["seasons"] = str(season_id)

    data = _request(f"standings/leagues/{league_id}", params)
    if not data or "data" not in data:
        return []

    standings = []
    for group in data["data"]:
        for item in group.get("standings", []):
            details = item.get("participant", {})
            result = item.get("result", {})
            standings.append({
                'position': item.get("position", 0),
                'team': details.get("name", ""),
                'team_id': details.get("id"),
                'played': result.get("played", 0),
                'won': result.get("won", 0),
                'drawn': result.get("draw", 0),
                'lost': result.get("lost", 0),
                'goals_for': result.get("goals_scored", 0),
                'goals_against': result.get("goals_conceded", 0),
                'goal_difference': result.get("goal_difference", 0),
                'points': result.get("points", 0),
                'league': league,
                'source': 'sportmonks'
            })

    print(f"[sportmonks] 积分榜 {league}: {len(standings)}队")
    return standings


def get_lineups(fixture_id: int) -> Dict:
    """获取比赛阵容 (含xG)

    Returns:
        {"fixture_id", "data": raw, "source"}
        注: sportmonks API格式未确认(无API key测试)，暂返回raw data + fixture_id回写
    """
    data = _request(f"lineups/lineups/fixtures/{fixture_id}",
                    {"include": INCLUDES["lineups"]})
    if not data or "data" not in data:
        return {}
    return {
        'fixture_id': fixture_id,
        'data': data["data"],
        'source': 'sportmonks'
    }


def get_predictions(fixture_id: int) -> Dict:
    """获取比赛预测 (含xG预测)

    Returns:
        {"fixture_id", "data": raw, "source"}
        注: sportmonks API格式未确认(无API key测试)，暂返回raw data + fixture_id回写
    """
    data = _request(f"predictions/fixtures/{fixture_id}",
                    {"include": INCLUDES["predictions"]})
    if not data or "data" not in data:
        return {}
    return {
        'fixture_id': fixture_id,
        'data': data["data"],
        'source': 'sportmonks'
    }


if __name__ == "__main__":
    print("Sportmonks数据获取工具")
    print("注意: 需要配置API Key才能使用")