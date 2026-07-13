---
name: model_version_history
description: "模型版本演进链 v3.0→v3.9.2→v3.11: 各版本核心改动+验证数据+关键教训"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## 模型版本演进链 (合并自v3.2~v3.11共9条记忆)

### v3.2 — 回归权重+动机数值+场景增强
- Combined=52.6%, 场景权重增强后1000场53.2%, Brier 0.575, +3pp vs v3.0

### v3.3 — 赔率平局≥30%规则+南美杯冷门区
- Brier 0.5748, Draw recall 30%, 16场实战68.8%

### v3.4 — 全球冷门区1.25-1.35+赛季末1.15-1.25
- 83场实战验证, Brier 0.5747

### v3.6 — 动机不对称方向修正(强化主胜), CUP阈值1.40
- argmax+0.07pp, Brier-0.0001

### v3.8 — draw_threshold大幅削减(dt30 0.05→0.01)
- argmax+0.47pp, Brier-0.0005, 净+66场

### v3.9.1 — cup+prima减draw, 分联赛调优
- 50.55%, Brier 0.6033, net+124

### v3.9.2 — 赛季末均衡draw回调
- 50.55%, Brier 0.6032, net+124 **(当前生产版本)**

### v3.11 — 均衡draw boost分档验证
- v3.11=3/9反而差于v3.9.2=4/9, 均衡只做辅助信号, 未采纳

---

## 关键教训

1. **draw_threshold削减是最有效的单一改动**(v3.8 +0.47pp), 但118K场draw threshold全亏(见[[disagreement_strategy_fix]])
2. **均衡draw boost分档反而更差**(v3.11), 过度调优overfit
3. **模型-赔率分歧时模型38.5%赔率50%**(v3.9), 从boost模型改为blend 30%赔率
4. **规则调整必须先DB数据验证方向**(见[[feedback_data_driven_rules]]), 不能凭直觉

## 当前状态

生产版本: v3.9.2, 准确率50.55%, Brier 0.6032
分玩法目标: SPF达标, OU/BQC未达标(见[[reanalysis_model_version_review]])
