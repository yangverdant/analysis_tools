---
name: match-script-layer
description: "Unified match script layer (direction_axis, margin_axis, goal_axis, btts_axis, first_half_axis) ensuring cross-play consistency"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

Match script layer built — all 5 play types derive from one unified match script.

**What:** Every match gets a match_script with 7 axes: direction, margin, goal, BTTS, first_half, late_goal_risk, uncertainty + key_drivers. Cross-play contradictions are detected and flagged.

**Contradiction types detected:**
- spf_bqc_full_time_mismatch: SPF direction contradicts BQC full-time leg
- rqspf_bqc_full_time_mismatch: RQSPF implied full-time contradicts BQC
- goal_axis_score_candidate_mismatch: O/U says under but top score has many goals
- direction_margin_contradiction: Direction says home but margin says away
- first_half_bqc_mismatch: Half-time tempo contradicts BQC half-time leg

**API:** GET /api/v1/lottery/match-script/{lottery_match_id}

**Why:** Previous system had independent play predictions that could contradict each other (SPF=主胜 but BQC=负负). Match script enforces a single narrative.

**How to apply:** Frontend shows match script section in analysis detail. automation_center should reject predictions with high-severity contradictions.

[[model-baseline-system]]
