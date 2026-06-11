"""
值标准化 — 对适配后的记录做值级别的标准化

调用 fetchers/common/ 模块完成:
- home_team/away_team → normalize_team_name
- date → normalize_date
- league → normalize_league_name
- match_key → 自动计算

使用示例:
    from fetchers.adapter.normalizer import normalize_record

    record = {"home_team": "Man City", "away_team": "Ars", "date": "2026-05-25T15:00:00Z"}
    normalized = normalize_record(record)
    # normalized.home_team → "Manchester City"
    # normalized.date → "2026-05-25"
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fetchers.common.team_names import normalize_team_name
from fetchers.common.league_names import normalize_league_name
from fetchers.common.date_utils import normalize_date
from fetchers.common.match_key import make_match_key

logger = logging.getLogger(__name__)

# 需要标准化值的字段 → 对应的标准化函数
VALUE_NORMALIZERS = {
    "home_team": normalize_team_name,
    "away_team": normalize_team_name,
    "team": normalize_team_name,
    "home_team_standard": normalize_team_name,
    "away_team_standard": normalize_team_name,
    "date": normalize_date,
    "league": normalize_league_name,
    "league_standard": normalize_league_name,
}


def _extract_datetime(val: Any) -> tuple:
    """从各种日期时间格式中提取 date + time

    支持格式:
    - ISO datetime: "2026-05-25T15:00:00Z", "2026-05-25T15:00:00+08:00"
    - Unix timestamp (int): 1748188800
    - Unix timestamp (str): "1748188800"
    - 纯日期: "2026-05-25"
    - 中文日期: "2026年05月25日"
    - UK日期: "25/05/2026"

    Returns:
        (date_str, time_str) — date为YYYY-MM-DD, time为HH:MM或None
    """
    if val is None or val == "":
        return ("", None)

    # Unix timestamp (integer)
    if isinstance(val, (int, float)) and val > 1e9:
        from datetime import datetime as _dt, timezone
        try:
            dt_obj = _dt.fromtimestamp(val, tz=timezone.utc)
            return (dt_obj.strftime("%Y-%m-%d"), dt_obj.strftime("%H:%M"))
        except Exception:
            return ("", None)

    s = str(val)

    # Unix timestamp (string)
    if s.isdigit() and len(s) >= 10 and int(s) > 1e9:
        from datetime import datetime as _dt, timezone
        try:
            dt_obj = _dt.fromtimestamp(int(s), tz=timezone.utc)
            return (dt_obj.strftime("%Y-%m-%d"), dt_obj.strftime("%H:%M"))
        except Exception:
            return ("", None)

    # ISO datetime: "2026-05-25T15:00:00Z" or "2026-05-25T15:00:00+08:00"
    if "T" in s:
        parts = s.split("T")
        date_part = parts[0]
        time_raw = parts[1].split("+")[0].split("-")[0].split(".")[0].rstrip("Z")
        time_part = time_raw[:5] if len(time_raw) >= 5 else None
        return (date_part, time_part)

    # 中文日期+时间: "2026年05月25日 15:00"
    import re
    cn_match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?', s)
    if cn_match:
        y, m, d = cn_match.group(1), cn_match.group(2), cn_match.group(3)
        t = cn_match.group(4)
        return (f"{y}-{m.zfill(2)}-{d.zfill(2)}", t)

    # 纯日期 / UK日期 / 其他 — 用normalize_date处理
    date_str = normalize_date(s)
    return (date_str or "", None)


def normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """对已适配的记录做值级标准化

    对 VALUE_NORMALIZERS 中定义的字段，调用对应的标准化函数。
    保留原始值在 raw_ 前缀字段中。
    """
    normalized = dict(record)

    # 1. 日期时间提取和拆分
    # 从date字段提取date+time，处理ISO/timestamp/中文等所有格式
    dt_val = normalized.get("date", "")
    if dt_val:
        extracted_date, extracted_time = _extract_datetime(dt_val)
        if extracted_date and extracted_date != str(dt_val):
            normalized["raw_datetime"] = str(dt_val)
            normalized["date"] = extracted_date
            if extracted_time and not normalized.get("time"):
                normalized["time"] = extracted_time

    # 也检查start_time/commence_time等别名
    for alt_field in ("start_time", "commence_time"):
        alt_val = normalized.get(alt_field)
        if alt_val and not normalized.get("date"):
            extracted_date, extracted_time = _extract_datetime(alt_val)
            if extracted_date:
                normalized["raw_datetime"] = str(alt_val)
                normalized["date"] = extracted_date
                if extracted_time and not normalized.get("time"):
                    normalized["time"] = extracted_time

    # match_date / match_time 别名处理 (sporttery等)
    match_date = normalized.get("match_date")
    if match_date and not normalized.get("date"):
        extracted_date, extracted_time = _extract_datetime(match_date)
        if extracted_date:
            normalized["date"] = extracted_date
            if extracted_time and not normalized.get("time"):
                normalized["time"] = extracted_time
    match_time = normalized.get("match_time")
    if match_time and not normalized.get("time"):
        # "13:00.0" → "13:00"
        t = str(match_time).split(".")[0][:5]
        if t and ":" in t:
            normalized["time"] = t

    # 2. 值标准化
    for field, normalizer in VALUE_NORMALIZERS.items():
        value = normalized.get(field)
        if value is None or value == "" or value == "unknown":
            continue

        try:
            norm_value = normalizer(value)
            if norm_value and norm_value != value:
                normalized[f"raw_{field}"] = value
                normalized[field] = norm_value
        except Exception as e:
            logger.debug(f"标准化失败 [{field}={value}]: {e}")

    # 3. 确保match_key存在且有效
    if "match_key" not in normalized or not normalized["match_key"]:
        date = normalized.get("date", "")
        home = normalized.get("home_team", normalized.get("home_team_cn", ""))
        away = normalized.get("away_team", normalized.get("away_team_cn", ""))
        if date or home:
            normalized["match_key"] = make_match_key(date, home, away)

    return normalized


def normalize_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """批量标准化"""
    return [normalize_record(r) for r in records]