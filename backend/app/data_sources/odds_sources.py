"""
赔率数据源实现
使用 RapidAPI 的 Odds Feed / Bet365 / Football Betting Odds API
"""

import aiohttp
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import BaseDataSource, DataSourceConfig, DataCategory
from .base import MatchData


class OddsFeedAPI(BaseDataSource):
    """Odds Feed API - RapidAPI"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url
        self.api_key = config.api_key
        self.rapidapi_host = "odds-feed.p.rapidapi.com"

    async def _request(self, endpoint: str, params: Dict = None) -> Any:
        """发送API请求"""
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.rapidapi_host
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"API error: {response.status}")

    async def get_odds(self, match_id: str = None, league: str = None) -> List[Dict]:
        """获取赔率数据"""
        params = {}
        if match_id:
            params["match_id"] = match_id
        if league:
            params["league"] = league

        try:
            data = await self._request("v1/odds", params)
            odds_list = []

            for item in data.get("data", []):
                odds = {
                    "match_id": item.get("id"),
                    "sport": item.get("sport"),
                    "league": item.get("league"),
                    "home_team": item.get("home_team"),
                    "away_team": item.get("away_team"),
                    "match_time": item.get("match_time"),
                    "odds_home": item.get("odds", {}).get("home"),
                    "odds_draw": item.get("odds", {}).get("draw"),
                    "odds_away": item.get("odds", {}).get("away"),
                    "source": "odds_feed"
                }
                odds_list.append(odds)

            return odds_list
        except Exception as e:
            print(f"OddsFeed error: {e}")
            return []

    async def get_livescores(self, leagues: List[str] = None, date: str = None) -> List[MatchData]:
        """获取实时比分"""
        return []

    async def get_fixtures(self, league: str, season: str = None, team: str = None,
                          from_date: str = None, to_date: str = None) -> List[MatchData]:
        return []

    async def get_standings(self, league: str, season: str = None) -> List:
        return []

    async def get_matches(self, league: str, season: str = None, team: str = None,
                         limit: int = None) -> List[MatchData]:
        return []

    async def get_team(self, team_id: str) -> Optional:
        return None

    async def get_players(self, team: str = None, league: str = None,
                         season: str = None) -> List:
        return []

    async def get_scorers(self, league: str, season: str = None,
                         limit: int = None) -> List:
        return []


class Bet365API(BaseDataSource):
    """Bet365 API - RapidAPI"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url
        self.api_key = config.api_key
        self.rapidapi_host = "bet365-api.p.rapidapi.com"

    async def _request(self, endpoint: str, params: Dict = None) -> Any:
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.rapidapi_host
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"API error: {response.status}")

    async def get_odds(self, event_id: str = None) -> List[Dict]:
        """获取Bet365赔率"""
        params = {}
        if event_id:
            params["event_id"] = event_id

        try:
            data = await self._request("v1/odds", params)
            return data.get("data", [])
        except Exception as e:
            print(f"Bet365 error: {e}")
            return []

    async def get_livescores(self, leagues: List[str] = None, date: str = None) -> List[MatchData]:
        return []

    async def get_fixtures(self, league: str, season: str = None, team: str = None,
                          from_date: str = None, to_date: str = None) -> List[MatchData]:
        return []

    async def get_standings(self, league: str, season: str = None) -> List:
        return []

    async def get_matches(self, league: str, season: str = None, team: str = None,
                         limit: int = None) -> List[MatchData]:
        return []

    async def get_team(self, team_id: str) -> Optional:
        return None

    async def get_players(self, team: str = None, league: str = None,
                         season: str = None) -> List:
        return []

    async def get_scorers(self, league: str, season: str = None,
                         limit: int = None) -> List:
        return []


class FootballBettingOddsAPI(BaseDataSource):
    """Football Betting Odds API - RapidAPI"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url
        self.api_key = config.api_key
        self.rapidapi_host = "football-betting-odds.p.rapidapi.com"

    async def _request(self, endpoint: str, params: Dict = None) -> Any:
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.rapidapi_host
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"API error: {response.status}")

    async def get_odds(self, match_id: str = None) -> List[Dict]:
        """获取足球赔率"""
        params = {}
        if match_id:
            params["match_id"] = match_id

        try:
            data = await self._request("v1/odds", params)
            return data.get("data", [])
        except Exception as e:
            print(f"FootballBettingOdds error: {e}")
            return []

    async def get_livescores(self, leagues: List[str] = None, date: str = None) -> List[MatchData]:
        return []

    async def get_fixtures(self, league: str, season: str = None, team: str = None,
                          from_date: str = None, to_date: str = None) -> List[MatchData]:
        return []

    async def get_standings(self, league: str, season: str = None) -> List:
        return []

    async def get_matches(self, league: str, season: str = None, team: str = None,
                         limit: int = None) -> List[MatchData]:
        return []

    async def get_team(self, team_id: str) -> Optional:
        return None

    async def get_players(self, team: str = None, league: str = None,
                         season: str = None) -> List:
        return []

    async def get_scorers(self, league: str, season: str = None,
                         limit: int = None) -> List:
        return []
