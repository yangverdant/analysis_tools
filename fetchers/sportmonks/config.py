"""
Sportmonks API配置

数据源: api.sportmonks.com/v3 (需API Key)
特色: xG数据/阵容/预测/赔率/实时比分
覆盖: 全球100+联赛
"""

API_KEY = ""  # 需要填入
BASE_URL = "https://api.sportmonks.com/v3/football"
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 3

# 联赛ID映射 (league_name -> sportmonks league_id)
LEAGUE_IDS = {
    "premier_league": 8, "英超": 8,
    "la_liga": 7, "西甲": 7,
    "bundesliga": 5, "德甲": 5,
    "serie_a": 9, "意甲": 9,
    "ligue_1": 6, "法甲": 6,
    "eredivisie": 10, "荷甲": 10,
    "primeira_liga": 11, "葡超": 11,
    "championship": 12, "英冠": 12,
    "j1_league": 13, "J联赛": 13,
    "k1_league": 14, "K联赛": 14,
    "champions_league": 2, "欧冠": 2,
    "europa_league": 3, "欧联": 3,
}

# 包含参数 (Sportmonks特有, 用include参数请求关联数据)
INCLUDES = {
    "fixtures": "scores,participants,periods",
    "standings": "participants.details",
    "lineups": "players",
    "predictions": "predictions",
}