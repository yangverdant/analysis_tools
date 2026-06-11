"""
OpenLigaDB数据获取工具

数据源: api.openligadb.de (免费, 无需认证)
提供: 德甲/德乙/英超比赛数据
"""

from fetchers.openligadb.get_matches import (
    get_current_matches, get_matchday_matches, get_match_detail, get_available_matchdays
)