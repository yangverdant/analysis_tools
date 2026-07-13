---
name: oddsfe-data-coverage
description: "oddsfe_merged.db数据覆盖详情：249,797场比赛、11庄赔率、4个盘口类型、prematch=收盘价的关键发现"
metadata: 
  node_type: memory
  type: reference
  originSessionId: a3325eab-87ac-48a6-8496-2ff45be69cae
---

# oddsfe_merged.db 数据覆盖

## 基本信息
- 路径: `fetchers/odds_feed_api/oddsfe_merged.db`
- 大小: 2.38 GB
- 表: oddsfe (唯一表, 378列, 全TEXT类型)
- 日期: 2024-08-16 ~ 2026-06-14
- 总比赛: 249,797场
- 有比分: 248,061场 (99.3%)
- 赛事: 1,001个锦标赛
- 球队: 13,310支 (需用category_name筛选, 如England+Premier League才是英超)

## Pinnacle赔率覆盖
| 盘口 | prematch数 | 说明 |
|------|-----------|------|
| 1X2 | 120,501 | 胜平负 |
| O/U | 121,132 | 大小球 |
| AH | 121,120 | 亚盘 |
| BTTS | 18,969 | 双方进球 |
| Live 1X2 | 89,016 | 滚球 |

## 11家博彩公司
PINNACLE, BET365, BETFAIR_EXCH, BETFAIR, 1XBET, WILLIAM_HILL, DAFABET, BWIN, UNIBET, 888_SPORT, STAKE_COM, MATCHBOOK, BET_AT_HOME

## 列分组 (378列)
- 1X2: 94列 (prematch 47 + live 47)
- OVER_UNDER: 94列
- ASIAN_HANDICAP: 94列
- BOTH_TEAMS_TO_SCORE: 64列
- event/tournament/team/category: 32列

## 关键发现: prematch = 收盘价
- 实测478场英超: **95.4%** 的oddsfe Pinnacle prematch更接近CSV收盘价(PSCH)
- 只有4.6%接近开盘价(PSH)
- "close"字段全是1.00, 无意义
- **oddsfe里没有真正的开盘价**
- 做CLV需: CSV的PSH(开盘) + oddsfe的prematch(收盘)

## SQL注意事项
- 列名必须双引号: `"1X2_prematch_PINNACLE_home"`
- 查数值需CAST: `CAST("1X2_prematch_PINNACLE_home" AS FLOAT)`
- 筛选英超必须加category: `WHERE category_name = 'England' AND tournament_name = 'Premier League'`
- tournament_name不唯一! 同名"Premier League"存在于36+国家

## 友谊赛覆盖
- Friendly International: 1,248场
- Club Friendly: 6,331场
- 共8,492场友谊赛

## Top5赛事 (全量)
1. Premier League: 11,090
2. Club Friendly: 6,331
3. Super League: 3,275
4. Division 1: 2,282
5. Ligue 1: 2,070

## 与其他源的关系
- CSV all.csv: 有开盘+收盘, 但只覆盖27联赛; oddsfe补小联赛和友谊赛
- football_v2.db: 赔率收盘全空; oddsfe是其赔率数据的补充
- 球队名仅23.7%重叠, 需日期+模糊匹配桥接 (Man City=Manchester City)
