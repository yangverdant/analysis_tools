---
name: fetcher-scrape-sources
description: 所有Scrape类fetcher的抓取方式、URL结构、CSS选择器、ID映射完整记录（11个）
metadata: 
  node_type: memory
  type: reference
  originSessionId: a3325eab-87ac-48a6-8496-2ff45be69cae
---

# Scrape 类 Fetcher 调用方式与 ID 映射

## 1. fbref (FBRef — statsbycoords)

**Base URL**: `https://fbref.com`
**方式**: requests + BeautifulSoup

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 联赛赛程 | /comps/{comp_id}/schedule/Schedule | comp_id对应联赛 |
| 球队赛程 | /squads/{team_id}/Schedule | team_id对应球队 |
| 球员页面 | /players/{player_id}/Player-Name | player_id是唯一标识 |
| 比赛报告 | /matches/{match_id}/Match-Report | match_id格式: {date}-{home}-vs-{away} |
| 联赛积分 | /comps/{comp_id}/{season}/stats | 如 /comps/9/2024-2025/stats |

**COMP_IDS**:
| 联赛 | comp_id | 联赛 | comp_id |
|------|---------|------|---------|
| Big 5合并 | 9 | EPL | 9(Big5合并) |
| La Liga | 12 | Bundesliga | 20 |
| Serie A | 11 | Ligue 1 | 13 |
| CL | 8 | EL | 19 |
| WC | - | | |

**注意**: FBRef有反爬，需设User-Agent，单次请求间隔>3秒

---

## 2. transfermarkt (Transfermarkt)

**Base URL**: `https://www.transfermarkt.com`
**方式**: requests + BeautifulSoup，需设置浏览器UA

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 球队页面 | /{team_name}/startseite/verein/{team_id} | team_id数字 |
| 球员页面 | /{player_name}/profil/spieler/{player_id} | player_id数字 |
| 赛事页面 | /{match_name}/index/spielbericht/{match_id} | match_id数字 |
| 联赛页面 | /{league_name}/startseite/wettbewerb/{league_id} | league_id如L1,GB1 |
| 球员身价 | /{player_name}/marktwert/spieler/{player_id} | — |

**LEAGUE_IDS**:
| 联赛 | id | 联赛 | id |
|------|---|------|---|
| EPL | GB1 | La Liga | ES1 |
| Bundesliga | L1 | Serie A | IT1 |
| Ligue 1 | FR1 | CL | CL |
| EL | EL | | |

---

## 3. understat (Understat — xG数据)

**Base URL**: `https://understat.com`
**方式**: requests + 正则提取JSON（数据在JS变量里，需decode）

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 联赛 | /league/{league_name}/{season} | — |
| 球队 | /team/{team_name}/{season} | — |
| 球员 | /player/{player_id} | player_id数字 |

**LEAGUE_SLUGS**:
| 联赛 | slug | 联赛 | slug |
|------|------|------|------|
| EPL | EPL | La Liga | La_liga |
| Bundesliga | Bundesliga | Serie A | Serie_A |
| Ligue 1 | Ligue_1 | | |

**关键**: 数据在 `<script>` 标签里，格式为 `var datesData = JSON.parse(unescape('...'))`，需 base64 decode + aes_decrypt

---

## 4. who_scored (WhoScored)

**Base URL**: `https://www.whoscored.com`
**方式**: requests + BeautifulSoup，需浏览器UA + cookie

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 联赛赛程 | /Regions/{region_id}/Tournaments/{tourn_id}/Seasons/{season_id} | 三级ID |
| 球队 | /Teams/{team_id} | — |
| 球员 | /Players/{player_id} | — |
| 比赛 | /Matches/{match_id}/Live | match_id数字 |

**注意**: WhoScored反爬严格，频繁请求会封IP

---

## 5. soccerway (Soccerway)

**Base URL**: `https://int.soccerway.com`
**方式**: requests + BeautifulSoup

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 联赛 | /matches/{date}/ | 按日期查 |
| 球队 | /teams/{team_slug}/{team_id}/ | — |
| 球员 | /players/{player_slug}/{player_id}/ | — |
| 比赛 | /matches/{match_id}/ | — |

---

## 6. fotmob (FotMob — 网页版)

**Base URL**: `https://www.fotmob.com`
**API**: `https://www.fotmob.com/api`

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 联赛 | /leagues/{league_id}/overview | — |
| 比赛 | /matches/{match_id} | — |
| 球队 | /teams/{team_id} | — |
| 球员 | /players/{player_id} | — |

**API端点**:
| 端点 | 路径 | 参数 |
|------|------|------|
| matchDetail | /api/matchDetail | matchId |
| leagueTable | /api/leagueTable | league, season |
| teamDetail | /api/teamDetail | teamId |

---

## 7. worldfootball (WorldFootball.net)

**Base URL**: `https://www.worldfootball.net`
**方式**: requests + BeautifulSoup

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 联赛 | /schedule/{league_slug}-{season}/ | — |
| 比赛 | /report/{match_slug}/ | — |
| 球队 | /teams/{team_slug}/ | — |

---

## 8. besoccer (BeSoccer)

**Base URL**: `https://www.besoccer.com`
**API**: `https://apibeta.besoccer.com/api/v3`
**认证**: Query param `page={key}`

| 端点 | URL模板 | 关键参数 |
|------|---------|----------|
| live | /api/v3/live | key |
| match | /api/v3/match/{match_id} | key |
| team | /api/v3/team/{team_id} | key |
| standings | /api/v3/standings/{league_id} | key |

---

## 9. ai_score (AI Score)

**Base URL**: `https://www.ai-score.com` / `https://api.ai-score.com`
**方式**: requests

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 赛事列表 | /api/v1/events | date |
| 赛事详情 | /api/v1/events/{event_id} | — |
| 比分 | /api/v1/scores | date |

---

## 10. zucai168 (买彩网/竞彩168)

**Base URL**: `https://www.zucai168.com` / `https://m.zucai168.com`
**方式**: requests + BeautifulSoup

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 竞彩赛程 | /jcsp/ | 竞彩足球赛事 |
| 赛事详情 | /match/{match_id}/ | — |
| 赔率 | /odds/{match_id}/ | 亚盘欧赔 |

**注意**: 中文站点，数据含亚盘/大小球

---

## 11. zqzq (足球之家)

**Base URL**: `https://www.zqzq.com`
**方式**: requests + BeautifulSoup

| 端点 | URL模板 | 说明 |
|------|---------|------|
| 赛程 | /match/list/ | 按日期 |
| 赛事 | /match/{match_id}/ | — |
| 联赛 | /league/{league_id}/ | — |

**注意**: 中文站点，含中超数据
