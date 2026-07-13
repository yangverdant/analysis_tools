---
name: cn_labels_i18n_fix
description: "分析报告英文enum泄漏修复: 新建cn_labels.py统一映射+5处插值点+前端消费*_cn字段"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## 分析报告中文化修复 (2026-07-07)

### 问题
分析报告JSON中混入英文enum: `predicted_result: "away_win"`, `confidence_level: "medium"`,
`motivation_type: "friendly"`, `gate_reason: "historical_pattern_gate"` 等.
前端只部分映射(rlMap/confCNMap), 未覆盖的就会在中文句子里显示英文.

### 修复方案: 双键保留(English key + *_cn sibling)

**Why not 直接替换成中文**: 下游逻辑(止损/归因/投注排序)依赖英文key做判断,
替换成中文会导致 `if result == "away_win"` 全部失效.

**核心文件**: `backend/app/core/cn_labels.py` — 11种映射:
- PREDICTED_RESULT_CN: away_win→客胜, draw→平局, home_win→主胜
- CONFIDENCE_LEVEL_CN: high→强烈推荐, medium→谨慎推荐, low→仅供参考, avoid→建议回避
- ADVANTAGE_CN: home→主队, away→客队, balanced→两队均衡
- LEVEL_CN: neutral→中性, slight→轻微, moderate→中等, significant→明显
- MOTIVATION_TYPE_CN: friendly→友谊赛, league→联赛, cup→杯赛, qualifier→预选赛...
- MOTIVATION_LEVEL_CN: high→高, medium→中, low→低
- COMPETITION_TYPE_CN: friendly_intl→国际友谊赛, league→联赛, cup→杯赛...
- PARTICIPANT_TYPE_CN: national→国家队, club→俱乐部
- MATCH_PHASE_CN: group_stage→小组赛, knockout→淘汰赛, final→决赛...
- GATE_REASON_CN: historical_pattern_gate→历史规律校准...
- SCENARIO_TYPE_CN: 同COMPETITION_TYPE_CN

### 5处插值点
1. `comprehensive.py:_generate_prediction_report` — predicted_result_cn + confidence_level_cn
2. `comprehensive.py` — advantage_cn + level_cn (优势描述)
3. `comprehensive.py` — motivation_type_cn + motivation_level_cn (动机描述)
4. `analyze.py:recommendation_gate` — tier_cn, base_tier_cn, reason_cn, scenario_type_cn (4种玩法)
5. `engine.py:MatchProfile.to_dict` — competition_type_cn, participant_type_cn, match_phase_cn

### 前端消费
`LotteryCenter.vue:1741` — `compLabel = mp.competition_type_cn || COMP[mp.competition_type] || mp.competition_type`
优先用 `*_cn` 字段, fallback到硬编码COMP map, 再fallback到原始英文值.

### How to apply
- 新增enum时必须同步cn_labels.py, 否则前端会显示英文原文(cn函数的default=str(value))
- 前端新增展示字段时, 优先读 `*_cn` 字段, 不要自己维护翻译map
- 见 [[automation_loop_p0_fixes]] — 同日修复的3个P0断点
