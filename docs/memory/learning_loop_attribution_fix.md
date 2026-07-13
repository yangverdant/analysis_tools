---
name: learning_loop_attribution_fix
description: "学习闭环归因断点修复: run_validation只调_validate_predictions漏掉_attribute_failures+_settle_bets"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## 学习闭环归因断点修复 (2026-07-08)

### 问题: learning-refresh产生0参数变更

`run_automation_task.py`的`run_validation()`直接导入`_validate_predictions`，
跳过了`validate()`编排器中的`_attribute_failures`和`_settle_bets`两个关键步骤。

**根因链**:
1. `run_validation`只调`_validate_predictions` → `lottery_validation.attribution`始终为NULL
2. 归因为NULL → `attribution_driven_learning`的`analyze_attribution_patterns`查不到归因数据
3. 无归因数据 → 0个可执行模式 → 0项参数调整 → `model_params_history`无新记录

**影响**: 7/3-7/8共5天, 178条错误预测的归因为NULL, 学习闭环完全中断。

### Fix: `run_validation`改为调用完整`validate()`编排器

修改`run_automation_task.py:311-324`:
- 旧: `from validate import _validate_predictions; result = _validate_predictions(db, dates)`
- 新: `from validate import validate; result = validate(state=None, db_path=db, agent=agent)`

`validate()`完整流程: oddsfe同步→结果获取→回填→验证→**归因**→**结算**

同时修改`validate.py`返回值, 增加`attributed`和`settled`字段供automation_center追踪。

### 验证结果

手动运行`_attribute_failures(skip_agent=True)`: 110条归因成功, 0条NULL剩余。
归因分布: low_confidence_noise:211, close_match:151, goal_axis_misread:95, half_time_axis_misread:50, model_overconfidence:23

运行`run_attribution_driven_learning`: 24个模式, 4项调整写入model_params_history:
- bqc_ht_transition_league重算(18样本)
- bqc_ht_transition_international_cup更新(51样本)
- 2个flag_tournament_rule_review(friendly_intl bf/ou)

### Why: 自动化闭环完整性

之前"学习0变更"不是learn.py的bug, 而是上游validate步骤不完整导致归因数据缺失。
修复后, 每次tick的validation任务都会自动执行归因+结算, 学习闭环恢复。

### How to apply

无需额外操作, tick自动调用`run_validation`, 其中已集成完整`validate()`。
如果需要手动触发归因: `validate(state=None, db_path=db, agent=None)`。

### 依赖

- [[automation_loop_p0_fixes]] — team_id修复后分析全覆盖
- [[intelligence_gap_pipeline_fix]] — 情报采集管道断点修复
- [[automation_loop_design_philosophy]] — tick的validation步骤在wave 7执行
