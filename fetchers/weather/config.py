"""
天气数据配置

数据源: wttr.in (免费, 无需API Key)
备用: OpenWeatherMap (需要API Key)
"""

WTTR_IN_URL = "https://wttr.in"
OPENWEATHERMAP_URL = "https://api.openweathermap.org/data/2.5"
OPENWEATHERMAP_API_KEY = None  # 需要填入

REQUEST_TIMEOUT = 15