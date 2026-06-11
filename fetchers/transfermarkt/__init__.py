"""
Transfermarkt数据获取工具

数据源: transfermarkt.com (爬虫, 需绕反爬)
提供: 球员身价/转会记录/阵容
"""

from fetchers.transfermarkt.get_data import get_squad, get_player_value, get_league_valuations