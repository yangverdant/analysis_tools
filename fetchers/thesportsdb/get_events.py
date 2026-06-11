"""
TheSportsDB数据获取

功能:
1. 获取某日比赛
2. 获取球队详情 (含logo/场馆/网站)
3. 获取球队最近比赛
4. 获取比赛详情 (含阵容/进球详情)

数据来源: thesportsdb.com (免费, 无需Key)

使用示例:
    from fetchers.thesportsdb.get_events import get_events_by_date, get_team_detail

    # 某日比赛
    events = get_events_by_date("2026-01-15")

    # 球队详情
    team = get_team_detail("133604")  # Arsenal
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
import requests

from fetchers.thesportsdb.config import BASE_URL, REQUEST_TIMEOUT

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
    url = f"{BASE_URL}{endpoint}"
    session = _get_session()
    try:
        resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"TheSportsDB请求失败: {e}")
        print(f"[错误] TheSportsDB请求失败: {str(e)[:60]}")
    return None


# ==================== 核心接口 ====================

def get_events_by_date(date: str = None) -> List[Dict]:
    """获取某日比赛

    Args:
        date: 日期 (YYYY-MM-DD, 默认今天)

    Returns:
        [{"event_id", "home_team", "away_team", "home_score", "away_score",
          "date", "time", "league", "round", "venue", "status", "source"}]
    """
    if date:
        date_str = date.replace("-", "")
    else:
        date_str = datetime.now().strftime("%Y%m%d")

    data = _request("/eventsday.php", {"d": date_str, "s": "Soccer"})
    if not data:
        return []

    events = []
    for item in data.get("events", []):
        if not item:
            continue
        events.append({
            'event_id': str(item.get("idEvent", "")),
            'home_team': item.get("strHomeTeam", ""),
            'home_team_id': str(item.get("idHomeTeam", "")),
            'away_team': item.get("strAwayTeam", ""),
            'away_team_id': str(item.get("idAwayTeam", "")),
            'home_score': int(item.get("intHomeScore", 0)) if item.get("intHomeScore") else None,
            'away_score': int(item.get("intAwayScore", 0)) if item.get("intAwayScore") else None,
            'date': item.get("dateEvent", ""),
            'time': item.get("strTime", "")[:5] if item.get("strTime") else None,
            'league': item.get("strLeague", ""),
            'league_id': str(item.get("idLeague", "")),
            'round': int(item.get("intRound", 0)) if item.get("intRound") else None,
            'venue': item.get("strVenue", ""),
            'status': item.get("strStatus", ""),
            'thumb': item.get("strThumb", ""),
            'home_goals_detail': item.get("strHomeGoalDetails", ""),
            'away_goals_detail': item.get("strAwayGoalDetails", ""),
            'home_red_cards': item.get("strHomeRedCards", ""),
            'away_red_cards': item.get("strAwayRedCards", ""),
            'home_yellow_cards': item.get("strHomeYellowCards", ""),
            'away_yellow_cards': item.get("strAwayYellowCards", ""),
            'home_lineup_gk': item.get("strHomeLineupGoalkeeper", ""),
            'away_lineup_gk': item.get("strAwayLineupGoalkeeper", ""),
            'home_lineup_def': item.get("strHomeLineupDefense", ""),
            'away_lineup_def': item.get("strAwayLineupDefense", ""),
            'home_lineup_mid': item.get("strHomeLineupMidfield", ""),
            'away_lineup_mid': item.get("strAwayLineupMidfield", ""),
            'home_lineup_fwd': item.get("strHomeLineupForward", ""),
            'away_lineup_fwd': item.get("strAwayLineupForward", ""),
            'home_formation': item.get("strHomeFormation", ""),
            'away_formation': item.get("strAwayFormation", ""),
            'source': 'thesportsdb'
        })

    print(f"[thesportsdb] 比赛 {date or '今天'}: {len(events)}场")
    return events


def get_event_detail(event_id: str) -> Dict:
    """获取比赛详情

    Returns:
        比赛详细信息 (含阵容/进球详情/视频)
    """
    data = _request("/lookupevent.php", {"id": event_id})
    if not data or not data.get("events"):
        return {}

    item = data["events"][0]
    result = {
        'event_id': str(item.get("idEvent", "")),
        'home_team': item.get("strHomeTeam", ""),
        'away_team': item.get("strAwayTeam", ""),
        'home_score': int(item.get("intHomeScore", 0)) if item.get("intHomeScore") else None,
        'away_score': int(item.get("intAwayScore", 0)) if item.get("intAwayScore") else None,
        'date': item.get("dateEvent", ""),
        'league': item.get("strLeague", ""),
        'venue': item.get("strVenue", ""),
        'video': item.get("strVideo", ""),
        'thumb': item.get("strThumb", ""),
        'source': 'thesportsdb'
    }
    return result


def get_team_detail(team_id: str) -> Dict:
    """获取球队详情

    Returns:
        {"team_id", "name", "short_name", "country", "founded", "venue",
         "capacity", "badge", "website", "description", "source"}
    """
    data = _request("/lookupteam.php", {"id": team_id})
    if not data or not data.get("teams"):
        return {}

    item = data["teams"][0]
    return {
        'team_id': str(item.get("idTeam", "")),
        'name': item.get("strTeam", ""),
        'short_name': item.get("strTeamShort", ""),
        'alternate': item.get("strAlternate", ""),
        'country': item.get("strCountry", ""),
        'founded': int(item.get("intFormedYear", 0)) if item.get("intFormedYear") else None,
        'venue': item.get("strStadium", ""),
        'venue_location': item.get("strStadiumLocation", ""),
        'capacity': int(item.get("intStadiumCapacity", 0)) if item.get("intStadiumCapacity") else None,
        'badge': item.get("strTeamBadge", ""),
        'jersey': item.get("strTeamJersey", ""),
        'logo': item.get("strTeamLogo", ""),
        'website': item.get("strWebsite", ""),
        'description': item.get("strDescriptionEN", ""),
        'league': item.get("strLeague", ""),
        'source': 'thesportsdb'
    }


def get_team_next_events(team_id: str) -> List[Dict]:
    """获取球队下一场比赛"""
    data = _request("/eventsnext.php", {"id": team_id})
    if not data:
        return []

    events = []
    for item in data.get("events", []):
        if item:
            events.append({
                'event_id': str(item.get("idEvent", "")),
                'home_team': item.get("strHomeTeam", ""),
                'away_team': item.get("strAwayTeam", ""),
                'date': item.get("dateEvent", ""),
                'league': item.get("strLeague", ""),
                'source': 'thesportsdb'
            })
    return events


def get_team_last_events(team_id: str) -> List[Dict]:
    """获取球队最近比赛"""
    data = _request("/eventslast.php", {"id": team_id})
    if not data:
        return []

    events = []
    for item in data.get("events", []):
        if item:
            events.append({
                'event_id': str(item.get("idEvent", "")),
                'home_team': item.get("strHomeTeam", ""),
                'away_team': item.get("strAwayTeam", ""),
                'home_score': int(item.get("intHomeScore", 0)) if item.get("intHomeScore") else None,
                'away_score': int(item.get("intAwayScore", 0)) if item.get("intAwayScore") else None,
                'date': item.get("dateEvent", ""),
                'league': item.get("strLeague", ""),
                'source': 'thesportsdb'
            })
    return events


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.thesportsdb.get_events today")
        print("  python -m fetchers.thesportsdb.get_events date 2026-01-15")
        print("  python -m fetchers.thesportsdb.get_events team 133604")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "today":
        for e in get_events_by_date():
            score = f"{e['home_score']}-{e['away_score']}" if e['home_score'] else "vs"
            print(f"  {e['home_team']} {score} {e['away_team']} [{e['league']}]")
    elif cmd == "date":
        date = sys.argv[2] if len(sys.argv) > 2 else "2026-01-15"
        for e in get_events_by_date(date):
            print(f"  {e['home_team']} vs {e['away_team']} [{e['league']}]")
    elif cmd == "team":
        tid = sys.argv[2] if len(sys.argv) > 2 else "133604"
        t = get_team_detail(tid)
        if t:
            print(f"  {t['name']} ({t['country']}) - {t['venue']}")