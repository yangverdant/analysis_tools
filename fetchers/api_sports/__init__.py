"""
api-sports.io数据获取工具

数据源: api-sports.io / RapidAPI
提供: 赛程/赔率/伤病 (与apifootball同源, RapidAPI接入)
"""

from fetchers.api_sports.get_data import get_fixtures, get_odds, get_injuries