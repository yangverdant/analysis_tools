"""
体彩官网 (sporttery.cn) 数据获取工具

无需认证，公开API
提供: 开售比赛列表、赔率、开奖结果

可用模块:
- config: API端点、玩法类型
- get_matches: 获取比赛和赔率
"""

from fetchers.sporttery.config import PLAY_TYPES
from fetchers.sporttery.get_matches import get_match_list, get_match_results, get_odds
