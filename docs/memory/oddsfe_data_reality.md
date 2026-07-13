---
name: oddsfe-data-reality
description: oddsfe_merged.db实际数据状况——从真实查询得出的字段、覆盖率、数据类型、采集流程
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

# oddsfe_merged.db 实际数据状况

## 基本信息
- 位置：服务器 /opt/football_tools/data/oddsfe_merged.db (2.2GB)
- 行数：249,797
- 列数：378
- 日期范围：2024-08-16 ~ 2026-06-14
- 已加索引：idx_status, idx_tournament, idx_category, idx_start

## event_status分布（注意：全大写）
- FINISHED: 248,233 (99.4%)
- SCHEDULED: 935
- POSTPONED: 392
- CANCELLED: 121
- LIVE: 63
- ABANDONED: 48
- INTERRUPTED: 5

**关键：oddsfe的status全大写(FINISHED/SCHEDULED)，和football_v2.db的混合大小写不同。同步时需要统一为小写。**

## 赔率覆盖率
- PINNACLE 1X2 prematch: 120,501 (48%)
- PINNACLE 1X2 live: 89,016 (35%)
- BET365 1X2 prematch: 38,396 (15%)
- PINNACLE prematch+live都有: 部分
- **PINNACLE只覆盖48%，意味着52%的比赛没有PINNACLE赔率**

## 赔率数据类型
- 所有赔率列都是TEXT类型，不是REAL（如"1.53", "3.81"）
- 同步时需要CAST为REAL

## 比分覆盖
- 有比分: 248,061 (99.5%)
- 无比分: 1,736 (0.5%) — 主要是scheduled/live

## Tournament TOP20（注意：名称是英文，有歧义）
- Premier League: 11,090
- Club Friendly: 6,331
- Super League: 3,275 (哪个Super League？需要category_name区分)
- Division 1: 2,282 (哪个国家？)
- Ligue 1: 2,072
- Ligue 2: 2,030
- Primera Division: 1,784
- Championship: 1,758
- Serie B: 1,670
- Friendly International: 1,248

**关键问题：tournament_name不唯一！** "Division 1"可能是法国/挪威/其他国家的。
**必须用 tournament_name + category_name 组合才能唯一确定联赛。**

## Category分布（国家/地区）
- Spain: 17,159
- England: 14,898
- Brazil: 12,885
- Italy: 11,313
- Germany: 10,537
- World: 9,738 (国际赛事)
- Argentina: 6,189
- Czech Republic: 6,013
- Portugal: 4,884
- Poland: 4,855

## 队名格式
- 英文原名：Bayern Munich, Korea Republic, Mexico, Serbia
- **没有中文名，需要映射文件**
- **没有team_id，需要自行分配或映射**

## 赛事类型识别
需要从 tournament_name + category_name 推断：
- "Friendly International" + "World" → 友谊赛(国家队)
- "Club Friendly" + 任意 → 友谊赛(俱乐部)
- "Premier League" + "England" → 英超(联赛)
- "Champions League" + "World" → 欧冠(洲际杯赛)
- 世界杯需要看tournament_slug或具体tournament_name

## 采集流程（3步）
1. **oddsfe_realtime_schedule.py** → 采集/bind/schedule/ API
   - 获取过去5天+未来9天的schedule
   - 输出: event_id, 赛事信息, PINNACLE摘要赔率(main_out_0/1/2)
   - 只追加新event_id

2. **oddsfe_realtime_detail_v2.py** → 采集/events/{id}页面
   - 爬取4市场×2时机×15庄家的完整赔率
   - 还采集score_details(半场/加时/点球比分)
   - 支持多worker并行
   - 输出: 每个event一行，赔率packed在字段里

3. **oddsfe_clean_merge.py** → 合并schedule+detail
   - 展开赔率：从packed格式展开为378列（每个庄家每个outcome一列）
   - RED LINE: 历史数据不可修改，只更新recent_days范围内的
   - 输出: oddsfe_merged.db

4. **oddsfe_realtime_refresh.py** → 一键刷新
   - 串联以上3步
   - 每天运行一次

## 同步管道需注意的问题

### 1. tournament_name歧义
"Division 1"在法国、挪威、丹麦等都有。
解决方案：league_id = hash(tournament_name + category_name) 或用 tournament_id

### 2. PINNACLE赔率只覆盖48%
52%的比赛没有PINNACLE赔率，可能有BET365或其他庄家。
同步时需要遍历所有庄家，取第一个有值的作为fallback。

### 3. 赔率值是TEXT
需要CAST(odds AS REAL)。

### 4. 时间格式
event_start_at = "2026-06-10T11:00:00" (UTC)
需要转为北京时间(+8h)。

### 5. 赔率快照区分
oddsfe的prematch赔率实际上是**收盘价**（赛前最后一次更新），不是开盘价。
live赔率是盘中赔率。
之前验证过95.4%的prematch赔率与收盘价一致。
开盘价需要从football-data.co.uk CSV补充。

### 6. 比分格式
event_score_home/away = "2", "1" (TEXT，需要CAST为INT)
score_details在detail v2里，格式是**各半场各自进球数**（不是累积比分）:
- 2段: "上半场, 下半场" → 如 "0:1, 2:1" = 上半场0:1下半场2:1, 全场=0+2:1+1=2:2
- 3段: "上半场, 下半场, 点球大战" → 如 "1:0, 2:1, 5:4"
- 4段: "上半场, 下半场, 加时, 点球大战" → 如 "0:0, 1:1, 0:0, 5:6"
- 常规时间全场 = 上半场+下半场进球求和

### 7. 重复event_id
同一个event_id在不同天的schedule中可能出现（status从SCHEDULED→FINISHED）。
oddsfe_clean_merge.py已有RED LINE保护：历史数据不覆盖，只更新recent_days内的。
同步时需要以最新status为准。
