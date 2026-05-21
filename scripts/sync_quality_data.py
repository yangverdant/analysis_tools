#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高质量数据同步脚本
从多个API获取历史数据，确保数据准确性、真实性和去重
"""

import os
import sys
import sqlite3
import json
import asyncio
import aiohttp
import hashlib
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass

# Windows编码处理
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / 'data' / 'football_v2.db'
CONFIG_PATH = PROJECT_ROOT / 'api_config.json'


@dataclass
class MatchRecord:
    """比赛记录"""
    match_id: str
    league_id: int
    season_id: int
    match_date: str
    home_team_id: int
    away_team_id: int
    home_goals: Optional[int]
    away_goals: Optional[int]
    home_goals_ht: Optional[int]
    away_goals_ht: Optional[int]
    status: str
    round_num: Optional[int]
    venue: Optional[str]
    referee: Optional[str]
    source: str
    source_match_id: Optional[str]


class QualityDataSyncer:
    """高质量数据同步器"""

    def __init__(self):
        self.config = self._load_config()
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # API配置
        self.apis = self.config.get('apis', {})

        # 数据验证规则
        self.validation_rules = {
            'match_date': lambda x: bool(re.match(r'\d{4}-\d{2}-\d{2}', str(x))),
            'goals': lambda x: x is None or (0 <= int(x) <= 20),
            'team_name': lambda x: len(str(x)) >= 2 and len(str(x)) <= 100,
        }

        # 去重缓存
        self.match_cache: Dict[str, str] = {}
        self.team_cache: Dict[str, int] = {}
        self._load_caches()

        # 统计
        self.stats = {
            'matches_added': 0,
            'matches_updated': 0,
            'matches_skipped': 0,
            'teams_added': 0,
            'standings_updated': 0,
            'errors': 0
        }

    def _load_config(self) -> dict:
        """加载配置文件"""
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_caches(self):
        """加载缓存数据"""
        # 加载比赛缓存
        self.cursor.execute("""
            SELECT match_id, home_team_id, away_team_id, match_date
            FROM matches
        """)
        for row in self.cursor.fetchall():
            key = f"{row['home_team_id']}-{row['away_team_id']}-{row['match_date']}"
            self.match_cache[key] = row['match_id']

        # 加载球队缓存
        self.cursor.execute("SELECT team_id, name_en, name_cn FROM teams")
        for row in self.cursor.fetchall():
            self.team_cache[row['name_en'].lower()] = row['team_id']
            if row['name_cn']:
                self.team_cache[row['name_cn'].lower()] = row['team_id']

    def _validate_data(self, field: str, value: Any) -> bool:
        """验证数据"""
        if field in self.validation_rules:
            try:
                return self.validation_rules[field](value)
            except:
                return False
        return True

    def _generate_match_id(self, league_id: int, season_id: int, match_date: str,
                           home_team_id: int, away_team_id: int) -> str:
        """生成唯一比赛ID"""
        return f"{league_id}_{season_id}_{match_date}_{home_team_id}_vs_{away_team_id}"

    def _get_or_create_team(self, name: str, country: str = None, tla: str = None) -> int:
        """获取或创建球队（带去重）"""
        if not name:
            return 0

        name_lower = name.lower().strip()

        # 查找缓存
        if name_lower in self.team_cache:
            return self.team_cache[name_lower]

        # 查找数据库（模糊匹配）
        self.cursor.execute("""
            SELECT team_id FROM teams
            WHERE LOWER(name_en) = ? OR LOWER(name_cn) = ? OR LOWER(tla) = ?
        """, (name_lower, name_lower, tla.lower() if tla else ''))

        result = self.cursor.fetchone()
        if result:
            team_id = result[0]
            self.team_cache[name_lower] = team_id
            return team_id

        # 创建新球队
        self.cursor.execute("""
            INSERT INTO teams (name_en, name_cn, tla, country, team_type, created_at)
            VALUES (?, NULL, ?, ?, 'club', datetime('now'))
        """, (name.strip(), tla, country))

        team_id = self.cursor.lastrowid
        self.team_cache[name_lower] = team_id
        self.stats['teams_added'] += 1

        return team_id

    def _check_match_duplicate(self, home_team_id: int, away_team_id: int,
                               match_date: str, league_id: int) -> Tuple[bool, Optional[str]]:
        """检查比赛是否重复"""
        key = f"{home_team_id}-{away_team_id}-{match_date}"

        if key in self.match_cache:
            return True, self.match_cache[key]

        # 检查数据库
        self.cursor.execute("""
            SELECT match_id FROM matches
            WHERE home_team_id = ? AND away_team_id = ? AND match_date = ? AND league_id = ?
        """, (home_team_id, away_team_id, match_date, league_id))

        result = self.cursor.fetchone()
        if result:
            self.match_cache[key] = result['match_id']
            return True, result['match_id']

        return False, None

    def _insert_match(self, match: MatchRecord) -> bool:
        """插入比赛记录（带验证）"""
        # 验证数据
        if not self._validate_data('match_date', match.match_date):
            self.stats['errors'] += 1
            return False

        if not self._validate_data('goals', match.home_goals):
            self.stats['errors'] += 1
            return False

        if not self._validate_data('goals', match.away_goals):
            self.stats['errors'] += 1
            return False

        # 检查重复
        is_duplicate, existing_id = self._check_match_duplicate(
            match.home_team_id, match.away_team_id, match.match_date, match.league_id
        )

        if is_duplicate:
            # 更新现有记录（如果有新数据）
            if match.home_goals is not None and match.away_goals is not None:
                self.cursor.execute("""
                    UPDATE matches SET
                        home_goals = ?, away_goals = ?, status = ?, source = ?, updated_at = datetime('now')
                    WHERE match_id = ? AND (home_goals IS NULL OR away_goals IS NULL)
                """, (match.home_goals, match.away_goals, match.status, match.source, existing_id))

                if self.cursor.rowcount > 0:
                    self.stats['matches_updated'] += 1
                    return True

            self.stats['matches_skipped'] += 1
            return False

        # 插入新记录
        self.cursor.execute("""
            INSERT INTO matches (
                match_id, league_id, season_id, match_date, home_team_id, away_team_id,
                home_goals, away_goals, home_goals_ht, away_goals_ht, status, round_num,
                venue, referee, source, sb_match_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            match.match_id, match.league_id, match.season_id, match.match_date,
            match.home_team_id, match.away_team_id, match.home_goals, match.away_goals,
            match.home_goals_ht, match.away_goals_ht, match.status, match.round_num,
            match.venue, match.referee, match.source, match.source_match_id
        ))

        # 更新缓存
        key = f"{match.home_team_id}-{match.away_team_id}-{match.match_date}"
        self.match_cache[key] = match.match_id
        self.stats['matches_added'] += 1

        return True

    async def _make_request(self, session: aiohttp.ClientSession, url: str,
                            headers: dict = None, params: dict = None) -> Optional[dict]:
        """发送HTTP请求（带错误处理）"""
        try:
            async with session.get(url, headers=headers, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    # 验证响应数据
                    if data and isinstance(data, dict):
                        return data
                elif response.status == 429:
                    print(f"  Rate limit exceeded, waiting...")
                    await asyncio.sleep(60)
                else:
                    print(f"  Request failed: {response.status}")
                return None
        except asyncio.TimeoutError:
            print(f"  Request timeout")
            return None
        except Exception as e:
            print(f"  Request error: {e}")
            return None

    async def sync_football_data_org_matches(self):
        """从football-data.org同步历史比赛数据"""
        print("\n" + "=" * 60)
        print("Syncing Historical Matches from football-data.org")
        print("=" * 60)

        api_config = self.apis.get('football_data_org', {})
        base_url = api_config.get('base_url', 'https://api.football-data.org/v4')
        api_token = api_config.get('api_token', '')

        if not api_token:
            print("  No API token configured")
            return

        headers = {'X-Auth-Token': api_token}

        # 联赛映射
        competitions = {
            'PL': {'league_id': 1, 'name': 'Premier League'},
            'PD': {'league_id': 2, 'name': 'La Liga'},
            'BL1': {'league_id': 3, 'name': 'Bundesliga'},
            'SA': {'league_id': 4, 'name': 'Serie A'},
            'FL1': {'league_id': 5, 'name': 'Ligue 1'},
            'CL': {'league_id': 10, 'name': 'Champions League'},
        }

        async with aiohttp.ClientSession() as session:
            for code, info in competitions.items():
                print(f"\n  Processing {info['name']}...")

                # 获取多个赛季的数据
                for season_year in [2024, 2023, 2022, 2021, 2020]:
                    try:
                        url = f"{base_url}/competitions/{code}/matches"
                        params = {'season': season_year}

                        data = await self._make_request(session, url, headers, params)

                        if not data:
                            continue

                        matches = data.get('matches', [])
                        print(f"    Season {season_year}: {len(matches)} matches")

                        # 获取或创建赛季
                        season_id = self._get_or_create_season(info['league_id'], season_year)

                        for match_data in matches:
                            try:
                                # 解析比赛数据
                                home_team = match_data.get('homeTeam', {})
                                away_team = match_data.get('awayTeam', {})

                                home_team_id = self._get_or_create_team(
                                    home_team.get('name'),
                                    home_team.get('tla')
                                )
                                away_team_id = self._get_or_create_team(
                                    away_team.get('name'),
                                    away_team.get('tla')
                                )

                                # 解析比分
                                score = match_data.get('score', {})
                                full_time = score.get('fullTime', {})
                                half_time = score.get('halfTime', {})

                                home_goals = full_time.get('home')
                                away_goals = full_time.get('away')
                                home_goals_ht = half_time.get('home')
                                away_goals_ht = half_time.get('away')

                                # 解析日期
                                utc_date = match_data.get('utcDate', '')
                                match_date = utc_date[:10] if utc_date else None

                                if not match_date:
                                    continue

                                # 解析状态
                                status_map = {
                                    'FINISHED': 'finished',
                                    'IN_PLAY': 'live',
                                    'PAUSED': 'live',
                                    'SCHEDULED': 'scheduled',
                                    'TIMED': 'scheduled',
                                    'POSTPONED': 'postponed',
                                    'CANCELLED': 'cancelled',
                                }
                                status = status_map.get(match_data.get('status'), 'scheduled')

                                # 解析轮次
                                round_num = match_data.get('matchday')

                                # 创建比赛记录
                                match_record = MatchRecord(
                                    match_id=self._generate_match_id(
                                        info['league_id'], season_id, match_date,
                                        home_team_id, away_team_id
                                    ),
                                    league_id=info['league_id'],
                                    season_id=season_id,
                                    match_date=match_date,
                                    home_team_id=home_team_id,
                                    away_team_id=away_team_id,
                                    home_goals=home_goals,
                                    away_goals=away_goals,
                                    home_goals_ht=home_goals_ht,
                                    away_goals_ht=away_goals_ht,
                                    status=status,
                                    round_num=round_num,
                                    venue=None,
                                    referee=None,
                                    source='football-data.org',
                                    source_match_id=str(match_data.get('id'))
                                )

                                self._insert_match(match_record)

                            except Exception as e:
                                self.stats['errors'] += 1
                                continue

                        self.conn.commit()
                        print(f"    Added: {self.stats['matches_added']}, Updated: {self.stats['matches_updated']}, Skipped: {self.stats['matches_skipped']}")

                        # 请求间隔（10 requests per minute）
                        await asyncio.sleep(7)

                    except Exception as e:
                        print(f"    Error: {e}")
                        continue

    def _get_or_create_season(self, league_id: int, year: int) -> int:
        """获取或创建赛季"""
        season_name = f"{year}-{year+1}"

        self.cursor.execute("""
            SELECT season_id FROM seasons
            WHERE league_id = ? AND season_name = ?
        """, (league_id, season_name))

        result = self.cursor.fetchone()
        if result:
            return result[0]

        self.cursor.execute("""
            INSERT INTO seasons (league_id, season_name, year, status, created_at)
            VALUES (?, ?, ?, 'active', datetime('now'))
        """, (league_id, season_name, year))

        return self.cursor.lastrowid

    async def sync_standings(self):
        """同步积分榜数据"""
        print("\n" + "=" * 60)
        print("Syncing Standings")
        print("=" * 60)

        api_config = self.apis.get('football_data_org', {})
        base_url = api_config.get('base_url', 'https://api.football-data.org/v4')
        api_token = api_config.get('api_token', '')

        headers = {'X-Auth-Token': api_token}

        competitions = {
            'PL': {'league_id': 1},
            'PD': {'league_id': 2},
            'BL1': {'league_id': 3},
            'SA': {'league_id': 4},
            'FL1': {'league_id': 5},
        }

        async with aiohttp.ClientSession() as session:
            for code, info in competitions.items():
                try:
                    url = f"{base_url}/competitions/{code}/standings"
                    params = {'season': 2024}

                    data = await self._make_request(session, url, headers, params)

                    if not data:
                        continue

                    standings = data.get('standings', [])

                    for table in standings:
                        if table.get('type') == 'TOTAL':
                            season_id = self._get_or_create_season(info['league_id'], 2024)

                            for row in table.get('table', []):
                                team = row.get('team', {})
                                team_id = self._get_or_create_team(team.get('name'), tla=team.get('tla'))

                                self.cursor.execute("""
                                    INSERT OR REPLACE INTO standings (
                                        season_id, league_id, team_id, position,
                                        played, won, drawn, lost, goals_for, goals_against,
                                        goal_diff, points, updated_at
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                                """, (
                                    season_id, info['league_id'], team_id, row.get('position'),
                                    row.get('playedGames'), row.get('won'), row.get('draw'),
                                    row.get('lost'), row.get('goalsFor'), row.get('goalsAgainst'),
                                    row.get('goalDifference'), row.get('points')
                                ))

                                self.stats['standings_updated'] += 1

                    self.conn.commit()
                    print(f"  {code}: standings synced")

                    await asyncio.sleep(7)

                except Exception as e:
                    print(f"  Error: {e}")
                    continue

    async def run(self):
        """运行所有同步任务"""
        print("=" * 60)
        print("High Quality Data Sync Started")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Database: {DATABASE_PATH}")
        print("=" * 60)

        try:
            # 同步历史比赛
            await self.sync_football_data_org_matches()

            # 同步积分榜
            await self.sync_standings()

            # 打印统计
            print("\n" + "=" * 60)
            print("Sync Statistics")
            print("=" * 60)
            print(f"Matches Added: {self.stats['matches_added']}")
            print(f"Matches Updated: {self.stats['matches_updated']}")
            print(f"Matches Skipped (Duplicates): {self.stats['matches_skipped']}")
            print(f"Teams Added: {self.stats['teams_added']}")
            print(f"Standings Updated: {self.stats['standings_updated']}")
            print(f"Errors: {self.stats['errors']}")
            print("=" * 60)

        except Exception as e:
            print(f"\nError during sync: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.conn.close()


async def main():
    syncer = QualityDataSyncer()
    await syncer.run()


if __name__ == '__main__':
    asyncio.run(main())