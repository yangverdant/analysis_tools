# Odds Feed API 数据备份

## 渠道信息
- **渠道名称**: Odds Feed API (oddsfe.com)
- **网站地址**: https://oddsfe.com
- **数据类型**: 全球足球赛事赔率数据
- **采集日期**: 2026-05-29 ~ 2026-06-01
- **日期范围**: 2024-08-16 至 2026-06-09

## 数据文件

### 1. 完整合并数据
- **文件**: `oddsfe_data_full.csv` (1.13 GB)
- **说明**: Schedule数据 + 详情页赔率数据合并，每行一场比赛的完整数据
- **字段数**: 36个（schedule 28个 + 赔率 8个）
- **总行数**: 247,622 场赛事
- **有赔率**: 154,613 场（62.5%）
- **串联key**: event_id

### 2. Schedule原始数据
- **文件**: `oddsfe_data.csv` (32.8 MB)
- **说明**: 仅来自 /bind/schedule/ API 的赛事基础信息 + Pinnacle赔率
- **字段数**: 28个
- **总行数**: 247,622 场赛事
- **内容**: 赛事信息、联赛信息、球队、Pinnacle 1X2赔率及投注量

### 3. 详情页赔率数据
- **文件**: `oddsfe_detail_odds.csv` (818 MB)
- **说明**: 仅来自 /events/{id} 详情页的多市场赔率数据
- **字段数**: 9个（event_id + 8个市场赔率字段）
- **总行数**: 247,947 条
- **去重后**: 165,793 场有赔率
- **串联key**: event_id（与schedule数据关联）

## 8个赔率字段说明
| 字段 | 说明 | 格式 |
|------|------|------|
| 1X2_prematch_bookmakers | 1X2开盘赔率 | PINNACLE:1.64:5.35:4.34;BET365:1.60:5.25:4.20 |
| 1X2_live_bookmakers | 1X2滚球赔率 | 同上 |
| OVER_UNDER_prematch_bookmakers | 大小球开盘赔率 | PINNACLE:1.95:2.5:1.95 |
| OVER_UNDER_live_bookmakers | 大小球滚球赔率 | 同上 |
| ASIAN_HANDICAP_prematch_bookmakers | 亚盘开盘赔率 | PINNACLE:1.90:-0.5:2.00 |
| ASIAN_HANDICAP_live_bookmakers | 亚盘滚球赔率 | 同上 |
| BOTH_TEAMS_TO_SCORE_prematch_bookmakers | 双方进球开盘赔率 | PINNACLE:1.75:2.10 |
| BOTH_TEAMS_TO_SCORE_live_bookmakers | 双方进球滚球赔率 | 同上 |

## 完整字段说明
详见 `oddsfe_data_fields.md`

## 注意事项
- 早期赛事（2024年）大多无详情页赔率数据，属正常情况
- 赔率数据约覆盖62.5%的赛事，主要集中在2025年之后的赛事
- 每场赛事的赔率包含~10-30家bookmaker的数据
