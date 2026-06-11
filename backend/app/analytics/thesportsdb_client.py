"""
TheSportsDB API 集成模块

功能:
1. 球队信息查询
2. 球员信息查询
3. 比赛赛程查询
4. 联赛积分榜
5. 实时比分
6. 球员荣誉/里程碑/合同
7. 比赛阵容/时间线/统计

API文档: https://www.thesportsdb.com/api.php
"""

import requests
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
import time


@dataclass
class TeamInfo:
    """球队信息"""
    team_id: str
    name: str
    short_name: str
    alternate_name: str
    country: str
    stadium: str
    stadium_capacity: int
    website: str
    founded: int
    badge_url: str
    jersey_url: str
    logo_url: str


@dataclass
class PlayerInfo:
    """球员信息"""
    player_id: str
    name: str
    nationality: str
    position: str
    height: str
    weight: str
    birth_date: str
    team: str
    thumb_url: str


@dataclass
class EventInfo:
    """比赛信息"""
    event_id: str
    title: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    date: str
    time: str
    league: str
    season: str
    stadium: str
    status: str


class TheSportsDBClient:
    """TheSportsDB API客户端"""

    # V1 API基础URL（免费用户）
    BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"

    # 热门联赛ID
    LEAGUES = {
        'premier_league': {'id': '4328', 'name': '英超', 'name_en': 'English Premier League'},
        'la_liga': {'id': '4335', 'name': '西甲', 'name_en': 'Spanish La Liga'},
        'bundesliga': {'id': '4331', 'name': '德甲', 'name_en': 'German Bundesliga'},
        'serie_a': {'id': '4332', 'name': '意甲', 'name_en': 'Italian Serie A'},
        'ligue_1': {'id': '4334', 'name': '法甲', 'name_en': 'French Ligue 1'},
        'champions_league': {'id': '4329', 'name': '欧冠', 'name_en': 'UEFA Champions League'},
        'europa_league': {'id': '4330', 'name': '欧联', 'name_en': 'UEFA Europa League'},
        'world_cup': {'id': '4429', 'name': '世界杯', 'name_en': 'FIFA World Cup'},
        'euro': {'id': '4422', 'name': '欧洲杯', 'name_en': 'UEFA Euro'},
    }

    def __init__(self, db_path: str = None):
        self.db_path = db_path

        # 禁用代理
        os.environ['HTTP_PROXY'] = ''
        os.environ['HTTPS_PROXY'] = ''
        os.environ['http_proxy'] = ''
        os.environ['https_proxy'] = ''

        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # 缓存
        self.cache = {}
        self.cache_duration = 300  # 5分钟缓存

    def get_connection(self):
        if self.db_path:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        return None

    # ==================== 搜索功能 ====================

    def search_team(self, team_name: str) -> List[Dict]:
        """
        搜索球队

        Args:
            team_name: 球队名称

        Returns:
            球队列表
        """
        try:
            url = f"{self.BASE_URL}/searchteams.php"
            params = {'t': team_name}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                teams = data.get('teams', [])

                return [
                    {
                        'team_id': t.get('idTeam'),
                        'name': t.get('strTeam'),
                        'short_name': t.get('strTeamShort'),
                        'alternate_name': t.get('strAlternate'),
                        'country': t.get('strCountry'),
                        'stadium': t.get('strStadium'),
                        'stadium_capacity': t.get('intStadiumCapacity'),
                        'website': t.get('strWebsite'),
                        'founded': t.get('intFormedYear'),
                        'badge': t.get('strBadge'),
                        'jersey': t.get('strJersey'),
                        'logo': t.get('strLogo'),
                        'description': t.get('strDescriptionEN', '')[:500]
                    } for t in teams
                ]
        except Exception as e:
            print(f"搜索球队失败: {e}")

        return []

    def search_player(self, player_name: str) -> List[Dict]:
        """
        搜索球员

        Args:
            player_name: 球员名称

        Returns:
            球员列表
        """
        try:
            url = f"{self.BASE_URL}/searchplayers.php"
            params = {'p': player_name}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                players = data.get('player', [])

                return [
                    {
                        'player_id': p.get('idPlayer'),
                        'name': p.get('strPlayer'),
                        'nationality': p.get('strNationality'),
                        'position': p.get('strPosition'),
                        'height': p.get('strHeight'),
                        'weight': p.get('strWeight'),
                        'birth_date': p.get('dateBorn'),
                        'team': p.get('strTeam'),
                        'thumb': p.get('strThumb'),
                        'description': p.get('strDescriptionEN', '')[:500]
                    } for p in players
                ]
        except Exception as e:
            print(f"搜索球员失败: {e}")

        return []

    def search_event(self, event_name: str, season: str = None, date: str = None) -> List[Dict]:
        """
        搜索比赛

        Args:
            event_name: 比赛名称
            season: 赛季（可选）
            date: 日期（可选）

        Returns:
            比赛列表
        """
        try:
            url = f"{self.BASE_URL}/searchevents.php"
            params = {'e': event_name}
            if season:
                params['s'] = season
            if date:
                params['d'] = date

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                events = data.get('event', [])

                return [self._parse_event(e) for e in events]
        except Exception as e:
            print(f"搜索比赛失败: {e}")

        return []

    # ==================== 查询功能 ====================

    def get_team_by_id(self, team_id: str) -> Optional[Dict]:
        """
        通过ID获取球队详情

        Args:
            team_id: 球队ID

        Returns:
            球队信息
        """
        try:
            url = f"{self.BASE_URL}/lookupteam.php"
            params = {'id': team_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                teams = data.get('teams', [])

                if teams:
                    t = teams[0]
                    return {
                        'team_id': t.get('idTeam'),
                        'name': t.get('strTeam'),
                        'short_name': t.get('strTeamShort'),
                        'alternate_name': t.get('strAlternate'),
                        'country': t.get('strCountry'),
                        'stadium': t.get('strStadium'),
                        'stadium_capacity': t.get('intStadiumCapacity'),
                        'website': t.get('strWebsite'),
                        'facebook': t.get('strFacebook'),
                        'twitter': t.get('strTwitter'),
                        'instagram': t.get('strInstagram'),
                        'founded': t.get('intFormedYear'),
                        'badge': t.get('strBadge'),
                        'jersey': t.get('strJersey'),
                        'logo': t.get('strLogo'),
                        'description': t.get('strDescriptionEN', '')
                    }
        except Exception as e:
            print(f"获取球队详情失败: {e}")

        return None

    def get_player_by_id(self, player_id: str) -> Optional[Dict]:
        """
        通过ID获取球员详情

        Args:
            player_id: 球员ID

        Returns:
            球员信息
        """
        try:
            url = f"{self.BASE_URL}/lookupplayer.php"
            params = {'id': player_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                players = data.get('players', [])

                if players:
                    p = players[0]
                    return {
                        'player_id': p.get('idPlayer'),
                        'name': p.get('strPlayer'),
                        'nationality': p.get('strNationality'),
                        'position': p.get('strPosition'),
                        'height': p.get('strHeight'),
                        'weight': p.get('strWeight'),
                        'birth_date': p.get('dateBorn'),
                        'birth_place': p.get('strBirthLocation'),
                        'team': p.get('strTeam'),
                        'thumb': p.get('strThumb'),
                        'cutout': p.get('strCutout'),
                        'description': p.get('strDescriptionEN', '')
                    }
        except Exception as e:
            print(f"获取球员详情失败: {e}")

        return None

    def get_event_by_id(self, event_id: str) -> Optional[Dict]:
        """
        通过ID获取比赛详情

        Args:
            event_id: 比赛ID

        Returns:
            比赛信息
        """
        try:
            url = f"{self.BASE_URL}/lookupevent.php"
            params = {'id': event_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                events = data.get('events', [])

                if events:
                    return self._parse_event(events[0])
        except Exception as e:
            print(f"获取比赛详情失败: {e}")

        return None

    # ==================== 球员扩展信息 ====================

    def get_player_honours(self, player_id: str) -> List[Dict]:
        """
        获取球员荣誉

        Args:
            player_id: 球员ID

        Returns:
            荣誉列表
        """
        try:
            url = f"{self.BASE_URL}/lookuphonours.php"
            params = {'id': player_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                honours = data.get('honours', [])

                return [
                    {
                        'honour_id': h.get('idHonour'),
                        'player_id': h.get('idPlayer'),
                        'player_name': h.get('strPlayer'),
                        'honour': h.get('strHonour'),
                        'team': h.get('strTeam'),
                        'season': h.get('strSeason')
                    } for h in honours
                ]
        except Exception as e:
            print(f"获取球员荣誉失败: {e}")

        return []

    def get_player_former_teams(self, player_id: str) -> List[Dict]:
        """
        获取球员前球队

        Args:
            player_id: 球员ID

        Returns:
            前球队列表
        """
        try:
            url = f"{self.BASE_URL}/lookupformerteams.php"
            params = {'id': player_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                teams = data.get('formerteams', [])

                return [
                    {
                        'player_id': t.get('idPlayer'),
                        'player_name': t.get('strPlayer'),
                        'team': t.get('strFormerTeam'),
                        'start_date': t.get('strJoined'),
                        'end_date': t.get('strDeparted')
                    } for t in teams
                ]
        except Exception as e:
            print(f"获取球员前球队失败: {e}")

        return []

    def get_player_milestones(self, player_id: str) -> List[Dict]:
        """
        获取球员里程碑

        Args:
            player_id: 球员ID

        Returns:
            里程碑列表
        """
        try:
            url = f"{self.BASE_URL}/lookupmilestones.php"
            params = {'id': player_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                milestones = data.get('milestones', [])

                return [
                    {
                        'milestone_id': m.get('idMilestone'),
                        'player_id': m.get('idPlayer'),
                        'player_name': m.get('strPlayer'),
                        'milestone': m.get('strMilestone'),
                        'team': m.get('strTeam'),
                        'season': m.get('strSeason')
                    } for m in milestones
                ]
        except Exception as e:
            print(f"获取球员里程碑失败: {e}")

        return []

    def get_player_contracts(self, player_id: str) -> List[Dict]:
        """
        获取球员合同

        Args:
            player_id: 球员ID

        Returns:
            合同列表
        """
        try:
            url = f"{self.BASE_URL}/lookupcontracts.php"
            params = {'id': player_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                contracts = data.get('contracts', [])

                return [
                    {
                        'contract_id': c.get('idContract'),
                        'player_id': c.get('idPlayer'),
                        'player_name': c.get('strPlayer'),
                        'team': c.get('strTeam'),
                        'start_date': c.get('strYearStart'),
                        'end_date': c.get('strYearEnd'),
                        'wage': c.get('strWage')
                    } for c in contracts
                ]
        except Exception as e:
            print(f"获取球员合同失败: {e}")

        return []

    # ==================== 比赛扩展信息 ====================

    def get_event_lineup(self, event_id: str) -> Dict:
        """
        获取比赛阵容

        Args:
            event_id: 比赛ID

        Returns:
            阵容信息
        """
        try:
            url = f"{self.BASE_URL}/lookuplineup.php"
            params = {'id': event_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                lineup = data.get('lineup', [])

                home_players = []
                away_players = []

                for p in lineup:
                    player_info = {
                        'player_id': p.get('idPlayer'),
                        'player_name': p.get('strPlayer'),
                        'position': p.get('strPosition'),
                        'formation_position': p.get('strFormationPosition'),
                        'number': p.get('intNumber'),
                        'is_substitute': p.get('strSubstitute') == 'True'
                    }

                    if p.get('strHome') == 'True':
                        home_players.append(player_info)
                    else:
                        away_players.append(player_info)

                return {
                    'event_id': event_id,
                    'home_team': home_players,
                    'away_team': away_players,
                    'home_formation': lineup[0].get('strHomeFormation') if lineup else None,
                    'away_formation': lineup[0].get('strAwayFormation') if lineup else None
                }
        except Exception as e:
            print(f"获取比赛阵容失败: {e}")

        return {}

    def get_event_timeline(self, event_id: str) -> List[Dict]:
        """
        获取比赛时间线

        Args:
            event_id: 比赛ID

        Returns:
            时间线事件列表
        """
        try:
            url = f"{self.BASE_URL}/lookuptimeline.php"
            params = {'id': event_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                timeline = data.get('timeline', [])

                return [
                    {
                        'timeline_id': t.get('idTimeline'),
                        'event_id': t.get('idEvent'),
                        'type': t.get('strTimeline'),
                        'detail': t.get('strTimelineDetail'),
                        'player': t.get('strPlayer'),
                        'player_id': t.get('idPlayer'),
                        'team': t.get('strTeam'),
                        'minute': t.get('intTime'),
                        'home_score': t.get('strHomeScore'),
                        'away_score': t.get('strAwayScore')
                    } for t in timeline
                ]
        except Exception as e:
            print(f"获取比赛时间线失败: {e}")

        return []

    def get_event_statistics(self, event_id: str) -> List[Dict]:
        """
        获取比赛统计

        Args:
            event_id: 比赛ID

        Returns:
            统计数据列表
        """
        try:
            url = f"{self.BASE_URL}/lookupeventstats.php"
            params = {'id': event_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                stats = data.get('eventstats', [])

                return [
                    {
                        'stat_id': s.get('idEventStats'),
                        'event_id': s.get('idEvent'),
                        'type': s.get('strStat'),
                        'home_value': s.get('intHome'),
                        'away_value': s.get('intAway')
                    } for s in stats
                ]
        except Exception as e:
            print(f"获取比赛统计失败: {e}")

        return []

    def get_event_tv(self, event_id: str) -> List[Dict]:
        """
        获取比赛电视转播

        Args:
            event_id: 比赛ID

        Returns:
            电视频道列表
        """
        try:
            url = f"{self.BASE_URL}/lookuptv.php"
            params = {'id': event_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                tv = data.get('tv', [])

                return [
                    {
                        'channel': t.get('strChannel'),
                        'country': t.get('strCountry'),
                        'sport': t.get('strSport')
                    } for t in tv
                ]
        except Exception as e:
            print(f"获取比赛电视转播失败: {e}")

        return []

    # ==================== 赛程功能 ====================

    def get_team_next_events(self, team_id: str, limit: int = 10) -> List[Dict]:
        """
        获取球队即将开始的比赛

        Args:
            team_id: 球队ID
            limit: 返回数量

        Returns:
            比赛列表
        """
        try:
            url = f"{self.BASE_URL}/eventsnext.php"
            params = {'id': team_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                events = data.get('events', [])

                return [self._parse_event(e) for e in events[:limit]]
        except Exception as e:
            print(f"获取球队即将开始的比赛失败: {e}")

        return []

    def get_team_previous_events(self, team_id: str, limit: int = 10) -> List[Dict]:
        """
        获取球队最近比赛

        Args:
            team_id: 球队ID
            limit: 返回数量

        Returns:
            比赛列表
        """
        try:
            url = f"{self.BASE_URL}/eventslast.php"
            params = {'id': team_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                events = data.get('results', [])

                return [self._parse_event(e) for e in events[:limit]]
        except Exception as e:
            print(f"获取球队最近比赛失败: {e}")

        return []

    def get_league_next_events(self, league_id: str, limit: int = 10) -> List[Dict]:
        """
        获取联赛即将开始的比赛

        Args:
            league_id: 联赛ID
            limit: 返回数量

        Returns:
            比赛列表
        """
        try:
            url = f"{self.BASE_URL}/eventsnextleague.php"
            params = {'id': league_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                events = data.get('events', [])

                return [self._parse_event(e) for e in events[:limit]]
        except Exception as e:
            print(f"获取联赛即将开始的比赛失败: {e}")

        return []

    def get_league_previous_events(self, league_id: str, limit: int = 10) -> List[Dict]:
        """
        获取联赛最近比赛

        Args:
            league_id: 联赛ID
            limit: 返回数量

        Returns:
            比赛列表
        """
        try:
            url = f"{self.BASE_URL}/eventspastleague.php"
            params = {'id': league_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                events = data.get('events', [])

                return [self._parse_event(e) for e in events[:limit]]
        except Exception as e:
            print(f"获取联赛最近比赛失败: {e}")

        return []

    def get_events_by_day(self, date: str, sport: str = 'Soccer', league_id: str = None) -> List[Dict]:
        """
        获取某天的比赛

        Args:
            date: 日期 (YYYY-MM-DD)
            sport: 运动类型
            league_id: 联赛ID（可选）

        Returns:
            比赛列表
        """
        try:
            url = f"{self.BASE_URL}/eventsday.php"
            params = {'d': date, 's': sport}
            if league_id:
                params['l'] = league_id

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                events = data.get('events', [])

                return [self._parse_event(e) for e in events]
        except Exception as e:
            print(f"获取某天比赛失败: {e}")

        return []

    def get_season_events(self, league_id: str, season: str) -> List[Dict]:
        """
        获取赛季所有比赛

        Args:
            league_id: 联赛ID
            season: 赛季 (如 "2023-2024")

        Returns:
            比赛列表
        """
        try:
            url = f"{self.BASE_URL}/eventsseason.php"
            params = {'id': league_id, 's': season}

            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 200 and response.text:
                data = response.json()
                events = data.get('events', [])

                return [self._parse_event(e) for e in events]
        except Exception as e:
            print(f"获取赛季比赛失败: {e}")

        return []

    # ==================== 列表功能 ====================

    def get_all_sports(self) -> List[Dict]:
        """获取所有运动项目"""
        try:
            url = f"{self.BASE_URL}/all_sports.php"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                sports = data.get('sports', [])

                return [
                    {
                        'sport_id': s.get('idSport'),
                        'name': s.get('strSport'),
                        'format': s.get('strFormat'),
                        'thumb': s.get('strSportThumb')
                    } for s in sports
                ]
        except Exception as e:
            print(f"获取所有运动项目失败: {e}")

        return []

    def get_all_countries(self) -> List[Dict]:
        """获取所有国家"""
        try:
            url = f"{self.BASE_URL}/all_countries.php"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                countries = data.get('countries', [])

                return [
                    {
                        'country_id': c.get('idCountry'),
                        'name': c.get('name_en'),
                        'name_cn': c.get('name_cn'),
                        'flag': c.get('flag')
                    } for c in countries
                ]
        except Exception as e:
            print(f"获取所有国家失败: {e}")

        return []

    def get_all_leagues(self) -> List[Dict]:
        """获取所有联赛"""
        try:
            url = f"{self.BASE_URL}/all_leagues.php"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                leagues = data.get('leagues', [])

                return [
                    {
                        'league_id': l.get('idLeague'),
                        'name': l.get('strLeague'),
                        'alternate_name': l.get('strLeagueAlternate'),
                        'sport': l.get('strSport'),
                        'badge': l.get('strBadge')
                    } for l in leagues
                ]
        except Exception as e:
            print(f"获取所有联赛失败: {e}")

        return []

    def get_league_teams(self, league_id: str) -> List[Dict]:
        """
        获取联赛所有球队

        Args:
            league_id: 联赛ID

        Returns:
            球队列表
        """
        try:
            url = f"{self.BASE_URL}/lookup_all_teams.php"
            params = {'id': league_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                teams = data.get('teams', [])

                return [
                    {
                        'team_id': t.get('idTeam'),
                        'name': t.get('strTeam'),
                        'short_name': t.get('strTeamShort'),
                        'country': t.get('strCountry'),
                        'stadium': t.get('strStadium'),
                        'badge': t.get('strBadge')
                    } for t in teams
                ]
        except Exception as e:
            print(f"获取联赛球队失败: {e}")

        return []

    def get_league_seasons(self, league_id: str) -> List[Dict]:
        """
        获取联赛所有赛季

        Args:
            league_id: 联赛ID

        Returns:
            赛季列表
        """
        try:
            url = f"{self.BASE_URL}/search_all_seasons.php"
            params = {'id': league_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                seasons = data.get('seasons', [])

                return [
                    {
                        'season_id': s.get('idSeason'),
                        'name': s.get('strSeason'),
                        'league_id': s.get('idLeague')
                    } for s in seasons
                ]
        except Exception as e:
            print(f"获取联赛赛季失败: {e}")

        return []

    def get_team_players(self, team_id: str) -> List[Dict]:
        """
        获取球队所有球员

        Args:
            team_id: 球队ID

        Returns:
            球员列表
        """
        try:
            url = f"{self.BASE_URL}/lookup_all_players.php"
            params = {'id': team_id}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                players = data.get('player', [])

                return [
                    {
                        'player_id': p.get('idPlayer'),
                        'name': p.get('strPlayer'),
                        'nationality': p.get('strNationality'),
                        'position': p.get('strPosition'),
                        'height': p.get('strHeight'),
                        'weight': p.get('strWeight'),
                        'birth_date': p.get('dateBorn'),
                        'thumb': p.get('strThumb')
                    } for p in players
                ]
        except Exception as e:
            print(f"获取球队球员失败: {e}")

        return []

    # ==================== 积分榜 ====================

    def get_league_table(self, league_id: str, season: str = None) -> List[Dict]:
        """
        获取联赛积分榜

        Args:
            league_id: 联赛ID
            season: 赛季（可选）

        Returns:
            积分榜
        """
        try:
            url = f"{self.BASE_URL}/lookuptable.php"
            params = {'l': league_id}
            if season:
                params['s'] = season

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200 and response.text:
                data = response.json()
                table = data.get('table', [])

                return [
                    {
                        'rank': t.get('intRank'),
                        'team_id': t.get('idTeam'),
                        'team_name': t.get('strTeam'),
                        'played': t.get('intPlayed'),
                        'won': t.get('intWin'),
                        'draw': t.get('intDraw'),
                        'lost': t.get('intLoss'),
                        'goals_for': t.get('intGoalsFor'),
                        'goals_against': t.get('intGoalsAgainst'),
                        'goal_diff': t.get('intGoalDifference'),
                        'points': t.get('intPoints'),
                        'form': t.get('strForm'),
                        'badge': t.get('strBadge')
                    } for t in table
                ]
        except Exception as e:
            print(f"获取联赛积分榜失败: {e}")

        return []

    # ==================== 辅助方法 ====================

    def _parse_event(self, e: Dict) -> Dict:
        """解析比赛数据"""
        return {
            'event_id': e.get('idEvent'),
            'title': e.get('strEvent'),
            'home_team': e.get('strHomeTeam'),
            'away_team': e.get('strAwayTeam'),
            'home_team_id': e.get('idHomeTeam'),
            'away_team_id': e.get('idAwayTeam'),
            'home_score': e.get('intHomeScore'),
            'away_score': e.get('intAwayScore'),
            'home_score_ht': e.get('intHomeScoreHT'),
            'away_score_ht': e.get('intAwayScoreHT'),
            'date': e.get('dateEvent'),
            'time': e.get('strTime'),
            'league': e.get('strLeague'),
            'league_id': e.get('idLeague'),
            'season': e.get('strSeason'),
            'round': e.get('intRound'),
            'stadium': e.get('strVenue'),
            'stadium_id': e.get('idVenue'),
            'country': e.get('strCountry'),
            'status': e.get('strStatus'),
            'postponed': e.get('strPostponed') == 'True',
            'locked': e.get('strLocked') == 'True',
            'thumb': e.get('strThumb'),
            'video': e.get('strVideo')
        }


def main():
    """测试TheSportsDB客户端"""
    client = TheSportsDBClient()

    print("TheSportsDB API 测试")
    print("=" * 60)

    # 测试搜索球队
    print("\n[搜索球队: Arsenal]")
    teams = client.search_team('Arsenal')
    if teams:
        print(f"找到 {len(teams)} 个球队")
        print(f"  第一个: {teams[0]['name']} (ID: {teams[0]['team_id']})")
        print(f"  体育场: {teams[0]['stadium']}")
        print(f"  成立年份: {teams[0]['founded']}")

    # 测试搜索球员
    print("\n[搜索球员: Harry Kane]")
    players = client.search_player('Harry Kane')
    if players:
        print(f"找到 {len(players)} 个球员")
        print(f"  第一个: {players[0]['name']} ({players[0]['position']})")
        print(f"  国籍: {players[0]['nationality']}")

    # 测试联赛积分榜
    print("\n[英超积分榜]")
    table = client.get_league_table('4328')
    if table:
        print(f"排名前5:")
        for t in table[:5]:
            print(f"  {t['rank']}. {t['team_name']} - {t['points']}分 ({t['won']}胜{t['draw']}平{t['lost']}负)")

    # 测试球队球员
    if teams:
        print(f"\n[{teams[0]['name']} 球员]")
        team_players = client.get_team_players(teams[0]['team_id'])
        print(f"共 {len(team_players)} 名球员")
        for p in team_players[:5]:
            print(f"  {p['name']} - {p['position']}")

    # 测试比赛阵容
    print("\n[最近英超比赛]")
    events = client.get_league_previous_events('4328', 1)
    if events:
        event = events[0]
        print(f"比赛: {event['title']}")
        print(f"比分: {event['home_score']} - {event['away_score']}")
        print(f"日期: {event['date']}")

        # 获取阵容
        lineup = client.get_event_lineup(event['event_id'])
        if lineup:
            print(f"阵型: {lineup.get('home_formation')} vs {lineup.get('away_formation')}")
            print(f"主队球员: {len(lineup.get('home_team', []))}人")

        # 获取时间线
        timeline = client.get_event_timeline(event['event_id'])
        if timeline:
            print(f"事件数: {len(timeline)}")
            for t in timeline[:3]:
                print(f"  {t['minute']}' {t['type']}: {t['player']}")


if __name__ == "__main__":
    main()
