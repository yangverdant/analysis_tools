---
name: bf-missing-prediction-fix
description: BF (比分) predictions never written to lottery_predictions table — root cause and fix
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

BF predictions were completely missing from `lottery_predictions` table (0 out of 479 matches).

**Root cause**: `_compute_all_plays` stores score predictions as `plays['top3_scores']` (a list), but `_save_play_predictions` only saves dict entries (`isinstance(pred, dict)` check). The list was skipped silently.

**Fix**: Added `_build_bf_play_entry(plays)` function that creates a `plays['bf']` dict entry from `top3_scores` data, with recommendation (e.g. "2:1"), probabilities, confidence, and confidence_tier. Called after `_apply_selective_recommendation_guard` so it can copy gate info.

**Why**: The list format `top3_scores` is still needed for push channels and validation (which read from report JSON). The `bf` dict is a parallel entry specifically for `lottery_predictions` table persistence.

**Impact**: Backfilled 2325 historical BF predictions. Today's 20 matches all have BF predictions now. BF accuracy tracking via `lottery_predictions ↔ lottery_validation` JOIN now works.

**Also fixed**: `_compact_play_predictions` now handles `bf` play type with top3_scores sub-field. `_compute_plays_from_probs` (fallback path) also gets `_build_bf_play_entry`.
