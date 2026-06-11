#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从API同步球员统计数据
"""

import os
import sys
import sqlite3
import json
import asyncio
import aiohttp
import re
from pathlib import Path
from datetime import datetime

# Windows编码处理
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / 'data' / 'football_v2.db'
CONFIG_PATH = PROJECT_ROOT / 'api_config.json'


class PlayerDataSyncer:
    """球员数据同步器"""

    def __init__(self):
        self.config = self._load_config()
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self.stats = {
            'players_added': 0,
            'players_updated': 0,
            'stats_added': 0,
            'errors': 0
        }

    def _load_config(self) -> dict:
        """加载配置文件"""
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def sync_scorers(self):
        """同步射手榜数据"""
        print("\n" + "=" * 60)
        print("Syncing Scorers from football-data.org")
        print("=" * 60)

        api_config = self.config.get('apis', {}).get('football_data_org', {})
        base_url = api_config.get('base_url', 'https://api.football-data.org/v4')
        api_token = api_config.get('api_token', '')

        headers = {'X-Auth-Token': api_token}

        competitions = ['PL', 'PD', 'BL1', 'SA', 'FL1', 'CL']

        async with aiohttp.ClientSession() as session:
            for code in competitions:
                try:
                    print(f"\n  Processing {code}...")

                    url = f"{base_url}/competitions/{code}/scorers"
                    params = {'limit': 50}

                    async with session.get(url, headers=headers, params=params, timeout=30) as response:
                        if response.status != 200:
                            print(f"    Error: {response.status}")
                            continue

                        data = await response.json()
                        scorers = data.get('scorers', [])

                        print(f"    Scorers: {len(scorers)}")

                        for scorer in scorers:
                            player = scorer.get('player', {})
                            team = scorer.get('team', {})

                            player_name = player.get('name')
                            if not player_name:
                                continue

                            # 查找或创建球员
                            self.cursor.execute("SELECT player_id FROM players WHERE name_en = ?", (player_name,))
                            result = self.cursor.fetchone()

                            if result:
                                player_id = result[0]
                            else:
                                player_code = re.sub(r'[^a-zA-Z0-9]', '_', player_name.lower())[:30]
                                self.cursor.execute("""
                                    INSERT INTO players (player_code, name_en, nationality, position_main, status, created_at)
                                    VALUES (?, ?, ?, ?, 'active', datetime('now'))
                                """, (player_code, player_name, player.get('nationality'), player.get('position')))
                                player_id = self.cursor.lastrowid
                                self.stats['players_added'] += 1

                            # 查找球队
                            team_name = team.get('name')
                            self.cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (team_name,))
                            team_result = self.cursor.fetchone()

                            if team_result:
                                team_id = team_result[0]
                                # 更新球员的球队信息（如果需要）
                                # 注意：players表没有team_id字段，需要通过其他方式关联

                        self.conn.commit()

                        await asyncio.sleep(7)  # Rate limit

                except Exception as e:
                    print(f"    Error: {e}")
                    self.stats['errors'] += 1
                    continue

    async def sync_team_squads(self):
        """同步球队阵容数据"""
        print("\n" + "=" * 60)
        print("Syncing Team Squads from football-data.org")
        print("=" * 60)

        api_config = self.config.get('apis', {}).get('football_data_org', {})
        base_url = api_config.get('base_url', 'https://api.football-data.org/v4')
        api_token = api_config.get('api_token', '')

        headers = {'X-Auth-Token': api_token}

        # 获取主要球队ID
        self.cursor.execute("SELECT team_id, name_en, fd_team_id FROM teams WHERE fd_team_id IS NOT NULL LIMIT 20")
        teams = self.cursor.fetchall()

        if not teams:
            # 尝试从英超球队开始
            self.cursor.execute("SELECT team_id, name_en FROM teams WHERE name_en LIKE '%United%' OR name_en LIKE '%City%' OR name_en LIKE '%Arsenal%' LIMIT 10")
            teams = self.cursor.fetchall()

        print(f"  Found {len(teams)} teams to sync")

        async with aiohttp.ClientSession() as session:
            for team in teams:
                try:
                    team_id = team['team_id']
                    team_name = team['name_en']
                    fd_team_id = team['fd_team_id']

                    print(f"\n  Processing {team_name}...")

                    # 使用football-data.org的team ID
                    if fd_team_id:
                        url = f"{base_url}/teams/{fd_team_id}"
                    else:
                        # 尝试通过名称匹配
                        continue

                    async with session.get(url, headers=headers, timeout=30) as response:
                        if response.status != 200:
                            print(f"    Error: {response.status}")
                            continue

                        data = await response.json()
                        squad = data.get('squad', [])

                        print(f"    Squad size: {len(squad)}")

                        for player in squad:
                            player_name = player.get('name')
                            if not player_name:
                                continue

                            # 查找或创建球员
                            self.cursor.execute("SELECT player_id FROM players WHERE name_en = ?", (player_name,))
                            result = self.cursor.fetchone()

                            if result:
                                player_id = result[0]
                                # 更新球员信息
                                self.cursor.execute("""
                                    UPDATE players SET
                                        nationality = COALESCE(nationality, ?),
                                        position_main = COALESCE(position_main, ?),
                                        updated_at = datetime('now')
                                    WHERE player_id = ?
                                """, (player.get('nationality'), player.get('position'), player_id))
                                self.stats['players_updated'] += 1
                            else:
                                player_code = re.sub(r'[^a-zA-Z0-9]', '_', player_name.lower())[:30]
                                self.cursor.execute("""
                                    INSERT INTO players (player_code, name_en, nationality, position_main, status, created_at)
                                    VALUES (?, ?, ?, ?, 'active', datetime('now'))
                                """, (player_code, player_name, player.get('nationality'), player.get('position')))
                                player_id = self.cursor.lastrowid
                                self.stats['players_added'] += 1

                        self.conn.commit()

                        await asyncio.sleep(7)  # Rate limit

                except Exception as e:
                    print(f"    Error: {e}")
                    self.stats['errors'] += 1
                    continue

    async def run(self):
        """运行所有同步任务"""
        print("=" * 60)
        print("Player Data Sync Started")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        try:
            await self.sync_scorers()
            await self.sync_team_squads()

            print("\n" + "=" * 60)
            print("Sync Statistics")
            print("=" * 60)
            print(f"Players Added: {self.stats['players_added']}")
            print(f"Players Updated: {self.stats['players_updated']}")
            print(f"Errors: {self.stats['errors']}")

            # 最终统计
            self.cursor.execute("SELECT COUNT(*) FROM players")
            print(f"Total Players: {self.cursor.fetchone()[0]}")

        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.conn.close()


async def main():
    syncer = PlayerDataSyncer()
    await syncer.run()


if __name__ == '__main__':
    asyncio.run(main())