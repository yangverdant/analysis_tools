---
name: attribution-coverage-and-team-id-fix
description: 归因覆盖率25%→95%+team_id自动匹配+_find_team_id+回填上限50→500+206场历史回填
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 2026-07-13 归因+team_id修复

## 归因覆盖率从25%→95%
- 根因: _attribute_failures回填LIMIT 50条 + 10分钟Agent时限 → 545条翻车永远得不到归因
- 修复: LIMIT 50→500, 规则引擎归因极快(<1ms/条), Agent时限只影响Agent增强部分
- 手动批量归因: 529条翻车 + 631条正确 = 1160条归因, 仅用<1秒
- 归因分布变化: goal_axis_misread 67→305, model_overconfidence 10→141, tournament_context_misread 16→112

## team_id自动匹配
- 根因: oddsfe采集只填home_team_cn/away_team_cn, 不填home_team_id/away_team_id → analyze_single跳过(需team_id)
- 修复: 新增_find_team_id()函数, 4层查找: EN精确→CN精确→别名→EN模糊
- _derive_match_fields返回值新增home_team_id/away_team_id
- INSERT/UPDATE均包含team_id字段(用COALESCE保留已有值)
- 206场历史比赛回填team_id, 未来比赛team_id覆盖率75%→99%

## 归因驱动学习闭环激活
- 529条新归因驱动了更多学习调整:
  - BQC HT→FT transition重算(33条HT方向错误, 样本44→58)
  - continental_cup SPF high_prob_multiplier 1.0→0.92(11条overconfidence)
  - domestic_cup O/U lambda缩放 1.2→0.8(11条进球轴错误)
  - 友谊赛tournament_context_misread flag(4个玩法共57条)
