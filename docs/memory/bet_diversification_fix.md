---
name: bet_diversification_fix
description: "_rank_value_bets硬编码spf导致78场全spf, 修复为spf+rqspf动态择优, 发现odds_baseline已是概率形式不是小数odds"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 投注玩法多样化修复

## 发现 (2026-07-02)
- bet_records 78场全是spf, 错失rqspf(49%准确率)的高edge机会
- 根因: `_rank_value_bets` 第380行硬编码 `'play_type': 'spf'`, 从不评估其他玩法

## 修复过程两个隐藏bug

### Bug 1: odds_baseline误解
- `odds_baseline` 存的是**概率形式** (`home_win: 0.55`), 不是小数odds (`1.85`)
- 原代码做 `1/0.55=1.82` 再 `1/1.82=0.55` 双转换, 导致implied_prob失真
- 修复: `odds_baseline > 1.5` 才做1/odds转换, 否则直接当概率用
- 数据源: `odds_baseline.source = 'latest'`, `source_quality = 'prematch'`

### Bug 2: rqspf.recommendation字段为None
- `play_predictions.rqspf.recommendation` 字段始终为None
- 实际推荐在 `rqspf.direction` 字段 (`'3'/'1'/'0'`)
- 中文名在 `rqspf.direction_cn` 或 `rqspf.recommendation_cn`
- 原条件 `rqspf.get('recommendation')` 永远跳过rqspf候选
- 修复: `rqspf.get('recommendation') or rqspf.get('direction')`

## 体彩可投玩法
- ✅ spf/rqspf/bf/bqc/ttg (有lottery_odds数据)
- ❌ ou (体彩无此玩法, 即使模型推荐也不投注)
- 策略: 只把spf+rqspf纳入top3价值投注(bf/bqc准确率27%/36%太低)

## _get_real_odds兼容
- rqspf的selection可能是 `'3'/'1'/'0'` 或带handicap的 `'3+1'`
- 修复: `sel_key = selection.split('+')[0].split('-')[0].strip()`
- lottery_odds.rqspf 结构: `{'3': 1.9, '1': 3.5, '0': 3.15, 'goal_line': '-1'}`

## 验证 (2026-07-02)
- 6场世界杯热身赛, 修复前top3全是spf
- 修复后: 4场rqspf (美国让平edge=0.279, 比利时让负edge=0.158, 葡萄牙让负edge=0.145, 西班牙让平edge=0.089)
- 世界杯热身赛让球盘价值明显高于胜平负(冷门多, 让球+1/-1有保护)

## How to apply
- `_rank_value_bets` 现在对每场评估spf+rqspf, 取edge最大者
- edge阈值0.03 (3pp), 低于此不投注
- format_daily_push显示[玩法标签]+备选玩法
- 后续若bf/bqc准确率提升, 可加入候选池
