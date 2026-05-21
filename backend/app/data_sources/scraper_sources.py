"""
爬虫类数据源实现
包含: FBref, FlashScore, Soccerway, ESPN, Understat, Transfermarkt
"""

import time
import re
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

from .base import (
    BaseDataSource, DataSourceConfig, DataSourceType, DataCategory,
    MatchData, StandingData, TeamData, PlayerData
)


class FBrefScraper(BaseDataSource):
    """FBref爬虫 - 免费足球数据"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://fbref.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.session.trust_env = False

        self.league_urls = {
            "k1_league": "https://fbref.com/en/comps/55/K-League-1-Stats",
            "j1_league": "https://fbref.com/en/comps/51/J1-League-Stats",
            "allsvenskan": "https://fbref.com/en/comps/45/Allsvenskan-Stats",
            "mls": "https://fbref.com/en/comps/74/MLS-Stats",
            "europa_league": "https://fbref.com/en/comps/19/Europa-League-Stats",
            "bundesliga": "https://fbref.com/en/comps/20/Bundesliga-Stats",
            "la_liga": "https://fbref.com/en/comps/12/La-Liga-Stats",
            "serie_a": "https://fbref.com/en/comps/11/Serie-A-Stats",
            "ligue_1": "https://fbref.com/en/comps/13/Ligue-1-Stats",
            "premier_league": "https://fbref.com/en/comps/9/Premier-League-Stats",
        }

    def _fetch(self, url: str) -> Optional[str]:
        """获取页面内容"""
        self._rate_limit()
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"FBref scraper error: {e}")
        return None

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分"""
        return []

    async def get_fixtures(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[MatchData]:
        """获取赛程"""
        url = self.league_urls.get(league)
        if not url:
            return []

        html = self._fetch(url)
        if not html:
            return []

        return self._parse_fixtures(html, league)

    async def get_standings(
        self,
        league: str,
        season: Optional[str] = None
    ) -> List[StandingData]:
        """获取积分榜"""
        url = self.league_urls.get(league)
        if not url:
            return []

        html = self._fetch(url)
        if not html:
            return []

        return self._parse_standings(html, league)

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
        return None

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

    def _parse_fixtures(self, html: str, league: str) -> List[MatchData]:
        """解析赛程"""
        soup = BeautifulSoup(html, 'html.parser')
        matches = []

        tables = soup.find_all('table')
        for table in tables:
            if 'schedule' in table.get('id', '').lower():
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cols = row.find_all('td')
                    if len(cols) >= 6:
                        try:
                            date = cols[0].get_text(strip=True)
                            home = cols[2].get_text(strip=True)
                            away = cols[4].get_text(strip=True)
                            score = cols[3].get_text(strip=True)

                            home_score, away_score = 0, 0
                            if score:
                                parts = score.split('–')
                                if len(parts) == 2:
                                    home_score = int(parts[0].strip())
                                    away_score = int(parts[1].strip())

                            matches.append(MatchData(
                                date=date,
                                home_team=home,
                                away_team=away,
                                home_score=home_score,
                                away_score=away_score,
                                league=league,
                                source="fbref"
                            ))
                        except:
                            continue

        return matches

    def _parse_standings(self, html: str, league: str) -> List[StandingData]:
        """解析积分榜"""
        soup = BeautifulSoup(html, 'html.parser')
        standings = []

        tables = soup.find_all('table')
        for table in tables:
            if 'stats' in table.get('id', '').lower():
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cols = row.find_all(['th', 'td'])
                    if len(cols) >= 10:
                        try:
                            standings.append(StandingData(
                                position=int(cols[0].get_text(strip=True)) if cols[0].get_text(strip=True).isdigit() else 0,
                                team=cols[1].get_text(strip=True),
                                played=int(cols[2].get_text(strip=True)) if cols[2].get_text(strip=True).isdigit() else 0,
                                won=int(cols[3].get_text(strip=True)) if cols[3].get_text(strip=True).isdigit() else 0,
                                drawn=int(cols[4].get_text(strip=True)) if cols[4].get_text(strip=True).isdigit() else 0,
                                lost=int(cols[5].get_text(strip=True)) if cols[5].get_text(strip=True).isdigit() else 0,
                                goals_for=int(cols[6].get_text(strip=True)) if cols[6].get_text(strip=True).isdigit() else 0,
                                goals_against=int(cols[7].get_text(strip=True)) if cols[7].get_text(strip=True).isdigit() else 0,
                                goal_difference=int(cols[8].get_text(strip=True)) if cols[8].get_text(strip=True).lstrip('-').isdigit() else 0,
                                points=int(cols[9].get_text(strip=True)) if cols[9].get_text(strip=True).isdigit() else 0,
                                league=league,
                                source="fbref"
                            ))
                        except:
                            continue

        return standings


class FlashScoreScraper(BaseDataSource):
    """FlashScore爬虫 - 实时比分"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://www.flashscore.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.session.trust_env = False

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分"""
        html = await self._fetch(self.base_url)
        if not html:
            return []

        return self._parse_matches(html)

    async def _fetch(self, url: str) -> Optional[str]:
        """获取页面内容"""
        self._rate_limit()
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"FlashScore scraper error: {e}")
        return None

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

    def _parse_matches(self, html: str) -> List[MatchData]:
        """解析比赛数据"""
        soup = BeautifulSoup(html, 'html.parser')
        matches = []

        match_rows = soup.find_all('div', class_='event__match')
        for row in match_rows:
            try:
                home = row.find('div', class_='event__participant--home')
                away = row.find('div', class_='event__participant--away')
                score_home = row.find('div', class_='event__score--home')
                score_away = row.find('div', class_='event__score--away')

                if home and away and score_home and score_away:
                    sh = score_home.get_text(strip=True)
                    sa = score_away.get_text(strip=True)

                    matches.append(MatchData(
                        home_team=home.get_text(strip=True),
                        away_team=away.get_text(strip=True),
                        home_score=int(sh) if sh.isdigit() else None,
                        away_score=int(sa) if sa.isdigit() else None,
                        source="flashscore"
                    ))
            except:
                continue

        return matches


class SoccerwayScraper(BaseDataSource):
    """Soccerway爬虫 - 足球数据"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://int.soccerway.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.session.trust_env = False

        self.league_urls = {
            "premier_league": "https://int.soccerway.com/national/england/premier-league/",
            "bundesliga": "https://int.soccerway.com/national/germany/bundesliga/",
            "la_liga": "https://int.soccerway.com/national/spain/primera-division/",
            "serie_a": "https://int.soccerway.com/national/italy/serie-a/",
            "ligue_1": "https://int.soccerway.com/national/france/ligue-1/",
        }

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分"""
        matches = []
        for league in leagues or list(self.league_urls.keys()):
            url = self.league_urls.get(league)
            if url:
                html = await self._fetch(url)
                if html:
                    matches.extend(self._parse_matches(html, league))
        return matches

    async def _fetch(self, url: str) -> Optional[str]:
        """获取页面内容"""
        self._rate_limit()
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"Soccerway scraper error: {e}")
        return None

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

    def _parse_matches(self, html: str, league: str) -> List[MatchData]:
        """解析比赛数据"""
        soup = BeautifulSoup(html, 'html.parser')
        matches = []

        rows = soup.find_all('tr', class_='match')
        for row in rows:
            try:
                teams = row.find_all('td', class_='team')
                score_td = row.find('td', class_='score')

                if len(teams) >= 2 and score_td:
                    home = teams[0].get_text(strip=True)
                    away = teams[1].get_text(strip=True)
                    score_text = score_td.get_text(strip=True)

                    scores = re.findall(r'(\d+)\s*-\s*(\d+)', score_text)
                    if scores:
                        matches.append(MatchData(
                            home_team=home,
                            away_team=away,
                            home_score=int(scores[0][0]),
                            away_score=int(scores[0][1]),
                            league=league,
                            source="soccerway"
                        ))
            except:
                continue

        return matches


class ESPNScraper(BaseDataSource):
    """ESPN爬虫 - 足球比分"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://www.espn.com/soccer/scoreboard"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.session.trust_env = False

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分"""
        html = await self._fetch(self.base_url)
        if not html:
            return []

        return self._parse_matches(html)

    async def _fetch(self, url: str) -> Optional[str]:
        """获取页面内容"""
        self._rate_limit()
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"ESPN scraper error: {e}")
        return None

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

    def _parse_matches(self, html: str) -> List[MatchData]:
        """解析比赛数据"""
        soup = BeautifulSoup(html, 'html.parser')
        matches = []

        containers = soup.find_all('div', class_='game-score-container')
        for container in containers:
            try:
                teams = container.find_all('span', class_='team-name')
                scores = container.find_all('span', class_='score')

                if len(teams) >= 2 and len(scores) >= 2:
                    matches.append(MatchData(
                        home_team=teams[0].get_text(strip=True),
                        away_team=teams[1].get_text(strip=True),
                        home_score=int(scores[0].get_text(strip=True)) if scores[0].get_text(strip=True).isdigit() else None,
                        away_score=int(scores[1].get_text(strip=True)) if scores[1].get_text(strip=True).isdigit() else None,
                        source="espn"
                    ))
            except:
                continue

        return matches


class UnderstatScraper(BaseDataSource):
    """Understat爬虫 - xG数据"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://understat.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.session.trust_env = False

        self.league_codes = {
            "premier_league": "EPL",
            "la_liga": "La_liga",
            "bundesliga": "Bundesliga",
            "serie_a": "Serie_A",
            "ligue_1": "Ligue_1",
        }

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取比赛数据（含xG）"""
        matches = []
        for league in leagues or list(self.league_codes.keys()):
            code = self.league_codes.get(league)
            if code:
                year = datetime.now().year
                html = await self._fetch(f"{self.base_url}/league/{code}/{year}")
                if html:
                    matches.extend(self._parse_matches(html, league))
        return matches

    async def _fetch(self, url: str) -> Optional[str]:
        """获取页面内容"""
        self._rate_limit()
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"Understat scraper error: {e}")
        return None

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

    def _parse_matches(self, html: str, league: str) -> List[MatchData]:
        """解析比赛数据 - Understat使用JavaScript渲染"""
        matches = []

        # 查找datesData
        pattern = r"datesData\s*=\s*JSON.parse\('([^']+)'\)"
        match = re.search(pattern, html)

        if match:
            try:
                encoded_data = match.group(1)
                decoded = bytes(encoded_data, 'utf-8').decode('unicode_escape')
                data = json.loads(decoded)

                for item in data:
                    matches.append(MatchData(
                        home_team=item.get('h', {}).get('title', ''),
                        away_team=item.get('a', {}).get('title', ''),
                        home_score=int(item.get('goals', {}).get('h', 0)),
                        away_score=int(item.get('goals', {}).get('a', 0)),
                        date=item.get('datetime', '')[:10],
                        league=league,
                        statistics={
                            'xG_home': float(item.get('xG', {}).get('h', 0)),
                            'xG_away': float(item.get('xG', {}).get('a', 0)),
                        },
                        source="understat"
                    ))
            except Exception as e:
                print(f"Understat parse error: {e}")

        return matches


class TransfermarktScraper(BaseDataSource):
    """Transfermarkt爬虫 - 球员身价数据"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://www.transfermarkt.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.session.trust_env = False

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
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
        return []

    async def get_team(self, team_id: str) -> Optional[TeamData]:
        """获取球队信息"""
        return None

    async def get_players(
        self,
        team: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None
    ) -> List[PlayerData]:
        """获取球员信息（含身价）"""
        # Transfermarkt需要复杂的爬虫逻辑
        # 这里返回空列表，实际使用时需要实现具体逻辑
        return []

    async def get_scorers(
        self,
        league: str,
        season: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[PlayerData]:
        return []
