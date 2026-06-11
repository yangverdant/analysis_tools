# 完整字段映射文档

## 一、数据流总览

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              数据流转全景图                                          │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  数据源      │    │ EntityMapper │    │    DAO       │    │  Database    │
│  (API/爬虫)  │───▶│  字段映射     │───▶│  数据访问     │───▶│  数据库表     │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
     │                    │                    │                    │
     │ 源字段             │ 标准字段           │ 表字段             │ 列名
     │ matchId            │ lottery_match_id   │ lottery_match_id   │ lottery_match_id
     │ homeTeam           │ home_team_cn       │ home_team_cn       │ home_team_cn
     │ ...                │ ...                │ ...                │ ...

示例: 体彩数据流
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 体彩官网API                                                                          │
│ {                                                                                    │
│   "matchId": "20260524001",                                                          │
│   "matchNum": "001",                                                                 │
│   "homeTeam": "曼联",                                                                │
│   "awayTeam": "利物浦",                                                              │
│   "matchDate": "2026-05-24",                                                         │
│   "matchTime": "22:00",                                                              │
│   "leagueName": "英超",                                                              │
│   "sellStatus": "on"                                                                 │
│ }                                                                                    │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ EntityMapper.map_to_standard('lottery', raw_data)
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 标准化数据                                                                           │
│ {                                                                                    │
│   "lottery_match_id": "20260524001",                                                 │
│   "match_num": "001",                                                                │
│   "home_team_cn": "曼联",                                                            │
│   "away_team_cn": "利物浦",                                                          │
│   "match_date": "2026-05-24",                                                        │
│   "match_time": "22:00",                                                             │
│   "league_name_cn": "英超",                                                          │
│   "sell_status": "selling",        ← 值转换: "on" → "selling"                        │
│   "_source": "lottery"                                                               │
│ }                                                                                    │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ LotteryMatchDAO.insert(match_data)
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ SQL语句                                                                              │
│ INSERT INTO lottery_matches (                                                        │
│   lottery_match_id, match_num, home_team_cn, away_team_cn,                          │
│   match_date, match_time, league_name_cn, sell_status                               │
│ ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)                                                    │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 数据库表: lottery_matches                                                            │
│ ┌──────────────────────┬──────────────────┬──────────────────┬──────────────────┐   │
│ │ lottery_match_id     │ match_num        │ home_team_cn     │ away_team_cn     │   │
│ ├──────────────────────┼──────────────────┼──────────────────┼──────────────────┤   │
│ │ 20260524001          │ 001              │ 曼联             │ 利物浦           │   │
│ └──────────────────────┴──────────────────┴──────────────────┴──────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、各数据源字段映射表

### 2.1 体彩官网 (Lottery) → lottery_matches 表

| 源字段 (API返回) | 标准字段 | 数据库表 | 数据库列 | 值转换 |
|-----------------|----------|----------|----------|--------|
| `matchId` | `lottery_match_id` | `lottery_matches` | `lottery_match_id` | 直接使用 |
| `matchNum` | `match_num` | `lottery_matches` | `match_num` | 直接使用 |
| `homeTeam` | `home_team_cn` | `lottery_matches` | `home_team_cn` | 直接使用 |
| `awayTeam` | `away_team_cn` | `lottery_matches` | `away_team_cn` | 直接使用 |
| `leagueName` | `league_name_cn` | `lottery_matches` | `league_name_cn` | 直接使用 |
| `matchDate` | `match_date` | `lottery_matches` | `match_date` | 截取前10位 |
| `matchTime` | `match_time` | `lottery_matches` | `match_time` | 截取时间部分 |
| `beijingTime` | `beijing_time` | `lottery_matches` | `beijing_time` | 直接使用 |
| `sellStatus` | `sell_status` | `lottery_matches` | `sell_status` | `"on"→"selling"`, `"off"→"stopped"` |
| `sellEndTime` | `sell_end_time` | `lottery_matches` | `sell_end_time` | 直接使用 |
| `handicapLine` | `handicap_line` | `lottery_matches` | `handicap_line` | 转float |
| `playTypes[]` | `play_types` | `lottery_matches` | `play_types` | JSON序列化 |

**代码实现:**
```python
# entity_mapper.py
FIELD_MAPPINGS['lottery'] = {
    'matchId': 'lottery_match_id',
    'matchNum': 'match_num',
    'homeTeam': 'home_team_cn',
    'awayTeam': 'away_team_cn',
    'leagueName': 'league_name_cn',
    'matchDate': 'match_date',
    'matchTime': 'match_time',
    'beijingTime': 'beijing_time',
    'sellStatus': 'sell_status',
    'sellEndTime': 'sell_end_time',
    'handicapLine': 'handicap_line',
}

VALUE_CONVERTERS = {
    'match_date': lambda v: v[:10] if v else None,
    'sell_status': lambda v: {'on': 'selling', 'off': 'stopped'}.get(v, v),
}
```

---

### 2.2 Sportmonks API → matches 表

| 源字段 (API返回) | 标准字段 | 数据库表 | 数据库列 | 说明 |
|-----------------|----------|----------|----------|------|
| `id` | `match_id` | `matches` | `match_id` | Sportmonks fixture ID |
| `starting_at` | `match_datetime` | `matches` | `match_time` | UTC时间 |
| `league_id` | `league_id` | `matches` | `league_id` | 联赛ID |
| `season_id` | `season_id` | `matches` | `season_id` | 赛季ID |
| `round.name` | `round_name` | `matches` | `round` | 轮次名 |
| `state_id` | `status` | `matches` | `status` | 比赛状态 |
| `venue_id` | `venue_id` | `matches` | `venue_id` | 场馆ID |
| `referee.id` | `referee_id` | `matches` | `referee_id` | 裁判ID |
| `participants[0]` | `home_team_id` | `matches` | `home_team_id` | 主队 (meta.location=home) |
| `participants[1]` | `away_team_id` | `matches` | `away_team_id` | 客队 (meta.location=away) |

**scores 子对象:**
| 源字段 | 标准字段 | 数据库列 | 说明 |
|--------|----------|----------|------|
| `scores[0].home_score` | `home_goals_ht` | `home_goals_ht` | 半场主队进球 |
| `scores[0].away_score` | `away_goals_ht` | `away_goals_ht` | 半场客队进球 |
| `scores[1].home_score` | `home_goals_ft` | `home_goals` | 全场主队进球 |
| `scores[1].away_score` | `away_goals_ft` | `away_goals` | 全场客队进球 |

**代码实现:**
```python
FIELD_MAPPINGS['sportmonks'] = {
    'id': 'match_id',
    'starting_at': 'match_datetime',
    'league_id': 'league_id',
    'season_id': 'season_id',
    'round.name': 'round_name',
    'state_id': 'status',
    'venue_id': 'venue_id',
    'referee.id': 'referee_id',
    # participants特殊处理
    'participants': '_participants_special',
}

# 特殊处理participants
def _handle_special_mapping(source_name, path, data):
    result = {}
    if source_name == 'sportmonks' and path == 'participants':
        participants = data.get('participants', [])
        for p in participants:
            if p.get('meta', {}).get('location') == 'home':
                result['home_team_id'] = p.get('id')
                result['home_team_name'] = p.get('name')
            elif p.get('meta', {}).get('location') == 'away':
                result['away_team_id'] = p.get('id')
                result['away_team_name'] = p.get('name')
    return result
```

---

### 2.3 API-Football → matches 表

| 源字段 (API返回) | 标准字段 | 数据库表 | 数据库列 | 说明 |
|-----------------|----------|----------|----------|------|
| `fixture.id` | `match_id` | `matches` | `match_id` | API-Football fixture ID |
| `fixture.date` | `match_date` | `matches` | `match_date` | 日期 (YYYY-MM-DD) |
| `fixture.time` | `match_time` | `matches` | `match_time` | 时间 (HH:MM) |
| `fixture.status.short` | `status` | `matches` | `status` | 状态码 |
| `league.id` | `league_id` | `matches` | `league_id` | 联赛ID |
| `league.name` | `league_name` | `matches` | `league_name` | 联赛名 |
| `teams.home.id` | `home_team_id` | `matches` | `home_team_id` | 主队ID |
| `teams.home.name` | `home_team_name` | `matches` | `home_team_name` | 主队名 |
| `teams.away.id` | `away_team_id` | `matches` | `away_team_id` | 客队ID |
| `teams.away.name` | `away_team_name` | `matches` | `away_team_name` | 客队名 |
| `goals.home` | `home_goals` | `matches` | `home_goals` | 主队进球 |
| `goals.away` | `away_goals` | `matches` | `away_goals` | 客队进球 |
| `score.halftime.home` | `home_goals_ht` | `matches` | `home_goals_ht` | 半场主队进球 |
| `score.halftime.away` | `away_goals_ht` | `matches` | `away_goals_ht` | 半场客队进球 |

**代码实现:**
```python
FIELD_MAPPINGS['api_football'] = {
    'fixture.id': 'match_id',
    'fixture.date': 'match_date',
    'fixture.time': 'match_time',
    'fixture.status.short': 'status',
    'league.id': 'league_id',
    'league.name': 'league_name',
    'teams.home.id': 'home_team_id',
    'teams.home.name': 'home_team_name',
    'teams.away.id': 'away_team_id',
    'teams.away.name': 'away_team_name',
    'goals.home': 'home_goals',
    'goals.away': 'away_goals',
    'score.halftime.home': 'home_goals_ht',
    'score.halftime.away': 'away_goals_ht',
}
```

---

### 2.4 FBref 爬虫 → matches / team_stats 表

| 源字段 (爬虫解析) | 标准字段 | 数据库表 | 数据库列 | 说明 |
|-----------------|----------|----------|----------|------|
| `Date` | `match_date` | `matches` | `match_date` | 比赛日期 |
| `Time` | `match_time` | `matches` | `match_time` | 比赛时间 |
| `HomeTeam` | `home_team_name` | `matches` | `home_team_name` | 主队名 |
| `AwayTeam` | `away_team_name` | `matches` | `away_team_name` | 客队名 |
| `FTHG` | `home_goals` | `matches` | `home_goals` | 全场主队进球 |
| `FTAG` | `away_goals` | `matches` | `away_goals` | 全场客队进球 |
| `HTHG` | `home_goals_ht` | `matches` | `home_goals_ht` | 半场主队进球 |
| `HTAG` | `away_goals_ht` | `matches` | `away_goals_ht` | 半场客队进球 |
| `FTR` | `result` | `matches` | `result` | 结果 (H/D/A) |
| `Referee` | `referee_name` | `matches` | `referee_name` | 裁判名 |
| `HS` | `home_shots` | `match_stats` | `home_shots` | 主队射门 |
| `AS` | `away_shots` | `match_stats` | `away_shots` | 客队射门 |
| `HST` | `home_shots_on_target` | `match_stats` | `home_shots_on_target` | 主队射正 |
| `AST` | `away_shots_on_target` | `match_stats` | `away_shots_on_target` | 客队射正 |
| `HC` | `home_corners` | `match_stats` | `home_corners` | 主队角球 |
| `AC` | `away_corners` | `match_stats` | `away_corners` | 客队角球 |
| `HF` | `home_fouls` | `match_stats` | `home_fouls` | 主队犯规 |
| `AF` | `away_fouls` | `match_stats` | `away_fouls` | 客队犯规 |
| `HY` | `home_yellow_cards` | `match_stats` | `home_yellow_cards` | 主队黄牌 |
| `AY` | `away_yellow_cards` | `match_stats` | `away_yellow_cards` | 客队黄牌 |
| `HR` | `home_red_cards` | `match_stats` | `home_red_cards` | 主队红牌 |
| `AR` | `away_red_cards` | `match_stats` | `away_red_cards` | 客队红牌 |

**xG 数据:**
| 源字段 | 标准字段 | 数据库表 | 数据库列 |
|--------|----------|----------|----------|
| `home_xg` | `home_xg` | `match_xg` | `home_xg` |
| `away_xg` | `away_xg` | `match_xg` | `away_xg` |

**代码实现:**
```python
FIELD_MAPPINGS['fbref'] = {
    'Date': 'match_date',
    'Time': 'match_time',
    'HomeTeam': 'home_team_name',
    'AwayTeam': 'away_team_name',
    'FTHG': 'home_goals',
    'FTAG': 'away_goals',
    'HTHG': 'home_goals_ht',
    'HTAG': 'away_goals_ht',
    'FTR': 'result',
    'Referee': 'referee_name',
    'HS': 'home_shots',
    'AS': 'away_shots',
    'HST': 'home_shots_on_target',
    'AST': 'away_shots_on_target',
    'HC': 'home_corners',
    'AC': 'away_corners',
    'HF': 'home_fouls',
    'AF': 'away_fouls',
    'HY': 'home_yellow_cards',
    'AY': 'away_yellow_cards',
    'HR': 'home_red_cards',
    'AR': 'away_red_cards',
    'home_xg': 'home_xg',
    'away_xg': 'away_xg',
}
```

---

### 2.5 Football-Data.org → matches 表

| 源字段 (API返回) | 标准字段 | 数据库表 | 数据库列 | 说明 |
|-----------------|----------|----------|----------|------|
| `match.id` | `match_id` | `matches` | `match_id` | 比赛ID |
| `matchday` | `round` | `matches` | `round` | 轮次 |
| `utcDate` | `match_datetime` | `matches` | `match_time` | UTC时间 |
| `status` | `status` | `matches` | `status` | 状态 |
| `homeTeam.id` | `home_team_id` | `matches` | `home_team_id` | 主队ID |
| `homeTeam.shortName` | `home_team_name` | `matches` | `home_team_name` | 主队名 |
| `awayTeam.id` | `away_team_id` | `matches` | `away_team_id` | 客队ID |
| `awayTeam.shortName` | `away_team_name` | `matches` | `away_team_name` | 客队名 |
| `score.fullTime.home` | `home_goals` | `matches` | `home_goals` | 主队进球 |
| `score.fullTime.away` | `away_goals` | `matches` | `away_goals` | 客队进球 |
| `score.halfTime.home` | `home_goals_ht` | `matches` | `home_goals_ht` | 半场主队进球 |
| `score.halfTime.away` | `away_goals_ht` | `matches` | `away_goals_ht` | 半场客队进球 |
| `competition.code` | `league_id` | `matches` | `league_id` | 联赛代码 |

---

### 2.6 TheSportsDB → matches 表

| 源字段 (API返回) | 标准字段 | 数据库表 | 数据库列 |
|-----------------|----------|----------|----------|
| `idEvent` | `match_id` | `matches` | `match_id` |
| `strEvent` | `match_name` | `matches` | `match_name` |
| `dateEvent` | `match_date` | `matches` | `match_date` |
| `strTime` | `match_time` | `matches` | `match_time` |
| `idHomeTeam` | `home_team_id` | `matches` | `home_team_id` |
| `strHomeTeam` | `home_team_name` | `matches` | `home_team_name` |
| `idAwayTeam` | `away_team_id` | `matches` | `away_team_id` |
| `strAwayTeam` | `away_team_name` | `matches` | `away_team_name` |
| `intHomeScore` | `home_goals` | `matches` | `home_goals` |
| `intAwayScore` | `away_goals` | `matches` | `away_goals` |
| `idLeague` | `league_id` | `matches` | `league_id` |
| `strLeague` | `league_name` | `matches` | `league_name` |
| `strVenue` | `venue_name` | `matches` | `venue_name` |

---

## 三、球队名称映射

### 3.1 体彩名称 → 系统 team_id 映射

```
体彩名称        →  系统team_id  →  英文名                    →  数据库
"曼联"          →  585          →  "Manchester United"      →  teams.team_id=585
"利物浦"        →  561          →  "Liverpool"              →  teams.team_id=561
"阿森纳"        →  572          →  "Arsenal"                →  teams.team_id=572
"曼城"          →  584          →  "Manchester City"        →  teams.team_id=584
"切尔西"        →  575          →  "Chelsea"                →  teams.team_id=575
"热刺"          →  588          →  "Tottenham"              →  teams.team_id=588
"皇马"          →  86           →  "Real Madrid"            →  teams.team_id=86
"巴萨"          →  81           →  "Barcelona"              →  teams.team_id=81
```

### 3.2 映射流程

```python
# 1. 从 team_name_mapping 表加载映射
def _load_team_mappings(self):
    cursor.execute("SELECT lottery_name, team_id FROM team_name_mapping")
    for row in cursor.fetchall():
        self._team_name_cache[row[0]] = row[1]  # "曼联" → 585

# 2. 精确匹配
def get_team_id(self, lottery_name: str) -> Optional[int]:
    if lottery_name in self._team_name_cache:
        return self._team_name_cache[lottery_name]  # 直接返回
    # 3. 模糊匹配
    return self._fuzzy_match_team(lottery_name)

# 4. 模糊匹配算法
def _fuzzy_match_team(self, lottery_name: str) -> Optional[int]:
    for cached_name, team_id in self._team_name_cache.items():
        score = SequenceMatcher(None, lottery_name, cached_name).ratio()
        if score > 0.8:  # 相似度阈值
            return team_id
    return None
```

---

## 四、赔率数据映射

### 4.1 体彩赔率 → lottery_odds 表

| 源数据 | 玩法 | 数据库列 | JSON格式 |
|--------|------|----------|----------|
| `spfOdds` | SPF (胜平负) | `odds_data` | `{"3": 2.15, "1": 3.20, "0": 3.05}` |
| `bfOdds` | BF (比分) | `odds_data` | `{"10": 12.0, "20": 8.5, "21": 7.0, ...}` |
| `bqcOdds` | BQC (半全场) | `odds_data` | `{"33": 3.5, "31": 6.0, "30": 18.0, ...}` |
| `rqspfOdds` | RQSPF (让球胜平负) | `odds_data` | `{"3": 1.85, "1": 3.50, "0": 4.20}` |

**存储流程:**
```python
# 1. 获取原始赔率
raw_odds = {
    'spfOdds': {'3': 2.15, '1': 3.20, '0': 3.05},
    'bfOdds': {...},
    'bqcOdds': {...},
    'rqspfOdds': {...}
}

# 2. 写入 lottery_odds 表
for play_type, odds in raw_odds.items():
    lottery_odds_dao.insert({
        'lottery_match_id': '20260524001',
        'play_type': play_type.replace('Odds', ''),  # "spfOdds" → "spf"
        'odds_data': json.dumps(odds)
    })
```

---

## 五、多数据源优先级与合并

### 5.1 数据源优先级

| 数据类型 | 主数据源 | 备用数据源 | 说明 |
|----------|----------|------------|------|
| 实时比分 | sportmonks | thesportsdb, 365scores | Sportmonks最准确 |
| 赛程 | sportmonks | football_data_org | Sportmonks覆盖最全 |
| 积分榜 | football_data_org | sportmonks | football-data免费额度多 |
| 赔率 | apifootball | odds_feed | API-Football含赔率 |
| xG数据 | fbref | sportmonks | FBref有详细xG |
| 体彩数据 | lottery_crawler | - | 官网爬虫唯一来源 |

### 5.2 合并策略

```python
def merge_multi_source(self, sources_data: Dict[str, Dict]) -> Dict:
    """
    合并多数据源

    策略: 按优先级填充，已填充字段不覆盖
    """
    merged = {}
    filled_fields = set()

    # 优先级顺序
    source_priority = ['api_football', 'sportmonks', 'fbref', 'lottery']

    for source_name in source_priority:
        if source_name not in sources_data:
            continue

        data = sources_data[source_name]
        standardized = self.map_to_standard(source_name, data)

        for field, value in standardized.items():
            # 只填充未赋值的字段
            if field not in filled_fields and value is not None:
                merged[field] = value
                filled_fields.add(field)

    return merged
```

**示例:**
```python
# 多源数据
sources_data = {
    'sportmonks': {
        'id': 12345,
        'starting_at': '2026-05-24 22:00:00',
        'participants': [{'id': 585, 'name': 'Manchester United'}, ...]
    },
    'fbref': {
        'Date': '2026-05-24',
        'HomeTeam': 'Manchester United',
        'home_xg': 1.85,
        'away_xg': 0.92
    }
}

# 合并结果
merged = {
    'match_id': 12345,        # 来自sportmonks (优先级高)
    'match_datetime': '2026-05-24 22:00:00',  # 来自sportmonks
    'home_team_name': 'Manchester United',    # 来自sportmonks
    'home_xg': 1.85,          # 来自fbref (sportmonks无此字段)
    'away_xg': 0.92,          # 来自fbref
}
```

---

## 六、完整数据流示例

### 示例: 同步体彩比赛

```
1. 爬虫获取数据
   ┌─────────────────────────────────────────────────────────────┐
   │ LotteryCrawler.crawl_matches_sync()                         │
   │ 返回: [{                                                     │
   │   "matchId": "20260524001",                                  │
   │   "matchNum": "001",                                         │
   │   "homeTeam": "曼联",                                        │
   │   "awayTeam": "利物浦",                                      │
   │   "matchDate": "2026-05-24",                                 │
   │   "matchTime": "22:00",                                      │
   │   "leagueName": "英超",                                      │
   │   "sellStatus": "on",                                        │
   │   "spfOdds": {"3": 2.15, "1": 3.20, "0": 3.05}              │
   │ }]                                                           │
   └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
2. 字段映射 + 球队映射
   ┌─────────────────────────────────────────────────────────────┐
   │ EntityMapper.map_lottery_to_system(raw_match)               │
   │                                                              │
   │ 步骤1: 字段映射                                              │
   │   matchId → lottery_match_id                                 │
   │   homeTeam → home_team_cn                                    │
   │   sellStatus: "on" → sell_status: "selling"                  │
   │                                                              │
   │ 步骤2: 球队映射                                              │
   │   "曼联" → get_team_id() → 585                               │
   │   "利物浦" → get_team_id() → 561                             │
   │                                                              │
   │ 返回: {                                                      │
   │   "lottery_match_id": "20260524001",                         │
   │   "match_num": "001",                                        │
   │   "home_team_cn": "曼联",                                    │
   │   "away_team_cn": "利物浦",                                  │
   │   "home_team_id": 585,        ← 映射后的team_id              │
   │   "away_team_id": 561,        ← 映射后的team_id              │
   │   "match_date": "2026-05-24",                                │
   │   "match_time": "22:00",                                     │
   │   "league_name_cn": "英超",                                  │
   │   "sell_status": "selling"                                   │
   │ }                                                            │
   └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
3. DAO入库
   ┌─────────────────────────────────────────────────────────────┐
   │ LotteryMatchDAO.insert(match_data)                          │
   │                                                              │
   │ SQL:                                                         │
   │ INSERT INTO lottery_matches (                                │
   │   lottery_match_id, match_num, home_team_cn, away_team_cn,  │
   │   home_team_id, away_team_id, match_date, match_time,       │
   │   league_name_cn, sell_status                                │
   │ ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)                      │
   └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
4. 数据库表
   ┌─────────────────────────────────────────────────────────────┐
   │ lottery_matches 表                                           │
   │ ┌────────────────────┬────────────┬──────────────┬────────┐ │
   │ │ lottery_match_id   │ match_num  │ home_team_cn │ home_  │ │
   │ │                    │            │              │ team_id│ │
   │ ├────────────────────┼────────────┼──────────────┼────────┤ │
   │ │ 20260524001        │ 001        │ 曼联         │ 585    │ │
   │ └────────────────────┴────────────┴──────────────┴────────┘ │
   └─────────────────────────────────────────────────────────────┘

5. 赔率入库
   ┌─────────────────────────────────────────────────────────────┐
   │ LotteryOddsDAO.insert({                                     │
   │   'lottery_match_id': '20260524001',                        │
   │   'play_type': 'spf',                                       │
   │   'odds_data': '{"3": 2.15, "1": 3.20, "0": 3.05}'         │
   │ })                                                           │
   └─────────────────────────────────────────────────────────────┘
```

---

## 七、映射表维护

### 7.1 查看未映射球队

```python
# 列出未映射的体彩球队
unmapped = mapper.list_unmapped_teams()
# ['某新球队', '另一个球队']

# 手动添加映射
mapper.register_team_mapping('某新球队', 999, method='manual')
```

### 7.2 API添加映射

```bash
# 通过API添加球队映射
POST /api/v1/lottery/team-mappings
{
    "lottery_name": "某新球队",
    "team_id": 999
}
```

---

## 八、总结

### 关键点

1. **统一入口**: 所有数据源通过 `EntityMapper.map_to_standard()` 统一转换
2. **字段映射表**: `FIELD_MAPPINGS` 定义每个数据源的字段对应关系
3. **值转换器**: `VALUE_CONVERTERS` 处理数据格式转换
4. **球队映射**: 体彩名称通过 `team_name_mapping` 表关联 `team_id`
5. **多源合并**: `merge_multi_source()` 按优先级合并多数据源
6. **DAO隔离**: 数据库操作封装在DAO层，与映射逻辑解耦

### 扩展新数据源

1. 在 `FIELD_MAPPINGS` 添加新数据源字段映射
2. 在 `VALUE_CONVERTERS` 添加必要的值转换
3. 创建对应的爬虫/API客户端
4. 调用 `EntityMapper.map_to_standard()` 转换数据
5. 通过DAO入库
