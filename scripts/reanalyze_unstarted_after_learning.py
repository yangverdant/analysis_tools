"""Re-run predictions for not-yet-started matches after learning refresh.

This is the bridge from post-match learning back into pre-match predictions:
reviews/similar cases/calibration are refreshed first, then unsettled future
matches in the same window are analyzed again with the latest assets.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get("DB_PATH") or ROOT / "data" / "football_v2.db")
DEFAULT_ODDSFE_DB = Path(
    os.environ.get("ODDSFE_DB_PATH") or ROOT / "fetchers" / "odds_feed_api" / "oddsfe_merged.db"
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app.data_access.task_lock import clean_path_arg  # noqa: E402
from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner  # noqa: E402


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--oddsfe-db", default=str(DEFAULT_ODDSFE_DB))
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--to", dest="date_to", required=True)
    parser.add_argument("--league", default="")
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--trigger-source", default="manual_post_learning_future_reanalysis")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    args.db = clean_path_arg(args.db)
    args.oddsfe_db = clean_path_arg(args.oddsfe_db)
    result = LotteryAutoGapRunner(args.db, args.oddsfe_db).reanalyze_unstarted_after_learning(
        args.date_from,
        args.date_to,
        league=args.league or None,
        limit=args.limit,
        trigger_source=args.trigger_source,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
