---
name: record_bets_dedup_fix
description: "_record_bets用date('now')UTC清理pending导致北京时间跨天失效, 同一场被多次daily_cycle重复投注, 历史69条删42条重复"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# _record_bets 重复投注bug

## 发现 (2026-07-02)
- bet_records里202607013082(美国vs波黑)有15条pending重复投注
- 历史数据: 69条总记录, 42条是重复(同lm_id+play_type+selection), 只有27条独立
- 旧逻辑 inflated 了ROI: 旧+20.8% → 清理后 +10.5% (spf仍+20.8%, 但rqspf -62.1%)

## 根因
```python
# 旧代码 — 清理逻辑用UTC时间
cursor.execute("""
    DELETE FROM bet_records WHERE result = 'pending'
    AND lottery_match_id IN (
        SELECT lottery_match_id FROM lottery_matches WHERE match_date = date('now')
    )
""")
```
- `date('now')` 是UTC, 北京时间7-2凌晨0-8点的比赛, UTC是7-1 16-24点
- 当daily_cycle在7-2 00:30触发push时, `date('now')`='2026-07-01', 但比赛match_date='2026-07-02'
- 删除条件不匹配 → 旧pending没清理 → 又INSERT新的 → 累积重复

## 修复
```python
# 新代码 — 按(lm_id, play_type, selection)存在性检查
existing = cursor.execute("""
    SELECT id FROM bet_records
    WHERE lottery_match_id = ? AND play_type = ? AND selection = ?
    LIMIT 1
""", (lm_id, play_type, str(selection))).fetchone()
if existing:
    continue  # 已存在(不管pending还是已结算)都跳过
```

## How to apply
- bet_records去重不能依赖时间戳, 必须用业务唯一键(lm_id+play_type+selection)
- 一场比赛一个玩法只投一次, 后续daily_cycle刷新预测不重复投注
- 已结算的也保留, 不被新投注覆盖
- 若想重新投注(比如预测大幅变化), 需要先手动DELETE旧记录

## 今日rqspf表现 (2026-07-02, 5场)
- 美国vs波黑 让平 odds=3.5 → 实际让胜 → lose
- 法国vs瑞典 让负 → 实际让胜 → lose
- 科特迪瓦vs挪威 让胜 → 实际让平 → lose
- 比利时vs塞内加尔 让负 odds=1.64 → 实际让负 → win +16
- 墨西哥vs厄瓜多尔 让负 → 实际让胜 → lose
- 1胜4负, -67元. 世界杯热身赛冷门多, rqspf让球盘风险大, 样本小不结论.
- 见 [[bet_diversification_fix]] — _rank_value_bets多玩法选择的前置修复
