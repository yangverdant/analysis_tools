"""
FlashLive数据获取

功能:
1. 获取实时比分
2. 获取赛程
3. 获取联赛数据

数据来源: flashlive-sports.p.rapidapi.com (RapidAPI, 需Key)

使用示例:
    from fetchers.flashlive.get_live import get_livescores

    matches = get_livescores()
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.flashlive.config import RAPIDAPI_KEY, BASE_URL, RAPIDAPI_HOST, REQUEST_TIMEOUT

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
    """发送RapidAPI请求"""
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }

    session = _get_session()
    try:
        resp = session.get(f"{BASE_URL}/{endpoint}", headers=headers,
                           params=params, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"FlashLive请求失败: {e}")
        print(f"[错误] FlashLive请求失败: {str(e)[:60]}")
    return None


# ==================== 核心接口 ====================

def get_livescores(sport_id: int = 1) -> List[Dict]:
    """获取实时比分

    Args:
        sport_id: 运动类型ID (1=足球)

    Returns:
        [{"match_id", "home_team", "away_team", "home_score", "away_score",
          "status", "minute", "league", "source"}]
    """
    data = _request("events/list", {
        "sport_id": sport_id,
        "indent": "today",
    })

    if not data or "DATA" not in data:
        return []

    matches = []
    for item in data["DATA"]:
        for event in item.get("EVENTS", []):
            home = event.get("HOME_PARTICIPANT", {})
            away = event.get("AWAY_PARTICIPANT", {})

            matches.append({
                'match_id': event.get("EVENT_ID"),
                'home_team': home.get("SHORT_NAME", ""),
                'away_team': away.get("SHORT_NAME", ""),
                'home_score': event.get("HOME_SCORE"),
                'away_score': event.get("AWAY_SCORE"),
                'status': event.get("STAGE", ""),
                'minute': event.get("MINUTE"),
                'league': item.get("TOURNAMENT_NAME", ""),
                'league_id': item.get("TOURNAMENT_ID"),
                'date': event.get("START_TIME", "")[:10] if event.get("START_TIME") else None,
                'source': 'flashlive'
            })

    print(f"[flashlive] 实时比分: {len(matches)}场")
    return matches


def get_league_events(league_id: str) -> List[Dict]:
    """获取联赛比赛

    Args:
        league_id: 联赛ID

    Returns:
        比赛列表
    """
    data = _request("events/list-by-tournament", {
        "tournament_id": league_id,
        "indent": "today",
    })

    if not data or "DATA" not in data:
        return []

    matches = []
    for event in data["DATA"]:
        home = event.get("HOME_PARTICIPANT", {})
        away = event.get("AWAY_PARTICIPANT", {})

        matches.append({
            'match_id': event.get("EVENT_ID"),
            'home_team': home.get("SHORT_NAME", ""),
            'away_team': away.get("SHORT_NAME", ""),
            'home_score': event.get("HOME_SCORE"),
            'away_score': event.get("AWAY_SCORE"),
            'date': event.get("START_TIME", "")[:10] if event.get("START_TIME") else None,
            'source': 'flashlive'
        })

    print(f"[flashlive] 联赛 {league_id}: {len(matches)}场")
    return matches


if __name__ == "__main__":
    matches = get_livescores()
    for m in matches[:20]:
        score = f"{m['home_score']}-{m['away_score']}" if m['home_score'] else "vs"
        print(f"  {m['home_team']} {score} {m['away_team']} [{m['league']}]")