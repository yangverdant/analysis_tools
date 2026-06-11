"""
跨源数据关联工具

功能:
1. 给定目标比赛(date+home+away)，从多个源的数据中找到对应记录 (find_match_across_sources)
2. 给定球队名，从新闻源中找到相关新闻 (find_team_news)
3. 一站式聚合比赛全部关联数据 (get_match_context)

使用示例:
    from fetchers.common.linker import get_match_context

    context = get_match_context("2026-05-25", "Arsenal", "Chelsea", all_data)
    # context 包含: results, odds, xg, lineups, injuries, weather, news, highlights
"""

import logging
from typing import Any, Dict, List, Optional

from fetchers.common.team_names import normalize_team_name, get_team_aliases, is_same_team
from fetchers.common.match_key import make_match_key, match_keys_match, make_key_from_match_data
from fetchers.common.league_names import normalize_league_name

logger = logging.getLogger(__name__)


def find_match_across_sources(
    date: str,
    home_team: str,
    away_team: str,
    sources_data: Dict[str, List[Dict]],
    threshold: float = 0.85,
) -> Dict[str, Dict]:
    """从多个数据源中找到与目标比赛匹配的记录

    Args:
        date: 比赛日期 (任何格式)
        home_team: 主队名 (任何语言/格式)
        away_team: 客队名 (任何语言/格式)
        sources_data: {"源名": [比赛数据列表]}
        threshold: 匹配阈值

    Returns:
        {"源名": 匹配的比赛数据dict} — 每个源最多匹配一条
    """
    target_key = make_match_key(date, home_team, away_team)
    results = {}

    for source_name, matches in sources_data.items():
        if not isinstance(matches, list):
            continue
        for match in matches:
            if not isinstance(match, dict):
                continue
            match_key = make_key_from_match_data(match)
            if match_keys_match(target_key, match_key, threshold):
                results[source_name] = match
                break

    return results


def find_team_news(
    team_name: str,
    news_sources: Dict[str, List[Dict]],
    date: Optional[str] = None,
) -> List[Dict]:
    """从新闻源中找到与指定球队相关的新闻

    通过球队名+所有别名在标题中做子字符串匹配。
    如果提供date，还检查新闻日期是否匹配。

    Args:
        team_name: 球队名 (任何语言/格式)
        news_sources: {"源名": [新闻列表]}
        date: 可选日期过滤

    Returns:
        匹配的新闻列表 (带source字段)
    """
    aliases = get_team_aliases(team_name)
    # 所有可能的名字 (小写用于匹配)
    alias_lower = [a.lower() for a in aliases if a]
    # 加上原始输入
    alias_lower.append(team_name.lower())

    # 去重
    alias_lower = list(set(alias_lower))

    results = []
    for source_name, news_list in news_sources.items():
        if not isinstance(news_list, list):
            continue
        for news in news_list:
            if not isinstance(news, dict):
                continue
            title = news.get("title", "")
            if not title:
                continue

            title_lower = title.lower()
            matched = any(alias in title_lower for alias in alias_lower)

            if matched:
                entry = dict(news)
                entry["_matched_team"] = normalize_team_name(team_name)
                entry["_matched_source"] = source_name

                # 日期过滤
                if date:
                    news_date = news.get("date", "")
                    from fetchers.common.date_utils import normalize_date
                    if normalize_date(news_date) != normalize_date(date):
                        continue

                results.append(entry)

    return results


def get_match_context(
    date: str,
    home_team: str,
    away_team: str,
    all_data: Dict[str, Any],
) -> Dict:
    """一站式聚合比赛全部关联数据

    Args:
        date: 比赛日期
        home_team: 主队名
        away_team: 客队名
        all_data: 所有源的数据，格式:
            {
                "results": {"apifootball": [...], "football_data_org": [...], ...},
                "odds": {"the_odds_api": [...], "okooo": [...], ...},
                "xg": {"understat": [...], "statsbomb": [...], ...},
                "lineups": {"bifen188": [...], ...},
                "injuries": {"premierleague": [...], ...},
                "weather": {"wttr_in": [...], ...},
                "news": {"zhibo8": [...], ...},
                "highlights": {"scorebat": [...], ...},
            }

    Returns:
        {
            "match_key": "2026-05-25|arsenal|chelsea",
            "date": "2026-05-25",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "results": {"apifootball": {...}, ...},
            "odds": {"the_odds_api": {...}, ...},
            "xg": {"understat": {...}, ...},
            "lineups": {"bifen188": {...}, ...},
            "injuries": {"premierleague": [...], ...},
            "weather": {...},
            "news": [...],
            "highlights": [...],
        }
    """
    from fetchers.common.date_utils import normalize_date
    from fetchers.common.team_names import team_to_city, team_to_stadium

    standard_home = normalize_team_name(home_team)
    standard_away = normalize_team_name(away_team)
    standard_date = normalize_date(date) or date

    context = {
        "match_key": make_match_key(date, home_team, away_team),
        "date": standard_date,
        "home_team": standard_home,
        "away_team": standard_away,
        "home_city": team_to_city(home_team),
        "home_stadium": team_to_stadium(home_team),
        "results": {},
        "odds": {},
        "xg": {},
        "lineups": {},
        "injuries": {},
        "weather": {},
        "news": [],
        "highlights": [],
    }

    # 比赛结果 / 赔率 / xG / 阵容 — 用match_key匹配
    for category in ["results", "odds", "xg", "lineups"]:
        sources = all_data.get(category, {})
        if isinstance(sources, dict):
            context[category] = find_match_across_sources(
                date, home_team, away_team, sources
            )

    # 伤病 — 按球队匹配
    injury_sources = all_data.get("injuries", {})
    if isinstance(injury_sources, dict):
        for source_name, injury_list in injury_sources.items():
            if not isinstance(injury_list, list):
                continue
            matched = []
            for inj in injury_list:
                if not isinstance(inj, dict):
                    continue
                team_val = inj.get("team", "")
                if is_same_team(team_val, home_team) or is_same_team(team_val, away_team):
                    matched.append(inj)
            if matched:
                context["injuries"][source_name] = matched

    # 天气 — 按日期+主场城市匹配
    weather_sources = all_data.get("weather", {})
    if isinstance(weather_sources, dict):
        for source_name, weather_list in weather_sources.items():
            if isinstance(weather_list, list):
                for w in weather_list:
                    if not isinstance(w, dict):
                        continue
                    w_city = w.get("city", "")
                    w_date = w.get("date", "")
                    from fetchers.common.date_utils import normalize_date as nd
                    city_match = is_same_team(home_team, w_city) or (
                        team_to_city(home_team) and team_to_city(home_team).lower() == w_city.lower()
                    )
                    date_match = nd(w_date) == standard_date
                    if city_match and date_match:
                        context["weather"][source_name] = w
                        break
            elif isinstance(weather_list, dict):
                w_city = weather_list.get("city", "")
                w_date = weather_list.get("date", "")
                from fetchers.common.date_utils import normalize_date as nd
                city_match = (
                    team_to_city(home_team) and team_to_city(home_team).lower() == w_city.lower()
                )
                date_match = nd(w_date) == standard_date
                if city_match and date_match:
                    context["weather"][source_name] = weather_list

    # 新闻 — 按球队+日期匹配
    news_sources = all_data.get("news", {})
    if isinstance(news_sources, dict):
        context["news"] = find_team_news(home_team, news_sources, date)
        away_news = find_team_news(away_team, news_sources, date)
        seen_titles = {n.get("title", "") for n in context["news"]}
        for n in away_news:
            if n.get("title", "") not in seen_titles:
                context["news"].append(n)

    # 视频集锦 — 按match_key匹配
    highlight_sources = all_data.get("highlights", {})
    if isinstance(highlight_sources, dict):
        for source_name, hl_list in highlight_sources.items():
            if not isinstance(hl_list, list):
                continue
            for hl in hl_list:
                if not isinstance(hl, dict):
                    continue
                hl_home = hl.get("home_team", "")
                hl_away = hl.get("away_team", "")
                if hl_home and hl_away:
                    hl_key = make_match_key(date, hl_home, hl_away)
                    if match_keys_match(context["match_key"], hl_key):
                        context["highlights"].append(hl)
                        break

    return context


if __name__ == "__main__":
    # 简单测试
    mock_data = {
        "results": {
            "apifootball": [
                {"date": "2026-05-25", "home_team": "Arsenal FC", "away_team": "Chelsea FC",
                 "home_score": 2, "away_score": 1, "league": "Premier League"}
            ]
        },
        "odds": {
            "the_odds_api": [
                {"commence_time": "2026-05-25T15:00:00Z", "home_team": "Arsenal", "away_team": "Chelsea",
                 "odds": []}
            ]
        },
        "weather": {
            "wttr_in": [
                {"city": "London", "date": "2026-05-25", "temp_c": 18}
            ]
        },
        "news": {
            "zhibo8": [
                {"title": "枪手2-1力克蓝军！阿森纳主场获胜", "date": "2026-05-25", "url": "https://..."},
                {"title": "利物浦爆冷输球", "date": "2026-05-25", "url": "https://..."}
            ]
        }
    }

    ctx = get_match_context("2026-05-25", "Arsenal", "Chelsea", mock_data)
    from fetchers.common.match_key import parse_match_key
    import json

    print("=== 比赛上下文测试 ===")
    print(f"  match_key: {ctx['match_key']}")
    print(f"  results: {list(ctx['results'].keys())}")
    print(f"  weather: {list(ctx['weather'].keys())}")
    print(f"  news count: {len(ctx['news'])}")
    for n in ctx["news"]:
        print(f"    - {n['title']}")