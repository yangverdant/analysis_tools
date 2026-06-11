"""
去重合并 — 同一比赛多源数据的合并策略

规则:
1. 基础字段(date, home_team, away_team)已存在 → 跳过
2. 扩展字段不存在 → 添加，带源标签
3. 扩展字段已存在但值相同 → 跳过
4. 扩展字段已存在但值不同 → 保留为 source_field 格式

使用示例:
    from fetchers.adapter.merger import merge_records

    existing = {"date": "2026-05-25", "home_team": "Arsenal", "home_score": 2}
    new = {"date": "2026-05-25", "home_team": "Arsenal", "home_score": 3, "home_xg": 1.8}
    merged = merge_records(existing, new, "okooo")
    # merged.okooo_home_score = 3, merged.home_xg = 1.8
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 合并时不变的锚定字段 — 这些是比赛的核心标识，多源应一致
ANCHOR_FIELDS = {
    "match_key", "date", "home_team", "away_team", "league", "league_standard",
    "season", "source"
}

# 合并时跳过的元数据字段
SKIP_FIELDS = {"_computed", "_meta", "raw_date", "raw_home_team", "raw_away_team", "raw_league"}


def merge_records(existing: Dict[str, Any], new_data: Dict[str, Any],
                  source: str) -> Dict[str, Any]:
    """合并同一比赛的多源数据

    Args:
        existing: 已有记录（可能来自多个源）
        new_data: 新源数据
        source: 新数据来源标识

    Returns:
        合并后的记录
    """
    merged = dict(existing)

    for key, value in new_data.items():
        if key in SKIP_FIELDS:
            continue
        if value is None or value == "":
            continue

        if key in ANCHOR_FIELDS:
            # 锚定字段：已有就跳过（第一条源为准）
            if key not in merged or merged[key] is None or merged[key] == "":
                merged[key] = value
            continue

        if key not in merged or merged[key] is None:
            # 新字段：直接添加
            merged[key] = value
            continue

        existing_val = merged[key]

        # 值相同：跳过
        if _values_equal(existing_val, value):
            continue

        # 值不同：用 source_key 格式保留
        source_key = f"{source}_{key}"

        # 如果原始字段还未按源标记，先把现有值也标记来源
        if key not in ANCHOR_FIELDS and not key.startswith("_"):
            original_source = existing.get("source", "unknown")
            orig_source_key = f"{original_source}_{key}"
            if orig_source_key not in merged:
                merged[orig_source_key] = existing_val

        merged[source_key] = value

    # 记录数据来源列表
    sources = merged.get("_sources", [])
    if source not in sources:
        sources.append(source)
    merged["_sources"] = sources

    return merged


def _values_equal(v1: Any, v2: Any) -> bool:
    """比较两个值是否相等（处理类型差异）"""
    if v1 == v2:
        return True
    # 数值比较：1 和 1.0 应相等
    try:
        if float(v1) == float(v2):
            return True
    except (ValueError, TypeError):
        pass
    # 字符串比较：忽略前后空格
    if isinstance(v1, str) and isinstance(v2, str):
        if v1.strip().lower() == v2.strip().lower():
            return True
    return False


def merge_match_group(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """将同一match_key的多条记录合并为一条

    Args:
        records: 同一比赛的多条记录（不同源）

    Returns:
        合并后的单条记录
    """
    if not records:
        return {}
    if len(records) == 1:
        records[0]["_sources"] = [records[0].get("source", "unknown")]
        return records[0]

    # 按数据质量排序：有更多字段的排前面
    sorted_recs = sorted(records, key=lambda r: len([v for v in r.values() if v is not None]), reverse=True)

    result = dict(sorted_recs[0])
    result["_sources"] = [result.get("source", "unknown")]

    for rec in sorted_recs[1:]:
        source = rec.get("source", "unknown")
        result = merge_records(result, rec, source)

    return result