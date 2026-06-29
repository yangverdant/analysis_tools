"""Audit/backfill exact-event oddsfe Pinnacle O/U lines.

Examples:
    python scripts/sync_oddsfe_ou_lines.py --from 2026-06-01 --to 2026-06-21
    python scripts/sync_oddsfe_ou_lines.py --from 2026-06-01 --to 2026-06-21 --apply --fetch-live --max-events 8
    python scripts/sync_oddsfe_ou_lines.py --days 3 --apply --reanalyze
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.lottery.services.oddsfe_ou_line_sync import (  # noqa: E402
    DEFAULT_DB_PATH,
    DEFAULT_ODDSFE_DB_PATH,
    OddsfeOuLineSync,
    default_date_range,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync oddsfe Pinnacle O/U lines into football_v2.db")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to football_v2.db")
    parser.add_argument("--oddsfe-db", default=DEFAULT_ODDSFE_DB_PATH, help="Path to oddsfe_merged.db")
    parser.add_argument("--from", dest="date_from", help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="End date YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=21, help="Default date range ending today")
    parser.add_argument("--apply", action="store_true", help="Write O/U lines. Default is dry-run audit.")
    parser.add_argument("--fetch-live", action="store_true", help="Fetch oddsfe market pages when oddsfe_merged lacks O/U")
    parser.add_argument("--max-events", type=int, help="Maximum missing events to process in this run")
    parser.add_argument("--reanalyze", action="store_true", help="Immediately re-run analysis for updated matches")
    parser.add_argument("--audit-only", action="store_true", help="Only print audit summary even when --apply is present")
    args = parser.parse_args()

    date_from, date_to = args.date_from, args.date_to
    if not date_from or not date_to:
        date_from, date_to = default_date_range(args.days)

    sync = OddsfeOuLineSync(args.db, args.oddsfe_db)
    if args.audit_only or not args.apply:
        output = sync.audit(date_from, date_to)
    else:
        output = sync.run(
            date_from,
            date_to,
            apply=True,
            fetch_live=args.fetch_live,
            max_events=args.max_events,
            reanalyze=args.reanalyze,
            trigger_source="manual_script",
        )

    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
