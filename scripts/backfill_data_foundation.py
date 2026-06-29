"""Backfill durable foundation tables from existing local database assets.

This is intentionally idempotent. It derives snapshots/reviews from current
normalized tables and does not overwrite match, odds, report, or validation
source data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "football_v2.db"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.data_access.foundation_dao import FoundationDAO
from backend.app.core.validate import _build_structured_review


def compact_review_id(match_key: Any, play_type: Any) -> str:
    raw = f"{'' if match_key is None else match_key}|{play_type or 'unknown'}"
    return "review_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def compact_snapshot_id(prefix: str, match_key: Any, source_report_id: Any = None, payload: Any = None) -> str:
    if source_report_id is not None:
        raw = f"{'' if match_key is None else match_key}|{source_report_id}"
    else:
        raw = f"{'' if match_key is None else match_key}|{json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)}"
    return f"{prefix}_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def loads_json(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) and value else default
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone() is not None


def count_rows_fresh(conn: sqlite3.Connection, table: str) -> int:
    """Count with a fresh connection so writes made through FoundationDAO are visible."""
    db_row = conn.execute("PRAGMA database_list").fetchone()
    db_file = db_row[2] if db_row and len(db_row) > 2 else None
    if not db_file:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    fresh = sqlite3.connect(db_file, timeout=10)
    try:
        return fresh.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        fresh.close()


def iter_rows(conn: sqlite3.Connection, query: str, params: Iterable[Any] = ()) -> Iterable[sqlite3.Row]:
    return conn.execute(query, tuple(params)).fetchall()


def backfill_mappings(conn: sqlite3.Connection, dao: FoundationDAO, limit: Optional[int]) -> int:
    query = """
        SELECT lottery_match_id, oddsfe_event_id, home_team_id, away_team_id,
               home_team_cn, away_team_cn
        FROM lottery_matches
        ORDER BY match_date DESC, match_time DESC
    """
    if limit:
        query += " LIMIT ?"
        rows = iter_rows(conn, query, [limit])
    else:
        rows = iter_rows(conn, query)

    count = 0

    def upsert_if_needed(
        entity_type: str,
        source_name: str,
        source_entity_id: Any,
        canonical_id: Any,
        source_entity_name: Any,
        confidence: float,
    ) -> bool:
        if source_entity_id is None:
            return False
        if table_exists(conn, "source_entity_mappings"):
            existing = conn.execute(
                """
                SELECT canonical_id, source_entity_name, confidence, status
                FROM source_entity_mappings
                WHERE entity_type = ? AND source_name = ? AND source_entity_id = ?
                """,
                (entity_type, source_name, str(source_entity_id)),
            ).fetchone()
            if existing:
                # Backfill is conservative: an existing mapping is treated as
                # human/system-reviewed. Ambiguous source ids are not rewritten
                # here because that can make scheduled learning refreshes
                # oscillate between canonical ids.
                if existing["canonical_id"]:
                    return False
                same = (
                    (existing["canonical_id"] or "") == ("" if canonical_id is None else str(canonical_id))
                    and abs(safe_float(existing["confidence"], 0) - confidence) < 0.0001
                    and (existing["status"] or "active") == "active"
                )
                if same:
                    return False
        return bool(
            dao.upsert_mapping(
                entity_type,
                source_name,
                source_entity_id,
                canonical_id,
                source_entity_name,
                confidence,
            )
        )

    for row in rows:
        match_name = f"{row['home_team_cn']} vs {row['away_team_cn']}"
        if upsert_if_needed('match', 'sporttery', row['lottery_match_id'], row['lottery_match_id'], match_name, 0.95):
            count += 1
        if row['oddsfe_event_id']:
            if upsert_if_needed('event', 'oddsfe', row['oddsfe_event_id'], row['lottery_match_id'], match_name, 0.9):
                count += 1
        if row['home_team_id']:
            if upsert_if_needed('team', 'sporttery', row['home_team_id'], row['home_team_id'], row['home_team_cn'], 0.8):
                count += 1
        if row['away_team_id']:
            if upsert_if_needed('team', 'sporttery', row['away_team_id'], row['away_team_id'], row['away_team_cn'], 0.8):
                count += 1
    return count


def backfill_reviews(
    conn: sqlite3.Connection,
    dao: FoundationDAO,
    limit: Optional[int],
    refresh_existing: bool = False,
) -> int:
    query = """
        SELECT lottery_match_id, play_type, predicted_result, actual_result,
               is_correct, predicted_prob, brier_score, scenario_type,
               attribution, attribution_detail, actionable, validated_at
        FROM lottery_validation
        ORDER BY validated_at DESC
    """
    if limit:
        query += " LIMIT ?"
        rows = iter_rows(conn, query, [limit])
    else:
        rows = iter_rows(conn, query)

    count = 0
    for row in rows:
        review = dict(row)
        existing = conn.execute(
            """
            SELECT predicted_result, actual_result, is_correct, attribution, review_json
            FROM post_match_reviews
            WHERE match_key = ? AND play_type = ?
            """,
            (row["lottery_match_id"], row["play_type"]),
        ).fetchone() if table_exists(conn, "post_match_reviews") else None
        if existing:
            same_review = (
                (existing["predicted_result"] or "") == (row["predicted_result"] or "")
                and (existing["actual_result"] or "") == (row["actual_result"] or "")
                and (None if existing["is_correct"] is None else int(existing["is_correct"]))
                    == (None if row["is_correct"] is None else int(bool(row["is_correct"])))
                and (existing["attribution"] or "") == (row["attribution"] or "")
            )
            existing_json = loads_json(existing["review_json"], {})
            structured = existing_json.get("structured_review") if isinstance(existing_json, dict) else None
            has_structured = isinstance(structured, dict) and bool(structured.get("reason_text"))
            if same_review and has_structured and not refresh_existing:
                continue
        attribution = {}
        if row["attribution"] or row["attribution_detail"]:
            attribution = {
                "level": row["attribution"],
                "detail": row["attribution_detail"],
            }
        structured_review = {}
        try:
            structured_review = _build_structured_review(conn, review, attribution)
        except Exception:
            structured_review = {}
        review_json = {
            "validation": review,
            "attribution": attribution,
            "structured_review": structured_review,
        }
        if structured_review:
            review_json["reason_text"] = structured_review.get("reason_text")
            review_json["learning_tags"] = structured_review.get("learning_tags") or []
            review_json["action_items"] = structured_review.get("action_items") or []
        review_id = compact_review_id(row["lottery_match_id"], row["play_type"])
        conn.execute(
            """
            INSERT OR REPLACE INTO post_match_reviews
            (review_id, match_key, play_type, predicted_result, actual_result,
             is_correct, attribution, review_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                review_id,
                str(row["lottery_match_id"]),
                row["play_type"] or "unknown",
                row["predicted_result"],
                row["actual_result"],
                None if row["is_correct"] is None else int(bool(row["is_correct"])),
                row["attribution"],
                json.dumps(review_json, ensure_ascii=False, sort_keys=True, default=str),
            ),
        )
        count += 1
    conn.commit()
    return count


def latest_intelligence(conn: sqlite3.Connection, lottery_match_id: str, match_id: Any) -> Dict[str, Any]:
    if not table_exists(conn, "intelligence_packages"):
        return {}

    clauses = []
    params = []
    if lottery_match_id:
        clauses.append("ij.lottery_match_id = ?")
        params.append(lottery_match_id)
    if match_id:
        clauses.append("ij.match_id = ?")
        params.append(match_id)
    if not clauses:
        return {}

    row = conn.execute(
        f"""
        SELECT ip.package_json, ip.completeness, ip.missing_required_json,
               ip.updated_at, ij.job_id, ij.status
        FROM intelligence_packages ip
        JOIN intelligence_jobs ij ON ip.job_id = ij.job_id
        WHERE {' OR '.join(clauses)}
        ORDER BY ip.updated_at DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    if not row:
        return {}
    return {
        "job_id": row["job_id"],
        "status": row["status"],
        "completeness": row["completeness"],
        "missing_required": loads_json(row["missing_required_json"], []),
        "package": loads_json(row["package_json"], {}),
        "updated_at": row["updated_at"],
    }


def context_snapshot_exists_for_report(conn: sqlite3.Connection, match_key: Any, report_id: Any) -> bool:
    if not table_exists(conn, "match_context_snapshots") or match_key is None or report_id is None:
        return False
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM match_context_snapshots
            WHERE match_key = ?
              AND CAST(json_extract(data_quality_json, '$.source_report_id') AS TEXT) = ?
            LIMIT 1
            """,
            (str(match_key), str(report_id)),
        ).fetchone()
        return row is not None
    except sqlite3.OperationalError:
        patterns = [
            f'%"source_report_id": {report_id}%',
            f'%"source_report_id": "{report_id}"%',
        ]
        for pattern in patterns:
            row = conn.execute(
                """
                SELECT 1
                FROM match_context_snapshots
                WHERE match_key = ?
                  AND data_quality_json LIKE ?
                LIMIT 1
                """,
                (str(match_key), pattern),
            ).fetchone()
            if row:
                return True
        return False


def feature_snapshot_exists_for_report(conn: sqlite3.Connection, report_id: Any) -> bool:
    if not table_exists(conn, "match_feature_snapshots") or report_id is None:
        return False
    row = conn.execute(
        """
        SELECT 1
        FROM match_feature_snapshots
        WHERE source_report_id = ?
        LIMIT 1
        """,
        (str(report_id),),
    ).fetchone()
    return row is not None


def backfill_snapshots(conn: sqlite3.Connection, dao: FoundationDAO, limit: Optional[int]) -> int:
    query = """
        SELECT lar.report_id, lar.lottery_match_id, lar.match_id, lar.report_type,
               lar.report_data, lar.created_at,
               lm.home_team_id, lm.away_team_id, lm.home_team_cn, lm.away_team_cn,
               lm.league_name_cn, lm.match_date, lm.match_time, lm.beijing_time,
               lm.handicap_line, lm.oddsfe_event_id
        FROM lottery_analysis_reports lar
        LEFT JOIN lottery_matches lm ON lm.lottery_match_id = lar.lottery_match_id
        WHERE lar.report_type IN ('prediction', 'full')
          AND lar.rowid = (
              SELECT ar2.rowid
              FROM lottery_analysis_reports ar2
              WHERE ar2.lottery_match_id = lar.lottery_match_id
                AND ar2.report_type IN ('prediction', 'full')
              ORDER BY ar2.created_at DESC, ar2.rowid DESC
              LIMIT 1
          )
        ORDER BY lar.created_at DESC
    """
    if limit:
        query += " LIMIT ?"
        rows = iter_rows(conn, query, [limit])
    else:
        rows = iter_rows(conn, query)

    inserted = 0
    for row in rows:
        report = loads_json(row["report_data"], {})
        if not report:
            continue
        match_key = row["lottery_match_id"] or row["match_id"]
        if not match_key:
            continue

        match = {
            "lottery_match_id": row["lottery_match_id"],
            "match_id": row["match_id"],
            "home_team_id": row["home_team_id"],
            "away_team_id": row["away_team_id"],
            "home_team_cn": row["home_team_cn"],
            "away_team_cn": row["away_team_cn"],
            "league_name_cn": row["league_name_cn"],
            "match_date": row["match_date"],
            "match_time": row["match_time"],
            "beijing_time": row["beijing_time"],
            "handicap_line": row["handicap_line"],
            "oddsfe_event_id": row["oddsfe_event_id"],
        }
        intel = latest_intelligence(conn, row["lottery_match_id"], row["match_id"])
        play_predictions = report.get("play_predictions", {})
        odds_context = {
            "odds_baseline": report.get("odds_baseline", {}),
            "model_vs_odds": report.get("model_vs_odds", {}),
            "play_predictions": {
                "spf": play_predictions.get("spf", {}),
                "rqspf": play_predictions.get("rqspf", {}),
                "ou": play_predictions.get("ou", {}),
            },
        }
        quality = {
            "has_team_mapping": bool(row["home_team_id"] and row["away_team_id"]),
            "has_odds": bool(report.get("odds_baseline")),
            "has_intelligence_package": bool(intel.get("package")),
            "has_rqspf": bool(play_predictions.get("rqspf")),
            "has_ou": bool(play_predictions.get("ou")),
            "source_report_id": row["report_id"],
        }
        features = {
            "final_prediction": report.get("final_prediction", {}),
            "play_predictions": play_predictions,
            "factor_breakdown": report.get("factor_breakdown", {}),
            "weights_used": report.get("weights_used", {}),
            "model_vs_odds": report.get("model_vs_odds", {}),
            "base_prediction": report.get("base_prediction", {}),
        }
        if not context_snapshot_exists_for_report(conn, match_key, row["report_id"]):
            snapshot_id = compact_snapshot_id("ctx", match_key, source_report_id=row["report_id"])
            conn.execute(
                """
                INSERT OR REPLACE INTO match_context_snapshots
                (snapshot_id, match_key, competition_context_json,
                 odds_context_json, intel_context_json, data_quality_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    str(match_key),
                    json.dumps({"match": match}, ensure_ascii=False, sort_keys=True, default=str),
                    json.dumps(odds_context, ensure_ascii=False, sort_keys=True, default=str),
                    json.dumps(intel, ensure_ascii=False, sort_keys=True, default=str),
                    json.dumps(quality, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            inserted += 1
        if not feature_snapshot_exists_for_report(conn, row["report_id"]):
            snapshot_id = compact_snapshot_id("feat", match_key, source_report_id=row["report_id"])
            conn.execute(
                """
                INSERT OR REPLACE INTO match_feature_snapshots
                (snapshot_id, match_key, feature_json, model_version, source_report_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    str(match_key),
                    json.dumps(features, ensure_ascii=False, sort_keys=True, default=str),
                    report.get("model_version") or report.get("weights_used", {}).get("source") or "backfill",
                    str(row["report_id"]),
                ),
            )
            inserted += 1
    conn.commit()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill data foundation tables from existing records")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to football_v2.db")
    parser.add_argument("--limit", type=int, default=0, help="Optional per-section row limit")
    parser.add_argument(
        "--refresh-reviews",
        action="store_true",
        help="Regenerate structured review JSON even when a review already has one",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    dao = FoundationDAO(str(db_path))
    conn = connect(db_path)
    try:
        limit = args.limit or None
        summary = {
            "mappings": backfill_mappings(conn, dao, limit),
            "reviews": backfill_reviews(conn, dao, limit, refresh_existing=args.refresh_reviews),
            "snapshots": backfill_snapshots(conn, dao, limit),
        }
    finally:
        conn.close()

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
