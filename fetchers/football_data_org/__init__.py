"""
football-data.org数据获取工具

数据源: api.football-data.org/v4 (免费, 需Token)
提供: 比赛/积分榜/射手榜/球队/阵容/球员
"""

from fetchers.football_data_org.get_matches import (
    get_today_matches, get_league_matches, get_standings,
    get_scorers, get_team_detail, get_match_detail
)