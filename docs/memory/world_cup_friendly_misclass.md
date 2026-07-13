---
name: world_cup_friendly_misclass
description: "sporttery/oddsfe把世界杯热身赛标为\"世界杯\", 系统误判为TOURNAMENT_INTL draw_boost=0.02偏低, 已加match_phase降级识别"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 世界杯热身赛误识别为正赛

## 发现 (2026-07-02)
- lottery_matches里league_name_cn="世界杯"的76场中, 实际都是世界杯**热身赛** (2026-06-11到07-03)
- 真正的2026世界杯正赛还未开始
- sporttery/oddsfe都不区分热身赛和正赛, 全标为"世界杯"

## 影响
- CompetitionRuleEngine把"世界杯"匹配到TOURNAMENT_INTL_KEYWORDS → tournament_intl → draw_boost=0.02
- 但热身赛实际平局率28% (76场中23平), 正赛小组赛平局率约25%, 热身赛应给更高draw_boost
- FRIENDLY_INTL draw_boost=0.08 才是正确分类

## 修复 (commit 321b5c5)
- 在engine.py classify()里加判断: TOURNAMENT_INTL + 无match_phase + is_national → 降级FRIENDLY_INTL
- 逻辑: 正赛应有明确match_phase(group/knockout/final), 无phase说明数据源没标识阶段, 是热身赛
- draw_boost从0.02提升到0.08
- tags自动加 `friendly_draw_boost`

## 测试验证
- 热身赛(无phase): → FRIENDLY_INTL draw_boost=0.08 ✅
- 正赛(group): → TOURNAMENT_INTL draw_boost=0.02 ✅
- 友谊赛: → FRIENDLY_INTL draw_boost=0.08 ✅

## How to apply
- 正赛开始后(2026世界杯具体日期), 数据源会给match_phase=group, 不会被误降级
- 如果数据源一直无match_phase, 正赛期间需要额外判断(比如时间窗口)
- 比利时vs塞内加尔(2-2平局): 此修复让draw从0.291升到0.333, 但argmax仍是away_win(0.385)
  - 需要配合赔率偏斜规则才能完全命中平局, 见 [[wc_vs_wc_friendly_rule]]
