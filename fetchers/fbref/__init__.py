"""
FBref爬虫数据获取工具

数据源: fbref.com (免费, 爬虫)
提供: 积分榜/赛程/球员高级统计/xG数据
"""

from fetchers.fbref.get_stats import get_standings, get_fixtures, get_team_stats_url