# 价值投注模块使用说明

## 功能概述

价值投注模块帮助识别预测概率与市场赔率之间的差异，发现潜在的价值投注机会。

---

## 核心概念

### 价值投注定义

当 **预测概率 > 市场隐含概率** 时，存在价值投注机会。

```
隐含概率 = 1 / 赔率
Edge = 预测概率 - 隐含概率
```

### Kelly Criterion

Kelly公式计算最优投注比例：

```
f = (bp - q) / b

b = 赔率 - 1 (净赔率)
p = 预测概率
q = 1 - p (失败概率)
```

---

## API端点

### 1. 分析比赛价值投注
```
GET /api/v1/analytics/value-bet/match/{match_id}
```

**示例**:
```bash
curl "http://127.0.0.1:18888/api/v1/analytics/value-bet/match/premier_league_2025-2026_2026-05-24_sunderland_vs_chelsea"
```

**返回**:
```json
{
  "match_id": "premier_league_2025-2026_2026-05-24_sunderland_vs_chelsea",
  "home_team": "Sunderland",
  "away_team": "Chelsea",
  "odds": {"home": 3.5, "draw": 3.2, "away": 2.1},
  "prediction": {"home_win": 0.25, "draw": 0.28, "away_win": 0.47},
  "value_bets": [
    {
      "market": "away_win",
      "prediction_prob": 47.0,
      "implied_prob": 47.6,
      "odds": 2.1,
      "edge": -0.6,
      "value_rating": "none",
      "kelly_fraction": 0,
      "expected_value": -1.3
    }
  ],
  "summary": "当前赔率无明显价值投注机会"
}
```

### 2. 扫描未来价值投注
```
GET /api/v1/analytics/value-bet/scan?days=7&min_edge=0.05
```

**参数**:
- `days`: 扫描未来N天 (默认7)
- `min_edge`: 最小优势阈值 (默认0.05=5%)

### 3. 自定义分析
```
POST /api/v1/analytics/value-bet/analyze
```

**请求体**:
```json
{
  "prediction": {"home_win": 0.45, "draw": 0.25, "away_win": 0.30},
  "odds": {"home": 2.5, "draw": 3.5, "away": 2.8}
}
```

### 4. Kelly计算
```
GET /api/v1/analytics/value-bet/kelly?prediction_prob=0.4&odds=2.5&fractional=0.5
```

**返回**:
```json
{
  "prediction_prob": 40.0,
  "odds": 2.5,
  "implied_prob": 40.0,
  "edge": 0.0,
  "expected_value": 0.0,
  "kelly_fraction": 0.0,
  "value_rating": "none",
  "recommendation": "无价值投注"
}
```

### 5. 套利机会计算
```
POST /api/v1/analytics/value-bet/arbitrage
```

**请求体**:
```json
[
  {"bookmaker": "bet365", "home": 2.5, "draw": 3.2, "away": 2.8},
  {"bookmaker": "pinnacle", "home": 2.6, "draw": 3.1, "away": 2.9}
]
```

**返回** (存在套利时):
```json
{
  "has_arbitrage": true,
  "arbitrage_margin": 2.5,
  "best_odds": {
    "home": {"odds": 2.6, "bookmaker": "pinnacle"},
    "draw": {"odds": 3.2, "bookmaker": "bet365"},
    "away": {"odds": 2.9, "bookmaker": "pinnacle"}
  },
  "bet_allocation": {
    "home": 38.5,
    "draw": 31.3,
    "away": 30.2
  },
  "guaranteed_profit": 2.5
}
```

---

## 价值等级

| 等级 | Edge阈值 | 说明 |
|------|----------|------|
| **high** | ≥8% | 强烈推荐 |
| **medium** | ≥5% | 推荐考虑 |
| **low** | ≥3% | 谨慎考虑 |
| **none** | <3% | 无价值 |

---

## Python使用示例

```python
from value_bet import ValueBetAnalyzer

db_path = "d:\\football_tools\\data\\football_v2.db"
analyzer = ValueBetAnalyzer(db_path)

# 计算Kelly
kelly = analyzer.calculate_kelly_criterion(
    prediction_prob=0.4,
    odds=2.5,
    fractional=0.5  # 半Kelly更保守
)
print(f"建议投注比例: {kelly*100:.1f}%")

# 查找价值投注
prediction = {'home_win': 0.45, 'draw': 0.25, 'away_win': 0.30}
odds = {'home': 2.5, 'draw': 3.5, 'away': 2.8}
value_bets = analyzer.find_value_bets(prediction, odds)

for vb in value_bets:
    print(f"{vb.market}: Edge={vb.edge*100:.1f}%, Kelly={vb.kelly_fraction*100:.1f}%")

# 扫描未来比赛
upcoming = analyzer.scan_upcoming_value_bets(days=7, min_edge=0.05)
for match in upcoming:
    print(f"{match['home_team']} vs {match['away_team']}")
    for vb in match['value_bets']:
        print(f"  {vb['market']}: Edge={vb['edge']:.1f}%")
```

---

## 注意事项

1. **预测准确性**: 价值投注的前提是预测概率准确，建议结合多种分析维度
2. **Kelly保守**: 实际使用建议采用半Kelly(0.5)或四分之一Kelly(0.25)
3. **赔率变化**: 赔率实时变化，需及时更新
4. **资金管理**: Kelly比例是单次投注建议，需结合总资金规划

---

## 文件位置

- 价值投注模块: [backend/app/analytics/value_bet.py](backend/app/analytics/value_bet.py)
- API路由: [backend/app/analytics/routes.py](backend/app/analytics/routes.py)
