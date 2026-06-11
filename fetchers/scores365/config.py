"""
365Scores数据源配置

数据源: webws.365scores.com (免费公开API, 无需认证)
覆盖: 全球200+联赛
特色: 实时比分/比赛事件/统计数据
"""

BASE_URL = "https://webws.365scores.com/web"
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 2

# 联赛/比赛ID映射 (competition_id)
COMPETITION_IDS = {
    "premier_league": 1, "英超": 1,
    "la_liga": 5, "西甲": 5,
    "bundesliga": 3, "德甲": 3,
    "serie_a": 4, "意甲": 4,
    "ligue_1": 2, "法甲": 2,
    "champions_league": 10, "欧冠": 10,
    "europa_league": 11, "欧联": 11,
}

# 默认查询参数
DEFAULT_PARAMS = {
    "langId": 14,       # 中文
    "timezoneName": "Asia/Shanghai",
    "userCountryId": 1,
    "appTypeId": 1,
}