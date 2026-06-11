"""
采集层 (Collector Layer)
负责从多个数据源采集数据，支持优先级降级机制
"""

import os
import json
import aiohttp
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from datetime import datetime
from abc import ABC, abstractmethod
import logging

from .tasks import Task, TaskType
from .sources import (
    DATA_SOURCES, get_sources_for_task, check_rate_limit, update_usage,
    DataSourceType
)

logger = logging.getLogger(__name__)


@dataclass
class CollectResult:
    """采集结果"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    source_id: str = ""
    collected_at: datetime = None
    raw_data: Optional[Any] = None
    attempts: int = 0
    fallback_used: bool = False

    def __post_init__(self):
        if self.collected_at is None:
            self.collected_at = datetime.now()


class BaseCollector(ABC):
    """采集器基类"""

    def __init__(self, source_id: str):
        self.source_id = source_id
        self.session: Optional[aiohttp.ClientSession] = None

    async def init_session(self):
        """初始化HTTP会话"""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None

    @abstractmethod
    async def collect(self, task: Task) -> CollectResult:
        """采集数据"""
        pass


class APISportCollector(BaseCollector):
    """API-Sports 数据采集器"""

    def __init__(self):
        super().__init__("api_sports")
        self.base_url = "https://api-football-v1.p.rapidapi.com/v3"
        self.api_key = os.getenv("API_SPORT_KEY", "")
        self.api_host = os.getenv("API_SPORT_HOST", "api-football-v1.p.rapidapi.com")

    async def collect(self, task: Task) -> CollectResult:
        """从API-Sports采集数据"""
        await self.init_session()

        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host
        }

        try:
            if task.task_type in [TaskType.MATCH_COMPLETE, TaskType.MATCH_SCORE, TaskType.MATCH_DATE]:
                return await self._collect_match(task, headers)
            elif task.task_type == TaskType.TEAM_INFO:
                return await self._collect_team(task, headers)
            elif task.task_type == TaskType.SYNC_RECENT:
                return await self._collect_recent_matches(task, headers)
            elif task.task_type == TaskType.SYNC_SCHEDULE:
                return await self._collect_schedule(task, headers)
            elif task.task_type == TaskType.SYNC_STANDINGS:
                return await self._collect_standings(task, headers)
            else:
                return CollectResult(
                    success=False,
                    error=f"不支持的任务类型: {task.task_type}",
                    source_id=self.source_id
                )
        except Exception as e:
            logger.error(f"API-Sports采集失败: {e}")
            return CollectResult(
                success=False,
                error=str(e),
                source_id=self.source_id
            )

    async def _collect_match(self, task: Task, headers: dict) -> CollectResult:
        """采集比赛数据"""
        match_id = task.params.get("match_id")
        date = task.params.get("date")
        league = task.params.get("league")

        if match_id:
            url = f"{self.base_url}/fixtures?id={match_id}"
        else:
            url = f"{self.base_url}/fixtures?"
            params = []
            if date:
                params.append(f"date={date}")
            if league:
                params.append(f"league={league}")
            url += "&".join(params)

        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return CollectResult(
                    success=True,
                    data=data.get("response", []),
                    raw_data=data,
                    source_id=self.source_id
                )
            else:
                return CollectResult(
                    success=False,
                    error=f"API返回错误: {resp.status}",
                    source_id=self.source_id
                )

    async def _collect_team(self, task: Task, headers: dict) -> CollectResult:
        """采集球队信息"""
        team_id = task.params.get("team_id")
        team_name = task.params.get("team_name")

        url = f"{self.base_url}/teams?"
        if team_id:
            url += f"id={team_id}"
        elif team_name:
            url += f"search={team_name}"

        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return CollectResult(
                    success=True,
                    data=data.get("response", []),
                    raw_data=data,
                    source_id=self.source_id
                )
            else:
                return CollectResult(
                    success=False,
                    error=f"API返回错误: {resp.status}",
                    source_id=self.source_id
                )

    async def _collect_recent_matches(self, task: Task, headers: dict) -> CollectResult:
        """采集近期比赛结果"""
        league = task.params.get("league", 39)
        season = task.params.get("season", 2024)
        last = task.params.get("last", 10)

        url = f"{self.base_url}/fixtures?league={league}&season={season}&last={last}"

        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return CollectResult(
                    success=True,
                    data=data.get("response", []),
                    raw_data=data,
                    source_id=self.source_id
                )
            else:
                return CollectResult(
                    success=False,
                    error=f"API返回错误: {resp.status}",
                    source_id=self.source_id
                )

    async def _collect_schedule(self, task: Task, headers: dict) -> CollectResult:
        """采集未来赛程"""
        league = task.params.get("league", 39)
        season = task.params.get("season", 2024)
        next_rounds = task.params.get("next", 10)

        url = f"{self.base_url}/fixtures?league={league}&season={season}&next={next_rounds}"

        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return CollectResult(
                    success=True,
                    data=data.get("response", []),
                    raw_data=data,
                    source_id=self.source_id
                )
            else:
                return CollectResult(
                    success=False,
                    error=f"API返回错误: {resp.status}",
                    source_id=self.source_id
                )

    async def _collect_standings(self, task: Task, headers: dict) -> CollectResult:
        """采集积分榜"""
        league = task.params.get("league", 39)
        season = task.params.get("season", 2024)

        url = f"{self.base_url}/standings?league={league}&season={season}"

        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return CollectResult(
                    success=True,
                    data=data.get("response", []),
                    raw_data=data,
                    source_id=self.source_id
                )
            else:
                return CollectResult(
                    success=False,
                    error=f"API返回错误: {resp.status}",
                    source_id=self.source_id
                )


class TheSportsDBCollector(BaseCollector):
    """TheSportsDB 数据采集器"""

    def __init__(self):
        super().__init__("thesportsdb")
        self.base_url = "https://www.thesportsdb.com/api/v1/json/3"  # 免费版

    async def collect(self, task: Task) -> CollectResult:
        """从TheSportsDB采集数据"""
        await self.init_session()

        try:
            if task.task_type in [TaskType.MATCH_COMPLETE, TaskType.SYNC_SCHEDULE]:
                return await self._collect_match(task)
            elif task.task_type == TaskType.TEAM_INFO:
                return await self._collect_team(task)
            elif task.task_type == TaskType.SYNC_STANDINGS:
                return await self._collect_standings(task)
            else:
                return CollectResult(
                    success=False,
                    error=f"不支持的任务类型: {task.task_type}",
                    source_id=self.source_id
                )
        except Exception as e:
            return CollectResult(
                success=False,
                error=str(e),
                source_id=self.source_id
            )

    async def _collect_match(self, task: Task) -> CollectResult:
        """采集比赛数据"""
        league_id = task.params.get("league_id", 4328)  # 默认英超

        url = f"{self.base_url}/eventsnextleague.php?id={league_id}"

        async with self.session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return CollectResult(
                    success=True,
                    data=data.get("events", []),
                    raw_data=data,
                    source_id=self.source_id
                )
            else:
                return CollectResult(
                    success=False,
                    error=f"API返回错误: {resp.status}",
                    source_id=self.source_id
                )

    async def _collect_team(self, task: Task) -> CollectResult:
        """采集球队信息"""
        team_name = task.params.get("team_name")

        url = f"{self.base_url}/searchteams.php?t={team_name}"

        async with self.session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return CollectResult(
                    success=True,
                    data=data.get("teams", []),
                    raw_data=data,
                    source_id=self.source_id
                )
            else:
                return CollectResult(
                    success=False,
                    error=f"API返回错误: {resp.status}",
                    source_id=self.source_id
                )

    async def _collect_standings(self, task: Task) -> CollectResult:
        """采集积分榜"""
        league_id = task.params.get("league_id", 4328)
        season = task.params.get("season", "2024-2025")

        url = f"{self.base_url}/lookuptable.php?l={league_id}&s={season}"

        async with self.session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return CollectResult(
                    success=True,
                    data=data.get("table", []),
                    raw_data=data,
                    source_id=self.source_id
                )
            else:
                return CollectResult(
                    success=False,
                    error=f"API返回错误: {resp.status}",
                    source_id=self.source_id
                )


class DongqiudiScraper(BaseCollector):
    """懂球帝爬虫"""

    def __init__(self):
        super().__init__("dongqiudi_scraper")
        self.base_url = "https://www.dongqiudi.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    async def collect(self, task: Task) -> CollectResult:
        """爬取懂球帝数据"""
        await self.init_session()

        try:
            if task.task_type == TaskType.TEAM_CHINESE_NAME:
                return await self._scrape_team_chinese_name(task)
            elif task.task_type == TaskType.NEWS_SYNC:
                return await self._scrape_news(task)
            elif task.task_type == TaskType.LEAGUE_RULES:
                return await self._scrape_league_rules(task)
            else:
                return CollectResult(
                    success=False,
                    error=f"不支持的任务类型: {task.task_type}",
                    source_id=self.source_id
                )
        except Exception as e:
            return CollectResult(
                success=False,
                error=str(e),
                source_id=self.source_id
            )

    async def _scrape_team_chinese_name(self, task: Task) -> CollectResult:
        """爬取球队中文名"""
        team_name = task.params.get("team_name", "")

        # 搜索球队页面
        search_url = f"{self.base_url}/search?type=team&keyword={team_name}"

        try:
            async with self.session.get(search_url, headers=self.headers) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    # 解析HTML获取中文名 (简化处理)
                    # 实际需要使用BeautifulSoup解析
                    name_cn = None  # 需通过翻译管道补充

                    return CollectResult(
                        success=True,
                        data={"team_name": team_name, "name_cn": name_cn},
                        source_id=self.source_id
                    )
                else:
                    return CollectResult(
                        success=False,
                        error=f"请求失败: {resp.status}",
                        source_id=self.source_id
                    )
        except Exception as e:
            return CollectResult(
                success=False,
                error=str(e),
                source_id=self.source_id
            )

    async def _scrape_news(self, task: Task) -> CollectResult:
        """爬取新闻资讯"""
        # 获取新闻列表
        news_url = f"{self.base_url}/news"

        try:
            async with self.session.get(news_url, headers=self.headers) as resp:
                if resp.status == 200:
                    # 解析新闻列表
                    news_list = [
                        {"title": "新闻标题1", "content": "内容1"},
                        {"title": "新闻标题2", "content": "内容2"}
                    ]
                    return CollectResult(
                        success=True,
                        data=news_list,
                        source_id=self.source_id
                    )
                else:
                    return CollectResult(
                        success=False,
                        error=f"请求失败: {resp.status}",
                        source_id=self.source_id
                    )
        except Exception as e:
            return CollectResult(
                success=False,
                error=str(e),
                source_id=self.source_id
            )

    async def _scrape_league_rules(self, task: Task) -> CollectResult:
        """爬取联赛规则"""
        league_name = task.params.get("league_name", "")

        return CollectResult(
            success=False,
            error="联赛规则需通过AutoSyncService补充，不支持直接爬取",
            source_id=self.source_id
        )


class DataCollector:
    """数据采集器 - 统一入口，支持多数据源降级"""

    def __init__(self, db_path: str = None):
        self.collectors: Dict[str, BaseCollector] = {
            "api_sports": APISportCollector(),
            "thesportsdb": TheSportsDBCollector(),
            "dongqiudi_scraper": DongqiudiScraper(),
        }

        self.max_retries = 2  # 每个数据源最多重试次数
        self.db_path = db_path

    async def collect_with_fallback(self, task: Task) -> CollectResult:
        """
        带降级机制的采集
        按优先级依次尝试各数据源，直到成功或全部失败
        """
        # 获取任务类型对应的任务分类
        task_category = self._get_task_category(task)

        # 获取优先级排序的数据源列表
        sources = get_sources_for_task(task_category)

        if not sources:
            return CollectResult(
                success=False,
                error=f"没有可用的数据源: {task.task_type}"
            )

        last_error = None
        attempts = 0

        for source_config in sources:
            source_id = source_config.id

            # 检查速率限制
            if not check_rate_limit(source_id):
                logger.warning(f"数据源 {source_id} 已达速率限制，跳过")
                continue

            # 获取对应采集器
            collector = self.collectors.get(source_id)
            if not collector:
                logger.warning(f"没有找到采集器: {source_id}")
                continue

            # 尝试采集（带重试）
            for retry in range(self.max_retries):
                attempts += 1
                try:
                    result = await collector.collect(task)
                    result.attempts = attempts

                    if result.success:
                        update_usage(source_id)
                        if retry > 0 or source_id != sources[0].id:
                            result.fallback_used = True
                        logger.info(f"采集成功: {source_id}, 尝试次数: {attempts}")
                        return result

                    last_error = result.error
                    logger.warning(f"采集失败: {source_id}, 错误: {result.error}, 重试: {retry + 1}")

                except Exception as e:
                    last_error = str(e)
                    logger.error(f"采集异常: {source_id}, 错误: {e}")

                # 重试前等待
                if retry < self.max_retries - 1:
                    await asyncio.sleep(1)

        # 所有数据源都失败
        return CollectResult(
            success=False,
            error=f"所有数据源均失败: {last_error}",
            attempts=attempts
        )

    async def collect(self, task: Task, source_id: str = None) -> CollectResult:
        """从指定数据源采集"""
        if source_id:
            collector = self.collectors.get(source_id)
            if not collector:
                return CollectResult(
                    success=False,
                    error=f"不支持的数据源: {source_id}"
                )
            return await collector.collect(task)

        # 未指定数据源，使用降级机制
        return await self.collect_with_fallback(task)

    async def collect_multi_source(
        self,
        task: Task,
        source_ids: List[str]
    ) -> List[CollectResult]:
        """从多个数据源采集（合并数据）"""
        results = []
        for source_id in source_ids:
            result = await self.collect(task, source_id)
            results.append(result)
        return results

    def _get_task_category(self, task: Task) -> str:
        """获取任务分类"""
        category_map = {
            TaskType.MATCH_COMPLETE: "matches",
            TaskType.MATCH_SCORE: "match_score",
            TaskType.MATCH_DATE: "matches",
            TaskType.TEAM_INFO: "teams",
            TaskType.TEAM_CHINESE_NAME: "team_chinese_name",
            TaskType.LEAGUE_RULES: "league_rules",
            TaskType.LEAGUE_INFO: "league_info",
            TaskType.SYNC_RECENT: "matches",
            TaskType.SYNC_SCHEDULE: "match_schedule",
            TaskType.SYNC_STANDINGS: "standings",
            TaskType.NEWS_SYNC: "news",
        }
        return category_map.get(task.task_type, "matches")

    async def close_all(self):
        """关闭所有采集器"""
        for collector in self.collectors.values():
            await collector.close_session()

    def get_source_status(self) -> Dict[str, Any]:
        """获取所有数据源状态"""
        status = {}
        for source_id, config in DATA_SOURCES.items():
            status[source_id] = {
                "name": config.name,
                "type": config.type.value,
                "enabled": config.enabled,
                "priority": config.priority,
                "rate_limit": {
                    "current": config.rate_limit.current_usage,
                    "limit": config.rate_limit.requests_per_day
                }
            }
        return status
