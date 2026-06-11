"""
TheSportsDB数据获取工具

数据源: thesportsdb.com (免费, 无需Key)
提供: 比赛/球队详情/球员/联赛
"""

from fetchers.thesportsdb.get_events import (
    get_events_by_date, get_event_detail,
    get_team_detail, get_team_next_events, get_team_last_events
)