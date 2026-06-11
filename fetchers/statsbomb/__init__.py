"""
StatsBomb xG数据获取工具

数据源: StatsBomb Open Data (本地JSON)
提供: 比赛xG/事件数据/球员动作
"""

from fetchers.statsbomb.get_xg import get_competition_matches, get_match_xg, get_match_events