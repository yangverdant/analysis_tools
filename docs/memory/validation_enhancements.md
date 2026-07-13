---
name: validation-enhancements
description: "Enhanced validation: 11 fine-grained attribution types, Asian settlement grades, enriched BF metrics, confidence tier recalibration"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

Four validation enhancements completed 2026-06-29, covering P0-6.9.6, P0-6.9.7.2, P0-6.9.7.5, and P0-6.9.4.

**Fine-grained attribution** (P0-6.9.6): Replaced generic unknown attribution (67.8% of errors) with 11 specific types. `_determine_attribution()` now handles all 5 play types via `_play_specific_attribution()`. Key types: `goal_axis_misread` (O/U/BF), `margin_axis_misread` (RQSPF), `half_time_axis_misread` (BQC), `missing_lineup`, `missing_injury`, `tournament_context_misread`, `low_confidence_noise`, `market_misread`, `model_weight_issue`. Backfill: `_attribute_failures()` now also processes records where `attribution IS NULL`.

**Asian settlement grades** (P0-6.9.7.2): `compute_ou_settlement()` and `compute_handicap_settlement()` in validate.py handle quarter lines (2.25/2.75), half lines (2.5), and integer lines (2.0/3.0). Returns: full_win/half_win/push/half_loss/full_loss/void. DB column: `settlement_grade`. Backfilled 128 O/U + 107 RQSPF records.

**Enriched BF metrics** (P0-6.9.7.5): Added 5 columns to lottery_validation: `top3_score_hit`, `goal_bucket_hit`, `margin_bucket_hit`, `btts_hit`, `ou_consistency_hit`. Computed in `_validate_bf_for_report()`. Current rates: margin_bucket=40%, btts=49.6%, ou_consistency=51.2% — much more informative than 20.8% exact score hit.

**Confidence tier recalibration** (P0-6.9.4): `compute_confidence_tier()` uses multi-axis consistency (model direction + market alignment + intel completeness). 4 tiers: strong (75.0% acc, >72% target), medium (57.3%), low (45.7%), avoid (21.4%). Frontend shows tier labels (强/中/弱/观望) with avoid in gray italic. DB column: `confidence_tier`. API: `/lottery/accuracy-by-tier`. Backfilled 571 records.

**Why:** Previous validation was too coarse — unknown attributions, binary O/U/RQSPF correctness, exact-only BF scoring, uncalibrated confidence. These enhancements make validation data actionable for model improvement.

**How to apply:** Attribution types map to `next_data_requirements` via `_ATTRIBUTION_DATA_MAP`. Settlement grades feed into ROI calculations (push/half-win != full-win). BF enriched metrics provide more granular feedback for score prediction. Confidence tiers control frontend display intensity.

[[match-script-layer]] [[model-baseline-system]]
