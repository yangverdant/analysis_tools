"""Compare a model reanalysis backup with the current validation table.

The reanalysis runner stores the analysis layer before it mutates reports and
validations. This helper shows exactly which play predictions changed after a
model experiment, so a "same total accuracy" run can still be inspected for
O/U, BQC, handicap, or score regressions.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"


PLAY_LABELS = {
    "spf": "胜平负",
    "rqspf": "让球胜平负",
    "bqc": "半全场",
    "ou": "大小球",
    "bf": "比分",
}


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def placeholders(values: Sequence[Any]) -> str:
    return ",".join(["?"] * len(values))


def load_backup(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_backup_validations(payload: Dict[str, Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    rows = (((payload.get("tables") or {}).get("lottery_validation") or {}).get("rows") or [])
    result: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        match_id = str(row.get("lottery_match_id") or "")
        play_type = str(row.get("play_type") or "")
        if match_id and play_type:
            result[(match_id, play_type)] = row
    return result


def load_current_validations(
    conn: sqlite3.Connection,
    match_ids: Sequence[str],
) -> List[sqlite3.Row]:
    if not match_ids:
        return []
    return conn.execute(
        f"""
        SELECT lv.lottery_match_id, lv.play_type, lv.predicted_result,
               lv.actual_result, lv.is_correct,
               lm.match_num, lm.match_date, lm.match_time, lm.beijing_time,
               lm.league_name_cn, lm.home_team_cn, lm.away_team_cn,
               lr.home_goals_ft, lr.away_goals_ft,
               lr.home_goals_ht, lr.away_goals_ht
        FROM lottery_validation lv
        JOIN lottery_matches lm ON lm.lottery_match_id = lv.lottery_match_id
        LEFT JOIN lottery_results lr ON lr.lottery_match_id = lv.lottery_match_id
        WHERE lv.lottery_match_id IN ({placeholders(match_ids)})
        ORDER BY substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10),
                 COALESCE(lm.match_time, ''),
                 lm.match_num,
                 lv.play_type
        """,
        list(match_ids),
    ).fetchall()


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def clean(value: Any) -> str:
    return "" if value is None else str(value)


def compare(payload: Dict[str, Any], current_rows: Sequence[sqlite3.Row], play_filter: set[str]) -> Dict[str, Any]:
    before_map = load_backup_validations(payload)
    changes = []
    summary: Dict[str, Any] = {
        "total_changes": 0,
        "improved": 0,
        "regressed": 0,
        "prediction_changed_only": 0,
        "by_play_type": {},
    }

    for row in current_rows:
        match_id = str(row["lottery_match_id"])
        play_type = str(row["play_type"] or "")
        if play_filter and play_type not in play_filter:
            continue
        before = before_map.get((match_id, play_type))
        if not before:
            continue

        before_correct = as_int(before.get("is_correct"))
        after_correct = as_int(row["is_correct"])
        before_predicted = clean(before.get("predicted_result"))
        after_predicted = clean(row["predicted_result"])
        before_actual = clean(before.get("actual_result"))
        after_actual = clean(row["actual_result"])

        if (
            before_correct == after_correct
            and before_predicted == after_predicted
            and before_actual == after_actual
        ):
            continue

        if after_correct > before_correct:
            direction = "improved"
        elif after_correct < before_correct:
            direction = "regressed"
        else:
            direction = "changed"

        bucket = summary["by_play_type"].setdefault(
            play_type,
            {"changes": 0, "improved": 0, "regressed": 0, "changed": 0},
        )
        bucket["changes"] += 1
        bucket[direction] += 1
        summary["total_changes"] += 1
        if direction == "improved":
            summary["improved"] += 1
        elif direction == "regressed":
            summary["regressed"] += 1
        else:
            summary["prediction_changed_only"] += 1

        changes.append(
            {
                "match_key": match_id,
                "match_num": row["match_num"],
                "match_date": row["match_date"],
                "beijing_time": row["beijing_time"],
                "league": row["league_name_cn"],
                "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
                "score": (
                    f"{row['home_goals_ft']}:{row['away_goals_ft']}"
                    if row["home_goals_ft"] is not None and row["away_goals_ft"] is not None
                    else ""
                ),
                "half_score": (
                    f"{row['home_goals_ht']}:{row['away_goals_ht']}"
                    if row["home_goals_ht"] is not None and row["away_goals_ht"] is not None
                    else ""
                ),
                "play_type": play_type,
                "play_label": PLAY_LABELS.get(play_type, play_type),
                "direction": direction,
                "before": {
                    "predicted": before_predicted,
                    "actual": before_actual,
                    "is_correct": bool(before_correct),
                },
                "after": {
                    "predicted": after_predicted,
                    "actual": after_actual,
                    "is_correct": bool(after_correct),
                },
            }
        )

    return {
        "backup": {
            "created_at": payload.get("created_at"),
            "version_tag": payload.get("version_tag"),
            "dates": payload.get("dates"),
            "match_ids": len(payload.get("match_ids") or []),
        },
        "summary": summary,
        "changes": changes,
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--backup", required=True)
    parser.add_argument("--play-types", default="", help="Comma-separated filter, e.g. ou,bf")
    parser.add_argument("--summary-only", action="store_true")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    payload = load_backup(Path(args.backup))
    match_ids = [str(item) for item in payload.get("match_ids") or []]
    play_filter = {item.strip() for item in str(args.play_types or "").split(",") if item.strip()}
    with connect(Path(args.db)) as conn:
        current_rows = load_current_validations(conn, match_ids)
    result = compare(payload, current_rows, play_filter)
    if args.summary_only:
        result = {key: result[key] for key in ("backup", "summary")}
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
