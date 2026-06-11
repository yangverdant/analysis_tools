"""
football-data.org数据获取

功能:
1. 获取今日比赛/联赛赛程
2. 获取积分榜 (含主客场分榜)
3. 获取射手榜
4. 获取球队详情/阵容
5. 获取球员信息

数据来源: api.football-data.org/v4 (免费, 需Token)

使用示例:
    from fetchers.football_data_org.get_matches import get_today_matches, get_standings

    # 今日比赛
    matches = get_today_matches()

    # 积分榜
    standings = get_standings("premier_league")

    # 射手榜
    scorers = get_scorers("premier_league")
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.football_data_org.config import (
    API_TOKEN, BASE_URL, REQUEST_TIMEOUT,
    COMPETITION_CODES, STATUS_MAP
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
        _session.headers.update({"X-Auth-Token": API_TOKEN})
    return _session


def _request(endpoint: str, params: Dict = None) -> Optional[Dict]:
    """发送API请求"""
    session = _get_session()
    url = f"{BASE_URL}/{endpoint}"
    try:
        resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"API错误 {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"请求失败: {e}")
        print(f"[错误] football-data.org请求失败: {str(e)[:60]}")
    return None


def _resolve_code(league: str) -> str:
    """解析联赛代码"""
    if league in COMPETITION_CODES:
        return COMPETITION_CODES[league]
    return league.upper()


# ==================== 核心接口 ====================

def get_today_matches() -> List[Dict]:
    """获取今日所有比赛

    Returns:
        [{"match_id", "home_team", "away_team", "home_score", "away_score",
          "home_score_ht", "away_score_ht", "date", "time", "status",
          "league", "round", "source"}]
    """
    data = _request("matches")
    if not data:
        return []

    matches = []
    for item in data.get("matches", []):
        score = item.get("score", {})
        ft = score.get("fullTime", {})
        ht = score.get("halfTime", {})
        matches.append({
            'match_id': str(item.get("id", "")),
            'home_team': item.get("homeTeam", {}).get("shortName", ""),
            'home_team_id': str(item.get("homeTeam", {}).get("id", "")),
            'away_team': item.get("awayTeam", {}).get("shortName", ""),
            'away_team_id': str(item.get("awayTeam", {}).get("id", "")),
            'home_score': ft.get("home"),
            'away_score': ft.get("away"),
            'home_score_ht': ht.get("home"),
            'away_score_ht': ht.get("away"),
            'date': item.get("utcDate", "")[:10],
            'time': item.get("utcDate", "")[11:16] if item.get("utcDate") else None,
            'status': STATUS_MAP.get(item.get("status", ""), item.get("status", "")),
            'league': item.get("competition", {}).get("name", ""),
            'league_code': item.get("competition", {}).get("code", ""),
            'round': item.get("matchday"),
            'source': 'football-data.org'
        })

    print(f"[football-data.org] 今日比赛: {len(matches)}场")
    return matches


def get_league_matches(league: str, season: str = None) -> List[Dict]:
    """获取联赛比赛列表

    Args:
        league: 联赛名称或代码 (如 "premier_league" 或 "PL")
        season: 赛季起始年 (如 "2025")

    Returns:
        同 get_today_matches 格式
    """
    code = _resolve_code(league)
    endpoint = f"competitions/{code}/matches"
    params = {}
    if season:
        params["season"] = int(season[:4])

    data = _request(endpoint, params)
    if not data:
        return []

    matches = []
    for item in data.get("matches", []):
        score = item.get("score", {})
        ft = score.get("fullTime", {})
        ht = score.get("halfTime", {})
        matches.append({
            'match_id': str(item.get("id", "")),
            'home_team': item.get("homeTeam", {}).get("shortName", ""),
            'home_team_id': str(item.get("homeTeam", {}).get("id", "")),
            'away_team': item.get("awayTeam", {}).get("shortName", ""),
            'away_team_id': str(item.get("awayTeam", {}).get("id", "")),
            'home_score': ft.get("home"),
            'away_score': ft.get("away"),
            'home_score_ht': ht.get("home"),
            'away_score_ht': ht.get("away"),
            'date': item.get("utcDate", "")[:10],
            'time': item.get("utcDate", "")[11:16] if item.get("utcDate") else None,
            'status': STATUS_MAP.get(item.get("status", ""), item.get("status", "")),
            'league': item.get("competition", {}).get("name", ""),
            'league_code': item.get("competition", {}).get("code", ""),
            'round': item.get("matchday"),
            'group': item.get("group"),
            'stage': item.get("stage"),
            'source': 'football-data.org'
        })

    print(f"[football-data.org] {league} 比赛: {len(matches)}场")
    return matches


def get_standings(league: str, season: str = None) -> List[Dict]:
    """获取积分榜 (含TOTAL/HOME/AWAY分榜)

    Args:
        league: 联赛名称或代码
        season: 赛季起始年

    Returns:
        [{"position", "team", "team_id", "played", "won", "drawn", "lost",
          "goals_for", "goals_against", "goal_difference", "points",
          "form", "league", "season", "source"}]
    """
    code = _resolve_code(league)
    endpoint = f"competitions/{code}/standings"
    params = {}
    if season:
        params["season"] = int(season[:4])

    data = _request(endpoint, params)
    if not data or "standings" not in data:
        return []

    standings = []
    for table in data["standings"]:
        if table.get("type") == "TOTAL":
            for item in table.get("table", []):
                standings.append({
                    'position': item.get("position", 0),
                    'team': item.get("team", {}).get("shortName", ""),
                    'team_id': str(item.get("team", {}).get("id", "")),
                    'team_crest': item.get("team", {}).get("crest", ""),
                    'played': item.get("playedGames", 0),
                    'won': item.get("won", 0),
                    'drawn': item.get("draw", 0),
                    'lost': item.get("lost", 0),
                    'goals_for': item.get("goalsFor", 0),
                    'goals_against': item.get("goalsAgainst", 0),
                    'goal_difference': item.get("goalDifference", 0),
                    'points': item.get("points", 0),
                    'form': item.get("form", ""),
                    'league': league,
                    'season': season,
                    'source': 'football-data.org'
                })

    print(f"[football-data.org] 积分榜 {league}: {len(standings)}队")
    return standings


def get_scorers(league: str, season: str = None, limit: int = 100) -> List[Dict]:
    """获取射手榜

    Returns:
        [{"player_id", "player_name", "team", "goals", "assists",
          "played_matches", "source"}]
    """
    code = _resolve_code(league)
    endpoint = f"competitions/{code}/scorers"
    params = {"limit": limit}
    if season:
        params["season"] = int(season[:4])

    data = _request(endpoint, params)
    if not data:
        return []

    scorers = []
    for item in data.get("scorers", []):
        scorers.append({
            'player_id': str(item.get("player", {}).get("id", "")),
            'player_name': item.get("player", {}).get("name", ""),
            'team': item.get("team", {}).get("shortName", ""),
            'team_id': str(item.get("team", {}).get("id", "")),
            'goals': item.get("goals", 0),
            'assists': item.get("assists", 0),
            'played_matches': item.get("playedMatches", 0),
            'source': 'football-data.org'
        })

    print(f"[football-data.org] 射手榜 {league}: {len(scorers)}人")
    return scorers


def get_team_detail(team_id: str) -> Dict:
    """获取球队详情 (含阵容)

    Returns:
        {"team_id", "name", "short_name", "tla", "country", "founded",
         "venue", "crest", "squad", "source"}
    """
    data = _request(f"teams/{team_id}")
    if not data:
        return {}

    result = {
        'team_id': str(data.get("id", "")),
        'name': data.get("name", ""),
        'short_name': data.get("shortName", ""),
        'tla': data.get("tla", ""),
        'country': data.get("area", {}).get("name", ""),
        'founded': data.get("founded"),
        'venue': data.get("venue", ""),
        'crest': data.get("crest", ""),
        'source': 'football-data.org'
    }

    # 阵容
    squad = []
    for p in data.get("squad", []):
        squad.append({
            'player_id': str(p.get("id", "")),
            'name': p.get("name", ""),
            'position': p.get("position", ""),
            'nationality': p.get("nationality", ""),
            'date_of_birth': p.get("dateOfBirth", "")[:10] if p.get("dateOfBirth") else None,
        })
    result['squad'] = squad

    return result


def get_match_detail(match_id: str) -> Dict:
    """获取比赛详情

    Returns:
        比赛详细信息
    """
    data = _request(f"matches/{match_id}")
    return data if data else {}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.football_data_org.get_matches today")
        print("  python -m fetchers.football_data_org.get_matches standings premier_league")
        print("  python -m fetchers.football_data_org.get_matches scorers PL")
        sys.exit(0)

    cmd = sys.argv[1]
    league = sys.argv[2] if len(sys.argv) > 2 else "premier_league"

    if cmd == "today":
        for m in get_today_matches():
            print(f"  {m['home_team']} {m['home_score']}-{m['away_score']} {m['away_team']} [{m['league']}]")
    elif cmd == "standings":
        for s in get_standings(league):
            print(f"  {s['position']}. {s['team']} {s['points']}pts ({s['form']})")
    elif cmd == "scorers":
        for s in get_scorers(league)[:10]:
            print(f"  {s['player_name']} ({s['team']}) {s['goals']}球")