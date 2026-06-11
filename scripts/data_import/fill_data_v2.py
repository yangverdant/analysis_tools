#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补充缺失数据脚本 V2
- 球队Logo
- 场地信息
- 中文名翻译
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


class DataFillerV2:
    """数据补充器 V2"""

    def __init__(self):
        self.config = self._load_config()
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self.stats = {
            'logos_updated': 0,
            'venues_updated': 0,
            'team_names_translated': 0,
            'player_names_translated': 0,
            'errors': 0
        }

    def _load_config(self) -> dict:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def fill_team_details(self):
        """从football-data.org补充球队详情"""
        print("\n" + "=" * 60)
        print("Filling Team Details")
        print("=" * 60)

        api_config = self.config.get('apis', {}).get('football_data_org', {})
        base_url = api_config.get('base_url', 'https://api.football-data.org/v4')
        api_token = api_config.get('api_token', '')

        headers = {'X-Auth-Token': api_token}

        # 获取需要更新的球队
        self.cursor.execute("""
            SELECT team_id, name_en, fd_team_id, tla
            FROM teams
            WHERE logo_url IS NULL OR stadium IS NULL
            ORDER BY team_id
            LIMIT 50
        """)
        teams = self.cursor.fetchall()
        print(f"  Teams to process: {len(teams)}")

        async with aiohttp.ClientSession() as session:
            for team in teams:
                try:
                    fd_id = team['fd_team_id']
                    if not fd_id:
                        continue

                    url = f"{base_url}/teams/{fd_id}"

                    async with session.get(url, headers=headers, timeout=30) as response:
                        if response.status != 200:
                            continue

                        data = await response.json()

                        crest = data.get('crest')
                        venue = data.get('venue')
                        founded = data.get('founded')

                        self.cursor.execute("""
                            UPDATE teams SET
                                logo_url = COALESCE(logo_url, ?),
                                stadium = COALESCE(stadium, ?),
                                founded_year = COALESCE(founded_year, ?),
                                updated_at = datetime('now')
                            WHERE team_id = ?
                        """, (crest, venue, founded, team['team_id']))

                        if crest:
                            self.stats['logos_updated'] += 1
                        if venue:
                            self.stats['venues_updated'] += 1

                        self.conn.commit()
                        print(f"    Updated: {team['name_en']}")

                        await asyncio.sleep(7)

                except Exception as e:
                    self.stats['errors'] += 1
                    continue

        print(f"  Logos: {self.stats['logos_updated']}, Venues: {self.stats['venues_updated']}")

    async def translate_names(self):
        """翻译中文名"""
        print("\n" + "=" * 60)
        print("Translating Names")
        print("=" * 60)

        api_config = self.config.get('apis', {}).get('deepseek', {})
        base_url = api_config.get('base_url', 'https://spanagent.xyz/v1')
        api_key = api_config.get('api_key', '')
        model = api_config.get('model', 'deepseek-v4-pro')

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        # 翻译球队名
        self.cursor.execute("SELECT team_id, name_en FROM teams WHERE name_cn IS NULL LIMIT 100")
        teams = self.cursor.fetchall()
        print(f"  Teams to translate: {len(teams)}")

        if teams:
            names = [t['name_en'] for t in teams]
            prompt = f"""翻译以下足球队名为中文，每行一个，格式：原名:中文名

{chr(10).join(names[:50])}

只返回翻译，不要解释。"""

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        f"{base_url}/chat/completions",
                        headers=headers,
                        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3},
                        timeout=60
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            content = result['choices'][0]['message']['content']

                            for line in content.strip().split('\n'):
                                if ':' in line or '：' in line:
                                    parts = re.split(r'[:：]', line, 1)
                                    if len(parts) == 2:
                                        self.cursor.execute(
                                            "UPDATE teams SET name_cn = ?, updated_at = datetime('now') WHERE name_en = ? AND name_cn IS NULL",
                                            (parts[1].strip(), parts[0].strip())
                                        )
                                        if self.cursor.rowcount > 0:
                                            self.stats['team_names_translated'] += 1

                            self.conn.commit()
                            print(f"  Teams translated: {self.stats['team_names_translated']}")
                except Exception as e:
                    print(f"  Error: {e}")
                    self.stats['errors'] += 1

        # 翻译球员名
        self.cursor.execute("SELECT player_id, name_en FROM players WHERE name_cn IS NULL LIMIT 200")
        players = self.cursor.fetchall()
        print(f"  Players to translate: {len(players)}")

        if players:
            names = [p['name_en'] for p in players]
            prompt = f"""翻译以下足球运动员名为中文，每行一个，格式：原名:中文名

{chr(10).join(names[:50])}

只返回翻译，不要解释。"""

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        f"{base_url}/chat/completions",
                        headers=headers,
                        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3},
                        timeout=60
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            content = result['choices'][0]['message']['content']

                            for line in content.strip().split('\n'):
                                if ':' in line or '：' in line:
                                    parts = re.split(r'[:：]', line, 1)
                                    if len(parts) == 2:
                                        self.cursor.execute(
                                            "UPDATE players SET name_cn = ?, updated_at = datetime('now') WHERE name_en = ? AND name_cn IS NULL",
                                            (parts[1].strip(), parts[0].strip())
                                        )
                                        if self.cursor.rowcount > 0:
                                            self.stats['player_names_translated'] += 1

                            self.conn.commit()
                            print(f"  Players translated: {self.stats['player_names_translated']}")
                except Exception as e:
                    print(f"  Error: {e}")
                    self.stats['errors'] += 1

    async def run(self):
        print("=" * 60)
        print(f"Data Filling V2 - {datetime.now()}")
        print("=" * 60)

        try:
            await self.fill_team_details()
            await self.translate_names()

            print("\n" + "=" * 60)
            print("Results")
            print("=" * 60)
            print(f"Logos: {self.stats['logos_updated']}")
            print(f"Venues: {self.stats['venues_updated']}")
            print(f"Team names: {self.stats['team_names_translated']}")
            print(f"Player names: {self.stats['player_names_translated']}")
            print(f"Errors: {self.stats['errors']}")

        finally:
            self.conn.close()


async def main():
    filler = DataFillerV2()
    await filler.run()


if __name__ == '__main__':
    asyncio.run(main())