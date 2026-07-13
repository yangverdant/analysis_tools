---
name: scenario-advantage
description: 模型信息差场景分析结果 — CLV+动机同向场景有正ROI
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

模型在哪些子集有真正的预测优势（13993场历史数据验证）

## 已验证的优势场景

**CLV+动机同向（最强信号）：**
- 定义：abs(CLV)>0.03 AND abs(动机差)>0.3 AND CLV×动机差>0
- 全量：argmax=55.6%, 开盘ROI=+5.6%, 闭盘ROI=+3.9%
- 测试集(2024-08后)：开盘ROI=+5.8%, 闭盘ROI=+4.2%
- 逻辑：赔率调整方向与战意一致 → 市场确认了基本面信息

**五大联赛+CLV>0.05：**
- argmax=54.8%, 数据质量更高

**动机差>1.0：**
- argmax=55.9%, 争冠/保级战意差明显

## 已验证的无效场景

- 模型反对赔率方向：准确率33.1%（模型几乎总是错的）
- 纯信号覆盖无基本面：无信息差
- EV>0但无CLV/动机确认：开盘ROI仍为负

## 基线数据

- 整体argmax: 50.2%
- 开盘赔率argmax: 49.3%
- 闭盘赔率argmax: 50.6%
- 整体Brier: 0.6046

## v3.2权重（逻辑回归学习）

euro_odds=0.28, odds_movement=0.10, prediction=0.10, elo_rating=0.08, h2h=0.04, motivation=0.04

**Why:** 用sklearn LogisticRegression从13993场历史数据学习，发现euro_odds占28%，standing/form几乎无用(2%/1%)
**How to apply:** 在CLV+动机同向的场景中，增大调整幅度（scenario_boost最多4%）
