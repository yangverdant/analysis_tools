---
name: oddsfe-com-scraper
description: oddsfe.com网站爬取方式：内部API端点、认证header、数据结构、赛事字段、采集策略
metadata: 
  node_type: memory
  type: reference
  originSessionId: a3325eab-87ac-48a6-8496-2ff45be69cae
---

# oddsfe.com 爬取完整信息

## 网站
- URL: `https://oddsfe.com/schedule/football/{YYYY-MM-DD}`
- 修改日期可查看每天的比赛内容
- 是Odds Feed API的官网展示前端

## 内部API端点（从active.js逆向获取）

### 1. 赛程列表（核心端点）
```
GET https://oddsfe.com/bind/schedule/{sport}/{date}
例: /bind/schedule/football/2026-05-27
认证: 需要3个自定义header（见下方）
返回: JSON array, 每个元素是一个tournament(联赛)，内含events列表
```

### 2. 单场赛事详情（比分+状态）
```
GET https://oddsfe.com/bind/event/{event_id}
例: /bind/event/571506
认证: 需要1个自定义header（f6309c3a4cbe8a02f266f3d44b88f2af）
返回: JSON dict — event_id, event_status, score_home, score_away, score_details, winner
```

**注意**: `/bind/event/` 返回的是比分/状态摘要，不含赔率。赔率数据通过 HTML 页面获取。

### 3. 赛事详情页（赔率核心数据 — HTML渲染）
```
GET https://oddsfe.com/events/{event_id}
例: /events/571506
参数（query string切换市场类型）:
  mt=1X2                    — 标准胜平负
  mt=OVER_UNDER             — 大小球
  mt=ASIAN_HANDICAP         — 亚盘
  mt=BOTH_TEAMS_TO_SCORE    — 双方进球
  live=False                — 开盘赔率(默认)
  live=True                 — 滚球赔率
```

### 4. 赔率变动历史
```
GET https://oddsfe.com/history/{bookmaker_event_id}
例: /history/92759936
返回: HTML页面，含完整赔率变动时间线
数据: 赔率变化记录表格(时间+1/X/2)，实测单场182条记录
bookmaker_event_id: 与event_id不同，需从赛事页面链接提取
```

## 认证 Header（关键）

不带header返回 401: Missing bearer token

| Header名 | Header值 | 哪个端点需要 |
|----------|----------|-------------|
| `4e03bff03849a16a21ab4f767d33105f` | `908188c313330fb5a125e9371c8128bf` | schedule |
| `n7R6b9CKPdnd46vK1` | `59nfZbY3yIb` | schedule |
| `bearer` | `SnrsZ0OzuEZvauaA8mq0eXl6Qkq0B7==` | schedule |
| `f6309c3a4cbe8a02f266f3d44b88f2af` | `f3bbdf3a786dd85cf493f72b91ba5bf0` | event |

**注意**: schedule端点和event端点用不同的认证header！schedule用3个header，event只用1个(f6309...)。

## 数据结构

### Tournament 对象
```json
{
  "tournament": {"id": 430, "name": "Premier League", "slug": "premier-league"},
  "season": {"id": 23865, "slug": "2025-2026"},
  "category": {"id": 49, "name": "England", "slug": "england"},
  "sum_tournament_outcome_volume": "2 716 300 €",
  "events": [ ... ]
}
```

### Event 对象（每场比赛）
```json
{
  "event_id": 587646,
  "event_start_at": "2026-05-27T19:00:00",
  "event_status": "FINISHED",
  "event_tournament_id": 470,
  "event_pin_event_id": 1630267880,
  "event_winner": 0,  // 0=主胜, 1=平, 2=客胜
  "event_score_home": 1,
  "event_score_away": 0,
  "event_outcome_0": 211,  // 欧赔×100（实际赔率=2.11）
  "event_outcome_1": 321,
  "event_outcome_2": 409,
  "event_volume_0": 2000,
  "event_volume_1": 2000,
  "event_volume_2": 2000,
  "tournament_id": 470,
  "tournament_name": "Conference League",
  "season_id": 23220,
  "season_slug": "2025-2026",
  "team_home_id": 588,
  "team_home_name": "Crystal Palace",
  "team_away_id": 1214,
  "team_away_name": "Rayo Vallecano",
  "category_id": 52,
  "category_name": "Europe",
  "category_slug": "europe",
  "main_out_0": "2.11",     // Pinnacle主胜赔率（字符串）
  "main_volume_0": "20 000 €",
  "main_out_1": "3.21",     // Pinnacle平局赔率
  "main_volume_1": "20 000 €",
  "main_out_2": "4.09",     // Pinnacle客胜赔率
  "main_volume_2": "20 000 €",
  "event_link": "https://oddsfe.com/events/587646"
}
```

### 关键发现
- **赔率字段有两套**：`event_outcome_0/1/2` 是整数×100（如211=2.11），`main_out_0/1/2` 是字符串格式（如"2.11"）
- **main_out 系列**来自Pinnacle（主bookmaker），含投注量(volume)
- **event_volume** 看起来是归一化后的值
- **event_winner**: 0=主胜(HOME_WIN), 1=平(DRAW), 2=客胜(AWAY_WIN)
- **event_pin_event_id**: Pinnacle内部ID，可用于对齐数据

### Event detail 返回（/bind/event/{id}）
```json
{
  "event_id": 592956,
  "event_status": "FINISHED",
  "event_status_details": null,
  "final_result_only": false,
  "score_home": 1,
  "score_away": 3,
  "score_details": "(0:1, 1:2)",
  "comments": null,
  "winner": 2
}
```
比分详情含半场比分！

## 已知 Tournament ID（从5月27日实际数据验证）

| tid | 联赛名 | tid | 联赛名 |
|-----|---------|-----|---------|
| 430 | Premier League | 470 | Conference League |
| 560 | Bundesliga | 719 | Serie A |
| 1146 | LaLiga | 1123 | Copa Libertadores |
| 1124 | Copa Sudamericana | 322 | China Super League |
| 862 | Eredivisie | 763 | J1 League |
| 1265 | MLS | 431 | Championship |
| 778 | Premier League(其他地区) | 50 | Premier League(其他) |

**注意**: 同名"Premier League"可能有多个tid（不同国家），需用category区分

## 采集策略

1. **按日期批量采集** — `/bind/schedule/football/{date}` 一次请求拿当天所有赛事+基础赔率(Pinnacle 1X2)
2. **赛事详情HTML解析** — `/events/{event_id}?mt={市场}&live={开盘/滚球}` 获取30家bookmaker详细赔率
3. **赔率变动历史** — `/history/{bk_event_id}` 获取开盘→闭盘的完整赔率变化时间线
4. **速度控制** — 每次请求间隔3-5秒，避免触发反爬
5. **两个认证体系** — schedule用3个header，event用1个不同的header
6. **三个数据源互补**：
   - oddsfe.com `/bind/schedule/` → 赛事列表+Pinnacle基础赔率（最快）
   - oddsfe.com `/events/{id}` → 30家bookmaker详细赔率（最全）
   - Portal API `/api/v1/events/markets` → JSON格式赔率数据（最结构化）
7. **日期范围** — 可循环遍历过去N天的日期，补采历史数据

## 赛事详情页数据结构（/events/{id} — HTML解析）

详情页是服务端渲染(SSR)的HTML，需用BeautifulSoup解析。通过query string切换市场类型。

### 赔率数据格式
每个bookmaker一行，结构为 `div.row.border-bottom.cast-hover`：
```
| Bookmaker名 | 赔率1 | 赔率X | 赔率2 | [volume] | 时间 |
```

### 1X2 Prematch（默认 mt=1X2&live=False）
- 约30家bookmaker的1X2赔率
- 含：PINNACLE, BET365, 1XBET, UNIBET, DRAKE, COOL等
- 每行包含：bookmaker名 + 1/X/2赔率 + 更新时间
- Bookmaker名有链接到 `/history/{bk_event_id}`（赔率变动时间线）

### OVER_UNDER（mt=OVER_UNDER）
- 大小球赔率，含盘口线(如2.5)
- 格式：Bookmaker | Over赔率 | 盘口线 | Under赔率 | 时间

### ASIAN_HANDICAP（mt=ASIAN_HANDICAP）
- 亚盘赔率，含让球数
- 格式：Bookmaker | 主让赔率 | 让球数 | 客让赔率 | 时间

### BOTH_TEAMS_TO_SCORE（mt=BOTH_TEAMS_TO_SCORE）
- 双方进球(是/否)
- 格式：Bookmaker | Yes赔率 | No赔率 | 时间

### Live赔率（live=True）
- 同上四种市场类型，但为滚球(in-play)赔率
- 数据量可能较少（取决于是否有滚球数据）

### 赛事基本信息
页面顶部有赛事信息表格：
- 比赛时间、联赛、球队
- 比分（如已完赛）
- 其他赛事元数据

## 赔率变动历史（/history/{bk_event_id}）

- 返回HTML页面，含赔率变动时间线
- 格式：时间 + 1/X/2 赔率变动记录
- 实测单场182条记录（从开盘到闭盘的完整变化）
- bk_event_id 与 event_id 不同，需从赛事页面的bookmaker链接提取

## Python调用示例

```python
import requests
from bs4 import BeautifulSoup

s = requests.Session()
s.trust_env = False  # 禁用系统代理

# === 1. 获取某天所有赛事（JSON API） ===
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://oddsfe.com',
    'Referer': 'https://oddsfe.com/schedule/football/2026-05-27',
    '4e03bff03849a16a21ab4f767d33105f': '908188c313330fb5a125e9371c8128bf',
    'n7R6b9CKPdnd46vK1': '59nfZbY3yIb',
    'bearer': 'SnrsZ0OzuEZvauaA8mq0eXl6Qkq0B7==',
})
r = s.get('https://oddsfe.com/bind/schedule/football/2026-05-27', timeout=15)
data = r.json()  # list of tournaments, each with events[]

# === 2. 获取单场赛事比分（JSON API） ===
s.headers.update({
    'Referer': 'https://oddsfe.com/events/571506',
    'f6309c3a4cbe8a02f266f3d44b88f2af': 'f3bbdf3a786dd85cf493f72b91ba5bf0',
})
r = s.get('https://oddsfe.com/bind/event/571506', timeout=15)
event = r.json()  # dict with score_details "(0:1, 1:2)"

# === 3. 获取赛事详情页赔率（HTML解析） ===
s2 = requests.Session()
s2.trust_env = False
s2.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

# 1X2 Prematch
r = s2.get('https://oddsfe.com/events/571506', timeout=15)
soup = BeautifulSoup(r.text, 'html.parser')
bk_rows = soup.find_all('div', class_='row border-bottom cast-hover')
for row in bk_rows:
    cols = row.find_all('div', class_=re.compile(r'^col'))
    data = [c.get_text(strip=True) for c in cols]
    # data = [bookmaker, odds_1, odds_x, odds_2, time]

# 亚盘
r = s2.get('https://oddsfe.com/events/571506?mt=ASIAN_HANDICAP', timeout=15)

# 大小球
r = s2.get('https://oddsfe.com/events/571506?mt=OVER_UNDER', timeout=15)

# 滚球1X2
r = s2.get('https://oddsfe.com/events/571506?mt=1X2&live=True', timeout=15)

# === 4. 赔率变动历史 ===
r = s2.get('https://oddsfe.com/history/92759936', timeout=15)
# 解析HTML表格获取时间+赔率变化
```

## 与 Portal API (Odds Feed) 的关系

oddsfe.com 是 Odds Feed API 的前端展示网站，两者数据同源：
- **oddsfe.com /bind/schedule/** = Portal API `/api/v1/events` 的精简版（含赔率摘要）
- **oddsfe.com /bind/event/** = Portal API `/api/v1/events/{id}` 的精简版（只含比分）
- Portal API `/api/v1/events/markets` 提供多家bookmaker详细赔率（oddsfe.com前端也展示但需爬HTML）
- **建议**: 用 oddsfe.com 扫赛事列表拿 event_id，再用 Portal API 查详细赔率

## 相关代码与记忆

- [[odds-feed-api]] — Odds Feed API三入口完整信息
- [[odds-feed-team-ids]] — 持续积累的event_id+球队名映射
- [[fetcher-api-sources]] — 所有API类fetcher
- [[fetcher-scrape-sources]] — 所有Scrape类fetcher