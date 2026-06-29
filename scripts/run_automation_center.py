"""Run the parallel lottery automation center.

Examples:
    python scripts/run_automation_center.py --mode rolling --workers 3 --apply
    python scripts/run_automation_center.py --mode range --from 2026-06-13 --to 2026-06-23 --league 世界杯 --workers 4 --apply
    python scripts/run_automation_center.py --mode mixed --historical-dates 2 --workers 3 --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app.lottery.services.automation_center import AutomationCenter  # noqa: E402


DEFAULT_DB = Path(os.environ.get("DB_PATH") or ROOT / "data" / "football_v2.db")
DEFAULT_ODDSFE_DB = Path(
    os.environ.get("ODDSFE_DB_PATH") or ROOT / "fetchers" / "odds_feed_api" / "oddsfe_merged.db"
)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--oddsfe-db", default=str(DEFAULT_ODDSFE_DB))
    parser.add_argument("--mode", choices=["rolling", "range", "historical", "mixed"], default="rolling")
    parser.add_argument("--from", dest="date_from")
    parser.add_argument("--to", dest="date_to")
    parser.add_argument("--league", default="")
    parser.add_argument("--historical-dates", type=int, default=0)
    parser.add_argument("--historical-lookback-days", type=int, default=180)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--task-timeout", type=int, default=300)
    parser.add_argument("--max-events", type=int, default=6)
    parser.add_argument("--max-analysis", type=int, default=10)
    parser.add_argument("--max-intelligence", type=int, default=6)
    parser.add_argument("--max-validation-dates", type=int, default=1)
    parser.add_argument("--no-fetch-live-ou", dest="fetch_live_ou", action="store_false", default=True)
    parser.add_argument("--no-network-intelligence", dest="network_intelligence", action="store_false", default=True)
    parser.add_argument("--no-learning", dest="include_learning", action="store_false", default=True)
    parser.add_argument("--no-national-ou-gate", dest="national_ou_gate", action="store_false", default=True)
    parser.add_argument("--national-ou-fact-table", default=os.environ.get("FOOTBALL_NATIONAL_REFERENCE_FACT_TABLE"))
    parser.add_argument("--force-analysis", action="store_true", help="Re-run analysis even when reports already exist.")
    parser.add_argument("--force-validation", action="store_true", help="Rebuild validation even when records already exist.")
    parser.add_argument("--force-learning", action="store_true", help="Run final learning refresh even when no gap requests it.")
    parser.add_argument("--apply", action="store_true", help="Execute tasks. Default only prints the task plan.")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    center = AutomationCenter(args.db, args.oddsfe_db)
    if not args.apply:
        result = center.plan(
            mode=args.mode,
            date_from=args.date_from,
            date_to=args.date_to,
            league=args.league,
            historical_dates=args.historical_dates,
            historical_lookback_days=args.historical_lookback_days,
            include_learning=args.include_learning,
            national_ou_gate=args.national_ou_gate,
            force_analysis=args.force_analysis,
            force_validation=args.force_validation,
            force_learning=args.force_learning,
        )
    else:
        result = center.run(
            mode=args.mode,
            date_from=args.date_from,
            date_to=args.date_to,
            league=args.league,
            historical_dates=args.historical_dates,
            historical_lookback_days=args.historical_lookback_days,
            include_learning=args.include_learning,
            national_ou_gate=args.national_ou_gate,
            national_ou_fact_table=args.national_ou_fact_table,
            force_analysis=args.force_analysis,
            force_validation=args.force_validation,
            force_learning=args.force_learning,
            workers=args.workers,
            task_timeout_seconds=args.task_timeout,
            max_events=args.max_events,
            max_analysis=args.max_analysis,
            max_intelligence=args.max_intelligence,
            max_validation_dates=args.max_validation_dates,
            fetch_live_ou=args.fetch_live_ou,
            network_intelligence=args.network_intelligence,
            trigger_source="manual_automation_center_script",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
