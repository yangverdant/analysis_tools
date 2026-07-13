---
name: attribution_driven_learning_bridge
description: "learn.py原只消费market_wrong归因, 新增attribution_driven_learning.py消费8类归因生成针对性调整, 集成到learn()step11"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 归因驱动学习闭环

## 发现 (2026-07-02)
- `learn.py` 的 `learn()` 只在 `compute_odds_baseline` (line 412) 用 `market_wrong` 归因推算赔率基线
- 其它7类归因(low_confidence_noise/model_overconfidence/close_match/half_time_axis_misread/goal_axis_misread/market_misread/tournament_context_misread)全部浪费
- scene-based loop只看"scene准确率<赔率基线→降权重", 不知道"为什么错"
- 结果: circuit_break反复触发同一scene (league_club_spf/ou/bqc), 但权重只降不升, 无法修复

## 修复: attribution_driven_learning.py

### 8类归因→5种调整动作映射
| attribution | action_type | 说明 |
|---|---|---|
| low_confidence_noise | raise_confidence_threshold | prob<0.5仍预测, 提高阈值 |
| model_overconfidence | reduce_high_prob_calibration | prob>=0.65但错, 降high-prob乘数 |
| half_time_axis_misread | flag_ht_transition_issue | bqc HT方向错, flag给后续模块 |
| goal_axis_misread | flag_xg_calibration_issue | ou进球轴错, flag给xG模块 |
| market_misread | increase_odds_blend | 模型未跟随赔率, 提高blend权重 |
| tournament_context_misread | flag_tournament_rule_review | 场景规则需复核 |
| close_match | None | inherent uncertainty, 不可调 |
| market_wrong | None | 模型对赔率错, 不调 |

### 主入口
`run_attribution_driven_learning(db_path, days=30, agent=None)`
- `analyze_attribution_patterns`: 按(scene, play_type)分组统计
- `apply_attribution_driven_adjustments`: 写入model_params_history, 已应用的不重复

### 集成位置
`learn.py` step 11, 在概率校准(step 10)后, 最终commit前.
通过 `conn.commit()` 释放写锁, 用新连接调用.

## 服务器测试 (2026-07-02 17:45)
- patterns_found=15, adjustments=7
- spf_confidence_threshold: international_cup 0.4→0.5 (20条low_confidence_noise, avg_prob=0.45)
- flag_ht_transition: bqc league(9) + international_cup(31) = 40条HT误判
- flag_xg_calibration: ou league(36) + international_cup(28) = 64条进球轴误判
- flag_tournament_rule_review: friendly_intl ou(6) + bf(5)

## How to apply
- 归因数据是宝贵反馈, 不能只落库不消费
- 新归因类型加入时, 在`_determine_action`加映射分支
- flag类调整(HT/xG/tournament)是占位, 后续需专门模块读取flag真正调参
- model_params_history的param_name后缀`_attribution`区分常规调整
- 已应用的调整不重复(suggested <= current 跳过)

## 升级 (2026-07-02 第二轮)
flag从"只记录"升级为"可执行":
1. **HT transition重算**: `half_time_axis_misread` → LEFT JOIN lottery_results取HT/FT goals → `_compute_scene_transition`按场景统计P(FT|HT) → 写入`bqc_ht_transition_{scene}_attribution` (JSON)
   - `_compute_bqc`运行时通过`_load_scene_ht_transition`读取, 优先用scene-specific transition替代全局empirical matrix
   - sample<8时降级为flag(数据不足)
2. **OU lambda缩放**: `goal_axis_misread` → `_compute_ou_lambda_scale`从失败case计算实际总进球/预测线 → 写入`ou_lambda_scale_{scene}_attribution` (float, 0.80-1.20)
   - `_load_scene_ou_lambda_scale`读取器已就位, 但OU主流程尚未注入(留给后续)

## 服务器实测结果 (2026-07-02 18:00)
- league/ou: lambda_scale 1.0→0.8 (36条大球预测错实际小球)
- international_cup/ou: lambda_scale 1.0→0.8 (28条)
- league/bqc: transition重算 (15有效样本, HT=h→a=1.0小样本噪声)
- international_cup/bqc: transition重算 (52样本, HT=a→FT=h=26.7% vs empirical 11.1%, 世界杯半场客胜翻盘率2.4倍)
- international_cup/spf: confidence_threshold 0.4→0.5 (20条low_confidence_noise avg_prob=0.45)
- friendly_intl: 2 tournament_rule_review flag
- analyze_single运行验证: bqc使用scene transition正常输出
