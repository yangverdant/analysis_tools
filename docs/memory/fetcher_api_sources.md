---
name: fetcher-api-sources
description: 所有API类fetcher的调用方式、认证、端点、ID映射完整记录（19个）
metadata: 
  node_type: memory
  type: reference
  originSessionId: a3325eab-87ac-48a6-8496-2ff45be69cae
---

# API 类 Fetcher 调用方式与 ID 映射

## 1. api_sports (API-Sports.io v3)

**认证**: Header `x-apisports-key: {key}`，key 从 env `API_SPORTS_KEY`
**Base URL**: `https://v3.football.api-sports.io`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| fixtures | /fixtures | date, league, season, team, fixture_id |
| fixture_stats | /fixtures/statistics | fixture_id |
| lineups | /fixtures/lineups | fixture_id |
| teams | /teams | league, season, team_id |
| standings | /standings | league, season |
| players | /players | id, team, season, search |
| leagues | /leagues | id, name, country |
| injuries | /injuries | fixture_id, league, season |
| predictions | /predictions | fixture_id |
| venues | /venues | id, name, city |
| coaches | /coaches | id, team, search |

**Python**:
```python
import requests
headers = {"x-apisports-key": "{key}"}
r = requests.get("https://v3.football.api-sports.io/fixtures?date=2026-05-28&league=39&season=2025", headers=headers)
```

---

## 2. apifootball (API-Football v3 via RapidAPI)

**认证**: Header `X-RapidAPI-Key: {key}` + `X-RapidAPI-Host: api-football-v1.p.rapidapi.com`
**Base URL**: `https://api-football-v1.p.rapidapi.com/v3`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| fixtures | /fixtures | date, league, season, team, fixture_id |
| fixture_stats | /fixtures/statistics | fixture_id |
| lineups | /fixtures/lineups | fixture_id |
| teams | /teams | league, season, id |
| standings | /standings | league, season |
| players | /players | id, team, season, search |
| leagues | /leagues | id, name, country |
| injuries | /injuries | fixture_id, league, season |
| predictions | /predictions | fixture_id |
| odds | /odds | fixture, league, bookmaker |
| timezone | /timezone | — |

**Python**:
```python
headers = {"X-RapidAPI-Key": "{key}", "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
r = requests.get("https://api-football-v1.p.rapidapi.com/v3/fixtures?date=2026-05-28", headers=headers)
```

---

## 3. odds_feed_api (Odds Feed — 3个入口)

**详见 [[odds-feed-api]] 和 [[odds-feed-team-ids]]**

| 入口 | Base URL | 认证 |
|------|----------|------|
| RapidAPI(新) | `https://odds-feed.p.rapidapi.com` | `x-rapidapi-key` + `x-rapidapi-host` |
| RapidAPI(旧) | 同上 | 同上（配额独立） |
| HugeAPI/Portal | `https://odds-feed-api.hgapi.top` | `x-portal-apikey` |

---

## 4. the_odds_api (The Odds API v4)

**认证**: Query param `apiKey={key}`，key 从 env `THE_ODDS_API_KEY`
**Base URL**: `https://api.the-odds-api.com/v4`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| sports | /sports | — |
| odds | /sports/{sport_key}/odds | regions, markets |
| scores | /sports/{sport_key}/scores | daysFrom |
| events | /sports/{sport_key}/events | — |
| event_odds | /sports/{sport_key}/events/{event_id}/odds | regions, markets |

**SPORT_KEYS**:
| 名 | key | 名 | key |
|----|-----|----|-----|
| EPL | soccer_epl | La Liga | soccer_spain_la_liga |
| Bundesliga | soccer_germany_bundesliga | Serie A | soccer_italy_serie_a |
| Ligue 1 | soccer_france_ligue_one | CL | soccer_champions_league |
| EL | soccer_europa_league | World Cup | soccer_world_cup |

**REGIONS**: us, us2, uk, au, eu
**MARKETS**: h2h, spreads, totals, outrights

**Python**:
```python
r = requests.get("https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?apiKey={key}&regions=uk&markets=h2h")
```

---

## 5. odds_api (The Odds API — 同源，env不同)

与 the_odds_api 相同上游，env var 为 `ODDS_API_KEY`，端点略少（无 event_odds）。

---

## 6. football_data_org (football-data.org v4)

**认证**: Header `X-Auth-Token: {key}`，key 从 env `FOOTBALL_DATA_ORG_KEY`
**Base URL**: `https://api.football-data.org/v4`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| competitions | /competitions | — |
| matches | /matches | date, competition, status |
| comp_matches | /competitions/{comp}/matches | dateFrom, dateTo, matchday |
| standings | /competitions/{comp}/standings | — |
| scorers | /competitions/{comp}/scorers | — |
| teams | /teams/{id} | — |
| person | /persons/{id} | — |

**COMPETITIONS**:
| 名 | code | 名 | code |
|----|------|----|------|
| PL | 2021 | La Liga | 2014 |
| Bundesliga | 2002 | Serie A | 2019 |
| Ligue 1 | 2015 | CL | 2001 |
| EL | 2016 | WC | 2000 |
| EC | 2018 | Eredivisie | 2003 |
| Primeira Liga | 2017 | Serie A(BRA) | 2013 |
| Copa Libertadores | 2004 |

**Python**:
```python
headers = {"X-Auth-Token": "{key}"}
r = requests.get("https://api.football-data.org/v4/competitions/2021/matches?dateFrom=2026-05-28&dateTo=2026-05-29", headers=headers)
```

---

## 7. espn (ESPN Public API — 无需key)

**Base URL**: `https://site.api.espn.com/apis/site/v2/sports/soccer`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| scoreboard | /scoreboard | league, date |
| summary | /summary | event_id |
| standings | /standings | league |

**LEAGUE_IDS**:
| 名 | slug | 名 | slug |
|----|------|----|------|
| EPL | eng.1 | La Liga | esp.1 |
| Bundesliga | ger.1 | Serie A | ita.1 |
| Ligue 1 | fra.1 | CL | uefa.champions |
| EL | uefa.europa | WC | fifa.world |
| CONCACAF CL | concacaf.champions | Eredivisie | ned.1 |
| Primeira Liga | por.1 | | |

**Python**:
```python
r = requests.get("https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard")
```

---

## 8. premierleague (PL PulseLive API — 无需key)

**Base URL**: `https://footballapi.pulselive.com`
**Headers**: `Origin: https://www.premierleague.com`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| fixtures | /football/fixtures | matchday, comp=274, season=578 |
| standings | /football/standings | comp, season |
| teams | /football/teams | — |
| player | /football/players/{id} | — |
| match_detail | /football/fixtures/{id} | — |

**COMPETITION_ID**: 274, **SEASON_ID**: 578

**Python**:
```python
headers = {"Origin": "https://www.premierleague.com"}
r = requests.get("https://footballapi.pulselive.com/football/fixtures?comp=274&season=578", headers=headers)
```

---

## 9. sofascore (SofaScore API — 无需key)

**Base URL**: `https://api.sofascore.com/api/v1`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| live | /sport/football/events/live | — |
| event | /event/{event_id} | — |
| event_stats | /event/{event_id}/statistics | — |
| lineups | /event/{event_id}/lineups | — |
| team | /team/{team_id} | — |
| player | /player/{player_id} | — |

**Python**:
```python
r = requests.get("https://api.sofascore.com/api/v1/sport/football/events/live")
```

---

## 10. sportmonks (SportMonks v3)

**认证**: Query param `api_token={key}`，key 从 env `SPORTMONKS_KEY`
**Base URL**: `https://api.sportmonks.com/v3/football`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| fixtures | /fixtures/ | date, league, season, team |
| fixture_detail | /fixtures/{id} | — |
| teams | /teams/ | league, season |
| team_detail | /teams/{id} | — |
| standings | /standings/seasons/{season_id} | — |
| leagues | /leagues/ | — |
| players | /players/ | search, country |
| player_detail | /players/{id} | — |
| odds | /odds/ | fixture_id, league, bookmaker |
| odds_fixture | /odds/fixtures/{fixture_id} | — |
| bookmakers | /bookmakers/ | — |

**Python**:
```python
r = requests.get("https://api.sportmonks.com/v3/football/fixtures/?api_token={key}&date=2026-05-28")
```

---

## 11. flashlive (FlashLive via RapidAPI)

**认证**: Header `X-RapidAPI-Key: {key}` + `X-RapidAPI-Host: flashlive-sports.p.rapidapi.com`
**Base URL**: `https://flashlive-sports.p.rapidapi.com/v1`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| live_list | /events/live-list | sport_id=1 |
| event_detail | /events/detail | event_id |
| event_statistics | /events/statistics | event_id |
| event_lineups | /events/lineups | event_id |
| search | /search/events | query |

---

## 12. scores365 (Scores365 via RapidAPI)

**认证**: Header `X-RapidAPI-Key: {key}` + `X-RapidAPI-Host: scores365.p.rapidapi.com`
**Base URL**: `https://scores365.p.rapidapi.com/v1`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| live | /events/live | sport_id=1 |
| event_detail | /events/detail | event_id |
| event_stats | /events/statistics | event_id |
| event_lineups | /events/lineups | event_id |

---

## 13. thesportsdb (TheSportsDB — 免费key=3)

**认证**: URL路径含key，免费key=`3`
**Base URL**: `https://www.thesportsdb.com/api/v1/json/{key}`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| search_teams | /searchteams.php | t |
| search_events | /searchevents.php | e |
| event_detail | /lookupevent.php | id |
| team_detail | /lookupteam.php | id |
| player_detail | /lookupplayer.php | id |
| past_events | /eventspastleague.php | id |
| next_events | /eventsnextleague.php | id |
| league_detail | /lookupleague.php | id |
| live_scores | /latestscore.php | (patron only) |

**Python**:
```python
r = requests.get("https://www.thesportsdb.com/api/v1/json/3/eventspastleague.php?id=4328")
```

---

## 14. openligadb (OpenLigaDB — 免费无需key)

**Base URL**: `https://api.openligadb.de`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| matchday | /getmatchdata/{league}/{season}/{matchday} | — |
| current_matchday | /getcurrentgroup/{league} | — |
| match | /getmatchdata/{match_id} | — |
| teams | /getavailableteams/{league}/{season} | — |
| bl_table | /getbltable/{league}/{season} | — |

**LEAGUE_SHORTCUTS**: bl1, bl2, bl3, dfb, cl, el

---

## 15. dongqiudi (懂球帝 API)

**Base URL**: `https://m.dongqiudi.com` / API: `https://api.dongqiudi.com`
**Headers**: 移动端 User-Agent

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| news | /news/list | page |
| news_detail | /news/{id} | — |
| team_news | /team/{team_id}/news | — |
| team_info | /team/{team_id} | — |
| player_info | /player/{player_id} | — |
| match_detail | /match/{match_id} | — |

**TEAM_ID_MAP**:
| 队名 | ID | 队名 | ID |
|------|----|------|----|
| Man City | 529 | Man Utd | 33 |
| Liverpool | 44 | Chelsea | 49 |
| Arsenal | 42 | Tottenham | 47 |
| Barcelona | 83 | Real Madrid | 86 |
| Atletico | 530 | Bayern | 2 |
| Dortmund | 4 | Juventus | 496 |
| Inter | 505 | Milan | 489 |
| PSG | 85 | | |

---

## 16. sporttery (体彩 — 中国体彩网)

**API Base**: `https://i.sporttery.cn`
**Headers**: 浏览器UA + 中文

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| match_list | /api/fb_match_info/get_pool_list | date |
| match_detail | /api/fb_match_info/get_match_info | match_id |
| odds | /api/fb_match_info/get_odds_info | match_id, pool_type |

**POOL_TYPES**: had(胜平负), crs(比分), ttg(总进球), haf(半场), ahc(亚盘)

---

## 17. news (NewsAPI.org)

**认证**: Header `X-Api-Key: {key}`，key 从 env `NEWS_API_KEY`
**Base URL**: `https://newsapi.org/v2`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| everything | /everything | q, language, page, pageSize |
| top_headlines | /top-headlines | country, category |
| sources | /sources | category |

**FOOTBALL_KEYWORDS**: football, soccer, Premier League, Champions League, World Cup, La Liga, Serie A, Bundesliga, Ligue 1

---

## 18. deepseek (DeepSeek AI Chat)

**认证**: Header `Authorization: Bearer {key}`，key 从 env `DEEPSEEK_API_KEY`
**Base URL**: `https://api.deepseek.com`
**MODEL**: deepseek-chat

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| chat | /chat/completions | model, messages, temperature, max_tokens |

---

## 19. search_api (Contextual Web Search via RapidAPI)

**认证**: Header `X-RapidAPI-Key: {key}`
**Base URL**: `https://contextualwebsearch-websearch-v1.p.rapidapi.com/api/Search`

| 端点 | 路径 | 关键参数 |
|------|------|----------|
| web_search | /WebSearchAPI | q, PageNumber, PageSize |
| news_search | /NewsSearchAPI | q, PageNumber, PageSize |
| image_search | /ImageSearchAPI | q, PageNumber, PageSize |
