"""
OpenLigaDB数据源配置

数据源: api.openligadb.de (免费, 无需认证)
覆盖: 德甲(BL1)/德乙(BL2)/英超(PL)
特色: 德国足球数据权威来源
"""

BASE_URL = "https://api.openligadb.de"
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 1

# 联赛代码映射
LEAGUE_CODES = {
    "bundesliga": "bl1", "德甲": "bl1",
    "bundesliga_2": "bl2", "德乙": "bl2",
    "premier_league": "pl", "英超": "pl",
    "liga3": "bl3", "德丙": "bl3",
}