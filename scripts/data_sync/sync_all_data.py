#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面数据同步脚本
从多个API获取历史数据并补充到数据库
"""

import os
import sys
import sqlite3
import json
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

# Windows编码处理
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / 'data' / 'football_v2.db'
CONFIG_PATH = PROJECT_ROOT / 'api_config.json'


class DataSyncer:
    """数据同步器"""

    def __init__(self):
        self.config = self._load_config()
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # API配置
        self.apis = self.config.get('apis', {})

        # 请求间隔
        self.request_interval = 1.0

    def _load_config(self) -> dict:
        """加载配置文件"""
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def _make_request(self, session: aiohttp.ClientSession, url: str, headers: dict = None, params: dict = None) -> Optional[dict]:
        """发送HTTP请求"""
        try:
            async with session.get(url, headers=headers, params=params, timeout=30) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"  Request failed: {response.status}")
                    return None
        except Exception as e:
            print(f"  Request error: {e}")
            return None

    async def sync_football_data_org(self):
        """从football-data.org同步数据"""
        print("\n" + "=" * 60)
        print("Syncing from football-data.org")
        print("=" * 60)

        api_config = self.apis.get('football_data_org', {})
        base_url = api_config.get('base_url', 'https://api.football-data.org/v4')
        api_token = api_config.get('api_token', '')

        if not api_token:
            print("  No API token configured")
            return

        headers = {'X-Auth-Token': api_token}

        # 支持的联赛
        competitions = {
            'PL': ('premier_league', 1),
            'PD': ('la_liga', 2),
            'BL1': ('bundesliga', 3),
            'SA': ('serie_a', 4),
            'FL1': ('ligue_1', 5),
            'CL': ('champions_league', 10),
            'ELC': ('championship', 11),
        }

        async with aiohttp.ClientSession() as session:
            for code, (league_name, league_id) in competitions.items():
                print(f"\n  Syncing {league_name}...")

                # 获取当前赛季
                try:
                    url = f"{base_url}/competitions/{code}/standings"
                    data = await self._make_request(session, url, headers)

                    if not data:
                        continue

                    # 解析积分榜
                    standings = data.get('standings', [])
                    if standings:
                        for table in standings:
                            if table.get('type') == 'TOTAL':
                                for row in table.get('table', []):
                                    team = row.get('team', {})
                                    team_id = self._get_or_create_team(team)

                                    # 更新积分榜
                                    self._update_standings(
                                        league_id=league_id,
                                        team_id=team_id,
                                        position=row.get('position'),
                                        played=row.get('playedGames'),
                                        won=row.get('won'),
                                        drawn=row.get('draw'),
                                        lost=row.get('lost'),
                                        goals_for=row.get('goalsFor'),
                                        goals_against=row.get('goalsAgainst'),
                                        points=row.get('points')
                                    )

                    print(f"    {league_name}: standings synced")

                    # 获取射手榜
                    url = f"{base_url}/competitions/{code}/scorers?limit=20"
                    data = await self._make_request(session, url, headers)

                    if data:
                        scorers = data.get('scorers', [])
                        for scorer in scorers:
                            player = scorer.get('player', {})
                            team = scorer.get('team', {})
                            self._update_player_stats(
                                player_name=player.get('name'),
                                team_name=team.get('name'),
                                goals=scorer.get('goals'),
                                assists=scorer.get('assists')
                            )
                        print(f"    {league_name}: {len(scorers)} scorers synced")

                    self.conn.commit()

                    # 请求间隔
                    await asyncio.sleep(7)  # 10 requests per minute limit

                except Exception as e:
                    print(f"    Error: {e}")
                    continue

    async def sync_thesportsdb(self):
        """从TheSportsDB同步数据"""
        print("\n" + "=" * 60)
        print("Syncing from TheSportsDB")
        print("=" * 60)

        api_config = self.apis.get('thesportsdb', {})
        base_url = api_config.get('base_url', 'https://www.thesportsdb.com/api/v1/json/3')

        # 获取今日比赛
        today = datetime.now().strftime('%Y%m%d')

        async with aiohttp.ClientSession() as session:
            # 获取今日比赛
            url = f"{base_url}/eventsday.php"
            params = {'d': today, 's': 'Soccer'}

            data = await self._make_request(session, url, params=params)

            if data:
                events = data.get('events', [])
                if events:
                    print(f"  Today's matches: {len(events)}")
                    for event in events[:10]:
                        home = event.get('strHomeTeam', '')
                        away = event.get('strAwayTeam', '')
                        league = event.get('strLeague', '')
                        print(f"    {home} vs {away} ({league})")

            await asyncio.sleep(1)

            # 获取世界杯数据
            print("\n  Syncing World Cup data...")
            world_cup_id = 44  # TheSportsDB World Cup ID

            url = f"{base_url}/lookupleague.php"
            params = {'id': world_cup_id}

            data = await self._make_request(session, url, params=params)

            if data:
                leagues = data.get('leagues', [])
                if leagues:
                    print(f"    World Cup info: {leagues[0].get('strLeague')}")

    async def sync_scorebat(self):
        """从ScoreBat同步比赛集锦数据"""
        print("\n" + "=" * 60)
        print("Syncing from ScoreBat")
        print("=" * 60)

        api_config = self.apis.get('scorebat', {})
        base_url = api_config.get('base_url', 'https://www.scorebat.com/video-api/v3')

        async with aiohttp.ClientSession() as session:
            url = f"{base_url}/"
            data = await self._make_request(session, url)

            if data:
                videos = data.get('response', [])
                print(f"  Total videos: {len(videos)}")

                # 解析最近的比赛
                recent_matches = []
                for video in videos[:50]:
                    title = video.get('title', '')
                    competition = video.get('competition', {}).get('name', '')
                    date = video.get('date', '')

                    # 从标题解析比分 (格式: "Team1 2-1 Team2")
                    import re
                    match = re.search(r'(\d+)\s*-\s*(\d+)', title)
                    if match:
                        home_score = int(match.group(1))
                        away_score = int(match.group(2))

                        # 解析队名
                        parts = title.split(match.group(0))
                        if len(parts) == 2:
                            home_team = parts[0].strip()
                            away_team = parts[1].strip()

                            recent_matches.append({
                                'home_team': home_team,
                                'away_team': away_team,
                                'home_score': home_score,
                                'away_score': away_score,
                                'competition': competition,
                                'date': date
                            })

                print(f"  Parsed matches: {len(recent_matches)}")
                for m in recent_matches[:5]:
                    print(f"    {m['home_team']} {m['home_score']}-{m['away_score']} {m['away_team']}")

    async def sync_365scores(self):
        """从365Scores同步实时比分"""
        print("\n" + "=" * 60)
        print("Syncing from 365Scores")
        print("=" * 60)

        api_config = self.apis.get('365scores', {})
        base_url = api_config.get('base_url', 'https://webws.365scores.com/web')

        async with aiohttp.ClientSession() as session:
            url = f"{base_url}/games/fixtures"
            params = {
                'langId': '1',
                'timezoneName': 'Asia/Shanghai',
                'userCountryId': '1',
                'appTypeId': '1'
            }

            data = await self._make_request(session, url, params=params)

            if data:
                fixtures = data.get('fixtures', [])
                print(f"  Total fixtures: {len(fixtures)}")

                live_count = 0
                for fixture in fixtures[:20]:
                    status = fixture.get('gameStatus', '')
                    if status == 'playing':
                        live_count += 1
                        home = fixture.get('homeCompetitor', {}).get('name', '')
                        away = fixture.get('awayCompetitor', {}).get('name', '')
                        home_score = fixture.get('homeScore', 0)
                        away_score = fixture.get('awayScore', 0)
                        print(f"    LIVE: {home} {home_score}-{away_score} {away}")

                print(f"  Live matches: {live_count}")

    def _get_or_create_team(self, team_data: dict) -> int:
        """获取或创建球队"""
        name = team_data.get('name') or team_data.get('shortName')
        if not name:
            return 0

        # 查找现有球队
        self.cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (name,))
        result = self.cursor.fetchone()

        if result:
            return result[0]

        # 创建新球队
        self.cursor.execute("""
            INSERT INTO teams (name_en, name_cn, tla, country, founded, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (
            name,
            None,
            team_data.get('tla'),
            team_data.get('area', {}).get('name'),
            team_data.get('founded')
        ))

        return self.cursor.lastrowid

    def _update_standings(self, league_id: int, team_id: int, position: int,
                          played: int, won: int, drawn: int, lost: int,
                          goals_for: int, goals_against: int, points: int):
        """更新积分榜"""
        # 获取当前赛季ID
        self.cursor.execute("""
            SELECT season_id FROM seasons
            WHERE league_id = ? AND is_current = 1
            ORDER BY season_id DESC LIMIT 1
        """, (league_id,))

        result = self.cursor.fetchone()
        season_id = result[0] if result else 1

        self.cursor.execute("""
            INSERT OR REPLACE INTO standings (
                season_id, league_id, team_id, position,
                played, won, drawn, lost, goals_for, goals_against, goal_difference, points, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (season_id, league_id, team_id, position, played, won, drawn, lost,
              goals_for, goals_against, goals_for - goals_against, points))

    def _update_player_stats(self, player_name: str, team_name: str, goals: int, assists: int):
        """更新球员统计"""
        if not player_name:
            return

        # 查找球员
        self.cursor.execute("SELECT player_id FROM players WHERE name_en = ?", (player_name,))
        result = self.cursor.fetchone()

        if result:
            player_id = result[0]
        else:
            # 创建球员
            import re
            player_code = re.sub(r'[^a-zA-Z0-9]', '_', player_name.lower())[:30]
            self.cursor.execute("""
                INSERT INTO players (player_code, name_en, status, created_at)
                VALUES (?, ?, 'active', datetime('now'))
            """, (player_code, player_name))
            player_id = self.cursor.lastrowid

    async def run(self):
        """运行所有同步任务"""
        print("=" * 60)
        print("Starting Data Sync")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        try:
            # 按顺序同步各数据源
            await self.sync_football_data_org()
            await self.sync_thesportsdb()
            await self.sync_scorebat()
            await self.sync_365scores()

            print("\n" + "=" * 60)
            print("Data Sync Complete")
            print("=" * 60)

        except Exception as e:
            print(f"\nError during sync: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.conn.close()


async def main():
    syncer = DataSyncer()
    await syncer.run()


if __name__ == '__main__':
    asyncio.run(main())
