---
name: bqc-hh-zero-root-cause-fix
description: BQC hh=0.0根因修复 — 坏scene transition+stability reuse级联
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

**问题**: BQC预测中24+2场比赛`hh=0.0`，导致dh过度推荐，7天BQC准确率仅14.5%。

**根因链**:
1. `attribution_driven_learning.py`的`_apply_ht_transition_recompute`写入sample_count=15的league transition（h→h=0.0），旧代码无sanity check
2. `_load_scene_ht_transition`旧版无sample_count和合理性检查，直接接受h→h=0.0的transition
3. `_compute_bqc`用坏transition算出hh=0.0，推荐变成dh
4. `_apply_bqc_stability_reuse`从旧报告加载坏BQC（hh=0.0），替换新计算的正确结果（hh=0.32）

**修复**:
1. 删除model_params_history中3条坏transition（league sample=15/18, international_cup a.a=0.375）
2. `_load_scene_ht_transition`已有sanity check（sample>=30, h.h>=0.40, a.a>=0.40）
3. `attribution_driven_learning.py`新增同样的sanity check，防止再写入坏数据
4. `_apply_bqc_stability_reuse`新增：当current hh>0但previous hh=0时跳过（previous是坏数据）

**结果**: hh=0.0从26个降到0个，BQC推荐分布从dh=36→17, hh=39→71
