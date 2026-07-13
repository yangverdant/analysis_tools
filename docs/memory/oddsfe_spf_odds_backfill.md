---
name: oddsfe_spf_odds_backfill
description: "sporttery WAF后用oddsfe 1X2 Pinnacle赔率转spf格式写入lottery_odds的治本方案, 63/63全覆盖"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# oddsfe → lottery_odds.spf 适配器 (2026-07-05)

## 背景
sporttery lottery API WAF-ban后, 通过 oddsfe_schedule_to_lottery.py 采集的赛事没有 spf 赔率(只有 lottery_matches 行, 无 lottery_odds 行)。导致前端"缺赔率"红标, _rank_value_bets 无法算价值投注, ROI 跟踪跳过这些场。

## 治本方案
oddsfe 的 `/events/{eid}` HTML 端点(经 `oddsfe_realtime_detail_v2.parse_event_odds_v2` 解析)返回 `1X2_prematch_lines` 字段, 格式:
```
:home/draw/away:moid|PINNACLE:h:d:a:time;BK2:h:d:a:time;...
```
转 sporttery spf 格式: `{"3": home, "1": draw, "0": away}` 写入 `lottery_odds` 表, `snapshot_type='current'`.

## 关键设计
- 优先用 PINNACLE 赔率(最锐), 没有则用 summary line 的 `:h/d/a`
- 幂等(INSERT OR IGNORE), 不覆盖 sporttery 已有 spf 行
- 同时写 `play_types = '["spf"]'` 让前端识别该玩法可用
- 只覆盖 0/1/2 三天 + 有 oddsfe_event_id 的场 — 不影响历史数据

## 文件
- `scripts/oddsfe_spf_odds_backfill.py` — 主脚本
- 已接入 `cloud_automation_tick.sh` 在 `oddsfe_results_supplement.py` 之后
- 每 tick 都跑, 新比赛自动覆盖

## 验证(2026-07-05)
- 7/5+7/6+7/7 共 63 场, 跑两次后 63/63 全有 spf 赔率
- 唯一漏掉的: sporttery 历史遗留的无 oddsfe_event_id 行(不在 oddsfe 覆盖范围)

## How to apply
- sporttery WAF 期间这是 spf 赔率的主路径
- 只补 spf — rqspf/ttg/bf/bqc 暂不补(无对应源, sporttery 专属玩法)
- 见 [[oddsfe_primary_collection_path]] — 主采集路径
- 见 [[sporttery_waf_ban]] — 为什么不用 sporttery
- 见 [[oddsfe_dedup_and_name_learning]] — 配套的队名学习机制
