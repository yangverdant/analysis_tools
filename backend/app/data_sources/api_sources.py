"""
API类数据源实现
包含: Sportmonks, football-data.org, TheSportsDB, ScoreBat, 365Scores, OpenLigaDB
"""

import time
import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

from .base import (
    BaseDataSource, DataSourceConfig, DataSourceType, DataCategory,
    MatchData, StandingData, TeamData, PlayerData
)


class SportmonksAPI(BaseDataSource):
    """Sportmonks API - 功能最全的足球API"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.api_token = config.api_key or "4iBqABzPSz3JX65i166agPqQiliD4f79vD7o2NrJX1OmMBt7wHJ2ttvxdQoq"
        self.base_url = config.base_url or "https://api.sportmonks.com/v3/football"
        self.session = requests.Session()
        self.session.trust_env = False

    def _request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """发送API请求"""
        self._rate_limit()
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        params["api_token"] = self.api_token

        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Sportmonks API error: {e}")
        return None

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分"""
        endpoint = "/livescores/inplay"
        params = {"include": "participants;scores;periods;events;league.country;round"}

        data = self._request(endpoint, params)
        if not data:
            return []

        matches = []
        for item in data.get("data", []):
            match = self._parse_match(item)
            if match:
                matches.append(match)
        return matches

    async def get_fixtures(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[MatchData]:
        """获取赛程"""
        if from_date and to_date:
            endpoint = f"/fixtures/between/{from_date}/{to_date}"
        else:
            endpoint = "/fixtures"

        params = {"include": "participants;scores;league.country;round"}
        if league:
            params["filters"] = f"leagueIds:{self._get_league_id(league)}"

        data = self._request(endpoint, params)
        if not data:
            return []

        return [self._parse_match(item) for item in data.get("data", []) if self._parse_match(item)]

    async def get_standings(
        self,
        league: str,
        season: Optional[str] = None
    ) -> List[StandingData]:
        """获取积分榜"""
        season_id = self._get_season_id(league, season)
        endpoint = f"/standings/seasons/{season_id}"
        params = {"include": "participant;details;form"}

        data = self._request(endpoint, params)
        if not data:
            return []

        standings = []
        for item in data.get("data", []):
            for detail in item.get("details", []):
                standings.append(StandingData(
                    position=item.get("position", 0),
                    team=item.get("participant", {}).get("name", ""),
                    team_id=str(item.get("participant_id", "")),
                    played=detail.get("played", 0),
                    won=detail.get("won", 0),
                    drawn=detail.get("draw", 0),
                    lost=detail.get("lost", 0),
                    goals_for=detail.get("goals_scored", 0),
                    goals_against=detail.get("goals_against", 0),
                    goal_difference=detail.get("goal_difference", 0),
                    points=detail.get("points", 0),
                    form=item.get("form", ""),
                    league=league,
                    season=season,
                    source="sportmonks"
                ))
        return standings

    async def get_matches(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MatchData]:
        """获取历史比赛"""
        return await self.get_fixtures(league, season, team)

    async def get_team(self, team_id: str) -> Optional[TeamData]:
        """获取球队信息"""
        endpoint = f"/teams/{team_id}"
        params = {"include": "country;venue"}

        data = self._request(endpoint, params)
        if not data or not data.get("data"):
            return None

        item = data["data"]
        return TeamData(
            team_id=str(item.get("id", "")),
            name=item.get("name", ""),
            short_name=item.get("short_code", ""),
            country=item.get("country", {}).get("name", ""),
            founded=item.get("founded"),
            venue=item.get("venue", {}).get("name", ""),
            capacity=item.get("venue", {}).get("capacity"),
            logo_url=item.get("image_path", ""),
            source="sportmonks"
        )

    async def get_players(
        self,
        team: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None
    ) -> List[PlayerData]:
        """获取球员信息"""
        if not team:
            return []

        endpoint = f"/teams/{team}/squad"
        params = {"include": "player.country;player.position"}

        data = self._request(endpoint, params)
        if not data:
            return []

        players = []
        for item in data.get("data", []):
            player = item.get("player", {})
            players.append(PlayerData(
                player_id=str(player.get("id", "")),
                name=player.get("name", ""),
                team=team,
                position=player.get("position", {}).get("name", ""),
                nationality=player.get("country", {}).get("name", ""),
                date_of_birth=player.get("date_of_birth", ""),
                height=player.get("height"),
                weight=player.get("weight"),
                source="sportmonks"
            ))
        return players

    async def get_scorers(
        self,
        league: str,
        season: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[PlayerData]:
        """获取射手榜"""
        # Sportmonks需要通过赛季统计获取
        return []

    def _parse_match(self, item: Dict) -> Optional[MatchData]:
        """解析比赛数据"""
        if not item:
            return None

        participants = item.get("participants", [])
        home_team = away_team = ""
        home_score = away_score = 0

        for p in participants:
            if p.get("meta", {}).get("location") == "home":
                home_team = p.get("name", "")
                home_score = p.get("meta", {}).get("winner", False)
            else:
                away_team = p.get("name", "")

        scores = item.get("scores", [])
        for s in scores:
            if s.get("type") == "FT":
                home_score = s.get("home_score", 0)
                away_score = s.get("away_score", 0)

        return MatchData(
            match_id=str(item.get("id", "")),
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
            date=item.get("starting_at", "")[:10],
            time=item.get("starting_at", "")[11:16] if item.get("starting_at") else None,
            status=item.get("state_id"),
            league=item.get("league", {}).get("name", ""),
            round_num=item.get("round", {}).get("name"),
            source="sportmonks"
        )

    def _get_league_id(self, league: str) -> int:
        """获取联赛ID"""
        league_map = {
            "premier_league": 8, "la_liga": 564, "bundesliga": 35,
            "serie_a": 384, "ligue_1": 301, "championship": 48,
            "eredivisie": 64, "primeira_liga": 2, "champions_league": 7,
            "europa_league": 679, "conference_league": 832,
        }
        return league_map.get(league, 0)

    def _get_season_id(self, league: str, season: str) -> int:
        """获取赛季ID - 需要实际查询"""
        return 0


class FootballDataOrgAPI(BaseDataSource):
    """football-data.org API - 免费足球数据API"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.api_token = config.api_key or "944e431594bf477fa85d24fa04d9c2fe"
        self.base_url = config.base_url or "https://api.football-data.org/v4"
        self.session = requests.Session()
        self.session.headers.update({"X-Auth-Token": self.api_token})
        self.session.trust_env = False

        self.competition_codes = {
            "premier_league": "PL", "la_liga": "PD", "bundesliga": "BL1",
            "serie_a": "SA", "ligue_1": "FL1", "eredivisie": "DED",
            "primeira_liga": "PPL", "champions_league": "CL",
            "championship": "ELC", "world_cup": "WC", "euro": "EC",
        }

    def _request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """发送API请求"""
        self._rate_limit()
        url = f"{self.base_url}/{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"football-data.org API error: {e}")
        return None

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分"""
        data = self._request("matches")
        if not data:
            return []

        matches = []
        for item in data.get("matches", []):
            match = self._parse_match(item)
            if match:
                matches.append(match)
        return matches

    async def get_fixtures(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[MatchData]:
        """获取赛程"""
        code = self.competition_codes.get(league, league.upper())
        endpoint = f"competitions/{code}/matches"
        params = {}
        if season:
            params["season"] = int(season[:4])

        data = self._request(endpoint, params)
        if not data:
            return []

        return [self._parse_match(item) for item in data.get("matches", []) if self._parse_match(item)]

    async def get_standings(
        self,
        league: str,
        season: Optional[str] = None
    ) -> List[StandingData]:
        """获取积分榜"""
        code = self.competition_codes.get(league, league.upper())
        endpoint = f"competitions/{code}/standings"
        params = {}
        if season:
            params["season"] = int(season[:4])

        data = self._request(endpoint, params)
        if not data or "standings" not in data:
            return []

        standings = []
        for table in data["standings"]:
            if table.get("type") == "TOTAL":
                for item in table.get("table", []):
                    standings.append(StandingData(
                        position=item.get("position", 0),
                        team=item.get("team", {}).get("shortName", ""),
                        team_id=str(item.get("team", {}).get("id", "")),
                        played=item.get("playedGames", 0),
                        won=item.get("won", 0),
                        drawn=item.get("draw", 0),
                        lost=item.get("lost", 0),
                        goals_for=item.get("goalsFor", 0),
                        goals_against=item.get("goalsAgainst", 0),
                        goal_difference=item.get("goalDifference", 0),
                        points=item.get("points", 0),
                        form=item.get("form", ""),
                        league=league,
                        season=season,
                        source="football-data.org"
                    ))
        return standings

    async def get_matches(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MatchData]:
        """获取历史比赛"""
        return await self.get_fixtures(league, season, team)

    async def get_team(self, team_id: str) -> Optional[TeamData]:
        """获取球队信息"""
        data = self._request(f"teams/{team_id}")
        if not data:
            return None

        return TeamData(
            team_id=str(data.get("id", "")),
            name=data.get("name", ""),
            short_name=data.get("shortName", ""),
            tla=data.get("tla", ""),
            country=data.get("area", {}).get("name", ""),
            founded=data.get("founded"),
            venue=data.get("venue", ""),
            logo_url=data.get("crest", ""),
            source="football-data.org"
        )

    async def get_players(
        self,
        team: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None
    ) -> List[PlayerData]:
        """获取球员信息"""
        if not team:
            return []

        data = self._request(f"teams/{team}")
        if not data:
            return []

        players = []
        for p in data.get("squad", []):
            players.append(PlayerData(
                player_id=str(p.get("id", "")),
                name=p.get("name", ""),
                team=team,
                position=p.get("position", ""),
                nationality=p.get("nationality", ""),
                date_of_birth=p.get("dateOfBirth", "")[:10] if p.get("dateOfBirth") else None,
                source="football-data.org"
            ))
        return players

    async def get_scorers(
        self,
        league: str,
        season: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[PlayerData]:
        """获取射手榜"""
        code = self.competition_codes.get(league, league.upper())
        endpoint = f"competitions/{code}/scorers"
        params = {"limit": limit or 100}
        if season:
            params["season"] = int(season[:4])

        data = self._request(endpoint, params)
        if not data:
            return []

        players = []
        for i, item in enumerate(data.get("scorers", []), 1):
            players.append(PlayerData(
                player_id=str(item.get("player", {}).get("id", "")),
                name=item.get("player", {}).get("name", ""),
                team=item.get("team", {}).get("shortName", ""),
                goals=item.get("goals", 0),
                assists=item.get("assists", 0),
                appearances=item.get("playedMatches", 0),
                source="football-data.org"
            ))
        return players

    def _parse_match(self, item: Dict) -> Optional[MatchData]:
        """解析比赛数据"""
        if not item:
            return None

        score = item.get("score", {})
        ft = score.get("fullTime", {})
        ht = score.get("halfTime", {})

        return MatchData(
            match_id=str(item.get("id", "")),
            home_team=item.get("homeTeam", {}).get("shortName", ""),
            away_team=item.get("awayTeam", {}).get("shortName", ""),
            home_score=ft.get("home"),
            away_score=ft.get("away"),
            home_score_ht=ht.get("home"),
            away_score_ht=ht.get("away"),
            date=item.get("utcDate", "")[:10],
            time=item.get("utcDate", "")[11:16] if item.get("utcDate") else None,
            status=item.get("status", ""),
            league=item.get("competition", {}).get("name", ""),
            round_num=item.get("matchday"),
            source="football-data.org"
        )


class TheSportsDBAPI(BaseDataSource):
    """TheSportsDB API - 免费体育数据API"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://www.thesportsdb.com/api/v1/json/3"
        self.session = requests.Session()
        self.session.trust_env = False

    def _request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """发送API请求"""
        self._rate_limit()
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"TheSportsDB API error: {e}")
        return None

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分"""
        if date:
            date_str = date.replace("-", "")
        else:
            date_str = datetime.now().strftime("%Y%m%d")

        data = self._request(f"/eventsday.php", {"d": date_str, "s": "Soccer"})
        if not data:
            return []

        matches = []
        for item in data.get("events", []):
            if item:
                matches.append(self._parse_match(item))
        return [m for m in matches if m]

    async def get_fixtures(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[MatchData]:
        """获取赛程"""
        return []

    async def get_standings(
        self,
        league: str,
        season: Optional[str] = None
    ) -> List[StandingData]:
        """获取积分榜"""
        return []

    async def get_matches(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MatchData]:
        """获取历史比赛"""
        return []

    async def get_team(self, team_id: str) -> Optional[TeamData]:
        """获取球队信息"""
        data = self._request(f"/lookupteam.php", {"id": team_id})
        if not data or not data.get("teams"):
            return None

        item = data["teams"][0]
        return TeamData(
            team_id=str(item.get("idTeam", "")),
            name=item.get("strTeam", ""),
            short_name=item.get("strTeamShort", ""),
            country=item.get("strCountry", ""),
            founded=int(item.get("intFormedYear", 0)) if item.get("intFormedYear") else None,
            venue=item.get("strStadium", ""),
            capacity=int(item.get("intStadiumCapacity", 0)) if item.get("intStadiumCapacity") else None,
            logo_url=item.get("strTeamBadge", ""),
            source="thesportsdb"
        )

    async def get_players(
        self,
        team: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None
    ) -> List[PlayerData]:
        """获取球员信息"""
        return []

    async def get_scorers(
        self,
        league: str,
        season: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[PlayerData]:
        """获取射手榜"""
        return []

    def _parse_match(self, item: Dict) -> Optional[MatchData]:
        """解析比赛数据"""
        if not item:
            return None

        return MatchData(
            match_id=str(item.get("idEvent", "")),
            home_team=item.get("strHomeTeam", ""),
            away_team=item.get("strAwayTeam", ""),
            home_score=int(item.get("intHomeScore", 0)) if item.get("intHomeScore") else None,
            away_score=int(item.get("intAwayScore", 0)) if item.get("intAwayScore") else None,
            date=item.get("dateEvent", ""),
            time=item.get("strTime", "")[:5] if item.get("strTime") else None,
            status=item.get("strStatus", ""),
            league=item.get("strLeague", ""),
            round_num=int(item.get("intRound", 0)) if item.get("intRound") else None,
            source="thesportsdb"
        )


class ScoreBatAPI(BaseDataSource):
    """ScoreBat API - 免费足球视频API，可解析比分"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://www.scorebat.com/video-api/v3"
        self.session = requests.Session()
        self.session.trust_env = False

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分"""
        self._rate_limit()
        try:
            response = self.session.get(self.base_url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                matches = []
                for item in data.get("response", []):
                    match = self._parse_match(item)
                    if match:
                        matches.append(match)
                return matches
        except Exception as e:
            print(f"ScoreBat API error: {e}")
        return []

    async def get_fixtures(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[MatchData]:
        return []

    async def get_standings(
        self,
        league: str,
        season: Optional[str] = None
    ) -> List[StandingData]:
        return []

    async def get_matches(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MatchData]:
        return await self.get_livescores()

    async def get_team(self, team_id: str) -> Optional[TeamData]:
        return None

    async def get_players(
        self,
        team: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None
    ) -> List[PlayerData]:
        return []

    async def get_scorers(
        self,
        league: str,
        season: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[PlayerData]:
        return []

    def _parse_match(self, item: Dict) -> Optional[MatchData]:
        """解析比赛数据 - 从标题解析比分"""
        if not item:
            return None

        title = item.get("title", "")
        # 格式: "Team1 2-1 Team2"
        match = re.search(r'(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+)', title)
        if match:
            return MatchData(
                home_team=match.group(1).strip(),
                away_team=match.group(4).strip(),
                home_score=int(match.group(2)),
                away_score=int(match.group(3)),
                date=item.get("date", "")[:10],
                league=item.get("competition", ""),
                source="scorebat"
            )
        return None


class Scores365API(BaseDataSource):
    """365Scores API - 实时比分数据"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://webws.365scores.com/web"
        self.session = requests.Session()
        self.session.trust_env = False

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分"""
        self._rate_limit()
        try:
            params = {
                "langId": "1",
                "timezoneName": "Asia/Shanghai",
                "userCountryId": "1",
                "appTypeId": "1"
            }
            response = self.session.get(f"{self.base_url}/games/fixtures", params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                matches = []
                for item in data.get("games", []):
                    matches.append(self._parse_match(item))
                return [m for m in matches if m]
        except Exception as e:
            print(f"365Scores API error: {e}")
        return []

    async def get_fixtures(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[MatchData]:
        return []

    async def get_standings(
        self,
        league: str,
        season: Optional[str] = None
    ) -> List[StandingData]:
        return []

    async def get_matches(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MatchData]:
        return await self.get_livescores()

    async def get_team(self, team_id: str) -> Optional[TeamData]:
        return None

    async def get_players(
        self,
        team: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None
    ) -> List[PlayerData]:
        return []

    async def get_scorers(
        self,
        league: str,
        season: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[PlayerData]:
        return []

    def _parse_match(self, item: Dict) -> Optional[MatchData]:
        """解析比赛数据"""
        if not item:
            return None

        home = item.get("homeCompetitor", {})
        away = item.get("awayCompetitor", {})

        return MatchData(
            match_id=str(item.get("gameId", "")),
            home_team=home.get("name", ""),
            away_team=away.get("name", ""),
            home_score=item.get("homeScore"),
            away_score=item.get("awayScore"),
            date=item.get("startTime", "")[:10] if item.get("startTime") else None,
            time=item.get("startTime", "")[11:16] if item.get("startTime") else None,
            status=item.get("gameStatus", ""),
            league=item.get("competition", {}).get("name", ""),
            source="365scores"
        )


class OpenLigaDBAPI(BaseDataSource):
    """OpenLigaDB API - 德国足球数据API"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://api.openligadb.de"
        self.session = requests.Session()
        self.session.trust_env = False

        self.league_codes = {
            "bundesliga": "bl1",
            "bundesliga_2": "bl2",
            "premier_league": "pl",
        }

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分"""
        matches = []
        for league in leagues or ["bundesliga"]:
            code = self.league_codes.get(league, league)
            data = await self._get_matches(code)
            matches.extend(data)
        return matches

    async def _get_matches(self, league_code: str) -> List[MatchData]:
        """获取联赛比赛"""
        self._rate_limit()
        try:
            url = f"{self.base_url}/getmatchdata/{league_code}"
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                matches = []
                for item in data:
                    matches.append(self._parse_match(item))
                return [m for m in matches if m]
        except Exception as e:
            print(f"OpenLigaDB API error: {e}")
        return []

    async def get_fixtures(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[MatchData]:
        return await self.get_livescores([league])

    async def get_standings(
        self,
        league: str,
        season: Optional[str] = None
    ) -> List[StandingData]:
        return []

    async def get_matches(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MatchData]:
        return await self.get_livescores([league])

    async def get_team(self, team_id: str) -> Optional[TeamData]:
        return None

    async def get_players(
        self,
        team: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None
    ) -> List[PlayerData]:
        return []

    async def get_scorers(
        self,
        league: str,
        season: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[PlayerData]:
        return []

    def _parse_match(self, item: Dict) -> Optional[MatchData]:
        """解析比赛数据"""
        if not item:
            return None

        results = item.get("matchResults", [])
        ft_score = results[-1] if results else {}

        return MatchData(
            match_id=str(item.get("matchID", "")),
            home_team=item.get("team1", {}).get("teamName", ""),
            away_team=item.get("team2", {}).get("teamName", ""),
            home_score=ft_score.get("pointsTeam1"),
            away_score=ft_score.get("pointsTeam2"),
            date=item.get("matchDateTime", "")[:10],
            time=item.get("matchDateTime", "")[11:16] if item.get("matchDateTime") else None,
            status=item.get("matchIsFinished"),
            source="openligadb"
        )
