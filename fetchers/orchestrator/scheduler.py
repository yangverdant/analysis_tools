"""
自动采集调度器

功能:
- 未开始比赛: 定时更新赔率/阵容/伤病
- 进行中比赛: 高频更新比分
- 已完结比赛: 只采集一次，数据固定

使用示例:
    from fetchers.orchestrator.scheduler import FetchScheduler

    scheduler = FetchScheduler()
    scheduler.run_daily()      # 每日全量采集
    scheduler.run_live()       # 实时更新
"""

import logging
from datetime import date as _date, datetime, timedelta
from typing import Dict, List, Optional

from fetchers.orchestrator.collector import DataCollector
from fetchers.storage.crud import UnifiedStorage

logger = logging.getLogger(__name__)


class FetchScheduler:
    """自动采集调度器"""

    def __init__(self, db_path: str = None):
        self.collector = DataCollector(db_path)
        self.storage = self.collector.storage

    def run_daily(self) -> Dict[str, int]:
        """每日全量采集

        流程:
        1. 获取未来7天赛程
        2. 采集积分榜
        3. 采集新闻
        4. 对今日比赛采集赔率+xG+天气
        """
        logger.info("===== 开始每日全量采集 =====")
        results = {}

        # 1. 赛程
        today = str(_date.today())
        week_later = str(_date.today() + timedelta(days=7))
        results.update(self.collector.collect_fixtures(today, week_later))

        # 2. 主要联赛积分榜
        major_leagues = [
            "premier_league", "la_liga", "bundesliga",
            "serie_a", "ligue_1"
        ]
        for league in major_leagues:
            try:
                standings = self.collector.collect_standings(league)
                results.update(standings)
            except Exception as e:
                logger.warning(f"积分榜采集失败 [{league}]: {e}")

        # 3. 新闻
        results.update(self.collector.collect_news())

        # 4. 今日比赛的上下文
        today_matches = self.storage.get_matches_by_date(today)
        for match in today_matches[:20]:
            try:
                context = self.collector.collect_match_context(match["match_key"])
                for k, v in context.items():
                    results[f"context_{k}"] = results.get(f"context_{k}", 0) + v
            except Exception as e:
                logger.warning(f"上下文采集失败 [{match['match_key']}]: {e}")

        logger.info(f"===== 每日采集完成: {sum(results.values())} 条 =====")
        return results

    def run_live(self) -> Dict[str, int]:
        """实时比分更新（高频，5分钟级别）"""
        results = {}

        live_sources = [
            ("apifootball", "get_livescores"),
            ("espn", "get_livescores"),
            ("scores365", "get_livescores"),
        ]

        for fetcher_name, func_name in live_sources:
            try:
                count = self.collector.fetch_and_store(fetcher_name, func_name)
                results[fetcher_name] = count
            except Exception as e:
                logger.warning(f"实时采集失败 [{fetcher_name}]: {e}")

        return results

    def run_pre_match(self) -> Dict[str, int]:
        """赛前数据采集（赛前2小时）

        流程:
        1. 获取今日未开始比赛
        2. 采集赔率
        3. 采集阵容/伤病
        4. 采集天气
        """
        results = {}
        today = str(_date.today())
        upcoming = self.storage.get_upcoming_matches(days=1)

        for match in upcoming:
            match_key = match["match_key"]
            try:
                # 赔率
                odds = self.collector.collect_odds_for_match(match_key)
                for k, v in odds.items():
                    results[k] = results.get(k, 0) + v

                # 上下文
                context = self.collector.collect_match_context(match_key)
                for k, v in context.items():
                    results[k] = results.get(k, 0) + v
            except Exception as e:
                logger.warning(f"赛前采集失败 [{match_key}]: {e}")

        return results

    def run_post_match(self) -> Dict[str, int]:
        """赛后数据采集（比赛结束后）

        已完结比赛数据固定，只采集一次
        - 最终比分+统计
        - xG数据
        """
        results = {}

        # 获取最近完成的比赛（status=finished 或有比分）
        matches = self.storage.search_matches(
            date_from=str(_date.today() - timedelta(days=1)),
            date_to=str(_date.today()),
            status="finished",
            limit=50
        )

        for match in matches:
            match_key = match["match_key"]
            # 检查是否已有详细数据
            existing = self.storage.get_match_data(match_key, data_type="match")
            if existing:
                continue

            try:
                context = self.collector.collect_match_context(match_key)
                for k, v in context.items():
                    results[k] = results.get(k, 0) + v
            except Exception as e:
                logger.warning(f"赛后采集失败 [{match_key}]: {e}")

        return results