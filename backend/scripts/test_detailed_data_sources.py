"""
日韩联赛详细数据补充方案
使用多种数据源获取赔率、球员、球队城市等信息
"""

import asyncio
import aiohttp
import sqlite3
import json
import logging
import os
from datetime import datetime
from pathlib import Path

# 禁用代理
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CONFIG_PATH = PROJECT_ROOT / "api_config.json"


async def test_all_data_sources():
    """测试所有数据源对详细数据的支持"""

    results = {}

    # 1. 测试API-Football详细数据端点
    print("\n[1] 测试 API-Football 详细数据端点...")

    config = json.load(open(CONFIG_PATH, encoding='utf-8'))
    api_key = config.get("apis", {}).get("apifootball", {}).get("api_key", "")
    base_url = "https://apiv3.apifootball.com"

    async with aiohttp.ClientSession(trust_env=False) as session:
        # 测试赔率
        params = {"action": "get_odds", "APIkey": api_key, "league_id": 98}
        async with session.get(f"{base_url}/", params=params) as resp:
            data = await resp.json()
            results["apifootball_odds"] = {
                "status": "success" if isinstance(data, list) else "failed",
                "count": len(data) if isinstance(data, list) else 0,
                "sample": data[0] if isinstance(data, list) and data else None
            }
            print(f"  赔率端点: {results['apifootball_odds']['count']} 条")

        await asyncio.sleep(1)

        # 测试球队阵容
        params = {"action": "get_squad", "APIkey": api_key, "team_id": 2283}  # 测试一个已知球队ID
        async with session.get(f"{base_url}/", params=params) as resp:
            data = await resp.json()
            results["apifootball_squad"] = {
                "status": "success" if isinstance(data, list) else "failed",
                "count": len(data) if isinstance(data, list) else 0
            }
            print(f"  球队阵容端点: {results['apifootball_squad']['count']} 人")

        await asyncio.sleep(1)

        # 测试比赛统计
        params = {"action": "get_statistics", "APIkey": api_key, "match_id": 88237}
        async with session.get(f"{base_url}/", params=params) as resp:
            data = await resp.json()
            results["apifootball_stats"] = {
                "status": "success" if isinstance(data, dict) else "failed",
                "has_data": bool(data) if isinstance(data, dict) else False
            }
            print(f"  比赛统计端点: {results['apifootball_stats']['has_data']}")

    # 2. 测试TheSportsDB球队信息
    print("\n[2] 测试 TheSportsDB 球队信息...")

    async with aiohttp.ClientSession(trust_env=False) as session:
        url = "https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t=Yokohama"
        async with session.get(url) as resp:
            data = await resp.json()
            teams = data.get("teams", [])
            results["thesportsdb_teams"] = {
                "count": len(teams),
                "sample": teams[0] if teams else None
            }
            if teams:
                team = teams[0]
                print(f"  球队: {team.get('strTeam')}")
                print(f"  球场: {team.get('strStadium')}")
                print(f"  城市: {team.get('strStadiumLocation')}")
                print(f"  容量: {team.get('intStadiumCapacity')}")
                print(f"  成立: {team.get('intFormedYear')}")

    # 3. 测试365Scores实时数据
    print("\n[3] 测试 365Scores 实时数据...")

    async with aiohttp.ClientSession(trust_env=False) as session:
        url = "https://webws.365scores.com/web"
        params = {
            "action": "2",
            "langId": "1",
            "timezoneName": "Asia/Tokyo",
            "userCountryId": "108",
            "competitors": "39",  # K联赛
            "appTypeId": "1"
        }
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                results["365scores"] = {"status": "success", "has_data": bool(data)}
                print(f"  实时数据: 成功获取")
            else:
                results["365scores"] = {"status": "failed"}
                print(f"  实时数据: 失败 ({resp.status})")

    # 4. 测试RapidAPI赔率
    print("\n[4] 测试 RapidAPI 赔率数据...")

    rapidapi_key = config.get("rapidapi", {}).get("key", "")
    if rapidapi_key:
        async with aiohttp.ClientSession(trust_env=False) as session:
            headers = {"X-RapidAPI-Key": rapidapi_key}
            url = "https://odds-feed.p.rapidapi.com/odds"
            params = {"sport": "soccer", "league": "japan-j1-league"}
            try:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results["rapidapi_odds"] = {"status": "success", "count": len(data) if isinstance(data, list) else 0}
                        print(f"  赔率数据: {results['rapidapi_odds']['count']} 条")
                    else:
                        results["rapidapi_odds"] = {"status": "failed", "code": resp.status}
                        print(f"  赔率数据: 失败 ({resp.status})")
            except Exception as e:
                results["rapidapi_odds"] = {"status": "error", "message": str(e)}
                print(f"  赔率数据: 错误 - {str(e)[:50]}")
    else:
        results["rapidapi_odds"] = {"status": "no_key"}
        print("  赔率数据: 未配置Key")

    # 5. 测试SofaScore爬虫
    print("\n[5] 测试 SofaScore API...")

    async with aiohttp.ClientSession(trust_env=False) as session:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        url = "https://api.sofascore.com/api/v1/unique-tournament/19/team-events"  # 测试端点
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results["sofascore"] = {"status": "success", "has_data": bool(data)}
                    print("  SofaScore: 成功")
                else:
                    results["sofascore"] = {"status": "failed", "code": resp.status}
                    print(f"  SofaScore: 失败 ({resp.status})")
        except Exception as e:
            results["sofascore"] = {"status": "error", "message": str(e)[:50]}
            print(f"  SofaScore: 错误")

    # 保存测试结果
    print("\n" + "=" * 60)
    print("数据源测试结果汇总")
    print("=" * 60)

    for source, result in results.items():
        status = "[OK]" if result.get("status") == "success" or result.get("count", 0) > 0 else "[--]"
        print(f"{status} {source}: {result}")

    # 推荐数据源
    print("\n推荐数据源优先级:")
    print("  [赔率] API-Football免费无数据，需RapidAPI付费")
    print("  [球队详情] TheSportsDB (免费，有球场/城市信息)")
    print("  [球员] API-Football getSquad (需已知team_id)")
    print("  [实时] 365Scores (免费)")

    return results


async def collect_from_thesportsdb():
    """从TheSportsDB采集球队详细信息"""

    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 获取所有日韩球队名称
    cursor.execute("""
        SELECT team_id, name_en, country
        FROM teams
        WHERE country IN ('Japan', 'South Korea')
    """)
    teams = cursor.fetchall()

    print(f"\n从TheSportsDB采集 {len(teams)} 个球队的详细信息...")

    updated = 0
    async with aiohttp.ClientSession(trust_env=False) as session:
        for team in teams:
            try:
                # 搜索球队
                url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={team['name_en'].replace(' ', '%20')}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tsdb_teams = data.get("teams", [])

                        if tsdb_teams:
                            tsdb_team = tsdb_teams[0]

                            # 更新球队信息
                            cursor.execute("""
                                UPDATE teams SET
                                    stadium = ?,
                                    stadium_capacity = ?,
                                    founded_year = ?,
                                    logo_url = ?,
                                    updated_at = ?
                                WHERE team_id = ?
                            """, (
                                tsdb_team.get("strStadium"),
                                tsdb_team.get("intStadiumCapacity"),
                                tsdb_team.get("intFormedYear"),
                                tsdb_team.get("strTeamBadge"),
                                datetime.now().isoformat(),
                                team["team_id"]
                            ))

                            if cursor.rowcount > 0:
                                updated += 1
                                logger.info(f"更新 {team['name_en']}: {tsdb_team.get('strStadium')}")

                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"采集 {team['name_en']} 失败: {e}")

    conn.commit()
    conn.close()

    print(f"更新了 {updated} 个球队的详细信息")
    return updated


async def main():
    """主函数"""

    print("=" * 60)
    print("日韩联赛详细数据采集")
    print("=" * 60)

    # 测试所有数据源
    await test_all_data_sources()

    # 使用TheSportsDB采集球队详情
    await collect_from_thesportsdb()

    # 显示最终数据质量
    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()

    print("\n最终数据质量:")
    cursor.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN stadium IS NOT NULL THEN 1 ELSE 0 END) as with_stadium
        FROM teams WHERE country IN ('Japan', 'South Korea')
    """)
    row = cursor.fetchone()
    print(f"  球队: {row[0]}个，有球场信息: {row[1]}个")

    conn.close()


if __name__ == "__main__":
    asyncio.run(main())