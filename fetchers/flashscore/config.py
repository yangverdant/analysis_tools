"""
FlashScore爬虫配置

数据源: flashscore.com (爬虫, 需要绕反爬)
特色: 实时比分/比赛统计/赔率对比
"""

BASE_URL = "https://www.flashscore.com"
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 5

# 联赛ID映射
LEAGUE_IDS = {
    "premier_league": "/football/england/premier-league/",
    "la_liga": "/football/spain/laliga/",
    "bundesliga": "/football/germany/bundesliga/",
    "serie_a": "/football/italy/serie-a/",
    "ligue_1": "/football/france/ligue-1/",
    "champions_league": "/football/europe/champions-league/",
}

LEAGUE_CN = {
    "英超": "premier_league", "西甲": "la_liga", "德甲": "bundesliga",
    "意甲": "serie_a", "法甲": "ligue_1", "欧冠": "champions_league",
}