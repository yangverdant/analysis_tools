"""
赔率API数据获取

功能:
1. 获取Odds Feed赔率 (多家公司欧赔)
2. 获取Bet365赔率
3. 获取Football Betting Odds赔率

数据来源: RapidAPI (需Key)

使用示例:
    from fetchers.odds_api.get_odds import get_odds_feed, get_bet365_odds

    # Odds Feed赔率
    odds = get_odds_feed(match_id="12345")

    # Bet365赔率
    odds = get_bet365_odds(event_id="12345")
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.odds_api.config import (
    RAPIDAPI_KEY, ODDS_FEED_URL, ODDS_FEED_HOST,
    BET365_URL, BET365_HOST, FB_ODDS_URL, FB_ODDS_HOST,
    REQUEST_TIMEOUT
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


def _rapidapi_request(base_url: str, host: str, endpoint: str, params: Dict = None) -> Optional[Dict]:
    """发送RapidAPI请求"""
    url = f"{base_url}/{endpoint}"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": host
    }

    session = _get_session()
    try:
        resp = session.get(url, headers=headers, params=params,
                           timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"RapidAPI错误 {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"RapidAPI请求失败: {e}")
        print(f"[错误] 赔率API请求失败: {str(e)[:60]}")
    return None


# ==================== 核心接口 ====================

def get_odds_feed(match_id: str = None, league: str = None) -> List[Dict]:
    """获取Odds Feed赔率

    Args:
        match_id: 比赛ID
        league: 联赛名

    Returns:
        [{"match_id", "sport", "league", "home_team", "away_team",
          "match_time", "odds_home", "odds_draw", "odds_away", "source"}]
    """
    params = {}
    if match_id:
        params["match_id"] = match_id
    if league:
        params["league"] = league

    data = _rapidapi_request(ODDS_FEED_URL, ODDS_FEED_HOST, "v1/odds", params)
    if not data or "data" not in data:
        return []

    odds_list = []
    for item in data["data"]:
        odds = item.get("odds", {})
        odds_list.append({
            'match_id': item.get("id"),
            'sport': item.get("sport"),
            'league': item.get("league"),
            'home_team': item.get("home_team"),
            'away_team': item.get("away_team"),
            'match_time': item.get("match_time"),
            'odds_home': odds.get("home"),
            'odds_draw': odds.get("draw"),
            'odds_away': odds.get("away"),
            'source': 'odds_feed'
        })

    print(f"[odds_api] Odds Feed赔率: {len(odds_list)}条")
    return odds_list


def get_bet365_odds(event_id: str = None) -> List[Dict]:
    """获取Bet365赔率

    Returns:
        [{"event_id", "source", "data": raw_api_data}]
        注: Bet365 API格式未确认，暂返回raw data + event_id回写
    """
    params = {}
    if event_id:
        params["event_id"] = event_id

    data = _rapidapi_request(BET365_URL, BET365_HOST, "v1/odds", params)
    if not data or "data" not in data:
        return []

    results = []
    for item in data["data"]:
        entry = {
            'event_id': event_id,
            'source': 'bet365',
            'data': item,
        }
        # 尝试提取常见字段（如果能匹配的话）
        if isinstance(item, dict):
            entry['home_team'] = item.get("home_team", "")
            entry['away_team'] = item.get("away_team", "")
            entry['date'] = item.get("match_time", item.get("date", ""))
        results.append(entry)

    print(f"[odds_api] Bet365赔率: {len(results)}条")
    return results


def get_fb_odds(match_id: str = None) -> List[Dict]:
    """获取Football Betting Odds赔率

    Returns:
        [{"match_id", "source", "data": raw_api_data}]
        注: FB Odds API格式未确认，暂返回raw data + match_id回写
    """
    params = {}
    if match_id:
        params["match_id"] = match_id

    data = _rapidapi_request(FB_ODDS_URL, FB_ODDS_HOST, "v1/odds", params)
    if not data or "data" not in data:
        return []

    results = []
    for item in data["data"]:
        entry = {
            'match_id': match_id,
            'source': 'football_betting_odds',
            'data': item,
        }
        # 尝试提取常见字段（如果能匹配的话）
        if isinstance(item, dict):
            entry['home_team'] = item.get("home_team", "")
            entry['away_team'] = item.get("away_team", "")
            entry['date'] = item.get("match_time", item.get("date", ""))
        results.append(entry)

    print(f"[odds_api] FB Odds赔率: {len(results)}条")
    return results


if __name__ == "__main__":
    print("赔率API数据获取工具")
    print("数据源: Odds Feed / Bet365 / Football Betting Odds (RapidAPI)")