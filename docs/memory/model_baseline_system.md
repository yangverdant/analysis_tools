---
name: model-baseline-system
description: "Model baseline comparison system with market_favorite, poisson, elo, recent_form, hybrid_current predictions stored in model_baselines table"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

Model baseline system built and integrated into analyze.py flow.

**What:** Every analyzed match now computes predictions from 5 baseline models (market_favorite, market_implied, poisson, elo, recent_form) plus hybrid_current, stored in `model_baselines` table.

**Key files:**
- `backend/app/core/model_baselines.py` — computation + DB persistence
- `backend/app/core/match_script.py` — unified match script layer
- `backend/app/core/analyze.py` — integration in _analyze_single steps 13-13b
- `backend/app/lottery/routers/lottery.py` — /baseline-comparison and /match-script/{id} APIs
- `frontend/src/api/index.js` — getBaselineComparison, getMatchScript
- `frontend/src/components/LotteryCenter.vue` — match script display + model vs market status card

**Why:** Model improvements must be measured against objective benchmarks. If new model doesn't beat market_favorite baseline, it's not an improvement.

**How to apply:** Query `/api/v1/lottery/baseline-comparison?play_type=spf&days=30` for accuracy comparison. Use `model_baselines` table for custom queries. Match script contradictions flag cross-play inconsistencies.

[[match-script-layer]]
