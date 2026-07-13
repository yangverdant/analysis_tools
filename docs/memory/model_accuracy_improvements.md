---
name: model-accuracy-improvements
description: "Enhanced Linear Model accuracy optimization history, v3.1+CLV results, and EV analysis"
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## Enhanced Linear Model 优化历程 (2026-05-27)

### 当前版本: v3.1+CLV | 11030+场比赛

### v3.1 改进内容 (CLV引入)
1. **euro_odds因素增强** — 同时输出开盘+闭盘赔率、CLV变化delta
2. **odds_movement改为numeric CLV因素** — 闭盘概率-开盘概率作为信号
3. **模型权重调整** — euro_odds从0.22降到0.18，新增odds_movement 0.08，injury 0.03
4. **CLV交互项** — odds_movement*euro_odds(0.05), odds_movement*elo(0.03), injury*odds_movement(0.02)
5. **EV用闭盘赔率** — fair_odds用闭盘均值计算，不再用开盘

### v3.0 → v3.1 权重变化
| 因素 | v3.0 | v3.1 |
|------|------|------|
| euro_odds | 0.22 | 0.18 |
| standing | 0.12 | 0.10 |
| form | 0.10 | 0.08 |
| home_away | 0.05 | 0.04 |
| home_away_deep | 0.05 | 0.04 |
| asian_handicap | 0.05 | 0.04 |
| prediction | 0.06 | 0.05 |
| h2h | 0.04 | 0.03 |
| elo_rating | 0.08 | 0.07 |
| rest_days | 0.04 | 0.03 |
| schedule_difficulty | 0.03 | 0.02 |
| possession_counter | 0.03 | 0.02 |
| odds_movement | 0.00 | 0.08 |
| injury | 0.00 | 0.03 |

### CLV数据覆盖
- football-data-co-uk: 9,951场有开盘+闭盘赔率 (71.1%覆盖率)
- CLV信号: 闭盘概率-开盘概率 (home_clv, away_clv)
- 方向性: 正CLV=市场升了该队预期, 负CLV=市场降了该队预期

### 核心认知 (从v3.0延续)
- **用闭盘赔率无法打败闭盘线** — 模型与闭盘方向99.6%一致
- **CLV是增量信息** — 开盘→闭盘变化代表市场调整，包含新信息
- **EV>0不代表能赢** — 需要真正的信息差(开盘赔率+基本面)才能盈利
- **概率校准比argmax准确率更重要** — Brier/Log Loss才是衡量概率质量的标尺

### 下一步方向
1. **采集开盘赔率时间序列** — 不只是initial/final，看中间变化过程
2. **基本面增量数据** — 伤病、天气、阵容变化 vs 赔率变化的对应关系
3. **用基本面和赔率对碰** — 找市场反应滞后的比赛
4. **凯利公式** — 只在模型概率 vs 赔率概率有真正信息差时下注

**Why:** 追踪模型从"预测赛果"到"找价值差"的核心转变，CLV是第一步增量
**How to apply:** 进一步优化应聚焦于(1)赔率时间序列细节(2)基本面增量(3)EV>0的真正信息差