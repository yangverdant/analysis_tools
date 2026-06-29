"""Run one bounded LotteryAutoGapRunner segment.

Kept as a separate process so the parent segmented loop can enforce timeouts
and continue with the next segment if network collection hangs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get("DB_PATH") or ROOT / "data" / "football_v2.db")
DEFAULT_ODDSFE_DB = Path(
    os.environ.get("ODDSFE_DB_PATH") or ROOT / "fetchers" / "odds_feed_api" / "oddsfe_merged.db"
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--oddsfe-db", default=str(DEFAULT_ODDSFE_DB))
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--to", dest="date_to", required=True)
    parser.add_argument("--league", default="")
    parser.add_argument("--max-events", type=int, default=8)
    parser.add_argument("--max-analysis", type=int, default=16)
    parser.add_argument("--max-intelligence", type=int, default=8)
    parser.add_argument("--max-validation-dates", type=int, default=4)
    parser.add_argument("--no-live-ou", action="store_true")
    parser.add_argument("--no-network-intelligence", action="store_true")
    args = parser.parse_args()

    result = LotteryAutoGapRunner(args.db, args.oddsfe_db).run(
        args.date_from,
        args.date_to,
        max_events=args.max_events,
        max_analysis=args.max_analysis,
        max_intelligence=args.max_intelligence,
        max_validation_dates=args.max_validation_dates,
        fetch_live_ou=not args.no_live_ou,
        network_intelligence=not args.no_network_intelligence,
        league=args.league,
        trigger_source="segmented_auto_loop",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
