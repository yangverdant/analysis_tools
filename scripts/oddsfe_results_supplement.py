#!/usr/bin/env python3
"""Cloud automation tick helper: backfill results from oddsfe for finished matches.

Called by cloud_automation_tick.sh after oddsfe_schedule_to_lottery.py.
Loops through the last N days of lottery_matches that have oddsfe_event_id but
no/missing lottery_results, and supplements them via _supplement_results_from_oddsfe.

This replaces sporttery as the primary results source since sporttery WAF ban.
"""
import sys
import sqlite3
from datetime import date, datetime, timedelta

ROOT = "/opt/football_tools"
DB_PATH = f"{ROOT}/data/football_v2.db"

sys.path.insert(0, ROOT)
sys.path.insert(0, f"{ROOT}/backend")


def _supplement_one_day(target_date: date) -> int:
    """Run _supplement_results_from_oddsfe for a single date. Returns count filled."""
    try:
        from backend.app.lottery.services.sync_service import LotterySyncService
    except Exception as exc:
        print(f"import LotterySyncService failed: {exc}")
        return 0

    svc = LotterySyncService(DB_PATH)
    try:
        filled = svc._supplement_results_from_oddsfe(target_date)
        if filled:
            print(f"supplement {target_date}: filled={filled}")
        return filled
    except Exception as exc:
        print(f"supplement error {target_date}: {exc}")
        return 0
    finally:
        try:
            svc.close()
        except Exception:
            pass


def main() -> None:
    """Backfill last 4 days (today + 3 prior) of results from oddsfe."""
    today = date.today()
    total_filled = 0
    for offset in (-3, -2, -1, 0):
        target = today + timedelta(days=offset)
        total_filled += _supplement_one_day(target)
    if total_filled:
        print(f"oddsfe_results_supplement done: total_filled={total_filled}")


if __name__ == "__main__":
    main()
