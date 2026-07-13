---
name: p2-improvements-completed
description: "P2分析改进完成: form对手强度加权+简化动机+赔率异动+杯赛轮换+赔率基线修复+bet_records真实赔率"
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

# P2分析改进 — 已完成

## P2-1: form对手强度加权
- `analyze_form_with_opponent_strength` 连接到 `comprehensive.py`
- 胜/负按对手Elo比值加权(0.5-1.5x)
- 对手弱→form打折, 对手强→form加权

## P2-2: 简化动机评估(国家队/友谊赛)
- `motivation.py` 新增 `analyze_motivation_simplified` 方法
- 信号: FIFA排名动机 + 赛事类型动机 + 休息/疲劳 + 赛程密度
- 友谊赛urgency-15, 世预赛+25, 欧国联+15
- 当 `league_id/season_id` 不可用时自动启用
- `comprehensive.py` 中用urgency_diff直接调整概率

## P2-3: 赔率异动检测
- `comprehensive.py` 新增 `_load_odds_movement` 从intel报告加载
- 赔率异动信号 → 概率微调(magnitude * 0.3)
- 向异动方向调整(市场信号)

## P2-4: 杯赛轮换预测
- `comprehensive.py` 新增 `_apply_rotation_adjustment`
- 轮换概率 = 基础(赛事类型) + 密度修正 + 排名安全度修正
- 友谊赛0.55, 杯赛0.30, 超级杯0.10
- 轮换差异>5%时调整概率

## 赔率基线修复
- SPF odds key: '3'/'1'/'0' (非 'home'/'draw'/'away')
- RQSPF作为fallback(部分比赛无SPF)
- 覆盖率: 73% → 90%

## bet_records真实赔率
- `_record_bets` 改为从lottery_odds获取体彩实际赔率
- SPF优先, RQSPF fallback
- 每次push前清理pending记录避免重复

## 6/8验证: 3/3正确, Brier 0.2665
## 30场预测: model-odds agree=19, disagree=8, no_odds=3

## Bug修复
- `motivation.py`: row_factory兼容(tuple vs Row), fifa_rankings列名rank_date
- `comprehensive.py` report: motivation_type兼容两种格式, adj factor兼容
