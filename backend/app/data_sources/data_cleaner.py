"""
数据清洗转换器 - 将数据源数据转换为数据库格式
支持:
1. 字段映射转换
2. 数据类型转换
3. 数据验证
4. SQL语句生成
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, date, time
import re
import json

from .source_registry import (
    FieldMapping, FieldType, DataSourceRegistry, registry_manager
)


@dataclass
class TransformResult:
    """转换结果"""
    success: bool
    data: Dict[str, Any]
    errors: List[str]
    warnings: List[str]
    source: str
    table: str


class DataTransformer:
    """数据转换器"""

    def __init__(self):
        self.transform_functions = {
            "str": self._to_string,
            "int": self._to_int,
            "float": self._to_float,
            "extract_date": self._extract_date,
            "extract_time": self._extract_time,
            "parse_round": self._parse_round,
            "match_status": self._match_status,
            "league_id_fd": self._league_id_fd,
            "team_name_to_id": self._team_name_to_id,
        }

    def transform(
        self,
        raw_data: Dict[str, Any],
        mappings: List[FieldMapping],
        source: str,
        table: str
    ) -> TransformResult:
        """转换数据"""
        result = {}
        errors = []
        warnings = []

        for mapping in mappings:
            try:
                # 获取源数据值
                value = self._get_nested_value(raw_data, mapping.source_field)

                if value is None:
                    if mapping.default is not None:
                        result[mapping.db_field] = mapping.default
                    elif mapping.required:
                        errors.append(f"缺少必需字段: {mapping.db_field}")
                    continue

                # 类型转换
                if mapping.transform and mapping.transform in self.transform_functions:
                    value = self.transform_functions[mapping.transform](value)
                else:
                    value = self._convert_type(value, mapping.db_type)

                result[mapping.db_field] = value

            except Exception as e:
                if mapping.required:
                    errors.append(f"字段 {mapping.db_field} 转换失败: {str(e)}")
                else:
                    warnings.append(f"字段 {mapping.db_field} 转换失败: {str(e)}")

        return TransformResult(
            success=len(errors) == 0,
            data=result,
            errors=errors,
            warnings=warnings,
            source=source,
            table=table
        )

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """获取嵌套值，支持路径如 'score.home_score' 和数组过滤"""
        if not path or path == "None":
            return None

        parts = path.split(".")
        current = data

        for part in parts:
            if current is None:
                return None

            # 处理数组过滤，如 participants[meta.location=home]
            if "[" in part and part.endswith("]"):
                field_name = part.split("[")[0]
                filter_expr = part[part.index("[")+1:-1]

                if isinstance(current, dict):
                    current = current.get(field_name, [])
                elif isinstance(current, list):
                    current = current

                if isinstance(current, list):
                    # 解析过滤条件
                    if "=" in filter_expr:
                        filter_field, filter_value = filter_expr.split("=", 1)
                        for item in current:
                            if isinstance(item, dict):
                                nested = self._get_nested_value(item, filter_field)
                                if nested == filter_value:
                                    current = item
                                    break
                        else:
                            current = None
                    else:
                        # 索引访问
                        try:
                            idx = int(filter_expr)
                            current = current[idx] if idx < len(current) else None
                        except ValueError:
                            current = None
            else:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None

        return current

    def _convert_type(self, value: Any, target_type: FieldType) -> Any:
        """类型转换"""
        if value is None:
            return None

        if target_type == FieldType.STRING:
            return str(value)
        elif target_type == FieldType.INTEGER:
            return int(value) if value else None
        elif target_type == FieldType.FLOAT:
            return float(value) if value else None
        elif target_type == FieldType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        elif target_type == FieldType.DATE:
            return self._parse_date(value)
        elif target_type == FieldType.TIME:
            return self._parse_time(value)
        elif target_type == FieldType.DATETIME:
            return self._parse_datetime(value)

        return value

    # ===== 转换函数 =====

    def _to_string(self, value: Any) -> str:
        return str(value) if value is not None else ""

    def _to_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _to_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _extract_date(self, value: str) -> Optional[str]:
        """从datetime字符串提取日期"""
        if not value:
            return None
        try:
            dt = self._parse_datetime(value)
            return dt.strftime("%Y-%m-%d") if dt else None
        except:
            return None

    def _extract_time(self, value: str) -> Optional[str]:
        """从datetime字符串提取时间"""
        if not value:
            return None
        try:
            dt = self._parse_datetime(value)
            return dt.strftime("%H:%M:%S") if dt else None
        except:
            return None

    def _parse_round(self, value: Any) -> Optional[int]:
        """解析轮次"""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            # 提取数字
            match = re.search(r'\d+', value)
            return int(match.group()) if match else None
        return None

    def _match_status(self, value: Any) -> str:
        """比赛状态转换"""
        status_map = {
            1: "scheduled",
            2: "in_play",
            3: "paused",
            4: "finished",
            5: "postponed",
            6: "cancelled",
        }
        if isinstance(value, int):
            return status_map.get(value, "unknown")
        return str(value).lower()

    def _league_id_fd(self, value: str) -> Optional[int]:
        """football-data.org联赛代码转ID"""
        code_map = {
            "PL": 8,      # 英超
            "PD": 564,    # 西甲
            "BL1": 35,    # 德甲
            "SA": 384,    # 意甲
            "FL1": 301,   # 法甲
            "CL": 7,      # 欧冠
            "ELC": 48,    # 英冠
        }
        return code_map.get(value)

    def _team_name_to_id(self, value: str) -> Optional[int]:
        """球队名称转ID (需要查询数据库)"""
        # 这里需要实际的数据库查询
        # 暂时返回None，由调用方处理
        return None

    def _parse_date(self, value: Any) -> Optional[str]:
        """解析日期"""
        if not value:
            return None
        if isinstance(value, (date, datetime)):
            return value.strftime("%Y-%m-%d")

        # 尝试多种格式
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d"]
        for fmt in formats:
            try:
                dt = datetime.strptime(str(value), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _parse_time(self, value: Any) -> Optional[str]:
        """解析时间"""
        if not value:
            return None
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")

        # 尝试多种格式
        formats = ["%H:%M:%S", "%H:%M", "%I:%M %p"]
        for fmt in formats:
            try:
                t = datetime.strptime(str(value), fmt).time()
                return t.strftime("%H:%M:%S")
            except ValueError:
                continue
        return None

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """解析日期时间"""
        if not value:
            return None
        if isinstance(value, datetime):
            return value

        # ISO格式
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            pass

        # 其他格式
        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(str(value), fmt)
            except ValueError:
                continue
        return None


class SQLGenerator:
    """SQL语句生成器"""

    def __init__(self, db_path: str = "data/football_v2.db"):
        self.db_path = db_path

    def generate_insert(
        self,
        table: str,
        data: Dict[str, Any],
        on_conflict: str = "REPLACE"
    ) -> Tuple[str, List[Any]]:
        """生成INSERT语句"""
        if not data:
            return "", []

        fields = list(data.keys())
        placeholders = ["?" for _ in fields]
        values = [data[f] for f in fields]

        if on_conflict == "REPLACE":
            sql = f"INSERT OR REPLACE INTO {table} ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        elif on_conflict == "IGNORE":
            sql = f"INSERT OR IGNORE INTO {table} ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        else:
            sql = f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"

        return sql, values

    def generate_update(
        self,
        table: str,
        data: Dict[str, Any],
        where_fields: List[str]
    ) -> Tuple[str, List[Any]]:
        """生成UPDATE语句"""
        if not data or not where_fields:
            return "", []

        set_parts = []
        values = []
        where_parts = []

        for field, value in data.items():
            if field not in where_fields:
                set_parts.append(f"{field} = ?")
                values.append(value)

        for field in where_fields:
            where_parts.append(f"{field} = ?")
            values.append(data.get(field))

        sql = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {' AND '.join(where_parts)}"
        return sql, values

    def generate_upsert(
        self,
        table: str,
        data: Dict[str, Any],
        key_fields: List[str]
    ) -> Tuple[str, List[Any]]:
        """生成UPSERT语句 (INSERT ON CONFLICT UPDATE)"""
        if not data or not key_fields:
            return "", []

        fields = list(data.keys())
        placeholders = ["?" for _ in fields]
        values = [data[f] for f in fields]

        # 更新部分 (排除key字段)
        update_parts = [f"{f} = excluded.{f}" for f in fields if f not in key_fields]

        sql = f"""
        INSERT INTO {table} ({', '.join(fields)})
        VALUES ({', '.join(placeholders)})
        ON CONFLICT({', '.join(key_fields)})
        DO UPDATE SET {', '.join(update_parts)}
        """

        return sql.strip(), values

    def generate_batch_insert(
        self,
        table: str,
        data_list: List[Dict[str, Any]],
        on_conflict: str = "REPLACE"
    ) -> List[Tuple[str, List[Any]]]:
        """批量生成INSERT语句"""
        results = []
        for data in data_list:
            sql, values = self.generate_insert(table, data, on_conflict)
            if sql:
                results.append((sql, values))
        return results


class DataCleaner:
    """数据清洗器"""

    def __init__(self):
        self.transformer = DataTransformer()
        self.sql_generator = SQLGenerator()

    def clean_match_data(
        self,
        raw_data: Dict[str, Any],
        source_registry: DataSourceRegistry
    ) -> TransformResult:
        """清洗比赛数据"""
        mappings = source_registry.field_mappings.get("matches", [])
        return self.transformer.transform(raw_data, mappings, source_registry.name, "matches")

    def clean_team_data(
        self,
        raw_data: Dict[str, Any],
        source_registry: DataSourceRegistry
    ) -> TransformResult:
        """清洗球队数据"""
        mappings = source_registry.field_mappings.get("teams", [])
        return self.transformer.transform(raw_data, mappings, source_registry.name, "teams")

    def clean_standings_data(
        self,
        raw_data: Dict[str, Any],
        source_registry: DataSourceRegistry
    ) -> TransformResult:
        """清洗积分榜数据"""
        mappings = source_registry.field_mappings.get("standings", [])
        return self.transformer.transform(raw_data, mappings, source_registry.name, "standings")

    def clean_player_data(
        self,
        raw_data: Dict[str, Any],
        source_registry: DataSourceRegistry
    ) -> TransformResult:
        """清洗球员数据"""
        mappings = source_registry.field_mappings.get("players", [])
        return self.transformer.transform(raw_data, mappings, source_registry.name, "players")

    def batch_clean(
        self,
        raw_data_list: List[Dict[str, Any]],
        table: str,
        source_registry: DataSourceRegistry
    ) -> List[TransformResult]:
        """批量清洗数据"""
        mappings = source_registry.field_mappings.get(table, [])
        return [
            self.transformer.transform(data, mappings, source_registry.name, table)
            for data in raw_data_list
        ]

    def generate_sql_for_result(
        self,
        result: TransformResult,
        key_fields: List[str] = None
    ) -> Tuple[str, List[Any]]:
        """为转换结果生成SQL"""
        if not result.success or not result.data:
            return "", []

        if key_fields:
            return self.sql_generator.generate_upsert(result.table, result.data, key_fields)
        return self.sql_generator.generate_insert(result.table, result.data)


# 全局实例
data_cleaner = DataCleaner()
