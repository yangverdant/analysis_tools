# oddsfe_data.csv 字段说明

## 数据来源
- **schedule 数据**：来自 `https://oddsfe.com/bind/schedule/football/{date}` JSON API
- **详细赔率数据**：来自 `https://oddsfe.com/events/{event_id}?mt={市场类型}&live={开盘/滚球}` HTML页面解析

## 字段列表

### 赛事基础信息

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| event_id | int | 赛事唯一ID，oddsfe.com内部ID | 587646 |
| event_start_at | string | 开赛时间（UTC） | 2026-05-27T19:00:00 |
| event_status | string | 赛事状态 | NOT_STARTED / LIVE / FINISHED |
| event_winner | int | 比赛结果 | 0=主胜, 1=平, 2=客胜, 空=未完赛 |
| event_score_home | int | 主队全场进球 | 1 |
| event_score_away | int | 客队全场进球 | 0 |

### 联赛信息

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| tournament_id | int | 联赛ID | 430 |
| tournament_name | string | 联赛名称 | Premier League |
| tournament_slug | string | 联赛URL slug | premier-league |
| season_id | int | 赛季ID | 23865 |
| season_slug | string | 赛季标识 | 2025-2026 |
| category_id | int | 地区ID | 49 |
| category_name | string | 地区名称 | England |
| category_slug | string | 地区slug | england |

### 球队信息

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| team_home_id | int | 主队ID | 588 |
| team_home_name | string | 主队名称 | Crystal Palace |
| team_away_id | int | 客队ID | 1214 |
| team_away_name | string | 客队名称 | Rayo Vallecano |

### Pinnacle 赔率（来自schedule摘要）

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| main_out_0 | string | Pinnacle 主胜赔率 | 2.11 |
| main_out_1 | string | Pinnacle 平局赔率 | 3.21 |
| main_out_2 | string | Pinnacle 客胜赔率 | 4.09 |
| main_volume_0 | string | Pinnacle 主胜投注量 | 20 000 € |
| main_volume_1 | string | Pinnacle 平局投注量 | 20 000 € |
| main_volume_2 | string | Pinnacle 客胜投注量 | 20 000 € |
| event_outcome_0 | int | 主胜赔率×100（整数格式） | 211 (即2.11) |
| event_outcome_1 | int | 平局赔率×100（整数格式） | 321 (即3.21) |
| event_outcome_2 | int | 客胜赔率×100（整数格式） | 409 (即4.09) |
| event_pin_event_id | int | Pinnacle内部赛事ID | 1630267880 |
| sum_tournament_outcome_volume | string | 该联赛总投注量 | 2 716 300 € |

### 多市场赔率（来自 /events/{id} 详情页）

以下4个字段组，每组对应一种市场类型 × 开盘/滚球，共8个字段。
数据格式为分号分隔的bookmaker列表，每个bookmaker格式为 `名称:赔率1|赔率2|...`。

| 字段名 | 说明 | 数据格式 |
|--------|------|----------|
| 1X2_prematch_bookmakers | 1X2开盘赔率（~30家bookmaker） | `PINNACLE:2.11\|3.21\|4.09;BET365:2.10\|3.25\|4.00` |
| 1X2_live_bookmakers | 1X2滚球赔率 | 同上（无滚球数据时为空） |
| OVER_UNDER_prematch_bookmakers | 大小球开盘赔率 | `PINNACLE:1.95\|2.5\|1.95;BET365:1.90\|2.5\|2.00` |
| OVER_UNDER_live_bookmakers | 大小球滚球赔率 | 同上 |
| ASIAN_HANDICAP_prematch_bookmakers | 亚盘开盘赔率 | `PINNACLE:1.90\|-0.5\|2.00;1XBET:1.85\|-0.5\|2.05` |
| ASIAN_HANDICAP_live_bookmakers | 亚盘滚球赔率 | 同上 |
| BOTH_TEAMS_TO_SCORE_prematch_bookmakers | 双方进球开盘赔率 | `PINNACLE:1.75\|2.10;BET365:1.80\|2.05` |
| BOTH_TEAMS_TO_SCORE_live_bookmakers | 双方进球滚球赔率 | 同上 |

### 赔率字段内部格式详解

**1X2 格式**：`bookmaker:主胜|平局|客胜`
- 例：`PINNACLE:2.11|3.21|4.09`
- 主胜=2.11, 平局=3.21, 客胜=4.09

**OVER_UNDER 格式**：`bookmaker:Over赔率|盘口线|Under赔率`
- 例：`PINNACLE:1.95|2.5|1.95`
- Over=1.95, 线=2.5, Under=1.95

**ASIAN_HANDICAP 格式**：`bookmaker:主让赔率|让球数|客让赔率`
- 例：`PINNACLE:1.90|-0.5|2.00`
- 主让赔率=1.90, 让球=-0.5(主让半球), 客让赔率=2.00

**BOTH_TEAMS_TO_SCORE 格式**：`bookmaker:Yes赔率|No赔率`
- 例：`PINNACLE:1.75|2.10`
- Yes=1.75, No=2.10

### 多bookmaker分隔

- 不同bookmaker之间用 `;` 分隔
- 同一bookmaker的赔率值用 `|` 分隔
- 例：`PINNACLE:2.11|3.21|4.09;BET365:2.10|3.25|4.00;1XBET:2.15|3.20|3.90`

## 常见Bookmaker名称

| 名称 | 全称 | 名称 | 全称 |
|------|------|------|------|
| PINNACLE | Pinnacle Sports | BET365 | Bet365 |
| 1XBET | 1xBet | UNIBET | Unibet |
| DRAKE | Drake | COOL | Coolbet |
| BWIN | bwin | WILLIAM_HILL | William Hill |
| MARATHON | Marathonbet | 10BET | 10Bet |
| BETFAIR | Betfair Exchange | LADBROKES | Ladbrokes |

## 采集范围

- **日期范围**：2024-08-16 至 2026-06-09
- **覆盖联赛**：全球所有足球联赛（oddsfe.com 有数据的）
- **赛事状态**：包含已完赛(FINISHED)、进行中(LIVE)、未开赛(NOT_STARTED)
- **更新频率**：可增量采集，每天追加最新数据

## 使用示例

```python
import csv

with open('oddsfe_data.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # 基础筛选：只看EPL
        if row['tournament_name'] == 'Premier League':
            print(f"{row['team_home_name']} vs {row['team_away_name']}")
            print(f"  Pinnacle: {row['main_out_0']}/{row['main_out_1']}/{row['main_out_2']}")
            print(f"  Score: {row['event_score_home']}-{row['event_score_away']}")

        # 解析多bookmaker赔率
        if row['1X2_prematch_bookmakers']:
            for bk_entry in row['1X2_prematch_bookmakers'].split(';'):
                name, odds_str = bk_entry.split(':')
                odds = odds_str.split('|')
                print(f"  {name}: 1={odds[0]} X={odds[1]} 2={odds[2]}")
```
