---
name: disagreement_strategy_fix
description: 模型-赔率分歧策略从boost模型改为blend向赔率靠拢，基于76场回测验证
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

模型-赔率分歧策略修正 (2026-06-29)

**Why:** 76场验证集回测：模型与赔率一致时70%准确，分歧时模型仅38.5%而赔率50%。旧逻辑boost模型方向反而降低准确率。

**How to apply:**
- `_apply_disagreement_boost`: 不再boost模型方向，改为blend 30%赔率权重
- 模型强信(>=40%且>赔率+5pp): 保留方向但降置信度
- `_apply_spf_market_anchor`: 阈值从0.69/0.20降至0.55/0.12

**118K场oddsfe回测:**
- Pinnacle argmax = 52.8%
- 所有draw threshold策略都亏损（简单平局boost无效）
- 赔率2.0-3.0区间是最大机会区（三方概率接近）

**数据源现状:**
- api_sports/apifootball: key过期，需要续费或找替代
- bifen188: 网站空壳
- player_status: 1000条但5月20日后未更新
- expected_lineup/injuries_suspensions: 全部fallback
