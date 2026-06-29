"""Normalize SPF play fields in lottery analysis report JSON.

Adds play_predictions.spf.recommendation and recommendation_cn from the existing
direction/direction_cn fields. The prediction itself is not recalculated.

Dry-run by default.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_DB = ROOT / "data" / "football_v2.db"
SPF_CN = {"3": "主胜", "1": "平局", "0": "客胜"}


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def decode_league(value: str) -> str:
    return value.encode("utf-8").decode("unicode_escape") if "\\u" in value else value


def latest_report_rows(conn: sqlite3.Connection, date_from: str, date_to: str, league: str) -> List[sqlite3.Row]:
    return conn.execute(
        """
        WITH latest AS (
            SELECT lottery_match_id, MAX(report_id) AS report_id
            FROM lottery_analysis_reports
            WHERE report_type IN ('prediction', 'full')
              AND COALESCE(is_stale, 0) = 0
            GROUP BY lottery_match_id
        )
        SELECT r.report_id, r.lottery_match_id, r.report_data,
               lm.match_num, lm.home_team_cn, lm.away_team_cn
        FROM latest l
        JOIN lottery_analysis_reports r ON r.report_id = l.report_id
        JOIN lottery_matches lm ON lm.lottery_match_id = r.lottery_match_id
        WHERE substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?
          AND COALESCE(lm.league_name_cn, '') = ?
        ORDER BY lm.beijing_time, lm.lottery_match_id
        """,
        (date_from, date_to, league),
    ).fetchall()


def normalize_report(data: Dict[str, Any]) -> bool:
    plays = data.get("play_predictions")
    if not isinstance(plays, dict):
        return False
    spf = plays.get("spf")
    if not isinstance(spf, dict):
        return False
    direction = str(spf.get("direction") or "").strip()
    if direction not in SPF_CN:
        return False
    cn = str(spf.get("direction_cn") or SPF_CN[direction]).strip()
    changed = False
    if spf.get("recommendation") != direction:
        spf["recommendation"] = direction
        changed = True
    if spf.get("recommendation_cn") != cn:
        spf["recommendation_cn"] = cn
        changed = True
    return changed


def run(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    league = decode_league(args.league)
    summary: Dict[str, Any] = {
        "success": True,
        "dry_run": not args.apply,
        "db": str(db_path),
        "date_from": args.date_from,
        "date_to": args.date_to,
        "league": league,
        "checked": 0,
        "changed": 0,
        "examples": [],
    }

    with connect(db_path) as conn:
        rows = latest_report_rows(conn, args.date_from, args.date_to, league)
        summary["checked"] = len(rows)
        for row in rows:
            try:
                data = json.loads(row["report_data"] or "{}")
            except json.JSONDecodeError as exc:
                summary.setdefault("parse_errors", []).append(
                    {"report_id": row["report_id"], "error": str(exc)}
                )
                continue
            if not normalize_report(data):
                continue
            summary["changed"] += 1
            if len(summary["examples"]) < 20:
                spf = ((data.get("play_predictions") or {}).get("spf") or {})
                summary["examples"].append(
                    {
                        "report_id": row["report_id"],
                        "lottery_match_id": row["lottery_match_id"],
                        "match_num": row["match_num"],
                        "match": f"{row['home_team_cn']} vs {row['away_team_cn']}",
                        "spf": spf.get("recommendation_cn"),
                    }
                )
            if args.apply:
                conn.execute(
                    "UPDATE lottery_analysis_reports SET report_data = ? WHERE report_id = ?",
                    (json.dumps(data, ensure_ascii=False, separators=(",", ":")), row["report_id"]),
                )
        if args.apply:
            conn.commit()
    return summary


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--league", default="\\u4e16\\u754c\\u676f")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
