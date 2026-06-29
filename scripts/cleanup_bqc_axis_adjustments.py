"""Remove obsolete BQC post-hoc SPF-axis adjustment markers.

Older reports sometimes selected BQC from the unconstrained 9-way maximum and
then recorded a consistency_adjustment to align the full-time side with SPF.
Current analysis selects BQC inside the SPF full-time axis directly, so those
old markers are just noisy explanation debt.

Default mode is dry-run. Use --apply to update active prediction reports.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "football_v2.db"
DEFAULT_LEAGUE = "世界杯"


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    return conn


def loads_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def spf_target(plays: Dict[str, Any]) -> str | None:
    spf = plays.get("spf") if isinstance(plays.get("spf"), dict) else {}
    return {"3": "h", "1": "d", "0": "a"}.get(str(spf.get("direction") or ""))


def scrub_derivation_summary(bqc: Dict[str, Any]) -> None:
    derivation = bqc.get("derivation")
    if not isinstance(derivation, dict):
        return
    summary = derivation.get("summary")
    if not isinstance(summary, str) or not summary:
        return
    summary = re.sub(r"；已按胜平负主轴校正为[^；]+", "", summary)
    derivation["summary"] = summary


def cleanup_report(report: Dict[str, Any]) -> Dict[str, Any] | None:
    plays = report.get("play_predictions")
    if not isinstance(plays, dict):
        plays = report.get("analyses")
    if not isinstance(plays, dict):
        return None

    bqc = plays.get("bqc")
    if not isinstance(bqc, dict):
        return None
    adjustment = bqc.get("consistency_adjustment")
    if not isinstance(adjustment, dict) or adjustment.get("reason") != "spf_axis":
        return None

    target = spf_target(plays)
    rec = str(bqc.get("recommendation") or "")
    if not target or len(rec) != 2 or rec[1] != target:
        return None

    probabilities = bqc.get("probabilities") if isinstance(bqc.get("probabilities"), dict) else {}
    candidate_count = sum(1 for key in probabilities if isinstance(key, str) and len(key) == 2 and key[1] == target)
    bqc.pop("consistency_adjustment", None)
    bqc["axis_constraint"] = {
        "source": "spf_axis",
        "full_time_axis": target,
        "candidate_count": candidate_count,
    }
    scrub_derivation_summary(bqc)
    return {
        "recommendation": rec,
        "target": target,
        "removed_adjustment": adjustment,
    }


def fetch_rows(conn: sqlite3.Connection, args: argparse.Namespace) -> List[sqlite3.Row]:
    filters = [
        "ar.report_type = ?",
        "COALESCE(ar.is_stale, 0) = 0",
    ]
    params: List[Any] = [args.report_type]
    if args.date_from:
        filters.append("lm.match_date >= ?")
        params.append(args.date_from)
    if args.date_to:
        filters.append("lm.match_date <= ?")
        params.append(args.date_to)
    if args.league:
        filters.append("lm.league_name_cn = ?")
        params.append(args.league)

    where = " AND ".join(filters)
    return list(conn.execute(
        f"""
        SELECT ar.report_id, ar.lottery_match_id, ar.report_data,
               lm.home_team_cn, lm.away_team_cn, lm.match_date, lm.match_time
        FROM lottery_analysis_reports ar
        JOIN lottery_matches lm ON lm.lottery_match_id = ar.lottery_match_id
        WHERE {where}
        ORDER BY lm.match_date, lm.match_time, ar.report_id
        """,
        params,
    ))


def run(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    conn = connect(db_path)
    rows = fetch_rows(conn, args)
    updates: List[Dict[str, Any]] = []

    for row in rows:
        report = loads_json(row["report_data"])
        change = cleanup_report(report)
        if not change:
            continue
        updates.append({
            "report_id": int(row["report_id"]),
            "lottery_match_id": row["lottery_match_id"],
            "match": f"{row['home_team_cn']} vs {row['away_team_cn']}",
            "date": f"{row['match_date']} {row['match_time']}",
            "report": report,
            "change": change,
        })

    if args.apply and updates:
        with conn:
            for item in updates:
                conn.execute(
                    "UPDATE lottery_analysis_reports SET report_data = ? WHERE report_id = ?",
                    (json.dumps(item["report"], ensure_ascii=False), item["report_id"]),
                )

    conn.close()
    result = {
        "db": str(db_path),
        "mode": "apply" if args.apply else "dry_run",
        "scanned": len(rows),
        "updated": len(updates) if args.apply else 0,
        "candidates": len(updates),
        "preview": [
            {k: v for k, v in item.items() if k != "report"}
            for item in updates[: args.limit]
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--date-from", default="2026-06-11")
    parser.add_argument("--date-to", default="2026-07-19")
    parser.add_argument("--report-type", default="prediction")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--apply", action="store_true")
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
