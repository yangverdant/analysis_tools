---
name: bqc_accuracy_improvement_v2
description: "BQC准确率改进v2: 禁用phase_axis_adjustment, 回测对比6种策略结果"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## BQC准确率改进实验(2026-07-09)

### 核心发现: phase_axis_adjustment是负优化

7月回测(74场比赛):
- Report推荐(含后处理): 21.6%
- Simple argmax from probs: 24.3%
- Raw argmax (half_time×transition, no axis): 27.0%
- "Always hh": 25.7%

phase_axis_adjustment分析: 12次改变推荐, 0帮助5伤害, 净-5。它把正确的hh改成dh(因为half_draw高)，但实际结果仍是hh。

### 已禁用的改动(经验证无效或有害)
1. **贝叶斯校准推荐** (model_prob/prior选最大): 准确率从27%降到10.8%
2. **SPF轴约束释放** (当约束池<无约束池×0.7): axis=23% > no_axis=10.8%
3. **Transition v2** (h→h从0.762降到0.71): 准确率从27%降到24.3%
4. **均衡化** (hh>0.25时转移15%): 在轴约束内无效果

### 已保留的改动
1. **禁用phase_axis_adjustment**: `if False and axis_target and constrained_probs:` + `result.pop('phase_axis_adjustment', None)`
2. **stability_reuse中清除phase_axis**: `preserved.pop('phase_axis_adjustment', None)`

### 根本问题
BQC是9选1，即使模型完美概率，argmax也很难命中。"Always hh"(23%)和模型(27%)差距只有4pp。真正的提升需要更好的半场概率模型，而非推荐逻辑调整。
