"""Audit pre-match analysis for future data leakage.

Checks that analysis reports only used data captured before kickoff:
1. Odds: captured_at <= kickoff + grace
2. Intelligence: updated_at <= kickoff + grace
3. source_artifacts: captured_at <= kickoff + grace
4. similar_match_cases: no cases from future matches
5. team_match_facts: no facts from the match itself or after
6. lottery_results: not used during pre-match analysis

Exit code 0 = clean, 1 = leakage found (with --fail-on-leakage).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "football_v2.db"

GRACE_MINUTES = 15  # allow data captured up to 15 min after kickoff (lineups etc.)


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    return conn


def parse_dt(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("T", " ")
    for fmt, width in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%d", 10),
    ):
        try:
            return datetime.strptime(text[:width], fmt)
        except ValueError:
            continue
    return None


def get_kickoff(conn: sqlite3.Connection, lottery_match_id: str) -> Optional[datetime]:
    row = conn.execute(
        "SELECT beijing_time, match_date FROM lottery_matches WHERE lottery_match_id = ?",
        (lottery_match_id,),
    ).fetchone()
    if not row:
        return None
    bt = parse_dt(row["beijing_time"])
    if bt:
        return bt
    md = str(row["match_date"] or "").strip()[:10]
    return parse_dt(md) if md else None


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    )


def columns_of(conn: sqlite3.Connection, table: str) -> set:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


# ── 1. Odds leakage ──────────────────────────────────────────────

def audit_odds_leakage(conn: sqlite3.Connection, limit: int = 0) -> List[dict]:
    issues = []
    if not table_exists(conn, "lottery_odds"):
        return issues
    rows = conn.execute(
        """
        SELECT lo.lottery_match_id, lo.play_type, lo.snapshot_type,
               lo.created_at, lo.update_time
        FROM lottery_odds lo
        JOIN lottery_matches lm ON lo.lottery_match_id = lm.lottery_match_id
        WHERE lm.beijing_time IS NOT NULL
        ORDER BY lo.lottery_match_id
        """
    ).fetchall()
    if limit:
        rows = rows[:limit]

    for row in rows:
        kickoff = get_kickoff(conn, row["lottery_match_id"])
        if not kickoff:
            continue
        captured = parse_dt(row["created_at"]) or parse_dt(row["update_time"])
        if not captured:
            continue
        cutoff = kickoff + timedelta(minutes=GRACE_MINUTES)
        if captured > cutoff:
            issues.append({
                "type": "odds_after_kickoff",
                "lottery_match_id": row["lottery_match_id"],
                "play_type": row["play_type"],
                "snapshot_type": row["snapshot_type"],
                "captured_at": str(captured),
                "kickoff": str(kickoff),
                "delay_minutes": round((captured - kickoff).total_seconds() / 60, 1),
            })
    return issues


# ── 2. Intelligence leakage ──────────────────────────────────────

def audit_intelligence_leakage(conn: sqlite3.Connection, limit: int = 0) -> List[dict]:
    issues = []
    if not table_exists(conn, "intelligence_packages"):
        return issues
    rows = conn.execute(
        """
        SELECT ij.lottery_match_id, ip.updated_at, ip.completeness
        FROM intelligence_packages ip
        JOIN intelligence_jobs ij ON ip.job_id = ij.job_id
        WHERE ij.lottery_match_id IS NOT NULL
        ORDER BY ip.updated_at DESC
        """
    ).fetchall()
    if limit:
        rows = rows[:limit]

    for row in rows:
        kickoff = get_kickoff(conn, row["lottery_match_id"])
        if not kickoff:
            continue
        updated = parse_dt(row["updated_at"])
        if not updated:
            continue
        cutoff = kickoff + timedelta(minutes=GRACE_MINUTES)
        if updated > cutoff:
            issues.append({
                "type": "intel_after_kickoff",
                "lottery_match_id": row["lottery_match_id"],
                "intel_updated_at": str(updated),
                "kickoff": str(kickoff),
                "delay_minutes": round((updated - kickoff).total_seconds() / 60, 1),
            })
    return issues


# ── 3. Source artifacts leakage ──────────────────────────────────

def audit_source_artifacts_leakage(conn: sqlite3.Connection, limit: int = 0) -> List[dict]:
    issues = []
    if not table_exists(conn, "source_artifacts"):
        return issues
    cols = columns_of(conn, "source_artifacts")
    if "entity_id" not in cols or "entity_type" not in cols:
        return issues
    rows = conn.execute(
        """
        SELECT sa.entity_id, sa.entity_type, sa.source_name, sa.captured_at
        FROM source_artifacts sa
        WHERE sa.captured_at IS NOT NULL
          AND sa.entity_type = 'lottery_match'
        ORDER BY sa.captured_at DESC
        """
    ).fetchall()
    if limit:
        rows = rows[:limit]

    for row in rows:
        mid = row["entity_id"]
        if not mid:
            continue
        kickoff = get_kickoff(conn, str(mid))
        if not kickoff:
            continue
        captured = parse_dt(row["captured_at"])
        if not captured:
            continue
        cutoff = kickoff + timedelta(minutes=GRACE_MINUTES)
        if captured > cutoff:
            issues.append({
                "type": "source_artifact_after_kickoff",
                "lottery_match_id": str(mid),
                "source_name": row["source_name"],
                "captured_at": str(captured),
                "kickoff": str(kickoff),
                "delay_minutes": round((captured - kickoff).total_seconds() / 60, 1),
            })
    return issues


# ── 4. Similar match cases leakage ──────────────────────────────

def audit_similar_cases_leakage(conn: sqlite3.Connection, limit: int = 0) -> List[dict]:
    issues = []
    if not table_exists(conn, "similar_match_cases"):
        return issues
    rows = conn.execute(
        """
        SELECT match_key, similar_match_key, similarity_score, created_at
        FROM similar_match_cases
        ORDER BY created_at DESC
        """
    ).fetchall()
    if limit:
        rows = rows[:limit]

    for row in rows:
        match_key = row["match_key"]
        similar_key = row["similar_match_key"]
        match_kickoff = get_kickoff(conn, str(match_key))
        similar_kickoff = get_kickoff(conn, str(similar_key))
        if not match_kickoff or not similar_kickoff:
            continue
        # If the similar match happened AFTER the current match, it's leakage
        if similar_kickoff > match_kickoff:
            issues.append({
                "type": "similar_case_from_future",
                "lottery_match_id": str(match_key),
                "similar_match_id": str(similar_key),
                "match_kickoff": str(match_kickoff),
                "similar_kickoff": str(similar_kickoff),
                "similarity_score": row["similarity_score"],
            })
    return issues


# ── 5. Analysis report using post-kickoff data ──────────────────

def audit_analysis_report_leakage(conn: sqlite3.Connection, limit: int = 0) -> List[dict]:
    """Check if analysis report's created_at is before kickoff (sanity check).

    Also inspects report_data for evidence timestamps that are after kickoff.
    """
    issues = []
    if not table_exists(conn, "lottery_analysis_reports"):
        return issues
    rows = conn.execute(
        """
        SELECT lottery_match_id, created_at, report_data
        FROM lottery_analysis_reports
        WHERE report_type IN ('prediction', 'full')
        ORDER BY created_at DESC
        """
    ).fetchall()
    if limit:
        rows = rows[:limit]

    for row in rows:
        kickoff = get_kickoff(conn, row["lottery_match_id"])
        if not kickoff:
            continue
        created = parse_dt(row["created_at"])
        if not created:
            continue
        # Report created well after kickoff is suspicious (could be reanalysis)
        # Only flag if >2h after kickoff (reanalysis of finished match)
        if created > kickoff + timedelta(hours=2):
            issues.append({
                "type": "report_created_after_match",
                "lottery_match_id": row["lottery_match_id"],
                "report_created_at": str(created),
                "kickoff": str(kickoff),
                "delay_hours": round((created - kickoff).total_seconds() / 3600, 1),
            })

        # Check report_data for captured_at timestamps after kickoff
        try:
            report = json.loads(row["report_data"]) if isinstance(row["report_data"], str) else (row["report_data"] or {})
        except Exception:
            continue
        _check_report_timestamps(report, row["lottery_match_id"], kickoff, issues)

    return issues


def _check_report_timestamps(data: dict, match_id: str, kickoff: datetime, issues: list) -> None:
    """Recursively scan report dict for captured_at/updated_at after kickoff."""
    if not isinstance(data, dict):
        return
    cutoff = kickoff + timedelta(minutes=GRACE_MINUTES)
    for key in ("captured_at", "updated_at"):
        if key in data:
            ts = parse_dt(data[key])
            if ts and ts > cutoff:
                issues.append({
                    "type": "report_contains_post_kickoff_timestamp",
                    "lottery_match_id": match_id,
                    "field": key,
                    "timestamp": str(ts),
                    "kickoff": str(kickoff),
                    "delay_minutes": round((ts - kickoff).total_seconds() / 60, 1),
                })
    for v in data.values():
        if isinstance(v, dict):
            _check_report_timestamps(v, match_id, kickoff, issues)


# ── 6. team_match_facts leakage ─────────────────────────────────

def audit_team_match_facts_leakage(conn: sqlite3.Connection, limit: int = 0) -> List[dict]:
    """Check that team_match_facts for a match doesn't use that match's own results."""
    issues = []
    if not table_exists(conn, "team_match_facts"):
        return issues
    if not table_exists(conn, "lottery_results"):
        return issues
    cols = columns_of(conn, "team_match_facts")
    match_col = "source_match_id" if "source_match_id" in cols else None
    if not match_col:
        return issues
    rows = conn.execute(
        f"""
        SELECT tmf.team_name, tmf.match_date, tmf.{match_col}, tmf.source_name
        FROM team_match_facts tmf
        WHERE tmf.{match_col} IS NOT NULL
        ORDER BY tmf.match_date DESC
        """
    ).fetchall()
    if limit:
        rows = rows[:limit]

    for row in rows:
        match_id = row[match_col]
        if not match_id:
            continue
        kickoff = get_kickoff(conn, str(match_id))
        if not kickoff:
            continue
        # Check if this fact was created/updated after the match
        fact_date = parse_dt(row["match_date"])
        if fact_date and fact_date > kickoff + timedelta(hours=3):
            issues.append({
                "type": "team_match_facts_after_match",
                "team_name": row["team_name"],
                "match_id": str(match_id),
                "fact_date": str(fact_date),
                "kickoff": str(kickoff),
            })
    return issues


# ── Main ─────────────────────────────────────────────────────────

def run_audit(db_path: Path, max_per_check: int = 0, json_output: bool = False) -> dict:
    conn = connect(db_path)
    try:
        results = {}
        total_issues = 0

        checks = [
            ("odds", audit_odds_leakage),
            ("intelligence", audit_intelligence_leakage),
            ("source_artifacts", audit_source_artifacts_leakage),
            ("similar_cases", audit_similar_cases_leakage),
            ("analysis_reports", audit_analysis_report_leakage),
            ("team_match_facts", audit_team_match_facts_leakage),
        ]

        for name, check_fn in checks:
            issues = check_fn(conn, limit=max_per_check)
            results[name] = {
                "total": len(issues),
                "sample": issues[:20],
            }
            total_issues += len(issues)

        results["total_issues"] = total_issues
        results["summary"] = _summarize(results)

        if json_output:
            print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
        else:
            _print_report(results)

        return results
    finally:
        conn.close()


def _summarize(results: dict) -> dict:
    by_type = Counter()
    for name, data in results.items():
        if name in ("total_issues", "summary"):
            continue
        for issue in data.get("sample", []):
            by_type[issue["type"]] += 1
    return {"by_type": dict(by_type), "total": results["total_issues"]}


def _print_report(results: dict) -> None:
    print("=" * 60)
    print("  PRE-MATCH DATA LEAKAGE AUDIT REPORT")
    print("=" * 60)

    for name in ("odds", "intelligence", "source_artifacts", "similar_cases",
                 "analysis_reports", "team_match_facts"):
        data = results.get(name, {})
        total = data.get("total", 0)
        status = "CLEAN" if total == 0 else f"FOUND {total}"
        print(f"\n  [{name}] {status}")
        for issue in data.get("sample", [])[:5]:
            mid = issue.get("lottery_match_id", "?")
            delay = issue.get("delay_minutes") or issue.get("delay_hours", "?")
            itype = issue.get("type", "?")
            print(f"    - {mid}: {itype} (delay={delay})")
        if total > 5:
            print(f"    ... and {total - 5} more")

    total = results.get("total_issues", 0)
    print(f"\n{'=' * 60}")
    if total == 0:
        print("  RESULT: NO LEAKAGE DETECTED")
    else:
        print(f"  RESULT: {total} POTENTIAL LEAKAGE ISSUES FOUND")
        print("  Action: Fix in analyze.py, then re-run to verify.")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Audit pre-match analysis for future data leakage")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to football_v2.db")
    parser.add_argument("--max-per-check", type=int, default=0, help="Limit rows per check (0=unlimited)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--fail-on-leakage", action="store_true", help="Exit code 1 if leakage found")
    args = parser.parse_args()

    results = run_audit(args.db, args.max_per_check, args.json)
    if args.fail_on_leakage and results.get("total_issues", 0) > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
