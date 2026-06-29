"""Audit O/U goal-axis coherence in lottery analysis reports.

This catches the specific class of problems where the O/U recommendation,
expected goals, real line, score candidates, and goal_axis evidence contradict
each other. The script is read-only and is intended for both local and cloud
post-sync checks.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "football_v2.db"
DEFAULT_LEAGUE = "\u4e16\u754c\u676f"


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    return conn


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def fetch_reports(
    conn: sqlite3.Connection,
    date_from: str,
    date_to: str,
    league: str,
    report_type: str,
) -> Iterable[sqlite3.Row]:
    report_cols = columns(conn, "lottery_analysis_reports")
    stale_filter = "AND COALESCE(ar.is_stale, 0) = 0" if "is_stale" in report_cols else ""

    where = ["ar.report_type = ?"]
    params: List[Any] = [report_type]
    if date_from:
        where.append("date(lm.match_date) >= date(?)")
        params.append(date_from)
    if date_to:
        where.append("date(lm.match_date) <= date(?)")
        params.append(date_to)
    if league:
        where.append("lm.league_name_cn = ?")
        params.append(league)

    return conn.execute(
        f"""
        SELECT ar.lottery_match_id, lm.home_team_cn, lm.away_team_cn,
               lm.match_date, ar.report_data, ar.created_at
        FROM lottery_analysis_reports ar
        JOIN lottery_matches lm ON lm.lottery_match_id = ar.lottery_match_id
        WHERE {' AND '.join(where)}
          {stale_filter}
        ORDER BY datetime(ar.created_at) DESC, ar.report_id DESC
        """,
        params,
    ).fetchall()


def as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ou_side(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "\u5927" in text or "over" in text:
        return "over"
    if "\u5c0f" in text or "under" in text:
        return "under"
    return ""


def parse_line(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def score_total(value: Any) -> Optional[int]:
    match = re.search(r"(\d+)\s*[-:]\s*(\d+)", str(value or ""))
    if not match:
        return None
    return int(match.group(1)) + int(match.group(2))


def total_side(total: int, line: Optional[float]) -> str:
    if line is None:
        return ""
    if total > line:
        return "over"
    if total < line:
        return "under"
    return "push"


def audit_report(row: sqlite3.Row, report: Dict[str, Any], require_similarity: bool = False) -> List[Dict[str, Any]]:
    plays = as_dict(report.get("play_predictions") or report.get("analyses"))
    ou = as_dict(plays.get("ou") or plays.get("over_under"))
    fp = as_dict(report.get("final_prediction"))
    issues: List[Dict[str, Any]] = []
    if not ou:
        return [{
            "severity": "hard",
            "code": "missing_ou_prediction",
            "detail": "缺少大小球预测",
        }]

    diagnostics = as_dict(ou.get("diagnostics"))
    goal_axis = as_dict(ou.get("goal_axis"))
    recommendation = ou.get("recommendation") or ou.get("recommendation_cn")
    side = ou_side(recommendation) or goal_axis.get("side") or diagnostics.get("model_side")
    line = (
        parse_line(ou.get("best_line"))
        or parse_line(ou.get("line"))
        or parse_line(goal_axis.get("line"))
        or parse_line(diagnostics.get("line"))
        or parse_line(recommendation)
    )
    expected_total = goal_axis.get("expected_total")
    if expected_total is None:
        expected_total = diagnostics.get("expected_total")
    if expected_total is None:
        expected = as_dict(fp.get("expected_score"))
        if expected.get("home") is not None and expected.get("away") is not None:
            try:
                expected_total = float(expected.get("home") or 0) + float(expected.get("away") or 0)
            except (TypeError, ValueError):
                expected_total = None
    try:
        expected_total = float(expected_total) if expected_total is not None else None
    except (TypeError, ValueError):
        expected_total = None

    probs = as_dict(ou.get("best_line_probs") or ou.get("over_under_probs"))
    over_prob = probs.get("over")
    under_prob = probs.get("under")
    if over_prob is None:
        over_prob = diagnostics.get("decision_over_probability") or diagnostics.get("over_line_probability")
    if under_prob is None:
        under_prob = diagnostics.get("decision_under_probability") or diagnostics.get("under_line_probability")
    try:
        over_prob = float(over_prob) if over_prob is not None else None
        under_prob = float(under_prob) if under_prob is not None else None
    except (TypeError, ValueError):
        over_prob = None
        under_prob = None

    def add(severity: str, code: str, detail: str) -> None:
        issues.append({
            "severity": severity,
            "code": code,
            "detail": detail,
        })

    if line is None:
        add("hard", "missing_real_ou_line", "缺少真实大小球盘口线")
    if not goal_axis:
        add("hard", "missing_goal_axis", "缺少进球判断轴 goal_axis")
    if side not in {"over", "under"}:
        add("hard", "unknown_ou_side", f"无法识别大小球方向: {recommendation}")

    if side in {"over", "under"} and over_prob is not None and under_prob is not None:
        probability_side = "over" if over_prob > under_prob else "under"
        if side != probability_side and abs(over_prob - under_prob) >= 0.03:
            add(
                "hard",
                "recommendation_probability_conflict",
                f"推荐{side}，但概率分布更偏{probability_side}: over={over_prob:.3f}, under={under_prob:.3f}",
            )

    if side in {"over", "under"} and expected_total is not None and line is not None:
        gap = expected_total - line
        if gap >= 0.55 and side == "under":
            add(
                "soft",
                "expected_total_points_over_but_recommends_under",
                f"预期总进球{expected_total:.2f}明显高于盘口{line:g}，但推荐小球",
            )
        elif gap <= -0.55 and side == "over":
            add(
                "soft",
                "expected_total_points_under_but_recommends_over",
                f"预期总进球{expected_total:.2f}明显低于盘口{line:g}，但推荐大球",
            )

    score_items = plays.get("top3_scores") or fp.get("most_likely_scores") or []
    score_sides: List[str] = []
    if isinstance(score_items, list) and line is not None:
        for item in score_items[:3]:
            if not isinstance(item, dict):
                continue
            total = score_total(item.get("score"))
            if total is None:
                continue
            score_sides.append(total_side(total, line))
        opposite = "under" if side == "over" else "over"
        if side in {"over", "under"} and score_sides and score_sides.count(opposite) >= 2:
            add(
                "soft",
                "top_scores_conflict_with_ou_side",
                f"Top比分多数落在{opposite}侧: {score_sides}",
            )

    similarity = as_dict(goal_axis.get("historical_similarity_signal"))
    if require_similarity and goal_axis and not similarity:
        add("soft", "missing_ou_similarity_signal", "进球轴未带入相似大小球案例信号")

    return issues


def run(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    conn = connect(db_path)
    rows = list(fetch_reports(conn, args.date_from, args.date_to, args.league, args.report_type))
    conn.close()

    seen = set()
    issues = []
    parse_errors = []
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
        report_issues = audit_report(row, report, require_similarity=args.require_similarity)
        if report_issues:
            issues.append({
                "lottery_match_id": match_id,
                "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
                "match_date": row["match_date"],
                "created_at": row["created_at"],
                "issues": report_issues,
            })

    hard_count = sum(
        1
        for item in issues
        for issue in item["issues"]
        if issue["severity"] == "hard"
    )
    soft_count = sum(
        1
        for item in issues
        for issue in item["issues"]
        if issue["severity"] == "soft"
    )
    result = {
        "db": str(db_path),
        "report_type": args.report_type,
        "date_from": args.date_from,
        "date_to": args.date_to,
        "league": args.league,
        "reports_checked": len(seen),
        "hard_issues": hard_count,
        "soft_issues": soft_count,
        "issue_reports": len(issues),
        "issue_preview": issues[: args.limit],
        "parse_errors": parse_errors[: args.limit],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.fail_on_hard and hard_count:
        return 2
    if args.fail_on_any and (hard_count or soft_count):
        return 2
    if (args.fail_on_hard or args.fail_on_any) and parse_errors:
        return 3
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit O/U goal-axis coherence")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--date-from", default="2026-06-11")
    parser.add_argument("--date-to", default="2026-07-19")
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--report-type", default="prediction")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--require-similarity", action="store_true")
    parser.add_argument("--fail-on-hard", action="store_true")
    parser.add_argument("--fail-on-any", action="store_true")
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
