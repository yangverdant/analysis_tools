"""
football-data.org API配置

数据源: api.football-data.org/v4 (免费REST API)
认证: X-Auth-Token header
免费计划: 10次/分钟
覆盖: 12个T1联赛 (英超/西甲/德甲/意甲/法甲/荷甲/葡超/英冠/欧冠/世界杯/欧洲杯/巴甲)
"""

API_TOKEN = "944e431594bf477fa85d24fa04d9c2fe"
BASE_URL = "https://api.football-data.org/v4"
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 7  # 免费计划10次/分钟, 间隔7秒安全

# 联赛代码映射 (league_name -> competition code)
COMPETITION_CODES = {
    "premier_league": "PL", "英超": "PL",
    "la_liga": "PD", "西甲": "PD",
    "bundesliga": "BL1", "德甲": "BL1",
    "serie_a": "SA", "意甲": "SA",
    "ligue_1": "FL1", "法甲": "FL1",
    "eredivisie": "DED", "荷甲": "DED",
    "primeira_liga": "PPL", "葡超": "PPL",
    "championship": "ELC", "英冠": "ELC",
    "champions_league": "CL", "欧冠": "CL",
    "world_cup": "WC", "世界杯": "WC",
    "euro": "EC", "欧洲杯": "EC",
    "brasileirao": "BSA", "巴甲": "BSA",
}

# 比赛状态映射
STATUS_MAP = {
    "SCHEDULED": "scheduled", "TIMED": "timed",
    "IN_PLAY": "live", "PAUSED": "halftime",
    "FINISHED": "finished", "POSTPONED": "postponed",
    "CANCELLED": "cancelled", "SUSPENDED": "suspended",
}