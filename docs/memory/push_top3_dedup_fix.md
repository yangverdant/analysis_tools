---
name: push_top3_dedup_fix
description: "推送TOP3全是同一场比赛的bug — _get_today_predictions没过滤is_stale也没去重, 每场累积75-92份重复报告"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 推送TOP3重复场次bug

## 发现 (2026-07-02)
- push_history表里top3_json的3个item都是同一场比赛(美国vs波黑), 只是prob略不同(0.5563/0.5444/0.5442)
- 根因: automation定时器每15分钟跑一次analyze, `_save_report`用INSERT OR REPLACE生成新行
- 每场累积75-92份prediction报告(is_stale=1标记旧报告, is_stale=0是最新的)
- 但 `_get_today_predictions` 查询没过滤is_stale, 也没去重
- 导致6场比赛返回约500份预测, `_rank_value_bets`按edge排序后TOP3都是同一场的不同报告

## 修复 (commit 848fdb9)
- SQL加 `AND (ar.is_stale = 0 OR ar.is_stale IS NULL)` 过滤
- SQL加 `ORDER BY ar.lottery_match_id, ar.created_at DESC` 按场次分组+最新优先
- Python层加 `seen_matches` set 按 lottery_match_id 去重

## 验证
- 修复前: 6场返回500+份预测, TOP3全是美国vs波黑
- 修复后: 6场返回6份预测, TOP3=英格兰/美国/法国 三场不同比赛

## How to apply
- `_save_report`用is_stale标记旧报告但不清除, 设计上是保留历史用于回溯
- 查询lottery_analysis_reports时**必须**加is_stale=0过滤
- validate.py已有`_active_report_filter`封装, push.py直接抄了类似逻辑
- 其他地方查询该表也要检查: backtest.py/analyze.py的几处查询
