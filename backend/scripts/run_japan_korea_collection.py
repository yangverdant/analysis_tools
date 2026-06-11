"""
日韩联赛数据采集启动脚本
支持命令行参数指定联赛、数据源、日期范围
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.collect_japan_korea import JapanKoreaCollector, JAPAN_KOREA_LEAGUES


async def collect_specific_leagues(leagues: list, source: str, days: int):
    """采集指定联赛数据"""
    collector = JapanKoreaCollector()

    print(f"\n开始采集数据...")
    print(f"联赛: {', '.join(leagues)}")
    print(f"数据源: {source}")
    print(f"日期范围: 过去{days}天 ~ 未来{days}天")
    print("=" * 60)

    results = {}

    for league_key in leagues:
        if league_key not in JAPAN_KOREA_LEAGUES:
            print(f"未知联赛: {league_key}")
            continue

        league_config = JAPAN_KOREA_LEAGUES[league_key]
        print(f"\n采集 {league_config['name_cn']} ({league_config['name_en']})...")

        if source in ["apifootball", "all"]:
            print("  从 API-Football 获取...")
            result = await collector.collect_from_apifootball(league_key, days)
            results[f"{league_key}_api"] = result
            print(f"    获取: {result.get('matches_fetched', 0)} 场")
            print(f"    新增: {result.get('matches_inserted', 0)} 场")
            print(f"    更新: {result.get('matches_updated', 0)} 场")
            if result.get("errors"):
                print(f"    错误: {len(result['errors'])} 个")
            await asyncio.sleep(2)  # 避免请求过快

        if source in ["fbref", "all"]:
            print("  从 FBref 获取...")
            result = await collector.collect_from_fbref(league_key)
            results[f"{league_key}_fbref"] = result
            print(f"    比赛: {result.get('matches_fetched', 0)} 场")
            print(f"    积分榜: {result.get('standings_fetched', 0)} 条")
            if result.get("errors"):
                print(f"    错误: {len(result['errors'])} 个")
            await asyncio.sleep(3)  # FBref 反爬严格

    return results


def show_current_stats():
    """显示当前数据统计"""
    collector = JapanKoreaCollector()
    stats = collector.get_japan_korea_stats()

    print("\n" + "=" * 60)
    print("当前日韩联赛数据统计")
    print("=" * 60)

    total_matches = 0
    for league, data in stats.items():
        total_matches += data["matches"]
        print(f"\n{data['name']} ({league})")
        print(f"  比赛数: {data['matches']}")
        print(f"  球队数: {data['teams']}")
        if data['date_range']['from']:
            print(f"  日期范围: {data['date_range']['from']} ~ {data['date_range']['to']}")

    print(f"\n总计: {total_matches} 场比赛")


def main():
    parser = argparse.ArgumentParser(description="日韩联赛数据采集工具")
    parser.add_argument(
        "--leagues", "-l",
        nargs="+",
        default=["j1_league", "j2_league", "k1_league", "k2_league"],
        choices=list(JAPAN_KOREA_LEAGUES.keys()),
        help="要采集的联赛 (默认: J1, J2, K1, K2)"
    )
    parser.add_argument(
        "--source", "-s",
        default="all",
        choices=["all", "apifootball", "fbref"],
        help="数据源选择 (默认: all)"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=30,
        help="采集日期范围 (默认: 30天)"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="只显示当前统计信息"
    )

    args = parser.parse_args()

    if args.stats:
        show_current_stats()
        return

    # 显示当前统计
    show_current_stats()

    # 执行采集
    asyncio.run(collect_specific_leagues(args.leagues, args.source, args.days))

    # 显示更新后统计
    print("\n" + "=" * 60)
    print("采集完成！更新后统计:")
    show_current_stats()


if __name__ == "__main__":
    main()
