# 分析中心新增模块总结

## 已完成的新增模块

### 1. 天气数据模块 (weather.py)

**功能**:
- OpenWeatherMap API集成
- 城市名称映射（支持足球城市）
- 天气影响系数计算（进球、体能、传球）
- 模拟数据fallback

**API端点**:
- `GET /api/v1/analytics/weather/city/{city}` - 获取城市天气
- `GET /api/v1/analytics/weather/match/{match_id}` - 获取比赛天气
- `POST /api/v1/analytics/weather/batch-update` - 批量更新天气

**文件**: [backend/app/analytics/weather.py](backend/app/analytics/weather.py)

---

### 2. 价值投注模块 (value_bet.py)

**功能**:
- Kelly Criterion投注比例计算
- Edge优势计算（预测概率 - 隐含概率）
- 期望值(EV)计算
- 价值等级评估（high/medium/low）
- 套利机会检测

**API端点**:
- `GET /api/v1/analytics/value-bet/match/{match_id}` - 分析比赛价值投注
- `GET /api/v1/analytics/value-bet/scan` - 扫描未来价值投注
- `POST /api/v1/analytics/value-bet/analyze` - 自定义分析
- `POST /api/v1/analytics/value-bet/arbitrage` - 套利机会
- `GET /api/v1/analytics/value-bet/kelly` - Kelly计算

**文件**: [backend/app/analytics/value_bet.py](backend/app/analytics/value_bet.py)

---

### 3. 裁判分析模块 (referee.py)

**功能**:
- 裁判历史统计（黄牌、红牌、点球）
- 主队/客队执法差异
- 裁判风格分析（严厉/宽松）
- 主场偏向分析
- 对比赛的影响评估

**API端点**:
- `GET /api/v1/analytics/referee/list` - 获取裁判列表
- `GET /api/v1/analytics/referee/{referee_name}` - 获取裁判统计
- `GET /api/v1/analytics/referee/impact/{match_id}` - 分析裁判对比赛的影响

**文件**: [backend/app/analytics/referee.py](backend/app/analytics/referee.py)

---

### 4. 球场/场地分析模块 (venue.py)

**功能**:
- 球场信息获取（名称、容量、海拔）
- 主场优势强度计算
- 客队旅行距离估算（Haversine公式）
- 海拔影响分析
- 球场历史战绩分析

**API端点**:
- `GET /api/v1/analytics/venue/distance` - 计算城市距离
- `GET /api/v1/analytics/venue/impact/{match_id}` - 分析球场影响
- `GET /api/v1/analytics/venue/team/{team_id}/home-performance` - 主场表现

**文件**: [backend/app/analytics/venue.py](backend/app/analytics/venue.py)

---

### 5. 疲劳度分析模块 (fatigue.py)

**功能**:
- 近期出场时间统计
- 休息天数计算
- 7天/14天比赛密度分析
- 疲劳等级评估（low/moderate/high/extreme）
- 两队疲劳度对比

**API端点**:
- `GET /api/v1/analytics/fatigue/team/{team_id}` - 获取球队疲劳度
- `GET /api/v1/analytics/fatigue/compare` - 比较两队疲劳度
- `GET /api/v1/analytics/fatigue/match/{match_id}` - 分析比赛疲劳因素

**文件**: [backend/app/analytics/fatigue.py](backend/app/analytics/fatigue.py)

---

## 前端集成

### MatchPage.vue 新增显示

1. **天气数据**
   - 温度、湿度、风速
   - 天气影响系数（进球、体能、传球）
   - 影响描述

2. **价值投注**
   - 市场赔率
   - 预测概率 vs 隐含概率
   - Edge优势、Kelly比例
   - 价值等级

---

## 核心算法

### Kelly Criterion
```
f = (bp - q) / b
b = 赔率 - 1 (净赔率)
p = 预测概率
q = 1 - p (失败概率)
```

### 海拔影响
- 高海拔(>1500m): 主队优势+8%
- 极高海拔(>2500m): 主队优势+15%

### 疲劳影响
- 休息<3天: -15%
- 休息<5天: -10%
- 7天内>2场: -15%

---

## 使用示例

```python
# 天气分析
from app.analytics.weather import WeatherAnalyzer
weather = WeatherAnalyzer(db_path)
result = weather.get_match_weather(match_id, conn)

# 价值投注
from app.analytics.value_bet import ValueBetAnalyzer
vb = ValueBetAnalyzer(db_path)
bets = vb.find_value_bets(prediction, odds)

# 裁判分析
from app.analytics.referee import RefereeAnalyzer
ref = RefereeAnalyzer(db_path)
impact = ref.analyze_referee_impact(referee_name, home_id, away_id, conn)

# 球场分析
from app.analytics.venue import VenueAnalyzer
venue = VenueAnalyzer(db_path)
advantage = venue.analyze_venue_advantage(home_id, away_id, venue_name, conn)

# 疲劳度分析
from app.analytics.fatigue import FatigueAnalyzer
fatigue = FatigueAnalyzer(db_path)
comparison = fatigue.compare_teams_fatigue(home_id, away_id, match_date, conn)
```

---

## 待实现功能

1. **实时赔率浮动** - 需要Odds Feed API订阅
2. **AI预测增强** - 需要训练ML模型
3. **Pressure Index** - 需要Sportmonks All-In订阅
4. **实时比赛追踪** - 需要WebSocket支持
