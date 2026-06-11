"""
赔率API数据源配置

数据源: RapidAPI Odds Feed / Bet365 / Football Betting Odds
认证: X-RapidAPI-Key header
特色: 多家博彩公司赔率/亚盘/大小球
"""

RAPIDAPI_KEY = "232de9f410msh8da4a38f557b694p1d2d4fjsn978df1ba1263"

# Odds Feed
ODDS_FEED_URL = "https://odds-feed.p.rapidapi.com"
ODDS_FEED_HOST = "odds-feed.p.rapidapi.com"

# Bet365 API
BET365_URL = "https://bet365-api.p.rapidapi.com"
BET365_HOST = "bet365-api.p.rapidapi.com"

# Football Betting Odds
FB_ODDS_URL = "https://football-betting-odds.p.rapidapi.com"
FB_ODDS_HOST = "football-betting-odds.p.rapidapi.com"

REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 3