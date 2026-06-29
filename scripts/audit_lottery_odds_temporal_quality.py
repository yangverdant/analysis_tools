"""Audit lottery odds temporal quality for pre-match analysis.

The model should not silently treat post-kickoff inserts as clean pre-match
odds. This script is read-only and flags timing/shape issues so repair scripts
can stay conservative.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "football_v2.db"
DEFAULT_LEAGUE = "\u4e16\u754c\u676f"


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    return conn


def columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def parse_json(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return fallback


def parse_dt(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("T", " ")
    formats = (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%d", 10),
    )
    for fmt, width in formats:
        try:
            return datetime.strptime(text[:width], fmt)
        except ValueError:
            continue
    return None


def kickoff_time(match: sqlite3.Row) -> Optional[datetime]:
    beijing_time = str(match["beijing_time"] or "").strip()
    parsed = parse_dt(beijing_time)
    if parsed:
        return parsed
    match_date = str(match["match_date"] or "").strip()[:10]
    match_time = str(match["match_time"] or "").strip() if "match_time" in match.keys() else ""
    return parse_dt(f"{match_date} {match_time}".strip())


def odds_timestamp(row: sqlite3.Row) -> Optional[datetime]:
    for key in ("update_time", "created_at", "updated_at"):
        if key in row.keys():
            parsed = parse_dt(row[key])
            if parsed:
                return parsed
    return None


def fetch_matches(conn: sqlite3.Connection, args: argparse.Namespace) -> List[sqlite3.Row]:
    where = ["1=1"]
    params: List[Any] = []
    if args.date_from:
        where.append("date(match_date) >= date(?)")
        params.append(args.date_from)
    if args.date_to:
        where.append("date(match_date) <= date(?)")
        params.append(args.date_to)
    if args.league and not args.all_leagues:
        where.append("league_name_cn = ?")
        params.append(args.league)
    if args.ids:
        ids = [item.strip() for item in args.ids.split(",") if item.strip()]
        if ids:
            where.append("lottery_match_id IN ({})".format(",".join(["?"] * len(ids))))
            params.extend(ids)

    match_cols = columns(conn, "lottery_matches")
    select_cols = [
        col
        for col in (
            "lottery_match_id",
            "match_num",
            "league_name_cn",
            "match_date",
            "match_time",
            "beijing_time",
            "home_team_cn",
            "away_team_cn",
            "play_types",
            "sell_status",
        )
        if col in match_cols
    ]
    return conn.execute(
        f"""
        SELECT {", ".join(select_cols)}
        FROM lottery_matches
        WHERE {" AND ".join(where)}
        ORDER BY date(match_date), beijing_time, lottery_match_id
        """,
        params,
    ).fetchall()


def fetch_odds(conn: sqlite3.Connection, match_ids: Sequence[str]) -> Dict[str, List[sqlite3.Row]]:
    if not match_ids:
        return {}
    odds_cols = columns(conn, "lottery_odds")
    select_cols = [
        col
        for col in (
            "odds_id",
            "lottery_match_id",
            "play_type",
            "snapshot_type",
            "odds_data",
            "opening_odds",
            "latest_odds",
            "odds_movement",
            "update_time",
            "created_at",
            "updated_at",
        )
        if col in odds_cols
    ]
    rows = conn.execute(
        f"""
        SELECT {", ".join(select_cols)}
        FROM lottery_odds
        WHERE lottery_match_id IN ({",".join(["?"] * len(match_ids))})
        ORDER BY lottery_match_id, play_type, snapshot_type, created_at
        """,
        list(match_ids),
    ).fetchall()
    grouped: Dict[str, List[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[str(row["lottery_match_id"])].append(row)
    return grouped


def issue(
    issue_type: str,
    severity: str,
    match: sqlite3.Row,
    detail: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "type": issue_type,
        "severity": severity,
        "lottery_match_id": match["lottery_match_id"],
        "match_num": match["match_num"] if "match_num" in match.keys() else None,
        "teams": f"{match['home_team_cn']} vs {match['away_team_cn']}",
        **detail,
    }


def declared_play_types(match: sqlite3.Row) -> set[str]:
    raw = parse_json(match["play_types"] if "play_types" in match.keys() else None, [])
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    if isinstance(raw, dict):
        return {str(key).strip() for key, value in raw.items() if value}
    return set()


def has_odds_payload(row: sqlite3.Row) -> bool:
    data = parse_json(row["odds_data"] if "odds_data" in row.keys() else None, {})
    return isinstance(data, dict) and bool(data)


def audit_match(
    match: sqlite3.Row,
    rows: Sequence[sqlite3.Row],
    grace: timedelta,
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    kickoff = kickoff_time(match)
    if not kickoff:
        issues.append(issue("kickoff_parse_failed", "high", match, {}))
        return issues

    declared = declared_play_types(match)
    available = {str(row["play_type"]) for row in rows if has_odds_payload(row)}
    declared_missing = sorted(declared - available)
    odds_extra = sorted(available - declared)
    if declared_missing:
        issues.append(
            issue(
                "declared_play_type_missing_odds",
                "medium",
                match,
                {"play_types": declared_missing},
            )
        )
    if odds_extra:
        issues.append(
            issue(
                "odds_without_declared_play_type",
                "medium",
                match,
                {"play_types": odds_extra},
            )
        )

    key_counts = Counter((str(row["play_type"]), str(row["snapshot_type"] or "")) for row in rows)
    for (play_type, snapshot), count in sorted(key_counts.items()):
        if count > 1:
            issues.append(
                issue(
                    "duplicate_play_snapshot",
                    "medium",
                    match,
                    {"play_type": play_type, "snapshot_type": snapshot, "count": count},
                )
            )

    for row in rows:
        if not has_odds_payload(row):
            continue
        play_type = str(row["play_type"])
        snapshot = str(row["snapshot_type"] or "")
        captured_at = odds_timestamp(row)
        if captured_at and captured_at > kickoff + grace:
            severity = "high" if snapshot in {"opening", "midday"} else "medium"
            issues.append(
                issue(
                    "captured_after_kickoff",
                    severity,
                    match,
                    {
                        "play_type": play_type,
                        "snapshot_type": snapshot,
                        "kickoff": kickoff.isoformat(sep=" "),
                        "captured_at": captured_at.isoformat(sep=" "),
                        "minutes_after_kickoff": round((captured_at - kickoff).total_seconds() / 60, 1),
                    },
                )
            )
        if snapshot == "opening" and "opening_odds" in row.keys() and not row["opening_odds"]:
            issues.append(
                issue(
                    "opening_snapshot_missing_opening_odds_field",
                    "low",
                    match,
                    {"play_type": play_type, "captured_at": str(row["created_at"] if "created_at" in row.keys() else "")},
                )
            )
    return issues


def audit(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    conn = connect(db_path)
    try:
        matches = fetch_matches(conn, args)
        odds_by_match = fetch_odds(conn, [str(row["lottery_match_id"]) for row in matches])
        grace = timedelta(minutes=args.kickoff_grace_minutes)
        issues: List[Dict[str, Any]] = []
        for match in matches:
            rows = odds_by_match.get(str(match["lottery_match_id"]), [])
            issues.extend(audit_match(match, rows, grace))
        by_type = Counter(item["type"] for item in issues)
        by_severity = Counter(item["severity"] for item in issues)
        result = {
            "db": str(db_path),
            "date_from": args.date_from,
            "date_to": args.date_to,
            "league": None if args.all_leagues else args.league,
            "matches_checked": len(matches),
            "issue_count": len(issues),
            "matches_with_issues": len({item["lottery_match_id"] for item in issues}),
            "by_type": dict(sorted(by_type.items())),
            "by_severity": dict(sorted(by_severity.items())),
            "issues": [] if args.summary_only else issues[: args.preview_limit],
        }
        return result
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--date-from", default="2026-06-13")
    parser.add_argument("--date-to", default="2026-06-23")
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--all-leagues", action="store_true")
    parser.add_argument("--ids", default="")
    parser.add_argument("--kickoff-grace-minutes", type=int, default=5)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--preview-limit", type=int, default=200)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    result = audit(args)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
