"""
比赛复合键 — 跨源比赛匹配的核心工具

功能:
1. 生成标准化比赛键 (make_match_key)
2. 比较两个比赛键是否匹配 (match_keys_match)
3. 从比赛数据中提取比赛键 (make_key_from_match_data)

比赛键格式: "YYYY-MM-DD|standardized_home_team|standardized_away_team"
日期和队名都经过标准化处理，可以跨源匹配。

使用示例:
    from fetchers.common.match_key import make_match_key, match_keys_match

    make_match_key("2026-05-25", "Arsenal", "Chelsea")
    # → "2026-05-25|arsenal|chelsea"

    # 跨源匹配: apifootball的"Arsenal FC" vs the_odds_api的"Arsenal"
    k1 = make_match_key("2026-05-25", "Arsenal FC", "Chelsea FC")
    k2 = make_match_key("2026-05-25", "Arsenal", "Chelsea")
    match_keys_match(k1, k2)  # → True
"""

from typing import Dict, Optional
from difflib import SequenceMatcher

from fetchers.common.team_names import normalize_team_name
from fetchers.common.date_utils import normalize_date


def make_match_key(date, home_team: str, away_team: str) -> str:
    """生成标准化比赛键

    Args:
        date: 任何格式的日期 (字符串、timestamp、None)
        home_team: 任何语言/格式的主队名
        away_team: 任何语言/格式的客队名

    Returns:
        "YYYY-MM-DD|standardized_home|standardized_away" (全小写)
        如果date无法解析: "UNKNOWN|standardized_home|standardized_away"
    """
    d = normalize_date(date) or "UNKNOWN"
    h = normalize_team_name(home_team).lower() if home_team else ""
    a = normalize_team_name(away_team).lower() if away_team else ""
    return f"{d}|{h}|{a}"


def make_key_from_match_data(data: Dict) -> str:
    """从比赛数据字典中提取比赛键

    自动识别常见的字段名:
    - 日期: date, match_date, commence_time, start_time, match_time
    - 主队: home_team, home_team_cn, HomeTeam, match_hometeam_name
    - 客队: away_team, away_team_cn, AwayTeam, match_awayteam_name

    Args:
        data: 比赛数据字典 (任何数据源格式)

    Returns:
        标准化比赛键
    """
    # 日期字段候选
    date_candidates = ["date", "match_date", "commence_time", "start_time",
                       "match_time", "Date", "matchDateTime"]
    date_val = None
    for key in date_candidates:
        if key in data:
            date_val = data[key]
            break

    # 主队字段候选
    home_candidates = ["home_team", "home_team_cn", "HomeTeam",
                       "match_hometeam_name", "homeTeam", "home"]
    home_val = ""
    for key in home_candidates:
        if key in data and data[key]:
            home_val = data[key]
            break

    # 客队字段候选
    away_candidates = ["away_team", "away_team_cn", "AwayTeam",
                       "match_awayteam_name", "awayTeam", "away"]
    away_val = ""
    for key in away_candidates:
        if key in data and data[key]:
            away_val = data[key]
            break

    return make_match_key(date_val, home_val, away_val)


def match_keys_match(key1: str, key2: str, threshold: float = 0.85) -> bool:
    """判断两个比赛键是否匹配

    日期必须完全一致，队名允许微小差异（如 "Arsenal FC" vs "Arsenal"）

    Args:
        key1: 标准化比赛键
        key2: 标准化比赛键
        threshold: 队名相似度阈值 (0-1)

    Returns:
        True 如果日期一致且两队名相似度都超过阈值
    """
    parts1 = key1.split("|")
    parts2 = key2.split("|")

    if len(parts1) != 3 or len(parts2) != 3:
        return False

    # 日期必须完全一致
    if parts1[0] != parts2[0] and parts1[0] != "UNKNOWN" and parts2[0] != "UNKNOWN":
        return False

    # 队名相似度
    home_sim = SequenceMatcher(None, parts1[1], parts2[1]).ratio()
    away_sim = SequenceMatcher(None, parts1[2], parts2[2]).ratio()

    return home_sim >= threshold and away_sim >= threshold


def parse_match_key(key: str) -> Optional[Dict]:
    """解析比赛键为组成部分

    Args:
        key: "YYYY-MM-DD|home|away"

    Returns:
        {"date": "YYYY-MM-DD", "home_team": "标准英文名", "away_team": "标准英文名"}
        或 None
    """
    parts = key.split("|")
    if len(parts) != 3:
        return None

    # 队名从小写恢复为标准英文名
    home = normalize_team_name(parts[1]) if parts[1] else ""
    away = normalize_team_name(parts[2]) if parts[2] else ""

    return {
        "date": parts[0] if parts[0] != "UNKNOWN" else None,
        "home_team": home,
        "away_team": away,
    }


if __name__ == "__main__":
    print("=== 比赛键测试 ===")

    # 生成测试
    keys = [
        make_match_key("2026-05-25", "Arsenal", "Chelsea"),
        make_match_key("2026-05-25T15:00:00Z", "枪手", "蓝军"),
        make_match_key("25/05/2026", "Man City", "Liverpool"),
        make_key_from_match_data({"date": "2026-05-25", "home_team": "Arsenal FC", "away_team": "Chelsea FC", "league": "PL"}),
        make_key_from_match_data({"Date": "25/05/2026", "HomeTeam": "Arsenal", "AwayTeam": "Chelsea"}),
    ]
    for k in keys:
        print(f"  make_match_key -> {k}")

    # 匹配测试
    print("\n=== 匹配测试 ===")
    match_tests = [
        ("2026-05-25|arsenal|chelsea", "2026-05-25|arsenal|chelsea", True),
        ("2026-05-25|arsenal fc|chelsea fc", "2026-05-25|arsenal|chelsea", True),
        ("2026-05-25|manchester city|liverpool", "2026-05-25|man city|liverpool", True),
        ("2026-05-25|arsenal|chelsea", "2026-05-26|arsenal|chelsea", False),
        ("2026-05-25|arsenal|chelsea", "2026-05-25|liverpool|man city", False),
    ]
    for k1, k2, expected in match_tests:
        result = match_keys_match(k1, k2)
        ok = "OK" if result == expected else "FAIL"
        print(f"  {ok} match_keys_match({k1!r}, {k2!r}) -> {result} (expect: {expected})")