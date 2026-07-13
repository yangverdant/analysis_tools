---
name: system_health_monitoring_gaps
description: "系统健康度监控缺口: 静默失败无告警+覆盖盲区+未来驾驶舱设计"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## 系统健康度监控缺口 (2026-07-07 思考)

### 问题: 系统在运转但用户看不见

3个P0断点都存在了数天(7/4-7/7), 用户只能通过前端截图发现"15今日开售, 2已分析"。
没有任何告警告诉用户"95%的赛事因team_id缺失被跳过"或"learning-refresh exit 1两天了"。

### 当前监控能力

| 检查项 | 有无 | 发现方式 |
|--------|------|---------|
| learning-refresh exit != 0 | ✅ systemd日志 | journalctl |
| tick运行状态 | ✅ systemd日志 | journalctl |
| push_history是否写入 | ✅ DB查询 | sqlite3 |
| 分析覆盖率 | ❌ 无告警 | 前端截图 |
| team_id缺失率 | ❌ 无告警 | 静默跳过 |
| Agent LLM 503率 | ❌ 无告警 | 日志grep |
| 止损模式激活 | ❌ 无主动通知 | 被动查API |
| 数据源健康 | ✅ perceive检查 | 日志 |

### 应加的健康度检查(按优先级)

1. **分析覆盖率告警**: ✅ 已实现(2026-07-07) — tick末尾检查today+tomorrow未分析占比>30%, 写WARNING
2. **team_id缺失率**: ✅ 已解决(2026-07-07) — tick.sh集成repair脚本自动补team_id
3. **learning-refresh失败告警**: service exit != 0时, 写一条到DB的system_alerts表
4. **Agent LLM降级率**: 连续3次fallback时写warning

### 驾驶舱设计(plan里Step 1)

前端独立页面"驾驶舱", 4个标签页:
1. 实时运转 — 当前tick/learning/push状态 + 24h Timeline
2. 模型表现 — 30天准确率曲线 + 版本时间线
3. 学习进度 — 参数变更 + 熔断事件 + 场景热力图
4. 投注ROI — ROI曲线 + 止损状态 + Kelly仓位

**How to apply**: 这是UI层改进, 不影响闭环运转. 先把告警逻辑加到后端, 前端驾驶舱是锦上添花.
当前更紧急的是: 在tick.sh末尾加健康度检查脚本, 异常时写system_alerts表或发Server酱.

### 依赖

- [[automation_loop_p0_fixes]] — 刚修复的3个P0断点, 如果有告警就不会沉默3天
- [[automation_loop_design_philosophy]] — timer分工和脆弱点分析
