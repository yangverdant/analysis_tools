#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
匹配球队ID并补充数据
"""

import os
import sys
import sqlite3
import json
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / 'data' / 'football_v2.db'
CONFIG_PATH = PROJECT_ROOT / 'api_config.json'


async def match_team_ids():
    """从football-data.org获取球队列表并匹配ID"""
    print("=" * 60)
    print("Matching Team IDs from football-data.org")
    print("=" * 60)

    config = json.load(open(CONFIG_PATH, 'r', encoding='utf-8'))
    api_config = config.get('apis', {}).get('football_data_org', {})
    base_url = api_config.get('base_url', 'https://api.football-data.org/v4')
    api_token = api_config.get('api_token', '')

    headers = {'X-Auth-Token': api_token}

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 获取所有联赛的球队
    competitions = ['PL', 'PD', 'BL1', 'SA', 'FL1', 'CL', 'ELC', 'DED', 'PPL']

    matched = 0
    logos_updated = 0
    venues_updated = 0

    async with aiohttp.ClientSession() as session:
        for code in competitions:
            try:
                print(f"\n  Processing {code}...")

                # 获取联赛的球队列表
                url = f"{base_url}/competitions/{code}/teams"

                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        print(f"    Error: {response.status}")
                        continue

                    data = await response.json()
                    teams = data.get('teams', [])

                    print(f"    Teams from API: {len(teams)}")

                    for team_data in teams:
                        fd_id = team_data.get('id')
                        name = team_data.get('name')
                        short_name = team_data.get('shortName')
                        tla = team_data.get('tla')
                        crest = team_data.get('crest')
                        venue = team_data.get('venue')
                        founded = team_data.get('founded')

                        # 尝试匹配数据库中的球队
                        cursor.execute("""
                            SELECT team_id FROM teams
                            WHERE name_en = ? OR name_en = ? OR tla = ?
                        """, (name, short_name, tla))

                        result = cursor.fetchone()

                        if result:
                            team_id = result[0]

                            # 更新球队信息
                            cursor.execute("""
                                UPDATE teams SET
                                    fd_team_id = ?,
                                    logo_url = COALESCE(logo_url, ?),
                                    stadium = COALESCE(stadium, ?),
                                    founded_year = COALESCE(founded_year, ?),
                                    short_name = COALESCE(short_name, ?),
                                    updated_at = datetime('now')
                                WHERE team_id = ?
                            """, (fd_id, crest, venue, founded, short_name, team_id))

                            matched += 1
                            if crest:
                                logos_updated += 1
                            if venue:
                                venues_updated += 1

                            print(f"      Matched: {name} -> team_id={team_id}")

                    conn.commit()

                    await asyncio.sleep(7)  # Rate limit

            except Exception as e:
                print(f"    Error: {e}")
                continue

    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    print(f"Teams matched: {matched}")
    print(f"Logos updated: {logos_updated}")
    print(f"Venues updated: {venues_updated}")

    conn.close()


async def translate_chinese_names():
    """翻译中文名"""
    print("\n" + "=" * 60)
    print("Translating Chinese Names")
    print("=" * 60)

    config = json.load(open(CONFIG_PATH, 'r', encoding='utf-8'))
    api_config = config.get('apis', {}).get('deepseek', {})
    base_url = api_config.get('base_url', 'https://spanagent.xyz/v1')
    api_key = api_config.get('api_key', '')
    model = api_config.get('model', 'deepseek-v4-pro')

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 翻译球队名
    cursor.execute("SELECT team_id, name_en FROM teams WHERE name_cn IS NULL LIMIT 100")
    teams = cursor.fetchall()
    print(f"  Teams to translate: {len(teams)}")

    team_translated = 0
    player_translated = 0

    if teams:
        names = [t[1] for t in teams]
        prompt = f"""翻译以下足球队名为中文，每行一个，格式：原名:中文名

{chr(10).join(names[:50])}

只返回翻译结果。"""

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

                        import re
                        for line in content.strip().split('\n'):
                            if ':' in line or '：' in line:
                                parts = re.split(r'[:：]', line, 1)
                                if len(parts) == 2:
                                    cursor.execute(
                                        "UPDATE teams SET name_cn = ?, updated_at = datetime('now') WHERE name_en = ? AND name_cn IS NULL",
                                        (parts[1].strip(), parts[0].strip())
                                    )
                                    if cursor.rowcount > 0:
                                        team_translated += 1

                        conn.commit()
                        print(f"  Teams translated: {team_translated}")
            except Exception as e:
                print(f"  Translation error: {e}")

    # 翻译球员名
    cursor.execute("SELECT player_id, name_en FROM players WHERE name_cn IS NULL LIMIT 200")
    players = cursor.fetchall()
    print(f"  Players to translate: {len(players)}")

    if players:
        names = [p[1] for p in players]
        prompt = f"""翻译以下足球运动员名为中文，每行一个，格式：原名:中文名

{chr(10).join(names[:50])}

只返回翻译结果。"""

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

                        import re
                        for line in content.strip().split('\n'):
                            if ':' in line or '：' in line:
                                parts = re.split(r'[:：]', line, 1)
                                if len(parts) == 2:
                                    cursor.execute(
                                        "UPDATE players SET name_cn = ?, updated_at = datetime('now') WHERE name_en = ? AND name_cn IS NULL",
                                        (parts[1].strip(), parts[0].strip())
                                    )
                                    if cursor.rowcount > 0:
                                        player_translated += 1

                        conn.commit()
                        print(f"  Players translated: {player_translated}")
            except Exception as e:
                print(f"  Translation error: {e}")

    conn.close()

    print("\n" + "=" * 60)
    print(f"Total: Teams={team_translated}, Players={player_translated}")
    print("=" * 60)


async def main():
    await match_team_ids()
    await translate_chinese_names()


if __name__ == '__main__':
    asyncio.run(main())