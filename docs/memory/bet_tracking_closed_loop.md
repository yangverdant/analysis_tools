---
name: bet_tracking_closed_loop
description: "Bet records settlement closed loop: validate→settle→ROI→stop-loss"
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

Bet records settlement is now a closed loop integrated into the daily cycle.

**Flow:**
1. push.py creates bet_records with stake (Kelly-adjusted, default 100 yuan)
2. validate.py runs _settle_bets() after validation
3. Matching lottery_results → win/lose, payout = stake * odds, profit calculated
4. ROI tracked via _compute_roi_summary (7d/30d/all)
5. Stop-loss triggers if 7-day ROI < -30%

**API:**
- POST /api/bets/settle — manual settlement trigger
- GET /api/bets/roi — ROI summary + recent bets
- Frontend AccuracyDashboard shows ROI cards + bet list

**Current data:** 3 bets (1 win +27 yuan, 2 pending)

**Why:** Before this, bet_records had stake=0 and no settlement logic — ROI tracking and stop-loss were theoretical only.
