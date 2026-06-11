# 天气数据模块使用说明

## 功能概述

天气模块可以根据比赛地点和时间获取天气数据，并分析天气对比赛的影响。

---

## API端点

### 1. 获取城市天气
```
GET /api/v1/analytics/weather/city/{city}
```

**示例**:
```bash
curl "http://127.0.0.1:18888/api/v1/analytics/weather/city/London"
```

**返回**:
```json
{
  "city": "London",
  "weather": {
    "temperature": 18.1,
    "humidity": 71,
    "wind_speed": 6.0,
    "weather_description": "light rain",
    "is_raining": true
  },
  "impact": {
    "goal_factor": 0.9,
    "stamina_factor": 1.0,
    "overall_factor": 0.93,
    "description": ["小雨: 进球率下降10%"]
  }
}
```

### 2. 获取比赛天气
```
GET /api/v1/analytics/weather/match/{match_id}
```

**示例**:
```bash
curl "http://127.0.0.1:18888/api/v1/analytics/weather/match/premier_league_2025-2026_2026-05-24_sunderland_vs_chelsea"
```

### 3. 批量更新天气
```
POST /api/v1/analytics/weather/batch-update?days=7
```

---

## 天气影响系数

| 天气条件 | 进球影响 | 体力影响 | 传球影响 |
|----------|----------|----------|----------|
| 晴天/多云 | 1.0 | 1.0 | 1.0 |
| 小雨 | 0.9 | 1.0 | 0.9 |
| 中雨 | 0.8 | 0.95 | 0.85 |
| 大雨 | 0.7 | 0.9 | 0.75 |
| 高温(>30°C) | 0.9 | 0.85 | 1.0 |
| 低温(<5°C) | 0.95 | 0.95 | 1.0 |
| 大风(>25m/s) | 0.85 | 1.0 | 0.85 |
| 高湿度(>85%) | 1.0 | 0.9 | 1.0 |

---

## 数据源

### OpenWeatherMap (推荐)

**免费额度**: 1000次/天

**注册**: https://openweathermap.org/api

**使用**:
```python
from weather import WeatherAnalyzer

# 设置API Key
analyzer = WeatherAnalyzer(db_path, api_key="YOUR_API_KEY")
```

### 模拟数据

当没有API Key时，模块会根据城市和月份生成合理的模拟天气数据。

---

## Python使用示例

```python
from weather import WeatherAnalyzer

db_path = "d:\\football_tools\\data\\football_v2.db"
analyzer = WeatherAnalyzer(db_path)

# 获取城市天气
weather = analyzer.get_weather_openweathermap("London")
print(f"温度: {weather['temperature']}°C")

# 获取比赛天气
match_weather = analyzer.get_match_weather(match_id)
print(f"天气: {match_weather['weather']['weather_description']}")

# 计算天气影响
impact = analyzer.calculate_weather_impact(weather)
print(f"综合影响: {impact['overall_factor']}")

# 批量更新
updated = analyzer.batch_update_weather(days=7)
print(f"更新了 {updated} 场比赛")
```

---

## 前端集成

在比赛分析页面显示天气:

```vue
<template>
  <section class="section-block" v-if="weather">
    <div class="section-title"><CloudIcon /><span>比赛天气</span></div>
    <div class="weather-info">
      <div class="weather-main">
        <span class="temp">{{ weather.temperature }}°C</span>
        <span class="desc">{{ weather.weather_description }}</span>
      </div>
      <div class="weather-details">
        <span>湿度: {{ weather.humidity }}%</span>
        <span>风速: {{ weather.wind_speed }}m/s</span>
      </div>
      <div class="weather-impact" v-if="impact">
        <span class="impact-label">天气影响:</span>
        <span class="impact-factor">{{ (impact.overall_factor * 100).toFixed(0) }}%</span>
      </div>
    </div>
  </section>
</template>
```

---

## 注意事项

1. **API限制**: OpenWeatherMap免费版1000次/天，建议使用缓存
2. **预测天气**: 未来天气最多预测5天
3. **城市映射**: 模块内置了常见足球城市的名称映射
4. **代理问题**: 国内访问需禁用代理，模块已自动处理

---

## 文件位置

- 天气模块: [backend/app/analytics/weather.py](backend/app/analytics/weather.py)
- API路由: [backend/app/analytics/routes.py](backend/app/analytics/routes.py)