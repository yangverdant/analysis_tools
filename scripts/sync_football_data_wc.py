"""Sync football-data.org WC schedule/results into local evidence.

Dry-run by default. Use --apply to write source artifacts, entity mappings,
finished scores, half-time scores, and result revalidation queue entries.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.lottery.services.football_data_wc_sync import (  # noqa: E402
    FootballDataWorldCupSync,
    default_date_range,
    default_db_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=default_db_path(), help="Path to football_v2.db")
    parser.add_argument("--from", dest="date_from", help="Start Beijing date YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="End Beijing date YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=3, help="Default range ending today when --from/--to are omitted")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--apply", action="store_true", help="Write artifacts/mappings/results. Default is dry-run.")
    parser.add_argument("--overwrite-results", action="store_true", help="Overwrite existing non-empty result fields.")
    parser.add_argument("--max-matches", type=int, help="Maximum matched rows to apply in this batch.")
    parser.add_argument("--time-tolerance-minutes", type=int, default=10)
    args = parser.parse_args()

    date_from, date_to = args.date_from, args.date_to
    if not date_from or not date_to:
        date_from, date_to = default_date_range(args.days)

    result = FootballDataWorldCupSync(args.db).run(
        date_from,
        date_to,
        apply=args.apply,
        season=args.season,
        overwrite_results=args.overwrite_results,
        max_matches=args.max_matches,
        time_tolerance_minutes=args.time_tolerance_minutes,
        trigger_source="manual_script",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
