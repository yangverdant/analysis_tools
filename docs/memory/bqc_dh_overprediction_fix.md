---
name: bqc-dh-overprediction-fix
description: "BQC \"dh\" (平胜) prediction 0% accuracy — stability reuse preserving bad old predictions + phase_axis_adjustment"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

BQC "dh" (HT-draw FT-home-win) predictions had 0/24 accuracy in 7-day data. Two bugs:

**Bug 1: `_apply_bqc_stability_reuse` preserved old bad recommendations**
- When `current_structural=False` and `previous_structural=True`, stability reuse copied the old "dh" recommendation
- The old "dh" came from pre-fix code with `min_candidate_ratio=0.55` (now 0.85)
- Fix: Skip stability reuse when current is clean but previous has forced adjustment (`not current_structural and previous_structural`)

**Bug 2: `phase_axis_adjustment` over-triggered to "dh"**
- When `low_tempo_half=True` and `draw_half >= same_half * 0.95`, it switched from "hh" to "dh"
- Half-time draw probability is naturally highest (0-0 is most common HT score), so this condition is almost always true
- Already tightened in prior session: `min_candidate_ratio` from 0.55→0.85, thresholds from 0.035→0.08 etc.
- After stability reuse fix, `phase_axis_adjustment` no longer triggers (0 matches today vs 2 before)

**Before fix**: 20 matches: hh:10, dh:6, aa:4 (6 bad dh predictions)
**After fix**: 20 matches: hh:12, dh:4, aa:4 (4 remaining dh are legitimate where hh=0.000)
