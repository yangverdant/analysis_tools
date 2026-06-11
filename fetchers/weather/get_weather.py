"""
比赛天气数据获取

功能:
1. 获取比赛城市天气 (温度/湿度/风力/降雨)
2. 评估天气对比赛的影响

数据来源: wttr.in (免费, 无需认证)

使用示例:
    from fetchers.weather.get_weather import get_match_weather

    # 获取伦敦天气
    w = get_match_weather("London")
    print(f"  {w['temp']}°C, {w['humidity']}%, {w['description']}")

    # 评估影响
    from fetchers.weather.get_weather import assess_weather_impact
    impact = assess_weather_impact(w)
    print(f"  影响: {impact['level']} - {impact['reason']}")
"""

import json
import os
import logging
from typing import Dict, Optional

import requests

from fetchers.weather.config import WTTR_IN_URL, REQUEST_TIMEOUT

os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'

logger = logging.getLogger(__name__)

# 城市名映射 (中文 -> 英文, wttr.in需要英文)
CITY_NAME_MAP = {
    "伦敦": "London",
    "曼彻斯特": "Manchester",
    "利物浦": "Liverpool",
    "马德里": "Madrid",
    "巴塞罗那": "Barcelona",
    "慕尼黑": "Munich",
    "多特蒙德": "Dortmund",
    "米兰": "Milan",
    "罗马": "Rome",
    "都灵": "Turin",
    "巴黎": "Paris",
    "里昂": "Lyon",
    "阿姆斯特丹": "Amsterdam",
    "里斯本": "Lisbon",
    "伊斯坦布尔": "Istanbul",
    "格拉斯哥": "Glasgow",
    "雅典": "Athens",
    "东京": "Tokyo",
    "首尔": "Seoul",
    "纽约": "New+York",
    "洛杉矶": "Los+Angeles",
}


def _create_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'curl/7.64.1',
        'Accept': 'application/json',
    })
    return session


# ==================== 核心接口 ====================

def get_match_weather(city: str, date: str = None, home_team: str = None) -> Optional[Dict]:
    """获取比赛城市天气

    Args:
        city: 城市名 (中文或英文)
        date: 比赛日期 (任何格式，用于串联)
        home_team: 主队名 (任何语言/格式，用于串联)

    Returns:
        {
            "city": "London",
            "city_input": "伦敦",
            "date": "2026-05-25",
            "home_team": "Arsenal",
            "temp_c": 18,
            "feels_like_c": 16,
            "humidity": 65,
            "wind_speed_kmh": 15,
            "wind_dir": "SW",
            "precipitation_mm": 0.0,
            "visibility_km": 10,
            "description": "Partly cloudy",
            "source": "wttr.in"
        }
    """
    city_en = CITY_NAME_MAP.get(city, city)
    from fetchers.common.date_utils import normalize_date
    from fetchers.common.team_names import normalize_team_name
    standard_date = normalize_date(date) if date else None
    standard_home = normalize_team_name(home_team) if home_team else None

    session = _create_session()

    try:
        url = f"{WTTR_IN_URL}/{city_en}?format=j1"
        response = session.get(url, timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})

        if response.status_code == 200:
            data = response.json()
            current = data.get('current_condition', [{}])[0]

            result = {
                'city': city_en,
                'city_input': city,
                'date': standard_date,
                'home_team': standard_home,
                'temp_c': int(current.get('temp_C', 0)),
                'feels_like_c': int(current.get('FeelsLikeC', 0)),
                'humidity': int(current.get('humidity', 0)),
                'wind_speed_kmh': int(current.get('windspeedKmph', 0)),
                'wind_dir': current.get('winddir16Point', ''),
                'precipitation_mm': float(current.get('precipMM', 0)),
                'visibility_km': int(current.get('visibility', 0)),
                'description': current.get('weatherDesc', [{}])[0].get('value', ''),
                'source': 'wttr.in'
            }

            print(f"[weather] {city}: {result['temp_c']}°C, {result['humidity']}%, {result['description']}")
            return result

    except Exception as e:
        logger.error(f"获取天气失败: {e}")
        print(f"[错误] 天气获取失败: {str(e)[:60]}")

    return None


def assess_weather_impact(weather: Dict) -> Dict:
    """评估天气对比赛的影响

    Returns:
        {
            "level": "low" / "medium" / "high",
            "reason": "原因说明",
            "factors": ["强风", "暴雨"]
        }
    """
    if not weather:
        return {'level': 'unknown', 'reason': '无天气数据', 'factors': []}

    factors = []
    reasons = []

    # 降雨
    precip = weather.get('precipitation_mm', 0)
    if precip > 10:
        factors.append('暴雨')
        reasons.append('暴雨影响传球和射门精度')
    elif precip > 3:
        factors.append('中雨')
        reasons.append('降雨影响场地条件')

    # 风力
    wind = weather.get('wind_speed_kmh', 0)
    if wind > 40:
        factors.append('强风')
        reasons.append('强风严重影响长传和定位球')
    elif wind > 25:
        factors.append('大风')
        reasons.append('大风影响传中球轨迹')

    # 温度
    temp = weather.get('temp_c', 20)
    if temp > 35:
        factors.append('高温')
        reasons.append('高温影响球员体能')
    elif temp < -5:
        factors.append('严寒')
        reasons.append('低温影响球员肌肉状态')

    # 湿度
    humidity = weather.get('humidity', 50)
    if humidity > 90 and temp > 25:
        factors.append('闷热')
        reasons.append('高湿+高温导致体能消耗加快')

    # 能见度
    visibility = weather.get('visibility_km', 10)
    if visibility < 2:
        factors.append('低能见度')
        reasons.append('低能见度可能影响比赛')

    # 评估等级
    if len(factors) >= 2:
        level = 'high'
    elif len(factors) == 1:
        level = 'medium'
    else:
        level = 'low'

    return {
        'level': level,
        'reason': '; '.join(reasons) if reasons else '天气条件正常',
        'factors': factors
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.weather.get_weather London")
        print("  python -m fetchers.weather.get_weather 伦敦")
        sys.exit(0)

    city = sys.argv[1]
    w = get_match_weather(city)
    if w:
        print(f"  温度: {w['temp_c']}°C (体感{w['feels_like_c']}°C)")
        print(f"  湿度: {w['humidity']}%")
        print(f"  风力: {w['wind_speed_kmh']}km/h {w['wind_dir']}")
        print(f"  降雨: {w['precipitation_mm']}mm")
        print(f"  能见度: {w['visibility_km']}km")
        print(f"  天气: {w['description']}")

        impact = assess_weather_impact(w)
        print(f"\n  影响评估: {impact['level']} - {impact['reason']}")