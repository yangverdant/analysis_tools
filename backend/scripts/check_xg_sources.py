"""
日韩联赛xG数据获取方案

StatsBomb开放数据不包含J联赛/K联赛，只有国家队世界杯数据
需要使用其他数据源获取俱乐部xG数据
"""

import asyncio
import aiohttp
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CONFIG_PATH = PROJECT_ROOT / "api_config.json"


async def check_xg_sources():
    """检查可用的xG数据源"""

    results = {}

    print("=" * 60)
    print("日韩联赛xG数据源检查")
    print("=" * 60)

    # 1. Sportmonks xG端点
    print("\n[1] Sportmonks xG数据...")

    config = json.load(open(CONFIG_PATH, encoding='utf-8'))
    token = config.get("apis", {}).get("sportmonks", {}).get("api_token", "")

    async with aiohttp.ClientSession(trust_env=False) as session:
        # 测试获取比赛xG数据
        url = "https://api.sportmonks.com/v3/football/fixtures"
        params = {
            "api_token": token,
            "include": "xG;participants",
            "filters": "leagueIds:55",  # K联赛1
            "limit": 5
        }

        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    fixtures = data.get("data", [])
                    results["sportmonks"] = {
                        "status": "success",
                        "count": len(fixtures),
                        "has_xg": False
                    }

                    for f in fixtures:
                        xg_data = f.get("xG", [])
                        if xg_data:
                            results["sportmonks"]["has_xg"] = True
                            print(f"  比赛 {f.get('id')}: 有xG数据")
                            print(f"    xG数据: {xg_data}")

                    if not results["sportmonks"]["has_xg"]:
                        print("  获取到比赛但无xG数据 (可能需要All-In计划)")
                elif resp.status == 403:
                    results["sportmonks"] = {"status": "forbidden", "note": "需要付费计划"}
                    print("  403禁止访问 - 需要付费计划")
                else:
                    results["sportmonks"] = {"status": "failed", "code": resp.status}
                    print(f"  失败: {resp.status}")
        except Exception as e:
            results["sportmonks"] = {"status": "error", "message": str(e)}
            print(f"  错误: {str(e)[:50]}")

    # 2. FBref xG页面
    print("\n[2] FBref xG数据...")

    async with aiohttp.ClientSession(trust_env=False) as session:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        url = "https://fbref.com/en/comps/55/K-League-1-Stats"

        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    # 检查是否包含xG数据
                    has_xg = "xG" in html or "Expected Goals" in html
                    results["fbref"] = {
                        "status": "success",
                        "has_xg": has_xg,
                        "content_length": len(html)
                    }
                    print(f"  成功获取页面 ({len(html)} bytes)")
                    print(f"  包含xG数据: {has_xg}")
                elif resp.status == 403:
                    results["fbref"] = {"status": "forbidden"}
                    print("  403禁止访问 - 反爬虫")
                else:
                    results["fbref"] = {"status": "failed", "code": resp.status}
                    print(f"  失败: {resp.status}")
        except Exception as e:
            results["fbref"] = {"status": "error", "message": str(e)}
            print(f"  错误: {str(e)[:50]}")

    # 3. Understat (有J联赛xG)
    print("\n[3] Understat数据源...")
    print("  Understat包含J联赛xG数据")
    print("  需要爬虫获取: https://understat.com/league/Japan")

    results["understat"] = {
        "status": "available",
        "url": "https://understat.com/league/Japan",
        "note": "需要爬虫实现"
    }

    # 4. 检查现有StatsBomb数据
    print("\n[4] 现有StatsBomb数据...")

    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()

    # 日本/韩国国家队xG
    cursor.execute('''
        SELECT COUNT(DISTINCT match_id)
        FROM statsbomb_shots
        WHERE team_name IN ('Japan', 'South Korea')
    ''')
    national_matches = cursor.fetchone()[0]

    # 总xG记录
    cursor.execute('SELECT COUNT(*) FROM statsbomb_shots WHERE xg IS NOT NULL')
    total_xg = cursor.fetchone()[0]

    conn.close()

    results["statsbomb"] = {
        "total_xg_records": total_xg,
        "japan_korea_matches": national_matches,
        "note": "仅国家队数据，无俱乐部数据"
    }
    print(f"  总xG记录: {total_xg}")
    print(f"  日本/韩国国家队比赛: {national_matches}场")
    print("  注: StatsBomb开放数据不包含J/K联赛俱乐部")

    # 5. 总结
    print("\n" + "=" * 60)
    print("xG数据获取方案总结")
    print("=" * 60)

    print("\n免费方案:")
    print("  1. FBref爬虫 - K联赛有xG，J联赛部分有")
    print("     需要解决403反爬问题")
    print("  2. Understat爬虫 - J联赛有完整xG")
    print("     URL: https://understat.com/league/Japan")

    print("\n付费方案:")
    print("  1. Sportmonks All-In计划 (€129/月)")
    print("     包含完整xG、xGA、npxG等")
    print("  2. API-Football付费 (€10/月起)")
    print("     部分比赛有xG数据")

    print("\n推荐:")
    print("  短期: 配置代理使用FBref爬虫获取K联赛xG")
    print("  长期: 升级Sportmonks获取完整xG+AI预测")

    return results


async def fetch_fbref_xg_sample():
    """尝试从FBref获取xG数据示例"""

    import requests
    from bs4 import BeautifulSoup

    print("\n尝试从FBref获取K联赛xG数据...")

    session = requests.Session()
    session.trust_env = False
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # K联赛赛程页面
    url = "https://fbref.com/en/comps/55/schedule/K-League-1-Scores-and-Fixtures"

    try:
        resp = session.get(url, headers=headers, timeout=30, proxies={"http": None, "https": None})

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")

            # 查找赛程表
            tables = soup.find_all("table")

            for table in tables:
                # 检查是否有xG列
                headers_row = table.find("tr")
                if headers_row:
                    header_texts = [th.get_text() for th in headers_row.find_all(["th", "td"])]
                    print(f"  表头: {header_texts[:10]}")

                    if "xG" in str(header_texts):
                        print("  找到xG数据!")
                        # 解析数据...
                        return True

            print("  未找到xG列")
            return False

        else:
            print(f"  HTTP {resp.status_code}")
            return False

    except Exception as e:
        print(f"  错误: {str(e)[:100]}")
        return False


async def main():
    await check_xg_sources()
    await fetch_fbref_xg_sample()


if __name__ == "__main__":
    asyncio.run(main())
