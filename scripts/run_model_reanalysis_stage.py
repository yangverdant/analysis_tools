"""Versioned model re-analysis for settled matches.

This script reruns only the analysis/model output layer. It does not refetch or
overwrite factual data such as matches, odds, results, or source artifacts.

Workflow:
1. Select settled match dates.
2. Backup current analysis outputs for those dates outside the project tree.
3. Rerun analysis for the selected settled matches.
4. Rebuild validation/reviews and compare accuracy before/after.
5. Optionally rollback analysis outputs if the new version is worse.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"
BACKUP_ROOT = Path(os.environ.get("FOOTBALL_BACKUP_DIR", ROOT.parent / "football_backups")) / "model_reanalysis"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.analyze import analyze_single  # noqa: E402
from backend.app.core.validate import _validate_predictions  # noqa: E402
from backend.app.data_access.foundation_dao import FoundationDAO  # noqa: E402


ANALYSIS_LAYER_TABLES = {
    "lottery_analysis_reports": "lottery_match_id",
    "lottery_predictions": "lottery_match_id",
    "lottery_validation": "lottery_match_id",
    "post_match_reviews": "match_key",
    "match_feature_snapshots": "match_key",
    "match_context_snapshots": "match_key",
}


def log(message: str, payload: Optional[Any] = None) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str), flush=True)


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> List[str]:
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def placeholders(values: Sequence[Any]) -> str:
    return ",".join(["?"] * len(values))


def parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def default_range(days: int, latest_offset_days: int) -> tuple[str, str]:
    end = datetime.now().date() - timedelta(days=max(latest_offset_days, 0))
    start = end - timedelta(days=max(days - 1, 0))
    return start.isoformat(), end.isoformat()


def target_dates(conn: sqlite3.Connection, args: argparse.Namespace) -> List[str]:
    date_from = args.date_from
    date_to = args.date_to
    if not date_from or not date_to:
        date_from, date_to = default_range(args.days, args.latest_offset_days)

    where = [
        "substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?",
        "lr.home_goals_ft IS NOT NULL",
        "lr.away_goals_ft IS NOT NULL",
    ]
    params: List[Any] = [date_from, date_to]
    if args.league:
        where.append("COALESCE(lm.league_name_cn, '') = ?")
        params.append(args.league)
    if args.require_existing_analysis:
        where.append(
            """
            EXISTS (
                SELECT 1
                FROM lottery_analysis_reports ar
                WHERE ar.lottery_match_id = lm.lottery_match_id
                  AND ar.report_type IN ('prediction', 'full')
            )
            """
        )

    rows = conn.execute(
        f"""
        SELECT substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) AS d,
               COUNT(*) AS settled_matches
        FROM lottery_matches lm
        JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
        WHERE {' AND '.join(where)}
        GROUP BY d
        ORDER BY d DESC
        LIMIT ?
        """,
        [*params, args.max_dates],
    ).fetchall()
    return [str(row["d"]) for row in rows]


def target_match_ids(conn: sqlite3.Connection, dates: Sequence[str], league: str = "") -> List[str]:
    if not dates:
        return []
    where = [
        f"substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) IN ({placeholders(dates)})",
        "lr.home_goals_ft IS NOT NULL",
        "lr.away_goals_ft IS NOT NULL",
        "lm.home_team_id IS NOT NULL",
        "lm.away_team_id IS NOT NULL",
    ]
    params: List[Any] = list(dates)
    if league:
        where.append("COALESCE(lm.league_name_cn, '') = ?")
        params.append(league)
    rows = conn.execute(
        f"""
        SELECT lm.lottery_match_id
        FROM lottery_matches lm
        JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
        WHERE {' AND '.join(where)}
        ORDER BY substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10),
                 COALESCE(lm.beijing_time, lm.match_date || ' ' || COALESCE(lm.match_time, '99:99')),
                 lm.lottery_match_id
        """,
        params,
    ).fetchall()
    return [str(row["lottery_match_id"]) for row in rows]


def load_table_rows(conn: sqlite3.Connection, table: str, key_column: str, match_ids: Sequence[str]) -> List[Dict[str, Any]]:
    if not match_ids or not table_exists(conn, table):
        return []
    rows = conn.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE {key_column} IN ({placeholders(match_ids)})
        """,
        list(match_ids),
    ).fetchall()
    return [dict(row) for row in rows]


def backup_analysis_layer(
    db_path: Path,
    conn: sqlite3.Connection,
    match_ids: Sequence[str],
    dates: Sequence[str],
    version_tag: str,
) -> Path:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_ROOT / f"analysis_layer_{version_tag}_{stamp}.json"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "database": str(db_path),
        "version_tag": version_tag,
        "dates": list(dates),
        "match_ids": list(match_ids),
        "tables": {
            table: {
                "key_column": key_column,
                "columns": columns(conn, table) if table_exists(conn, table) else [],
                "rows": load_table_rows(conn, table, key_column, match_ids),
            }
            for table, key_column in ANALYSIS_LAYER_TABLES.items()
        },
    }
    backup_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return backup_path


def backup_plan_path(version_tag: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return BACKUP_ROOT / f"analysis_layer_{version_tag}_{stamp}.json"


def stats_for_matches(conn: sqlite3.Connection, match_ids: Sequence[str]) -> Dict[str, Any]:
    if not match_ids or not table_exists(conn, "lottery_validation"):
        return {"total": 0, "correct": 0, "accuracy": 0, "by_play_type": {}}
    rows = conn.execute(
        f"""
        SELECT play_type,
               COUNT(*) AS total,
               SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS correct
        FROM lottery_validation
        WHERE lottery_match_id IN ({placeholders(match_ids)})
        GROUP BY play_type
        ORDER BY play_type
        """,
        list(match_ids),
    ).fetchall()
    total = 0
    correct = 0
    by_play = {}
    for row in rows:
        count = int(row["total"] or 0)
        hits = int(row["correct"] or 0)
        by_play[str(row["play_type"])] = {
            "total": count,
            "correct": hits,
            "accuracy": round(hits * 100 / count, 1) if count else 0,
        }
        total += count
        correct += hits
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct * 100 / total, 1) if total else 0,
        "by_play_type": by_play,
    }


def _validation_key(row: Dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("lottery_match_id") or ""), str(row.get("play_type") or ""))


def _as_correct(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def validation_candidate_changes(
    conn: sqlite3.Connection,
    backup_path: Path,
    match_ids: Sequence[str],
    limit: int = 50,
) -> Dict[str, Any]:
    """Compare pre-experiment validation rows with current rows before rollback.

    This makes rejected model experiments inspectable after the database is
    restored: the summary retains exactly which play changed, improved or
    regressed.
    """
    if not match_ids or not backup_path.exists() or not table_exists(conn, "lottery_validation"):
        return {"summary": {"total_changes": 0}, "changes": []}

    payload = json.loads(backup_path.read_text(encoding="utf-8"))
    before_rows = (((payload.get("tables") or {}).get("lottery_validation") or {}).get("rows") or [])
    before_map = {_validation_key(row): row for row in before_rows if _validation_key(row)[0] and _validation_key(row)[1]}
    current_rows = conn.execute(
        f"""
        SELECT lv.lottery_match_id, lv.play_type, lv.predicted_result,
               lv.actual_result, lv.is_correct,
               lm.match_num, lm.match_date, lm.beijing_time,
               lm.league_name_cn, lm.home_team_cn, lm.away_team_cn,
               lr.home_goals_ft, lr.away_goals_ft,
               lr.home_goals_ht, lr.away_goals_ht
        FROM lottery_validation lv
        JOIN lottery_matches lm ON lm.lottery_match_id = lv.lottery_match_id
        LEFT JOIN lottery_results lr ON lr.lottery_match_id = lv.lottery_match_id
        WHERE lv.lottery_match_id IN ({placeholders(match_ids)})
        ORDER BY substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10),
                 COALESCE(lm.beijing_time, lm.match_date),
                 lm.match_num,
                 lv.play_type
        """,
        list(match_ids),
    ).fetchall()

    summary: Dict[str, Any] = {
        "total_changes": 0,
        "improved": 0,
        "regressed": 0,
        "prediction_changed_only": 0,
        "by_play_type": {},
    }
    changes: List[Dict[str, Any]] = []
    for row in current_rows:
        key = (str(row["lottery_match_id"]), str(row["play_type"] or ""))
        before = before_map.get(key)
        if not before:
            continue
        before_correct = _as_correct(before.get("is_correct"))
        after_correct = _as_correct(row["is_correct"])
        before_predicted = "" if before.get("predicted_result") is None else str(before.get("predicted_result"))
        after_predicted = "" if row["predicted_result"] is None else str(row["predicted_result"])
        before_actual = "" if before.get("actual_result") is None else str(before.get("actual_result"))
        after_actual = "" if row["actual_result"] is None else str(row["actual_result"])
        if before_correct == after_correct and before_predicted == after_predicted and before_actual == after_actual:
            continue
        if after_correct > before_correct:
            direction = "improved"
        elif after_correct < before_correct:
            direction = "regressed"
        else:
            direction = "changed"
        play_type = key[1]
        bucket = summary["by_play_type"].setdefault(play_type, {"changes": 0, "improved": 0, "regressed": 0, "changed": 0})
        bucket["changes"] += 1
        bucket[direction] += 1
        summary["total_changes"] += 1
        if direction == "improved":
            summary["improved"] += 1
        elif direction == "regressed":
            summary["regressed"] += 1
        else:
            summary["prediction_changed_only"] += 1
        if len(changes) < limit:
            changes.append(
                {
                    "match_key": key[0],
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
                    "direction": direction,
                    "before": {"predicted": before_predicted, "actual": before_actual, "is_correct": bool(before_correct)},
                    "after": {"predicted": after_predicted, "actual": after_actual, "is_correct": bool(after_correct)},
                }
            )
    return {"summary": summary, "changes": changes}


def protected_play_type_regressions(
    before_stats: Dict[str, Any],
    after_stats: Dict[str, Any],
    protected_play_types: Sequence[str],
) -> List[Dict[str, Any]]:
    before_by_type = before_stats.get("by_play_type") or {}
    after_by_type = after_stats.get("by_play_type") or {}
    regressions: List[Dict[str, Any]] = []
    for play_type in protected_play_types:
        play_type = str(play_type or "").strip()
        if not play_type:
            continue
        before = before_by_type.get(play_type) or {}
        after = after_by_type.get(play_type) or {}
        before_correct = int(before.get("correct") or 0)
        after_correct = int(after.get("correct") or 0)
        delta = after_correct - before_correct
        if delta < 0:
            regressions.append(
                {
                    "play_type": play_type,
                    "before_correct": before_correct,
                    "after_correct": after_correct,
                    "delta_correct": delta,
                    "before_accuracy": before.get("accuracy"),
                    "after_accuracy": after.get("accuracy"),
                }
            )
    return regressions


def delete_analysis_layer(conn: sqlite3.Connection, match_ids: Sequence[str]) -> Dict[str, int]:
    deleted = {}
    if not match_ids:
        return deleted
    ids_sql = placeholders(match_ids)
    for table, key_column in ANALYSIS_LAYER_TABLES.items():
        if not table_exists(conn, table):
            deleted[table] = 0
            continue
        cursor = conn.execute(
            f"DELETE FROM {table} WHERE {key_column} IN ({ids_sql})",
            list(match_ids),
        )
        deleted[table] = int(cursor.rowcount or 0)
    return deleted


def insert_rows(conn: sqlite3.Connection, table: str, rows: Sequence[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    table_cols = columns(conn, table)
    inserted = 0
    for row in rows:
        cols = [col for col in table_cols if col in row]
        if not cols:
            continue
        sql = f"""
            INSERT OR REPLACE INTO {table} ({', '.join(cols)})
            VALUES ({', '.join(['?'] * len(cols))})
        """
        conn.execute(sql, [row.get(col) for col in cols])
        inserted += 1
    return inserted


def restore_backup(db_path: Path, backup_path: Path) -> Dict[str, Any]:
    payload = json.loads(backup_path.read_text(encoding="utf-8"))
    match_ids = [str(item) for item in payload.get("match_ids") or []]
    with connect(db_path) as conn:
        deleted = delete_analysis_layer(conn, match_ids)
        inserted = {}
        for table, data in (payload.get("tables") or {}).items():
            if not table_exists(conn, table):
                inserted[table] = 0
                continue
            inserted[table] = insert_rows(conn, table, data.get("rows") or [])
        conn.commit()
    return {"deleted_current": deleted, "restored_rows": inserted}


def reanalyze_matches(db_path: Path, match_ids: Sequence[str], limit: int = 0) -> Dict[str, Any]:
    analyzed = []
    failed = []
    selected = list(match_ids)[: limit if limit and limit > 0 else None]
    for match_id in selected:
        try:
            report = analyze_single(str(db_path), match_id)
            if report:
                analyzed.append(match_id)
            else:
                failed.append({"lottery_match_id": match_id, "error": "empty_report"})
        except Exception as exc:
            failed.append({"lottery_match_id": match_id, "error": str(exc)[:200]})
    return {
        "targets": len(selected),
        "analyzed": len(analyzed),
        "failed": len(failed),
        "failed_examples": failed[:10],
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    version_tag = args.version_tag or f"model_stage_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    foundation = FoundationDAO(str(db_path))
    run_id = foundation.start_run(
        run_type="model_reanalysis_stage",
        match_date=datetime.now().date().isoformat(),
        trigger_source="model_reanalysis_script",
        summary={"stage": "start", "version_tag": version_tag, "args": vars(args)},
    )
    summary: Dict[str, Any] = {"run_id": run_id, "version_tag": version_tag}
    try:
        with connect(db_path) as conn:
            dates = target_dates(conn, args)
            match_ids = target_match_ids(conn, dates, args.league or "")
            before_stats = stats_for_matches(conn, match_ids)
            backup_path = (
                backup_analysis_layer(db_path, conn, match_ids, dates, version_tag)
                if args.apply
                else backup_plan_path(version_tag)
            )

        summary.update(
            {
                "mode": "apply" if args.apply else "dry_run",
                "dates": dates,
                "target_matches": len(match_ids),
                "backup_path": str(backup_path) if args.apply else None,
                "backup_path_if_applied": str(backup_path) if not args.apply else None,
                "stats_before": before_stats,
            }
        )
        log("MODEL REANALYSIS PLAN", summary)

        if not args.apply:
            foundation.finish_run(run_id, status="success", summary=summary)
            return {"success": True, **summary}

        summary["reanalyze"] = reanalyze_matches(db_path, match_ids, args.limit_matches)
        validation_result = _validate_predictions(str(db_path), dates)
        summary["validation"] = validation_result
        with connect(db_path) as conn:
            after_stats = stats_for_matches(conn, match_ids)
            summary["candidate_changes"] = validation_candidate_changes(conn, backup_path, match_ids)
        summary["stats_after"] = after_stats

        before_accuracy = float(before_stats.get("accuracy") or 0)
        after_accuracy = float(after_stats.get("accuracy") or 0)
        summary["accuracy_delta"] = round(after_accuracy - before_accuracy, 2)
        summary["accepted"] = True
        protected_play_types = [
            item.strip()
            for item in str(args.protected_play_types or "").split(",")
            if item.strip()
        ]
        play_regressions = protected_play_type_regressions(before_stats, after_stats, protected_play_types)
        summary["protected_play_type_regressions"] = play_regressions

        if args.rollback_on_worse and after_accuracy + args.rollback_tolerance < before_accuracy:
            restore = restore_backup(db_path, backup_path)
            with connect(db_path) as conn:
                restored_stats = stats_for_matches(conn, match_ids)
            summary["accepted"] = False
            summary["rollback"] = {
                "reason": "accuracy_worse",
                "before_accuracy": before_accuracy,
                "after_accuracy": after_accuracy,
                "tolerance": args.rollback_tolerance,
                "restore": restore,
                "stats_restored": restored_stats,
            }
        elif args.rollback_on_protected_play_worse and play_regressions:
            restore = restore_backup(db_path, backup_path)
            with connect(db_path) as conn:
                restored_stats = stats_for_matches(conn, match_ids)
            summary["accepted"] = False
            summary["rollback"] = {
                "reason": "protected_play_type_worse",
                "regressions": play_regressions,
                "restore": restore,
                "stats_restored": restored_stats,
            }

        foundation.finish_run(run_id, status="success", summary=summary)
        log("MODEL REANALYSIS FINISH", summary)
        return {"success": True, **summary}
    except Exception as exc:
        summary["success"] = False
        summary["error"] = str(exc)
        foundation.finish_run(run_id, status="failed", summary=summary, error=str(exc))
        log("MODEL REANALYSIS FAILED", summary)
        return summary


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--from", dest="date_from", default=None)
    parser.add_argument("--to", dest="date_to", default=None)
    parser.add_argument("--days", type=int, default=7, help="Default date window when --from/--to are omitted")
    parser.add_argument("--latest-offset-days", type=int, default=1)
    parser.add_argument("--league", default="", help="Optional league filter; empty means all")
    parser.add_argument("--max-dates", type=int, default=1, help="Dates per stage")
    parser.add_argument("--limit-matches", type=int, default=0, help="Optional cap inside selected dates")
    parser.add_argument("--version-tag", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--require-existing-analysis", action="store_true", default=True)
    parser.add_argument("--include-without-existing-analysis", dest="require_existing_analysis", action="store_false")
    parser.add_argument("--rollback-on-worse", action="store_true")
    parser.add_argument("--rollback-tolerance", type=float, default=0.0, help="Allowed percentage-point drop before rollback")
    parser.add_argument("--rollback-on-protected-play-worse", action="store_true", help="Rollback if any protected play type loses correct picks")
    parser.add_argument("--protected-play-types", default="ou,bqc", help="Comma-separated play types for protected rollback checks")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    result = run(args)
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
