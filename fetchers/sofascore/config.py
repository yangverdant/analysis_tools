"""
Sofascore 实时数据配置

数据源: api.sofascore.com
无需认证, 但有反爬措施

备用源: football-data.org (需要API Token)
"""

# ==================== 主源: Sofascore ====================
SOFASCORE_API_URL = "https://api.sofascore.com/api/v1"

# ==================== 备用源: football-data.org ====================
FOOTBALL_DATA_API_URL = "https://api.football-data.org/v4"
FOOTBALL_DATA_API_KEY = "944e431594bf477fa85d24fa04d9c2fe"

# ==================== 请求配置 ====================
REQUEST_TIMEOUT = 15
CACHE_DURATION = 60  # 秒, 实时数据缓存1分钟