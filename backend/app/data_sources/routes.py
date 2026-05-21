"""
数据源API路由
提供统一的数据访问接口
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime

from .manager import DataSourceManager
from .base import DataCategory

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
