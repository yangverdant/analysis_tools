"""
Okooo (澳客网) 数据获取工具

可用模块:
- config: 配置(Cookie、联赛映射、公司映射)
- get_match_ids: 获取比赛ID列表
- get_odds: 获取赔率数据(欧赔/亚盘/大小球/凯利)

使用前必须在 config.py 中填入有效的Cookie!
"""

from fetchers.okooo.config import COOKIE, COMPANIES, LEAGUES
from fetchers.okooo.get_match_ids import get_match_ids_by_date, get_match_ids_by_league
from fetchers.okooo.get_odds import (
    get_match_basic, get_odds_change, get_ah_change, get_ou_change,
    get_full_odds_matrix, calc_kelly_from_odds, batch_fetch_to_csv
)
