"""Audit handicap-margin prediction errors.

This is a learning/audit task, not a prediction rewrite gate. It compares the
current RQSPF pick with the expected margin axis, score candidates, market
signal, and settled result. The output tells later model work whether the miss
came from one-goal boundary sensitivity, margin-tail underestimation, or a
misleading source axis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"
DEFAULT_LEAGUE = "\u4e16\u754c\u676f"

CN_TO_CODE = {
    "\u4e3b\u80dc": "3",
    "\u80dc": "3",
    "\u5e73\u5c40": "1",
    "\u5e73": "1",
    "\u5ba2\u80dc": "0",
    "\u8d1f": "0",
    "\u8ba9\u80dc": "3",
    "\u8ba9\u5e73": "1",
    "\u8ba9\u8d1f": "0",
    "home_win": "3",
    "draw": "1",
    "away_win": "0",
}

CODE_TO_RQSPF_CN = {
    "3": "\u8ba9\u80dc",
    "1": "\u8ba9\u5e73",
    "0": "\u8ba9\u8d1f",
}


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


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def placeholders(values: Sequence[Any]) -> str:
    return ",".join(["?"] * len(values))


def loads_json(value: Any, default: Any = None) -> Any:
    if default is None:
        default = {}
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return default
    try:
        return json.loads(str(value))
    except Exception:
        return default


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_code(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if text in {"3", "1", "0"}:
        return text
    return CN_TO_CODE.get(text, CN_TO_CODE.get(text.lower(), text))


def normalize_probs(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: Dict[str, float] = {}
    for key, raw in value.items():
        code = normalize_code(key)
        if code in {"3", "1", "0"}:
            prob = to_float(raw)
            if prob is not None:
                result[code] = prob
    return result


def top_prob(probs: Dict[str, float]) -> Tuple[str, float, float]:
    if not probs:
        return "", 0.0, 0.0
    ordered = sorted(probs.items(), key=lambda item: item[1], reverse=True)
    top_code, top_value = ordered[0]
    second = ordered[1][1] if len(ordered) > 1 else 0.0
    return top_code, float(top_value), float(top_value - second)


def rqspf_code_for_margin(goal_diff: int, handicap: float) -> str:
    adjusted = goal_diff - handicap
    if adjusted > 0:
        return "3"
    if adjusted == 0:
        return "1"
    return "0"


def rqspf_code_for_adjusted_margin(adjusted: Optional[float], edge: float) -> str:
    if adjusted is None:
        return ""
    if adjusted > edge:
        return "3"
    if adjusted < -edge:
        return "0"
    return "1"


def parse_score(value: Any) -> Optional[Tuple[int, int]]:
    if isinstance(value, dict):
        home = to_int(value.get("home_goals"))
        away = to_int(value.get("away_goals"))
        if home is not None and away is not None:
            return home, away
        value = value.get("score")
    match = re.search(r"(\d+)\s*[-:]\s*(\d+)", str(value or ""))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def score_candidate_axis(score_items: Any, handicap: float, limit: int) -> Dict[str, Any]:
    if not isinstance(score_items, list):
        return {"top": "", "gap": 0.0, "probabilities": {}, "items": []}
    weights: Dict[str, float] = defaultdict(float)
    items: List[Dict[str, Any]] = []
    for item in score_items[:limit]:
        parsed = parse_score(item)
        if not parsed:
            continue
        home, away = parsed
        prob = 0.0
        if isinstance(item, dict):
            prob = to_float(item.get("adjusted_probability"), None)
            if prob is None:
                prob = to_float(item.get("probability"), 0.0) or 0.0
        code = rqspf_code_for_margin(home - away, handicap)
        weights[code] += float(prob or 0.0)
        items.append({
            "score": f"{home}-{away}",
            "probability": round(float(prob or 0.0), 6),
            "rqspf": code,
            "rqspf_cn": CODE_TO_RQSPF_CN.get(code, code),
        })
    total = sum(weights.values())
    probs = {code: value / total for code, value in weights.items()} if total > 0 else dict(weights)
    top, value, gap = top_prob(probs)
    return {
        "top": top,
        "top_cn": CODE_TO_RQSPF_CN.get(top, top),
        "top_probability": round(value, 6),
        "gap": round(gap, 6),
        "probabilities": {key: round(value, 6) for key, value in sorted(probs.items())},
        "items": items,
    }


def fetch_latest_reports(
    conn: sqlite3.Connection,
    date_from: Optional[str],
    date_to: Optional[str],
    league: str,
    report_type: str,
    match_nums: str,
    limit: int,
) -> List[sqlite3.Row]:
    report_cols = table_columns(conn, "lottery_analysis_reports")
    stale_filter = "AND COALESCE(ar.is_stale, 0) = 0" if "is_stale" in report_cols else ""
    where = ["ar.report_type = ?"]
    params: List[Any] = [report_type]
    if date_from:
        where.append("substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) >= ?")
        params.append(date_from)
    if date_to:
        where.append("substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) <= ?")
        params.append(date_to)
    if league:
        where.append("lm.league_name_cn = ?")
        params.append(league)
    nums = [item.strip() for item in (match_nums or "").split(",") if item.strip()]
    if nums:
        where.append(f"lm.match_num IN ({placeholders(nums)})")
        params.extend(nums)

    limit_sql = ""
    if limit and limit > 0:
        limit_sql = "LIMIT ?"
        params.append(limit)

    return conn.execute(
        f"""
        SELECT ar.report_id, ar.report_data, ar.created_at AS report_created_at,
               lm.lottery_match_id, lm.match_id, lm.match_num, lm.home_team_cn, lm.away_team_cn,
               lm.league_name_cn, lm.match_date, lm.beijing_time, lm.handicap_line,
               lr.home_goals_ft, lr.away_goals_ft, lr.spf_result, lr.rqspf_result, lr.bf_result
        FROM lottery_analysis_reports ar
        JOIN lottery_matches lm ON lm.lottery_match_id = ar.lottery_match_id
        LEFT JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
        WHERE {" AND ".join(where)}
          {stale_filter}
          AND ar.report_id = (
              SELECT ar2.report_id
              FROM lottery_analysis_reports ar2
              WHERE ar2.lottery_match_id = ar.lottery_match_id
                AND ar2.report_type = ar.report_type
                {stale_filter.replace("ar.", "ar2.")}
              ORDER BY datetime(ar2.created_at) DESC, ar2.report_id DESC
              LIMIT 1
          )
        ORDER BY substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10), lm.lottery_match_id
        {limit_sql}
        """,
        params,
    ).fetchall()


def audit_row(row: sqlite3.Row, report: Dict[str, Any], *, expected_edge: float, score_limit: int) -> Dict[str, Any]:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    final = report.get("final_prediction") if isinstance(report.get("final_prediction"), dict) else {}
    rqspf = plays.get("rqspf") if isinstance(plays.get("rqspf"), dict) else {}
    spf = plays.get("spf") if isinstance(plays.get("spf"), dict) else {}

    handicap = to_float(rqspf.get("handicap"), None)
    if handicap is None:
        handicap = to_float(row["handicap_line"], 0.0) or 0.0

    current = normalize_code(rqspf.get("direction") or rqspf.get("recommendation") or rqspf.get("recommendation_cn"))
    actual = normalize_code(row["rqspf_result"])
    home_ft = to_int(row["home_goals_ft"])
    away_ft = to_int(row["away_goals_ft"])
    is_scored = actual in {"3", "1", "0"} and home_ft is not None and away_ft is not None

    expected = final.get("expected_score") if isinstance(final.get("expected_score"), dict) else {}
    expected_home = to_float(expected.get("home"))
    expected_away = to_float(expected.get("away"))
    expected_margin = None
    expected_adjusted = None
    if expected_home is not None and expected_away is not None:
        expected_margin = expected_home - expected_away
        expected_adjusted = expected_margin - handicap
    expected_axis = rqspf_code_for_adjusted_margin(expected_adjusted, expected_edge)

    score_items = plays.get("top3_scores") or final.get("most_likely_scores") or []
    score_axis = score_candidate_axis(score_items, handicap, score_limit)

    current_probs = normalize_probs(rqspf.get("probabilities"))
    current_top, current_top_prob, current_gap = top_prob(current_probs)
    market = rqspf.get("market_baseline") if isinstance(rqspf.get("market_baseline"), dict) else {}
    market_probs = normalize_probs(market.get("probabilities") or rqspf.get("market_probabilities"))
    market_top, market_top_prob, market_gap = top_prob(market_probs)
    uncond_probs = normalize_probs(rqspf.get("unconditional_probabilities"))
    uncond_top, uncond_top_prob, uncond_gap = top_prob(uncond_probs)
    axis_projection = rqspf.get("axis_projection") if isinstance(rqspf.get("axis_projection"), dict) else {}
    axis_probs = normalize_probs(axis_projection.get("probabilities"))
    axis_top, axis_top_prob, axis_gap = top_prob(axis_probs)

    spf_code = normalize_code(spf.get("direction") or spf.get("recommendation"))
    actual_margin = None
    actual_adjusted = None
    if home_ft is not None and away_ft is not None:
        actual_margin = home_ft - away_ft
        actual_adjusted = actual_margin - handicap

    correct = bool(is_scored and current == actual)
    tags: List[str] = []
    if correct:
        primary = "positive_case"
    else:
        if actual == "1" or current == "1":
            tags.append("one_goal_boundary_sensitive")
        if expected_axis and expected_axis == current and expected_axis != actual:
            tags.append("expected_margin_axis_miss")
        if score_axis.get("top") and score_axis.get("top") == current and score_axis.get("top") != actual:
            tags.append("score_candidate_axis_miss")
        if market_top and market_top == current and market_top != actual:
            tags.append("market_axis_miss")
        if axis_top and axis_top == current and axis_top != actual:
            tags.append("conditional_axis_miss")
        if score_axis.get("top") and score_axis.get("top") == actual and current != actual:
            tags.append("score_candidate_signal_was_available")
        if market_top and market_top == actual and current != actual:
            tags.append("market_signal_was_available")
        if actual_adjusted is not None and expected_adjusted is not None:
            delta = actual_adjusted - expected_adjusted
            if delta >= 1.0:
                tags.append("margin_tail_underestimated")
            elif delta <= -1.0:
                tags.append("margin_tail_overestimated")
        primary = tags[0] if tags else "unexplained_margin_axis_miss"

    actions: List[str] = []
    if "one_goal_boundary_sensitive" in tags:
        actions.append("calibrate_handicap_boundary")
    if "margin_tail_underestimated" in tags:
        actions.append("calibrate_margin_tail_up")
        actions.append("collect_recent_scoring_ceiling")
    if "margin_tail_overestimated" in tags:
        actions.append("calibrate_margin_tail_down")
        actions.append("collect_defensive_resistance")
    if "score_candidate_signal_was_available" in tags:
        actions.append("promote_score_candidate_axis_review")
    if "market_axis_miss" in tags:
        actions.append("downweight_weak_handicap_market")
    if "unexplained_margin_axis_miss" in tags or primary == "unexplained_margin_axis_miss":
        actions.append("collect_team_margin_factors")
    if correct:
        actions.append("keep_positive_pattern")

    signals = {
        "current": current,
        "current_cn": CODE_TO_RQSPF_CN.get(current, current),
        "actual": actual,
        "actual_cn": CODE_TO_RQSPF_CN.get(actual, actual),
        "spf_axis": spf_code,
        "handicap": handicap,
        "expected_home": expected_home,
        "expected_away": expected_away,
        "expected_margin": round(expected_margin, 6) if expected_margin is not None else None,
        "expected_adjusted_margin": round(expected_adjusted, 6) if expected_adjusted is not None else None,
        "expected_axis": expected_axis,
        "actual_margin": actual_margin,
        "actual_adjusted_margin": actual_adjusted,
        "score_axis": score_axis,
        "display_axis": {"top": current_top, "top_probability": current_top_prob, "gap": current_gap, "probabilities": current_probs},
        "market_axis": {"top": market_top, "top_probability": market_top_prob, "gap": market_gap, "probabilities": market_probs},
        "unconditional_axis": {"top": uncond_top, "top_probability": uncond_top_prob, "gap": uncond_gap, "probabilities": uncond_probs},
        "conditional_axis": {"top": axis_top, "top_probability": axis_top_prob, "gap": axis_gap, "probabilities": axis_probs},
        "display_source": rqspf.get("display_source"),
        "margin_distribution": rqspf.get("margin_distribution") if isinstance(rqspf.get("margin_distribution"), dict) else {},
    }

    return {
        "audit_id": "hmg_" + hashlib.sha256(
            f"{row['report_id']}|{row['lottery_match_id']}|handicap_margin_axis_v1".encode("utf-8")
        ).hexdigest()[:32],
        "version_tag": "handicap_margin_axis_v1",
        "report_id": int(row["report_id"]),
        "lottery_match_id": str(row["lottery_match_id"]),
        "match_num": row["match_num"],
        "match_date": str(row["beijing_time"] or row["match_date"])[:10],
        "league_name_cn": row["league_name_cn"],
        "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
        "home_team_cn": row["home_team_cn"],
        "away_team_cn": row["away_team_cn"],
        "handicap": handicap,
        "predicted": current,
        "predicted_cn": CODE_TO_RQSPF_CN.get(current, current),
        "actual": actual,
        "actual_cn": CODE_TO_RQSPF_CN.get(actual, actual),
        "is_scored": is_scored,
        "is_correct": correct if is_scored else None,
        "primary_category": primary,
        "tags": sorted(set(tags)),
        "actions": sorted(set(actions)),
        "signals": signals,
        "report_created_at": row["report_created_at"],
    }


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS handicap_margin_axis_audits (
            audit_id TEXT PRIMARY KEY,
            version_tag TEXT NOT NULL,
            lottery_match_id TEXT NOT NULL,
            report_id INTEGER,
            match_date TEXT,
            league_name_cn TEXT,
            home_team_cn TEXT,
            away_team_cn TEXT,
            handicap REAL,
            predicted_rqspf TEXT,
            actual_rqspf TEXT,
            is_correct INTEGER,
            primary_category TEXT,
            tags_json TEXT,
            actions_json TEXT,
            signals_json TEXT,
            report_created_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hmg_match_date ON handicap_margin_axis_audits(match_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hmg_category ON handicap_margin_axis_audits(primary_category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hmg_match ON handicap_margin_axis_audits(lottery_match_id)")


def save_audits(conn: sqlite3.Connection, audits: Sequence[Dict[str, Any]]) -> int:
    ensure_table(conn)
    saved = 0
    for item in audits:
        conn.execute(
            """
            INSERT OR REPLACE INTO handicap_margin_axis_audits (
                audit_id, version_tag, lottery_match_id, report_id, match_date, league_name_cn,
                home_team_cn, away_team_cn, handicap, predicted_rqspf, actual_rqspf, is_correct,
                primary_category, tags_json, actions_json, signals_json, report_created_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                item["audit_id"],
                item["version_tag"],
                item["lottery_match_id"],
                item["report_id"],
                item["match_date"],
                item["league_name_cn"],
                item["home_team_cn"],
                item["away_team_cn"],
                item["handicap"],
                item["predicted"],
                item["actual"],
                None if item["is_correct"] is None else int(bool(item["is_correct"])),
                item["primary_category"],
                dumps_json(item["tags"]),
                dumps_json(item["actions"]),
                dumps_json(item["signals"]),
                item["report_created_at"],
            ),
        )
        saved += 1
    conn.commit()
    return saved


def summarize(audits: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    scored = [item for item in audits if item.get("is_scored")]
    current_correct = sum(1 for item in scored if item.get("is_correct"))
    expected_correct = 0
    score_axis_correct = 0
    market_correct = 0
    conditional_correct = 0
    expected_total = 0
    score_total = 0
    market_total = 0
    conditional_total = 0
    category_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    for item in audits:
        category_counts[item["primary_category"]] += 1
        action_counts.update(item.get("actions") or [])
        tag_counts.update(item.get("tags") or [])
        if not item.get("is_scored"):
            continue
        actual = item.get("actual")
        signals = item.get("signals") if isinstance(item.get("signals"), dict) else {}
        expected_axis = signals.get("expected_axis")
        if expected_axis:
            expected_total += 1
            expected_correct += int(expected_axis == actual)
        score_top = ((signals.get("score_axis") or {}).get("top") if isinstance(signals.get("score_axis"), dict) else "")
        if score_top:
            score_total += 1
            score_axis_correct += int(score_top == actual)
        market_top = ((signals.get("market_axis") or {}).get("top") if isinstance(signals.get("market_axis"), dict) else "")
        if market_top:
            market_total += 1
            market_correct += int(market_top == actual)
        conditional_top = ((signals.get("conditional_axis") or {}).get("top") if isinstance(signals.get("conditional_axis"), dict) else "")
        if conditional_top:
            conditional_total += 1
            conditional_correct += int(conditional_top == actual)

    def rate(correct: int, total: int) -> Optional[float]:
        return round(correct * 100.0 / total, 1) if total else None

    return {
        "targets": len(audits),
        "scored_matches": len(scored),
        "current_correct": current_correct,
        "current_accuracy": rate(current_correct, len(scored)),
        "expected_axis": {"total": expected_total, "correct": expected_correct, "accuracy": rate(expected_correct, expected_total)},
        "score_axis": {"total": score_total, "correct": score_axis_correct, "accuracy": rate(score_axis_correct, score_total)},
        "market_axis": {"total": market_total, "correct": market_correct, "accuracy": rate(market_correct, market_total)},
        "conditional_axis": {"total": conditional_total, "correct": conditional_correct, "accuracy": rate(conditional_correct, conditional_total)},
        "top_categories": category_counts.most_common(10),
        "top_tags": tag_counts.most_common(10),
        "model_actions": action_counts.most_common(10),
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    with connect(db_path) as conn:
        rows = fetch_latest_reports(
            conn,
            args.date_from,
            args.date_to,
            args.league,
            args.report_type,
            args.match_nums,
            args.limit,
        )
        audits: List[Dict[str, Any]] = []
        parse_errors: List[Dict[str, Any]] = []
        for row in rows:
            report = loads_json(row["report_data"], {})
            if not isinstance(report, dict) or not report:
                parse_errors.append({"lottery_match_id": row["lottery_match_id"], "error": "empty_or_invalid_report_json"})
                continue
            audits.append(audit_row(row, report, expected_edge=args.expected_edge, score_limit=args.score_limit))
        saved = save_audits(conn, audits) if args.apply else 0

    examples = [
        {
            key: item[key]
            for key in (
                "match_num", "match_date", "teams", "handicap", "predicted_cn",
                "actual_cn", "is_correct", "primary_category", "tags", "actions",
            )
        }
        for item in audits
        if item.get("is_correct") is False
    ][: max(0, args.examples_limit)]

    result = {
        "success": True,
        "task": "handicap_margin_axis",
        "mode": "apply" if args.apply else "dry_run",
        "version_tag": "handicap_margin_axis_v1",
        "db": str(db_path),
        "date_from": args.date_from,
        "date_to": args.date_to,
        "league": args.league,
        "reports_checked": len(rows),
        "saved": saved,
        "summary": summarize(audits),
        "parse_errors": parse_errors[:10],
        "examples": examples,
    }
    if args.summary_only:
        result.pop("examples", None)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--date-from", dest="date_from", default=None)
    parser.add_argument("--date-to", dest="date_to", default=None)
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--match-nums", default="")
    parser.add_argument("--report-type", default="prediction")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--score-limit", type=int, default=5)
    parser.add_argument("--expected-edge", type=float, default=0.18)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--examples-limit", type=int, default=12)
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
