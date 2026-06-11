"""
API Football数据源实现
文档: https://apiv3.apifootball.com/api-docs
"""

import aiohttp
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import BaseDataSource, DataSourceConfig, DataCategory
from .base import MatchData, StandingData, TeamData, PlayerData


class APIFootballSource(BaseDataSource):
    """API Football数据源"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url
        self.api_key = config.api_key

    async def _request(self, action: str, params: Dict = None) -> Any:
        """发送API请求"""
        url = f"{self.base_url}/"
        query_params = {
            "action": action,
            "APIkey": self.api_key
        }
        if params:
            query_params.update(params)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=query_params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"API error: {response.status}")

    async def get_livescores(self, leagues: List[str] = None) -> List[MatchData]:
        """获取实时比分"""
        params = {"match_live": 1}
        if leagues:
            # API Football uses league_id, need to map
            pass

        try:
            data = await self._request("get_events", params)
            matches = []

            for item in data if isinstance(data, list) else []:
                match = MatchData(
                    match_id=str(item.get("match_id", "")),
                    home_team=item.get("match_hometeam_name", ""),
                    away_team=item.get("match_awayteam_name", ""),
                    home_score=self._parse_int(item.get("match_hometeam_score")),
                    away_score=self._parse_int(item.get("match_awayteam_score")),
                    date=item.get("match_date", ""),
                    time=item.get("match_time", ""),
                    status=item.get("match_status", ""),
                    league=item.get("league_name", ""),
                    round_num=self._parse_int(item.get("match_round")),
                    source="apifootball"
                )
                matches.append(match)

            return matches
        except Exception as e:
            print(f"APIFootball livescores error: {e}")
            return []

    async def get_fixtures(
        self,
        league_id: str = None,
        season: str = None,
        from_date: str = None,
        to_date: str = None
    ) -> List[MatchData]:
        """获取赛程"""
        params = {}

        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if league_id:
            params["league_id"] = league_id

        try:
            data = await self._request("get_events", params)
            matches = []

            for item in data if isinstance(data, list) else []:
                match = MatchData(
                    match_id=str(item.get("match_id", "")),
                    home_team=item.get("match_hometeam_name", ""),
                    away_team=item.get("match_awayteam_name", ""),
                    home_score=self._parse_int(item.get("match_hometeam_score")),
                    away_score=self._parse_int(item.get("match_awayteam_score")),
                    home_score_ht=self._parse_int(item.get("match_hometeam_halftime_score")),
                    away_score_ht=self._parse_int(item.get("match_awayteam_halftime_score")),
                    date=item.get("match_date", ""),
                    time=item.get("match_time", ""),
                    status=self._map_status(item.get("match_status", "")),
                    league=item.get("league_name", ""),
                    league_id=item.get("league_id"),
                    round_num=self._parse_int(item.get("match_round")),
                    venue=item.get("match_stadium", ""),
                    referee=item.get("match_referee", ""),
                    source="apifootball"
                )
                matches.append(match)

            return matches
        except Exception as e:
            print(f"APIFootball fixtures error: {e}")
            return []

    async def get_odds(
        self,
        match_id: str = None,
        from_date: str = None,
        to_date: str = None
    ) -> List[Dict]:
        """获取赔率数据"""
        params = {}

        if match_id:
            params["match_id"] = match_id
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        try:
            data = await self._request("get_odds", params)
            odds_list = []

            for item in data if isinstance(data, list) else []:
                odds = {
                    "match_id": item.get("match_id"),
                    "bookmaker": item.get("odd_bookmakers"),
                    "updated": item.get("odd_date"),
                    "home_win": self._parse_float(item.get("odd_1")),
                    "draw": self._parse_float(item.get("odd_x")),
                    "away_win": self._parse_float(item.get("odd_2")),
                    "home_win_or_draw": self._parse_float(item.get("odd_1x")),
                    "home_win_or_away": self._parse_float(item.get("odd_12")),
                    "draw_or_away": self._parse_float(item.get("odd_x2")),
                    "over_2_5": self._parse_float(item.get("o+2.5")),
                    "under_2_5": self._parse_float(item.get("u+2.5")),
                    "btts_yes": self._parse_float(item.get("bts_yes")),
                    "btts_no": self._parse_float(item.get("bts_no")),
                }
                odds_list.append(odds)

            return odds_list
        except Exception as e:
            print(f"APIFootball odds error: {e}")
            return []

    async def get_standings(self, league_id: str, season: str = None) -> List[StandingData]:
        """获取积分榜"""
        params = {"league_id": league_id}

        try:
            data = await self._request("get_standings", params)
            standings = []

            for item in data if isinstance(data, list) else []:
                gf = self._parse_int(item.get("overall_league_GF"))
                ga = self._parse_int(item.get("overall_league_GA"))
                gd = gf - ga if gf is not None and ga is not None else None
                standing = StandingData(
                    position=self._parse_int(item.get("overall_league_position")),
                    team=item.get("team_name", ""),
                    team_id=item.get("team_id"),
                    played=self._parse_int(item.get("overall_league_payed")),
                    won=self._parse_int(item.get("overall_league_W")),
                    drawn=self._parse_int(item.get("overall_league_D")),
                    lost=self._parse_int(item.get("overall_league_L")),
                    goals_for=gf,
                    goals_against=ga,
                    goal_difference=gd,
                    points=self._parse_int(item.get("overall_league_PTS")),
                    league=item.get("league_name", ""),
                    source="apifootball"
                )
                standings.append(standing)

            return standings
        except Exception as e:
            print(f"APIFootball standings error: {e}")
            return []

    async def get_teams(self, league_id: str = None, team_id: str = None) -> List[TeamData]:
        """获取球队信息"""
        params = {}
        if league_id:
            params["league_id"] = league_id
        if team_id:
            params["team_id"] = team_id

        try:
            data = await self._request("get_teams", params)
            teams = []

            for item in data if isinstance(data, list) else []:
                team = TeamData(
                    team_id=str(item.get("team_key", "")),
                    name=item.get("team_name", ""),
                    country=item.get("team_country", ""),
                    founded=item.get("team_founded"),
                    badge=item.get("team_badge"),
                    venue=item.get("venue", {}).get("venue_name") if item.get("venue") else None,
                    source="apifootball"
                )
                teams.append(team)

            return teams
        except Exception as e:
            print(f"APIFootball teams error: {e}")
            return []

    async def get_leagues(self, country_id: str = None) -> List[Dict]:
        """获取联赛列表"""
        params = {}
        if country_id:
            params["country_id"] = country_id

        try:
            data = await self._request("get_leagues", params)
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"APIFootball leagues error: {e}")
            return []

    async def get_countries(self) -> List[Dict]:
        """获取国家列表"""
        try:
            data = await self._request("get_countries")
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"APIFootball countries error: {e}")
            return []

    async def get_predictions(self, match_id: str) -> Dict:
        """获取比赛预测"""
        params = {"match_id": match_id}

        try:
            data = await self._request("get_predictions", params)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"APIFootball predictions error: {e}")
            return {}

    async def get_statistics(self, match_id: str) -> Dict:
        """获取比赛统计"""
        params = {"match_id": match_id}

        try:
            data = await self._request("get_statistics", params)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"APIFootball statistics error: {e}")
            return {}

    async def get_match_events(self, match_id: str) -> Dict:
        """获取单场比赛完整事件数据（进球、换人、红黄牌、阵容等）"""
        params = {"match_id": match_id}

        try:
            data = await self._request("get_events", params)
            if isinstance(data, list) and len(data) > 0:
                match_data = data[0]
                return {
                    "match_id": match_data.get("match_id"),
                    "date": match_data.get("match_date"),
                    "time": match_data.get("match_time"),
                    "status": match_data.get("match_status"),
                    "home_team": match_data.get("match_hometeam_name"),
                    "home_team_id": match_data.get("match_hometeam_id"),
                    "away_team": match_data.get("match_awayteam_name"),
                    "away_team_id": match_data.get("match_awayteam_id"),
                    "home_score": self._parse_int(match_data.get("match_hometeam_score")),
                    "away_score": self._parse_int(match_data.get("match_awayteam_score")),
                    "home_score_ht": self._parse_int(match_data.get("match_hometeam_halftime_score")),
                    "away_score_ht": self._parse_int(match_data.get("match_awayteam_halftime_score")),
                    "league": match_data.get("league_name"),
                    "league_id": match_data.get("league_id"),
                    "round": match_data.get("match_round"),
                    "venue": match_data.get("match_stadium"),
                    "referee": match_data.get("match_referee"),
                    "goalscorer": match_data.get("goalscorer", []),
                    "substitutions": match_data.get("substitutions", {}),
                    "cards": match_data.get("cards", []),
                    "lineup": match_data.get("lineup", {}),
                    "statistics": match_data.get("statistics", []),
                    "statistics_1half": match_data.get("statistics_1half", []),
                    "source": "apifootball"
                }
            return {}
        except Exception as e:
            print(f"APIFootball match events error: {e}")
            return {}

    async def get_match_events_by_date(
        self,
        from_date: str,
        to_date: str,
        league_id: str = None
    ) -> List[Dict]:
        """获取日期范围内的比赛事件数据"""
        params = {
            "from": from_date,
            "to": to_date
        }
        if league_id:
            params["league_id"] = league_id

        try:
            data = await self._request("get_events", params)
            events = []

            for match_data in data if isinstance(data, list) else []:
                event = {
                    "match_id": match_data.get("match_id"),
                    "date": match_data.get("match_date"),
                    "time": match_data.get("match_time"),
                    "status": match_data.get("match_status"),
                    "home_team": match_data.get("match_hometeam_name"),
                    "home_team_id": match_data.get("match_hometeam_id"),
                    "away_team": match_data.get("match_awayteam_name"),
                    "away_team_id": match_data.get("match_awayteam_id"),
                    "home_score": self._parse_int(match_data.get("match_hometeam_score")),
                    "away_score": self._parse_int(match_data.get("match_awayteam_score")),
                    "home_score_ht": self._parse_int(match_data.get("match_hometeam_halftime_score")),
                    "away_score_ht": self._parse_int(match_data.get("match_awayteam_halftime_score")),
                    "league": match_data.get("league_name"),
                    "league_id": match_data.get("league_id"),
                    "round": match_data.get("match_round"),
                    "venue": match_data.get("match_stadium"),
                    "referee": match_data.get("match_referee"),
                    "goalscorer": match_data.get("goalscorer", []),
                    "substitutions": match_data.get("substitutions", {}),
                    "cards": match_data.get("cards", []),
                    "lineup": match_data.get("lineup", {}),
                    "statistics": match_data.get("statistics", []),
                    "source": "apifootball"
                }
                events.append(event)

            return events
        except Exception as e:
            print(f"APIFootball events by date error: {e}")
            return []

    async def get_matches(
        self,
        league: str = None,
        season: str = None,
        team: str = None,
        limit: int = None
    ) -> List[MatchData]:
        """获取历史比赛"""
        params = {}

        if league:
            # 需要映射联赛名称到league_id
            params["league_id"] = league
        if team:
            params["team_id"] = team

        try:
            data = await self._request("get_events", params)
            matches = []

            for item in data if isinstance(data, list) else []:
                match = MatchData(
                    match_id=str(item.get("match_id", "")),
                    home_team=item.get("match_hometeam_name", ""),
                    away_team=item.get("match_awayteam_name", ""),
                    home_score=self._parse_int(item.get("match_hometeam_score")),
                    away_score=self._parse_int(item.get("match_awayteam_score")),
                    date=item.get("match_date", ""),
                    time=item.get("match_time", ""),
                    status=self._map_status(item.get("match_status", "")),
                    league=item.get("league_name", ""),
                    source="apifootball"
                )
                matches.append(match)

                if limit and len(matches) >= limit:
                    break

            return matches
        except Exception as e:
            print(f"APIFootball matches error: {e}")
            return []

    async def get_players(
        self,
        team: str = None,
        league: str = None,
        season: str = None
    ) -> List[PlayerData]:
        """获取球员信息"""
        params = {}

        if team:
            params["team_id"] = team

        try:
            data = await self._request("get_players", params)
            players = []

            for item in data if isinstance(data, list) else []:
                player = PlayerData(
                    player_id=str(item.get("player_id", "")),
                    name=item.get("player_name", ""),
                    team=item.get("team_name", ""),
                    position=item.get("player_type", ""),
                    number=self._parse_int(item.get("player_number")),
                    nationality=item.get("player_country", ""),
                    age=self._parse_int(item.get("player_age")),
                    goals=self._parse_int(item.get("player_goals")),
                    assists=self._parse_int(item.get("player_assists")),
                    source="apifootball"
                )
                players.append(player)

            return players
        except Exception as e:
            print(f"APIFootball players error: {e}")
            return []

    async def get_scorers(
        self,
        league: str = None,
        season: str = None,
        limit: int = None
    ) -> List[Dict]:
        """获取射手榜"""
        params = {}

        if league:
            params["league_id"] = league

        try:
            data = await self._request("get_topscorers", params)
            scorers = []

            for item in data if isinstance(data, list) else []:
                scorer = {
                    "player_id": item.get("player_id"),
                    "player_name": item.get("player_name"),
                    "team_name": item.get("team_name"),
                    "goals": item.get("goals"),
                    "assists": item.get("assists"),
                    "matches_played": item.get("matches_played"),
                }
                scorers.append(scorer)

                if limit and len(scorers) >= limit:
                    break

            return scorers
        except Exception as e:
            print(f"APIFootball scorers error: {e}")
            return []

    async def get_team(self, team_id: str) -> Optional[TeamData]:
        """获取单个球队信息"""
        teams = await self.get_teams(team_id=team_id)
        return teams[0] if teams else None

    def _parse_int(self, value) -> Optional[int]:
        """解析整数"""
        if value is None or value == "":
            return None
        try:
            return int(value)
        except:
            return None

    def _parse_float(self, value) -> Optional[float]:
        """解析浮点数"""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except:
            return None

    def _map_status(self, status: str) -> str:
        """映射比赛状态"""
        status_map = {
            "Finished": "finished",
            "Half Time": "halftime",
            "Postponed": "postponed",
            "Cancelled": "cancelled",
            "After ET": "finished_aet",
            "After Pen.": "finished_pen",
        }

        # 检查是否是分钟数（如 "45'", "67'"）
        if status and "'" in status:
            return "live"

        # 检查是否是数字（分钟）
        try:
            int(status)
            return "live"
        except:
            pass

        return status_map.get(status, status.lower() if status else "scheduled")
