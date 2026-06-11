"""
The Odds API赔率数据获取

功能:
1. 获取多家博彩公司实时赔率 (欧赔/亚盘/大小球)
2. 获取可用联赛列表
3. 支持RapidAPI代理访问

数据来源: the-odds-api.com (免费500次/月) / RapidAPI

使用示例:
    from fetchers.the_odds_api.get_odds import get_odds, get_sports

    # 英超赔率
    odds = get_odds("soccer_epl")

    # 亚盘赔率
    odds = get_odds("soccer_epl", markets="spreads")

    # 大小球赔率
    odds = get_odds("soccer_epl", markets="totals")
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.the_odds_api.config import (
    API_KEY, BASE_URL, RAPIDAPI_URL, RAPIDAPI_HOST,
    SPORT_KEYS, SPORT_CN, MARKETS, REQUEST_TIMEOUT
)
from fetchers.common.date_utils import normalize_date
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
    return _session


# ==================== 核心接口 ====================

def get_sports() -> List[Dict]:
    """获取可用联赛/运动列表

    Returns:
        [{"key", "active", "group", "description", "title"}]
    """
    session = _get_session()
    try:
        resp = session.get(f"{BASE_URL}/sports/", params={"apiKey": API_KEY},
                           timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            data = resp.json()
            print(f"[the-odds-api] 可用联赛: {len(data)}个")
            return data
    except Exception as e:
        logger.error(f"获取联赛列表失败: {e}")
    return []


def get_odds(sport: str = "soccer_epl", markets: str = "h2h",
             regions: str = "uk,eu", dateFormat: str = "iso") -> List[Dict]:
    """获取赔率数据

    Args:
        sport: 联赛key (如 "soccer_epl") 或中文名 (如 "英超")
        markets: 赔率市场 ("h2h"=胜负平, "spreads"=亚盘, "totals"=大小球)
        regions: 博彩公司区域 ("uk"=英国, "eu"=欧洲, "us"=美国)
        dateFormat: 日期格式

    Returns:
        [{"sport_key", "sport_title", "home_team", "away_team",
          "commence_time", "odds": [{"bookmaker", "markets": [...]}], "source"}]
    """
    # 解析联赛key
    if sport in SPORT_CN:
        sport = SPORT_CN[sport]
    sport_key = sport

    session = _get_session()
    try:
        resp = session.get(
            f"{BASE_URL}/sports/{sport_key}/odds/",
            params={
                "apiKey": API_KEY,
                "regions": regions,
                "markets": markets,
                "dateFormat": dateFormat,
                "oddsFormat": "decimal",
            },
            timeout=REQUEST_TIMEOUT,
            proxies={'http': None, 'https': None}
        )

        if resp.status_code == 200:
            data = resp.json()
            result = []
            for item in data:
                odds_list = []
                for bm in item.get("bookmakers", []):
                    bm_data = {
                        'bookmaker': bm.get("title", ""),
                        'key': bm.get("key", ""),
                        'markets': [],
                    }
                    for mkt in bm.get("markets", []):
                        mkt_data = {
                            'market_type': mkt.get("key", ""),
                            'outcomes': mkt.get("outcomes", []),
                        }
                        bm_data['markets'].append(mkt_data)
                    odds_list.append(bm_data)

                result.append({
                    'sport_key': item.get("sport_key", ""),
                    'sport_title': item.get("sport_title", ""),
                    'league': normalize_league_name(item.get("sport_key", "")),
                    'home_team': item.get("home_team", ""),
                    'away_team': item.get("away_team", ""),
                    'commence_time': item.get("commence_time", ""),
                    'date': normalize_date(item.get("commence_time", "")),
                    'market_type': markets,
                    'odds': odds_list,
                    'source': 'the-odds-api'
                })

            print(f"[the-odds-api] {sport_key} 赔率: {len(result)}场")
            return result

        elif resp.status_code == 401:
            print("[错误] The Odds API Key无效或已过期")
        elif resp.status_code == 429:
            print("[错误] API调用次数已达上限 (免费500次/月)")

    except Exception as e:
        logger.error(f"获取赔率失败: {e}")
        print(f"[错误] The Odds API请求失败: {str(e)[:60]}")

    return []


def get_odds_rapidapi(sport: str = "soccer") -> List[Dict]:
    """通过RapidAPI代理获取赔率

    Returns:
        赔率数据
    """
    session = _get_session()
    try:
        headers = {
            "X-RapidAPI-Key": API_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST,
        }
        resp = session.get(f"{RAPIDAPI_URL}/v1/odds", headers=headers,
                           params={"sport": sport},
                           timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.json().get("data", [])
    except Exception as e:
        logger.error(f"RapidAPI赔率请求失败: {e}")
    return []


if __name__ == "__main__":
    import sys

    sport = sys.argv[1] if len(sys.argv) > 1 else "soccer_epl"
    market = sys.argv[2] if len(sys.argv) > 2 else "h2h"

    odds = get_odds(sport, market)
    for o in odds[:5]:
        print(f"  {o['home_team']} vs {o['away_team']}")
        for bm in o.get('odds', [])[:3]:
            for mkt in bm.get('markets', []):
                outcomes = mkt.get('outcomes', [])
                prices = " / ".join(f"{x['name']}={x['price']}" for x in outcomes)
                print(f"    {bm['bookmaker']}: {prices}")