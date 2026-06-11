"""
体彩官网 (sporttery.cn) 数据获取配置

数据源: webapi.sporttery.cn
无需认证, 公开API
"""

BASE_URL = "https://webapi.sporttery.cn"

# API端点
URL_MATCH_LIST = BASE_URL + "/gateway/jc/football/getMatchCalculatorV1.qry"
URL_MATCH_RESULT = BASE_URL + "/gateway/jc/football/getMatchResultV1.qry"
URL_ODDS = BASE_URL + "/gateway/jc/football/getOddsV1.qry"

# 请求配置
REQUEST_TIMEOUT = 30

# 玩法类型
PLAY_TYPES = {
    "spf": "胜平负",
    "rqspf": "让球胜平负",
    "bf": "比分",
    "bqc": "半全场",
    "jqs": "进球数",
}