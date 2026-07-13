---
name: dedup_root_cause_fix
description: "比赛重复+时差bug根因: sporttery-era与oddsfe-era生成不同lottery_match_id, DAO只按PK去重导致重复. 修复3层: DAO按(home,away,date)跨源去重+eid_backfill同步beijing_time+dedup脚本迁移child行"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 比赛重复+时差根因修复 (2026-07-06)

## 根因
sporttery 和 oddsfe 为同一场比赛生成**不同**的 lottery_match_id:
- sporttery: `match_date + sporttery_match_num` (例: `202607061093` 葡萄牙vs西班牙)
- oddsfe: `beijing_date + eid[-4:]` (例: `202607078290` 同一场)

`LotteryMatchDAO.insert` 只用 PRIMARY KEY (lottery_match_id) 去重 (`INSERT OR IGNORE`)。两源 ID 不同 → 两行都插入 → 体彩中心显示重复比赛, 且 sporttery-era 行保留错误的 beijing_time (sporttery 时区处理有 bug)。

## 三层修复

### 1. DAO 跨源去重 (lottery_dao.py)
`LotteryMatchDAO.insert` 开头加查询:
```python
existing_row = cursor.execute(
    "SELECT lottery_match_id FROM lottery_matches "
    "WHERE home_team_cn = ? AND away_team_cn = ? AND match_date = ? LIMIT 1",
    (match['home_team_cn'], match['away_team_cn'], match['match_date'])
).fetchone()
if existing_row:
    # UPDATE existing row, don't insert new
```
这样 sporttery 尝试插入时, 若 oddsfe 已有同场, 只 UPDATE 不 INSERT, 杜绝新增重复。

### 2. eid_backfill 同步 beijing_time (oddsfe_eid_backfill.py)
原 UPDATE 只设 `oddsfe_event_id, league_name_cn`, 不修 `beijing_time/match_date/match_time`。导致 sporttery-era 行配对到 eid 后, 仍保留错误的 sporttery 时间。

修复: 用 oddsfe `event_start_at` (UTC+8) 重算 beijing_time 并 UPDATE:
```python
bj = _to_beijing_time(start_at)
if bj:
    new_date, new_time = bj[:10], bj[11:19]
    UPDATE ... beijing_time=COALESCE(?,beijing_time), match_date=COALESCE(?,match_date), match_time=COALESCE(?,match_time)
```

### 3. 一次性 dedup 脚本 (dedup_lottery_matches.py)
按 `oddsfe_event_id GROUP BY HAVING COUNT(*)>1` 找重复对, 取 beijing_time 更完整的行为 canonical, 把 child 行 (lottery_odds/results/predictions/validation/bet_records 等 12 张表) 从 dupe 迁移到 canonical, 然后 DELETE dupe。

## 修复时遇到的坑
- dedup 跑完后 sporttery tick 立刻又重建 dupe 行 — 因为 DAO 还没修。必须先部署 DAO 修复, 再 dedup。
- 2 行没 eid 的 sporttery-era 数据 (USA vs Belgium, Bromma vs GAIS) 因 match_date 错误 (sporttery 记 7/6, 实际 7/7), eid_backfill 按 match_date 查 oddsfe schedule 找不到 — 需手动跨日查找。后续可让 eid_backfill 在 match_date 找不到时 fallback 到 ±2 天查 schedule。

## How to apply
- DAO 修复是预防: 任何 sporttery 残余运行不会再造重复
- eid_backfill 修复是治本: 即使有遗留 sporttery-era 行, 一旦配对 eid 会自动同步正确时间
- dedup 脚本是清理历史: 一次性运行即可, 不需要周期调用
- sporttery WAF 已确认彻底封禁 (crawled=0), 但 `cloud_tick_sporttery_sync.py` 保留作 fallback 不删
- 见 [[oddsfe_primary_collection_path]] — oddsfe 是永久主源
- 见 [[sporttery_waf_ban]] — sporttery 不再用作真实在售清单
