"""
统一数据串联层 — 采集编排

核心模块:
- collector: 调fetcher → 经adapter → 存storage
- scheduler: 定时任务

使用示例:
    from fetchers.orchestrator import DataCollector

    collector = DataCollector()
    collector.collect_todays_matches()
    collector.collect_odds_for_match("2026-05-25|arsenal|chelsea")
"""

from fetchers.orchestrator.collector import DataCollector

__all__ = ['DataCollector']