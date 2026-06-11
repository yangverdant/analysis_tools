"""
OpenWeatherMap数据获取

功能:
1. 获取当前天气 (温度/湿度/风力/天气状况)
2. 获取5天/3小时预报
3. 获取空气质量指数 (AQI)

数据来源: api.openweathermap.org (需API Key, 免费计划60次/分)

注意: 如无需Key的天气数据, 建议使用 fetchers.weather (wttr.in)

使用示例:
    from fetchers.openweathermap.get_weather import get_current_weather

    w = get_current_weather("London")
"""

import os
import logging
from typing import Dict, Optional
import requests

from fetchers.openweathermap.config import API_KEY, BASE_URL, REQUEST_TIMEOUT

os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'

logger = logging.getLogger(__name__)

_session = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.trust_env = False
    return _session


def _request(endpoint: str, params: Dict) -> Optional[Dict]:
    if not API_KEY:
        print("[错误] OpenWeatherMap API Key未配置, 请在config.py中设置")
        print("       或使用 fetchers.weather (wttr.in, 免费无需Key)")
        return None

    params["appid"] = API_KEY
    params["units"] = "metric"

    session = _get_session()
    try:
        resp = session.get(f"{BASE_URL}/{endpoint}", params=params,
                           timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"OpenWeatherMap请求失败: {e}")
        print(f"[错误] OpenWeatherMap请求失败: {str(e)[:60]}")
    return None


# ==================== 核心接口 ====================

def get_current_weather(city: str) -> Dict:
    """获取当前天气

    Args:
        city: 城市名 (英文, 如 "London", "Manchester")

    Returns:
        {"city", "temp_c", "feels_like_c", "humidity", "pressure",
         "wind_speed_ms", "wind_deg", "clouds", "visibility_m",
         "description", "icon", "source"}
    """
    data = _request("weather", {"q": city})
    if not data:
        return {}

    weather = data.get("weather", [{}])[0]
    main = data.get("main", {})
    wind = data.get("wind", {})

    result = {
        'city': data.get("name", city),
        'city_input': city,
        'country': data.get("sys", {}).get("country", ""),
        'temp_c': main.get("temp"),
        'feels_like_c': main.get("feels_like"),
        'temp_min_c': main.get("temp_min"),
        'temp_max_c': main.get("temp_max"),
        'humidity': main.get("humidity"),
        'pressure': main.get("pressure"),
        'wind_speed_ms': wind.get("speed"),
        'wind_deg': wind.get("deg"),
        'wind_gust_ms': wind.get("gust"),
        'clouds': data.get("clouds", {}).get("all"),
        'visibility_m': data.get("visibility"),
        'description': weather.get("description", ""),
        'icon': weather.get("icon", ""),
        'source': 'openweathermap'
    }

    print(f"[openweathermap] {city}: {result['temp_c']}°C, {result['description']}")
    return result


def get_forecast(city: str, cnt: int = 40) -> list:
    """获取5天/3小时预报

    Args:
        city: 城市名
        cnt: 返回数据点数 (最多40, 即5天x8次/天)

    Returns:
        预报列表
    """
    data = _request("forecast", {"q": city, "cnt": cnt})
    if not data:
        return []

    forecasts = []
    for item in data.get("list", []):
        main = item.get("main", {})
        weather = item.get("weather", [{}])[0]
        wind = item.get("wind", {})

        forecasts.append({
            'city': city,
            'city_input': city,
            'datetime': item.get("dt_txt", ""),
            'temp_c': main.get("temp"),
            'feels_like_c': main.get("feels_like"),
            'humidity': main.get("humidity"),
            'wind_speed_ms': wind.get("speed"),
            'description': weather.get("description", ""),
            'pop': item.get("pop"),  # 降水概率
            'rain_3h': item.get("rain", {}).get("3h", 0) if item.get("rain") else 0,
        })

    print(f"[openweathermap] {city} 预报: {len(forecasts)}条")
    return forecasts


def get_air_quality(lat: float, lon: float) -> Dict:
    """获取空气质量指数

    Args:
        lat: 纬度
        lon: 经度

    Returns:
        {"aqi", "co", "no2", "o3", "pm2_5", "pm10", "source"}
    """
    params = {"lat": lat, "lon": lon}
    if not API_KEY:
        return {}

    params["appid"] = API_KEY
    session = _get_session()

    try:
        resp = session.get(f"{BASE_URL}/air_pollution", params=params,
                           timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            data = resp.json()
            item = data.get("list", [{}])[0]
            aqi_data = item.get("main", {})
            components = item.get("components", {})

            return {
                'lat': lat,
                'lon': lon,
                'aqi': aqi_data.get("aqi"),
                'co': components.get("co"),
                'no2': components.get("no2"),
                'o3': components.get("o3"),
                'pm2_5': components.get("pm2_5"),
                'pm10': components.get("pm10"),
                'so2': components.get("so2"),
                'source': 'openweathermap'
            }
    except Exception as e:
        logger.error(f"空气质量请求失败: {e}")

    return {}


if __name__ == "__main__":
    import sys
    city = sys.argv[1] if len(sys.argv) > 1 else "London"
    w = get_current_weather(city)
    if w:
        print(f"  {w['temp_c']}°C (体感{w['feels_like_c']}°C), {w['description']}")
        print(f"  湿度: {w['humidity']}%, 风速: {w['wind_speed_ms']}m/s")