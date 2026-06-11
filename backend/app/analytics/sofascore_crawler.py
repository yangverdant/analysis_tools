"""
Sofascore实时数据爬虫

功能:
1. 获取实时比分
2. 获取比赛事件（进球、红黄牌、换人）
3. 获取球员评分
4. 获取比赛统计

网站: https://www.sofascore.com
"""

import requests
import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
import time


class SofascoreCrawler:
    """Sofascore数据爬虫"""

    # API端点（Sofascore有公开API）
    BASE_URL = "https://api.sofascore.com/api/v1"

    # 备用URL（网页端）
    WEB_URL = "https://www.sofascore.com"

    # football-data.org API配置
    FOOTBALL_DATA_API_KEY = "944e431594bf477fa85d24fa04d9c2fe"
    FOOTBALL_DATA_URL = "https://api.football-data.org/v4"

    def __init__(self, db_path: str):
        self.db_path = db_path

        # 禁用代理
        os.environ['HTTP_PROXY'] = ''
        os.environ['HTTPS_PROXY'] = ''
        os.environ['http_proxy'] = ''
        os.environ['https_proxy'] = ''

        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://www.sofascore.com',
            'Referer': 'https://www.sofascore.com/'
        })

        # 缓存
        self.cache = {}
        self.cache_duration = 60  # 1分钟缓存

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_live_matches(self) -> List[Dict]:
        """
        获取正在进行的比赛

        Returns:
            实时比赛列表
        """
        cache_key = 'live_matches'

        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_duration:
                return cached['data']

        matches = []

        # 优先使用football-data.org（免费API，稳定性好）
        try:
            matches = self._get_footballdata_live()
            if matches:
                self.cache[cache_key] = {'timestamp': time.time(), 'data': matches}
                return matches
        except Exception as e:
            print(f"football-data.org failed: {e}")

        # 备用：尝试Sofascore API
        try:
            matches = self._get_sofascore_live()
            if matches:
                self.cache[cache_key] = {'timestamp': time.time(), 'data': matches}
                return matches
        except Exception as e:
            print(f"Sofascore API failed: {e}")

        return matches

    def _get_sofascore_live(self) -> List[Dict]:
        """尝试从Sofascore API获取实时数据"""
        try:
            url = "https://api.sofascore.com/api/v1/sport/football/events/live"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
            }
            response = self.session.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])
                matches = []
                for event in events:
                    matches.append({
                        'event_id': event.get('id'),
                        'home_team': event.get('homeTeam', {}).get('name'),
                        'away_team': event.get('awayTeam', {}).get('name'),
                        'home_score': event.get('homeScore', {}).get('current'),
                        'away_score': event.get('awayScore', {}).get('current'),
                        'status': event.get('status', {}).get('code'),
                        'minute': event.get('status', {}).get('time'),
                        'league': event.get('tournament', {}).get('name'),
                        'country': event.get('tournament', {}).get('category', {}).get('name'),
                        'start_time': event.get('startTimestamp')
                    })
                return matches
        except Exception as e:
            print(f"Sofascore error: {e}")
        return []

    def _get_footballdata_live(self) -> List[Dict]:
        """从football-data.org获取实时数据"""
        try:
            url = f"{self.FOOTBALL_DATA_URL}/matches"
            headers = {'X-Auth-Token': self.FOOTBALL_DATA_API_KEY}
            params = {'status': 'IN_PLAY,PAUSED,LIVE'}

            response = self.session.get(url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                matches = []

                for match in data.get('matches', []):
                    matches.append({
                        'event_id': match.get('id'),
                        'home_team': match.get('homeTeam', {}).get('shortName') or match.get('homeTeam', {}).get('name'),
                        'away_team': match.get('awayTeam', {}).get('shortName') or match.get('awayTeam', {}).get('name'),
                        'home_score': match.get('score', {}).get('fullTime', {}).get('home'),
                        'away_score': match.get('score', {}).get('fullTime', {}).get('away'),
                        'status': match.get('status'),
                        'minute': match.get('minute', 0),
                        'league': match.get('competition', {}).get('name'),
                        'country': match.get('competition', {}).get('area', {}).get('name'),
                        'start_time': match.get('utcDate')
                    })

                return matches
        except Exception as e:
            print(f"football-data.org error: {e}")

        return []

    def _get_footballdata_upcoming(self, date: str) -> List[Dict]:
        """从football-data.org获取即将开始的比赛"""
        try:
            url = f"{self.FOOTBALL_DATA_URL}/matches"
            headers = {'X-Auth-Token': self.FOOTBALL_DATA_API_KEY}
            params = {'dateFrom': date, 'dateTo': date}

            response = self.session.get(url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                matches = []

                for match in data.get('matches', []):
                    matches.append({
                        'event_id': match.get('id'),
                        'home_team': match.get('homeTeam', {}).get('shortName') or match.get('homeTeam', {}).get('name'),
                        'away_team': match.get('awayTeam', {}).get('shortName') or match.get('awayTeam', {}).get('name'),
                        'home_score': match.get('score', {}).get('fullTime', {}).get('home'),
                        'away_score': match.get('score', {}).get('fullTime', {}).get('away'),
                        'status': match.get('status'),
                        'minute': match.get('minute', 0),
                        'league': match.get('competition', {}).get('name'),
                        'country': match.get('competition', {}).get('area', {}).get('name'),
                        'start_time': match.get('utcDate')
                    })

                return matches
        except Exception as e:
            print(f"football-data.org upcoming error: {e}")

        return []

    def _get_flashscore_live(self) -> List[Dict]:
        """备用：从FlashScore获取实时数据"""
        try:
            # FlashScore数据端点
            url = "https://flashscore.com/feed/"

            response = self.session.get(url, timeout=15)

            # FlashScore返回的是特殊格式，需要解析
            # 这里简化处理，返回空列表
            return []

        except Exception as e:
            print(f"FlashScore备用失败: {e}")
            return []

    def get_match_events(self, event_id: int) -> List[Dict]:
        """
        获取比赛事件

        Args:
            event_id: Sofascore比赛ID

        Returns:
            事件列表（进球、红黄牌、换人等）
        """
        try:
            url = f"{self.BASE_URL}/event/{event_id}/events"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])

                formatted_events = []
                for event in events:
                    event_type = event.get('type')

                    formatted_events.append({
                        'event_id': event.get('id'),
                        'type': event_type,
                        'minute': event.get('time', {}).get('minute'),
                        'player': event.get('player', {}).get('name'),
                        'team': event.get('team', {}).get('name'),
                        'is_home': event.get('isHome'),
                        'detail': self._parse_event_detail(event)
                    })

                return formatted_events

        except Exception as e:
            print(f"获取比赛事件失败: {e}")

        return []

    def _parse_event_detail(self, event: Dict) -> str:
        """解析事件详情"""
        event_type = event.get('type')

        type_mapping = {
            'goal': '进球',
            'card': '黄牌/红牌',
            'subst': '换人',
            'penalty': '点球',
            'varDecision': 'VAR判罚',
            'period': '半场结束',
            'injuryTime': '伤停补时'
        }

        return type_mapping.get(event_type, event_type or '未知')

    def get_match_statistics(self, event_id: int) -> Dict:
        """
        获取比赛统计

        Args:
            event_id: Sofascore比赛ID

        Returns:
            统计数据（控球率、射门、传球等）
        """
        try:
            url = f"{self.BASE_URL}/event/{event_id}/statistics"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()
                stats = data.get('statistics', [])

                # 格式化统计
                formatted_stats = {}
                for stat_group in stats:
                    group_name = stat_group.get('groupName')
                    for stat_item in stat_group.get('statisticsItems', []):
                        stat_name = stat_item.get('name')
                        formatted_stats[stat_name] = {
                            'home': stat_item.get('homeValue'),
                            'away': stat_item.get('awayValue'),
                            'compare': stat_item.get('compareValue')
                        }

                return formatted_stats

        except Exception as e:
            print(f"获取比赛统计失败: {e}")

        return {}

    def get_player_ratings(self, event_id: int) -> List[Dict]:
        """
        获取球员评分

        Args:
            event_id: Sofascore比赛ID

        Returns:
            球员评分列表
        """
        try:
            url = f"{self.BASE_URL}/event/{event_id}/lineups"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()

                ratings = []

                # 主队球员
                home_players = data.get('homeTeam', {}).get('players', [])
                for player in home_players:
                    ratings.append({
                        'player_name': player.get('player', {}).get('name'),
                        'team': 'home',
                        'position': player.get('position'),
                        'rating': player.get('rating'),
                        'is_substitute': player.get('substitute')
                    })

                # 客队球员
                away_players = data.get('awayTeam', {}).get('players', [])
                for player in away_players:
                    ratings.append({
                        'player_name': player.get('player', {}).get('name'),
                        'team': 'away',
                        'position': player.get('position'),
                        'rating': player.get('rating'),
                        'is_substitute': player.get('substitute')
                    })

                return ratings

        except Exception as e:
            print(f"获取球员评分失败: {e}")

        return []

    def get_upcoming_matches(self, date: str = None) -> List[Dict]:
        """
        获取即将开始的比赛

        Args:
            date: 日期 (YYYY-MM-DD)，默认今天

        Returns:
            即将开始的比赛列表
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        cache_key = f'upcoming_{date}'

        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_duration:
                return cached['data']

        matches = []

        # 优先使用football-data.org
        try:
            matches = self._get_footballdata_upcoming(date)
            if matches:
                self.cache[cache_key] = {'timestamp': time.time(), 'data': matches}
                return matches
        except Exception as e:
            print(f"football-data.org upcoming failed: {e}")

        # 备用：Sofascore API
        try:
            timestamp = int(datetime.strptime(date, '%Y-%m-%d').timestamp())
            url = f"{self.BASE_URL}/sport/football/events/{timestamp}"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])

                for event in events:
                    matches.append({
                        'event_id': event.get('id'),
                        'home_team': event.get('homeTeam', {}).get('name'),
                        'away_team': event.get('awayTeam', {}).get('name'),
                        'league': event.get('tournament', {}).get('name'),
                        'start_time': event.get('startTimestamp'),
                        'status': event.get('status', {}).get('code')
                    })

                self.cache[cache_key] = {'timestamp': time.time(), 'data': matches}
        except Exception as e:
            print(f"获取即将开始的比赛失败: {e}")

        return matches

    def _get_footballdata_upcoming(self, date: str) -> List[Dict]:
        """从football-data.org获取即将开始的比赛"""
        try:
            api_token = os.environ.get('FOOTBALL_DATA_TOKEN', '')
            if not api_token:
                return []
            url = "https://api.football-data.org/v4/matches"
            headers = {'X-Auth-Token': api_token}
            params = {'dateFrom': date, 'dateTo': date}

            response = self.session.get(url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                matches = []

                for match in data.get('matches', []):
                    matches.append({
                        'event_id': match.get('id'),
                        'home_team': match.get('homeTeam', {}).get('name'),
                        'away_team': match.get('awayTeam', {}).get('name'),
                        'home_score': match.get('score', {}).get('fullTime', {}).get('home'),
                        'away_score': match.get('score', {}).get('fullTime', {}).get('away'),
                        'status': match.get('status'),
                        'minute': match.get('minute', 0),
                        'league': match.get('competition', {}).get('name'),
                        'country': match.get('competition', {}).get('area', {}).get('name'),
                        'start_time': match.get('utcDate')
                    })

                return matches
        except Exception as e:
            print(f"football-data.org upcoming error: {e}")

        return []

    def search_team(self, team_name: str) -> List[Dict]:
        """
        搜索球队

        Args:
            team_name: 球队名称

        Returns:
            球队列表
        """
        try:
            url = f"{self.BASE_URL}/search"
            params = {'query': team_name}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                teams = data.get('teams', [])

                return [
                    {
                        'team_id': team.get('id'),
                        'name': team.get('name'),
                        'country': team.get('country', {}).get('name'),
                        'sport': team.get('sport', {}).get('name')
                    } for team in teams
                ]

        except Exception as e:
            print(f"搜索球队失败: {e}")

        return []

    def get_team_matches(self, team_id: int) -> List[Dict]:
        """
        获取球队近期比赛

        Args:
            team_id: Sofascore球队ID

        Returns:
            比赛列表
        """
        try:
            url = f"{self.BASE_URL}/team/{team_id}/events/last/0"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])

                matches = []
                for event in events:
                    matches.append({
                        'event_id': event.get('id'),
                        'home_team': event.get('homeTeam', {}).get('name'),
                        'away_team': event.get('awayTeam', {}).get('name'),
                        'home_score': event.get('homeScore', {}).get('current'),
                        'away_score': event.get('awayScore', {}).get('current'),
                        'date': datetime.fromtimestamp(event.get('startTimestamp', 0)).strftime('%Y-%m-%d'),
                        'league': event.get('tournament', {}).get('name')
                    })

                return matches

        except Exception as e:
            print(f"获取球队比赛失败: {e}")

        return []

    def save_live_data(self, matches: List[Dict], conn: sqlite3.Connection = None):
        """保存实时数据到数据库"""
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        for match in matches:
            try:
                # 尝试匹配本地match_id
                cursor.execute("""
                    SELECT match_id FROM matches
                    WHERE (home_team_id IN (
                        SELECT team_id FROM teams WHERE name_en LIKE ?
                    ) OR home_team_id IN (
                        SELECT team_id FROM teams WHERE name_cn LIKE ?
                    ))
                    AND match_date = DATE(?)
                    LIMIT 1
                """, (
                    f'%{match["home_team"]}%',
                    f'%{match["home_team"]}%',
                    datetime.fromtimestamp(match.get('start_time', 0)).strftime('%Y-%m-%d')
                ))

                result = cursor.fetchone()

                if result:
                    # 更新实时比分
                    cursor.execute("""
                        UPDATE matches
                        SET home_goals = ?, away_goals = ?, status = ?
                        WHERE match_id = ?
                    """, (
                        match.get('home_score'),
                        match.get('away_score'),
                        'live' if match.get('status') == 1 else 'finished',
                        result['match_id']
                    ))

            except Exception as e:
                continue

        conn.commit()


def main():
    """测试Sofascore爬虫"""
    db_path = r"d:\football_tools\data\football_v2.db"
    crawler = SofascoreCrawler(db_path)

    print("Sofascore爬虫测试")
    print("=" * 60)

    # 获取实时比赛
    print("\n[实时比赛]")
    live_matches = crawler.get_live_matches()
    print(f"获取到 {len(live_matches)} 场实时比赛")

    for match in live_matches[:5]:
        print(f"  {match['home_team']} {match.get('home_score', '-')} vs {match.get('away_score', '-')} {match['away_team']}")
        print(f"    状态: {match['status']}, 分钟: {match.get('minute', '-')}")

    # 获取即将开始的比赛
    print("\n[即将开始的比赛]")
    upcoming = crawler.get_upcoming_matches()
    print(f"获取到 {len(upcoming)} 场即将开始的比赛")

    for match in upcoming[:5]:
        print(f"  {match['home_team']} vs {match['away_team']} ({match['league']})")


if __name__ == "__main__":
    main()