"""
API-Football数据源配置

数据源: apiv3.apifootball.com
认证: APIkey (query param)
文档: https://apiv3.apifootball.com/api-docs
免费计划: 10次/分钟
"""

API_KEY = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"
BASE_URL = "https://apiv3.apifootball.com"
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 2

# 联赛ID映射 (league_name -> apifootball league_id)
# ID来源: apiv3.apifootball.com get_leagues 接口实际查询
LEAGUE_IDS = {
    "英超": 152, "premier_league": 152,
    "西甲": 302, "la_liga": 302,
    "德甲": 175, "bundesliga": 175,
    "意甲": 207, "serie_a": 207,
    "法甲": 168, "ligue_1": 168,
    "英冠": 153, "championship": 153,
    "荷甲": 244, "eredivisie": 244,
    "葡超": 266, "primeira_liga": 266,
    "J1联赛": 209, "j1_league": 209,
    "J2联赛": 212, "j2_league": 212,
    "K联赛1": 219, "k1_league": 219,
    "K联赛2": 218, "k2_league": 218,
    "欧冠": 3, "champions_league": 3,
    "欧联": 4, "europa_league": 4,
    "天皇杯": 360, "emperor_cup": 360,
    "J联赛杯": 210, "j_league_cup": 210,
    "韩国足协杯": 419, "korean_fa_cup": 419,
    "挪超": 253, "eliteserien": 253,
    "瑞超": 307, "allsvenskan": 307,
    "欧协联": 683, "conference_league": 683,
    "解放者杯": 18, "copa_libertadores": 18,
    "世界杯": 28, "world_cup": 28,
    "世界杯预选赛(欧洲)": 24, "uefa_wc_qualifiers": 24,
    "世界杯预选赛(南美)": 27, "conmebol_wc_qualifiers": 27,
    "世界杯预选赛(亚洲)": 22, "afc_wc_qualifiers": 22,
    "联合会杯": 16, "confederations_cup": 16,
}

# 比赛状态映射
MATCH_STATUS_MAP = {
    "Finished": "finished",
    "Half Time": "halftime",
    "Postponed": "postponed",
    "Cancelled": "cancelled",
    "After ET": "finished_aet",
    "After Pen.": "finished_pen",
}

# API actions
API_ACTIONS = {
    "get_events": "比赛事件/赛程/实时比分",
    "get_odds": "赔率数据",
    "get_standings": "积分榜",
    "get_teams": "球队信息",
    "get_players": "球员信息",
    "get_topscorers": "射手榜",
    "get_predictions": "比赛预测",
    "get_statistics": "比赛统计",
    "get_leagues": "联赛列表",
    "get_countries": "国家列表",
    "get_lineups": "阵容",
    "get_h2h": "交锋记录",
}