# 分析中心完整模块清单

## 一、核心预测算法 (原有)

| 算法 | 文件 | 状态 | 说明 |
|------|------|------|------|
| Elo评分 | elo.py | ✅ | 计算球队实力评分，预测胜率 |
| Poisson分布 | poisson.py | ✅ | 预测比分概率、大小球、双方进球 |
| xG分析 | xg.py | ✅ | 预期进球分析 |
| 历史交锋 | h2h.py | ✅ | 交锋记录、心理优势分析 |
| 近期状态 | form.py | ✅ | 近5-10场状态评分 |
| 主客场优势 | home_away.py | ✅ | 主客场表现差异分析 |
| 动机分析 | motivation.py | ✅ | 保级/争冠/无欲无求分析 |
| 利好利空 | news_factors.py | ✅ | 球队动态影响分析 |
| 综合预测 | comprehensive.py | ✅ | 整合所有维度加权预测 |

---

## 二、新增分析模块

### 1. 天气数据模块 (weather.py) ✅

**功能**:
- OpenWeatherMap API集成
- 城市名称映射
- 天气影响系数计算

**API端点**:
- `GET /api/v1/analytics/weather/city/{city}`
- `GET /api/v1/analytics/weather/match/{match_id}`
- `POST /api/v1/analytics/weather/batch-update`

---

### 2. 价值投注模块 (value_bet.py) ✅

**功能**:
- Kelly Criterion投注比例
- Edge优势计算
- 套利机会检测

**API端点**:
- `GET /api/v1/analytics/value-bet/match/{match_id}`
- `GET /api/v1/analytics/value-bet/scan`
- `POST /api/v1/analytics/value-bet/analyze`
- `POST /api/v1/analytics/value-bet/arbitrage`
- `GET /api/v1/analytics/value-bet/kelly`

---

### 3. 裁判分析模块 (referee.py) ✅

**功能**:
- 裁判历史统计
- 执法风格分析
- 主场偏向分析

**API端点**:
- `GET /api/v1/analytics/referee/list`
- `GET /api/v1/analytics/referee/{referee_name}`
- `GET /api/v1/analytics/referee/impact/{match_id}`

---

### 4. 球场分析模块 (venue.py) ✅

**功能**:
- 球场信息获取
- 旅行距离计算
- 海拔影响分析

**API端点**:
- `GET /api/v1/analytics/venue/distance`
- `GET /api/v1/analytics/venue/impact/{match_id}`
- `GET /api/v1/analytics/venue/team/{team_id}/home-performance`

---

### 5. 疲劳度分析模块 (fatigue.py) ✅

**功能**:
- 休息天数计算
- 比赛密度分析
- 疲劳等级评估

**API端点**:
- `GET /api/v1/analytics/fatigue/team/{team_id}`
- `GET /api/v1/analytics/fatigue/compare`
- `GET /api/v1/analytics/fatigue/match/{match_id}`

---

### 6. 连锁反应分析模块 (league_impact.py) ✅

**功能**:
- 积分榜模拟
- 降级形势分析
- 争冠/欧战资格影响

**API端点**:
- `GET /api/v1/analytics/league-impact/standings/{league_id}/{season_id}`
- `GET /api/v1/analytics/league-impact/match/{match_id}`
- `GET /api/v1/analytics/league-impact/team/{team_id}/relegation`
- `GET /api/v1/analytics/league-impact/team/{team_id}/title`

---

### 7. AI预测增强模块 (ml_predictor.py) ✅

**功能**:
- 特征工程
- 加权评分模型
- 多模型融合

**API端点**:
- `GET /api/v1/analytics/ml/predict`
- `GET /api/v1/analytics/ml/features`
- `POST /api/v1/analytics/ml/blend`

---

## 三、API端点统计

| 模块 | 端点数 | 状态 |
|------|--------|------|
| 天气数据 | 3 | ✅ |
| 价值投注 | 5 | ✅ |
| 裁判分析 | 3 | ✅ |
| 球场分析 | 3 | ✅ |
| 疲劳度 | 3 | ✅ |
| 连锁反应 | 4 | ✅ |
| AI预测 | 3 | ✅ |
| **总计** | **24** | ✅ |

---

## 四、待实现功能

| 功能 | 优先级 | 难度 | 依赖 |
|------|--------|------|------|
| 实时赔率浮动 | P1 | 中 | Odds Feed API订阅 |
| Pressure Index | P3 | 低 | Sportmonks All-In |
| 实时比赛追踪 | P3 | 高 | WebSocket |

---

## 五、使用示例

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

# 连锁反应分析
from app.analytics.league_impact import LeagueImpactAnalyzer
impact = LeagueImpactAnalyzer(db_path)
result = impact.analyze_match_impact(match_id, conn)

# AI预测
from app.analytics.ml_predictor import MLPredictor
ml = MLPredictor(db_path)
prediction = ml.predict_match(home_id, away_id, match_date, conn)
```

---

## 六、文件位置

所有分析模块位于: `backend/app/analytics/`

- weather.py - 天气数据
- value_bet.py - 价值投注
- referee.py - 裁判分析
- venue.py - 球场分析
- fatigue.py - 疲劳度
- league_impact.py - 连锁反应
- ml_predictor.py - AI预测

API路由: `backend/app/analytics/routes.py`
