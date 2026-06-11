"""
Okooo (澳客网) 爬虫配置

使用前必须填入有效的Cookie，否则会被WAF拦截。
Cookie获取方式: 浏览器登录okooo.com -> F12开发者工具 -> Network -> 复制Cookie请求头
"""

# ==================== 认证配置 ====================
# [必须] 填入你的浏览器Cookie
COOKIE = "LastUrl=; _ga=GA1.1.401386.1778232853; FirstURL=www.okooo.com/soccer/match/1307740/formation/; FirstOKURL=https%3A//www.okooo.com/soccer/match/1307740/history/; First_Source=www.okooo.com; historyShowThisMatch=1; Hm_lvt_213d524a1d07274f17dfa17b79db318f=1778232853,1778656686,1779029275; HMACCOUNT=1F3EF521C8A0AE95; PHPSESSID=9e2f1e217ccb1233deae8c43732436beb6b9de5d; pm=; Hm_lpvt_213d524a1d07274f17dfa17b79db318f=1779436699; _ga_B3LCXP8H9E=GS2.1.s1779436698$o8$g0$t1779436701$j57$l0$h985629783; acw_tc=76b20f7117797096967237538e21751c0283458ca4f049cb0df4e12d2950b8; IMUserID=33011182; IMUserName=%E5%BF%85%E8%B5%A2king; OkAutoUuid=52d52aec56a2332cc6db4057cb03c26f; OkMsIndex=2; OKSID=9e2f1e217ccb1233deae8c43732436beb6b9de5d; M_UserName=%22ok_212261533570%22; M_UserID=33011182; M_Ukey=2c895ad05383e086a955e7243e8b266c; OkTouchAutoUuid=52d52aec56a2332cc6db4057cb03c26f; OkTouchMsIndex=2; DRUPAL_LOGGED_IN=Y; isInvitePurview=0"

# ==================== 请求配置 ====================
# 请求间隔(秒)，防止触发反爬
REQUEST_INTERVAL_MIN = 2.5
REQUEST_INTERVAL_MAX = 4.0
# 公司间休眠
COMPANY_INTERVAL_MIN = 1.5
COMPANY_INTERVAL_MAX = 3.0
# 比赛间休眠
MATCH_INTERVAL_MIN = 14.0
MATCH_INTERVAL_MAX = 16.0
# 最大重试次数
MAX_RETRIES = 5

# ==================== 博彩公司ID映射 ====================
COMPANIES = {
    "WH":     14,    # 威廉希尔 William Hill
    "B365":   27,    # Bet365
    "IW":     43,    # Interwetten
    "1XBET":  744,   # 1xBet
    "BF":     19,    # Betfair
    "SBO":    280,   # SBOBET
    "188BET": 322,   # 188BET
    "SABA":   220,   # 沙巴 SABA Sports
    "PIN":    50,    # 平博 Pinnacle
}

# ==================== 联赛ID映射 ====================
# key: 通用联赛缩写
# value: dict with okooo league_id, season_id (当前赛季), total_teams
#
# ⚠️ league_id和season_id需要到okooo.com确认
#    确认方式: 浏览器打开 https://www.okooo.com/soccer/league/{league_id}/schedule/
#    看URL和页面是否对应正确联赛
#    season_id在赛程页URL中: /soccer/league/{league_id}/schedule/{season_id}/
#
# 已确认:
#   - 英超: league_id=8, 来自参考爬虫代码
#   - 其他联赛ID参考okooo网站, 待二次确认

LEAGUES = {
    # 五大联赛
    "英超": {
        "league_id": 8,
        "season_id": 110140,    # 2024-25赛季, 需每个赛季更新
        "total_teams": 20,
        "rounds": 38,
        "name_en": "Premier League",
    },
    "西甲": {
        "league_id": 17,
        "season_id": None,      # 待确认
        "total_teams": 20,
        "rounds": 38,
        "name_en": "La Liga",
    },
    "德甲": {
        "league_id": 9,
        "season_id": None,      # 待确认
        "total_teams": 18,
        "rounds": 34,
        "name_en": "Bundesliga",
    },
    "意甲": {
        "league_id": 35,
        "season_id": None,      # 待确认
        "total_teams": 20,
        "rounds": 38,
        "name_en": "Serie A",
    },
    "法甲": {
        "league_id": 11,
        "season_id": None,      # 待确认
        "total_teams": 18,
        "rounds": 34,
        "name_en": "Ligue 1",
    },
    # 其他联赛
    "挪超": {
        "league_id": 20,
        "season_id": 110575,  # 2026赛季
        "total_teams": 16,
        "rounds": 30,
        "name_en": "Eliteserien",
    },
    "瑞超": {
        "league_id": 40,
        "season_id": 110582,  # 2026赛季
        "total_teams": 16,
        "rounds": 30,
        "name_en": "Allsvenskan",
    },
    "日职": {
        "league_id": 151,
        "season_id": None,
        "total_teams": 20,
        "rounds": 38,
        "name_en": "J1 League",
    },
    "K联赛": {
        "league_id": 55,
        "season_id": None,
        "total_teams": 12,
        "rounds": 38,
        "name_en": "K League 1",
    },
    "美职联": {
        "league_id": 161,
        "season_id": None,
        "total_teams": 30,
        "rounds": 34,
        "name_en": "MLS",
    },
    "英冠": {
        "league_id": 23,
        "season_id": None,
        "total_teams": 24,
        "rounds": 46,
        "name_en": "Championship",
    },
    "葡超": {
        "league_id": 82,
        "season_id": None,
        "total_teams": 18,
        "rounds": 34,
        "name_en": "Primeira Liga",
    },
    "荷甲": {
        "league_id": 16,
        "season_id": None,
        "total_teams": 18,
        "rounds": 34,
        "name_en": "Eredivisie",
    },
    # 杯赛
    "欧冠": {
        "league_id": 5,
        "season_id": None,
        "total_teams": None,
        "rounds": None,
        "name_en": "Champions League",
    },
    "亚冠": {
        "league_id": 66,
        "season_id": None,
        "total_teams": None,
        "rounds": None,
        "name_en": "AFC Champions League",
    },
}

# ==================== 盘口变化时间节点 ====================
TARGET_HOURS = [48, 36, 24, 12, 6, 3, 2, 1, 0.5, 0.25, 0.1]
TIME_LABELS = ["opening", "48h", "36h", "24h", "12h", "6h", "3h", "2h", "1h", "0.5h", "0.25h", "0.1h", "closing"]

# ==================== URL模板 ====================
BASE_URL = "https://www.okooo.com"

# 比赛列表(按日期)
URL_MATCH_LIST = BASE_URL + "/soccer/match/{date}/"

# 联赛赛程
URL_LEAGUE_SCHEDULE = BASE_URL + "/soccer/league/{league_id}/schedule/{season_id}/{round_start}-{round_end}-{round_num}/"

# 比赛基本面+欧赔
URL_MATCH_ODDS = BASE_URL + "/soccer/match/{match_id}/odds/"

# 欧赔变化(某公司)
URL_ODDS_CHANGE = BASE_URL + "/soccer/match/{match_id}/odds/change/{company_id}/"

# 亚盘变化(某公司)
URL_AH_CHANGE = BASE_URL + "/soccer/match/{match_id}/ah/change/{company_id}/"

# 大小球变化(某公司)
URL_OU_CHANGE = BASE_URL + "/soccer/match/{match_id}/overunder/change/{company_id}/"

# 亚盘即时
URL_AH = BASE_URL + "/soccer/match/{match_id}/ah/"

# 大小球即时
URL_OU = BASE_URL + "/soccer/match/{match_id}/ou/"
