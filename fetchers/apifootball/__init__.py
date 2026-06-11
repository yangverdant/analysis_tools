"""
API-Football数据获取工具

数据源: apiv3.apifootball.com (需API Key)
提供: 实时比分/赛程/积分榜/赔率/预测/统计/阵容/交锋
"""

from fetchers.apifootball.get_data import (
    get_livescores, get_fixtures, get_match_detail,
    get_standings, get_match_odds, get_predictions,
    get_teams, get_topscorers, get_h2h
)