"""
任务定义模块
定义所有数据任务类型和状态
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


class TaskType(Enum):
    """任务类型"""
    # 比赛相关
    MATCH_COMPLETE = "match_complete"           # 补全比赛数据
    MATCH_SCORE = "match_score"                 # 补全比赛比分
    MATCH_DATE = "match_date"                   # 补全比赛日期

    # 球队相关
    TEAM_INFO = "team_info"                     # 同步球队信息
    TEAM_CHINESE_NAME = "team_chinese_name"     # 补全球队中文名

    # 联赛相关
    LEAGUE_RULES = "league_rules"               # 同步联赛规则
    LEAGUE_INFO = "league_info"                 # 同步联赛信息

    # 同步任务
    SYNC_RECENT = "sync_recent"                 # 同步近期比赛结果
    SYNC_SCHEDULE = "sync_schedule"             # 同步未来赛程
    SYNC_STANDINGS = "sync_standings"           # 同步积分榜

    # 新闻相关
    NEWS_SYNC = "news_sync"                     # 同步新闻资讯

    # 批量任务
    BATCH_IMPORT = "batch_import"               # 批量导入


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"         # 等待处理
    ROUTING = "routing"         # 分拣中
    COLLECTING = "collecting"   # 采集中
    CLEANING = "cleaning"       # 清洗中
    LOADING = "loading"         # 导入中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"     # 已取消


class TaskPriority(Enum):
    """任务优先级"""
    HIGH = 1      # 高优先级: 比分、近期比赛
    MEDIUM = 2    # 中优先级: 球队信息、赛程
    LOW = 3       # 低优先级: 新闻、历史数据


@dataclass
class Task:
    """任务定义"""
    task_type: TaskType
    priority: TaskPriority = TaskPriority.MEDIUM
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: TaskStatus = TaskStatus.PENDING
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    source: Optional[str] = None          # 数据来源
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "params": self.params,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "source": self.source,
            "retry_count": self.retry_count
        }


class TaskManager:
    """任务管理器"""

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.pending_queue: List[Task] = []

    def create_task(
        self,
        task_type: TaskType,
        params: Dict[str, Any] = None,
        priority: TaskPriority = TaskPriority.MEDIUM
    ) -> Task:
        """创建新任务"""
        task = Task(
            task_type=task_type,
            params=params or {},
            priority=priority
        )
        self.tasks[task.task_id] = task
        self.pending_queue.append(task)
        self._sort_queue()
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)

    def get_next_task(self) -> Optional[Task]:
        """获取下一个待处理任务"""
        for task in self.pending_queue:
            if task.status == TaskStatus.PENDING:
                return task
        return None

    def update_task_status(self, task_id: str, status: TaskStatus, error: str = None):
        """更新任务状态"""
        task = self.tasks.get(task_id)
        if task:
            task.status = status
            if status == TaskStatus.COLLECTING and not task.started_at:
                task.started_at = datetime.now()
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task.completed_at = datetime.now()
            if error:
                task.error = error

    def complete_task(self, task_id: str, result: Dict[str, Any]):
        """完成任务"""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now()
            if task in self.pending_queue:
                self.pending_queue.remove(task)

    def fail_task(self, task_id: str, error: str):
        """标记任务失败"""
        task = self.tasks.get(task_id)
        if task:
            task.retry_count += 1
            if task.retry_count >= task.max_retries:
                task.status = TaskStatus.FAILED
                task.error = error
                task.completed_at = datetime.now()
                if task in self.pending_queue:
                    self.pending_queue.remove(task)
            else:
                task.status = TaskStatus.PENDING
                task.error = error

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """按状态获取任务"""
        return [t for t in self.tasks.values() if t.status == status]

    def get_stats(self) -> Dict[str, int]:
        """获取任务统计"""
        stats = {s.value: 0 for s in TaskStatus}
        for task in self.tasks.values():
            stats[task.status.value] += 1
        return stats

    def _sort_queue(self):
        """按优先级排序队列"""
        self.pending_queue.sort(key=lambda t: t.priority.value)

    def clear_completed(self):
        """清理已完成任务"""
        self.tasks = {
            k: v for k, v in self.tasks.items()
            if v.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]
        }
        self.pending_queue = [
            t for t in self.pending_queue
            if t.status == TaskStatus.PENDING
        ]
