# API 测试记录

**测试日期**: 2026-05-21
**RapidAPI Key**: `232de9f410msh8da4a38f557b694p1d2d4fjsn978df1ba1263`

---

## 已测试API汇总

### ✅ 可用API

| API名称 | 状态 | 数据类型 | 备注 |
|---------|------|----------|------|
| **Odds Feed** | ✅ 可用 | 赔率数据 | 返回比赛赔率、亚盘等 |
| **Bet365** | ✅ 可用 | 赔率数据 | Bet365专项赔率 |
| **Football Betting Odds** | ✅ 可用 | 赔率数据 | 综合赔率数据 |
| **apifootball** | ✅ 可用 | 比赛数据、进球时间 | `goalscorer.time` 字段提供进球时间 |
| **sportmonks** | ⚠️ 有限 | 比赛数据 | 免费版仅4个联赛(丹麦/苏格兰) |
| **football-data.org** | ⚠️ 有限 | 比赛数据 | 免费版限制请求频率 |
| **thesportsdb** | ✅ 可用 | 基础数据 | 开放API，历史数据 |
| **scorebat** | ✅ 可用 | 视频集锦 | 比赛视频链接 |
| **365scores** | ⚠️ 有限 | 比赛数据 | 需订阅 |

### ❌ 不可用API

| API名称 | 状态 | 错误信息 | 备注 |
|---------|------|----------|------|
| **Football xG Statistics** | ⚠️ 有限 | 仅返回England国家列表 | 数据覆盖范围极小，只有 `/countries/` 端点 |
| **LiveScore Sports** | ❌ 错误 | "General client error" | 无法正常访问 |
| **FlashLive Sports** | ⚠️ 非足球 | 返回篮球数据 | 端点示例是篮球，非足球 |

---

## 详细测试结果

### 1. Football xG Statistics API

**端点**: `https://football-xg-statistics.p.rapidapi.com`

**测试结果**:
- `/countries/` ✅ 返回 `[{"id":291,"name":"England"}]`
- `/leagues/` ❌ 不存在
- `/teams/` ❌ 不存在
- `/seasons/` ❌ 不存在
- `/matches/` ⏳ 超时未返回
- `/countries/291` ❌ 不存在
- `/countries/291/leagues` ❌ 不存在

**结论**: 该API数据覆盖极有限，目前只支持英格兰，且无法获取具体xG数据。**不推荐使用**。

---

### 2. FlashLive Sports API

**端点**: `https://flashlive-sports.p.rapidapi.com`

**测试结果**:
- `/v1/events/player-statistics-alt?locale=en_INT&event_id=fXx7UFrK` ✅ 返回数据
- 返回的是篮球(NBA)球员统计数据，非足球数据

**结论**: 该API支持多体育项目，但示例端点是篮球。需要查找足球相关event_id才能测试足球数据。

---

### 3. LiveScore Sports API

**端点**: `https://livescore-sports.p.rapidapi.com`

**测试结果**:
- `/v1/media/details?locale=EN&media_id=4&timezone=0` ❌ 返回 "General client error, try again"

**结论**: API不可用。

---

### 4. Odds Feed API (可用)

**端点**: `https://odds-feed.p.rapidapi.com`

**返回数据示例**:
```json
{
  "success": true,
  "data": [
    {
      "id": "match_id",
      "sport": "soccer",
      "league": "Premier League",
      "home_team": "Team A",
      "away_team": "Team B",
      "odds": {
        "home": 1.5,
        "draw": 3.5,
        "away": 5.0
      }
    }
  ]
}
```

**可用数据**: 比赛赔率、亚盘赔率、大小球赔率

---

### 5. Bet365 API (可用)

**端点**: `https://bet365-api.p.rapidapi.com`

**可用数据**: Bet365专项赔率数据

---

### 6. Football Betting Odds API (可用)

**端点**: `https://football-betting-odds.p.rapidapi.com`

**可用数据**: 综合足球赔率数据

---

### 7. apifootball API (可用)

**端点**: `https://apifootball.com/api/`

**关键端点**:
- `/matches/` - 比赛列表
- `/matches/{match_id}/goalscorer` - 进球详情，包含 `time` 字段（进球时间）

**可用数据**:
- 比赛基本信息
- 进球时间分布（通过 `goalscorer.time`）
- 比赛统计

---

## 数据缺失对照表

| 数据类型 | 当前状态 | 可获取API |
|----------|----------|-----------|
| **xG数据** | ❌ 缺失 | Football xG Statistics API 数据覆盖有限，不推荐 |
| **进球时间分布** | ⚠️ 部分有 | apifootball (`goalscorer.time`) |
| **赔率数据** | ❌ 缺失 | Odds Feed, Bet365, Football Betting Odds ✅ |
| **比赛统计** | ⚠️ 部分有 | apifootball, sportmonks(有限) |
| **球员统计** | ❌ 缺失 | FlashLive Sports (需足球event_id) |

---

## 推荐方案

### 获取赔率数据
使用 **Odds Feed API** 或 **Football Betting Odds API**，两者都可用且数据完整。

### 获取进球时间分布
使用 **apifootball API** 的 `goalscorer` 端点，解析 `time` 字段。

### 获取xG数据
**Football xG Statistics API** 数据覆盖极有限（仅英格兰），不推荐。
建议考虑其他来源：
- StatsBomb开源数据（已有部分）
- FBref网站数据（需爬虫）
- Understat数据（需爬虫）

---

## 下一步建议

1. **赔率数据**: 集成 Odds Feed API，填充数据库赔率字段
2. **进球时间**: 集成 apifootball goalscorer 端点
3. **xG数据**: 继续使用 StatsBomb 数据，或寻找其他xG数据源