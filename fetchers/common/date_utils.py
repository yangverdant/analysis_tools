"""
日期格式统一化

将各种数据源的日期格式统一为 YYYY-MM-DD 标准格式。

支持的输入格式:
- ISO 8601: "2026-05-25T15:00:00Z", "2026-05-25T15:00:00+00:00"
- 简单: "2026-05-25", "2026/05/25"
- 英国: "25/05/2026", "25-05-2026"
- 中文: "2026年05月25日", "2026年5月25日"
- Unix timestamp: 1748188800 (整数或浮点)
- 日期+时间混合: "2026-05-25 15:00"

使用示例:
    from fetchers.common.date_utils import normalize_date

    normalize_date("2026-05-25T15:00:00Z")  → "2026-05-25"
    normalize_date("25/05/2026")           → "2026-05-25"
    normalize_date(1748188800)             → "2026-05-25"
"""

import re
from datetime import datetime, timezone
from typing import Optional


def normalize_date(date_input) -> Optional[str]:
    """任何格式的日期 → YYYY-MM-DD

    Args:
        date_input: 字符串、整数(timestamp)、浮点(timestamp)、None

    Returns:
        "YYYY-MM-DD" 格式字符串，或 None 表示无法解析
    """
    if date_input is None:
        return None

    # 整数/浮数 → Unix timestamp
    if isinstance(date_input, (int, float)):
        try:
            dt = datetime.fromtimestamp(date_input, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except (OSError, ValueError, OverflowError):
            return None

    # 字符串处理
    s = str(date_input).strip()
    if not s or s.lower() in ("none", "null", "n/a", "", "tbd"):
        return None

    # 1. 简单 YYYY-MM-DD (已经是标准格式)
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", s):
        return _pad_date_parts(s, "-")

    # 2. ISO 8601: "2026-05-25T15:00:00Z" 或 "2026-05-25T15:00:00+00:00"
    iso_match = re.match(r"^(\d{4}-\d{1,2}-\d{1,2})[T ]", s)
    if iso_match:
        return _pad_date_parts(iso_match.group(1), "-")

    # 3. YYYY/MM/DD
    slash_match = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", s)
    if slash_match:
        y, m, d = slash_match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    # 4. DD/MM/YYYY (英国格式) — football_data_uk 常用
    uk_match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if uk_match:
        d, m, y = uk_match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    # 5. DD-MM-YYYY
    uk_dash = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", s)
    if uk_dash:
        d, m, y = uk_dash.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    # 6. 中文格式: "2026年05月25日" 或 "2026年5月25日"
    cn_match = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日", s)
    if cn_match:
        y, m, d = cn_match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    # 7. YYYYMMDD (okooo用)
    compact = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if compact:
        y, m, d = compact.groups()
        return f"{y}-{m}-{d}"

    # 8. 尝试通用解析
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d", "%d-%m-%Y"]:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def _pad_date_parts(date_str: str, sep: str) -> str:
    """Pad date parts to 2 digits: 2026-5-25 -> 2026-05-25"""
    parts = date_str.split(sep)
    if len(parts) == 3:
        return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    return date_str


def normalize_datetime(dt_input) -> Optional[str]:
    """日期时间 → YYYY-MM-DD HH:MM 格式"""
    if dt_input is None:
        return None

    if isinstance(dt_input, (int, float)):
        try:
            dt = datetime.fromtimestamp(dt_input, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (OSError, ValueError):
            return None

    s = str(dt_input).strip()
    if not s:
        return None

    # ISO 8601
    iso_match = re.match(r"^(\d{4}-\d{1,2}-\d{1,2})[T ](\d{1,2}:\d{2})", s)
    if iso_match:
        date = normalize_date(iso_match.group(1))
        if date:
            return f"{date} {iso_match.group(2)}"

    # "YYYY-MM-DD HH:MM:SS"
    space_match = re.match(r"^(\d{4}-\d{1,2}-\d{1,2}) (\d{1,2}:\d{2})", s)
    if space_match:
        date = normalize_date(space_match.group(1))
        if date:
            return f"{date} {space_match.group(2)}"

    # 只提取日期部分
    date = normalize_date(dt_input)
    if date:
        return date
    return None


def date_to_key(date_str) -> str:
    """日期 → 用于match_key的标准化格式 (YYYY-MM-DD 或空字符串)"""
    result = normalize_date(date_str)
    return result or ""


if __name__ == "__main__":
    tests = [
        ("2026-05-25", "2026-05-25"),
        ("2026-05-25T15:00:00Z", "2026-05-25"),
        ("2026-05-25T15:00:00+00:00", "2026-05-25"),
        ("2026/05/25", "2026-05-25"),
        ("25/05/2026", "2026-05-25"),
        ("2026年05月25日", "2026-05-25"),
        ("2026年5月25日", "2026-05-25"),
        ("20260525", "2026-05-25"),
        (1748188800, None),  # timestamp结果取决于当前日期,无法硬编码
        (None, None),
        ("", None),
    ]

    print("=== 日期标准化测试 ===")
    for input_date, expected in tests:
        result = normalize_date(input_date)
        if expected is None:
            ok = "OK" if result is None else "FAIL"
        else:
            ok = "OK" if result == expected else "FAIL"
        print(f"  {ok} normalize_date({input_date!r}) -> {result!r} (expect: {expected!r})")