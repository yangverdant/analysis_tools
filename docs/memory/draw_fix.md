---
name: draw-fix
description: 增强线性模型平局预测修复：从加法公式改为指数衰减，弱信号时draw概率最高
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

# 模型平局预测修复

## 问题

enhanced_linear模型0%预测平局。旧公式 draw先验0.28 < away先验0.30，平局永远排第三。

## 修复方案

从加法公式改为指数衰减模型：
- `draw_prob = DRAW_PEAK * exp(-|signal| / DRAW_DECAY)`
- 弱信号(signal≈0)时draw≈0.32最高，强信号时快速衰减到接近0
- 剩余概率按home/away基础比例分配

## 参数

```
HOME_PRIOR = 0.44
DRAW_PEAK = 0.32
AWAY_PRIOR = 0.30
SIGNAL_SCALE = 2.5
DRAW_DECAY = 0.06
```

## 效果

| signal | home | draw | away | 预测 |
|--------|------|------|------|------|
| 0.00   | 0.40 | 0.32 | 0.28 | draw |
| ±0.02  | 0.46 | 0.23 | 0.31 | home/away |
| ±0.05  | 0.50 | 0.14 | 0.36 | home/away |
| ±0.10  | 0.59 | 0.06 | 0.35 | home/away |

预期：约5-8%的比赛被预测为平局（signal在±0.02以内），接近实际25%平局率中的高置信部分。

## Why

旧公式 draw_prob = DRAW_PRIOR - draw_adj + home_adj*0.1，draw先验永远低于away，数学上不可能成为最大值。新模型让"接近的比赛→平局最可能"符合足球直觉。

## How to apply

修改 `fetchers/analysis/models/enhanced_linear.py` 中的概率映射部分，已实现。需重跑 `run_analysis_batch --force --model enhanced_linear`。