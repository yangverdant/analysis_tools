"""
数据流水线API路由
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import os

from .tasks import TaskManager, TaskType, TaskStatus, Task, TaskPriority
from .router import PipelineRouter
from .collector import DataCollector
from .cleaner import DataCleaner
from .loader import DataLoader
from .sources import (
    DATA_SOURCES, get_sources_for_task, get_data_type_support,
    get_available_fields, get_sources_for_league, get_all_supported_leagues
)
from .schema import (
    TABLES, get_table_def, get_column_names, get_all_tables_summary,
    API_SPORTS_FIELD_MAP, THESPORTSDB_FIELD_MAP
)

router = APIRouter(prefix="/api/v1/pipeline", tags=["Pipeline"])

# 初始化组件
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'football_v2.db')
task_manager = TaskManager()
pipeline_router = PipelineRouter(task_manager)
collector = DataCollector(DB_PATH)
cleaner = DataCleaner()
loader = DataLoader(DB_PATH)


# ==================== 请求模型 ====================

class TaskRequest(BaseModel):
    """任务请求"""
    action: str
    params: Optional[Dict[str, Any]] = None
    source: Optional[str] = None


class BatchTaskRequest(BaseModel):
    """批量任务请求"""
    tasks: List[TaskRequest]


# ==================== 数据源API ====================

@router.get("/sources")
async def get_data_sources():
    """获取所有数据源配置"""
    sources = []
    for source_id, config in DATA_SOURCES.items():
        # 获取套餐信息
        tiers = []
        for tier in config.tiers:
            tiers.append({
                "name": tier.tier_name,
                "price": tier.price,
                "requests_per_minute": tier.requests_per_minute,
                "requests_per_day": tier.requests_per_day,
                "requests_per_month": tier.requests_per_month,
                "max_leagues": tier.max_leagues,
                "historical_years": tier.historical_years,
                "has_realtime": tier.has_realtime,
                "has_odds": tier.has_odds,
                "has_lineups": tier.has_lineups,
                "has_statistics": tier.has_statistics,
                "has_player_data": tier.has_player_data,
                "notes": tier.notes,
            })

        # 获取数据类型
        data_types = []
        for dt_id, dt in config.data_types.items():
            data_types.append({
                "id": dt_id,
                "name": dt.data_type_cn,
                "free_available": dt.free_available,
                "paid_available": dt.paid_available,
                "quality_score": dt.quality_score,
                "coverage": dt.coverage,
                "update_frequency": dt.update_frequency,
                "fields_count": len(dt.fields),
            })

        sources.append({
            "id": source_id,
            "name": config.name,
            "name_cn": config.name_cn,
            "type": config.type.value,
            "enabled": config.enabled,
            "priority": config.priority,
            "tiers": tiers,
            "data_types": data_types,
            "free_leagues_count": config.free_leagues_count,
            "paid_leagues_count": config.paid_leagues_count,
            "total_leagues": config.total_leagues,
            "total_countries": config.total_countries,
            "description": config.description,
        })

    return {"data": sources}


@router.get("/sources/{source_id}")
async def get_data_source(source_id: str):
    """获取单个数据源详情"""
    config = DATA_SOURCES.get(source_id)
    if not config:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 套餐信息
    tiers = []
    for tier in config.tiers:
        tiers.append({
            "name": tier.tier_name,
            "price": tier.price,
            "requests_per_minute": tier.requests_per_minute,
            "requests_per_day": tier.requests_per_day,
            "requests_per_month": tier.requests_per_month,
            "max_leagues": tier.max_leagues,
            "max_seasons": tier.max_seasons,
            "historical_years": tier.historical_years,
            "has_realtime": tier.has_realtime,
            "has_odds": tier.has_odds,
            "has_lineups": tier.has_lineups,
            "has_statistics": tier.has_statistics,
            "has_player_data": tier.has_player_data,
            "priority_support": tier.priority_support,
            "notes": tier.notes,
        })

    # 数据类型详情
    data_types = {}
    for dt_id, dt in config.data_types.items():
        fields = []
        for f in dt.fields:
            fields.append({
                "field_name": f.field_name,
                "field_name_cn": f.field_name_cn,
                "description": f.description,
                "free_available": f.free_available,
                "paid_available": f.paid_available,
                "realtime": f.realtime,
                "delay_seconds": f.delay_seconds,
            })

        data_types[dt_id] = {
            "name": dt.data_type_cn,
            "free_available": dt.free_available,
            "paid_available": dt.paid_available,
            "quality_score": dt.quality_score,
            "coverage": dt.coverage,
            "update_frequency": dt.update_frequency,
            "delay_seconds": dt.delay_seconds,
            "fields": fields,
            "notes": dt.notes,
        }

    # 联赛列表
    leagues = []
    for league in config.leagues:
        leagues.append({
            "league_id": league.league_id,
            "league_name": league.league_name,
            "league_name_cn": league.league_name_cn,
            "country": league.country,
            "free_available": league.free_available,
            "paid_available": league.paid_available,
            "coverage": league.coverage,
            "notes": league.notes,
        })

    return {
        "id": config.id,
        "name": config.name,
        "name_cn": config.name_cn,
        "type": config.type.value,
        "base_url": config.base_url,
        "enabled": config.enabled,
        "priority": config.priority,
        "tiers": tiers,
        "data_types": data_types,
        "leagues": leagues,
        "free_leagues_count": config.free_leagues_count,
        "paid_leagues_count": config.paid_leagues_count,
        "total_leagues": config.total_leagues,
        "total_countries": config.total_countries,
        "description": config.description,
        "notes": config.notes,
    }


@router.get("/sources/{source_id}/data-types/{data_type}")
async def get_data_type_detail(source_id: str, data_type: str):
    """获取数据源的特定数据类型详情"""
    support = get_data_type_support(source_id, data_type)
    if not support:
        raise HTTPException(status_code=404, detail="数据类型不存在")

    fields = []
    for f in support.fields:
        fields.append({
            "field_name": f.field_name,
            "field_name_cn": f.field_name_cn,
            "description": f.description,
            "free_available": f.free_available,
            "paid_available": f.paid_available,
            "realtime": f.realtime,
            "delay_seconds": f.delay_seconds,
        })

    return {
        "source_id": source_id,
        "data_type": data_type,
        "name": support.data_type_cn,
        "free_available": support.free_available,
        "paid_available": support.paid_available,
        "quality_score": support.quality_score,
        "coverage": support.coverage,
        "update_frequency": support.update_frequency,
        "delay_seconds": support.delay_seconds,
        "fields": fields,
        "notes": support.notes,
    }


@router.get("/sources/{source_id}/fields/{data_type}")
async def get_available_fields_api(
    source_id: str,
    data_type: str,
    is_free: bool = Query(True, description="是否为免费版")
):
    """获取可用的数据字段列表"""
    fields = get_available_fields(source_id, data_type, is_free)
    support = get_data_type_support(source_id, data_type)

    return {
        "source_id": source_id,
        "data_type": data_type,
        "is_free": is_free,
        "available_fields": fields,
        "total_fields": len(support.fields) if support else 0,
    }


@router.get("/sources/{source_id}/leagues")
async def get_source_leagues(source_id: str):
    """获取数据源支持的所有联赛"""
    config = DATA_SOURCES.get(source_id)
    if not config:
        raise HTTPException(status_code=404, detail="数据源不存在")

    return {
        "source_id": source_id,
        "source_name": config.name,
        "free_leagues_count": config.free_leagues_count,
        "paid_leagues_count": config.paid_leagues_count,
        "total_leagues": config.total_leagues,
        "total_countries": config.total_countries,
        "leagues": [
            {
                "league_id": league.league_id,
                "league_name": league.league_name,
                "league_name_cn": league.league_name_cn,
                "country": league.country,
                "free_available": league.free_available,
                "paid_available": league.paid_available,
                "coverage": league.coverage,
                "notes": league.notes,
            }
            for league in config.leagues
        ]
    }


@router.get("/leagues/{league_id}/sources")
async def get_league_sources_api(league_id: int):
    """获取支持特定联赛的所有数据源"""
    sources = get_sources_for_league(league_id)
    return {
        "league_id": league_id,
        "sources": sources
    }


@router.get("/leagues/all")
async def get_all_leagues():
    """获取所有数据源支持的联赛列表"""
    return get_all_supported_leagues()


@router.get("/schema/tables")
async def get_database_tables():
    """获取数据库所有表结构概要"""
    return {
        "tables": get_all_tables_summary()
    }


@router.get("/schema/tables/{table_name}")
async def get_table_schema(table_name: str):
    """获取单个表的详细结构"""
    table = get_table_def(table_name)
    if not table:
        raise HTTPException(status_code=404, detail="表不存在")

    columns = []
    for col in table.columns:
        columns.append({
            "name": col.name,
            "name_cn": col.name_cn,
            "dtype": col.dtype,
            "is_pk": col.is_pk,
            "is_nullable": col.is_nullable,
            "default": col.default,
            "description": col.description,
        })

    return {
        "table_name": table.name,
        "table_name_cn": table.name_cn,
        "description": table.description,
        "count": table.count,
        "columns": columns
    }


@router.get("/schema/field-map/{source_id}/{table_name}")
async def get_field_map_api(source_id: str, table_name: str):
    """获取 API 字段到数据库字段的映射"""
    if source_id == "api_sports":
        field_map = API_SPORTS_FIELD_MAP.get(table_name, {})
    elif source_id == "thesportsdb":
        field_map = THESPORTSDB_FIELD_MAP.get(table_name, {})
    else:
        field_map = {}

    return {
        "source_id": source_id,
        "table_name": table_name,
        "field_map": field_map
    }


@router.get("/sources/task/{task_type}")
async def get_sources_for_task_type(task_type: str):
    """获取任务类型对应的数据源优先级列表"""
    sources = get_sources_for_task(task_type)
    return {
        "task_type": task_type,
        "sources": [
            {
                "id": s.id,
                "name": s.name,
                "name_cn": s.name_cn,
                "priority": s.priority,
                "free_leagues_count": s.free_leagues_count,
                "total_leagues": s.total_leagues,
            }
            for s in sources
        ]
    }


# ==================== 任务管理API ====================

@router.post("/tasks")
async def create_task(request: TaskRequest):
    """创建新任务"""
    try:
        routing_result = pipeline_router.route(request.dict())
        return {
            "task_id": routing_result.task.task_id,
            "task_type": routing_result.task.task_type.value,
            "status": routing_result.task.status.value,
            "source": routing_result.source.value,
            "handler": routing_result.handler,
            "estimated_time": routing_result.estimated_time
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/batch")
async def create_batch_tasks(request: BatchTaskRequest):
    """批量创建任务"""
    results = pipeline_router.batch_route([r.dict() for r in request.tasks])
    return {
        "created": len(results),
        "tasks": [
            {
                "task_id": r.task.task_id,
                "task_type": r.task.task_type.value,
                "source": r.source.value
            }
            for r in results
        ]
    }


@router.get("/tasks")
async def get_tasks(status: Optional[str] = None, limit: int = 50):
    """获取任务列表"""
    if status:
        try:
            task_status = TaskStatus(status)
            tasks = task_manager.get_tasks_by_status(task_status)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的状态")
    else:
        tasks = list(task_manager.tasks.values())

    return {
        "total": len(tasks),
        "tasks": [t.to_dict() for t in tasks[:limit]]
    }


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict()


@router.get("/tasks/stats")
async def get_task_stats():
    """获取任务统计"""
    return task_manager.get_stats()


# ==================== 流水线执行API ====================

@router.post("/execute/{task_id}")
async def execute_task(task_id: str, background_tasks: BackgroundTasks):
    """执行单个任务"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    background_tasks.add_task(run_pipeline, task)

    return {
        "task_id": task_id,
        "status": "running",
        "message": "任务已开始执行"
    }


@router.post("/execute-all")
async def execute_all_pending(background_tasks: BackgroundTasks):
    """执行所有待处理任务"""
    pending_tasks = task_manager.get_tasks_by_status(TaskStatus.PENDING)

    for task in pending_tasks:
        background_tasks.add_task(run_pipeline, task)

    return {
        "started": len(pending_tasks),
        "message": f"已启动 {len(pending_tasks)} 个任务"
    }


async def run_pipeline(task: Task):
    """执行完整流水线"""
    try:
        task_manager.update_task_status(task.task_id, TaskStatus.COLLECTING)

        collect_result = await collector.collect_with_fallback(task)
        if not collect_result.success:
            task_manager.fail_task(task.task_id, f"采集失败: {collect_result.error}")
            return

        task_manager.update_task_status(task.task_id, TaskStatus.CLEANING)

        clean_result = cleaner.clean(task, collect_result)
        if not clean_result.success:
            task_manager.fail_task(task.task_id, f"清洗失败: {clean_result.error}")
            return

        task_manager.update_task_status(task.task_id, TaskStatus.LOADING)

        load_result = loader.load(task, clean_result)
        if not load_result.success:
            task_manager.fail_task(task.task_id, f"导入失败: {load_result.error}")
            return

        task_manager.complete_task(task.task_id, {
            "records_inserted": load_result.records_inserted,
            "records_updated": load_result.records_updated,
            "records_skipped": load_result.records_skipped,
            "source_used": collect_result.source_id,
            "fallback_used": collect_result.fallback_used
        })

    except Exception as e:
        task_manager.fail_task(task.task_id, str(e))


# ==================== 快捷操作API ====================

@router.post("/sync/recent")
async def sync_recent_matches(
    background_tasks: BackgroundTasks,
    league: int = 39,
    season: int = 2024,
    last: int = 10
):
    """同步近期比赛结果"""
    task = task_manager.create_task(
        task_type=TaskType.SYNC_RECENT,
        params={"league": league, "season": season, "last": last},
        priority=TaskPriority.HIGH
    )

    background_tasks.add_task(run_pipeline, task)

    return {
        "task_id": task.task_id,
        "message": "同步任务已创建"
    }


@router.post("/sync/schedule")
async def sync_future_schedule(
    background_tasks: BackgroundTasks,
    league: int = 39,
    season: int = 2024,
    next_rounds: int = 10
):
    """同步未来赛程"""
    task = task_manager.create_task(
        task_type=TaskType.SYNC_SCHEDULE,
        params={"league": league, "season": season, "next": next_rounds},
        priority=TaskPriority.MEDIUM
    )

    background_tasks.add_task(run_pipeline, task)

    return {
        "task_id": task.task_id,
        "message": "同步任务已创建"
    }


@router.post("/sync/standings")
async def sync_standings(
    background_tasks: BackgroundTasks,
    league: int = 39,
    season: int = 2024
):
    """同步积分榜"""
    task = task_manager.create_task(
        task_type=TaskType.SYNC_STANDINGS,
        params={"league": league, "season": season},
        priority=TaskPriority.MEDIUM
    )

    background_tasks.add_task(run_pipeline, task)

    return {
        "task_id": task.task_id,
        "message": "同步任务已创建"
    }


@router.post("/complete/match/{match_id}")
async def complete_match_data(match_id: int, background_tasks: BackgroundTasks):
    """补全比赛数据"""
    task = task_manager.create_task(
        task_type=TaskType.MATCH_COMPLETE,
        params={"match_id": match_id},
        priority=TaskPriority.HIGH
    )

    background_tasks.add_task(run_pipeline, task)

    return {
        "task_id": task.task_id,
        "message": "补全任务已创建"
    }


@router.post("/complete/team/{team_id}")
async def complete_team_data(team_id: int, background_tasks: BackgroundTasks):
    """补全球队数据"""
    task = task_manager.create_task(
        task_type=TaskType.TEAM_INFO,
        params={"team_id": team_id},
        priority=TaskPriority.MEDIUM
    )

    background_tasks.add_task(run_pipeline, task)

    return {
        "task_id": task.task_id,
        "message": "补全任务已创建"
    }


@router.get("/status")
async def get_pipeline_status():
    """获取流水线状态"""
    stats = task_manager.get_stats()
    source_status = collector.get_source_status()

    return {
        "tasks": stats,
        "sources": source_status,
        "routing_stats": pipeline_router.get_routing_stats()
    }
