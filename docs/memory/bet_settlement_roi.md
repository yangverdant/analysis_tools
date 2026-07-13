---
name: bet_settlement_and_roi
description: bet_records结算闭环+ROI追踪+推送渠道扩展
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## 本轮完成的改进

### 1. bet_records结算闭环
- validate.py添加`_settle_bets()`: 匹配lottery_results, 计算win/lose/payout/profit
- clv_update.py也调用结算(14点上午比赛可能已有结果)
- push.py修改stake: 从0改为100*min(kelly,0.25)或默认100元
- push.py止损查询改为直接用profit列(不再重新计算)

### 2. 投注ROI API
- `/api/bets/roi` — 7d/30d/all ROI统计+最近20笔记录
- `/api/bets/settle` (POST) — 手动触发结算
- AccuracyDashboard.vue添加投注追踪面板(3卡片ROI+明细列表)

### 3. 推送渠道扩展
- push_channels.py添加`send_email()` — SMTP邮件推送(SSL/TLS)
- api_keys.yaml添加email配置模板
- push_to_all_channels()新增邮件渠道

### 4. Draw校准注入
- analyze.py添加`_calibrate_draw()` — 基于warmup校准5档赔率区间历史平局率
- 保守策略: 注入70%差距, cap 45%, 重归一化

### 5. DailyCycle前端增强
- 添加投注ROI显示(7d/30d/all)
- 添加定时任务状态显示
- 修复cycle/status API: 正确读取daily_cycle_state列格式
