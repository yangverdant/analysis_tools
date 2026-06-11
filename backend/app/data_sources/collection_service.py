"""
统一数据采集服务 - 整合数据源选择、采集、清洗、入库
支持:
1. 按需求字段智能选择数据源
2. 自动采集数据
3. 数据清洗转换
4. SQL入库
5. 采集任务管理
"""

import asyncio
import sqlite3
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json

from .source_registry import (
    DataSourceRegistry, SourceRegistryManager, registry_manager,
    FieldType, FieldMapping
)
from .data_cleaner import DataCleaner, TransformResult, data_cleaner
from .base import DataCategory
from .manager import DataSourceManager


@dataclass
class CollectionRequest:
    """采集请求"""
    table: str                           # 目标表名
    fields: Set[str]                     # 需要的字段
    filters: Dict[str, Any] = field(default_factory=dict)  # 过滤条件
    league: Optional[str] = None         # 联赛
    season: Optional[str] = None         # 蛋糕
    date_from: Optional[str] = None      # 开始日期
    date_to: Optional[str] = None        # 结束日期
    team: Optional[str] = None           # 球队
    limit: Optional[int] = None          # 数量限制
    preferred_source: Optional[str] = None  # 指定数据源


@dataclass
class CollectionResult:
    """采集结果"""
    success: bool
    table: str
    source: str
    records_count: int
    records: List[Dict[str, Any]]
    errors: List[str]
    warnings: List[str]
    sql_executed: int
    duration_seconds: float


class UnifiedCollectionService:
    """统一数据采集服务"""

    def __init__(self, db_path: str = "data/football_v2.db"):
        self.registry_manager = registry_manager
        self.data_cleaner = data_cleaner
        self.source_manager = DataSourceManager()
        self.db_path = db_path

    def analyze_request(self, request: CollectionRequest) -> Dict[str, Any]:
        """分析采集请求，返回数据源推荐"""
        # 查找支持该表的数据源
        sources = self.registry_manager.find_sources_for_fields(
            request.table, request.fields
        )

        # 获取字段覆盖报告
        coverage_report = self.registry_manager.get_field_coverage_report(
            request.table, request.fields
        )

        return {
            "table": request.table,
            "required_fields": list(request.fields),
            "recommended_sources": [s.name for s in sources],
            "best_source": sources[0].name if sources else None,
            "coverage_report": coverage_report,
            "filters": request.filters,
        }

    async def collect(self, request: CollectionRequest) -> CollectionResult:
        """执行数据采集"""
        start_time = datetime.now()

        # 1. 选择数据源
        if request.preferred_source:
            source_registry = self.registry_manager.get(request.preferred_source)
        else:
            source_registry = self.registry_manager.find_best_source(
                request.table, request.fields
            )

        if not source_registry:
            return CollectionResult(
                success=False,
                table=request.table,
                source="none",
                records_count=0,
                records=[],
                errors=["找不到支持所需字段的数据源"],
                warnings=[],
                sql_executed=0,
                duration_seconds=0
            )

        # 2. 采集原始数据
        raw_data = await self._fetch_raw_data(request, source_registry)

        if not raw_data:
            return CollectionResult(
                success=False,
                table=request.table,
                source=source_registry.name,
                records_count=0,
                records=[],
                errors=["采集数据失败或无数据"],
                warnings=[],
                sql_executed=0,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

        # 3. 清洗转换数据
        cleaned_results = self.data_cleaner.batch_clean(
            raw_data, request.table, source_registry
        )

        # 4. 过滤无效数据
        valid_records = [
            r for r in cleaned_results
            if r.success and r.data
        ]

        # 5. 入库
        sql_executed = 0
        errors = []
        warnings = []

        if valid_records:
            sql_executed = self._save_to_database(
                request.table,
                [r.data for r in valid_records],
                self._get_key_fields(request.table)
            )

        # 收集错误和警告
        for result in cleaned_results:
            errors.extend(result.errors)
            warnings.extend(result.warnings)

        duration = (datetime.now() - start_time).total_seconds()

        return CollectionResult(
            success=len(valid_records) > 0,
            table=request.table,
            source=source_registry.name,
            records_count=len(valid_records),
            records=[r.data for r in valid_records],
            errors=errors,
            warnings=warnings,
            sql_executed=sql_executed,
            duration_seconds=duration
        )

    async def _fetch_raw_data(
        self,
        request: CollectionRequest,
        source_registry: DataSourceRegistry
    ) -> List[Dict[str, Any]]:
        """从数据源获取原始数据"""
        source = self.source_manager.get_source(source_registry.name)
        if not source:
            return []

        try:
            # 根据表类型调用不同的方法
            if request.table == "matches":
                if request.date_from and request.date_to:
                    # 按日期范围获取
                    return await self._fetch_matches_by_date(
                        source, source_registry, request
                    )
                elif request.league:
                    # 按联赛获取
                    return await self._fetch_matches_by_league(
                        source, source_registry, request
                    )
                else:
                    # 获取实时比分
                    matches = await source.get_livescores()
                    return [m.__dict__ for m in matches]

            elif request.table == "standings":
                if request.league:
                    standings = await source.get_standings(
                        request.league, request.season
                    )
                    return [s.__dict__ for s in standings]

            elif request.table == "teams":
                if request.filters.get("team_id"):
                    team = await source.get_team(request.filters["team_id"])
                    return [team.__dict__] if team else []

            elif request.table == "players":
                players = await source.get_players(
                    request.team, request.league, request.season
                )
                return [p.__dict__ for p in players]

        except Exception as e:
            print(f"采集数据失败: {e}")
            return []

        return []

    async def _fetch_matches_by_date(
        self,
        source,
        source_registry: DataSourceRegistry,
        request: CollectionRequest
    ) -> List[Dict[str, Any]]:
        """按日期范围获取比赛"""
        # 使用数据源的日期范围端点
        if source_registry.name == "sportmonks":
            # Sportmonks 有专门的日期范围端点
            endpoint = source_registry.endpoints.get("fixtures_between")
            if endpoint:
                path = endpoint["path"].replace("{from}", request.date_from).replace("{to}", request.date_to)
                # 这里需要实现实际的API调用
                pass

        # 使用通用方法
        matches = await source.get_fixtures(
            request.league or "",
            request.season,
            request.team,
            request.date_from,
            request.date_to
        )
        return [m.__dict__ for m in matches]

    async def _fetch_matches_by_league(
        self,
        source,
        source_registry: DataSourceRegistry,
        request: CollectionRequest
    ) -> List[Dict[str, Any]]:
        """按联赛获取比赛"""
        matches = await source.get_matches(
            request.league,
            request.season,
            request.team,
            request.limit
        )
        return [m.__dict__ for m in matches]

    def _save_to_database(
        self,
        table: str,
        records: List[Dict[str, Any]],
        key_fields: List[str]
    ) -> int:
        """保存数据到数据库"""
        if not records:
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        executed = 0

        try:
            for record in records:
                # 生成UPSERT SQL
                sql, values = self.data_cleaner.sql_generator.generate_upsert(
                    table, record, key_fields
                )

                try:
                    cursor.execute(sql, values)
                    executed += 1
                except Exception as e:
                    print(f"SQL执行失败: {e}\nSQL: {sql}")

            conn.commit()
        finally:
            conn.close()

        return executed

    def _get_key_fields(self, table: str) -> List[str]:
        """获取表的主键字段"""
        key_fields_map = {
            "matches": ["match_id"],
            "teams": ["team_id"],
            "players": ["player_id"],
            "standings": ["season_id", "league_id", "team_id"],
            "leagues": ["league_id"],
            "seasons": ["season_id"],
        }
        return key_fields_map.get(table, ["id"])

    def get_available_tables(self) -> List[str]:
        """获取可采集的表列表"""
        tables = set()
        for source in self.registry_manager.list_sources():
            tables.update(source.field_mappings.keys())
        return list(tables)

    def get_table_fields(self, table: str) -> Dict[str, List[str]]:
        """获取某表在各数据源中可提供的字段"""
        result = {}
        for source in self.registry_manager.list_sources():
            fields = source.get_available_fields(table)
            if fields:
                result[source.name] = list(fields)
        return result

    def get_source_capabilities(self, source_name: str) -> Dict[str, Any]:
        """获取数据源的能力详情"""
        source = self.registry_manager.get(source_name)
        if not source:
            return {}

        return {
            "name": source.name,
            "type": source.source_type.value,
            "description": source.description,
            "categories": list(source.categories),
            "tables": list(source.field_mappings.keys()),
            "rate_limit": source.rate_limit,
            "priority": source.priority,
            "enabled": source.enabled,
            "league_ids": source.league_ids,
        }


class CollectionTaskManager:
    """采集任务管理器"""

    def __init__(self, service: UnifiedCollectionService):
        self.service = service
        self.tasks: Dict[str, CollectionResult] = {}
        self.task_queue: List[CollectionRequest] = []

    def add_task(self, request: CollectionRequest) -> str:
        """添加采集任务"""
        task_id = f"{request.table}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.task_queue.append(request)
        return task_id

    async def run_task(self, request: CollectionRequest) -> CollectionResult:
        """执行单个任务"""
        result = await self.service.collect(request)
        task_id = f"{request.table}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.tasks[task_id] = result
        return result

    async def run_all_tasks(self) -> List[CollectionResult]:
        """执行所有任务"""
        results = []
        for request in self.task_queue:
            result = await self.run_task(request)
            results.append(result)
        self.task_queue.clear()
        return results

    def get_task_history(self) -> Dict[str, CollectionResult]:
        """获取任务历史"""
        return self.tasks


# API路由集成
def get_collection_service() -> UnifiedCollectionService:
    """获取采集服务实例"""
    return UnifiedCollectionService()


# 全局实例
collection_service = UnifiedCollectionService()