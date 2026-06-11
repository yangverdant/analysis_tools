"""
分拣层 (Router Layer)
负责接收请求、分析任务类型、路由到对应的处理器
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import re

from .tasks import Task, TaskType, TaskPriority, TaskManager


class DataSource(Enum):
    """数据来源"""
    API_SPORT = "api_sport"           # API-Sports
    API_FOOTBALL = "api_football"     # API-Football
    WEB_SCRAPER = "web_scraper"       # 网页爬虫
    LOCAL_DB = "local_db"             # 本地数据库
    MANUAL = "manual"                 # 手动输入


@dataclass
class RoutingResult:
    """路由结果"""
    task: Task
    source: DataSource
    handler: str
    params: Dict[str, Any]
    estimated_time: int  # 预估处理时间(秒)


class PipelineRouter:
    """流水线分拣器"""

    # 任务类型到数据源的映射
    TASK_SOURCE_MAP = {
        TaskType.MATCH_COMPLETE: DataSource.API_SPORT,
        TaskType.MATCH_SCORE: DataSource.API_SPORT,
        TaskType.MATCH_DATE: DataSource.API_SPORT,
        TaskType.TEAM_INFO: DataSource.API_SPORT,
        TaskType.TEAM_CHINESE_NAME: DataSource.WEB_SCRAPER,
        TaskType.LEAGUE_RULES: DataSource.WEB_SCRAPER,
        TaskType.LEAGUE_INFO: DataSource.API_SPORT,
        TaskType.SYNC_RECENT: DataSource.API_SPORT,
        TaskType.SYNC_SCHEDULE: DataSource.API_SPORT,
        TaskType.SYNC_STANDINGS: DataSource.API_SPORT,
        TaskType.NEWS_SYNC: DataSource.WEB_SCRAPER,
        TaskType.BATCH_IMPORT: DataSource.LOCAL_DB,
    }

    # 任务类型到处理器的映射
    TASK_HANDLER_MAP = {
        TaskType.MATCH_COMPLETE: "match_handler",
        TaskType.MATCH_SCORE: "match_handler",
        TaskType.MATCH_DATE: "match_handler",
        TaskType.TEAM_INFO: "team_handler",
        TaskType.TEAM_CHINESE_NAME: "team_handler",
        TaskType.LEAGUE_RULES: "league_handler",
        TaskType.LEAGUE_INFO: "league_handler",
        TaskType.SYNC_RECENT: "sync_handler",
        TaskType.SYNC_SCHEDULE: "sync_handler",
        TaskType.SYNC_STANDINGS: "sync_handler",
        TaskType.NEWS_SYNC: "news_handler",
        TaskType.BATCH_IMPORT: "batch_handler",
    }

    # 预估处理时间
    ESTIMATED_TIME = {
        TaskType.MATCH_COMPLETE: 5,
        TaskType.MATCH_SCORE: 3,
        TaskType.MATCH_DATE: 3,
        TaskType.TEAM_INFO: 5,
        TaskType.TEAM_CHINESE_NAME: 10,
        TaskType.LEAGUE_RULES: 15,
        TaskType.LEAGUE_INFO: 5,
        TaskType.SYNC_RECENT: 30,
        TaskType.SYNC_SCHEDULE: 30,
        TaskType.SYNC_STANDINGS: 10,
        TaskType.NEWS_SYNC: 20,
        TaskType.BATCH_IMPORT: 60,
    }

    def __init__(self, task_manager: TaskManager = None):
        self.task_manager = task_manager or TaskManager()
        self.routing_history: List[Dict[str, Any]] = []

    def analyze_request(self, request: Dict[str, Any]) -> Optional[TaskType]:
        """分析请求，确定任务类型"""
        action = request.get("action", "").lower()
        params = request.get("params", {})

        # 关键词匹配
        if any(kw in action for kw in ["比分", "score", "result"]):
            return TaskType.MATCH_SCORE

        if any(kw in action for kw in ["日期", "date", "时间", "time"]):
            return TaskType.MATCH_DATE

        if any(kw in action for kw in ["补全", "complete", "缺失"]):
            if "match" in action or "比赛" in action:
                return TaskType.MATCH_COMPLETE
            if "team" in action or "球队" in action:
                return TaskType.TEAM_INFO

        if any(kw in action for kw in ["中文名", "chinese", "翻译"]):
            return TaskType.TEAM_CHINESE_NAME

        if any(kw in action for kw in ["球队", "team"]):
            return TaskType.TEAM_INFO

        if any(kw in action for kw in ["联赛", "league", "规则", "rules"]):
            if "规则" in action or "rules" in action:
                return TaskType.LEAGUE_RULES
            return TaskType.LEAGUE_INFO

        if any(kw in action for kw in ["同步", "sync"]):
            if any(kw in action for kw in ["近期", "recent", "结果", "result"]):
                return TaskType.SYNC_RECENT
            if any(kw in action for kw in ["赛程", "schedule", "未来", "future"]):
                return TaskType.SYNC_SCHEDULE
            if any(kw in action for kw in ["积分", "standings", "排名"]):
                return TaskType.SYNC_STANDINGS

        if any(kw in action for kw in ["新闻", "news", "资讯"]):
            return TaskType.NEWS_SYNC

        if any(kw in action for kw in ["批量", "batch", "导入", "import"]):
            return TaskType.BATCH_IMPORT

        # 检查参数
        if params:
            if "match_id" in params:
                if "home_goals" not in params or "away_goals" not in params:
                    return TaskType.MATCH_SCORE
                return TaskType.MATCH_COMPLETE

            if "team_id" in params:
                if "name_cn" not in params:
                    return TaskType.TEAM_CHINESE_NAME
                return TaskType.TEAM_INFO

            if "league_id" in params:
                return TaskType.LEAGUE_INFO

        return None

    def route(self, request: Dict[str, Any]) -> RoutingResult:
        """路由请求到对应处理器"""
        # 分析任务类型
        task_type = self.analyze_request(request)
        if not task_type:
            raise ValueError(f"无法识别的任务类型: {request}")

        # 确定优先级
        priority = self._determine_priority(task_type, request)

        # 创建任务
        task = self.task_manager.create_task(
            task_type=task_type,
            params=request.get("params", {}),
            priority=priority
        )

        # 确定数据源
        source = self._select_source(task_type, request)

        # 获取处理器
        handler = self.TASK_HANDLER_MAP.get(task_type, "default_handler")

        # 预估时间
        estimated_time = self.ESTIMATED_TIME.get(task_type, 10)

        # 记录路由历史
        self.routing_history.append({
            "task_id": task.task_id,
            "task_type": task_type.value,
            "source": source.value,
            "handler": handler,
            "timestamp": task.created_at.isoformat()
        })

        return RoutingResult(
            task=task,
            source=source,
            handler=handler,
            params=task.params,
            estimated_time=estimated_time
        )

    def batch_route(self, requests: List[Dict[str, Any]]) -> List[RoutingResult]:
        """批量路由"""
        results = []
        for request in requests:
            try:
                result = self.route(request)
                results.append(result)
            except Exception as e:
                # 记录失败但继续处理
                self.routing_history.append({
                    "error": str(e),
                    "request": request
                })
        return results

    def _determine_priority(self, task_type: TaskType, request: Dict[str, Any]) -> TaskPriority:
        """确定任务优先级"""
        # 比分相关任务高优先级
        if task_type in [TaskType.MATCH_SCORE, TaskType.SYNC_RECENT]:
            return TaskPriority.HIGH

        # 球队、赛程中优先级
        if task_type in [TaskType.TEAM_INFO, TaskType.SYNC_SCHEDULE, TaskType.MATCH_COMPLETE]:
            return TaskPriority.MEDIUM

        # 其他低优先级
        return TaskPriority.LOW

    def _select_source(self, task_type: TaskType, request: Dict[str, Any]) -> DataSource:
        """选择数据源"""
        # 检查请求中是否指定了数据源
        if "source" in request:
            source_str = request["source"].lower()
            for source in DataSource:
                if source.value == source_str:
                    return source

        # 使用默认映射
        return self.TASK_SOURCE_MAP.get(task_type, DataSource.API_SPORT)

    def get_routing_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        stats = {
            "total_routed": len(self.routing_history),
            "by_type": {},
            "by_source": {},
            "by_handler": {}
        }

        for record in self.routing_history:
            if "task_type" in record:
                t = record["task_type"]
                stats["by_type"][t] = stats["by_type"].get(t, 0) + 1

            if "source" in record:
                s = record["source"]
                stats["by_source"][s] = stats["by_source"].get(s, 0) + 1

            if "handler" in record:
                h = record["handler"]
                stats["by_handler"][h] = stats["by_handler"].get(h, 0) + 1

        return stats

    def get_pending_tasks(self) -> List[Task]:
        """获取待处理任务"""
        return self.task_manager.get_tasks_by_status(Task.TaskStatus.PENDING)
