"""
Soccerway爬虫配置

数据源: int.soccerway.com (免费, 爬虫)
覆盖: 英超/德甲/西甲/意甲/法甲
特色: 比赛数据/积分榜
"""

BASE_URL = "https://int.soccerway.com"
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 5

LEAGUE_URLS = {
    "premier_league": "https://int.soccerway.com/national/england/premier-league/",
    "bundesliga": "https://int.soccerway.com/national/germany/bundesliga/",
    "la_liga": "https://int.soccerway.com/national/spain/primera-division/",
    "serie_a": "https://int.soccerway.com/national/italy/serie-a/",
    "ligue_1": "https://int.soccerway.com/national/france/ligue-1/",
}

LEAGUE_CN = {
    "英超": "premier_league", "德甲": "bundesliga", "西甲": "la_liga",
    "意甲": "serie_a", "法甲": "ligue_1",
}