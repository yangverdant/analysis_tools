"""
英超官方数据源配置

数据源: premierleague.com (免费, 爬虫)
特色: 官方伤病名单/赛果/赛程
覆盖: 仅英超
"""

BASE_URL = "https://www.premierleague.com"
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 5

PLAYER_STATUS_MAP = {
    "a": "available",      # 可出场
    "u": "unavailable",    # 不可出场
    "d": "doubtful",       # 出场成疑
    "i": "injured",        # 受伤
    "s": "suspended",      # 停赛
    "n": "not_in_squad",   # 未入选
}