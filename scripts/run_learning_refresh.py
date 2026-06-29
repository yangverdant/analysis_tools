"""Refresh post-match learning assets and guarded model learning."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.learn import learn  # noqa: E402
from backend.app.data_access.task_lock import clean_path_arg, exclusive_task_lock  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--min-samples", type=int, default=10)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report that guarded learning would run. Learning writes history by design.",
    )
    args = parser.parse_args()
    args.db = clean_path_arg(args.db)

    if args.dry_run:
        output: Dict[str, Any] = {
            "success": True,
            "mode": "dry_run",
            "db": args.db,
            "days": args.days,
            "min_samples": args.min_samples,
        }
    else:
        with exclusive_task_lock("learning", args.db) as task_lock:
            if not task_lock.acquired:
                output = {
                    "success": True,
                    "mode": "apply",
                    "db": args.db,
                    "days": args.days,
                    "min_samples": args.min_samples,
                    "skipped": True,
                    "reason": "learning_task_already_running",
                    "lock_path": task_lock.path,
                    "lock_holder": task_lock.holder,
                }
            else:
                result = learn(args.db, agent=False, days=args.days, min_samples=args.min_samples)
                success = not bool(getattr(result, "error", None))
                output = {
                    "success": success,
                    "mode": "apply",
                    "db": args.db,
                    "days": args.days,
                    "min_samples": args.min_samples,
                    "learning": asdict(result),
                }
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0 if output.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
