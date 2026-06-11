"""
智能数据合并采集器 - 自动判断数据来源，合并多源数据

核心功能：
1. 根据联赛+字段自动选择最佳数据源组合
2. 从多个数据源采集数据并合并
3. 自动清洗转换入库
"""

import asyncio
import sqlite3
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json

from .source_knowledge import knowledge_base, DataSourceCapability, LEAGUES
from .data_cleaner import DataCleaner, DataTransformer, SQLGenerator


@dataclass
class MatchQuery:
    """比赛查询请求"""
    league: str                              # 联赛代码
    season: Optional[str] = None             # 赛季
    date_from: Optional[str] = None          # 开始日期
    date_to: Optional[str] = None            # 结束日期
    team: Optional[str] = None               # 球队
    match_id: Optional[str] = None           # 比赛ID
    required_fields: Set[str] = field(default_factory=set)  # 需要的字段


@dataclass
class MergedMatchData:
    """合并后的比赛数据"""
    match_id: str
    data: Dict[str, Any]
    sources: Dict[str, List[str]]  # {字段名: [来源列表]}
    coverage: float  # 字段覆盖率
    missing_fields: List[str]


class IntelligentCollector:
    """智能数据采集器"""

    def __init__(self, db_path: str = "data/football_v2.db"):
        self.db_path = db_path
        self.knowledge_base = knowledge_base
        self.transformer = DataTransformer()
        self.sql_generator = SQLGenerator(db_path)

    def analyze_query(self, query: MatchQuery) -> Dict[str, Any]:
        """分析查询请求，返回数据源推荐"""
        # 获取支持该联赛的数据源
        sources = self.knowledge_base.get_sources_for_league(query.league)

        # 获取字段覆盖报告
        coverage = self.knowledge_base.get_field_coverage("match", query.required_fields)

        # 找到最佳数据源组合
        best_sources = self.knowledge_base.find_best_sources(
            "match", query.required_fields, query.league
        )

        return {
            "league": query.league,
            "league_info": self.knowledge_base.get_league_info(query.league),
            "required_fields": list(query.required_fields),
            "available_sources": [s.name for s in sources],
            "best_source_combination": [s.name for s in best_sources],
            "field_coverage": coverage,
            "recommendation": self._generate_recommendation(coverage, best_sources)
        }

    def _generate_recommendation(
        self,
        coverage: Dict[str, Dict],
        best_sources: List[DataSourceCapability]
    ) -> str:
        """生成推荐说明"""
        if not best_sources:
            return "没有找到支持的数据源"

        lines = []
        lines.append(f"推荐使用 {len(best_sources)} 个数据源:")

        for i, source in enumerate(best_sources, 1):
            cov = coverage.get(source.name, {})
            lines.append(f"  {i}. {source.name} (覆盖率: {cov.get('coverage', 0)*100:.0f}%)")

        # 检查是否有缺失字段
        all_covered = set()
        for source in best_sources:
            cov = coverage.get(source.name, {})
            all_covered.update(cov.get("covered_fields", []))

        required = set()
        for c in coverage.values():
            required.update(c.get("covered_fields", []))
            required.update(c.get("missing_fields", []))

        missing = required - all_covered
        if missing:
            lines.append(f"\n警告: 以下字段无法获取: {', '.join(missing)}")

        return "\n".join(lines)

    async def collect_match_data(
        self,
        query: MatchQuery,
        save_to_db: bool = True
    ) -> List[MergedMatchData]:
        """采集比赛数据，自动合并多源"""
        # 1. 找到最佳数据源组合
        sources = self.knowledge_base.find_best_sources(
            "match", query.required_fields, query.league
        )

        if not sources:
            return []

        # 2. 从各数据源采集数据
        all_raw_data: Dict[str, List[Dict]] = {}  # {source_name: [raw_data]}

        for source in sources:
            raw_data = await self._fetch_from_source(source, query)
            if raw_data:
                all_raw_data[source.name] = raw_data

        # 3. 合并数据
        merged_data = self._merge_multi_source_data(all_raw_data, query.required_fields)

        # 4. 保存到数据库
        if save_to_db and merged_data:
            self._save_merged_data(merged_data)

        return merged_data

    async def _fetch_from_source(
        self,
        source: DataSourceCapability,
        query: MatchQuery
    ) -> List[Dict[str, Any]]:
        """从单个数据源获取数据"""
        # 这里需要根据数据源类型调用不同的获取方法
        # 实际实现需要集成到现有的数据源管理器

        # 模拟返回数据
        return []

    def _merge_multi_source_data(
        self,
        all_raw_data: Dict[str, List[Dict]],
        required_fields: Set[str]
    ) -> List[MergedMatchData]:
        """合并多源数据"""
        # 按match_id分组
        match_groups: Dict[str, Dict[str, Dict]] = {}  # {match_id: {source_name: data}}

        for source_name, raw_list in all_raw_data.items():
            for raw in raw_list:
                # 提取match_id (需要根据数据源格式调整)
                match_id = self._extract_match_id(raw, source_name)
                if match_id:
                    if match_id not in match_groups:
                        match_groups[match_id] = {}
                    match_groups[match_id][source_name] = raw

        # 合并每组数据
        results = []
        for match_id, source_data in match_groups.items():
            merged = self._merge_single_match(match_id, source_data, required_fields)
            results.append(merged)

        return results

    def _extract_match_id(self, raw: Dict, source_name: str) -> Optional[str]:
        """从原始数据提取match_id"""
        # 根据数据源格式提取
        id_fields = {
            "sportmonks": "id",
            "football_data_org": "id",
            "thesportsdb": "idEvent",
            "fbref": None,  # 需要组合生成
        }
        field = id_fields.get(source_name)
        if field and field in raw:
            return str(raw[field])
        return None

    def _merge_single_match(
        self,
        match_id: str,
        source_data: Dict[str, Dict],
        required_fields: Set[str]
    ) -> MergedMatchData:
        """合并单场比赛的多源数据"""
        merged = {"match_id": match_id}
        sources: Dict[str, List[str]] = {}

        # 按优先级合并字段
        for source_name, raw in source_data.items():
            source_cap = self.knowledge_base.get_source(source_name)
            if not source_cap:
                continue

            # 转换数据
            for field in required_fields:
                if field in source_cap.match_fields and field not in merged:
                    field_info = source_cap.match_fields[field]
                    value = self._extract_field_value(raw, field_info["source"])

                    if value is not None:
                        merged[field] = value
                        if field not in sources:
                            sources[field] = []
                        sources[field].append(source_name)

        # 计算覆盖率
        covered = set(merged.keys()) & required_fields
        missing = required_fields - set(merged.keys())
        coverage = len(covered) / len(required_fields) if required_fields else 1.0

        return MergedMatchData(
            match_id=match_id,
            data=merged,
            sources=sources,
            coverage=coverage,
            missing_fields=list(missing)
        )

    def _extract_field_value(self, raw: Dict, source_path: str) -> Any:
        """从原始数据提取字段值"""
        if not source_path:
            return None

        parts = source_path.split(".")
        current = raw

        for part in parts:
            if current is None:
                return None

            # 处理数组索引
            if "[" in part:
                field_name = part.split("[")[0]
                if isinstance(current, dict):
                    current = current.get(field_name)
                if isinstance(current, list) and len(current) > 0:
                    current = current[0]
            else:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None

        return current

    def _save_merged_data(self, merged_data: List[MergedMatchData]) -> int:
        """保存合并后的数据到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        saved = 0

        try:
            for item in merged_data:
                sql, values = self.sql_generator.generate_upsert(
                    "matches", item.data, ["match_id"]
                )
                try:
                    cursor.execute(sql, values)
                    saved += 1
                except Exception as e:
                    print(f"保存失败 {item.match_id}: {e}")

            conn.commit()
        finally:
            conn.close()

        return saved

    def get_match_with_all_data(self, match_id: str) -> Dict[str, Any]:
        """获取比赛的完整数据（从数据库+补充采集）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 查询现有数据
        cursor.execute("SELECT * FROM matches WHERE match_id = ?", (match_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {"error": "比赛不存在"}

        existing_data = dict(row)

        # 分析缺失字段
        all_possible_fields = self.knowledge_base.get_all_match_fields()
        existing_fields = {k for k, v in existing_data.items() if v is not None}
        missing_fields = all_possible_fields - existing_fields

        return {
            "match_id": match_id,
            "existing_data": existing_data,
            "existing_fields": list(existing_fields),
            "missing_fields": list(missing_fields),
            "coverage": len(existing_fields) / len(all_possible_fields) if all_possible_fields else 0,
            "can_supplement": len(missing_fields) > 0
        }


class DataCollectionAPI:
    """数据采集API - 提供给前端调用的接口"""

    def __init__(self, db_path: str = "data/football_v2.db"):
        self.collector = IntelligentCollector(db_path)

    def get_league_sources(self, league: str) -> Dict[str, Any]:
        """获取某联赛可用的数据源"""
        sources = self.collector.knowledge_base.get_sources_for_league(league)
        league_info = self.collector.knowledge_base.get_league_info(league)

        return {
            "league": league,
            "league_info": league_info,
            "sources": [
                {
                    "name": s.name,
                    "type": s.source_type,
                    "description": s.description,
                    "categories": list(s.categories),
                    "special_features": list(s.special_features),
                    "priority": s.priority,
                }
                for s in sources
            ]
        }

    def get_available_fields(self, league: str, table: str = "match") -> Dict[str, Any]:
        """获取某联赛可用的字段"""
        sources = self.collector.knowledge_base.get_sources_for_league(league)

        all_fields: Dict[str, List[str]] = {}  # {field: [sources]}

        for source in sources:
            fields_map = getattr(source, f"{table}_fields", {})
            for field in fields_map:
                if field not in all_fields:
                    all_fields[field] = []
                all_fields[field].append(source.name)

        return {
            "league": league,
            "table": table,
            "fields": all_fields,
            "total_fields": len(all_fields)
        }

    def analyze_collection_need(
        self,
        league: str,
        fields: List[str],
        season: str = None
    ) -> Dict[str, Any]:
        """分析采集需求"""
        query = MatchQuery(
            league=league,
            season=season,
            required_fields=set(fields)
        )
        return self.collector.analyze_query(query)

    async def collect_and_merge(
        self,
        league: str,
        fields: List[str],
        season: str = None,
        date_from: str = None,
        date_to: str = None
    ) -> Dict[str, Any]:
        """采集并合并数据"""
        query = MatchQuery(
            league=league,
            season=season,
            date_from=date_from,
            date_to=date_to,
            required_fields=set(fields)
        )

        # 分析
        analysis = self.collector.analyze_query(query)

        # 采集
        results = await self.collector.collect_match_data(query)

        return {
            "success": len(results) > 0,
            "analysis": analysis,
            "collected_count": len(results),
            "coverage_avg": sum(r.coverage for r in results) / len(results) if results else 0,
            "sample": results[0].data if results else None
        }


# 全局实例
collection_api = DataCollectionAPI()
