"""
FBref爬虫配置

数据源: fbref.com (免费, 无需认证, 爬虫)
覆盖联赛: 英超/西甲/德甲/意甲/法甲/荷甲/J联赛/K联赛/MLS等
特色: xG数据/球员高级统计/球队统计
"""

BASE_URL = "https://fbref.com"
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 3  # 爬虫建议间隔3秒

# 联赛URL映射
LEAGUE_URLS = {
    "premier_league": "https://fbref.com/en/comps/9/Premier-League-Stats",
    "la_liga": "https://fbref.com/en/comps/12/La-Liga-Stats",
    "bundesliga": "https://fbref.com/en/comps/20/Bundesliga-Stats",
    "serie_a": "https://fbref.com/en/comps/11/Serie-A-Stats",
    "ligue_1": "https://fbref.com/en/comps/13/Ligue-1-Stats",
    "eredivisie": "https://fbref.com/en/comps/23/Eredivisie-Stats",
    "championship": "https://fbref.com/en/comps/10/Championship-Stats",
    "j1_league": "https://fbref.com/en/comps/51/J1-League-Stats",
    "k1_league": "https://fbref.com/en/comps/55/K-League-1-Stats",
    "mls": "https://fbref.com/en/comps/74/MLS-Stats",
    "europa_league": "https://fbref.com/en/comps/19/Europa-League-Stats",
    "champions_league": "https://fbref.com/en/comps/8/Champions-League-Stats",
    "world_cup": "https://fbref.com/en/comps/1/World-Cup-Stats",
}

# 中文映射
LEAGUE_CN = {
    "英超": "premier_league", "西甲": "la_liga", "德甲": "bundesliga",
    "意甲": "serie_a", "法甲": "ligue_1", "荷甲": "eredivisie",
    "英冠": "championship", "J联赛": "j1_league", "K联赛": "k1_league",
    "MLS": "mls", "欧联": "europa_league", "欧冠": "champions_league",
}

# FBref页面ID映射 (comp ID)
COMP_IDS = {
    "premier_league": 9, "la_liga": 12, "bundesliga": 20,
    "serie_a": 11, "ligue_1": 13, "eredivisie": 23,
    "championship": 10, "j1_league": 51, "k1_league": 55,
    "mls": 74, "europa_league": 19, "champions_league": 8,
}