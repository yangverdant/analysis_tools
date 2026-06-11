"""
The Odds API数据源配置

数据源: the-odds-api.com (免费计划: 500次/月)
特色: 多家博彩公司实时赔率 (欧赔/亚盘/大小球)
覆盖: 英超/西甲/德甲/意甲/法甲/欧冠等
"""

API_KEY = "73eb627525msh86bc5d05071e3a6p143527jsna83ac1e2e6fc"  # RapidAPI代理
BASE_URL = "https://api.the-odds-api.com/v4"
RAPIDAPI_URL = "https://sports-betting-odds1.p.rapidapi.com"
RAPIDAPI_HOST = "sports-betting-odds1.p.rapidapi.com"
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 2

# 赔率市场
MARKETS = {
    "h2h": "胜负平 (1X2)",
    "spreads": "亚盘/让球",
    "totals": "大小球",
    "outrights": "冠军/出线",
}

# 联赛代码映射 (the-odds-api格式)
SPORT_KEYS = {
    "soccer_epl": "英超",
    "soccer_germany_bundesliga": "德甲",
    "soccer_spain_la_liga": "西甲",
    "soccer_italy_serie_a": "意甲",
    "soccer_france_ligue_one": "法甲",
    "soccer_champions_league": "欧冠",
    "soccer_europa_league": "欧联",
    "soccer_netherlands_eredivisie": "荷甲",
    "soccer_portugal_primeira_liga": "葡超",
    "soccer_japan_j_league": "J联赛",
    "soccer_korea_kleague1": "K联赛",
    "soccer_fifa_world_cup": "世界杯",
}

SPORT_CN = {v: k for k, v in SPORT_KEYS.items()}