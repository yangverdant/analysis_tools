"""
Odds Feed API — 赔率数据获取

功能:
1. get_events() — 获取赛事列表(含event_id)
2. get_odds() — 获取赛事赔率(1X2/亚盘/大小球)
3. get_tournaments() — 获取联赛列表
"""

import os
import requests
from typing import List, Dict, Optional
from fetchers.odds_feed_api.config import RAPIDAPI_KEY, RAPIDAPI_HOST, BASE_URL, REQUEST_TIMEOUT

# 禁用代理
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ['NO_PROXY'] = '*'


def _headers():
    return {
        'Content-Type': 'application/json',
        'x-rapidapi-host': RAPIDAPI_HOST,
        'x-rapidapi-key': RAPIDAPI_KEY,
    }


def _get(path: str, params: dict = None) -> Optional[dict]:
    try:
        resp = requests.get(
            f"{BASE_URL}/{path}",
            headers=_headers(),
            params=params or {},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  Odds Feed API error: {resp.status_code} {resp.text[:100]}")
            return None
    except Exception as e:
        print(f"  Odds Feed API exception: {str(e)[:80]}")
        return None


def get_events(page: int = 0, per_page: int = 50, sport_id: int = 1,
               category_id: int = None, tournament_id: int = None) -> List[Dict]:
    """获取赛事列表

    Returns: [{
        "id": 845, "slug": "arsenal-chelsea",
        "home_participant": {"name": "Arsenal", "slug": "arsenal"},
        "away_participant": {"name": "Chelsea", "slug": "chelsea"},
        "tournament": {"id": 1, "name": "Premier League", "slug": "premier-league"},
        "category": {"id": 56, "name": "England"},
        "start_date": "2026-05-25T15:00:00Z",
        "status": "not_started",
        "score": {"home": null, "away": null},
    }]
    """
    params = {
        'page': str(page),
        'per_page': str(per_page),
        'sport_id': str(sport_id),
    }
    if category_id:
        params['category_id'] = str(category_id)
    if tournament_id:
        params['tournament_id'] = str(tournament_id)

    data = _get("events", params)
    if not data:
        return []

    events = data.get('data', [])
    total = data.get('total', 0)
    return events


def get_odds(event_ids: List[int], market_name: str = "1X2",
             placing: str = "PREMATCH", bet_type: str = "BACK",
             period: str = "FULL_TIME") -> List[Dict]:
    """获取赛事赔率

    Args:
        event_ids: 赛事ID列表(最多10个)
        market_name: 赔率类型 — "1X2"(欧赔), "AH"(亚盘), "OU"(大小球)
        placing: "PREMATCH" 或 "LIVE"
        bet_type: "BACK" 或 "LAY"
        period: "FULL_TIME" 或 "FIRST_HALF"

    Returns: [{
        "event_id": 845,
        "markets": [{
            "bookmaker": {"id": 5, "name": "Bet365"},
            "market_name": "1X2",
            "outcomes": [
                {"name": "1", "price": 1.85},
                {"name": "X", "price": 3.50},
                {"name": "2", "price": 4.20},
            ]
        }]
    }]
    """
    ids_str = ','.join(str(i) for i in event_ids[:10])
    params = {
        'placing': placing,
        'market_name': market_name,
        'bet_type': bet_type,
        'page': '0',
        'event_ids': ids_str,
        'period': period,
    }

    data = _get("markets/feed", params)
    if not data:
        return []

    return data.get('markets', data.get('data', []))


def get_tournaments(sport_id: int = 1, category_id: int = None) -> List[Dict]:
    """获取联赛列表

    Returns: [{
        "id": 1, "name": "Premier League", "slug": "premier-league",
        "category": {"id": 56, "name": "England"},
    }]
    """
    params = {'sport_id': str(sport_id)}
    if category_id:
        params['category_id'] = str(category_id)

    data = _get("tournaments", params)
    if not data:
        return []

    return data.get('data', [])


def search_tournaments(query: str = None, sport_id: int = 1) -> Dict[str, int]:
    """搜索联赛，返回 {联赛名: tournament_id}

    用于一次性查找五大联赛的tournament_id
    """
    # 已知的category IDs
    CATEGORIES = {
        56: "England", 120: "Spain", 76: "Italy",
        43: "Germany", 50: "France", 134: "Norway", 144: "Sweden",
    }

    result = {}
    for cat_id, cat_name in CATEGORIES.items():
        tournaments = get_tournaments(sport_id=sport_id, category_id=cat_id)
        for t in tournaments:
            name = t.get('name', '')
            tid = t.get('id', 0)
            if query and query.lower() in name.lower():
                result[name] = tid
            elif not query:
                result[f"{cat_name}/{name}"] = tid
        import time
        time.sleep(1)

    return result


def get_match_odds_1x2(event_id: int) -> Optional[Dict]:
    """获取单场比赛欧赔(1X2)，返回标准化格式

    Returns: {
        "home_win": 1.85,
        "draw": 3.50,
        "away_win": 4.20,
        "home_win_closing": None,
        "draw_closing": None,
        "away_win_closing": None,
        "bookmaker": "Bet365",
        "all_bookmakers": [{"name": "Bet365", "1": 1.85, "X": 3.50, "2": 4.20}, ...],
    }
    """
    raw = get_odds([event_id], market_name="1X2")
    if not raw:
        return None

    all_bk = []
    best = None
    for mkt in raw:
        bk_name = mkt.get('bookmaker', {}).get('name', '?')
        outcomes = mkt.get('outcomes', [])
        prices = {o.get('name', ''): o.get('price') for o in outcomes}
        h = prices.get('1')
        d = prices.get('X')
        a = prices.get('2')
        if h and d and a:
            entry = {"name": bk_name, "1": h, "X": d, "2": a}
            all_bk.append(entry)
            # 优先选Bet365，其次选第一家
            if bk_name == 'Bet365' or (not best and bk_name != '?'):
                best = {"home_win": h, "draw": d, "away_win": a, "bookmaker": bk_name}

    if not best and all_bk:
        first = all_bk[0]
        best = {"home_win": first["1"], "draw": first["X"], "away_win": first["2"],
                "bookmaker": first["name"]}

    if best:
        best["all_bookmakers"] = all_bk
    return best


def get_match_odds_ah(event_id: int) -> Optional[Dict]:
    """获取单场比赛亚盘赔率

    Returns: {
        "handicap": -0.5,
        "home_win": 1.90,
        "away_win": 1.95,
        "bookmaker": "Bet365",
    }
    """
    raw = get_odds([event_id], market_name="AH")
    if not raw:
        return None

    for mkt in raw:
        bk_name = mkt.get('bookmaker', {}).get('name', '?')
        outcomes = mkt.get('outcomes', [])
        if len(outcomes) >= 2:
            # AH outcomes: [{"name": "1", "price": 1.9, "line": "-0.5"}, ...]
            line = outcomes[0].get('line', outcomes[0].get('handicap', 0))
            try:
                handicap = float(line)
            except (ValueError, TypeError):
                handicap = 0
            prices = {o.get('name', ''): o.get('price') for o in outcomes}
            return {
                "handicap": handicap,
                "home_win": prices.get('1'),
                "away_win": prices.get('2'),
                "bookmaker": bk_name,
            }
    return None


def get_match_odds_ou(event_id: int) -> Optional[Dict]:
    """获取单场比赛大小球赔率

    Returns: {
        "line": 2.5,
        "over": 1.90,
        "under": 1.95,
        "bookmaker": "Bet365",
    }
    """
    raw = get_odds([event_id], market_name="OU")
    if not raw:
        return None

    for mkt in raw:
        bk_name = mkt.get('bookmaker', {}).get('name', '?')
        outcomes = mkt.get('outcomes', [])
        if len(outcomes) >= 2:
            line = outcomes[0].get('line', outcomes[0].get('total', 2.5))
            try:
                total_line = float(line)
            except (ValueError, TypeError):
                total_line = 2.5
            prices = {o.get('name', ''): o.get('price') for o in outcomes}
            return {
                "line": total_line,
                "over": prices.get('Over', prices.get('1', None)),
                "under": prices.get('Under', prices.get('2', None)),
                "bookmaker": bk_name,
            }
    return None