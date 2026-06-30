"""
ESPN Soccer API数据获取

功能:
1. 获取赛后阵容 (首发+替补+阵型) — 已完赛比赛
2. 获取联赛赛程/比分
3. 获取球队伤病 (赛季期间可用)

数据来源: site.api.espn.com (免费, 无需认证)

注意:
- 赛后阵容数据完整(11首发+替补), 赛前阵容为空
- 伤病端点在赛季期间有数据, 休赛期为空
- 不需要API key, 但有隐含的请求频率限制

使用示例:
    from fetchers.espn.get_lineups import get_match_lineup, get_league_scoreboard
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.espn.config import REQUEST_TIMEOUT

os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'

logger = logging.getLogger(__name__)

API_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# ESPN league code mapping (league_cn -> espn code)
LEAGUE_CODES = {
    "英超": "eng.1", "premier_league": "eng.1",
    "西甲": "esp.1", "la_liga": "esp.1",
    "德甲": "ger.1", "bundesliga": "ger.1",
    "意甲": "ita.1", "serie_a": "ita.1",
    "法甲": "fra.1", "ligue_1": "fra.1",
    "荷甲": "ned.1", "eredivisie": "ned.1",
    "葡超": "por.1", "primeira_liga": "por.1",
    "英冠": "eng.2", "championship": "eng.2",
    "欧冠": "uefa.champions", "champions_league": "uefa.champions",
    "欧联": "uefa.europa", "europa_league": "uefa.europa",
    "中超": "chn.1", "chinese_super_league": "chn.1",
    "J联赛": "jpn.1", "j_league": "jpn.1",
    "K联赛": "kor.1", "k_league": "kor.1",
    "MLS": "usa.1", "major_league_soccer": "usa.1",
    "巴甲": "bra.1", "brasileirao": "bra.1",
    "阿甲": "arg.1", "argentine_primera": "arg.1",
    "墨超": "mex.1", "liga_mx": "mex.1",
}

_session = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.trust_env = False
        _session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
    return _session


def _api_request(endpoint: str, params: Dict = None) -> Optional[Dict]:
    session = _get_session()
    url = f"{API_BASE}/{endpoint}"
    try:
        resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"ESPN API {resp.status_code}: {url}")
    except Exception as e:
        logger.error(f"ESPN API request failed: {e}")
    return None


def resolve_league_code(league: str) -> Optional[str]:
    return LEAGUE_CODES.get(league) or LEAGUE_CODES.get(league.lower().replace(" ", "_"))


def get_league_scoreboard(league: str = "eng.1") -> Dict:
    """Get league scoreboard with current events.

    Returns:
        {"events": [...], "league": str, "source": "espn_api"}
    """
    code = resolve_league_code(league) or league
    data = _api_request(f"{code}/scoreboard")
    if not data:
        return {"events": [], "league": league, "source": "espn_api", "error": "no data"}

    events = []
    for ev in data.get("events", []):
        status_type = ev.get("status", {}).get("type", {})
        competitions = ev.get("competitions", [])
        home_team = away_team = ""
        home_score = away_score = None
        if competitions:
            comp = competitions[0]
            for c in comp.get("competitors", []):
                team = c.get("team", {})
                name = team.get("displayName", team.get("shortDisplayName", ""))
                score = c.get("score")
                if c.get("homeAway") == "home":
                    home_team = name
                    home_score = int(score) if score and str(score).isdigit() else None
                else:
                    away_team = name
                    away_score = int(score) if score and str(score).isdigit() else None

        events.append({
            "event_id": ev.get("id"),
            "name": ev.get("name", ""),
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "date": ev.get("date", ""),
            "status": status_type.get("name", ""),
            "completed": status_type.get("completed", False),
        })

    return {"events": events, "league": league, "source": "espn_api"}


def get_match_lineup(event_id: str, league: str = "eng.1") -> Dict:
    """Get match lineup from ESPN summary API.

    For completed matches: returns full lineup (starters + subs + formation).
    For scheduled matches: returns empty rosters (ESPN doesn't provide pre-match lineups).

    Args:
        event_id: ESPN event ID (e.g., "748515")
        league: ESPN league code (e.g., "eng.1")

    Returns:
        {"home": {...}, "away": {...}, "match_status": str, "has_lineup": bool, "source": "espn_api"}
    """
    code = resolve_league_code(league) or league
    data = _api_request(f"{code}/summary", {"event": event_id})
    if not data:
        return {"home": {}, "away": {}, "match_status": "unknown", "has_lineup": False,
                "source": "espn_api", "error": "no data"}

    rosters = data.get("rosters", [])
    result = {"home": {}, "away": {}, "match_status": "", "has_lineup": False, "source": "espn_api"}

    for r in rosters:
        team = r.get("team", {})
        team_name = team.get("displayName", "")
        team_id = team.get("id")
        roster = r.get("roster", [])
        formation = r.get("formation", {})

        starters = []
        subs = []
        for p in roster:
            athlete = p.get("athlete", {})
            entry = {
                "name": athlete.get("displayName", ""),
                "short_name": athlete.get("shortName", ""),
                "position": p.get("position", {}).get("abbreviation", ""),
                "jersey": p.get("jersey"),
                "starter": p.get("starter", False),
                "active": p.get("active", False),
            }
            if p.get("starter"):
                starters.append(entry)
            elif p.get("active"):
                subs.append(entry)

        side_data = {
            "team_id": team_id,
            "team_name": team_name,
            "formation": formation,
            "starters": starters,
            "subs": subs,
            "starter_count": len(starters),
            "sub_count": len(subs),
        }

        if r.get("homeAway") == "home" or (not result["home"] and not result["away"]):
            if not result["home"]:
                result["home"] = side_data
            else:
                result["away"] = side_data
        else:
            result["away"] = side_data

    has_lineup = bool(result["home"].get("starters") or result["away"].get("starters"))
    result["has_lineup"] = has_lineup

    return result


def get_league_injuries(league: str = "eng.1") -> Dict:
    """Get league-wide injury report.

    Returns empty list during off-season. Works during active season.

    Returns:
        {"injuries": [...], "league": str, "source": "espn_api"}
    """
    code = resolve_league_code(league) or league
    data = _api_request(f"{code}/injuries")
    if not data:
        return {"injuries": [], "league": league, "source": "espn_api", "error": "no data"}

    injuries = []
    for inj in data.get("injuries", []):
        athlete = inj.get("athlete", {})
        team = inj.get("team", {})
        injuries.append({
            "athlete_id": athlete.get("id"),
            "athlete_name": athlete.get("displayName", ""),
            "team_id": team.get("id"),
            "team_name": team.get("displayName", ""),
            "injury_type": inj.get("type", {}).get("description", ""),
            "status": inj.get("status", {}).get("name", ""),
            "return_date": inj.get("returnDate"),
        })

    return {"injuries": injuries, "league": league, "source": "espn_api"}


def get_team_injuries(league: str = "eng.1", team_id: int = None) -> Dict:
    """Get team-specific injuries.

    Args:
        league: ESPN league code
        team_id: ESPN team ID (e.g., 359 for Arsenal)

    Returns:
        {"injuries": [...], "team": str, "source": "espn_api"}
    """
    code = resolve_league_code(league) or league
    params = {}
    if team_id:
        params["team"] = team_id
    data = _api_request(f"{code}/injuries", params)
    if not data:
        return {"injuries": [], "team": str(team_id), "source": "espn_api", "error": "no data"}

    injuries = []
    for inj in data.get("injuries", []):
        athlete = inj.get("athlete", {})
        injuries.append({
            "athlete_id": athlete.get("id"),
            "athlete_name": athlete.get("displayName", ""),
            "injury_type": inj.get("type", {}).get("description", ""),
            "status": inj.get("status", {}).get("name", ""),
            "return_date": inj.get("returnDate"),
        })

    return {"injuries": injuries, "team": str(team_id), "source": "espn_api"}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m fetchers.espn.get_lineups scoreboard eng.1")
        print("  python -m fetchers.espn.get_lineups lineup 748515 esp.1")
        print("  python -m fetchers.espn.get_lineups injuries eng.1")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "scoreboard":
        lg = sys.argv[2] if len(sys.argv) > 2 else "eng.1"
        sb = get_league_scoreboard(lg)
        for ev in sb.get("events", []):
            print(f"  {ev['name']} ({ev['status']}) id={ev['event_id']}")
    elif cmd == "lineup":
        eid = sys.argv[2] if len(sys.argv) > 2 else "748515"
        lg = sys.argv[3] if len(sys.argv) > 3 else "esp.1"
        lu = get_match_lineup(eid, lg)
        for side in ("home", "away"):
            d = lu.get(side, {})
            print(f"  {d.get('team_name','?')} ({d.get('formation','?')}): {d.get('starter_count',0)} starters")
            for s in d.get("starters", []):
                print(f"    {s['name']} ({s['position']}) #{s['jersey']}")
    elif cmd == "injuries":
        lg = sys.argv[2] if len(sys.argv) > 2 else "eng.1"
        inj = get_league_injuries(lg)
        print(f"  Injuries: {len(inj.get('injuries', []))}")
