# 足球数据分析系统 - 完整API文档

> 版本: 1.0.0  
> 更新日期: 2026-05-20

---

## 目录

1. [系统概述](#系统概述)
2. [数据源架构](#数据源架构)
3. [API接口总览](#api接口总览)
4. [数据源管理接口](#数据源管理接口)
5. [比赛数据接口](#比赛数据接口)
6. [积分榜接口](#积分榜接口)
7. [球队接口](#球队接口)
8. [球员接口](#球员接口)
9. [联赛信息接口](#联赛信息接口)
10. [AI分析接口](#ai分析接口)
11. [数据同步接口](#数据同步接口)
12. [支持的联赛](#支持的联赛)
13. [错误处理](#错误处理)
14. [使用示例](#使用示例)

---

## 系统概述

### 技术栈

- **后端**: FastAPI + Python 3.10+
- **数据库**: SQLite (football_unified.db)
- **数据源**: 15+ API/爬虫/本地数据源
- **AI**: DeepSeek V4 Pro

### 基础URL

```
http://localhost:8000/api/v1
```

### 认证

当前版本无需认证，所有接口公开访问。

---

## 数据源架构

### 数据源类型

| 类型 | 说明 | 数据源 |
|------|------|--------|
| **API** | 官方/第三方API接口 | Sportmonks, football-data.org, TheSportsDB, ScoreBat, 365Scores, OpenLigaDB |
| **爬虫** | 网页数据爬取 | FBref, FlashScore, Soccerway, ESPN, Understat, Transfermarkt |
| **本地** | 本地文件/数据库 | CSV文件, SQLite数据库, StatsBomb数据 |
| **AI** | AI模型分析 | DeepSeek |

### 数据源优先级

系统按优先级自动选择最佳数据源：

```
本地数据源 (priority 1-3) → API数据源 (priority 4-10) → 爬虫数据源 (priority 7+)
```

### 数据类别

| 类别 | 说明 |
|------|------|
| `livescores` | 实时比分 |
| `fixtures` | 赛程 |
| `standings` | 积分榜 |
| `matches` | 历史比赛 |
| `teams` | 球队信息 |
| `players` | 球员信息 |
| `scorers` | 射手榜 |
| `squads` | 阵容 |
| `statistics` | 统计数据 |
| `xg` | 预期进球数据 |
| `odds` | 赔率数据 |
| `predictions` | 预测数据 |
| `analysis` | AI分析 |

---

## API接口总览

### 数据源管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/data/sources` | 列出所有数据源 |
| GET | `/data/sources/{name}` | 获取数据源详情 |
| POST | `/data/sources/{name}/test` | 测试数据源连接 |
| POST | `/data/sources/test-all` | 测试所有数据源 |

### 比赛数据

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/data/livescores` | 获取实时比分 |
| GET | `/data/fixtures/{league}` | 获取赛程 |
| GET | `/data/matches/{league}` | 获取历史比赛 |

### 积分榜

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/data/standings/{league}` | 获取积分榜 |

### 球队

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/data/teams/{team_id}` | 获取球队信息 |

### 球员

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/data/players` | 获取球员信息 |
| GET | `/data/scorers/{league}` | 获取射手榜 |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/data/leagues` | 列出支持的联赛 |
| GET | `/data/categories` | 列出数据类别 |

---

## 数据源管理接口

### 列出所有数据源

```http
GET /data/sources
```

**响应示例**:

```json
{
  "sources": [
    {
      "name": "sportmonks",
      "type": "api",
      "enabled": true,
      "priority": 1,
      "capabilities": ["livescores", "fixtures", "standings", "teams", "players"],
      "rate_limit": 30
    },
    {
      "name": "football_data_org",
      "type": "api",
      "enabled": true,
      "priority": 2,
      "capabilities": ["matches", "standings", "scorers", "squads"],
      "rate_limit": 10
    }
  ],
  "total": 15
}
```

### 获取数据源详情

```http
GET /data/sources/{source_name}
```

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| source_name | string | 数据源名称 |

**响应示例**:

```json
{
  "name": "sportmonks",
  "type": "api",
  "enabled": true,
  "priority": 1,
  "capabilities": ["livescores", "fixtures", "standings", "teams", "players"],
  "base_url": "https://api.sportmonks.com/v3/football",
  "rate_limit": 30,
  "request_interval": 2.0,
  "leagues": {
    "premier_league": {"id": 8, "name_cn": "英超"},
    "la_liga": {"id": 564, "name_cn": "西甲"}
  }
}
```

### 测试数据源连接

```http
POST /data/sources/{source_name}/test
```

**响应示例**:

```json
{
  "success": true,
  "source": "sportmonks"
}
```

### 测试所有数据源

```http
POST /data/sources/test-all
```

**响应示例**:

```json
{
  "sportmonks": {"success": true},
  "football_data_org": {"success": true},
  "thesportsdb": {"success": true},
  "scorebat": {"success": true},
  "fbref": {"success": false, "error": "Connection timeout"}
}
```

---

## 比赛数据接口

### 获取实时比分

```http
GET /data/livescores
```

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| leagues | string | 否 | 联赛列表，逗号分隔，如 `premier_league,bundesliga` |
| date | string | 否 | 日期，格式 `YYYY-MM-DD`，默认今天 |
| sources | string | 否 | 指定数据源，逗号分隔 |
| merge | boolean | 否 | 是否合并多数据源结果，默认 `true` |

**响应示例**:

```json
{
  "matches": [
    {
      "match_id": "12345",
      "home_team": "Arsenal",
      "away_team": "Chelsea",
      "home_score": 2,
      "away_score": 1,
      "home_score_ht": 1,
      "away_score_ht": 0,
      "date": "2026-05-20",
      "time": "21:00",
      "status": "finished",
      "league": "Premier League",
      "round_num": 38,
      "source": "football_data_org"
    }
  ],
  "total": 10,
  "date": "2026-05-20"
}
```

### 获取赛程

```http
GET /data/fixtures/{league}
```

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| league | string | 联赛代码，如 `premier_league` |

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| season | string | 否 | 赛季，如 `2025-2026` |
| team | string | 否 | 球队名称筛选 |
| from_date | string | 否 | 开始日期 |
| to_date | string | 否 | 结束日期 |
| source | string | 否 | 指定数据源 |

**响应示例**:

```json
{
  "league": "premier_league",
  "season": "2025-2026",
  "matches": [
    {
      "match_id": "12345",
      "home_team": "Arsenal",
      "away_team": "Chelsea",
      "date": "2026-05-20",
      "time": "21:00",
      "status": "SCHEDULED",
      "round_num": 38,
      "source": "football_data_org"
    }
  ],
  "total": 380
}
```

### 获取历史比赛

```http
GET /data/matches/{league}
```

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| league | string | 联赛代码 |

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| season | string | 否 | 赛季 |
| team | string | 否 | 球队名称筛选 |
| limit | integer | 否 | 限制返回数量 |
| source | string | 否 | 指定数据源 |

**响应示例**:

```json
{
  "league": "premier_league",
  "season": "2025-2026",
  "matches": [
    {
      "match_id": "12345",
      "home_team": "Arsenal",
      "away_team": "Chelsea",
      "home_score": 2,
      "away_score": 1,
      "date": "2026-05-20",
      "round_num": 38,
      "source": "local_csv"
    }
  ],
  "total": 380
}
```

---

## 积分榜接口

### 获取积分榜

```http
GET /data/standings/{league}
```

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| league | string | 联赛代码 |

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| season | string | 否 | 赛季 |
| source | string | 否 | 指定数据源 |

**响应示例**:

```json
{
  "league": "premier_league",
  "season": "2025-2026",
  "standings": [
    {
      "position": 1,
      "team": "Liverpool",
      "team_id": "64",
      "played": 38,
      "won": 28,
      "drawn": 7,
      "lost": 3,
      "goals_for": 85,
      "goals_against": 32,
      "goal_difference": 53,
      "points": 91,
      "form": "WDWWW",
      "source": "football_data_org"
    }
  ],
  "total": 20
}
```

---

## 球队接口

### 获取球队信息

```http
GET /data/teams/{team_id}
```

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| team_id | string | 球队ID或名称 |

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source | string | 否 | 指定数据源 |

**响应示例**:

```json
{
  "team_id": "64",
  "name": "Liverpool",
  "short_name": "Liverpool",
  "tla": "LIV",
  "country": "England",
  "founded": 1892,
  "venue": "Anfield",
  "capacity": 54074,
  "logo_url": "https://crests.football-data.org/64.png",
  "source": "football_data_org"
}
```

---

## 球员接口

### 获取球员信息

```http
GET /data/players
```

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| team | string | 否 | 球队名称 |
| league | string | 否 | 联赛 |
| season | string | 否 | 赛季 |
| source | string | 否 | 指定数据源 |

**响应示例**:

```json
{
  "players": [
    {
      "player_id": "123",
      "name": "Mohamed Salah",
      "team": "Liverpool",
      "position": "Forward",
      "nationality": "Egypt",
      "date_of_birth": "1992-06-15",
      "goals": 28,
      "assists": 10,
      "appearances": 38,
      "source": "football_data_org"
    }
  ],
  "total": 25
}
```

### 获取射手榜

```http
GET /data/scorers/{league}
```

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| league | string | 联赛代码 |

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| season | string | 否 | 赛季 |
| limit | integer | 否 | 限制返回数量 |
| source | string | 否 | 指定数据源 |

**响应示例**:

```json
{
  "league": "premier_league",
  "season": "2025-2026",
  "scorers": [
    {
      "player_id": "123",
      "name": "Mohamed Salah",
      "team": "Liverpool",
      "goals": 28,
      "assists": 10,
      "appearances": 38,
      "source": "football_data_org"
    }
  ],
  "total": 20
}
```

---

## 联赛信息接口

### 列出支持的联赛

```http
GET /data/leagues
```

**响应示例**:

```json
{
  "leagues": [
    {"code": "premier_league", "name": "英超", "country": "England"},
    {"code": "la_liga", "name": "西甲", "country": "Spain"},
    {"code": "bundesliga", "name": "德甲", "country": "Germany"},
    {"code": "serie_a", "name": "意甲", "country": "Italy"},
    {"code": "ligue_1", "name": "法甲", "country": "France"}
  ],
  "total": 20
}
```

### 列出数据类别

```http
GET /data/categories
```

**响应示例**:

```json
{
  "categories": [
    {"code": "livescores", "name": "实时比分"},
    {"code": "fixtures", "name": "赛程"},
    {"code": "standings", "name": "积分榜"},
    {"code": "matches", "name": "历史比赛"},
    {"code": "teams", "name": "球队信息"},
    {"code": "players", "name": "球员信息"},
    {"code": "scorers", "name": "射手榜"}
  ]
}
```

---

## AI分析接口

### 获取比赛AI分析

```http
POST /ai/analyze/match
```

**请求体**:

```json
{
  "home_team": "Arsenal",
  "away_team": "Chelsea",
  "league": "premier_league",
  "include_prediction": true
}
```

**响应示例**:

```json
{
  "analysis": "阿森纳近期状态出色，主场优势明显...",
  "prediction": {
    "home_win": 0.55,
    "draw": 0.25,
    "away_win": 0.20,
    "predicted_score": "2-1"
  },
  "key_factors": [
    "阿森纳主场5连胜",
    "切尔西客场防守不稳"
  ]
}
```

---

## 数据同步接口

### 同步联赛数据

```http
POST /sync/{league}
```

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| league | string | 联赛代码 |

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| season | string | 否 | 赛季 |
| source | string | 否 | 数据源 |

**响应示例**:

```json
{
  "status": "success",
  "league": "premier_league",
  "season": "2025-2026",
  "matches_synced": 380,
  "standings_synced": true
}
```

---

## 支持的联赛

### 五大联赛

| 代码 | 名称 | 国家 |
|------|------|------|
| `premier_league` | 英超 | England |
| `la_liga` | 西甲 | Spain |
| `bundesliga` | 德甲 | Germany |
| `serie_a` | 意甲 | Italy |
| `ligue_1` | 法甲 | France |

### 二级联赛

| 代码 | 名称 | 国家 |
|------|------|------|
| `championship` | 英冠 | England |
| `bundesliga_2` | 德乙 | Germany |
| `ligue_2` | 法乙 | France |
| `segunda_division` | 西乙 | Spain |
| `serie_b` | 意乙 | Italy |

### 其他欧洲联赛

| 代码 | 名称 | 国家 |
|------|------|------|
| `eredivisie` | 荷甲 | Netherlands |
| `primeira_liga` | 葡超 | Portugal |

### 欧战赛事

| 代码 | 名称 |
|------|------|
| `champions_league` | 欧冠 |
| `europa_league` | 欧联 |
| `conference_league` | 欧协联 |

### 国家队赛事

| 代码 | 名称 |
|------|------|
| `world_cup` | 世界杯 |
| `euro` | 欧洲杯 |

### 亚洲/美洲联赛

| 代码 | 名称 | 国家 |
|------|------|------|
| `k1_league` | K1联赛 | South Korea |
| `j1_league` | J1联赛 | Japan |
| `mls` | 美职联 | USA |

---

## 错误处理

### 错误响应格式

```json
{
  "detail": "数据源 sportmonks 不存在"
}
```

### HTTP状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 数据源不可用 |

### 常见错误

| 错误 | 说明 |
|------|------|
| `Source not found` | 数据源不存在 |
| `League not supported` | 不支持的联赛 |
| `Connection timeout` | 数据源连接超时 |
| `Rate limit exceeded` | 请求频率超限 |

---

## 使用示例

### Python示例

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# 获取实时比分
response = requests.get(f"{BASE_URL}/data/livescores", params={
    "leagues": "premier_league,bundesliga",
    "date": "2026-05-20"
})
matches = response.json()["matches"]

# 获取积分榜
response = requests.get(f"{BASE_URL}/data/standings/premier_league", params={
    "season": "2025-2026"
})
standings = response.json()["standings"]

# 指定数据源
response = requests.get(f"{BASE_URL}/data/fixtures/premier_league", params={
    "season": "2025-2026",
    "source": "football_data_org"
})
fixtures = response.json()["matches"]
```

### JavaScript示例

```javascript
const BASE_URL = "http://localhost:8000/api/v1";

// 获取实时比分
async function getLivescores() {
  const response = await fetch(`${BASE_URL}/data/livescores?leagues=premier_league`);
  const data = await response.json();
  return data.matches;
}

// 获取积分榜
async function getStandings(league, season) {
  const response = await fetch(`${BASE_URL}/data/standings/${league}?season=${season}`);
  const data = await response.json();
  return data.standings;
}

// 测试数据源
async function testSource(sourceName) {
  const response = await fetch(`${BASE_URL}/data/sources/${sourceName}/test`, {
    method: 'POST'
  });
  return await response.json();
}
```

### cURL示例

```bash
# 获取实时比分
curl "http://localhost:8000/api/v1/data/livescores?leagues=premier_league"

# 获取积分榜
curl "http://localhost:8000/api/v1/data/standings/premier_league?season=2025-2026"

# 测试数据源
curl -X POST "http://localhost:8000/api/v1/data/sources/sportmonks/test"

# 获取射手榜
curl "http://localhost:8000/api/v1/data/scorers/premier_league?limit=10"
```

---

## 附录

### 数据源配置文件

配置文件位置: `api_config.json`

```json
{
  "version": "1.0",
  "apis": {
    "sportmonks": {
      "base_url": "https://api.sportmonks.com/v3/football",
      "api_token": "YOUR_TOKEN",
      "rate_limit": 30,
      "priority": 1
    },
    "football_data_org": {
      "base_url": "https://api.football-data.org/v4",
      "api_token": "YOUR_TOKEN",
      "rate_limit": 10,
      "priority": 2
    }
  }
}
```

### 数据模型

#### MatchData

| 字段 | 类型 | 说明 |
|------|------|------|
| match_id | string | 比赛ID |
| home_team | string | 主队名称 |
| away_team | string | 客队名称 |
| home_score | integer | 主队比分 |
| away_score | integer | 客队比分 |
| date | string | 比赛日期 |
| time | string | 比赛时间 |
| status | string | 比赛状态 |
| league | string | 联赛名称 |
| round_num | integer | 轮次 |
| source | string | 数据来源 |

#### StandingData

| 字段 | 类型 | 说明 |
|------|------|------|
| position | integer | 排名 |
| team | string | 球队名称 |
| played | integer | 已赛场次 |
| won | integer | 胜 |
| drawn | integer | 平 |
| lost | integer | 负 |
| goals_for | integer | 进球 |
| goals_against | integer | 失球 |
| goal_difference | integer | 净胜球 |
| points | integer | 积分 |
| form | string | 近期战绩 |

#### TeamData

| 字段 | 类型 | 说明 |
|------|------|------|
| team_id | string | 球队ID |
| name | string | 球队名称 |
| short_name | string | 简称 |
| country | string | 国家 |
| founded | integer | 成立年份 |
| venue | string | 主场 |
| capacity | integer | 容量 |
| logo_url | string | 队徽URL |

#### PlayerData

| 字段 | 类型 | 说明 |
|------|------|------|
| player_id | string | 球员ID |
| name | string | 球员名称 |
| team | string | 所属球队 |
| position | string | 位置 |
| nationality | string | 国籍 |
| goals | integer | 进球数 |
| assists | integer | 助攻数 |
| appearances | integer | 出场次数 |

---

## 更新日志

### v1.0.0 (2026-05-20)

- 初始版本发布
- 支持15+数据源
- 实现统一数据接口
- 添加AI分析功能
- 支持多数据源自动切换和合并
