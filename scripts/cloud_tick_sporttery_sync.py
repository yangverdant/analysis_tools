#!/usr/bin/env python3
"""Cloud automation tick helper: sync sporttery future matches with dedup.

Called by cloud_automation_tick.sh before run_automation_center.py.
Skips if another sporttery_daily_matches run is active within 90 min.
"""
import sys
import sqlite3
from datetime import date, datetime, timedelta

ROOT = "/opt/football_tools"
DB_PATH = f"{ROOT}/data/football_v2.db"

sys.path.insert(0, ROOT)
sys.path.insert(0, f"{ROOT}/backend")


def _recent_run_active() -> bool:
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        row = conn.execute(
            "SELECT started_at FROM collection_runs "
            "WHERE run_type='sporttery_daily_matches' "
            "AND status='running' "
            "ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if not row:
            return False
        started_str = str(row[0])[:19]
        try:
            started = datetime.strptime(started_str, "%Y-%m-%d %H:%M:%S")
            return started >= datetime.now() - timedelta(minutes=90)
        except ValueError:
            return True
    except Exception:
        return False


def main() -> None:
    if _recent_run_active():
        print("sporttery_daily_matches already running, skip")
        return

    try:
        from backend.app.lottery.services.sync_service import LotterySyncService
    except Exception as exc:
        print(f"import LotterySyncService failed: {exc}")
        return

    svc = LotterySyncService(DB_PATH)
    try:
        for offset in (0, 1, 2):
            target_date = date.today() + timedelta(days=offset)
            try:
                result = svc.sync_daily_matches(
                    match_date=target_date,
                    bridge_oddsfe=False,
                    trigger_source="cloud_automation_tick_sporttery",
                )
                saved = result.get("saved", 0) if isinstance(result, dict) else 0
                print(f"sync {target_date}: saved={saved}")
            except Exception as exc:
                print(f"sync error offset={offset}: {exc}")
    finally:
        try:
            svc.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
