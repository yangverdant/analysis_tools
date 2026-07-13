---
name: attribution_priority_fix
description: "low_confidence_noise误判spf正常概率为噪声. 修复: market_misread优先, 收紧low_confidence条件到conf<0.35"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 归因优先级修复 (2026-07-03)

## 发现
- 7月1-3日74条翻车, low_confidence_noise占37条(50%)
- 抽样发现 spf|international|conf=0.48 但 prob=0.692 — confidence低但预测概率高
- 多数是 pred=3 actual=0 (反向猜错), 本应是 market_misread

## 根因
`_determine_attribution` 第1条规则过于激进:
```python
is_low_conf = (confidence > 0 and confidence < 0.35) or (confidence_level == 'low' and confidence > 0 and confidence < 0.5)
```
- 对spf三选一, 0.35-0.43是正常概率(不是低置信)
- `confidence_level=='low'` 这条路径把 [0.35, 0.43) 的spf误判为low_confidence_noise
- 真正的反向猜错(market_misread)被淹没

## 修复
### validate.py _determine_attribution 顺序调整
1. **market_misread 优先**(赔率方向对、模型反了) — 在low_confidence_noise之前
   ```python
   odds_direction = _get_odds_direction(conn, match_id)
   if odds_direction and odds_direction == actual and predicted != actual and play_type == 'spf':
       return {'level': 'market_misread', ...}
   ```
2. **收紧 low_confidence_noise**: 只在 `confidence < 0.35` 触发, 去掉 conf_level=='low' 冗余路径

## 重跑效果 (74条翻车)
- 22条改变归因
- low_confidence_noise: 37→28 (-9)
- market_misread: 1→3 (+2)
- close_match: 6→12 (+6, 中等概率方向对的case)
- model_overconfidence: 8→10 (+2)
- goal_axis_misread: 9→12 (+3)
- half_time_axis_misread: 4→8 (+4)

## How to apply
- 归因优先级很重要: 越具体的归因越优先, 越泛化的越靠后
- spf三选一, 0.35-0.43是正常概率, 不是噪声
- 反向猜错(pred=3 actual=0)本质是 market_misread, 不是low_confidence_noise
- 重新归因脚本: 直接调 `_determine_attribution(conn, failure)` 然后 UPDATE
- 见 [[attribution_driven_learning_bridge]] — 归因驱动学习的前提是归因正确
- 见 [[attribution_hang_fix]] — 归因循环的稳定性保障
