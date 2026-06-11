"""
FlashLive数据源配置

数据源: flashlive-sports.p.rapidapi.com (RapidAPI)
特色: 实时比分/赛程/联赛数据
覆盖: 全球200+联赛
"""

RAPIDAPI_KEY = "232de9f410msh8da4a38f557b694p1d2d4fjsn978df1ba1263"
BASE_URL = "https://flashlive-sports.p.rapidapi.com/v1"
RAPIDAPI_HOST = "flashlive-sports.p.rapidapi.com"
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 3

# 运动类型
SPORT_IDS = {
    "football": 1,
    "basketball": 2,
    "tennis": 3,
    "hockey": 4,
    "baseball": 5,
}

# 联赛ID (部分)
LEAGUE_IDS = {
    "premier_league": "ePL",
    "la_liga": "eLL",
    "bundesliga": "eBL",
    "serie_a": "eSA",
    "ligue_1": "eL1",
    "champions_league": "eCL",
}