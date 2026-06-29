"""Gate model re-analysis changes against a pre-run analysis backup.

The automation center stores analysis-layer rows before forced re-analysis.
This gate compares that backup with the current validation table, then combines
accuracy deltas with hard prediction-consistency checks. It does not refetch or
mutate factual data.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"
DEFAULT_LEAGUE = "\u4e16\u754c\u676f"
PLAY_ORDER = ["spf", "rqspf", "bqc", "ou", "bf"]
PLAY_LABELS = {
    "spf": "\u80dc\u5e73\u8d1f",
    "rqspf": "\u8ba9\u7403\u80dc\u5e73\u8d1f",
    "bqc": "\u534a\u5168\u573a",
    "ou": "\u5927\u5c0f\u7403",
    "bf": "\u6bd4\u5206",
}

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_prediction_consistency import audit_report, columns, fetch_reports  # noqa: E402


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def placeholders(values: Sequence[Any]) -> str:
    return ",".join(["?"] * len(values))


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def clean(value: Any) -> str:
    return "" if value is None else str(value)


def backup_validation_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    table = ((payload.get("tables") or {}).get("lottery_validation") or {})
    rows = table.get("rows") or []
    return [row for row in rows if row.get("lottery_match_id") and row.get("play_type")]


def row_key(row: Dict[str, Any] | sqlite3.Row) -> Tuple[str, str]:
    return (str(row["lottery_match_id"]), str(row["play_type"]))


def load_current_validation_rows(conn: sqlite3.Connection, match_ids: Sequence[str]) -> Dict[Tuple[str, str], sqlite3.Row]:
    if not match_ids:
        return {}
    rows = conn.execute(
        f"""
        SELECT lv.validation_id, lv.lottery_match_id, lv.play_type, lv.predicted_result,
               lv.actual_result, lv.is_correct, lv.predicted_prob, lv.confidence,
               lv.validated_at,
               lm.match_num, lm.match_date, lm.beijing_time, lm.league_name_cn,
               lm.home_team_cn, lm.away_team_cn, lm.handicap_line,
               lr.home_goals_ft, lr.away_goals_ft, lr.home_goals_ht, lr.away_goals_ht
        FROM lottery_validation lv
        JOIN lottery_matches lm ON lm.lottery_match_id = lv.lottery_match_id
        LEFT JOIN lottery_results lr ON lr.lottery_match_id = lv.lottery_match_id
        WHERE lv.lottery_match_id IN ({placeholders(match_ids)})
        ORDER BY lv.validation_id
        """,
        list(match_ids),
    ).fetchall()
    result: Dict[Tuple[str, str], sqlite3.Row] = {}
    for row in rows:
        result[row_key(row)] = row
    return result


def load_match_dates(conn: sqlite3.Connection, match_ids: Sequence[str]) -> Dict[str, Any]:
    if not match_ids:
        return {"date_from": "", "date_to": "", "leagues": []}
    rows = conn.execute(
        f"""
        SELECT substr(COALESCE(beijing_time, match_date), 1, 10) AS d,
               COALESCE(league_name_cn, '') AS league
        FROM lottery_matches
        WHERE lottery_match_id IN ({placeholders(match_ids)})
        """,
        list(match_ids),
    ).fetchall()
    dates = sorted({str(row["d"]) for row in rows if row["d"]})
    leagues = sorted({str(row["league"]) for row in rows if row["league"]})
    return {
        "date_from": dates[0] if dates else "",
        "date_to": dates[-1] if dates else "",
        "leagues": leagues,
    }


def filter_match_ids(
    conn: sqlite3.Connection,
    match_ids: Sequence[str],
    *,
    date_from: str,
    date_to: str,
    league: str,
) -> List[str]:
    if not match_ids:
        return []
    where = [f"lottery_match_id IN ({placeholders(match_ids)})"]
    params: List[Any] = list(match_ids)
    if date_from:
        where.append("date(substr(COALESCE(beijing_time, match_date), 1, 10)) >= date(?)")
        params.append(date_from)
    if date_to:
        where.append("date(substr(COALESCE(beijing_time, match_date), 1, 10)) <= date(?)")
        params.append(date_to)
    if league:
        where.append("COALESCE(league_name_cn, '') = ?")
        params.append(league)
    rows = conn.execute(
        f"""
        SELECT lottery_match_id
        FROM lottery_matches
        WHERE {' AND '.join(where)}
        """,
        params,
    ).fetchall()
    return [str(row["lottery_match_id"]) for row in rows]


def empty_stats() -> Dict[str, Any]:
    return {"total": 0, "correct": 0, "accuracy": 0.0}


def accuracy(correct: int, total: int) -> float:
    return round(correct * 100.0 / total, 1) if total else 0.0


def build_accuracy_stats(rows: Iterable[Any]) -> Dict[str, Any]:
    total = 0
    correct = 0
    by_play: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        play_type = str(row["play_type"])
        is_correct = as_int(row["is_correct"])
        bucket = by_play.setdefault(play_type, empty_stats())
        bucket["total"] += 1
        bucket["correct"] += is_correct
        total += 1
        correct += is_correct
    for bucket in by_play.values():
        bucket["accuracy"] = accuracy(int(bucket["correct"]), int(bucket["total"]))
    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy(correct, total),
        "by_play_type": by_play,
    }


def compare_stats(before_rows: Sequence[Dict[str, Any]], current_rows: Dict[Tuple[str, str], sqlite3.Row]) -> Dict[str, Any]:
    before_by_key = {row_key(row): row for row in before_rows}
    paired_keys = sorted(set(before_by_key) & set(current_rows))
    missing_current = sorted(set(before_by_key) - set(current_rows))
    new_current = sorted(set(current_rows) - set(before_by_key))
    before_paired = [before_by_key[key] for key in paired_keys]
    after_paired = [current_rows[key] for key in paired_keys]
    before_stats = build_accuracy_stats(before_paired)
    after_stats = build_accuracy_stats(after_paired)

    by_play_delta: Dict[str, Dict[str, Any]] = {}
    play_types = sorted(set(before_stats["by_play_type"]) | set(after_stats["by_play_type"]), key=lambda p: PLAY_ORDER.index(p) if p in PLAY_ORDER else 99)
    for play_type in play_types:
        before = before_stats["by_play_type"].get(play_type, empty_stats())
        after = after_stats["by_play_type"].get(play_type, empty_stats())
        by_play_delta[play_type] = {
            "label": PLAY_LABELS.get(play_type, play_type),
            "before": before,
            "after": after,
            "delta_pp": round(float(after.get("accuracy") or 0) - float(before.get("accuracy") or 0), 1),
        }

    changed = []
    improved = 0
    regressed = 0
    prediction_changed_only = 0
    for key in paired_keys:
        before = before_by_key[key]
        after = current_rows[key]
        before_correct = as_int(before.get("is_correct"))
        after_correct = as_int(after["is_correct"])
        before_pred = clean(before.get("predicted_result"))
        after_pred = clean(after["predicted_result"])
        before_actual = clean(before.get("actual_result"))
        after_actual = clean(after["actual_result"])
        if before_correct == after_correct and before_pred == after_pred and before_actual == after_actual:
            continue
        if after_correct > before_correct:
            direction = "improved"
            improved += 1
        elif after_correct < before_correct:
            direction = "regressed"
            regressed += 1
        else:
            direction = "changed"
            prediction_changed_only += 1
        changed.append(
            {
                "lottery_match_id": key[0],
                "match_num": after["match_num"],
                "match_date": after["match_date"],
                "beijing_time": after["beijing_time"],
                "league": after["league_name_cn"],
                "teams": f"{after['home_team_cn']} vs {after['away_team_cn']}",
                "score": (
                    f"{after['home_goals_ft']}:{after['away_goals_ft']}"
                    if after["home_goals_ft"] is not None and after["away_goals_ft"] is not None
                    else ""
                ),
                "half_score": (
                    f"{after['home_goals_ht']}:{after['away_goals_ht']}"
                    if after["home_goals_ht"] is not None and after["away_goals_ht"] is not None
                    else ""
                ),
                "handicap_line": after["handicap_line"],
                "play_type": key[1],
                "play_label": PLAY_LABELS.get(key[1], key[1]),
                "direction": direction,
                "before": {
                    "predicted": before_pred,
                    "actual": before_actual,
                    "is_correct": bool(before_correct),
                },
                "after": {
                    "predicted": after_pred,
                    "actual": after_actual,
                    "is_correct": bool(after_correct),
                },
            }
        )

    return {
        "before": before_stats,
        "after": after_stats,
        "overall_delta_pp": round(float(after_stats["accuracy"]) - float(before_stats["accuracy"]), 1),
        "by_play_delta": by_play_delta,
        "paired_validations": len(paired_keys),
        "missing_current_validations": len(missing_current),
        "new_current_validations": len(new_current),
        "change_summary": {
            "total_changes": len(changed),
            "improved": improved,
            "regressed": regressed,
            "prediction_changed_only": prediction_changed_only,
        },
        "change_preview": changed[:30],
    }


def consistency_audit(
    conn: sqlite3.Connection,
    *,
    date_from: str,
    date_to: str,
    league: str,
    limit: int,
) -> Dict[str, Any]:
    rows = list(fetch_reports(conn, date_from, date_to, league, "prediction"))
    seen = set()
    issues = []
    issue_counts: Counter[str] = Counter()
    parse_errors = []
    adjusted = 0
    report_cols = columns(conn, "lottery_analysis_reports")
    for row in rows:
        match_id = row["lottery_match_id"]
        if match_id in seen:
            continue
        seen.add(match_id)
        try:
            report = json.loads(row["report_data"])
        except Exception as exc:
            parse_errors.append({"lottery_match_id": match_id, "error": str(exc)})
            continue
        plays = report.get("play_predictions") or report.get("analyses") or {}
        bqc = plays.get("bqc") or {}
        if isinstance(bqc, dict) and bqc.get("consistency_adjustment"):
            adjusted += 1
        issue = audit_report(row, report)
        if issue:
            issues.append(issue)
            issue_counts.update(str(item) for item in issue.get("issues") or [])
    return {
        "date_from": date_from,
        "date_to": date_to,
        "league": league,
        "reports_checked": len(seen),
        "consistency_adjusted_reports": adjusted,
        "hard_issues": len(issues),
        "issue_counts": dict(issue_counts.most_common()),
        "parse_errors": len(parse_errors),
        "issue_preview": issues[:limit],
        "parse_error_preview": parse_errors[:limit],
        "stale_filter_supported": "is_stale" in report_cols,
    }


def decide(
    *,
    comparison: Dict[str, Any],
    consistency: Dict[str, Any],
    overall_drop_tolerance_pp: float,
    play_drop_tolerance_pp: float,
    fail_on_missing: bool,
) -> Dict[str, Any]:
    reasons: List[str] = []
    warnings: List[str] = []

    if consistency["hard_issues"] > 0:
        reasons.append(f"hard consistency issues: {consistency['hard_issues']}")
    if consistency["parse_errors"] > 0:
        reasons.append(f"report parse errors: {consistency['parse_errors']}")
    if fail_on_missing and comparison["missing_current_validations"] > 0:
        reasons.append(f"missing current validations: {comparison['missing_current_validations']}")

    overall_delta = float(comparison["overall_delta_pp"])
    if overall_delta < -abs(overall_drop_tolerance_pp):
        reasons.append(f"overall accuracy dropped {abs(overall_delta):.1f}pp")
    elif overall_delta < 0:
        warnings.append(f"overall accuracy slightly dropped {abs(overall_delta):.1f}pp")

    key_regressions = []
    soft_regressions = []
    for play_type, item in comparison["by_play_delta"].items():
        delta = float(item["delta_pp"])
        label = item["label"]
        if delta < -abs(play_drop_tolerance_pp):
            key_regressions.append(f"{label} dropped {abs(delta):.1f}pp")
        elif delta < 0:
            soft_regressions.append(f"{label} dropped {abs(delta):.1f}pp")
    reasons.extend(key_regressions)
    warnings.extend(soft_regressions)

    if reasons:
        decision = "fail"
    elif warnings:
        decision = "warn"
    else:
        decision = "pass"
    return {
        "decision": decision,
        "reasons": reasons,
        "warnings": warnings,
        "thresholds": {
            "overall_drop_tolerance_pp": overall_drop_tolerance_pp,
            "play_drop_tolerance_pp": play_drop_tolerance_pp,
            "fail_on_missing": fail_on_missing,
        },
    }


def evaluate_model_change(
    *,
    db_path: Path,
    backup_path: Path,
    date_from: str = "",
    date_to: str = "",
    league: str = DEFAULT_LEAGUE,
    overall_drop_tolerance_pp: float = 1.0,
    play_drop_tolerance_pp: float = 3.0,
    fail_on_missing: bool = True,
    limit: int = 30,
) -> Dict[str, Any]:
    payload = load_json(backup_path)
    before_rows = backup_validation_rows(payload)
    match_ids = [str(item) for item in payload.get("match_ids") or []]

    with connect(db_path) as conn:
        if date_from or date_to or league:
            match_ids = filter_match_ids(conn, match_ids, date_from=date_from, date_to=date_to, league=league)
            allowed = set(match_ids)
            before_rows = [row for row in before_rows if str(row.get("lottery_match_id")) in allowed]
        if not date_from or not date_to:
            inferred = load_match_dates(conn, match_ids)
            date_from = date_from or inferred["date_from"]
            date_to = date_to or inferred["date_to"]
            if not league and len(inferred["leagues"]) == 1:
                league = inferred["leagues"][0]
        current_rows = load_current_validation_rows(conn, match_ids)
        comparison = compare_stats(before_rows, current_rows)
        consistency = consistency_audit(conn, date_from=date_from, date_to=date_to, league=league, limit=limit)

    decision = decide(
        comparison=comparison,
        consistency=consistency,
        overall_drop_tolerance_pp=overall_drop_tolerance_pp,
        play_drop_tolerance_pp=play_drop_tolerance_pp,
        fail_on_missing=fail_on_missing,
    )
    return {
        "success": decision["decision"] != "fail",
        "decision": decision["decision"],
        "decision_detail": decision,
        "backup": {
            "path": str(backup_path),
            "created_at": payload.get("created_at"),
            "version_tag": payload.get("version_tag"),
            "dates": payload.get("dates"),
            "match_ids": len(match_ids),
            "backup_validations": len(before_rows),
        },
        "window": {
            "date_from": date_from,
            "date_to": date_to,
            "league": league,
        },
        "comparison": comparison,
        "consistency": consistency,
    }


def latest_backup_path(root: Path) -> Optional[Path]:
    if not root.exists():
        return None
    files = sorted(root.glob("analysis_layer_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0] if files else None


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--backup", default="", help="Backup JSON path. Defaults to latest model_reanalysis backup.")
    parser.add_argument("--backup-dir", default=str(ROOT.parent / "football_backups" / "model_reanalysis"))
    parser.add_argument("--date-from", default="")
    parser.add_argument("--date-to", default="")
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--overall-drop-tolerance-pp", type=float, default=1.0)
    parser.add_argument("--play-drop-tolerance-pp", type=float, default=3.0)
    parser.add_argument("--allow-missing", dest="fail_on_missing", action="store_false", default=True)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--summary-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    backup = Path(args.backup) if args.backup else latest_backup_path(Path(args.backup_dir))
    if backup is None:
        raise SystemExit(f"No analysis backup found under {args.backup_dir}")
    result = evaluate_model_change(
        db_path=Path(args.db),
        backup_path=backup,
        date_from=args.date_from,
        date_to=args.date_to,
        league=args.league,
        overall_drop_tolerance_pp=args.overall_drop_tolerance_pp,
        play_drop_tolerance_pp=args.play_drop_tolerance_pp,
        fail_on_missing=args.fail_on_missing,
        limit=args.limit,
    )
    if args.summary_only:
        result = {
            "success": result["success"],
            "decision": result["decision"],
            "decision_detail": result["decision_detail"],
            "backup": result["backup"],
            "window": result["window"],
            "comparison": {
                "before": result["comparison"]["before"],
                "after": result["comparison"]["after"],
                "overall_delta_pp": result["comparison"]["overall_delta_pp"],
                "by_play_delta": result["comparison"]["by_play_delta"],
                "paired_validations": result["comparison"]["paired_validations"],
                "missing_current_validations": result["comparison"]["missing_current_validations"],
                "new_current_validations": result["comparison"]["new_current_validations"],
                "change_summary": result["comparison"]["change_summary"],
            },
            "consistency": result["consistency"],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["decision"] in {"pass", "warn"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
