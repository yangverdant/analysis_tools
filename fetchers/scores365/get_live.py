"""
365Scores数据获取

功能:
1. 获取实时比分
2. 获取比赛事件 (进球/红黄牌/换人)
3. 获取比赛统计

数据来源: webws.365scores.com (免费, 无需认证)

使用示例:
    from fetchers.scores365.get_live import get_livescores

    # 实时比分
    matches = get_livescores()
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.scores365.config import BASE_URL, REQUEST_TIMEOUT, COMPETITION_IDS, DEFAULT_PARAMS

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
    query = dict(DEFAULT_PARAMS)
    if params:
        query.update(params)

    session = _get_session()
    try:
        resp = session.get(f"{BASE_URL}/{endpoint}", params=query,
                           timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"365Scores请求失败: {e}")
        print(f"[错误] 365Scores请求失败: {str(e)[:60]}")
    return None


def _parse_int(v) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except:
        return None


# ==================== 核心接口 ====================

def get_livescores(competition_id: int = None) -> List[Dict]:
    """获取实时比分

    Args:
        competition_id: 联赛ID (可选, 不填返回所有)

    Returns:
        [{"match_id", "home_team", "away_team", "home_score", "away_score",
          "status", "minute", "league", "date", "source"}]
    """
    params = {}
    if competition_id:
        params["competitors"] = str(competition_id)

    data = _request("matches/results", params)
    if not data:
        return []

    matches = []
    for game in data.get("games", []):
        home = game.get("homeCompetitor", {})
        away = game.get("awayCompetitor", {})

        matches.append({
            'match_id': str(game.get("id", "")),
            'home_team': home.get("shortName", "") or home.get("name", ""),
            'away_team': away.get("shortName", "") or away.get("name", ""),
            'home_score': _parse_int(home.get("score")),
            'away_score': _parse_int(away.get("score")),
            'status': game.get("gameStatus", {}).get("text", ""),
            'minute': game.get("gameTime", {}).get("minute"),
            'league': game.get("competition", {}).get("name", ""),
            'competition_id': game.get("competition", {}).get("id"),
            'date': game.get("startTime", "")[:10] if game.get("startTime") else None,
            'source': '365scores'
        })

    print(f"[365scores] 实时比分: {len(matches)}场")
    return matches


def get_match_events(match_id: str) -> List[Dict]:
    """获取比赛事件 (进球/红黄牌/换人等)

    Returns:
        [{"event_type", "minute", "player", "team", "detail", "source"}]
    """
    params = {"gameId": match_id}
    data = _request("matches/events", params)
    if not data:
        return []

    events = []
    for evt in data.get("events", []):
        events.append({
            'event_type': evt.get("type", ""),
            'minute': evt.get("minute"),
            'player': evt.get("player", {}).get("name", ""),
            'team': evt.get("competitor", {}).get("shortName", ""),
            'detail': evt.get("text", ""),
            'source': '365scores'
        })
    return events


def get_match_stats(match_id: str) -> Dict:
    """获取比赛统计数据

    Returns:
        {"match_id", "stats": [{"name", "home_value", "away_value"}], "source"}
    """
    params = {"gameId": match_id}
    data = _request("matches/stats", params)
    if not data:
        return {}

    stats = []
    for s in data.get("stats", []):
        stats.append({
            'name': s.get("name", ""),
            'home_value': s.get("homeValue", ""),
            'away_value': s.get("awayValue", ""),
        })

    return {
        'match_id': match_id,
        'stats': stats,
        'source': '365scores'
    }


if __name__ == "__main__":
    matches = get_livescores()
    for m in matches[:20]:
        score = f"{m['home_score']}-{m['away_score']}" if m['home_score'] is not None else "vs"
        print(f"  {m['home_team']} {score} {m['away_team']} [{m['league']}]")