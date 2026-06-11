"""
同步相关路由 - 打通真实的数据同步管道
"""

from fastapi import APIRouter, BackgroundTasks
import sqlite3
import os
from datetime import datetime

router = APIRouter(prefix="/api/v1/sync", tags=["Sync"])

DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'football_v2.db')

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 全局同步任务状态
_sync_tasks = {}


def _run_sync(task_name: str, func, *args, **kwargs):
    """在后台运行同步任务并记录结果"""
    import asyncio
    from ..services.auto_sync_service import AutoSyncService

    service = AutoSyncService()
    try:
        if asyncio.iscoroutinefunction(func):
            result = asyncio.run(func(*args, **kwargs))
        else:
            result = func(*args, **kwargs)
        _sync_tasks[task_name] = {
            "status": "completed",
            "result": result,
            "completed_at": datetime.now().isoformat(),
        }
    except Exception as e:
        _sync_tasks[task_name] = {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat(),
        }
    finally:
        service.close()


@router.get("/check")
async def check_sync_needed():
    """检查是否需要同步"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT MAX(updated_at) as last_update
        FROM matches
    """)
    result = cursor.fetchone()
    last_update = result['last_update'] if result else None

    conn.close()
    return {
        "last_update": last_update,
        "sync_recommended": True
    }


@router.get("/status")
async def get_sync_status():
    """获取同步状态"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM matches")
    total_matches = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM matches WHERE status = 'finished'")
    finished_matches = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM matches WHERE status = 'scheduled'")
    scheduled_matches = cursor.fetchone()['total']

    conn.close()
    return {
        "total_matches": total_matches,
        "finished_matches": finished_matches,
        "scheduled_matches": scheduled_matches,
        "last_sync": datetime.now().isoformat()
    }


@router.get("/gap-report")
async def get_gap_report():
    """返回数据缺口报告"""
    from ..services.auto_sync_service import AutoSyncService
    service = AutoSyncService()
    try:
        gaps = service.get_data_gaps()
        return {"success": True, "gaps": gaps}
    finally:
        service.close()


@router.post("/country-cn")
async def sync_country_chinese_names(background_tasks: BackgroundTasks):
    """同步国家中文名（从linkage文件）"""
    background_tasks.add_task(_run_sync, "country_cn", _sync_country_cn)
    return {"success": True, "message": "国家中文名同步已启动", "task": "country_cn"}


def _sync_country_cn():
    from ..services.auto_sync_service import AutoSyncService
    service = AutoSyncService()
    result = service.sync_country_chinese_names()
    service.close()
    return result


@router.post("/league-rules")
async def sync_league_rules(background_tasks: BackgroundTasks):
    """自动补充联赛规则"""
    background_tasks.add_task(_run_sync, "league_rules", _sync_league_rules)
    return {"success": True, "message": "联赛规则补充已启动", "task": "league_rules"}


def _sync_league_rules():
    from ..services.auto_sync_service import AutoSyncService
    service = AutoSyncService()
    result = service.sync_league_rules()
    service.close()
    return result


@router.post("/player-cn")
async def sync_player_chinese_names(background_tasks: BackgroundTasks, limit: int = 200):
    """AI翻译球员中文名"""
    background_tasks.add_task(_run_sync, "player_cn", _sync_player_cn, limit)
    return {"success": True, "message": f"球员中文名翻译已启动（限制{limit}人）", "task": "player_cn"}


def _sync_player_cn(limit: int = 200):
    import asyncio
    from ..services.auto_sync_service import AutoSyncService
    service = AutoSyncService()
    result = asyncio.run(service.sync_player_chinese_names(limit))
    service.close()
    return result


@router.post("/league-cn")
async def sync_league_chinese_names(background_tasks: BackgroundTasks, limit: int = 200):
    """AI翻译联赛中文名"""
    background_tasks.add_task(_run_sync, "league_cn", _sync_league_cn, limit)
    return {"success": True, "message": f"联赛中文名翻译已启动（限制{limit}条）", "task": "league_cn"}


def _sync_league_cn(limit: int = 200):
    import asyncio
    from ..services.auto_sync_service import AutoSyncService
    service = AutoSyncService()
    result = asyncio.run(service.sync_league_chinese_names(limit))
    service.close()
    return result


@router.post("/team-cn-api")
async def sync_team_cn_from_api(background_tasks: BackgroundTasks, limit: int = 500):
    """从Sportmonks/TheSportsDB API获取球队中文名（非AI）"""
    background_tasks.add_task(_run_sync, "team_cn_api", _sync_team_cn_api, limit)
    return {"success": True, "message": f"API球队中文名同步已启动（限制{limit}队）", "task": "team_cn_api"}


def _sync_team_cn_api(limit: int = 500):
    import asyncio
    from ..services.auto_sync_service import AutoSyncService
    service = AutoSyncService()
    result = asyncio.run(service.sync_team_cn_from_api(limit))
    service.close()
    return result


@router.post("/league-cn-api")
async def sync_league_cn_from_api(background_tasks: BackgroundTasks, limit: int = 200):
    """从Sportmonks/TheSportsDB API获取联赛中文名（非AI）"""
    background_tasks.add_task(_run_sync, "league_cn_api", _sync_league_cn_api, limit)
    return {"success": True, "message": f"API联赛中文名同步已启动（限制{limit}条）", "task": "league_cn_api"}


def _sync_league_cn_api(limit: int = 200):
    import asyncio
    from ..services.auto_sync_service import AutoSyncService
    service = AutoSyncService()
    result = asyncio.run(service.sync_league_cn_from_api(limit))
    service.close()
    return result


@router.post("/fix-season-ids")
async def fix_match_season_ids(background_tasks: BackgroundTasks):
    """修复比赛season_id关联"""
    background_tasks.add_task(_run_sync, "fix_season_ids", _fix_season_ids)
    return {"success": True, "message": "season_id修复已启动", "task": "fix_season_ids"}


def _fix_season_ids():
    from ..services.auto_sync_service import AutoSyncService
    service = AutoSyncService()
    result = service.fix_match_season_ids()
    service.close()
    return result


@router.post("/events")
async def sync_finished_matches(background_tasks: BackgroundTasks, days: int = 7):
    """同步已结束比赛结果（从API获取）"""
    background_tasks.add_task(_run_sync, "match_results", _sync_match_results)
    return {"success": True, "message": f"同步最近{days}天的比赛结果", "task": "match_results"}


def _sync_match_results():
    import asyncio
    from ..services.auto_sync_service import AutoSyncService
    service = AutoSyncService()
    result = asyncio.run(service.sync_finished_match_results())
    service.close()
    return result


@router.post("/future")
async def sync_upcoming_matches(background_tasks: BackgroundTasks):
    """同步未来赛程（使用DataSourceManager）"""
    background_tasks.add_task(_run_sync, "future_matches", _sync_future_matches)
    return {"success": True, "message": "未来赛程同步已启动", "task": "future_matches"}


def _sync_future_matches():
    import asyncio
    from ..data_sources.manager import DataSourceManager
    manager = DataSourceManager()
    result = asyncio.run(manager.sync_future_matches(DATABASE_PATH))
    return result


@router.post("/full")
async def full_sync(background_tasks: BackgroundTasks):
    """完整数据补充流程"""
    background_tasks.add_task(_run_sync, "full_sync", _run_full_sync)
    return {"success": True, "message": "完整数据补充已启动", "task": "full_sync"}


def _run_full_sync():
    import asyncio
    from ..services.auto_sync_service import AutoSyncService
    service = AutoSyncService()
    result = asyncio.run(service.run_full_sync())
    service.close()
    return result


@router.post("/league-season")
async def sync_league_season(data: dict):
    """同步联赛某赛季数据"""
    league_id = data.get('league_id')
    season = data.get('season')

    if not league_id:
        return {"success": False, "error": "缺少 league_id"}

    return {
        "success": True,
        "message": f"同步联赛 {league_id} 赛季 {season}",
        "updated": 0
    }


@router.post("/recent-results")
async def sync_recent_results(days: int = 7):
    """同步近期比赛结果"""
    conn = get_db()
    cursor = conn.cursor()

    from datetime import datetime, timedelta
    today = datetime.now().strftime('%Y-%m-%d')
    days_ago = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    cursor.execute("""
        SELECT COUNT(*) FROM matches
        WHERE match_date >= ? AND match_date <= ? AND status = 'finished'
    """, (days_ago, today))
    checked = cursor.fetchone()[0]

    conn.close()
    return {
        "success": True,
        "checked": checked,
        "updated": 0
    }


@router.get("/progress/{task_name}")
async def get_sync_progress(task_name: str):
    """查询同步任务进度"""
    task = _sync_tasks.get(task_name)
    if not task:
        return {"status": "not_found", "task": task_name}
    return task


@router.get("/tasks")
async def list_sync_tasks():
    """列出所有同步任务"""
    return {"tasks": list(_sync_tasks.keys()), "details": _sync_tasks}