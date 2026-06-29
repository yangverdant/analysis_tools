"""Export, import, verify, or restore lottery analysis-layer patches.

The patch contains derived analysis data only:
- lottery_analysis_reports active prediction reports
- lottery_predictions rows

Import is dry-run by default. With --apply it keeps old reports as stale,
replaces prediction rows, deletes affected validation/review rows, and can
rebuild validation. A compact SQLite backup is written outside the project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"
DEFAULT_LEAGUE = "\u4e16\u754c\u676f"
BACKUP_DIR = Path(os.environ.get("FOOTBALL_BACKUP_DIR", ROOT.parent / "football_backups")) / "analysis_layer_sync"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def require_existing_file(path: Path, label: str) -> None:
    if not path.exists() or not path.is_file():
        raise SystemExit(f"{label} not found: {path}")


def table_exists(conn: sqlite3.Connection, table: str, schema: str = "main") -> bool:
    master = "sqlite_master" if schema == "main" else f"{schema}.sqlite_master"
    return conn.execute(
        f"SELECT 1 FROM {master} WHERE type='table' AND name = ?",
        (table,),
    ).fetchone() is not None


def table_columns(conn: sqlite3.Connection, table: str, schema: str = "main") -> List[str]:
    if schema == "main":
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    else:
        rows = conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()
    return [str(row["name"]) for row in rows]


def placeholders(values: Sequence[Any]) -> str:
    return ",".join(["?"] * len(values))


def sha16(value: Any) -> str:
    raw = "" if value is None else str(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def split_csv(value: str) -> List[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def date_expr(alias: str = "lm") -> str:
    return f"substr(COALESCE({alias}.beijing_time, {alias}.match_date), 1, 10)"


def patch_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE target_match_ids (
            lottery_match_id TEXT PRIMARY KEY,
            match_num TEXT,
            match_date TEXT,
            home_team_cn TEXT,
            away_team_cn TEXT
        );
        CREATE TABLE analysis_reports (
            lottery_match_id TEXT NOT NULL,
            match_id INTEGER,
            report_type TEXT,
            report_data TEXT NOT NULL,
            created_at TEXT,
            is_stale INTEGER DEFAULT 0
        );
        CREATE TABLE predictions (
            lottery_match_id TEXT NOT NULL,
            match_id INTEGER,
            play_type TEXT NOT NULL,
            predictions TEXT NOT NULL,
            recommendation TEXT,
            confidence REAL,
            confidence_level TEXT,
            has_value_bet INTEGER DEFAULT 0,
            value_bets TEXT,
            features_json TEXT,
            weights_json TEXT,
            model_version TEXT,
            created_at TEXT
        );
        """
    )


def target_match_rows(
    conn: sqlite3.Connection,
    *,
    date_from: str,
    date_to: str,
    league: str,
    match_nums: str,
    settled_only: bool,
    report_type: str,
) -> List[sqlite3.Row]:
    where = [
        "EXISTS (SELECT 1 FROM lottery_analysis_reports ar "
        "WHERE ar.lottery_match_id = lm.lottery_match_id "
        "AND ar.report_type = ? AND COALESCE(ar.is_stale, 0) = 0)"
    ]
    params: List[Any] = [report_type]
    if date_from:
        where.append(f"{date_expr()} >= ?")
        params.append(date_from)
    if date_to:
        where.append(f"{date_expr()} <= ?")
        params.append(date_to)
    if league:
        where.append("COALESCE(lm.league_name_cn, '') = ?")
        params.append(league)
    nums = split_csv(match_nums)
    if nums:
        where.append(f"lm.match_num IN ({placeholders(nums)})")
        params.extend(nums)
    if settled_only:
        where.append(
            "EXISTS (SELECT 1 FROM lottery_results lr "
            "WHERE lr.lottery_match_id = lm.lottery_match_id "
            "AND COALESCE(lr.spf_result, '') <> '')"
        )
    return conn.execute(
        f"""
        SELECT lm.lottery_match_id, lm.match_num, {date_expr()} AS match_date,
               lm.home_team_cn, lm.away_team_cn
        FROM lottery_matches lm
        WHERE {" AND ".join(where)}
        ORDER BY match_date, lm.match_num, lm.lottery_match_id
        """,
        params,
    ).fetchall()


def export_patch(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    output_path = Path(args.output)
    require_existing_file(db_path, "source db")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not args.force:
        raise SystemExit(f"output already exists: {output_path}")
    if output_path.exists():
        output_path.unlink()

    with connect(db_path) as source, connect(output_path) as patch:
        patch_schema(patch)
        rows = target_match_rows(
            source,
            date_from=args.date_from,
            date_to=args.date_to,
            league=args.league,
            match_nums=args.match_nums,
            settled_only=args.settled_only,
            report_type=args.report_type,
        )
        ids = [str(row["lottery_match_id"]) for row in rows]
        patch.executemany(
            "INSERT INTO target_match_ids VALUES (?, ?, ?, ?, ?)",
            [tuple(row) for row in rows],
        )
        reports: List[tuple] = []
        predictions: List[tuple] = []
        if ids:
            id_sql = placeholders(ids)
            report_rows = source.execute(
                f"""
                SELECT lottery_match_id, match_id, report_type, report_data,
                       created_at, COALESCE(is_stale, 0) AS is_stale
                FROM lottery_analysis_reports
                WHERE lottery_match_id IN ({id_sql})
                  AND report_type = ?
                  AND COALESCE(is_stale, 0) = 0
                ORDER BY lottery_match_id, datetime(created_at) DESC, report_id DESC
                """,
                ids + [args.report_type],
            ).fetchall()
            seen = set()
            for row in report_rows:
                match_id = str(row["lottery_match_id"])
                if match_id in seen:
                    continue
                seen.add(match_id)
                reports.append(tuple(row))
            pred_rows = source.execute(
                f"""
                SELECT lottery_match_id, match_id, play_type, predictions,
                       recommendation, confidence, confidence_level,
                       has_value_bet, value_bets, features_json, weights_json,
                       model_version, created_at
                FROM lottery_predictions
                WHERE lottery_match_id IN ({id_sql})
                ORDER BY lottery_match_id, play_type, prediction_id
                """,
                ids,
            ).fetchall()
            predictions = [tuple(row) for row in pred_rows]

        patch.executemany("INSERT INTO analysis_reports VALUES (?, ?, ?, ?, ?, ?)", reports)
        patch.executemany("INSERT INTO predictions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", predictions)
        meta = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_db": str(db_path.resolve()),
            "league": args.league,
            "date_from": args.date_from,
            "date_to": args.date_to,
            "match_nums": args.match_nums,
            "settled_only": str(bool(args.settled_only)),
            "report_type": args.report_type,
            "match_count": str(len(ids)),
        }
        patch.executemany("INSERT INTO meta VALUES (?, ?)", sorted(meta.items()))
        patch.commit()

    return inspect_patch(output_path)


def inspect_patch(patch_path: Path) -> Dict[str, Any]:
    require_existing_file(patch_path, "patch")
    with connect(patch_path) as conn:
        meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta").fetchall()}
        return {
            "success": True,
            "patch": str(patch_path),
            "size_kb": round(patch_path.stat().st_size / 1024, 1),
            "meta": meta,
            "matches": conn.execute("SELECT COUNT(*) FROM target_match_ids").fetchone()[0],
            "reports": conn.execute("SELECT COUNT(*) FROM analysis_reports").fetchone()[0],
            "predictions": conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0],
        }


def patch_ids(conn: sqlite3.Connection) -> List[str]:
    return [str(row["lottery_match_id"]) for row in conn.execute("SELECT lottery_match_id FROM p.target_match_ids")]


def current_counts(conn: sqlite3.Connection, ids: Sequence[str], report_type: str) -> Dict[str, Any]:
    if not ids:
        return {
            "missing_matches": [],
            "reports": 0,
            "active_reports": 0,
            "predictions": 0,
            "validations": 0,
            "reviews": 0,
        }
    id_sql = placeholders(ids)
    missing = []
    for match_id in ids:
        exists = conn.execute(
            "SELECT 1 FROM lottery_matches WHERE lottery_match_id = ?",
            (match_id,),
        ).fetchone()
        if not exists:
            missing.append(str(match_id))
    return {
        "missing_matches": missing,
        "reports": conn.execute(
            f"SELECT COUNT(*) FROM lottery_analysis_reports WHERE lottery_match_id IN ({id_sql}) AND report_type = ?",
            list(ids) + [report_type],
        ).fetchone()[0],
        "active_reports": conn.execute(
            f"SELECT COUNT(*) FROM lottery_analysis_reports WHERE lottery_match_id IN ({id_sql}) AND report_type = ? AND COALESCE(is_stale, 0) = 0",
            list(ids) + [report_type],
        ).fetchone()[0],
        "predictions": conn.execute(
            f"SELECT COUNT(*) FROM lottery_predictions WHERE lottery_match_id IN ({id_sql})",
            list(ids),
        ).fetchone()[0],
        "validations": conn.execute(
            f"SELECT COUNT(*) FROM lottery_validation WHERE lottery_match_id IN ({id_sql})",
            list(ids),
        ).fetchone()[0]
        if table_exists(conn, "lottery_validation")
        else 0,
        "reviews": conn.execute(
            f"SELECT COUNT(*) FROM post_match_reviews WHERE match_key IN ({id_sql})",
            list(ids),
        ).fetchone()[0]
        if table_exists(conn, "post_match_reviews")
        else 0,
    }


def create_backup(conn: sqlite3.Connection, ids: Sequence[str], *, backup_dir: Path, report_type: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"analysis_layer_before_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    conn.execute("ATTACH DATABASE ? AS b", (str(backup_path),))
    conn.execute("CREATE TABLE b.meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany(
        "INSERT INTO b.meta VALUES (?, ?)",
        [
            ("created_at", datetime.now().isoformat(timespec="seconds")),
            ("report_type", report_type),
            ("match_count", str(len(ids))),
        ],
    )
    conn.execute("CREATE TABLE b.target_match_ids AS SELECT * FROM p.target_match_ids")
    id_sql = placeholders(ids)
    conn.execute(
        f"CREATE TABLE b.lottery_analysis_reports AS "
        f"SELECT * FROM main.lottery_analysis_reports WHERE lottery_match_id IN ({id_sql}) AND report_type = ?",
        list(ids) + [report_type],
    )
    conn.execute(
        f"CREATE TABLE b.lottery_predictions AS "
        f"SELECT * FROM main.lottery_predictions WHERE lottery_match_id IN ({id_sql})",
        list(ids),
    )
    if table_exists(conn, "lottery_validation"):
        conn.execute(
            f"CREATE TABLE b.lottery_validation AS "
            f"SELECT * FROM main.lottery_validation WHERE lottery_match_id IN ({id_sql})",
            list(ids),
        )
    else:
        conn.execute("CREATE TABLE b.lottery_validation (lottery_match_id TEXT)")
    if table_exists(conn, "post_match_reviews"):
        conn.execute(
            f"CREATE TABLE b.post_match_reviews AS "
            f"SELECT * FROM main.post_match_reviews WHERE match_key IN ({id_sql})",
            list(ids),
        )
    else:
        conn.execute("CREATE TABLE b.post_match_reviews (match_key TEXT)")
    conn.commit()
    conn.execute("DETACH DATABASE b")
    return backup_path


def patch_dates(conn: sqlite3.Connection) -> List[str]:
    return [
        str(row["match_date"])
        for row in conn.execute(
            "SELECT DISTINCT match_date FROM p.target_match_ids WHERE match_date IS NOT NULL ORDER BY match_date"
        ).fetchall()
        if row["match_date"]
    ]


def import_patch(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    patch_path = Path(args.patch)
    require_existing_file(db_path, "target db")
    require_existing_file(patch_path, "patch")
    with connect(db_path) as conn:
        conn.execute("ATTACH DATABASE ? AS p", (str(patch_path),))
        meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM p.meta").fetchall()}
        report_type = str(meta.get("report_type") or args.report_type)
        ids = patch_ids(conn)
        patch_summary = {
            "matches": len(ids),
            "reports": conn.execute("SELECT COUNT(*) FROM p.analysis_reports").fetchone()[0],
            "predictions": conn.execute("SELECT COUNT(*) FROM p.predictions").fetchone()[0],
        }
        before = current_counts(conn, ids, report_type)
        result: Dict[str, Any] = {
            "success": True,
            "mode": "apply" if args.apply else "dry_run",
            "db": str(db_path),
            "patch": str(patch_path),
            "patch_meta": meta,
            "patch_counts": patch_summary,
            "target_before": before,
        }
        if before["missing_matches"]:
            result["success"] = False
            result["error"] = "target database is missing patch matches"
            return result
        if not args.apply:
            result["would_mark_reports_stale"] = before["reports"]
            result["would_delete_predictions"] = before["predictions"]
            result["would_delete_validations"] = before["validations"]
            result["would_delete_reviews"] = before["reviews"]
            return result

        backup_path = None
        if not args.no_backup:
            backup_path = create_backup(conn, ids, backup_dir=Path(args.backup_dir), report_type=report_type)

        id_sql = placeholders(ids)
        conn.execute(
            f"UPDATE lottery_analysis_reports SET is_stale = 1 "
            f"WHERE lottery_match_id IN ({id_sql}) AND report_type = ?",
            list(ids) + [report_type],
        )
        conn.execute(f"DELETE FROM lottery_predictions WHERE lottery_match_id IN ({id_sql})", list(ids))
        if table_exists(conn, "lottery_validation"):
            conn.execute(f"DELETE FROM lottery_validation WHERE lottery_match_id IN ({id_sql})", list(ids))
        if table_exists(conn, "post_match_reviews"):
            conn.execute(f"DELETE FROM post_match_reviews WHERE match_key IN ({id_sql})", list(ids))

        report_rows = conn.execute(
            """
            SELECT ar.lottery_match_id, lm.match_id, ar.report_type, ar.report_data
            FROM p.analysis_reports ar
            JOIN lottery_matches lm ON lm.lottery_match_id = ar.lottery_match_id
            """
        ).fetchall()
        conn.executemany(
            """
            INSERT INTO lottery_analysis_reports
            (lottery_match_id, match_id, report_type, report_data, created_at, is_stale)
            VALUES (?, ?, ?, ?, datetime('now'), 0)
            """,
            [tuple(row) for row in report_rows],
        )
        prediction_rows = conn.execute(
            """
            SELECT pr.lottery_match_id, lm.match_id, pr.play_type, pr.predictions,
                   pr.recommendation, pr.confidence, pr.confidence_level,
                   pr.has_value_bet, pr.value_bets, pr.features_json,
                   pr.weights_json, pr.model_version
            FROM p.predictions pr
            JOIN lottery_matches lm ON lm.lottery_match_id = pr.lottery_match_id
            """
        ).fetchall()
        conn.executemany(
            """
            INSERT INTO lottery_predictions
            (lottery_match_id, match_id, play_type, predictions, recommendation,
             confidence, confidence_level, has_value_bet, value_bets, features_json,
             weights_json, model_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            [tuple(row) for row in prediction_rows],
        )
        conn.commit()
        dates = patch_dates(conn)
        after = current_counts(conn, ids, report_type)

    validation_result = None
    if args.rebuild_validation:
        from backend.app.core.validate import _validate_predictions  # noqa: WPS433

        validation_result = _validate_predictions(str(db_path), dates)

    result.update(
        {
            "backup": str(backup_path) if backup_path else None,
            "reports_inserted": len(report_rows),
            "predictions_inserted": len(prediction_rows),
            "target_after": after,
            "rebuild_dates": dates if args.rebuild_validation else [],
            "validation_result": validation_result,
        }
    )
    return result


def verify_patch(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    patch_path = Path(args.patch)
    require_existing_file(db_path, "target db")
    require_existing_file(patch_path, "patch")
    with connect(db_path) as conn:
        conn.execute("ATTACH DATABASE ? AS p", (str(patch_path),))
        ids = patch_ids(conn)
        rows = conn.execute(
            """
            SELECT p.lottery_match_id, p.report_data AS patch_data,
                   ar.report_data AS target_data
            FROM p.analysis_reports p
            LEFT JOIN lottery_analysis_reports ar
              ON ar.lottery_match_id = p.lottery_match_id
             AND ar.report_type = p.report_type
             AND COALESCE(ar.is_stale, 0) = 0
            ORDER BY p.lottery_match_id
            """
        ).fetchall()
        missing = []
        mismatches = []
        for row in rows:
            if row["target_data"] is None:
                missing.append(str(row["lottery_match_id"]))
            elif sha16(row["patch_data"]) != sha16(row["target_data"]):
                mismatches.append(str(row["lottery_match_id"]))
        report_type = (
            conn.execute("SELECT value FROM p.meta WHERE key = 'report_type'").fetchone() or {"value": "prediction"}
        )["value"]
        counts = current_counts(conn, ids, str(report_type))
        return {
            "success": not missing and not mismatches,
            "db": str(db_path),
            "patch": str(patch_path),
            "matches": len(ids),
            "active_reports_checked": len(rows),
            "missing_active_reports": missing,
            "hash_mismatches": mismatches,
            "target_counts": counts,
        }


def insert_backup_table(conn: sqlite3.Connection, table: str) -> int:
    cols = table_columns(conn, table, schema="b")
    if not cols:
        return 0
    col_sql = ", ".join(cols)
    conn.execute(f"INSERT INTO main.{table} ({col_sql}) SELECT {col_sql} FROM b.{table}")
    return conn.execute(f"SELECT COUNT(*) FROM b.{table}").fetchone()[0]


def restore_backup(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    backup_path = Path(args.backup)
    require_existing_file(db_path, "target db")
    require_existing_file(backup_path, "backup")
    with connect(db_path) as conn:
        conn.execute("ATTACH DATABASE ? AS b", (str(backup_path),))
        if not table_exists(conn, "target_match_ids", schema="b"):
            return {"success": False, "error": "backup is missing target_match_ids", "backup": str(backup_path)}
        ids = [str(row["lottery_match_id"]) for row in conn.execute("SELECT lottery_match_id FROM b.target_match_ids")]
        if not ids:
            return {"success": False, "error": "backup has no target match ids", "backup": str(backup_path)}
        report_type_row = conn.execute("SELECT value FROM b.meta WHERE key = 'report_type'").fetchone()
        report_type = str(report_type_row["value"] if report_type_row else "prediction")
        id_sql = placeholders(ids)
        result: Dict[str, Any] = {
            "success": True,
            "mode": "apply" if args.apply else "dry_run",
            "db": str(db_path),
            "backup": str(backup_path),
            "matches": len(ids),
            "report_type": report_type,
            "current_counts": current_counts(conn, ids, report_type),
            "backup_counts": {
                "reports": conn.execute("SELECT COUNT(*) FROM b.lottery_analysis_reports").fetchone()[0],
                "predictions": conn.execute("SELECT COUNT(*) FROM b.lottery_predictions").fetchone()[0],
                "validations": conn.execute("SELECT COUNT(*) FROM b.lottery_validation").fetchone()[0],
                "reviews": conn.execute("SELECT COUNT(*) FROM b.post_match_reviews").fetchone()[0],
            },
        }
        if not args.apply:
            return result
        conn.execute(
            f"DELETE FROM lottery_analysis_reports WHERE lottery_match_id IN ({id_sql}) AND report_type = ?",
            list(ids) + [report_type],
        )
        conn.execute(f"DELETE FROM lottery_predictions WHERE lottery_match_id IN ({id_sql})", list(ids))
        if table_exists(conn, "lottery_validation"):
            conn.execute(f"DELETE FROM lottery_validation WHERE lottery_match_id IN ({id_sql})", list(ids))
        if table_exists(conn, "post_match_reviews"):
            conn.execute(f"DELETE FROM post_match_reviews WHERE match_key IN ({id_sql})", list(ids))
        restored = {
            "reports": insert_backup_table(conn, "lottery_analysis_reports"),
            "predictions": insert_backup_table(conn, "lottery_predictions"),
            "validations": insert_backup_table(conn, "lottery_validation"),
            "reviews": insert_backup_table(conn, "post_match_reviews"),
        }
        conn.commit()
        result["restored"] = restored
        result["target_after"] = current_counts(conn, ids, report_type)
        return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="Create an analysis-layer patch SQLite file")
    export.add_argument("--db", default=str(DEFAULT_DB))
    export.add_argument("--output", required=True)
    export.add_argument("--from", dest="date_from", default="")
    export.add_argument("--to", dest="date_to", default="")
    export.add_argument("--league", default=DEFAULT_LEAGUE)
    export.add_argument("--match-nums", default="")
    export.add_argument("--report-type", default="prediction")
    export.add_argument("--settled-only", action="store_true")
    export.add_argument("--force", action="store_true")

    inspect = sub.add_parser("inspect", help="Inspect a patch file")
    inspect.add_argument("--patch", required=True)

    imp = sub.add_parser("import", help="Preview or apply an analysis-layer patch")
    imp.add_argument("--db", default=str(DEFAULT_DB))
    imp.add_argument("--patch", required=True)
    imp.add_argument("--report-type", default="prediction")
    imp.add_argument("--backup-dir", default=str(BACKUP_DIR))
    imp.add_argument("--no-backup", action="store_true")
    imp.add_argument("--rebuild-validation", action="store_true")
    imp.add_argument("--apply", action="store_true")

    verify = sub.add_parser("verify", help="Verify target active reports match the patch")
    verify.add_argument("--db", default=str(DEFAULT_DB))
    verify.add_argument("--patch", required=True)

    restore = sub.add_parser("restore", help="Preview or restore from an import backup")
    restore.add_argument("--db", default=str(DEFAULT_DB))
    restore.add_argument("--backup", required=True)
    restore.add_argument("--apply", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "export":
        result = export_patch(args)
    elif args.command == "inspect":
        result = inspect_patch(Path(args.patch))
    elif args.command == "import":
        result = import_patch(args)
    elif args.command == "verify":
        result = verify_patch(args)
    elif args.command == "restore":
        result = restore_backup(args)
    else:
        raise SystemExit(f"unknown command: {args.command}")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
