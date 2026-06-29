"""Sync oddsfe event details into source_artifacts and lottery_results.

Dry-run by default. Use --apply to fetch live oddsfe event detail, record raw
event evidence, and fill missing lottery_results fields.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.lottery.services.oddsfe_event_sync import (  # noqa: E402
    OddsfeEventDetailSync,
    default_date_range,
    default_db_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync oddsfe event detail cache/results")
    parser.add_argument("--db", default=default_db_path(), help="Path to football_v2.db")
    parser.add_argument("--from", dest="date_from", help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="End date YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=3, help="Default range ending today when --from/--to are omitted")
    parser.add_argument("--apply", action="store_true", help="Write artifacts/results. Default is dry-run only.")
    parser.add_argument("--refresh", action="store_true", help="Refetch event detail even when a usable cache exists.")
    parser.add_argument("--no-schedule-fetch", action="store_true", help="Use cached schedule artifacts only.")
    parser.add_argument("--no-schedule-only", action="store_true", help="Skip schedule-only World Cup fallback events.")
    parser.add_argument("--max-events", type=int, help="Maximum event candidates to process in this batch.")
    parser.add_argument("--batches", type=int, default=1, help="Number of batches to run.")
    parser.add_argument("--batch-gap-seconds", type=float, default=0, help="Pause between batches.")
    parser.add_argument("--schedule-padding-days", type=int, default=1, help="Extra schedule days on both sides for UTC/Beijing offset.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing non-empty lottery_results fields.")
    parser.add_argument("--cache-minutes", type=int, default=30, help="Reuse non-final event cache newer than this.")
    parser.add_argument("--sleep", type=float, default=0.15, help="Seconds between event API calls.")
    args = parser.parse_args()

    date_from, date_to = args.date_from, args.date_to
    if not date_from or not date_to:
        date_from, date_to = default_date_range(args.days)

    sync = OddsfeEventDetailSync(args.db)
    summaries = []
    total_batches = max(args.batches, 1)
    for batch_index in range(total_batches):
        summary = sync.run(
            date_from,
            date_to,
            apply=args.apply,
            refresh=args.refresh,
            fetch_schedule=not args.no_schedule_fetch,
            include_schedule_only=not args.no_schedule_only,
            max_events=args.max_events,
            schedule_padding_days=args.schedule_padding_days,
            overwrite=args.overwrite,
            cache_minutes=args.cache_minutes,
            sleep_seconds=args.sleep,
            trigger_source="manual_script",
        )
        summary["batch_index"] = batch_index + 1
        summaries.append(summary)

        if not summary.get("success"):
            break
        if not summary.get("candidates_deferred"):
            break
        if batch_index < total_batches - 1 and args.batch_gap_seconds > 0:
            time.sleep(args.batch_gap_seconds)

    output = summaries[0] if len(summaries) == 1 else {"success": all(s.get("success") for s in summaries), "batches": summaries}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
