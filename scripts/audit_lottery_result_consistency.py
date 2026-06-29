"""Audit and repair derived lottery result fields.

Examples:
  python scripts/audit_lottery_result_consistency.py --from 2026-06-13 --to 2026-06-23
  python scripts/audit_lottery_result_consistency.py --from 2026-06-13 --to 2026-06-23 --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.lottery.services.result_consistency import run_result_consistency_audit  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--to", dest="date_to", required=True)
    parser.add_argument("--league", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    result = run_result_consistency_audit(
        args.db,
        args.date_from,
        args.date_to,
        apply=args.apply,
        league=args.league or None,
        limit=args.limit,
        trigger_source="result_consistency_cli",
    )
    if args.compact:
        result = {
            key: result.get(key)
            for key in (
                "success",
                "dry_run",
                "date_from",
                "date_to",
                "rows_checked",
                "rows_changed",
                "field_changes",
                "queued_revalidation",
                "by_field",
                "error",
            )
            if key in result
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())

