---
name: fetcher-download-other-sources
description: 所有Download/特殊类fetcher（CSV下载、Selenium、免费API、中文抓取等）
metadata: 
  node_type: memory
  type: reference
  originSessionId: a3325eab-87ac-48a6-8496-2ff45be69cae
---

# Download / 特殊类 Fetcher 调用方式与 ID 映射

## 1. football_data_uk (football-data.co.uk CSV下载)

**Base URL**: `https://www.football-data.co.uk`
**方式**: 直接下载CSV文件，无需认证

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 当前赛季 | /mmz4281/{season}/{league}.csv | season如2425, league如E0 |
| 历史 | /mmz4281/{season}/{league}.csv | 同上 |

**LEAGUE_CODES**:
| 代码 | 联赛 | 代码 | 联赛 |
|------|------|------|------|
| E0 | EPL | E1 | Championship |
| E2 | League One | E3 | League Two |
| SC0 | Scottish Prem | D1 | Bundesliga |
| D2 | Bundesliga 2 | I1 | Serie A |
| I2 | Serie B | SP1 | La Liga |
| SP2 | La Liga 2 | F1 | Ligue 1 |
| F2 | Ligue 2 | N1 | Eredivisie |
| P1 | Primeira Liga | B1 | Jupiler Pro |
| T1 | Super Lig | | |

**CSV字段**（E0核心字段）:
- Div, Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR, HTHG, HTAG, HTR
- B365H, B365D, B365A (Bet365 1X2)
- BWH, BWD, BWA (Bet&Win)
- IWH, IWD, IWA (Interwetten)
- PSH, PSD, PSA (Pinnacle)
- WHH, WHD, WHA (William Hill)
- B365>2.5, B365<2.5 (大小球)
- AHh, B365AHH, B365AHA (亚盘)

**Python**:
```python
import requests
r = requests.get("https://www.football-data.co.uk/mmz4281/2425/E0.csv")
# 直接下载CSV文本，parse后入库
```

---

## 2. statsbomb (StatsBomb Open Data — GitHub)

**Base URL**: `https://raw.githubusercontent.com/statsbomb/open-data/master/data`
**方式**: 直接下载JSON文件，无需认证

| 端点 | URL模板 | 说明 |
|------|---------|------|
| competitions | /competitions.json | 所有联赛+赛季列表 |
| matches | /matches/{comp_id}/{season_id}.json | 某联赛某赛季所有比赛 |
| events | /events/{match_id}.json | 单场比赛所有事件(含xG) |
| lineups | /lineups/{match_id}.json | 阵容 |
| 360 | /three-sixty/{match_id}.json | 360数据(付费) |

**已知comp+season ID**:
| 联赛 | comp_id | season_id |
|------|---------|-----------|
| FA WSL | 2 | 44 |
| NWSL | 2 | 22 |
| La Liga 2015-20 | 11 | 多个 |
| Serie A 2015-20 | 12 | 多个 |
| Bundesliga 2015-20 | 9 | 多个 |
| WC 2018/2022 | 43 | 3 / 44 |
| Euro 2020 | 55 | 43 |
| CL 2015-20 | 16 | 多个 |

**Python**:
```python
import requests
r = requests.get("https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json")
r = requests.get("https://raw.githubusercontent.com/statsbomb/open-data/master/data/matches/11/42.json")  # La Liga 20-21
```

---

## 3. flashscore (FlashScore — Selenium)

**Base URL**: `https://www.flashscore.com`
**方式**: Selenium headless Chrome

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 实时比分 | / | 主页 |
| 比赛 | /match/{match_id}/ | 详情页 |
| 统计 | /match/{match_id}/#match-statistics | 需点击tab |

**CSS SELECTORS**:
| 元素 | 选择器 |
|------|--------|
| match_row | .event__match |
| match_time | .event__time |
| home_team | .event__participant--home |
| away_team | .event__participant--away |
| score | .event__scores |
| league_header | .event__header |

**注意**: FlashScore反爬最严格，必须用Selenium，单次间隔>2秒

---

## 4. bifen188 (188比分 — Selenium/requests)

**Base URL**: `https://bf.188bifen.com`
**方式**: requests + BeautifulSoup

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 实时 | /live/ | 主页 |
| 详情 | /match/{match_id} | — |
| 阵容 | /match/{match_id}/lineup | — |

**注意**: 中文比分站，含亚盘/大小球数据

---

## 5. okooo (Okooo — 澳客网)

**Base URL**: `https://www.okooo.com`
**API**: `https://api.okooo.com`
**方式**: requests + BeautifulSoup

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 赛程 | /soccer/{date}/ | 按日期 |
| 比赛详情 | /match/{match_id}/ | — |
| 欧赔 | /match/{match_id}/odds/euro/ |多家bookmaker 1X2 |
| 亚盘 | /match/{match_id}/odds/asian/ | — |
| 大小球 | /match/{match_id}/odds/overunder/ | — |
| 分析 | /match/{match_id}/analysis/ | — |

**注意**: 中文赔率站，数据丰富(含威廉希尔/立博/平博等)

---

## 6. hupu (虎扑)

**Base URL**: `https://bbs.hupu.com`
**API**: `https://games.hupu.com`
**方式**: requests + BeautifulSoup

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 赛程 | /soccer/match/list?date={date} | — |
| 比赛 | /soccer/match/{match_id} | — |
| 论坛 | /soccer/board | — |

---

## 7. openweathermap (OpenWeatherMap)

**认证**: Query param `appid={key}`，key 从 env `OPENWEATHERMAP_KEY`
**Base URL**: `https://api.openweathermap.org/data/2.5`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| current | /weather | q(城市), lat+lon, units |
| forecast | /forecast | lat, lon, units |
| onecall | /onecall | lat, lon, units |

---

## 8. weather (Open-Meteo — 免费无需key)

**Base URL**: `https://api.open-meteo.com/v1`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| current | /forecast | lat, lon, current_weather=true |
| forecast | /forecast | lat, lon, daily=... |

**Python**:
```python
r = requests.get("https://api.open-meteo.com/v1/forecast?latitude=51.5&longitude=-0.1&current_weather=true")
```

---

## 9. scorebat (Scorebat — 足球视频集锦)

**认证**: Query param `token={key}`
**Base URL**: `https://www.scorebat.com/video-api/v3`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| feed | /feed/ | token, competition, team |

**Python**:
```python
r = requests.get("https://www.scorebat.com/video-api/v3/feed/?token={key}")
```

---

## 10. wikipedia (Wikipedia API — 免费)

**Base URL**: `https://en.wikipedia.org/w/api.php`
**方式**: MediaWiki API

| 端点 | 参数 | 说明 |
|------|------|------|
| search | action=query, list=search, srsearch={query} | 搜索 |
| summary | action=query, prop=extracts, titles={title} | 摘要 |
| page | action=query, prop=revisions, titles={title} | 全文 |

**Python**:
```python
params = {"action": "query", "format": "json", "list": "search", "srsearch": "Arsenal FC"}
r = requests.get("https://en.wikipedia.org/w/api.php", params=params)
```