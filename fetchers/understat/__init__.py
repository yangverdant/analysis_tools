"""
Understat xG数据获取工具

数据源: understat.com (免费, 需解析JS数据)
提供: 球员/球队xG/xA数据
"""

from fetchers.understat.get_xg import get_league_players_xg, get_league_teams_xg, get_match_xg