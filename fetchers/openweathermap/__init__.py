"""
OpenWeatherMap数据获取工具

数据源: api.openweathermap.org (需Key, 免费计划60次/分)
提供: 天气预报/空气质量 (wttr.in的付费替代)
"""

from fetchers.openweathermap.get_weather import get_current_weather, get_forecast, get_air_quality