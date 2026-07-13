---
name: disagreement_boost_finding
description: 模型-赔率分歧时模型75%正确，实现disagreement boost
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## 核心发现

当模型argmax与Pinnacle赔率argmax不一致时(32个案例):
- **模型正确: 75% (24/32)**
- **赔率正确: 0% (0/32)**
- 0次模型预测draw而赔率预测其他 — 模型价值在于识别爆冷/主场优势, 不是平局

## 229K回测结论
- Pinnacle赔率argmax准确率: 54.14% (229,906场)
- 2.00-3.00区间: 41.38%, 平局率27.6%
- **纯赔率子区间不存在正draw edge** — Pinnacle平局定价非常准确
- 简单阈值draw策略不work, ROI全部为负

## 实现的改进
- analyze.py添加`_apply_disagreement_boost()`: 模型与赔率分歧时, 模型方向概率+15% gap boost
- 置信度升级: medium→high, low→medium
- boost信息写入model_vs_odds.disagreement_boost字段
- 效果: home_win 0.45→0.532, 提升Kelly投注比例和推送推荐强度

## Why
赔率对大众比赛定价准确, 但模型通过综合因子(Elo+form+动机+赛事类型)能发现赔率结构性偏误(尤其友谊赛/杯赛的轮换和动机), 这些是纯赔率无法捕捉的。
