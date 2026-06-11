"""
TheSportsDB数据源配置

数据源: thesportsdb.com/api/v1/json/3 (免费, 无需Key)
覆盖: 多运动项目, 足球为主要内容
特色: 球队详情/球员头像/比赛集锦/阵容
"""

BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 1