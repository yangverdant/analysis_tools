"""
Transfermarkt爬虫配置

数据源: transfermarkt.com (爬虫, 需要绕反爬)
特色: 球员身价/转会记录/合同信息
"""

BASE_URL = "https://www.transfermarkt.com"
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 5  # 爬虫建议5秒间隔

# 联赛URL映射
LEAGUE_URLS = {
    "premier_league": "/premier-league/startseite/wettbewerb/GB1",
    "la_liga": "/la-liga/startseite/wettbewerb/ES1",
    "bundesliga": "/bundesliga/startseite/wettbewerb/L1",
    "serie_a": "/serie-a/startseite/wettbewerb/IT1",
    "ligue_1": "/ligue-1/startseite/wettbewerb/FR1",
    "eredivisie": "/eredivisie/startseite/wettbewerb/NL1",
    "champions_league": "/uefa-champions-league/startseite/wettbewerb/CL",
}

LEAGUE_CN = {
    "英超": "premier_league", "西甲": "la_liga", "德甲": "bundesliga",
    "意甲": "serie_a", "法甲": "ligue_1", "荷甲": "eredivisie",
    "欧冠": "champions_league",
}