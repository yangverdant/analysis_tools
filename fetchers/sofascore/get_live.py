"""
Sofascore - 获取实时比分和比赛详情

功能:
1. 获取正在进行的比赛 (实时比分)
2. 获取即将开始的比赛
3. 获取比赛事件 (进球/红黄牌/换人)
4. 获取球员评分
5. 获取比赛统计

数据来源: api.sofascore.com (主) + football-data.org (备)
无需Cookie, 但Sofascore可能有反爬

使用示例:
    from fetchers.sofascore.get_live import get_live_matches, get_upcoming_matches

    # 获取实时比分
    matches = get_live_matches()
    for m in matches:
        print(f"  {m['home_team']} {m['home_score']}-{m['away_score']} {m['away_team']} [{m['minute']}']")

    # 获取今天即将开始的比赛
    upcoming = get_upcoming_matches()
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional

import requests

from fetchers.sofascore.config import (
    SOFASCORE_API_URL, FOOTBALL_DATA_API_URL, FOOTBALL_DATA_API_KEY,
    REQUEST_TIMEOUT, CACHE_DURATION
)

os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'

logger = logging.getLogger(__name__)

# 简易缓存
_cache = {}


def _create_session() -> requests.Session:
    """创建HTTP会话"""
    session = requests.Session()
    session.trust_env = False
    session.verify = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://www.sofascore.com',
        'Referer': 'https://www.sofascore.com/'
    })
    return session


# ==================== 核心接口 ====================

def get_live_matches() -> List[Dict]:
    """获取正在进行的比赛

    优先使用football-data.org (稳定), 备用Sofascore API

    Returns:
        [{
            "event_id": 12345,
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "home_score": 2,
            "away_score": 1,
            "status": "IN_PLAY",
            "minute": 67,
            "league": "Premier League",
            "country": "England",
            "start_time": "2025-05-25T15:00:00Z",
            "source": "football_data_org"
        }, ...]
    """
    cache_key = 'live_matches'
    if cache_key in _cache:
        cached = _cache[cache_key]
        if time.time() - cached['timestamp'] < CACHE_DURATION:
            return cached['data']

    session = _create_session()

    # 优先: football-data.org
    matches = _get_footballdata_live(session)
    if matches:
        _cache[cache_key] = {'timestamp': time.time(), 'data': matches}
        print(f"[sofascore] 实时比分: {len(matches)} 场 (football-data.org)")
        return matches

    # 备用: Sofascore API
    matches = _get_sofascore_live(session)
    if matches:
        _cache[cache_key] = {'timestamp': time.time(), 'data': matches}
        print(f"[sofascore] 实时比分: {len(matches)} 场 (sofascore)")
        return matches

    print("[sofascore] 实时比分: 无数据")
    return []


def get_upcoming_matches(date: str = None) -> List[Dict]:
    """获取即将开始的比赛

    Args:
        date: 日期 "2025-05-25", 默认今天

    Returns:
        同 get_live_matches 返回格式, status="SCHEDULED"
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    session = _create_session()

    try:
        url = f"{FOOTBALL_DATA_API_URL}/matches"
        headers = {'X-Auth-Token': FOOTBALL_DATA_API_KEY}
        params = {'dateFrom': date, 'dateTo': date}

        response = session.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            matches = []

            for match in data.get('matches', []):
                matches.append({
                    'event_id': match.get('id'),
                    'home_team': match.get('homeTeam', {}).get('shortName') or match.get('homeTeam', {}).get('name'),
                    'away_team': match.get('awayTeam', {}).get('shortName') or match.get('awayTeam', {}).get('name'),
                    'home_score': match.get('score', {}).get('fullTime', {}).get('home') if match.get('score') else None,
                    'away_score': match.get('score', {}).get('fullTime', {}).get('away') if match.get('score') else None,
                    'status': match.get('status'),
                    'league': match.get('competition', {}).get('name'),
                    'country': match.get('competition', {}).get('area', {}).get('name'),
                    'start_time': match.get('utcDate'),
                    'source': 'football_data_org'
                })

            print(f"[sofascore] {date} 赛程: {len(matches)} 场")
            return matches

    except Exception as e:
        logger.error(f"获取赛程失败: {e}")

    return []


def get_match_events(event_id: int) -> Optional[Dict]:
    """获取比赛事件 (进球/红黄牌/换人)

    Args:
        event_id: Sofascore比赛ID

    Returns:
        {"events": [...], "statistics": [...], "ratings": [...]}
    """
    session = _create_session()

    try:
        url = f"{SOFASCORE_API_URL}/event/{event_id}/incidents"
        response = session.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            incidents = data.get('incidents', [])

            events = []
            for inc in incidents:
                events.append({
                    'time': inc.get('time'),
                    'type': inc.get('incidentType'),
                    'player': inc.get('player', {}).get('name'),
                    'team': inc.get('team', {}).get('name') if inc.get('team') else None,
                    'home_score': inc.get('homeScore'),
                    'away_score': inc.get('awayScore'),
                })

            return {"events": events}

    except Exception as e:
        logger.error(f"获取比赛事件失败: {e}")

    return None


def get_match_statistics(event_id: int) -> Optional[List[Dict]]:
    """获取比赛统计

    Args:
        event_id: Sofascore比赛ID

    Returns:
        [{"name": "Ball possession", "home": "55%", "away": "45%"}, ...]
    """
    session = _create_session()

    try:
        url = f"{SOFASCORE_API_URL}/event/{event_id}/statistics"
        response = session.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            stats = []

            for group in data.get('statistics', []):
                for item in group.get('statistics', []):
                    stats.append({
                        'name': item.get('name'),
                        'home': item.get('home'),
                        'away': item.get('away'),
                    })

            return stats

    except Exception as e:
        logger.error(f"获取比赛统计失败: {e}")

    return None


# ==================== 内部方法 ====================

def _get_sofascore_live(session: requests.Session) -> List[Dict]:
    """从Sofascore API获取实时数据"""
    try:
        url = f"{SOFASCORE_API_URL}/sport/football/events/live"
        response = session.get(url, timeout=REQUEST_TIMEOUT)

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
                    'start_time': event.get('startTimestamp'),
                    'source': 'sofascore'
                })

            return matches

    except Exception as e:
        logger.debug(f"Sofascore API error: {e}")

    return []


def _get_footballdata_live(session: requests.Session) -> List[Dict]:
    """从football-data.org获取实时数据"""
    try:
        url = f"{FOOTBALL_DATA_API_URL}/matches"
        headers = {'X-Auth-Token': FOOTBALL_DATA_API_KEY}
        params = {'status': 'IN_PLAY,PAUSED,LIVE'}

        response = session.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            matches = []

            for match in data.get('matches', []):
                matches.append({
                    'event_id': match.get('id'),
                    'home_team': match.get('homeTeam', {}).get('shortName') or match.get('homeTeam', {}).get('name'),
                    'away_team': match.get('awayTeam', {}).get('shortName') or match.get('awayTeam', {}).get('name'),
                    'home_score': match.get('score', {}).get('fullTime', {}).get('home') if match.get('score') else None,
                    'away_score': match.get('score', {}).get('fullTime', {}).get('away') if match.get('score') else None,
                    'status': match.get('status'),
                    'minute': match.get('minute', 0),
                    'league': match.get('competition', {}).get('name'),
                    'country': match.get('competition', {}).get('area', {}).get('name'),
                    'start_time': match.get('utcDate'),
                    'source': 'football_data_org'
                })

            return matches

    except Exception as e:
        logger.debug(f"football-data.org error: {e}")

    return []


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.sofascore.get_live live")
        print("  python -m fetchers.sofascore.get_live upcoming")
        print("  python -m fetchers.sofascore.get_live upcoming 2025-05-25")
        print("  python -m fetchers.sofascore.get_live events 12345")
        print("  python -m fetchers.sofascore.get_live stats 12345")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "live":
        matches = get_live_matches()
        for m in matches:
            score = f" {m['home_score']}-{m['away_score']}" if m['home_score'] is not None else ""
            minute = f" [{m['minute']}']" if m.get('minute') else ""
            print(f"  {m['home_team']}{score} {m['away_team']}{minute} ({m['league']})")

    elif cmd == "upcoming":
        date_str = sys.argv[2] if len(sys.argv) > 2 else None
        matches = get_upcoming_matches(date_str)
        for m in matches:
            t = m.get('start_time', '')[:16] if m.get('start_time') else ''
            print(f"  {t} {m['home_team']} vs {m['away_team']} ({m['league']})")

    elif cmd == "events":
        event_id = int(sys.argv[2])
        result = get_match_events(event_id)
        if result:
            for e in result['events']:
                print(f"  {e['time']}' {e['type']}: {e['player']} ({e['team']})")

    elif cmd == "stats":
        event_id = int(sys.argv[2])
        stats = get_match_statistics(event_id)
        if stats:
            for s in stats:
                print(f"  {s['name']}: {s['home']} vs {s['away']}")