---
name: oddsfe_dedup_and_name_learning
description: oddsfe跨天重复+EN队名+POSTPONED状态3个根因修复. eid作天然唯一键+fuzzy匹配+持久化学习到teams.name_cn
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# oddsfe 跨天重复 + EN队名 + POSTPONED (2026-07-05)

## 3个根因+修复

### 1. 跨天重复 (7/5页面显示7/6比赛)
- **现象**: 7/5页面底部出现 "07-06 04:00 巴西 vs 挪威"
- **根因**: oddsfe schedule API对跨天比赛(开球时间 UTC 20:00 = 北京次日 04:00)在 7/5 和 7/6 都返回。旧逻辑用 `lottery_match_id` 作主键去重, 但 7/5 和 7/6 算出的 lottery_match_id 不同 (`202607057091` vs `202607066692`), 导致同 eid 两行
- **修复**:
  - `oddsfe_schedule_to_lottery.py` INSERT前先 `SELECT lottery_match_id WHERE oddsfe_event_id=?`, 已有则 UPDATE 而非 INSERT
  - 后端 `/api/v1/lottery/matches?date=X` 从 `BETWEEN date-1 AND date+1` 改为 `=date` (单天查询)
  - 新增 `scripts/dedup_lottery_by_eid.py`: 一次性清理现有4组跨天重复, 迁移 predictions/results/bets/analyses 到保留行

### 2. EN队名显示 (前端显示Seoul/Geoje等英文)
- **现象**: 韩职K League 1部分队显示EN ("Seoul"而不是"首尔FC")
- **根因**: teams表K-League/中超/中乙等联赛name_cn字段大量NULL。oddsfe返回"Seoul", teams表name_en="FC Seoul"有CN但精确匹配失败
- **修复**:
  - `_cn_team_name` 加fuzzy层 (Layer 4): `name_en LIKE '%input%'`, "Seoul" 匹配到 "FC Seoul" -> "首尔FC"
  - 持久化学习: `_learn_team_names_from_history` 从历史 lottery_matches (CN+eid) 反查 oddsfe schedule 学 EN->CN 映射, 写入 `teams.name_cn` (NULL时才写)
  - 数据源越跑越完善 — 每次tick学几个新映射, 不再每次重新学
- **遗留**: K League 2/Korean Cup/中乙/中甲/中超等联赛 teams.name_cn 仍大量NULL, 需外部数据源补充或手动补

### 3. POSTPONED比赛显示"已结束(待同步)"
- **现象**: 塔尔萨FC vs 萨克拉门托共和 显示"已结束(待同步)"但赛果空
- **根因**: oddsfe返回 `event_status=POSTPONED`, 但 `_supplement_results_from_oddsfe` 只处理 FINISHED, 跳过 POSTPONED 不改 sell_status, 前端仍按 selling 处理
- **修复**: 检测 POSTPONED/CANCELLED/ABANDONED/SUSPENDED 时 `UPDATE lottery_matches SET sell_status='postponed'`

## 关键设计

### oddsfe_event_id 作为天然唯一键
不用 `lottery_match_id` (按日期生成) 去重, 因为跨天比赛日期会变。用 `oddsfe_event_id` 一场一码, INSERT前先 SELECT, 已有则 UPDATE 保留原 lottery_match_id (避免破坏子表外键)。

### 持久化学习的两层
1. **临时层**: `_learn_en_to_cn_map` 在 backfill 脚本运行时学一遍 (内存里)
2. **持久层**: `_learn_team_names_from_history` + `_persist_team_name_cn` 写入 teams.name_cn (磁盘)
   - 只在 name_cn IS NULL 时写, 不覆盖已有CN
   - 同时写 team_aliases (alias_name=en, source='oddsfe_learned')
   - 下次脚本重启直接从 teams 表读, 不需要重新学

### fuzzy匹配的边界
- 输入长度 >= 3 才模糊匹配 (避免 "FC" 这种短词误匹配)
- 优先级: 精确 > alias > case-insensitive > fuzzy > EN fallback
- fuzzy用 `ORDER BY LENGTH(name_en) ASC` 选最短匹配 (最相似的)

## How to apply
- 跨天比赛的根因是 schedule API 行为, 不是 bug — 用 eid 唯一键去重
- 前端 date filter 应该是单天, 不应该返回前后1天 (前后1天只对世界杯跨时区有意义, 但 eid 唯一后不需要)
- teams.name_cn 持续完善 — 不需要一次性补全, 系统跑着跑着就学到了
- POSTPONED/CANCELLED 是数据正确状态, 不是缺失 — UI 应该展示"延期"而不是"待同步"
- 见 [[oddsfe_primary_collection_path]] — 主采集路径
- 见 [[sporttery_waf_ban]] — 为什么用oddsfe不用sporttery
