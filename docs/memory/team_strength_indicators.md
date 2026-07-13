---
name: team-strength-indicators
description: 球队实力指标采集全流程：Elo等级分(计算)、FIFA排名(爬取)、联赛积分榜(API)、身价(Transfermarkt待采集)
metadata: 
  node_type: memory
  type: reference
  originSessionId: a3325eab-87ac-48a6-8496-2ff45be69cae
---

# 球队实力指标采集 — Elo / 排名 / 积分榜 / 身价

## 一、指标总览

| 指标 | 覆盖 | 数据量 | 采集方式 | 状态 |
|------|------|--------|---------|------|
| Elo等级分 | 俱乐部1,037队 | 65,236条历史 | 自行计算 | 可用 |
| FIFA排名 | 国家队100+ | 423条(2快照) | Playwright爬FIFA官网 | 可用 |
| 联赛积分榜 | 6联赛78条 | 486条(unified) | apifootball API | 需刷新 |
| 球队身价 | **未采集** | 仅20条转会记录 | Transfermarkt爬虫 | **缺数据** |

## 二、Elo等级分

### 2.1 原理
- 初始分1500，K=32
- 按时间顺序遍历所有已完赛比赛，逐步更新
- 期望值: `E_h = 1 / (1 + 10^((Elo_away - Elo_home) / 400))`
- 更新: `Elo_new = Elo_old + K * (actual - expected)`

### 2.2 两个Elo系统

| 数据库 | 表 | 记录数 | 特点 |
|--------|-----|--------|------|
| football_v2.db | `elo_ratings` | 1,037 | 当前Elo + 比赛次数 |
| football_v2.db | `elo_history` | 65,236 | 每场比赛后的Elo变化 |
| unified_football.db | `match_data`(source=system, type=elo) | ~3,500 | 每场比赛的Elo JSON |

**注意**: 两套DB的Elo值不同（数据源和计算范围不同），以 `football_v2.db` 为准（覆盖更全）。

### 2.3 Top 10 (football_v2.db, 2026-05-20)

| 球队 | Elo | 比赛数 |
|------|-----|--------|
| Bayern | 1886 | 116 |
| Arsenal FC | 1853 | 149 |
| FC Barcelona | 1834 | 125 |
| PSG | 1816 | 118 |
| Celtic | 1795 | 132 |
| Manchester City FC | 1790 | 144 |
| Porto | 1788 | 122 |
| Sporting CP | 1787 | 114 |
| Fenerbahce | 1787 | 128 |

### 2.4 采集脚本 — `fetchers/scripts/compute_elo.py`

**功能**: 从 `unified_football.db` 的 finished 比赛计算Elo，存回 `match_data`

**数据流**:
```
unified_football.db matches(已完赛)
  → 按日期排序，逐场计算
  → 获取比分 (source='football-data.org', data_type='match')
  → 更新Elo，存入 match_data (source='system', data_type='elo')
  → 最终存全局ratings (match_key='_global', data_type='elo_ratings')
```

**运行**:
```bash
python fetchers/scripts/compute_elo.py
```

### 2.5 因子提取 — `fetchers/analysis/factors/elo_rating.py`

模型调用时读取预计算的Elo:
```python
from fetchers.analysis.factors.elo_rating import EloRatingFactor
factor = EloRatingFactor()
result = factor.extract(match_key, storage)
# → {home_value: 1790, away_value: 1650, diff: 0.35, confidence: 0.8}
```

**归一化**: `diff = (home_elo - away_elo) / 400`，量级约[-1, 1]

---

## 三、FIFA排名

### 3.1 数据范围
- 仅国家队（100+队）
- 最新快照: 2026-06-05
- Top 5: Argentina(1865), France(1850), Spain(1835), England(1812), Brazil(1795)

### 3.2 存储位置

| 位置 | 格式 | 记录数 |
|------|------|--------|
| `football_v2.db` → `fifa_rankings` 表 | 关系型 | 423 (2个日期快照) |
| `fetchers/fifa_ranking/data/fifa_ranking_current.json` | JSON | 100队 |
| `data/fifa_rankings/fifa_world_ranking_complete_2000_2026.csv` | CSV | 2,161行 |
| `data/fifa_rankings/fifa_club_ranking_complete_2000_2026.csv` | CSV | 361行(未入库) |

### 3.3 DB表结构 (`fifa_rankings`)

| 列 | 类型 | 说明 |
|----|------|------|
| ranking_id | PK | 自增ID |
| rank_date | TEXT | 快照日期 |
| team_id | INT | 外键→teams |
| rank | INT | 排名 |
| points | FLOAT | 积分 |
| previous_rank | INT | 上期排名 |
| previous_points | FLOAT | 上期积分 |
| movement | INT | 排名变化 |
| confederation | TEXT | 足联(UEFA/CONMEBOL/CAF/AFC/CONCACAF/OFC) |

### 3.4 采集脚本 — `fetchers/fifa_ranking/get_ranking.py`

**功能**: 读取本地JSON / Playwright爬取FIFA官网刷新

**关键函数**:
- `get_rankings(top_n)` → 完整排名列表
- `get_team_ranking(team_name)` → 单队排名+积分+足联
- `get_ranking_diff(home, away)` → 排名差+足联强度差（用于模型）
- `get_confederation(team_name)` → 足联+强度系数
- `refresh_rankings()` → Playwright爬 https://www.fifa.com/fifa-world-ranking/men

**足联强度系数** (`fetchers/fifa_ranking/config.py`):

| 足联 | 强度 |
|------|------|
| UEFA | 1.00 |
| CONMEBOL | 0.95 |
| CONCACAF | 0.80 |
| CAF | 0.75 |
| AFC | 0.70 |
| OFC | 0.50 |

**使用示例**:
```python
from fetchers.fifa_ranking.get_ranking import get_ranking_diff

diff = get_ranking_diff("Argentina", "Brazil")
# → {home_rank: 1, away_rank: 5, rank_diff: -4,
#    home_points: 1865, away_points: 1795, points_diff: 70,
#    confederation_strength_diff: 0.05}
```

**刷新命令**: 需先安装 Playwright
```bash
pip install playwright && playwright install chromium
python -c "from fetchers.fifa_ranking.get_ranking import refresh_rankings; refresh_rankings()"
```

### 3.5 缺口
- **FIFA俱乐部排名**: CSV文件有（`fifa_club_ranking_complete_2000_2026.csv`），但**未导入DB**
- 国家队排名已有2个快照，建议每月刷新1次

---

## 四、联赛积分榜

### 4.1 两个数据源

| 数据库 | 记录数 | 联赛 |
|--------|--------|------|
| football_v2.db → `standings` | 78 | 英超/意甲/西甲/德甲/英甲/挪超 |
| unified_football.db → `standings` | 486 | 更多联赛，数据更全 |

### 4.2 DB表结构 (football_v2.db `standings`)

| 列 | 说明 |
|----|------|
| position | 排名 |
| played/won/drawn/lost | 场次/胜/平/负 |
| goals_for/goals_against/goal_diff | 进球/失球/净胜球 |
| points | 积分 |
| form | 近期战绩 (如 "WWDLW") |
| home_* / away_* | 主/客场分拆统计 |
| xpts | 预期积分 |
| last_5_points / last_10_points | 近5/10场积分 |
| standing_type | TOTAL/HOME/AWAY |

### 4.3 采集方式

**方式1**: apifootball API（主要）
```python
from fetchers.apifootball.get_data import get_standings

standings = get_standings("premier_league", season="2026")
# → [{position: 1, team: "Liverpool", points: 82, ...}, ...]
```
- 需API Key（在 `fetchers/apifootball/config.py`）
- 免费100次/天

**方式2**: football-data.org API
```python
from fetchers.football_data_org.get_matches import get_standings
```
- 需API Token

**方式3**: 手动更新
```bash
python scripts/update_standings_data.py
```

### 4.4 因子提取 — `fetchers/analysis/factors/standing.py`

```python
from fetchers.analysis.factors.standing import StandingFactor
result = factor.extract(match_key, storage)
# → {home_value: 3, away_value: 7, diff: -0.2,  # 归一化: rank_diff/20
#    home_points: 65, away_points: 42,
#    home_ppg: 1.86, away_ppg: 1.20, ...}
```

### 4.5 缺口
- `football_v2.db` 只有6个联赛的积分榜，且只有78条
- 很多二级联赛（英冠/西乙/德乙等）没有积分榜数据
- 需要定期刷新（建议每周1次）

---

## 五、球队身价 — 最大缺口

### 5.1 现状
- **DB中无 squad_value 列**（football_v2.db teams表没有身价字段）
- 仅 `transfers` 表有20条转会费记录（Bellingham 100M, Haaland 60M等）
- `team_form` 表有3,349条，但不含身价

### 5.2 采集脚本 — `fetchers/transfermarkt/get_data.py`

**已实现**但**未实际运行采集**，存在反爬限制。

**关键函数**:
- `get_squad(team_url)` → 球队阵容（含每个球员身价）
  - 输入: `/arsenal-fc/startseite/verein/11`
  - 输出: `[{player_name, position, market_value_m, ...}]`
- `get_player_value(player_url)` → 单球员身价
- `get_league_valuations(league)` → 联赛身价排行（简化版）

**联赛URL映射** (`fetchers/transfermarkt/config.py`):

| 联赛 | URL |
|------|-----|
| 英超 | `/premier-league/startseite/wettbewerb/GB1` |
| 西甲 | `/la-liga/startseite/wettbewerb/ES1` |
| 德甲 | `/bundesliga/startseite/wettbewerb/L1` |
| 意甲 | `/serie-a/startseite/wettbewerb/IT1` |
| 法甲 | `/ligue-1/startseite/wettbewerb/FR1` |
| 荷甲 | `/eredivisie/startseite/wettbewerb/NL1` |
| 欧冠 | `/uefa-champions-league/startseite/wettbewerb/CL` |

**身价解析**: `€65.00m` → 65.0, `€3.50m` → 3.5, `€500k` → 0.5

**反爬**: 建议每请求间隔5秒，Transfermarkt有严格反爬

### 5.3 要跑起来需要
1. 在 `football_v2.db` 的 `teams` 表添加 `squad_value` 列
2. 写一个批量采集脚本，遍历7个联赛所有球队的 `get_squad()`
3. 汇总球员身价为球队总身价
4. 控制频率（5s间隔），可能需要代理或Cloudflare绕过

### 5.4 替代方案
- **apifootball API**: 有球队阵容接口，但不含身价
- **手动导入**: Transfermarkt页面数据可手动整理为CSV再导入
- **估算**: 用Elo×系数近似身价，精度差但可用

---

## 六、数据流总览

```
┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐
│ unified DB   │  │ football_v2  │  │ transfermarkt.com    │
│ (finished    │  │ (teams,      │  │ (球队阵容+球员身价)  │
│  matches)    │  │  matches)    │  │                      │
└──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘
       │                 │                      │
       ↓                 ↓                      │
  compute_elo.py    v2内部Elo计算               │  ← 未采集
       │            (backend/app/               │
       ↓             analytics/elo.py)          │
  unified DB        football_v2.db              │
  match_data        elo_ratings                 │
  (system/elo)      elo_history                 │
                    ┌───────────┐               │
                    │ FIFA官网  │               │
                    │ (Playwright)│              │
                    └─────┬─────┘               │
                          ↓                     ↓
                    fifa_ranking.py      get_squad() ← 待采集
                    (refresh_rankings)   → 球员身价→球队总身价
                          ↓                     ↓
                    football_v2.db       teams.squad_value ← 待建列
                    fifa_rankings
                          │
                    ┌─────┴─────┐
                    │apifootball│
                    │  API      │
                    │get_standings│
                    └─────┬─────┘
                          ↓
                    football_v2.db
                    standings (78条)
                    unified_football.db
                    standings (486条)
```

## 七、日常维护

| 任务 | 频率 | 命令 |
|------|------|------|
| 重算Elo | 每周 | `python fetchers/scripts/compute_elo.py` |
| 刷新FIFA排名 | 每月 | `python -c "from fetchers.fifa_ranking.get_ranking import refresh_rankings; refresh_rankings()"` |
| 更新积分榜 | 每周 | `python -c "from fetchers.apifootball.get_data import get_standings; ..."` |
| 采集身价 | 待实现 | 需先建列+写批量脚本 |

## 八、与赔率数据的关联

模型需要**赔率+实力**双维度:

| 维度 | 数据 | 来源 | 对应MD |
|------|------|------|--------|
| 市场看法 | 开盘/收盘赔率 | CSV + oddsfe | [[csv-odds-collection-alignment]] |
| 球队实力 | Elo/FIFA/积分榜 | 本MD | — |
| CLV信号 | 收盘-开盘 | CSV PSH + oddsfe prematch | [[csv-odds-collection-alignment]] |
| 实力-赔率差 | Elo差 vs 赔率隐含概率 | 两者结合 | — |

**最关键的组合**: CLV(开盘vs收盘) + Elo差 + 联赛排名差 → 模型的3个核心信号
