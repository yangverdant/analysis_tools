---
name: csv-odds-collection-alignment
description: football-data.co.uk CSV采集全流程：4个脚本、URL模板、18联赛代码、对齐oddsfe方法、最终输出oddsfe_opening_odds.csv
metadata: 
  node_type: memory
  type: reference
  originSessionId: a3325eab-87ac-48a6-8496-2ff45be69cae
---

# football-data.co.uk CSV采集 + oddsfe对齐 全流程

## 一、数据源概述

| 属性 | 值 |
|------|-----|
| 网址 | https://www.football-data.co.uk |
| 费用 | 免费，无需API Key |
| 数据 | 比赛结果 + 开盘/收盘赔率 + 比赛统计 |
| 覆盖 | 18个联赛，1993-94赛季至今 |
| 格式 | CSV直接下载 |

## 二、CSV下载URL模板

```
https://www.football-data.co.uk/mmz4281/{season}/{league_code}.csv
```

- `season`: 4位赛季代码，如 `2425` = 2024-25赛季，`2526` = 2025-26赛季
- `league_code`: 2-3位联赛代码

## 三、18个联赛代码

| 代码 | 联赛 | 国家 | 球队 | 轮次 |
|------|------|------|------|------|
| E0 | 英超 Premier League | England | 20 | 38 |
| E1 | 英冠 Championship | England | 24 | 46 |
| E2 | 英甲 League One | England | 24 | 46 |
| E3 | 英乙 League Two | England | 24 | 46 |
| SP1 | 西甲 La Liga | Spain | 20 | 38 |
| SP2 | 西乙 Segunda Division | Spain | 22 | 42 |
| D1 | 德甲 Bundesliga | Germany | 18 | 34 |
| D2 | 德乙 2. Bundesliga | Germany | 18 | 34 |
| I1 | 意甲 Serie A | Italy | 20 | 38 |
| I2 | 意乙 Serie B | Italy | 20 | 38 |
| F1 | 法甲 Ligue 1 | France | 18 | 34 |
| F2 | 法乙 Ligue 2 | France | 18 | 34 |
| N1 | 荷甲 Eredivisie | Netherlands | 18 | 34 |
| P1 | 葡超 Primeira Liga | Portugal | 18 | 34 |
| T1 | 土超 Super Lig | Turkey | 20 | 38 |
| B1 | 比甲 Jupiler League | Belgium | 18 | 34 |
| SC0 | 苏超 Premiership | Scotland | 12 | 38 |
| G1 | 希腊超 Super League | Greece | 14 | 36 |

## 四、4个采集/更新脚本

### 4.1 核心下载模块 — `fetchers/football_data_uk/get_csv.py`

**功能**: 下载+解析CSV为pandas DataFrame

**关键函数**:
- `fetch_league(league_name, season, session)` — 下载单个联赛/赛季
- `fetch_historical(league_name, from_season, to_season)` — 批量下载历史赛季
- `fetch_all_leagues(season)` — 下载所有联赛当前赛季
- `save_csv(df, output_path)` — 保存DataFrame到CSV
- `get_season_code(year)` — 年份转赛季代码 (2024 → "2425")

**配置**: `fetchers/football_data_uk/config.py`
- `BASE_URL = "https://www.football-data.co.uk"`
- `URL_CSV = BASE_URL + "/mmz4281/{season}/{league_code}.csv"`
- `LEAGUES` 字典: 18个联赛的中文名→代码映射
- `CSV_COLUMNS` 字典: 所有CSV列名的中文含义

**使用示例**:
```python
from fetchers.football_data_uk.get_csv import fetch_league, fetch_historical

# 下载英超当前赛季
df = fetch_league("英超")

# 下载英超2020-2025历史
dfs = fetch_historical("英超", from_season="2020", to_season="2025")

# 下载所有联赛当前赛季
from fetchers.football_data_uk.get_csv import fetch_all_leagues
results = fetch_all_leagues()
```

**命令行**:
```bash
python -m fetchers.football_data_uk.get_csv current 英超
python -m fetchers.football_data_uk.get_csv current 英超 2425
python -m fetchers.football_data_uk.get_csv history 英超 2020 2025
python -m fetchers.football_data_uk.get_csv all
```

**反爬**: 绕过代理 (`http_proxy=''`), 0.5s请求间隔

---

### 4.2 数据更新脚本 — `scripts/data_sync/update_football_data.py`

**功能**: 下载→去重→保存CSV→同步数据库

**类**:
- `FootballDataScraper` — 爬取数据，404时自动回退上一赛季
- `DataProcessor` — 处理日期(DD/MM/YYYY→YYYY-MM-DD)、去重(Date+HomeTeam+AwayTeam)、保存
- `DatabaseSync` — 同步到 `football_unified.db`

**保存路径**: `data/01_leagues/{country}/{file}_{season}.csv`

**命令行**:
```bash
python scripts/data_sync/update_football_data.py --all
python scripts/data_sync/update_football_data.py --leagues E0 E1
python scripts/data_sync/update_football_data.py --leagues 英超 德甲
```

---

### 4.3 简易批量更新 — `scripts/data_sync/update_all_leagues.py`

**功能**: 纯CSV更新，不涉及数据库

**流程**: 下载新数据 → 读取已有CSV → concat合并 → drop_duplicates → 按日期排序 → 保存

**保存路径**: `data/01_leagues/{country}/{file}` (无赛季后缀)

**命令行**:
```bash
python scripts/data_sync/update_all_leagues.py
```

---

### 4.4 赔率专用采集 — `fetchers/scripts/collect_odds_csv.py`

**功能**: 专门采集赔率数据，存入 `unified_football.db`

**覆盖**: 11个联赛 × 2-3个赛季 (2324/2425/2526)

**提取字段**:
- 平均赔率: AvgH/AvgD/AvgA (开盘), AvgCH/AvgCD/AvgCA (收盘)
- B365: B365H/B365D/B365A
- Pinnacle: PSH/PSD/PSA
- 大小球: B365>2.5/B365<2.5, Avg>2.5/Avg<2.5
- 亚盘: AHh, AvgAHH/AvgAHA

**存储**: `match_data` 表, source=`"football-data-co-uk"`, data_type=`"odds"`, JSON格式

**球队名标准化**: TEAM_MAP (160+映射) → `normalize_team_name()` → `make_match_key()`

**命令行**:
```bash
python fetchers/scripts/collect_odds_csv.py
```

---

### 4.5 定时任务 — `scripts/utilities/daily_update.bat`

```bat
cd /d d:\football_tools
python scripts\update_football_data.py --all
```

Windows任务计划程序每天自动执行。

## 五、CSV列名含义（赔率部分）

### 命名规则
```
{庄家}{S/C}{H/D/A}
S = Starting (开盘)
C = Closing (收盘)
H = Home (主胜)
D = Draw (平)
A = Away (客胜)
```

### 主要字段

| 列名 | 含义 | 类型 |
|------|------|------|
| PSH | Pinnacle开盘主胜 | 开盘 |
| PSD | Pinnacle开盘平 | 开盘 |
| PSA | Pinnacle开盘客胜 | 开盘 |
| PSCH | Pinnacle收盘主胜 | 收盘 |
| B365H | Bet365开盘主胜 | 开盘 |
| B365D | Bet365开盘平 | 开盘 |
| B365A | Bet365开盘客胜 | 开盘 |
| B365CH | Bet365收盘主胜 | 收盘 |
| WHH | William Hill开盘主胜 | 开盘 |
| BWH | BetWin开盘主胜 | 开盘 |
| IWH | Interwetten开盘主胜 | 开盘 |
| AHh | 亚盘让球数 | 盘口 |
| B365AHH | B365亚盘主 | 开盘 |
| B365AHA | B365亚盘客 | 开盘 |
| PAHH | Pinnacle亚盘主 | 开盘 |
| PAHA | Pinnacle亚盘客 | 开盘 |
| B365>2.5 | B365大2.5球 | 开盘 |
| B365<2.5 | B365小2.5球 | 开盘 |
| PS>2.5 | Pinnacle大2.5球 | 开盘 |
| PS<2.5 | Pinnacle小2.5球 | 开盘 |

### 比赛统计字段

| 列名 | 含义 |
|------|------|
| HS/AS | 主/客射门 |
| HST/AST | 主/客射正 |
| HF/AF | 主/客犯规 |
| HC/AC | 主/客角球 |
| HY/AY | 主/客黄牌 |
| HR/AR | 主/客红牌 |
| FTHG/FTAG | 全场主/客进球 |
| HTHG/HTAG | 半场主/客进球 |

## 六、CSV数据存储位置

```
data/
├── 01_europe_leagues/          ← 主要CSV存储 (football-data.co.uk标准格式)
│   ├── premier_league/         ← 英超
│   │   ├── premier_league_all.csv
│   │   ├── premier_league_2024-2025.csv
│   │   └── premier_league_2025-2026.csv
│   ├── bundesliga/
│   ├── serie_a/
│   ├── la_liga/
│   ├── ligue_1/
│   ├── eredivisie/
│   ├── primeira_liga/
│   ├── super_lig/
│   ├── jupiler_league/
│   ├── scotland_premier/
│   ├── super_league/           ← 希腊超
│   └── ... (27个子目录)
├── 01_leagues/                 ← update_football_data.py的输出
│   ├── england/
│   ├── germany/
│   └── ...
└── 02_europe_cups/             ← 杯赛CSV
```

## 七、oddsfe对齐脚本 — `fetchers/odds_feed_api/align_oddsfe_csv.py`

### 目的
将CSV开盘价(PSH等)与oddsfe_merged.db的收盘价对齐，生成CLV分析用的合并CSV。

### 背景
- oddsfe的"prematch"字段 = 收盘价（95.4%验证），没有真正的开盘价
- CSV的PSH = 真正的Pinnacle开盘价
- CLV = 收盘价 - 开盘价，是最强预测信号
- 必须合并两个源才能做CLV

### 匹配策略
1. **日期精确匹配** (YYYY-MM-DD)
2. **球队名3层匹配**:
   - 直接匹配: `Man City` == `Man City`
   - 映射匹配: `Man City` → `Manchester City` (TEAM_NAME_MAP, 100+映射)
   - 模糊匹配: 包含关系，短名≥4字符 (如 `Wolves` in `Wolves`)

### 数据流
```
data/01_europe_leagues/*.csv  →  load_csv_opening_odds()  →  csv_lookup
                                                                    ↓
oddsfe_merged.db              →  SQL查询(151,202场)        →  逐行匹配
                                                                    ↓
                                              oddsfe_opening_odds.csv
```

### 输出字段

| 分组 | 字段 | 来源 |
|------|------|------|
| 基础 | event_id, date, category, tournament, home, away, score, winner | oddsfe |
| Pinnacle收盘 | pin_close_h/d/a | oddsfe prematch |
| B365收盘 | b365_close_h/d/a | oddsfe prematch |
| 1XBET收盘 | 1xbet_close_h/d/a | oddsfe prematch |
| O/U收盘 | ou_over, ou_line, ou_under | oddsfe prematch |
| AH收盘 | ah_home, ah_hcp, ah_away | oddsfe prematch |
| BTTS收盘 | btts_yes, btts_no | oddsfe prematch |
| Pinnacle开盘 | psh, psd, psa | CSV |
| Pinnacle收盘验证 | psch | CSV |
| B365开盘 | b365h, b365d, b365a | CSV |
| B365收盘验证 | b365ch | CSV |
| 其他庄开盘 | whh, bwh, iwh | CSV |
| 比赛统计 | hs, as, hst, ast, hc, ac, hf, af, hy, ay, hr, ar | CSV |
| 大小球/亚盘 | b365_ou25, b365_under25, ah_handicap, b365_ahh/aha, ps_ahh/aha | CSV |
| 半场 | hthg, htag | CSV |
| 匹配信息 | match_type (direct/mapped/fuzzy) | 对齐过程 |

### 运行结果 (2026-06-06)

| 指标 | 数值 |
|------|------|
| 总比赛 | 151,202 |
| 匹配到CSV | 12,379 (8.2%) |
| - 直接匹配 | 8,701 |
| - 映射匹配 | 86 |
| - 模糊匹配 | 3,592 |
| 有Pinnacle开盘(PSH) | 6,999 |
| 有Pinnacle收盘 | 120,489 |
| 有B365收盘 | 38,375 |
| 有1XBET收盘 | 150,620 |
| CLV可用(open+close) | 6,963 |

### 各联赛匹配率

| 联赛 | 总数 | 有PSH | 匹配率 |
|------|------|-------|--------|
| 意甲 Serie A | 549 | 456 | 83.1% |
| 西乙 LaLiga2 | 645 | 482 | 74.7% |
| 德甲 Bundesliga | 458 | 330 | 72.1% |
| 法甲 Ligue 1 | 451 | 322 | 71.4% |
| 荷甲 Eredivisie | 453 | 304 | 67.1% |
| 法乙 Ligue 2 | 445 | 300 | 67.4% |
| 西甲 LaLiga | 559 | 372 | 66.5% |
| 英冠 Championship | 824 | 565 | 68.6% |
| 英超 Premier League | 559 | 299 | 53.5% |
| 比甲 Jupiler League | 452 | 191 | 42.3% |
| 希腊超 Super League | 342 | 132 | 38.6% |

### 覆盖率低的原因
1. **CSV只覆盖18个主流联赛**，oddsfe有1,001个锦标赛
2. **小联赛/杯赛/友谊赛**在CSV中无数据 (Club Friendly 3,023场全0%)
3. **赛季进行中**的PSH未填入 (英超2025-26: 210/379有PSH)
4. **球队名差异** (23.7%重叠，需映射表桥接)

### 运行命令
```bash
python fetchers/odds_feed_api/align_oddsfe_csv.py
```

### 输出文件
```
fetchers/odds_feed_api/oddsfe_opening_odds.csv  (24MB, 151,202行)
```

## 八、完整数据流总览

```
┌─────────────────────────┐
│  football-data.co.uk    │  免费，无需认证
│  /mmz4281/{s}/{lc}.csv  │
└───────────┬─────────────┘
            │ 下载
            ↓
┌─────────────────────────┐
│  4个采集脚本            │
│  get_csv.py (核心)      │
│  update_football_data   │
│  update_all_leagues     │
│  collect_odds_csv       │
└───────────┬─────────────┘
            │ 保存
            ↓
┌─────────────────────────┐
│  data/01_europe_leagues/│  2,346个CSV文件
│  *.csv (开盘+收盘赔率)  │  272,795场比赛
└───────────┬─────────────┘
            │
            │  ┌─────────────────────────┐
            │  │  oddsfe.com             │  爬取内部API
            │  │  3步采集流程            │  [[oddsfe-collection-pipeline]]
            │  └───────────┬─────────────┘
            │              │
            │              ↓
            │  ┌─────────────────────────┐
            │  │  oddsfe_merged.db       │  2.38GB, 378列
            │  │  249,797场比赛          │  prematch=收盘价
            │  └───────────┬─────────────┘
            │              │
            ↓              ↓
┌─────────────────────────────────────┐
│  align_oddsfe_csv.py               │  对齐合并
│  日期+球队名匹配                    │
│  direct → mapped → fuzzy            │
└─────────────────┬───────────────────┘
                  │
                  ↓
┌─────────────────────────────────────┐
│  oddsfe_opening_odds.csv           │  最终输出
│  151,202行 × 56列                  │
│  oddsfe收盘 + CSV开盘 + 统计       │
│  CLV = pin_close - psh             │
└─────────────────────────────────────┘
```

## 九、日常维护

### 更新CSV数据
```bash
# 每天更新所有联赛
python scripts/data_sync/update_football_data.py --all

# 或用定时任务
scripts/utilities/daily_update.bat
```

### 重新对齐oddsfe
```bash
# CSV更新后重新生成对齐文件
python fetchers/odds_feed_api/align_oddsfe_csv.py
```

### 注意事项
- CSV日期格式: DD/MM/YYYY (新) 或 DD-MM-YY (旧)，脚本自动识别
- oddsfe SQL列名必须双引号: `"1X2_prematch_PINNACLE_home"`
- oddsfe tournament_name不唯一，必须加category_name筛选
- 部分oddsfe赔率值含附加文本 (如 `1.972 250€`)，`safe_odds()` 自动取首值
