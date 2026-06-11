"""
OpenWeatherMap数据源配置

数据源: api.openweathermap.org (免费计划: 60次/分钟)
特色: 天气预报/历史天气/空气质量
备用: wttr.in (免费, 无需Key)
"""

API_KEY = None  # 需要填入, 在 https://openweathermap.org/api 注册
BASE_URL = "https://api.openweathermap.org/data/2.5"
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 1