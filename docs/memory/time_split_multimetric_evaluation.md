---
name: time-split-multimetric-evaluation
description: "Time-split backtest + multi-metric evaluation + competition contexts: train/val/test, Brier, calibration, leakage"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

Time-split backtest, multi-metric evaluation, and competition contexts completed 2026-06-29, covering P0-6.9.7.3, P0-6.9.7.4, P0-6.9.7.6.

**Time-split backtest** (P0-6.9.7.3): `query_time_split_comparison()` in model_baselines.py. Splits last N days into train(60%)/validation(20%)/test(20%). Each window computes accuracy + avg_brier per baseline. Overfitting detection: train-test gap > 5pp → `likely_overfitting: true`. Test set model vs market comparison is the only valid evaluation. API: `/lottery/time-split-comparison`.

**Multi-metric evaluation** (P0-6.9.7.4): `/lottery/validation-metrics` API. Returns: by_play_type (accuracy + avg_brier + high_conf_accuracy + low_conf_rate), calibration (6 confidence buckets → actual accuracy → calibration_gap), market_baseline_diff (model vs market_favorite per play_type), settlement distribution, leakage_summary. model_baselines table now stores `brier_score` column (SPF 3-class Brier).

**Competition contexts** (P0-6.9.7.6): `_build_type_context()` + `_COMPETITION_TYPE_CONTEXTS` dict. 8 types each with description/motivation_weight/draw_boost/rotation_risk/upset_risk/key_factors. Every analysis report now has `competition_context.type` set. Enriched from MatchProfile (is_neutral_venue, has_two_legs, stage_type). `data_quality` dict now includes `competition_type`. `_compact_competition_context()` preserves the new fields in saved reports.

**Competition split comparison**: `query_competition_split_comparison()` groups model_baselines by league_name_cn. API: `/lottery/competition-split-comparison`.

**Why:** Single rolling window evaluation is in-sample and overestimates performance. Accuracy alone is misleading (market baseline is strong). Without competition-type differentiation, cup/friendly contexts were treated same as league.

**How to apply:** Use `/time-split-comparison` for model change evaluations — only test set results are meaningful. Use `/validation-metrics` for comprehensive quality assessment. Use `/competition-split-comparison` to identify weak competition types. Use `competition_context.type` in analysis to drive type-specific weights.

[[prematch-leakage-protection]] [[validation-enhancements]] [[match-script-layer]]
