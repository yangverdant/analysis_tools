---
name: odds-feed-api
description: Odds Feed API双入口、认证、tournament ID、数据结构、采集策略完整记录
metadata: 
  node_type: memory
  type: reference
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

# Odds Feed API 完整信息

## 两个入口（独立配额）

| 入口 | Base URL | 认证方式 | Key |
|------|----------|----------|-----|
| RapidAPI(新) | `https://odds-feed.p.rapidapi.com` | Header: `x-rapidapi-key` + `x-rapidapi-host` | `36ce000ce1msh435e51a1d194fafp1883eejsn26b0639b7066` |
| RapidAPI(旧) | `https://odds-feed.p.rapidapi.com` | Header: `x-rapidapi-key` + `x-rapidapi-host` | `232de9f410msh8da4a38f557b694p1d2d4fjsn978df1ba1263`（2026-05配额用完，下月恢复） |
| HugeAPI | `https://odds-feed-api.hgapi.top` | Header: `x-portal-apikey` | `1bef4599c8a1442d8cbb7f30e9b61499` |
| Portal API | `https://{API_HOST}/api/v1` | Header: `x-portal-apikey` | 见 `fetchers/odds_feed_api/config.py` |

**关键**：三个入口配额独立。RapidAPI旧账号5月配额已用完（6月恢复），新账号和HugeAPI当前可用。Portal API是独立入口，认证方式与HugeAPI相同（都用 `x-portal-apikey`），但host不同。

## Tournament ID（用户从oddsfe.com验证确认）

| 联赛 | Tournament ID | League Standard Name |
|------|-------------|---------------------|
| Premier League | **430** | Premier League |
| Bundesliga | **560** | Bundesliga |
| Serie A | **719** | Serie A |
| LaLiga | **1146** | LaLiga |
| LaLiga2 | **1147** | LaLiga2 |
| Serie B | **720** | Serie B |
| Eredivisie | **862** | Eredivisie |
| J1 League | **763** | J1 League |
| MLS | **1265** | MLS |
| Championship | **431** | Championship |
| League One | **432** | League One |
| League Two | **433** | League Two |
| National League | **434** | National League |
| NPL Western Australia | **109** | NPL Western Australia |
| China Super League | **322** | China Super League |
| Bundesliga 2 | **561** | Bundesliga 2 |
| 3. Liga | **562** | 3. Liga |
| Ligue 1 | 待确认 | Ligue 1（之前445/540都不对） |
| Ligue 2 | **540**（待验证） | Ligue 2 |

## Portal API 端点（独立入口，用 x-portal-apikey 认证）

### P1. 按日期查赛事
```
GET /api/v1/events
参数: sport_id=1, start_at_min=2026-05-28 00:00:00, start_at_max=2026-05-29 00:00:00
认证: Header x-portal-apikey: {key}
```
Python:
```python
import requests
headers = {'x-portal-apikey': '{key}'}
params = {
    'sport_id': '1',
    'start_at_min': '2026-05-28 00:00:00',
    'start_at_max': '2026-05-29 00:00:00',
}
response = requests.get('https://{API_HOST}/api/v1/events', params=params, headers=headers)
```
Curl:
```bash
curl --header 'x-portal-apikey: {key}' "https://{API_HOST}/api/v1/events?sport_id=1&start_at_min=2026-05-28%2000:00:00&start_at_max=2026-05-29%2000:00:00"
```

### P2. 按event_id查赛事
```
GET /api/v1/events
参数: event_ids=592956
认证: Header x-portal-apikey: {key}
```
Python:
```python
import requests
headers = {'x-portal-apikey': '{key}'}
params = {'event_ids': '592956'}
response = requests.get('https://{API_HOST}/api/v1/events', params=params, headers=headers)
```
Curl:
```bash
curl --header 'x-portal-apikey: {key}' "https://{API_HOST}/api/v1/events?event_ids=592956"
```

### P3. 按event_id查赔率(markets)
```
GET /api/v1/events/markets
参数: event_id=592956
认证: Header x-portal-apikey: {key}
```
Python:
```python
import requests
headers = {'x-portal-apikey': '{key}'}
params = {'event_id': '592956'}
response = requests.get('https://{API_HOST}/api/v1/events/markets', params=params, headers=headers)
```
Curl:
```bash
curl --header 'x-portal-apikey: {key}' "https://{API_HOST}/api/v1/events/markets?event_id=592956"
```

**Portal API vs RapidAPI/HugeAPI 区别**：
- 认证统一用 `x-portal-apikey`（不用 `x-rapidapi-key`/`x-rapidapi-host`）
- Events 支持 `start_at_min/max` 按日期范围查询（RapidAPI不支持）
- Events 支持 `event_ids` 按ID查单场（RapidAPI用 tournament_id+page）
- Markets 路径是 `/api/v1/events/markets?event_id=` 单个赛事（RapidAPI用 `/api/v1/markets/feed?event_ids=` 批量）
- API_HOST 具体值见 config.py

## 核心API端点（RapidAPI/HugeAPI）

### 1. Events List（最关键 — 一个请求=赛事+比分+赔率）
```
GET /api/v1/events
参数: sport_id=1, tournament_id={id}, page={n}, per_page=100
返回: total, per_page, current_page, last_page, data[]
```

Events直接包含赔率字段：
- `main_outcome_0` = 主胜欧赔
- `main_outcome_1` = 平局欧赔
- `main_outcome_2` = 客胜欧赔
- `main_volume_1/2` = 投注量

**分页**：`per_page`最大100（不是200），用`last_page`判断是否到最后一页。

### 2. Event Markets（按赛事查详细赔率）
```
GET /api/v1/events/markets
参数: event_id={id}, placing=PREMATCH, market_name=1X2
返回: 多家bookmaker的赔率（Pinnacle/Bet365/1Xbet等）
```

### 3. Markets Feed（批量查赔率，最多100个event_ids）
```
GET /api/v1/markets/feed
参数: event_ids={csv}, placing=PREMATCH, market_name=1X2
```

### 4. Markets History（赔率变动历史）
```
GET /api/v1/markets/history?market_book_id={id}
```

### 5. Tournaments（搜索联赛）
```
GET /api/v1/tournaments
参数: sport_id=1, name={query}, category_id={id}
```

### 6. Categories（按国家查）
```
GET /api/v1/categories?sport_id=1
```
已知: England=49, Spain=149, Italy=77, Germany=60, France=56

### 7. Seasons
```
GET /api/v1/seasons?sport_id=1&tournament_id={id}&year_start=2025
```

## 数据结构

### Event对象核心字段
```json
{
  "id": 589227,
  "sport": {"id": 1, "name": "Football"},
  "category": {"id": 49, "name": "England"},
  "tournament": {"id": 430, "name": "Premier League"},
  "season": {"id": 23865, "slug": "2025-2026"},
  "team_home": {"id": 1, "name": "Sao Paulo", "team_type": "TEAM"},
  "team_away": {"id": 2, "name": "Palmeiras", "team_type": "TEAM"},
  "status": "FINISHED",
  "start_at": "2024-06-25 22:00:00.000",
  "winner": "HOME_WIN",
  "score_home": 2,
  "score_away": 1,
  "main_outcome_0": 2.2,
  "main_outcome_1": 3.8,
  "main_outcome_2": 2.1,
  "main_volume_1": 2495,
  "main_volume_2": 5495
}
```

### Market Book对象（详细赔率）
```json
{
  "market_book_id": 564,
  "market_id": 1,
  "is_open": true,
  "book": "PINNACLE",
  "outcome_0": 2.2,
  "outcome_1": 3.8,
  "outcome_2": 2.1
}
```

### 支持的Bookmaker
BETFAIR_EXCHANGE, MATCHBOOK, PINNACLE, BET365, 1XBET, ASIAN_ODDS, BETFAIR, UNIBET, DAFABET, 888_SPORT, WILLIAM_HILL, BET_AT_HOME, BWIN_ES, BET_IN_ASIA, STAKE_COM, BWIN

### Market Types
1X2, OVER_UNDER, ASIAN_HANDICAP, HOME_AWAY, BOTH_TEAMS_TO_SCORE

### Event Status
FINISHED, LIVE, SCHEDULED, CANCELLED, DELAYED, INTERRUPTED, POSTPONED, ABANDONED

## 已有数据状态（2026-05-26）

- PL: 749场赔率已采集
- Bundesliga: 503场（tid=429的数据，需用560重新采集）
- La Liga/Serie A/Ligue 1: 仅少量数据
- 总覆盖: 1259场/4085 finished = 30.8%

## 采集策略

1. **优先用HugeAPI入口**（RapidAPI配额已用完）
2. **用events端点批量采集**（一个请求=赛事+赔率，不需per-match调用）
3. **per_page=100**，翻页到last_page
4. 依次采集: PL(430) → Bundesliga(560) → SerieA(719) → LaLiga(1146) → 其他
5. 大联赛每个约需8-12页请求
6. INSERT OR REPLACE去重

## 相关代码

- `fetchers/odds_feed_api/config.py` — API配置、tournament ID、球队名映射
- `fetchers/odds_feed_api/get_odds.py` — API调用函数
- `fetchers/scripts/collect_odds.py` — 批量采集脚本