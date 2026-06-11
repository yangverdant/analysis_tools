# 全部Fetcher返回字段对照表

> 生成时间: 2026-05-25
> 目的: 展示所有fetcher返回数据的字段差异，明确common/串联层要解决的问题

---

## 一、比赛结果/赛程类 (需要 date + home_team + away_team + league 串联)

| Fetcher | 函数 | date字段 | home_team字段 | away_team字段 | league字段 | score字段 | 返回类型 |
|---------|------|---------|--------------|--------------|-----------|----------|---------|
| apifootball | get_livescores | `match_date` | `match_hometeam_name` | `match_awayteam_name` | `league_name` + `league_id` + `league_standard` | `match_hometeam_score` / `match_awayteam_score` | List[Dict] |
| apifootball | get_fixtures | `match_date` | `match_hometeam_name` | `match_awayteam_name` | `league_name` + `league_id` + `league_standard` | — | List[Dict] |
| apifootball | get_match_detail | `match_date` | `match_hometeam_name` | `match_awayteam_name` | `league_name` + `league_id` + `league_standard` | `match_hometeam_score` / `match_awayteam_score` | Dict |
| football_data_org | get_matches | `utcDate` | `homeTeam` (嵌套dict) | `awayTeam` (嵌套dict) | `competition` (嵌套dict) | `score` (嵌套dict) | List[Dict] |
| espn | get_livescores | `date` (today) | `home_team` | `away_team` | — | `home_score` / `away_score` | List[Dict] |
| soccerway | get_matches | — | `home_team` | `away_team` | `league` + `league_standard` | `home_score` / `away_score` | List[Dict] |
| scores365 | get_livescores | `startTime` (timestamp) | `homeCompetitor` / `homeTeam` | `awayCompetitor` / `awayTeam` | `competitionName` / `competitionId` | `homeScore` / `awayScore` | List[Dict] |
| flashlive | get_livescores | `startTime` (timestamp) | `homeTeam` (嵌套dict) | `awayTeam` (嵌套dict) | `tournament` (嵌套dict) | `homeScore` / `awayScore` | List[Dict] |
| sofascore | get_livescores | `startTimestamp` (timestamp) | `homeTeam` (嵌套dict) | `awayTeam` (嵌套dict) | `tournament` (嵌套dict) | `homeScore` / `awayScore` | List[Dict] |
| thesportsdb | get_events | `dateEvent` | `strHomeTeam` | `strAwayTeam` | `strLeague` + `idLeague` | `intHomeScore` / `intAwayScore` | List[Dict] |
| openligadb | get_matches | `matchDateTime` | `team1` (嵌套dict) | `team2` (嵌套dict) | `league` (嵌套dict) | `matchResults` (list) | List[Dict] |
| api_sports | get_fixtures | `fixture.date` (嵌套) | `teams.home.name` (嵌套) | `teams.away.name` (嵌套) | `league.name` (嵌套) | `goals.home` / `goals.away` (嵌套) | List[Dict] |
| fbref | get_match_results | `date` | `home_team` | `away_team` | `league` | `home_goals` / `away_goals` | List[Dict] |

### 串联问题总结:
- **date字段名**: 7种不同 (`match_date`, `utcDate`, `date`, `startTime`, `startTimestamp`, `dateEvent`, `matchDateTime`)
- **date格式**: ISO时间戳 / 纯日期 / Unix timestamp — 3种格式
- **home_team字段**: 7种不同，有的嵌套dict有的扁平
- **league字段**: 6种不同，有的嵌套dict，有的只有名字没有ID
- **缺少date**: soccerway完全没有
- **缺少league**: espn完全没有
- **score字段**: 5种不同命名

---

## 二、赔率类 (需要 date + home_team + away_team 串联)

| Fetcher | 函数 | date | home_team | away_team | league | odds格式 | 返回类型 |
|---------|------|------|-----------|-----------|--------|---------|---------|
| the_odds_api | get_odds | `commence_time` + `date` | `home_team` | `away_team` | `sport_key` + `league` | 嵌套: `odds[].bookmaker[].markets[].outcomes[]` | List[Dict] |
| okooo | get_match_basic | `date` | `home_team` + `home_team_standard` | `away_team` + `away_team_standard` | `league` | — (只有基本信息) | Dict |
| okooo | get_odds_change | — | — | — | — | 扁平: `h`(小时), `odds_home/draw/away` | List[Dict] |
| okooo | get_ah_change | — | — | — | — | 扁平: `h`, `ah_home/away`, `handicap` | List[Dict] |
| okooo | get_ou_change | — | — | — | — | 扁平: `h`, `over/under`, `line` | List[Dict] |
| okooo | get_full_odds_matrix | — | — | — | — | 嵌套: `odds{company{opening/closing}}` | Dict |
| sporttery | get_selling_matches | `match_date`(中文格式) | `home_team_cn` | `away_team_cn` | `league_cn` | `sp_home/draw/away` | List[Dict] |
| odds_api | get_odds_feed | `date` | `home_team` | `away_team` | `league` | 扁平: `odds_home/draw/away` | List[Dict] |
| odds_api | get_bet365_odds | — | — | — | — | raw data | List[Dict] |
| odds_api | get_fb_odds | — | — | — | — | raw data | List[Dict] |

### 串联问题总结:
- okooo的change函数只有`match_id`+`company_id`回写，没有home/away/team
- sporttery用中文队名和中文日期
- bet365/fb_odds完全无法串联(返回raw data)
- the_odds_api的odds嵌套太深，无法直接使用

---

## 三、xG/预测类 (需要 date + home_team + away_team 串联)

| Fetcher | 函数 | date | home_team | away_team | league | xG字段 | 返回类型 |
|---------|------|------|-----------|-----------|--------|--------|---------|
| understat | get_match_xg | — | `home_team` | `away_team` | — | `home_xg` / `away_xg` | Dict |
| understat | get_league_players_xg | — | `team` | — | `league` | `xg` / `xa` / `npxg` | List[Dict] |
| understat | get_league_teams_xg | — | `team` | — | `league` | `xg` / `xga` / `npxg` / `npxga` | List[Dict] |
| statsbomb | get_match_xg | `match_date` | `home_team` | `away_team` | `competition` | `home_xg` / `away_xg` | Dict |
| sportmonks | get_predictions | — | — | — | — | raw data | Dict |
| apifootball | get_predictions | `date` | `home_team` | `away_team` | `league` + `league_standard` | `home_win_prob` / `over_2_5_prob` | Dict |

### 串联问题总结:
- understat get_match_xg缺少date和league
- sportmonks predictions完全无法串联
- 各源xG字段名不同

---

## 四、阵容/伤病类

| Fetcher | 函数 | date | team | league | 核心字段 | 返回类型 |
|---------|------|------|------|--------|---------|---------|
| bifen188 | get_predicted_lineups | — | — | — | `home_lineup[]` / `away_lineup[]` | Dict |
| sportmonks | get_lineups | — | — | — | raw data | Dict |
| premierleague | get_injuries | — | `team` + `team_standard` | `league`(固定Premier League) | `player_name` / `status` / `reason` | List[Dict] |
| api_sports | get_injuries | 嵌套 | 嵌套 | 嵌套 | raw API data | List[Dict] |

### 串联问题总结:
- bifen188有home/away lineup但缺date和team名
- 伤病缺date，无法判断哪场比赛受影响
- api_sports返回raw嵌套数据

---

## 五、新闻/视频类 (需要 team + date 串联)

| Fetcher | 函数 | date | team | title | url | 返回类型 |
|---------|------|------|------|-------|-----|---------|
| dongqiudi | get_news | `date`(today) | — | `title` | `url` | List[Dict] |
| dongqiudi | get_team_news | — | — | `title` | `url` | List[Dict] |
| hupu | get_news | `date`(today) | — | `title` | `url` | List[Dict] |
| zhibo8 | get_news | `date` | — | `title` | `url` | List[Dict] |
| scorebat | get_highlights | — | `home_team` / `away_team` | `title` | `url` + `video_url` | List[Dict] |

### 串联问题总结:
- 新闻全靠标题里的队名匹配，没有结构化的team字段
- 缺date: dongqiudi get_team_news, scorebat

---

## 六、天气类 (需要 date + home_team/city 串联)

| Fetcher | 函数 | date | city/team | 核心字段 | 返回类型 |
|---------|------|------|-----------|---------|---------|
| weather | get_match_weather | `date` | `city` + `home_team` + `city_input` | `temp_c` / `humidity` / `wind` / `precipitation` | Dict |
| openweathermap | get_current_weather | — | `city` + `city_input` + `country` | `temp_c` / `humidity` / `description` | Dict |
| openweathermap | get_forecast | — | `city` + `city_input` | `datetime` / `temp_c` / `humidity` | List[Dict] |
| openweathermap | get_air_quality | — | `lat` / `lon` | `aqi` / `pm2_5` / `pm10` | Dict |

### 串联问题总结:
- openweathermap缺date字段
- air_quality用经纬度，无法直接和球队关联

---

## 七、积分榜/球员/身价类

| Fetcher | 函数 | league | team | 核心字段 | 返回类型 |
|---------|------|--------|------|---------|---------|
| apifootball | get_standings | `league_name` + `league_standard` | `team_name` | `rank` / `points` / `played` / `win/draw/lose` | List[Dict] |
| football_data_org | get_standings | 嵌套 | 嵌套 | raw API data | Dict |
| fbref | get_league_standings | `league` | `team` | `rank` / `points` / `goal_diff` | List[Dict] |
| transfermarkt | get_squad | — | (从url推断) | `name` / `position` / `number` / `market_value` | Dict |
| transfermarkt | get_player_value | — | — | `player_name` / `market_value` / `club` | Dict |
| transfermarkt | get_league_valuations | — | — | raw data | Dict |
| thesportsdb | get_players | — | `strTeam` | `strPlayer` / `strPosition` / `strThumb` | List[Dict] |

---

## 八、核心串联问题归纳

### 问题1: 字段名不统一 (同一含义，7种命名)

| 含义 | 字段名变体 |
|------|-----------|
| 日期 | `match_date`, `utcDate`, `date`, `startTime`, `startTimestamp`, `dateEvent`, `matchDateTime` |
| 主队 | `home_team`, `match_hometeam_name`, `strHomeTeam`, `homeTeam`(嵌套), `homeCompetitor`, `home_team_cn` |
| 客队 | `away_team`, `match_awayteam_name`, `strAwayTeam`, `awayTeam`(嵌套), `awayCompetitor`, `away_team_cn` |
| 联赛 | `league`, `league_name`, `competition`(嵌套), `tournament`(嵌套), `strLeague`, `sport_key` |
| 主队得分 | `home_score`, `match_hometeam_score`, `intHomeScore`, `homeScore`, `goals.home`, `home_goals` |

### 问题2: 数据结构不统一

| 类型 | 出现频率 | 示例 |
|------|---------|------|
| 扁平dict | 最多 | `{"home_team": "Arsenal", "away_team": "Chelsea"}` |
| 嵌套dict | football_data_org, api_sports, sofascore | `{"teams": {"home": {"name": "Arsenal"}}}` |
| 深层嵌套 | the_odds_api | `{"bookmakers": [{"markets": [{"outcomes": [...]}]}]}` |
| raw API data | sportmonks, odds_api(bet365/fb) | 无法使用 |

### 问题3: 串联字段缺失 (有多少fetcher缺关键字段)

| 字段 | 缺失的fetcher数量 | 最严重的 |
|------|-----------------|---------|
| date | 7个函数缺 | soccerway, okooo change, understat match_xg, scorebat |
| home_team | 5个函数缺 | okooo change, bifen188, sportmonks, scores365(字段名不同) |
| away_team | 5个函数缺 | 同上 |
| league | 6个函数缺 | espn, bifen188, understat, the_odds_api(需映射) |
| team (伤病/新闻) | 4个函数缺 | 新闻全靠标题匹配 |

### 问题4: 格式不统一

| 类型 | 变体 |
|------|------|
| 队名语言 | 英文 / 中文 / 德文 / 混合 |
| 队名格式 | "Arsenal" / "Arsenal FC" / "阿森纳" / "枪手" |
| 日期格式 | "2026-05-25" / "2026-05-25T15:00:00Z" / timestamp / "25/05/2026" / "2026年5月25日" |
| 联赛ID | apifootball=152 / football_data_org="PL" / the_odds_api="soccer_epl" / sportmonks=8 |
