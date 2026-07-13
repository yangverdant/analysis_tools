---
name: bqc_empirical_transition
description: "BQC经验转移矩阵+始终SPF轴约束改进: 34.2%→35.8%, Brier 0.809→0.797"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## BQC改进 (2026-06-30)

### 问题
BQC准确率33.1%, 远低于目标45%. 根因:
1. marginal_product(corr=1.5, anti_corr=0.7)校准偏差大: 33低估9.2pp, 10高估6.5pp
2. axis_trusted门控导致45%的比赛跳过SPF轴约束, 这些比赛BQC准确率0%

### 修复
1. **经验转移矩阵**: 用30K场比赛的P(FT|HT)替代P(FT)*corr
   - P(FT=3|HT=3)=77.6%, P(FT=1|HT=1)=40.1%, P(FT=0|HT=0)=68.0%
   - Brier: 0.8089→0.7970(-0.0119)
2. **始终SPF轴约束**: 移除axis_trusted门控, 所有BQC推荐必须匹配SPF全场方向
   - argmax: 34.2%→35.8%(+1.6pp)
3. **一致性函数**: 移除bqc_axis_threshold_not_met跳过逻辑

### BQC argmax上限
- SPF=3时: 33=60.8%, 13=34.9%, 03=4.2% (9类问题, argmax天花板~36%)
- 要达到45%+需要: 改进SPF准确率(当前57.6%)或增加半场预测精度
- **Why**: 9类分类中argmax自然倾向majority class, 即使完美概率模型argmax也只有~36%
- **How to apply**: BQC提升需从SPF/半场预测入手, 非BQC本身

### 文件
- `backend/app/core/analyze.py`: _compute_bqc() + axis constraint
