---
name: windowa-clv-validate-learn
description: 窗口A完成—CLV赔率更新(oddsfe)+validate(oddsfe备选结果源+去重+概率推导recommended)+learn闭环
metadata:
  node_type: memory
  type: project
  originSessionId: continued
---

## 窗口A完成状态

### 已改文件

| 文件 | 改动 |
|------|------|
| `backend/app/core/validate.py` | 添加`_sync_results_oddsfe`备选结果源+验证去重+概率推导recommended |
| `core/competition/engine.py` | 修复WC_QUALIFIER优先于TOURNAMENT_INTL关键词匹配 |

### validate.py关键改动

1. `_sync_results_oddsfe`: oddsfe schedule API获取已完赛比分, event_winner(0=主/1=平/2=客)→体彩(3/1/0), 通过oddsfe_event_id或队名匹配
2. validate()主函数: sporttery失败后自动fallback到oddsfe
3. `_save_validation`: 写入前先DELETE同match_id+play_type旧记录(去重)
4. `_validate_predictions`: recommended为空时从probabilities推导(max key → recommended)

### engine.py关键改动

1. `_classify_by_keywords`: WC_QUALIFIER检查移到TOURNAMENT_INTL之前
2. "世界杯预选赛"→wc_qualifier(而非tournament_intl)
3. "世界杯"仍正确→tournament_intl

### 未修改但验证通过的文件

- `clv_update.py`: 已正确使用oddsfe + snapshot_type='midday', detect_clv_signal工作正常
- `learn.py`: 依赖validate输出, 闭环可运行, compute_scene_accuracy/backtest/apply_weight_change全链路OK
- `daily_runner.py`: 9个handler全注册, run_mode各模式可用
- `state_machine.py`: 状态持久化到daily_cycle_state, 断点可恢复

### 验证结果
- sporttery结果API不可用(567/代理错误) → oddsfe备选自动切换 ✅
- validate 3场验证100%准确率 ✅
- learn 0调整0熔断(样本少+准确率高) ✅
- daily_cycle_state持久化 ✅
- model_accuracy表更新 ✅
