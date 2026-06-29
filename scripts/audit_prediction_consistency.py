"""Audit logical consistency across lottery play predictions.

The analysis UI displays SPF, handicap SPF, half/full time and O/U together.
This script catches hard contradictions such as:
- SPF says home win but BQC full-time leg says away win
- home gives goals and handicap result covers, but BQC/SPF is not home win

It is read-only by default and can be used after local or cloud re-analysis.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
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
               lm.handicap_line, ar.report_data, ar.created_at
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


def direction(value: Any) -> str:
    text = str(value or "").strip()
    aliases = {
        "home_win": "3",
        "draw": "1",
        "away_win": "0",
        "\u4e3b\u80dc": "3",
        "\u5e73\u5c40": "1",
        "\u5ba2\u80dc": "0",
        "\u80dc": "3",
        "\u5e73": "1",
        "\u8d1f": "0",
        "\u8ba9\u80dc": "3",
        "\u8ba9\u5e73": "1",
        "\u8ba9\u8d1f": "0",
    }
    return aliases.get(text, text)


def bqc_full_leg(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) == 2 and text[0] in "hda" and text[1] in "hda":
        return text[1]
    cn_map = {
        "\u80dc\u80dc": "h",
        "\u80dc\u5e73": "d",
        "\u80dc\u8d1f": "a",
        "\u5e73\u80dc": "h",
        "\u5e73\u5e73": "d",
        "\u5e73\u8d1f": "a",
        "\u8d1f\u80dc": "h",
        "\u8d1f\u5e73": "d",
        "\u8d1f\u8d1f": "a",
    }
    return cn_map.get(text, "")


def axis_context_trusted(value: Any) -> bool:
    if not isinstance(value, dict):
        return True
    return bool(value.get("usable_for_derived") or value.get("trusted"))


def rqspf_code_for_margin(goal_diff: int, handicap: float) -> str:
    adjusted = goal_diff - handicap
    if adjusted > 0:
        return "3"
    if adjusted == 0:
        return "1"
    return "0"


def rqspf_margin_requirement(handicap: float, value: str) -> str:
    try:
        h = float(handicap or 0.0)
    except (TypeError, ValueError):
        h = 0.0

    def num(raw: float) -> str:
        return str(int(raw)) if float(raw).is_integer() else f"{raw:g}"

    code = direction(value)
    if abs(h) < 1e-9:
        return {"3": "主队胜出", "1": "双方打平", "0": "客队胜出"}.get(code, "")

    if h > 0:
        line = num(h)
        cover = num(h + 1) if float(h).is_integer() else f"超过{line}"
        if code == "3":
            return f"主队至少赢{cover}球才是让胜"
        if code == "1":
            return f"主队正好赢{line}球才是让平"
        if code == "0":
            return f"主队净胜不足{line}球或不胜才是让负"
    else:
        line_value = abs(h)
        line = num(line_value)
        cover_limit = line_value - 1 if float(line_value).is_integer() else None
        miss = num(line_value + 1) if float(line_value).is_integer() else f"超过{line}"
        if code == "3":
            if cover_limit is not None and cover_limit <= 0:
                return "主队不败才是让胜"
            if cover_limit is not None:
                return f"主队不败或最多输{num(cover_limit)}球才是让胜"
            return f"主队受让{line}球后仍领先才是让胜"
        if code == "1":
            return f"客队正好赢{line}球才是让平"
        if code == "0":
            return f"客队至少赢{miss}球才是让负"
    return ""


def rqspf_possible_under_spf(handicap: float, rqspf_dir: str, spf_dir: str) -> bool:
    if spf_dir not in {"3", "1", "0"} or rqspf_dir not in {"3", "1", "0"}:
        return True
    # Goal difference is integer in real scores. A generous window is enough for
    # handicap sanity checks and avoids hand-coded sign mistakes.
    for diff in range(-15, 16):
        if spf_dir == "3" and diff <= 0:
            continue
        if spf_dir == "1" and diff != 0:
            continue
        if spf_dir == "0" and diff >= 0:
            continue
        if rqspf_code_for_margin(diff, handicap) == rqspf_dir:
            return True
    return False


def parse_score(value: Any) -> Optional[tuple[int, int]]:
    text = str(value or "").strip().replace(":", "-")
    if "-" not in text:
        return None
    left, right = text.split("-", 1)
    try:
        return int(left), int(right)
    except (TypeError, ValueError):
        return None


def score_matches_spf(score: Any, spf_dir: str) -> bool:
    parsed = parse_score(score)
    if parsed is None or spf_dir not in {"3", "1", "0"}:
        return True
    diff = parsed[0] - parsed[1]
    return (
        (spf_dir == "3" and diff > 0)
        or (spf_dir == "1" and diff == 0)
        or (spf_dir == "0" and diff < 0)
    )


def score_axis_count(item: Any) -> int:
    if not isinstance(item, dict):
        return 0
    axis = item.get("axis_match") if isinstance(item.get("axis_match"), dict) else {}
    return sum(1 for key in ("spf", "ou", "rqspf") if axis.get(key))


def score_display_axis_issue(plays: Dict[str, Any], spf_dir: str) -> Optional[Dict[str, Any]]:
    scores = plays.get("top3_scores") if isinstance(plays.get("top3_scores"), list) else []
    if not scores or spf_dir not in {"3", "1", "0"}:
        return None
    top = scores[0] if isinstance(scores[0], dict) else {}
    top_score = top.get("score")
    if score_matches_spf(top_score, spf_dir):
        return None
    try:
        top_probability = float(top.get("probability") or 0.0)
    except (TypeError, ValueError):
        top_probability = 0.0
    for item in scores[1:3]:
        if not isinstance(item, dict):
            continue
        try:
            item_probability = float(item.get("probability") or 0.0)
        except (TypeError, ValueError):
            item_probability = 0.0
        if (
            score_matches_spf(item.get("score"), spf_dir)
            and score_axis_count(item) >= 2
            and item_probability >= top_probability * 0.55
        ):
            return {
                "top_score": top_score,
                "candidate_score": item.get("score"),
                "top_probability": round(top_probability, 4),
                "candidate_probability": round(item_probability, 4),
            }
    return None


def audit_report(row: sqlite3.Row, report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    plays = as_dict(report.get("play_predictions") or report.get("analyses"))
    spf = as_dict(plays.get("spf"))
    rqspf = as_dict(plays.get("rqspf"))
    bqc = as_dict(plays.get("bqc"))

    spf_dir = direction(spf.get("direction") or spf.get("recommendation"))
    rqspf_dir = direction(rqspf.get("direction") or rqspf.get("recommendation"))
    rqspf_rec = direction(rqspf.get("recommendation") or rqspf.get("recommendation_cn"))
    rqspf_axis = as_dict(rqspf.get("axis_projection"))
    rqspf_axis_dir = direction(rqspf_axis.get("direction"))
    rqspf_display_source = rqspf.get("display_source")
    rqspf_axis_context = as_dict(rqspf.get("axis_context"))
    rqspf_full_time_arbitration = as_dict(rqspf.get("full_time_arbitration"))
    rqspf_boundary_profile = as_dict(rqspf.get("boundary_profile"))
    rqspf_margin_gate = as_dict(rqspf.get("handicap_margin_gate_adjustment"))
    rqspf_consistency_gate = as_dict(rqspf.get("consistency_gate_adjustment"))
    spf_arbitration = as_dict(spf.get("arbitration_adjustment"))
    spf_axis_trusted = axis_context_trusted(spf.get("axis_context"))
    try:
        handicap = float(rqspf.get("handicap") if rqspf.get("handicap") is not None else 0)
    except (TypeError, ValueError):
        handicap = 0.0
    expected_margin_requirement = rqspf_margin_requirement(handicap, rqspf_dir) if rqspf_dir else ""

    bqc_rec = bqc.get("recommendation") or bqc.get("recommendation_cn")
    full_leg = bqc_full_leg(bqc_rec)
    issues: List[str] = []
    warnings: List[str] = []

    spf_full = {"3": "h", "1": "d", "0": "a"}.get(spf_dir)
    if spf_axis_trusted and spf_full and full_leg and spf_full != full_leg:
        issues.append("bqc_full_time_conflicts_with_spf")

    if spf_axis_trusted and spf_dir and rqspf_dir and not rqspf_possible_under_spf(handicap, rqspf_dir, spf_dir):
        issues.append("rqspf_impossible_under_spf_axis")
    bqc_spf_dir = {"h": "3", "d": "1", "a": "0"}.get(full_leg)
    if bqc_spf_dir and rqspf_dir and not rqspf_possible_under_spf(handicap, rqspf_dir, bqc_spf_dir):
        issues.append("rqspf_impossible_under_bqc_axis")

    score_axis_problem = score_display_axis_issue(plays, spf_dir)
    if score_axis_problem:
        issues.append("score_top_conflicts_with_available_axis_candidate")

    if rqspf_rec and rqspf_dir and rqspf_rec != rqspf_dir:
        issues.append("rqspf_recommendation_conflicts_with_direction")
    if expected_margin_requirement and rqspf.get("margin_requirement") and rqspf.get("margin_requirement") != expected_margin_requirement:
        issues.append("rqspf_margin_requirement_stale")

    for gate_name, gate in (
        ("handicap_margin_gate", rqspf_margin_gate),
        ("play_consistency_gate", rqspf_consistency_gate),
    ):
        if not gate:
            continue
        gate_to = direction(gate.get("to") or gate.get("to_cn"))
        if gate_to and rqspf_dir and gate_to != rqspf_dir:
            issues.append(f"{gate_name}_to_conflicts_with_direction")
        if expected_margin_requirement and gate.get("margin_requirement") and gate.get("margin_requirement") != expected_margin_requirement:
            issues.append(f"{gate_name}_margin_requirement_stale")

    for boundary_key in ("gate_override_direction", "consistency_gate_override_direction"):
        boundary_direction = direction(rqspf_boundary_profile.get(boundary_key))
        if boundary_direction and rqspf_dir and boundary_direction != rqspf_dir:
            issues.append(f"boundary_{boundary_key}_conflicts_with_direction")

    if handicap > 0 and rqspf_dir in {"3", "1"}:
        if spf_axis_trusted and spf_dir and spf_dir != "3":
            issues.append("home_gives_handicap_cover_conflicts_with_spf")
        if full_leg and full_leg != "h":
            issues.append("home_gives_handicap_cover_conflicts_with_bqc")

    if handicap < 0 and rqspf_dir in {"0", "1"}:
        if spf_axis_trusted and spf_dir and spf_dir != "0":
            issues.append("home_receives_handicap_miss_conflicts_with_spf")
        if full_leg and full_leg != "a":
            issues.append("home_receives_handicap_miss_conflicts_with_bqc")

    if (
        rqspf_axis_dir
        and rqspf_axis_dir != rqspf_dir
        and rqspf.get("unconditional_direction") == rqspf_dir
        and rqspf_display_source in {None, "", "unconditional"}
        and not rqspf_full_time_arbitration.get("applied_to_spf")
        and not spf_arbitration
    ):
        warnings.append("rqspf_displays_unconditional_when_axis_projection_differs")
    if rqspf_axis_context.get("axis_conflict"):
        issues.append("spf_bqc_full_time_axis_conflict")

    if not issues:
        return None
    return {
        "lottery_match_id": row["lottery_match_id"],
        "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
        "spf": spf_dir,
        "rqspf": rqspf_dir,
        "handicap": handicap,
        "goal_line": -handicap,
        "bqc": bqc_rec,
        "score_axis_problem": score_axis_problem,
        "issues": issues,
        "warnings": warnings,
        "created_at": row["created_at"],
    }


def run(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    conn = connect(db_path)
    rows = list(fetch_reports(conn, args.date_from, args.date_to, args.league, args.report_type))
    seen = set()
    issues = []
    issue_counts: Counter[str] = Counter()
    adjusted = 0
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

        plays = as_dict(report.get("play_predictions") or report.get("analyses"))
        bqc = as_dict(plays.get("bqc"))
        if bqc.get("consistency_adjustment"):
            adjusted += 1
        issue = audit_report(row, report)
        if issue:
            issues.append(issue)
            issue_counts.update(str(item) for item in issue.get("issues") or [])

    conn.close()
    result = {
        "db": str(db_path),
        "report_type": args.report_type,
        "date_from": args.date_from,
        "date_to": args.date_to,
        "league": args.league,
        "reports_checked": len(seen),
        "consistency_adjusted_reports": adjusted,
        "issues": len(issues),
        "issue_counts": dict(issue_counts.most_common()),
        "issue_preview": issues[: args.limit],
        "parse_errors": parse_errors[: args.limit],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.fail_on_issues and issues:
        return 2
    if args.fail_on_issues and parse_errors:
        return 3
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--date-from", default="2026-06-11")
    parser.add_argument("--date-to", default="2026-07-19")
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--report-type", default="prediction")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--fail-on-issues", action="store_true")
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
