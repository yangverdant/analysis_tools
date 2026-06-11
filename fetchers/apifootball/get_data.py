"""
API-Football数据获取

功能:
1. 获取实时比分/赛程/历史比赛
2. 获取赔率数据 (多家公司欧赔/大小球)
3. 获取积分榜
4. 获取比赛统计/阵容/事件
5. 获取预测数据

数据来源: apiv3.apifootball.com (需API Key)

使用示例:
    from fetchers.apifootball.get_data import get_livescores, get_standings

    # 实时比分
    matches = get_livescores()

    # 积分榜
    standings = get_standings("premier_league")

    # 某日赛程
    fixtures = get_fixtures(from_date="2026-01-01", to_date="2026-01-31")

    # 比赛赔率
    odds = get_match_odds(match_id="12345")
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.apifootball.config import (
    API_KEY, BASE_URL, REQUEST_TIMEOUT, REQUEST_INTERVAL,
    LEAGUE_IDS, MATCH_STATUS_MAP
)
from fetchers.common.league_names import normalize_league_name
from fetchers.common.date_utils import normalize_date

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


def _request(action: str, params: Dict = None) -> Optional[List]:
    """发送API请求"""
    query = {"action": action, "APIkey": API_KEY}
    if params:
        query.update(params)

    session = _get_session()
    try:
        resp = session.get(BASE_URL, params=query, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and data.get('errors'):
                logger.error(f"API错误: {data['errors']}")
            return data
    except Exception as e:
        logger.error(f"请求失败 [{action}]: {e}")
        print(f"[错误] API-Football请求失败: {str(e)[:60]}")
    return None


def _parse_int(v) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except:
        return None


def _parse_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except:
        return None


def _map_status(status: str) -> str:
    if "'" in status:
        return "live"
    try:
        int(status)
        return "live"
    except:
        pass
    return MATCH_STATUS_MAP.get(status, status.lower() if status else "scheduled")


# ==================== 核心接口 ====================

def get_livescores() -> List[Dict]:
    """获取实时比分

    Returns:
        [{"match_id", "home_team", "away_team", "home_score", "away_score",
          "date", "time", "status", "league", "round", "source"}]
    """
    data = _request("get_events", {"match_live": 1})
    if not data or not isinstance(data, list):
        return []

    matches = []
    for item in data:
        matches.append({
            'match_id': str(item.get("match_id", "")),
            'home_team': item.get("match_hometeam_name", ""),
            'away_team': item.get("match_awayteam_name", ""),
            'home_score': _parse_int(item.get("match_hometeam_score")),
            'away_score': _parse_int(item.get("match_awayteam_score")),
            'date': item.get("match_date", ""),
            'time': item.get("match_time", ""),
            'status': _map_status(item.get("match_status", "")),
            'league': item.get("league_name", ""),
            'league_standard': normalize_league_name(item.get("league_id")),
            'league_id': item.get("league_id"),
            'round': _parse_int(item.get("match_round")),
            'source': 'apifootball'
        })

    print(f"[apifootball] 实时比分: {len(matches)}场")
    return matches


def get_fixtures(league: str = None, from_date: str = None, to_date: str = None) -> List[Dict]:
    """获取赛程

    Args:
        league: 联赛名称 (如 "premier_league") 或 league_id
        from_date: 起始日期 (YYYY-MM-DD)
        to_date: 截止日期 (YYYY-MM-DD)

    Returns:
        [{"match_id", "home_team", "away_team", "home_score", "away_score",
          "home_score_ht", "away_score_ht", "date", "time", "status",
          "league", "league_id", "round", "venue", "referee", "source"}]
    """
    params = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    if league:
        league_id = LEAGUE_IDS.get(league, league)
        params["league_id"] = league_id

    data = _request("get_events", params)
    if not data or not isinstance(data, list):
        return []

    matches = []
    for item in data:
        matches.append({
            'match_id': str(item.get("match_id", "")),
            'home_team': item.get("match_hometeam_name", ""),
            'home_team_id': item.get("match_hometeam_id"),
            'away_team': item.get("match_awayteam_name", ""),
            'away_team_id': item.get("match_awayteam_id"),
            'home_score': _parse_int(item.get("match_hometeam_score")),
            'away_score': _parse_int(item.get("match_awayteam_score")),
            'home_score_ht': _parse_int(item.get("match_hometeam_halftime_score")),
            'away_score_ht': _parse_int(item.get("match_awayteam_halftime_score")),
            'date': item.get("match_date", ""),
            'time': item.get("match_time", ""),
            'status': _map_status(item.get("match_status", "")),
            'league': item.get("league_name", ""),
            'league_standard': normalize_league_name(item.get("league_id")),
            'league_id': item.get("league_id"),
            'round': _parse_int(item.get("match_round")),
            'venue': item.get("match_stadium", ""),
            'referee': item.get("match_referee", ""),
            'source': 'apifootball'
        })

    print(f"[apifootball] 赛程: {len(matches)}场")
    return matches


def get_match_detail(match_id: str) -> Dict:
    """获取单场比赛完整数据 (进球/换人/红黄牌/阵容/统计)

    Returns:
        {"match_id", "date", "time", "status", "home_team", "away_team",
         "home_score", "away_score", "league", "venue", "referee",
         "goalscorer", "substitutions", "cards", "lineup", "statistics", "source"}
    """
    data = _request("get_events", {"match_id": match_id})
    if not data or not isinstance(data, list) or len(data) == 0:
        return {}

    item = data[0]
    result = {
        'match_id': item.get("match_id"),
        'date': item.get("match_date"),
        'time': item.get("match_time"),
        'status': item.get("match_status"),
        'home_team': item.get("match_hometeam_name"),
        'home_team_id': item.get("match_hometeam_id"),
        'away_team': item.get("match_awayteam_name"),
        'away_team_id': item.get("match_awayteam_id"),
        'home_score': _parse_int(item.get("match_hometeam_score")),
        'away_score': _parse_int(item.get("match_awayteam_score")),
        'home_score_ht': _parse_int(item.get("match_hometeam_halftime_score")),
        'away_score_ht': _parse_int(item.get("match_awayteam_halftime_score")),
        'league': item.get("league_name"),
        'league_id': item.get("league_id"),
        'round': item.get("match_round"),
        'venue': item.get("match_stadium"),
        'referee': item.get("match_referee"),
        'goalscorer': item.get("goalscorer", []),
        'substitutions': item.get("substitutions", {}),
        'cards': item.get("cards", []),
        'lineup': item.get("lineup", {}),
        'statistics': item.get("statistics", []),
        'statistics_1half': item.get("statistics_1half", []),
        'source': 'apifootball'
    }
    return result


def get_standings(league: str, season: str = None) -> List[Dict]:
    """获取积分榜

    Args:
        league: 联赛名称或league_id
        season: 起始年份 (如 "2026")

    Returns:
        [{"position", "team", "team_id", "played", "won", "drawn", "lost",
          "goals_for", "goals_against", "goal_difference", "points",
          "league", "source"}]
    """
    league_id = LEAGUE_IDS.get(league, league)
    params = {"league_id": league_id}
    if season:
        params["season"] = season

    data = _request("get_standings", params)
    if not data or not isinstance(data, list):
        return []

    standings = []
    for item in data:
        gf = _parse_int(item.get("overall_league_GF"))
        ga = _parse_int(item.get("overall_league_GA"))
        gd = gf - ga if gf is not None and ga is not None else None
        standings.append({
            'position': _parse_int(item.get("overall_league_position")),
            'team': item.get("team_name", ""),
            'team_id': item.get("team_id"),
            'played': _parse_int(item.get("overall_league_payed")),
            'won': _parse_int(item.get("overall_league_W")),
            'drawn': _parse_int(item.get("overall_league_D")),
            'lost': _parse_int(item.get("overall_league_L")),
            'goals_for': gf,
            'goals_against': ga,
            'goal_difference': gd,
            'points': _parse_int(item.get("overall_league_PTS")),
            'league': item.get("league_name", ""),
            'source': 'apifootball'
        })

    print(f"[apifootball] 积分榜 {league}: {len(standings)}队")
    return standings


def get_match_odds(match_id: str = None, from_date: str = None, to_date: str = None) -> List[Dict]:
    """获取赔率数据

    Args:
        match_id: 比赛ID
        from_date: 起始日期
        to_date: 截止日期

    Returns:
        [{"match_id", "bookmaker", "updated", "home_win", "draw", "away_win",
          "over_2_5", "under_2_5", "btts_yes", "btts_no", "source"}]
    """
    params = {}
    if match_id:
        params["match_id"] = match_id
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    data = _request("get_odds", params)
    if not data or not isinstance(data, list):
        return []

    odds_list = []
    for item in data:
        odds_list.append({
            'match_id': item.get("match_id"),
            'bookmaker': item.get("odd_bookmakers"),
            'updated': item.get("odd_date"),
            'home_win': _parse_float(item.get("odd_1")),
            'draw': _parse_float(item.get("odd_x")),
            'away_win': _parse_float(item.get("odd_2")),
            'home_win_or_draw': _parse_float(item.get("odd_1x")),
            'home_win_or_away': _parse_float(item.get("odd_12")),
            'draw_or_away': _parse_float(item.get("odd_x2")),
            'over_2_5': _parse_float(item.get("o+2.5")),
            'under_2_5': _parse_float(item.get("u+2.5")),
            'btts_yes': _parse_float(item.get("bts_yes")),
            'btts_no': _parse_float(item.get("bts_no")),
            'source': 'apifootball'
        })

    print(f"[apifootball] 赔率: {len(odds_list)}条")
    return odds_list


def get_predictions(match_id: str) -> Dict:
    """获取比赛预测

    Returns:
        {"match_id", "home_team", "away_team", "home_win_prob", "draw_prob",
         "away_win_prob", "over_2_5_prob", "under_2_5_prob", "btts_yes_prob",
         "btts_no_prob", "source"}
    """
    data = _request("get_predictions", {"match_id": match_id})
    if not data:
        return {}

    # API returns list
    if isinstance(data, list):
        if not data:
            return {}
        item = data[0]
    elif isinstance(data, dict):
        item = data
    else:
        return {}

    return {
        'match_id': item.get("match_id"),
        'home_team': item.get("match_hometeam_name", ""),
        'away_team': item.get("match_awayteam_name", ""),
        'date': item.get("match_date", ""),
        'league': item.get("league_name", ""),
        'league_standard': normalize_league_name(item.get("league_id")),
        'league_id': item.get("league_id"),
        'home_win_prob': _parse_float(item.get("prob_HW")),
        'draw_prob': _parse_float(item.get("prob_D")),
        'away_win_prob': _parse_float(item.get("prob_AW")),
        'over_2_5_prob': _parse_float(item.get("prob_O")),
        'under_2_5_prob': _parse_float(item.get("prob_U")),
        'btts_yes_prob': _parse_float(item.get("prob_bts")),
        'btts_no_prob': _parse_float(item.get("prob_ots")),
        'source': 'apifootball'
    }


def get_teams(league: str = None, team_id: str = None) -> List[Dict]:
    """获取球队信息

    Returns:
        [{"team_id", "name", "country", "founded", "badge", "venue", "source"}]
    """
    params = {}
    if league:
        params["league_id"] = LEAGUE_IDS.get(league, league)
    if team_id:
        params["team_id"] = team_id

    data = _request("get_teams", params)
    if not data or not isinstance(data, list):
        return []

    teams = []
    for item in data:
        teams.append({
            'team_id': str(item.get("team_key", "")),
            'name': item.get("team_name", ""),
            'country': item.get("team_country", ""),
            'founded': item.get("team_founded"),
            'badge': item.get("team_badge"),
            'venue': item.get("venue", {}).get("venue_name") if item.get("venue") else None,
            'source': 'apifootball'
        })

    print(f"[apifootball] 球队: {len(teams)}条")
    return teams


def get_topscorers(league: str) -> List[Dict]:
    """获取射手榜

    Returns:
        [{"player_id", "player_name", "team_name", "goals", "assists", "matches_played"}]
    """
    league_id = LEAGUE_IDS.get(league, league)
    data = _request("get_topscorers", {"league_id": league_id})
    if not data or not isinstance(data, list):
        return []

    scorers = []
    for item in data:
        scorers.append({
            'player_id': item.get("player_id"),
            'player_name': item.get("player_name"),
            'team_name': item.get("team_name"),
            'goals': item.get("goals"),
            'assists': item.get("assists"),
            'matches_played': item.get("matches_played"),
            'source': 'apifootball'
        })
    return scorers


def get_h2h(team1_id: str, team2_id: str) -> List[Dict]:
    """获取交锋记录

    Returns:
        比赛列表
    """
    data = _request("get_H2H", {"firstTeamId": team1_id, "secondTeamId": team2_id})
    if not data or not isinstance(data, list):
        return []

    matches = []
    for item in data:
        matches.append({
            'match_id': str(item.get("match_id", "")),
            'home_team': item.get("match_hometeam_name", ""),
            'away_team': item.get("match_awayteam_name", ""),
            'home_score': _parse_int(item.get("match_hometeam_score")),
            'away_score': _parse_int(item.get("match_awayteam_score")),
            'date': item.get("match_date", ""),
            'league': item.get("league_name", ""),
            'source': 'apifootball'
        })
    return matches


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.apifootball.get_data livescores")
        print("  python -m fetchers.apifootball.get_data standings premier_league")
        print("  python -m fetchers.apifootball.get_data fixtures --from 2026-01-01 --to 2026-01-31")
        print("  python -m fetchers.apifootball.get_data odds --match_id 12345")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "livescores":
        for m in get_livescores():
            print(f"  {m['home_team']} {m['home_score']}-{m['away_score']} {m['away_team']} [{m['league']}]")

    elif cmd == "standings":
        league = sys.argv[2] if len(sys.argv) > 2 else "premier_league"
        for s in get_standings(league):
            print(f"  {s['position']}. {s['team']} {s['points']}pts ({s['won']}W {s['drawn']}D {s['lost']}L)")

    elif cmd == "fixtures":
        matches = get_fixtures()
        for m in matches[:20]:
            print(f"  {m['date']} {m['home_team']} vs {m['away_team']} [{m['league']}]")

    elif cmd == "odds":
        odds = get_match_odds()
        for o in odds[:10]:
            print(f"  {o['bookmaker']}: H{o['home_win']} D{o['draw']} A{o['away_win']}")