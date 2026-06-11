"""
统一数据串联工具集 (fetchers/common)

核心模块:
- team_names:   队名标准化+别名匹配 (枪手→Arsenal, Man City→Manchester City)
- league_names:  联赛名标准化+ID跨源映射 (英超→Premier League, 152→Premier League)
- match_key:    比赛复合键 (date+home+away)
- date_utils:   日期格式统一化
- linker:       跨源数据关联

使用示例:
    from fetchers.common.team_names import normalize_team_name
    from fetchers.common.league_names import normalize_league_name
    from fetchers.common.match_key import make_match_key
    from fetchers.common.linker import get_match_context

    normalize_team_name("枪手")      # -> "Arsenal"
    normalize_league_name("英超")    # -> "Premier League"
    make_match_key("2026-05-25", "Arsenal", "Chelsea")  # -> "2026-05-25|arsenal|chelsea"
"""

from fetchers.common.team_names import (
    normalize_team_name,
    get_team_aliases,
    get_team_info,
    team_to_city,
    team_to_stadium,
    find_team,
    is_same_team,
    get_all_standard_names,
    get_stats as get_team_stats,
)

from fetchers.common.league_names import (
    normalize_league_name,
    league_to_source_id,
    source_id_to_league,
    get_league_aliases,
    get_league_info,
    get_all_standard_leagues,
    get_stats as get_league_stats,
)

from fetchers.common.match_key import (
    make_match_key,
    make_key_from_match_data,
    match_keys_match,
    parse_match_key,
)

from fetchers.common.date_utils import (
    normalize_date,
    normalize_datetime,
    date_to_key,
)

from fetchers.common.linker import (
    find_match_across_sources,
    find_team_news,
    get_match_context,
)