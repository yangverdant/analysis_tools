"""
Understat数据源配置

数据源: understat.com (免费, 需解析JS数据)
特色: xG/xA数据 (球员/球队/比赛级别)
覆盖: 英超/西甲/德甲/意甲/法甲/俄超
"""

BASE_URL = "https://understat.com"
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 3

# 联赛代码映射
LEAGUE_CODES = {
    "premier_league": "EPL", "英超": "EPL",
    "la_liga": "La_liga", "西甲": "La_liga",
    "bundesliga": "Bundesliga", "德甲": "Bundesliga",
    "serie_a": "Serie_A", "意甲": "Serie_A",
    "ligue_1": "Ligue_1", "法甲": "Ligue_1",
    "rfpl": "RFPL", "俄超": "RFPL",
}