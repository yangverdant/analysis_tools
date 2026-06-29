"""Settle prediction reanalysis changes with post-match validation results."""

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
    parser.add_argument("--from", dest="date_from", default="")
    parser.add_argument("--to", dest="date_to", default="")
    parser.add_argument("--league", default="")
    parser.add_argument("--limit", type=int, default=200)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    args.db = clean_path_arg(args.db)
    args.oddsfe_db = clean_path_arg(args.oddsfe_db)
    result = LotteryAutoGapRunner(args.db, args.oddsfe_db).settle_reanalysis_changes(
        args.date_from or None,
        args.date_to or None,
        league=args.league or None,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
