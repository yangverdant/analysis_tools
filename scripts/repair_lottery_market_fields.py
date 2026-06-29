"""Repair derived lottery match market fields from stored lottery_odds.

The source of truth for available play types and the RQSPF goal line is
lottery_odds. This script backfills lottery_matches.play_types and
lottery_matches.handicap_line when collector/import paths left them empty or
with a stale value.

Dry-run is the default. Use --apply to write changes; a database backup is
created outside the project by default before applying.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "football_v2.db"
DEFAULT_BACKUP_DIR = Path(os.environ.get("FOOTBALL_BACKUP_DIR", REPO_ROOT.parent / "football_backups"))
DEFAULT_LEAGUE = "\u4e16\u754c\u676f"
PLAY_ORDER = ("spf", "rqspf", "bf", "bqc", "ttg", "ou")
SNAPSHOT_PRIORITY = {
    "latest": 0,
    "current": 1,
    "midday": 2,
    "opening": 3,
}


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def parse_jsonish(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return default
    text = value.strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        return ast.literal_eval(text)
    except Exception:
        return default


def parse_play_types(value: Any) -> List[str]:
    parsed = parse_jsonish(value, None)
    if isinstance(parsed, list):
        raw = parsed
    elif isinstance(value, str):
        raw = [item.strip() for item in value.split(",")]
    else:
        raw = []
    seen = set()
    result = []
    for item in raw:
        key = str(item or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return sort_play_types(result)


def sort_play_types(values: Iterable[str]) -> List[str]:
    order = {name: index for index, name in enumerate(PLAY_ORDER)}
    return sorted({str(item).strip().lower() for item in values if str(item).strip()}, key=lambda x: (order.get(x, 99), x))


def dump_play_types(values: Sequence[str]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def normalize_handicap_from_goal_line(goal_line: Any) -> Optional[float]:
    parsed = safe_float(goal_line)
    if parsed is None:
        return None
    # Internal convention: positive means home gives goals.
    # Sporttery goal_line: -2 means home gives 2, +1 means home receives 1.
    return -parsed


def format_number(value: Optional[float]) -> Any:
    if value is None:
        return None
    if abs(value - round(value)) < 1e-9:
        return int(round(value))
    return round(float(value), 4)


def ensure_audit_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lottery_market_field_repairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            lottery_match_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            source_json TEXT,
            applied INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def backup_db(db_path: Path, backup_root: Path) -> Path:
    backup_dir = backup_root / "market_field_repairs"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_before_market_field_repair_{stamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def fetch_matches(
    conn: sqlite3.Connection,
    ids: Sequence[str],
    date_from: str,
    date_to: str,
    league: str,
    all_leagues: bool,
) -> List[sqlite3.Row]:
    where = ["1=1"]
    params: List[Any] = []
    if ids:
        where.append("lottery_match_id IN ({})".format(",".join(["?"] * len(ids))))
        params.extend(ids)
    if date_from:
        where.append("date(match_date) >= date(?)")
        params.append(date_from)
    if date_to:
        where.append("date(match_date) <= date(?)")
        params.append(date_to)
    if league and not all_leagues:
        where.append("league_name_cn = ?")
        params.append(league)

    return conn.execute(
        f"""
        SELECT lottery_match_id, match_num, league_name_cn, match_date, beijing_time,
               home_team_cn, away_team_cn, play_types, handicap_line
        FROM lottery_matches
        WHERE {' AND '.join(where)}
        ORDER BY date(match_date), beijing_time, lottery_match_id
        """,
        params,
    ).fetchall()


def fetch_odds(conn: sqlite3.Connection, match_ids: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not match_ids:
        return {}
    placeholders = ",".join(["?"] * len(match_ids))
    rows = conn.execute(
        f"""
        SELECT lottery_match_id, play_type, odds_data, snapshot_type, update_time, created_at
        FROM lottery_odds
        WHERE lottery_match_id IN ({placeholders})
        ORDER BY lottery_match_id, play_type
        """,
        list(match_ids),
    ).fetchall()
    result: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        item = dict(row)
        item["odds_data_parsed"] = parse_jsonish(row["odds_data"], {})
        result.setdefault(str(row["lottery_match_id"]), []).append(item)
    return result


def latest_rqspf_goal_line(odds_rows: Sequence[Dict[str, Any]]) -> Optional[Any]:
    rqspf = [row for row in odds_rows if str(row.get("play_type") or "").lower() == "rqspf"]
    if not rqspf:
        return None

    def sort_key(row: Dict[str, Any]) -> tuple:
        snapshot = str(row.get("snapshot_type") or "")
        stamp = row.get("update_time") or row.get("created_at") or ""
        return (SNAPSHOT_PRIORITY.get(snapshot, 99), str(stamp), str(row.get("created_at") or ""))

    for row in sorted(rqspf, key=sort_key):
        data = row.get("odds_data_parsed")
        if isinstance(data, dict) and data.get("goal_line") not in (None, ""):
            return data.get("goal_line")
    return None


def plan_repairs(rows: Sequence[sqlite3.Row], odds_by_match: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []
    for row in rows:
        match_id = str(row["lottery_match_id"])
        odds_rows = odds_by_match.get(match_id, [])
        derived_play_types = sort_play_types(row.get("play_type") for row in odds_rows)
        current_play_types = parse_play_types(row["play_types"])
        current_play_types_raw = str(row["play_types"] or "").strip()
        canonical_play_types_raw = dump_play_types(derived_play_types)
        if derived_play_types and (
            current_play_types != derived_play_types
            or current_play_types_raw != canonical_play_types_raw
        ):
            changes.append(
                {
                    "lottery_match_id": match_id,
                    "match_num": row["match_num"],
                    "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
                    "field": "play_types",
                    "old": current_play_types,
                    "new": derived_play_types,
                    "source": {
                        "odds_play_types": derived_play_types,
                        "old_raw": current_play_types_raw,
                        "new_raw": canonical_play_types_raw,
                    },
                }
            )

        goal_line = latest_rqspf_goal_line(odds_rows)
        derived_handicap = normalize_handicap_from_goal_line(goal_line)
        current_handicap = safe_float(row["handicap_line"]) or 0.0
        if derived_handicap is not None and abs(current_handicap - derived_handicap) > 1e-9:
            changes.append(
                {
                    "lottery_match_id": match_id,
                    "match_num": row["match_num"],
                    "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
                    "field": "handicap_line",
                    "old": format_number(current_handicap),
                    "new": format_number(derived_handicap),
                    "source": {"rqspf_goal_line": goal_line, "convention": "handicap_line=-goal_line"},
                }
            )
    return changes


def apply_repairs(conn: sqlite3.Connection, changes: Sequence[Dict[str, Any]], run_id: str) -> None:
    ensure_audit_table(conn)
    for change in changes:
        match_id = change["lottery_match_id"]
        field = change["field"]
        if field == "play_types":
            new_value = dump_play_types(change["new"])
            conn.execute(
                "UPDATE lottery_matches SET play_types=?, updated_at=CURRENT_TIMESTAMP WHERE lottery_match_id=?",
                (new_value, match_id),
            )
        elif field == "handicap_line":
            new_value = float(change["new"])
            conn.execute(
                "UPDATE lottery_matches SET handicap_line=?, updated_at=CURRENT_TIMESTAMP WHERE lottery_match_id=?",
                (new_value, match_id),
            )
        else:
            continue
        conn.execute(
            """
            INSERT INTO lottery_market_field_repairs (
                run_id, lottery_match_id, field_name, old_value, new_value,
                source_json, applied
            ) VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (
                run_id,
                match_id,
                field,
                json.dumps(change["old"], ensure_ascii=False),
                json.dumps(change["new"], ensure_ascii=False),
                json.dumps(change.get("source", {}), ensure_ascii=False),
            ),
        )


def summarize_changes(changes: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for change in changes:
        summary[change["field"]] = summary.get(change["field"], 0) + 1
    return summary


def repair(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    ids = [item.strip() for item in str(args.ids or "").split(",") if item.strip()]
    conn = connect(db_path)
    try:
        if not table_exists(conn, "lottery_matches") or not table_exists(conn, "lottery_odds"):
            raise SystemExit("Required tables lottery_matches/lottery_odds are missing.")
        rows = fetch_matches(conn, ids, args.date_from, args.date_to, args.league, args.all_leagues)
        odds_by_match = fetch_odds(conn, [str(row["lottery_match_id"]) for row in rows])
        changes = plan_repairs(rows, odds_by_match)
        backup_path = None
        if args.apply and changes and not args.no_backup:
            backup_path = backup_db(db_path, Path(args.backup_dir))
        run_id = f"market_fields_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        if args.apply and changes:
            apply_repairs(conn, changes, run_id)
            conn.commit()
        else:
            conn.rollback()
        return {
            "db": str(db_path),
            "mode": "apply" if args.apply else "dry_run",
            "date_from": args.date_from,
            "date_to": args.date_to,
            "league": None if args.all_leagues else args.league,
            "matches_scanned": len(rows),
            "matches_with_odds": sum(1 for row in rows if odds_by_match.get(str(row["lottery_match_id"]))),
            "changes": len(changes),
            "changes_by_field": summarize_changes(changes),
            "backup": str(backup_path) if backup_path else None,
            "preview": list(changes[: args.preview_limit]),
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--ids", default="", help="Comma-separated lottery_match_id values")
    parser.add_argument("--date-from", default="2026-06-13")
    parser.add_argument("--date-to", default="2026-06-23")
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--all-leagues", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--preview-limit", type=int, default=80)
    args = parser.parse_args()
    result = repair(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
