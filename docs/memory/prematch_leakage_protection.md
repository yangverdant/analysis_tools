---
name: prematch-leakage-protection
description: "Pre-match data leakage audit + 3 runtime gates: intel cutoff, similar_cases filter, duplicate odds cleanup"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

Pre-match data leakage protection completed 2026-06-29, covering P0-6.9.7.1.

**Audit script** (`scripts/audit_no_future_leakage.py`): 6 checks covering odds, intelligence, source_artifacts, similar_match_cases, analysis_reports, team_match_facts. Baseline audit found 812 potential issues (99 odds + 115 intel + 5 similar cases + 593 reports). Run with `--fail-on-leakage` for CI gating.

**Intelligence cutoff gate**: `_load_intelligence_context()` in analyze.py now adds `AND ip.updated_at <= kickoff + 15min` to the SQL query. Prevents post-kickoff intelligence packages from entering pre-match analysis.

**Similar cases filter**: `_load_ou_similarity_signal()` now filters out rows where `similar_match_key` has a kickoff time after the current match. Uses `_get_lottery_kickoff()` for each similar case.

**Duplicate odds functions removed**: Old unfiltered `_get_match_odds_baseline()` (line 1124) and `_get_ttg_odds_baseline()` (line 1261) removed. Only the pre-match filtered versions (using `_select_prematch_lottery_odds_row`) remain.

**Validation leakage flag**: `_check_prematch_leakage()` scans report data for `captured_at`/`updated_at` timestamps after kickoff. Flag stored in `leakage_flag` column of `lottery_validation` (dynamically added). Format: `captured_at_after_kickoff|intel_after_kickoff`.

**Why:** Analysis using post-match data inflates backtest accuracy and makes validation unreliable. The three runtime gates prevent new leakage; the audit script detects historical leakage.

**How to apply:** Run `audit_no_future_leakage.py` periodically. New analyses automatically use the gates. Validation records with `leakage_flag` set should be treated as potentially unreliable.

[[validation-enhancements]] [[match-script-layer]]
