---
name: automation_loop_design_philosophy
description: "自动化闭环的设计哲学和运维要点: 3个timer的职责分工+脆弱点+未来改进"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## 自动化闭环设计哲学

### 3个timer的职责

| Timer | 频率 | 职责 | 入口 |
|-------|------|------|------|
| football-automation-tick | ~15min | 采集+补缺+分析+验证 | run_automation_center.py --mode mixed |
| football-learning-refresh | 每日02:53 | 归因+学习+重分析 | run_automation_center.py --mode mixed --force-learning |
| football-daily-push | 每日09:00 | TOP3推送+Agent早报+止损 | daily_runner --mode push |

**设计原则**: tick做"发现+补缺", learning做"深度学习", push做"输出".
tick是轻量高频, learning是重量低频, push依赖前两者的产出.

### 脆弱点和防护

1. **team_id缺失会静默跳过分析**: `infer_action_counts`的WHERE过滤不是报错而是静默跳过.
   tick末尾覆盖率告警已加(2026-07-07). repair脚本已增强4层保护(2026-07-07 commit 1275e9b):
   unambiguous_label_match + sample_advantage保护 + mismatch_override + context_mismatch(联赛国家消歧).
   **How to apply**: 每次修改auto_gap_runner.py的WHERE条件时, 检查是否有静默过滤.

2. **补充源fail会级联杀死整个pipeline**: football_data_wc不是唯一案例.
   任何task的success=False都会让run_automation_center的failed_tasks>0,
   如果shell脚本用set -e或检查exit code就会abort.
   **How to apply**: 补充/非关键task应始终降级为warning, 不要fail.
   关键task(analysis/validation)才应该fail.

3. **push和tick是两条独立路径**: tick走automation_center, push走daily_runner.
   这意味着push的state和tick的state可能不同步(比如push时cycle_state是failed,
   但tick已经分析完了). 当前push()是自包含的(直接查DB不依赖cycle_state), 所以OK.
   **How to apply**: 如果未来push要依赖cycle_state, 需要确保tick和push共享状态.

4. **tick的--max-analysis=8限制分析吞吐**: 每天4次tick × 8 = 32场分析上限.
   对于30+场的日期可能不够. 可以根据当天未分析数动态调整.
   **How to apply**: 考虑在tick.sh中加 `--max-analysis $(max 8, 未分析数/4)` 逻辑.

5. **oddsfe同步→team_id修复→分析 有顺序依赖**: tick.sh已按顺序跑
   oddsfe_schedule→eid_backfill→**repair_team_id**→results_supplement→spf_backfill→sporttery→automation_center.
   team_id修复已集成(2026-07-07 commit a630ffe), 不再需要手动跑repair脚本.

6. **分析覆盖率告警**: tick.sh末尾检查today+tomorrow未分析占比>30%, 输出WARNING到日志(2026-07-07 commit a630ffe).

### 未来改进方向

- ~~**team_id自动解析**: oddsfe同步时直接用team_aliases/teams表匹配, 不要事后repair~~ → 已在tick.sh中集成repair(2026-07-07)
- ~~**分析覆盖监控**: tick末尾检查"今日未分析占比", >30%时打warning到日志~~ → 已实现(2026-07-07)
- **推送渠道激活**: Server酱/邮件渠道已有代码但未配置环境变量, 用户想收到推送时配即可
- **Agent LLM稳定性**: 讯飞中转503频繁(今日3次), Agent早报fallback到规则化兜底已OK,
  但止损决策也依赖LLM, 应考虑止损也加规则化兜底
- **前端驾驶舱**: 见[[system_health_monitoring_gaps]]
