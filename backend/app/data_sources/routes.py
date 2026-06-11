"""
数据源API路由
提供统一的数据访问接口
"""

import os
import sqlite3
from fastapi import APIRouter, Query, HTTPException, Body
from typing import Optional, List, Dict, Any, Set
from datetime import datetime
from pydantic import BaseModel

from .manager import DataSourceManager
from .base import DataCategory
from .collection_service import (
    UnifiedCollectionService, CollectionRequest,
    collection_service
)
from .source_registry import registry_manager
from .source_knowledge import knowledge_base, LEAGUES
from .intelligent_collector import collection_api
from .data_completion import DataGapDetector, AutoSyncScheduler

router = APIRouter(prefix="/data", tags=["数据源"])

# 全局管理器实例
_manager: Optional[DataSourceManager] = None


def get_manager() -> DataSourceManager:
    """获取数据源管理器"""
    global _manager
    if _manager is None:
        _manager = DataSourceManager()
    return _manager


@router.get("/sources")
async def list_sources():
    """列出所有数据源"""
    manager = get_manager()
    return {
        "sources": manager.list_sources(),
        "total": len(manager.sources)
    }


@router.get("/sources/{source_name}")
async def get_source_info(source_name: str):
    """获取数据源详情"""
    manager = get_manager()
    info = manager.get_source_info(source_name)
    if not info:
        raise HTTPException(status_code=404, detail=f"数据源 {source_name} 不存在")
    return info


@router.post("/sources/{source_name}/test")
async def test_source(source_name: str):
    """测试数据源连接"""
    manager = get_manager()
    result = await manager.test_source(source_name)
    return result


@router.post("/sources/test-all")
async def test_all_sources():
    """测试所有数据源"""
    manager = get_manager()
    results = await manager.test_all_sources()
    return results


@router.get("/livescores")
async def get_livescores(
    leagues: Optional[str] = Query(None, description="联赛列表，逗号分隔"),
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    sources: Optional[str] = Query(None, description="数据源列表，逗号分隔"),
    merge: bool = Query(True, description="是否合并多数据源结果")
):
    """获取实时比分"""
    manager = get_manager()

    league_list = leagues.split(",") if leagues else None
    source_list = sources.split(",") if sources else None

    if merge:
        matches = await manager.get_livescores_merged(league_list, date)
        return {
            "matches": [m.model_dump() for m in matches],
            "total": len(matches),
            "date": date or datetime.now().strftime("%Y-%m-%d")
        }
    else:
        results = await manager.get_livescores(league_list, date, source_list)
        return {
            "sources": {
                name: {
                    "matches": [m.model_dump() for m in matches],
                    "count": len(matches)
                }
                for name, matches in results.items()
            },
            "date": date or datetime.now().strftime("%Y-%m-%d")
        }


@router.get("/fixtures/{league}")
async def get_fixtures(
    league: str,
    season: Optional[str] = Query(None, description="赛季，如 2025-2026"),
    team: Optional[str] = Query(None, description="球队名称"),
    from_date: Optional[str] = Query(None, description="开始日期"),
    to_date: Optional[str] = Query(None, description="结束日期"),
    source: Optional[str] = Query(None, description="指定数据源")
):
    """获取赛程"""
    manager = get_manager()
    matches = await manager.get_fixtures(league, season, team, from_date, to_date, source)

    return {
        "league": league,
        "season": season,
        "matches": [m.model_dump() for m in matches],
        "total": len(matches)
    }


@router.get("/standings/{league}")
async def get_standings(
    league: str,
    season: Optional[str] = Query(None, description="赛季，如 2025-2026"),
    source: Optional[str] = Query(None, description="指定数据源")
):
    """获取积分榜"""
    manager = get_manager()
    standings = await manager.get_standings(league, season, source)

    return {
        "league": league,
        "season": season,
        "standings": [s.model_dump() for s in standings],
        "total": len(standings)
    }


@router.get("/matches/{league}")
async def get_matches(
    league: str,
    season: Optional[str] = Query(None, description="赛季"),
    team: Optional[str] = Query(None, description="球队名称"),
    limit: Optional[int] = Query(None, description="限制数量"),
    source: Optional[str] = Query(None, description="指定数据源")
):
    """获取历史比赛"""
    manager = get_manager()
    matches = await manager.get_matches(league, season, team, limit, source)

    return {
        "league": league,
        "season": season,
        "matches": [m.model_dump() for m in matches],
        "total": len(matches)
    }


@router.get("/teams/{team_id}")
async def get_team(
    team_id: str,
    source: Optional[str] = Query(None, description="指定数据源")
):
    """获取球队信息"""
    manager = get_manager()
    team = await manager.get_team(team_id, source)

    if not team:
        raise HTTPException(status_code=404, detail=f"球队 {team_id} 不存在")

    return team.model_dump()


@router.get("/players")
async def get_players(
    team: Optional[str] = Query(None, description="球队名称"),
    league: Optional[str] = Query(None, description="联赛"),
    season: Optional[str] = Query(None, description="赛季"),
    source: Optional[str] = Query(None, description="指定数据源")
):
    """获取球员信息"""
    manager = get_manager()
    players = await manager.get_players(team, league, season, source)

    return {
        "players": [p.model_dump() for p in players],
        "total": len(players)
    }


@router.get("/scorers/{league}")
async def get_scorers(
    league: str,
    season: Optional[str] = Query(None, description="赛季"),
    limit: Optional[int] = Query(None, description="限制数量"),
    source: Optional[str] = Query(None, description="指定数据源")
):
    """获取射手榜"""
    manager = get_manager()
    scorers = await manager.get_scorers(league, season, limit, source)

    return {
        "league": league,
        "season": season,
        "scorers": [s.model_dump() for s in scorers],
        "total": len(scorers)
    }


# 支持的联赛列表
SUPPORTED_LEAGUES = {
    "premier_league": {"name": "英超", "country": "England"},
    "la_liga": {"name": "西甲", "country": "Spain"},
    "bundesliga": {"name": "德甲", "country": "Germany"},
    "serie_a": {"name": "意甲", "country": "Italy"},
    "ligue_1": {"name": "法甲", "country": "France"},
    "championship": {"name": "英冠", "country": "England"},
    "bundesliga_2": {"name": "德乙", "country": "Germany"},
    "ligue_2": {"name": "法乙", "country": "France"},
    "segunda_division": {"name": "西乙", "country": "Spain"},
    "serie_b": {"name": "意乙", "country": "Italy"},
    "eredivisie": {"name": "荷甲", "country": "Netherlands"},
    "primeira_liga": {"name": "葡超", "country": "Portugal"},
    "champions_league": {"name": "欧冠", "country": "Europe"},
    "europa_league": {"name": "欧联", "country": "Europe"},
    "conference_league": {"name": "欧协联", "country": "Europe"},
    "world_cup": {"name": "世界杯", "country": "International"},
    "euro": {"name": "欧洲杯", "country": "Europe"},
    "k1_league": {"name": "K1联赛", "country": "South Korea"},
    "j1_league": {"name": "J1联赛", "country": "Japan"},
    "mls": {"name": "美职联", "country": "USA"},
}


@router.get("/leagues")
async def list_leagues():
    """列出支持的联赛"""
    return {
        "leagues": [
            {"code": code, **info}
            for code, info in SUPPORTED_LEAGUES.items()
        ],
        "total": len(SUPPORTED_LEAGUES)
    }


@router.get("/categories")
async def list_categories():
    """列出数据类别"""
    return {
        "categories": [
            {"code": c.value, "name": _get_category_name(c)}
            for c in DataCategory
        ]
    }


def _get_category_name(category: DataCategory) -> str:
    """获取数据类别中文名"""
    names = {
        DataCategory.LIVESCORES: "实时比分",
        DataCategory.FIXTURES: "赛程",
        DataCategory.STANDINGS: "积分榜",
        DataCategory.MATCHES: "历史比赛",
        DataCategory.TEAMS: "球队信息",
        DataCategory.PLAYERS: "球员信息",
        DataCategory.SCORERS: "射手榜",
        DataCategory.SQUADS: "阵容",
        DataCategory.STATISTICS: "统计数据",
        DataCategory.XG: "预期进球",
        DataCategory.ODDS: "赔率",
        DataCategory.PREDICTIONS: "预测",
        DataCategory.ANALYSIS: "AI分析",
    }
    return names.get(category, category.value)


# ==================== 统一数据采集API ====================

class CollectionRequestModel(BaseModel):
    """采集请求模型"""
    table: str
    fields: List[str] = []
    filters: Dict[str, Any] = {}
    league: Optional[str] = None
    season: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    team: Optional[str] = None
    limit: Optional[int] = None
    preferred_source: Optional[str] = None


@router.get("/collection/tables")
async def get_available_tables():
    """获取可采集的表列表"""
    tables = collection_service.get_available_tables()
    return {
        "tables": tables,
        "total": len(tables)
    }


@router.get("/collection/tables/{table}/fields")
async def get_table_fields(table: str):
    """获取某表在各数据源中可提供的字段"""
    fields = collection_service.get_table_fields(table)
    if not fields:
        raise HTTPException(status_code=404, detail=f"表 {table} 不存在")
    return {
        "table": table,
        "sources": fields
    }


@router.get("/collection/sources/{source_name}/capabilities")
async def get_source_capabilities(source_name: str):
    """获取数据源能力详情"""
    capabilities = collection_service.get_source_capabilities(source_name)
    if not capabilities:
        raise HTTPException(status_code=404, detail=f"数据源 {source_name} 不存在")
    return capabilities


@router.post("/collection/analyze")
async def analyze_collection_request(request: CollectionRequestModel):
    """分析采集请求，返回数据源推荐"""
    analysis = collection_service.analyze_request(
        CollectionRequest(
            table=request.table,
            fields=set(request.fields) if request.fields else set(),
            filters=request.filters,
            league=request.league,
            season=request.season,
            date_from=request.date_from,
            date_to=request.date_to,
            team=request.team,
            limit=request.limit,
            preferred_source=request.preferred_source
        )
    )
    return analysis


@router.post("/collection/execute")
async def execute_collection(request: CollectionRequestModel):
    """执行数据采集"""
    result = await collection_service.collect(
        CollectionRequest(
            table=request.table,
            fields=set(request.fields) if request.fields else set(),
            filters=request.filters,
            league=request.league,
            season=request.season,
            date_from=request.date_from,
            date_to=request.date_to,
            team=request.team,
            limit=request.limit,
            preferred_source=request.preferred_source
        )
    )
    return {
        "success": result.success,
        "table": result.table,
        "source": result.source,
        "records_count": result.records_count,
        "sql_executed": result.sql_executed,
        "duration_seconds": result.duration_seconds,
        "errors": result.errors,
        "warnings": result.warnings,
        "sample_records": result.records[:5] if result.records else []
    }


@router.get("/registry/sources")
async def list_registered_sources():
    """列出所有已注册的数据源"""
    sources = registry_manager.list_sources()
    return {
        "sources": [
            {
                "name": s.name,
                "type": s.source_type.value,
                "description": s.description,
                "categories": list(s.categories),
                "priority": s.priority,
                "enabled": s.enabled,
                "rate_limit": s.rate_limit,
            }
            for s in sources
        ],
        "total": len(sources)
    }


@router.get("/registry/coverage/{table}")
async def get_field_coverage(table: str, fields: str = Query(None)):
    """获取字段覆盖报告"""
    field_set = set(fields.split(",")) if fields else set()
    report = registry_manager.get_field_coverage_report(table, field_set)
    return {
        "table": table,
        "requested_fields": list(field_set) if field_set else "all",
        "coverage": report
    }


# ==================== 智能采集API ====================

@router.get("/knowledge/leagues")
async def get_all_leagues():
    """获取所有支持的联赛"""
    return {
        "leagues": [
            {
                "code": code,
                "name_en": info["name_en"],
                "name_cn": info["name_cn"],
                "country": info["country"],
                "tier": info["tier"],
            }
            for code, info in LEAGUES.items()
        ],
        "total": len(LEAGUES)
    }


@router.get("/knowledge/leagues/{league}/sources")
async def get_league_sources(league: str):
    """获取某联赛可用的数据源"""
    return collection_api.get_league_sources(league)


@router.get("/knowledge/leagues/{league}/fields")
async def get_league_available_fields(league: str, table: str = Query("match")):
    """获取某联赛可用的数据字段"""
    return collection_api.get_available_fields(league, table)


@router.post("/knowledge/analyze")
async def analyze_data_need(
    league: str = Body(...),
    fields: List[str] = Body(default=[]),
    season: Optional[str] = Body(default=None)
):
    """分析数据需求，推荐数据源组合"""
    return collection_api.analyze_collection_need(league, fields, season)


# ==================== 查漏补缺API ====================

# 获取数据库绝对路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(BASE_DIR, "data", "football_v2.db")


class GapAnalysisRequest(BaseModel):
    """缺口分析请求"""
    league_id: int
    season_id: int
    expected_rounds: Optional[int] = 38


@router.post("/gaps/analyze")
async def analyze_data_gaps(request: GapAnalysisRequest):
    """分析数据缺口"""
    detector = DataGapDetector(DB_PATH)

    gaps = detector.detect_league_gaps(request.league_id, request.season_id)
    missing = detector.detect_missing_matches(
        request.league_id, request.season_id, request.expected_rounds
    )
    priority = detector.get_completion_priority(request.league_id, request.season_id)

    return {
        "league_id": request.league_id,
        "season_id": request.season_id,
        "field_gaps": gaps,
        "missing_matches": missing,
        "completion_priority": priority
    }


@router.post("/sync/plan")
async def create_sync_plan(request: GapAnalysisRequest):
    """创建同步计划"""
    scheduler = AutoSyncScheduler(DB_PATH)
    plan = scheduler.create_sync_plan(request.league_id, request.season_id)
    return plan


# ==================== 数据源能力详情 ====================

@router.get("/knowledge/sources/{source_name}/detail")
async def get_source_detail(source_name: str):
    """获取数据源详细能力"""
    source = knowledge_base.get_source(source_name)
    if not source:
        raise HTTPException(status_code=404, detail=f"数据源 {source_name} 不存在")

    return {
        "name": source.name,
        "type": source.source_type,
        "description": source.description,
        "supported_leagues": list(source.supported_leagues),
        "categories": list(source.categories),
        "match_fields": source.match_fields,
        "team_fields": source.team_fields,
        "player_fields": source.player_fields,
        "standings_fields": source.standings_fields,
        "special_features": list(source.special_features),
        "rate_limit": source.rate_limit,
        "priority": source.priority,
        "sample_response": source.sample_response
    }


@router.get("/knowledge/sources/{source_name}/leagues")
async def get_source_supported_leagues(source_name: str):
    """获取数据源支持的联赛列表"""
    source = knowledge_base.get_source(source_name)
    if not source:
        raise HTTPException(status_code=404, detail=f"数据源 {source_name} 不存在")

    leagues_info = []
    for league_code in source.supported_leagues:
        info = LEAGUES.get(league_code)
        if info:
            leagues_info.append({
                "code": league_code,
                "name_en": info["name_en"],
                "name_cn": info["name_cn"],
            })

    return {
        "source": source_name,
        "supported_leagues": leagues_info,
        "total": len(leagues_info)
    }


@router.get("/knowledge/compare")
async def compare_sources_for_league(league: str):
    """比较各数据源对某联赛的支持情况"""
    sources = knowledge_base.get_sources_for_league(league)

    comparison = []
    for source in sources:
        comparison.append({
            "name": source.name,
            "type": source.source_type,
            "priority": source.priority,
            "match_field_count": len(source.match_fields),
            "special_features": list(source.special_features),
            "rate_limit": source.rate_limit,
        })

    # 字段覆盖矩阵
    all_fields = knowledge_base.get_all_match_fields()
    field_matrix = {}
    for field in all_fields:
        field_matrix[field] = [
            source.name for source in sources
            if field in source.match_fields
        ]

    return {
        "league": league,
        "sources_comparison": comparison,
        "field_coverage_matrix": field_matrix,
        "total_sources": len(sources),
        "total_fields": len(all_fields)
    }


# ==================== 自动同步API ====================

@router.get("/sync/status")
async def get_sync_status():
    """获取同步状态"""
    from datetime import timedelta
    today = datetime.now().strftime("%Y-%m-%d")
    future_3 = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    future_7 = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    status = {}
    for days, label in [(3, "next_3_days"), (7, "next_7_days")]:
        future = future_3 if days == 3 else future_7
        cursor.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN odds_home IS NOT NULL THEN 1 ELSE 0 END)
            FROM matches WHERE match_date >= ? AND match_date <= ?
        """, (today, future))

        row = cursor.fetchone()
        status[label] = {
            "total": row[0],
            "has_time": row[1],
            "has_odds": row[2],
            "time_coverage": round(row[1] / row[0] * 100, 1) if row[0] > 0 else 0,
            "odds_coverage": round(row[2] / row[0] * 100, 1) if row[0] > 0 else 0,
        }

    conn.close()
    return {
        "timestamp": datetime.now().isoformat(),
        "status": status
    }


@router.post("/sync/execute")
async def execute_sync():
    """执行自动同步"""
    import asyncio
    from app.data_sources.manager import DataSourceManager

    manager = DataSourceManager()
    source = manager.get_source("football_data_org")

    if not source:
        return {"success": False, "error": "数据源不可用"}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    leagues = [
        ("SA", "serie_a"),
        ("PD", "la_liga"),
        ("BL1", "bundesliga"),
        ("FL1", "ligue_1"),
        ("PL", "premier_league"),
    ]

    results = {"time_updated": 0, "errors": []}

    for api_code, league_code in leagues:
        try:
            fixtures = await source.get_fixtures(api_code, None)

            if fixtures:
                for f in fixtures:
                    if f.date and f.time:
                        cursor.execute("""
                            UPDATE matches SET
                                match_time = ?,
                                status = COALESCE(?, status),
                                source = COALESCE(source || '+auto_sync', 'auto_sync')
                            WHERE match_date = ?
                            AND (match_time IS NULL OR match_time = '')
                            AND home_team_id = (
                                SELECT team_id FROM teams
                                WHERE name_en LIKE ? OR name_cn LIKE ?
                                LIMIT 1
                            )
                        """, (f.time, getattr(f, "status", None), f.date, f"%{f.home_team}%", f"%{f.home_team}%"))

                        if cursor.rowcount > 0:
                            results["time_updated"] += 1

                conn.commit()

        except Exception as e:
            results["errors"].append(f"{league_code}: {str(e)}")

    conn.close()
    return {"success": True, "results": results}
