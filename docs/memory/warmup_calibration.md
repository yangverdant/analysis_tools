---
name: warmup_calibration
description: Hot startup calibration using 229K oddsfe historical matches for initial weights and odds-based confidence
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

Hot startup (warmup.py) uses oddsfe CSV 229,880 finished matches with Pinnacle odds to calibrate the system on cold start.

**Key calibration results:**
- Overall odds-only argmax accuracy: 54.13%
- Home odds <1.30: 82.9% accuracy, 10.7% draw rate (strong favorites)
- Home odds 1.30-1.60: 67.0% accuracy, 18.8% draw rate
- Home odds 1.60-2.00: 53.4% accuracy, 25.0% draw rate
- Home odds 2.00-3.00: 41.4% accuracy, 27.6% draw rate (hardest zone)
- Home odds >3.00: 57.1% accuracy, 23.0% draw rate

**Why:** System had only 15 validations — insufficient for statistical confidence. 229K matches provide a reliable baseline.

**How to apply:**
- Warmup runs automatically when perceive detects <10 validations (cold start)
- Also available via POST /api/warmup and GET /api/warmup/status
- Calibration data stored in odds_calibration table
- analyze.py uses calibration to adjust confidence levels per odds bucket
- Frontend AccuracyDashboard has "热启动校准" button + calibration display
- MatchPreview shows factor breakdown (elo/poisson/form/motivation/odds) per match
