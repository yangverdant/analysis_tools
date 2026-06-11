"""
适配器入口 — 原始fetcher数据 → 统一格式

核心流程:
1. 查字段映射表 (field_map)
2. 字段重命名
3. 值标准化 (normalizer)
4. 计算派生字段 (match_key等)
5. 添加元数据

使用示例:
    from fetchers.adapter import adapt

    # 批量适配
    raw = get_livescores()  # apifootball原始输出
    unified = adapt("apifootball", "get_livescores", raw)

    # 单条适配
    single = adapt_one("apifootball", "get_livescores", raw[0])
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fetchers.adapter.field_map import get_field_map, get_data_type
from fetchers.adapter.normalizer import normalize_record

logger = logging.getLogger(__name__)


def adapt(fetcher_name: str, func_name: str, raw_data: Any) -> List[Dict[str, Any]]:
    """将fetcher原始输出翻译为统一格式

    Args:
        fetcher_name: 源名称 (如 "apifootball", "okooo")
        func_name: 函数名 (如 "get_livescores")
        raw_data: 原始返回数据 (List[Dict], Dict, 或其他)

    Returns:
        统一格式的记录列表
    """
    fmap = get_field_map(fetcher_name, func_name)

    # 没有映射表：passthrough + 添加source
    if not fmap:
        logger.warning(f"无字段映射: {fetcher_name}.{func_name}, 使用passthrough")
        return _passthrough(fetcher_name, raw_data)

    # 处理不同返回类型
    if isinstance(raw_data, dict):
        records = [raw_data]
    elif isinstance(raw_data, list):
        records = raw_data
    else:
        logger.warning(f"未知返回类型: {type(raw_data)} for {fetcher_name}.{func_name}")
        return _passthrough(fetcher_name, raw_data)

    result = []
    for record in records:
        if not isinstance(record, dict):
            continue
        adapted = _adapt_one_record(record, fmap, fetcher_name, func_name)
        result.append(adapted)

    return result


def adapt_one(fetcher_name: str, func_name: str, raw_record: Dict) -> Dict[str, Any]:
    """适配单条记录"""
    fmap = get_field_map(fetcher_name, func_name)
    if not fmap:
        record = dict(raw_record)
        record["_fetcher"] = fetcher_name
        record["_func"] = func_name
        return record
    return _adapt_one_record(raw_record, fmap, fetcher_name, func_name)


def _adapt_one_record(record: Dict, fmap: Dict, fetcher_name: str,
                       func_name: str) -> Dict[str, Any]:
    """单条记录的适配流程"""
    result = {}

    # 1. 字段重命名
    for src_field, dst_field in fmap.items():
        if src_field.startswith("_"):
            continue
        if src_field in record:
            result[dst_field] = record[src_field]

    # 2. 计算派生字段
    computed = fmap.get("_computed", {})
    for dst_field, compute_fn in computed.items():
        try:
            value = compute_fn(record)
            if value:
                result[dst_field] = value
        except Exception as e:
            logger.debug(f"计算字段失败 [{dst_field}]: {e}")

    # 3. 保留未映射的原始字段（放在 _raw 命名空间下）
    mapped_src_fields = {k for k in fmap.keys() if not k.startswith("_")}
    for key, value in record.items():
        if key not in mapped_src_fields and key not in result:
            result[f"_raw_{key}"] = value

    # 4. 值标准化
    result = normalize_record(result)

    # 5. 添加元数据
    result["_fetcher"] = fetcher_name
    result["_func"] = func_name
    result["_data_type"] = fmap.get("_meta", {}).get("data_type", "unknown")

    # 确保source字段存在
    if "source" not in result:
        result["source"] = fetcher_name

    return result


def _passthrough(fetcher_name: str, raw_data: Any) -> List[Dict[str, Any]]:
    """无映射表时的passthrough模式"""
    if isinstance(raw_data, dict):
        raw_data["_fetcher"] = fetcher_name
        raw_data["_data_type"] = "unknown"
        return [raw_data]
    elif isinstance(raw_data, list):
        result = []
        for item in raw_data:
            if isinstance(item, dict):
                item["_fetcher"] = fetcher_name
                item["_data_type"] = "unknown"
                result.append(item)
        return result
    return []