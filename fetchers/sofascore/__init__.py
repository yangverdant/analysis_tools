"""
Sofascore 实时数据获取工具

主源: api.sofascore.com
备用: football-data.org

提供: 实时比分、赛程、比赛事件、比赛统计
"""

from fetchers.sofascore.get_live import (
    get_live_matches, get_upcoming_matches,
    get_match_events, get_match_statistics
)
