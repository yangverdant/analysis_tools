"""Audit BQC full-time leg against SPF and score-axis evidence.

This is a diagnostic task. It reads the active pre-match report, compares the
BQC full-time leg with the SPF axis and score-candidate axis, and stores why a
settled BQC full-time leg was likely wrong. It never rewrites predictions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"
DEFAULT_VERSION = "bqc_full_time_axis_v1"

DIR_TO_CN = {"3": "\u4e3b\u80dc", "1": "\u5e73\u5c40", "0": "\u5ba2\u80dc"}
BQC_LATIN_TO_CODE = {
    "hh": "33", "hd": "31", "ha": "30",
    "dh": "13", "dd": "11", "da": "10",
    "ah": "03", "ad": "01", "aa": "00",
}
BQC_CN_TO_CODE = {
    "\u80dc\u80dc": "33", "\u80dc\u5e73": "31", "\u80dc\u8d1f": "30",
    "\u5e73\u80dc": "13", "\u5e73\u5e73": "11", "\u5e73\u8d1f": "10",
    "\u8d1f\u80dc": "03", "\u8d1f\u5e73": "01", "\u8d1f\u8d1f": "00",
}
RESULT_ALIASES = {
    "home_win": "3", "draw": "1", "away_win": "0",
    "\u4e3b\u80dc": "3", "\u80dc": "3",
    "\u5e73\u5c40": "1", "\u5e73": "1",
    "\u5ba2\u80dc": "0", "\u8d1f": "0",
    "\u8ba9\u80dc": "3", "\u8ba9\u5e73": "1", "\u8ba9\u8d1f": "0",
}


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS bqc_full_time_axis_audits (
    audit_id TEXT PRIMARY KEY,
    lottery_match_id TEXT NOT NULL,
    report_id INTEGER,
    match_date TEXT,
    match_num TEXT,
    league_name_cn TEXT,
    home_team_cn TEXT,
    away_team_cn TEXT,
    actual_spf TEXT,
    actual_score TEXT,
    bqc_full_axis TEXT,
    spf_axis TEXT,
    score_top_axis TEXT,
    score_weighted_axis TEXT,
    bqc_full_correct INTEGER,
    spf_correct INTEGER,
    score_top_correct INTEGER,
    score_weighted_correct INTEGER,
    axis_driver TEXT,
    risk_tags_json TEXT,
    axis_json TEXT,
    version_tag TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_bqc_full_axis_date ON bqc_full_time_axis_audits(match_date, version_tag, axis_driver);",
    "CREATE INDEX IF NOT EXISTS idx_bqc_full_axis_match ON bqc_full_time_axis_audits(lottery_match_id, version_tag);",
]


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def compact_id(prefix: str, *parts: Any) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]}"


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


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


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_SQL)
    for sql in INDEX_SQL:
        conn.execute(sql)


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_result(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return RESULT_ALIASES.get(text, RESULT_ALIASES.get(text.lower(), text))


def normalize_bqc(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in BQC_LATIN_TO_CODE:
        return BQC_LATIN_TO_CODE[lowered]
    if text in BQC_CN_TO_CODE:
        return BQC_CN_TO_CODE[text]
    if len(text) == 2 and set(text) <= {"0", "1", "3"}:
        return text
    return text


def result_from_goals(home_goals: Any, away_goals: Any) -> str:
    home = int(home_goals or 0)
    away = int(away_goals or 0)
    if home > away:
        return "3"
    if home == away:
        return "1"
    return "0"


def score_text(item: Any) -> str:
    if isinstance(item, dict):
        if item.get("score"):
            return str(item["score"]).replace(":", "-")
        if item.get("home_goals") is not None and item.get("away_goals") is not None:
            return f"{item['home_goals']}-{item['away_goals']}"
    return str(item or "").replace(":", "-")


def score_result(value: str) -> str:
    if not value or "-" not in value:
        return ""
    left, right = value.split("-", 1)
    try:
        return result_from_goals(int(left), int(right))
    except (TypeError, ValueError):
        return ""


def probability_of(item: Any) -> float:
    if not isinstance(item, dict):
        return 0.0
    for key in ("adjusted_probability", "probability", "prob"):
        value = to_float(item.get(key), 0.0)
        if value:
            return value
    return 0.0


def normalize_probabilities(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: Dict[str, float] = {}
    for key, raw in value.items():
        code = normalize_result(key)
        if code in {"3", "1", "0"}:
            result[code] = to_float(raw)
    return result


def score_axis(scores: Sequence[Any]) -> Dict[str, Any]:
    items = []
    weighted = {"3": 0.0, "1": 0.0, "0": 0.0}
    for raw in scores[:5]:
        score = score_text(raw)
        direction = score_result(score)
        weight = probability_of(raw)
        if direction in weighted:
            weighted[direction] += weight
        items.append({"score": score, "direction": direction, "weight": round(weight, 4)})
    top_axis = items[0]["direction"] if items else ""
    weighted_axis = max(weighted, key=weighted.get) if any(weighted.values()) else top_axis
    total = sum(weighted.values())
    shares = {key: round(value / total, 4) for key, value in weighted.items()} if total > 0 else weighted
    return {
        "top_axis": top_axis,
        "weighted_axis": weighted_axis,
        "weighted_share": shares,
        "top_scores": items,
    }


def active_report_rows(conn: sqlite3.Connection, args: argparse.Namespace) -> List[sqlite3.Row]:
    report_cols = table_columns(conn, "lottery_analysis_reports")
    stale_filter = "AND COALESCE(ar2.is_stale, 0) = 0" if "is_stale" in report_cols else ""
    where = [
        "substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?",
        "lr.home_goals_ft IS NOT NULL",
        "lr.away_goals_ft IS NOT NULL",
    ]
    params: List[Any] = [args.report_type, args.date_from, args.date_to]
    if args.league:
        where.append("COALESCE(lm.league_name_cn, '') = ?")
        params.append(args.league)
    if args.match_nums:
        nums = [item.strip() for item in str(args.match_nums).split(",") if item.strip()]
        if nums:
            where.append(f"lm.match_num IN ({','.join(['?'] * len(nums))})")
            params.extend(nums)
    if args.only_bqc_full_miss and table_exists(conn, "bqc_phase_error_patterns"):
        where.append(
            """
            EXISTS (
                SELECT 1
                FROM bqc_phase_error_patterns p
                WHERE p.lottery_match_id = lm.lottery_match_id
                  AND p.pattern_type = 'full_time_axis_miss'
            )
            """
        )
    if args.limit:
        params.append(args.limit)
    limit_sql = " LIMIT ?" if args.limit else ""
    return conn.execute(
        f"""
        SELECT lm.lottery_match_id, lm.match_num,
               substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) AS match_date,
               lm.league_name_cn, lm.home_team_cn, lm.away_team_cn,
               lr.home_goals_ft, lr.away_goals_ft, lr.home_goals_ht, lr.away_goals_ht,
               lr.spf_result, lr.bqc_result, lr.bf_result,
               ar.report_id, ar.report_data, ar.created_at AS report_created_at
        FROM lottery_matches lm
        JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
        LEFT JOIN lottery_analysis_reports ar ON ar.report_id = (
            SELECT ar2.report_id
            FROM lottery_analysis_reports ar2
            WHERE ar2.lottery_match_id = lm.lottery_match_id
              AND ar2.report_type = ?
              {stale_filter}
            ORDER BY datetime(ar2.created_at) DESC, ar2.report_id DESC
            LIMIT 1
        )
        WHERE {" AND ".join(where)}
        ORDER BY substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10), lm.match_time, lm.match_num
        {limit_sql}
        """,
        params,
    ).fetchall()


def extract_axes(report: Dict[str, Any]) -> Dict[str, Any]:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    final = report.get("final_prediction") if isinstance(report.get("final_prediction"), dict) else {}
    spf = plays.get("spf") if isinstance(plays.get("spf"), dict) else {}
    bqc = plays.get("bqc") if isinstance(plays.get("bqc"), dict) else {}
    top_scores = plays.get("top3_scores") or final.get("most_likely_scores") or []
    bqc_code = normalize_bqc(bqc.get("recommendation_cn") or bqc.get("recommendation"))
    bqc_full = bqc_code[1] if len(bqc_code) == 2 and bqc_code[1] in {"3", "1", "0"} else ""
    spf_axis = normalize_result(
        spf.get("direction")
        or spf.get("direction_cn")
        or spf.get("recommendation_cn")
        or spf.get("recommendation")
        or final.get("predicted_result")
    )
    spf_probs = normalize_probabilities(spf.get("probabilities") or final.get("probabilities"))
    if not spf_axis and spf_probs:
        spf_axis = max(spf_probs, key=spf_probs.get)
    ordered_probs = sorted(spf_probs.items(), key=lambda item: item[1], reverse=True)
    score = score_axis(top_scores)
    expected = final.get("expected_score") if isinstance(final.get("expected_score"), dict) else {}
    return {
        "bqc_code": bqc_code,
        "bqc_full_axis": bqc_full,
        "spf_axis": spf_axis,
        "spf_probabilities": spf_probs,
        "spf_top_probability": round(ordered_probs[0][1], 4) if ordered_probs else None,
        "spf_gap": round(ordered_probs[0][1] - ordered_probs[1][1], 4) if len(ordered_probs) > 1 else None,
        "score_axis": score,
        "expected_home": to_float(expected.get("home"), None),
        "expected_away": to_float(expected.get("away"), None),
    }


def classify_driver(row: sqlite3.Row, axes: Dict[str, Any]) -> Dict[str, Any]:
    actual = result_from_goals(row["home_goals_ft"], row["away_goals_ft"])
    bqc_full = axes.get("bqc_full_axis") or ""
    spf_axis = axes.get("spf_axis") or ""
    score_top = (axes.get("score_axis") or {}).get("top_axis") or ""
    score_weighted = (axes.get("score_axis") or {}).get("weighted_axis") or ""
    spf_correct = spf_axis == actual if spf_axis else None
    bqc_correct = bqc_full == actual if bqc_full else None
    score_top_correct = score_top == actual if score_top else None
    score_weighted_correct = score_weighted == actual if score_weighted else None
    tags: List[str] = []

    if bqc_correct:
        driver = "bqc_full_positive"
    elif spf_axis and bqc_full == spf_axis and spf_correct is False:
        if score_top_correct or score_weighted_correct:
            driver = "spf_dragged_bqc_ignored_score_axis"
            tags.append("score_axis_had_actual_direction")
        else:
            driver = "spf_dragged_bqc_global_direction_miss"
    elif spf_correct is True and bqc_correct is False:
        driver = "bqc_detached_from_correct_spf"
    elif score_top_correct or score_weighted_correct:
        driver = "score_axis_signal_ignored"
    elif score_top and score_top == bqc_full and bqc_correct is False:
        driver = "score_axis_and_bqc_misread"
    else:
        driver = "unclassified_full_time_axis_miss"

    if actual == "1" and spf_axis != "1":
        tags.append("draw_risk_underweighted")
    if actual == "1" and score_top == "1":
        tags.append("top_score_draw_warning")
    if spf_axis and score_top and spf_axis != score_top:
        tags.append("spf_score_axis_disagreement")
    if axes.get("spf_top_probability") is not None and axes.get("spf_top_probability") < 0.55:
        tags.append("low_spf_top_probability")
    if axes.get("spf_gap") is not None and axes.get("spf_gap") < 0.10:
        tags.append("thin_spf_gap")

    exp_home = axes.get("expected_home")
    exp_away = axes.get("expected_away")
    expected_margin = None
    if exp_home is not None and exp_away is not None:
        expected_margin = round(float(exp_home) - float(exp_away), 4)
        if abs(expected_margin) < 0.35:
            tags.append("expected_margin_near_draw")

    return {
        "actual_spf": actual,
        "bqc_full_correct": bqc_correct,
        "spf_correct": spf_correct,
        "score_top_correct": score_top_correct,
        "score_weighted_correct": score_weighted_correct,
        "axis_driver": driver,
        "risk_tags": sorted(set(tags)),
        "expected_margin": expected_margin,
    }


def build_item(row: sqlite3.Row) -> Dict[str, Any]:
    report = loads_json(row["report_data"], {})
    axes = extract_axes(report)
    driver = classify_driver(row, axes)
    actual_score = f"{row['home_goals_ft']}:{row['away_goals_ft']}"
    return {
        "lottery_match_id": str(row["lottery_match_id"]),
        "report_id": row["report_id"],
        "match_date": row["match_date"],
        "match_num": row["match_num"],
        "league_name_cn": row["league_name_cn"],
        "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
        "actual_score": actual_score,
        "actual_spf": driver["actual_spf"],
        "actual_spf_cn": DIR_TO_CN.get(driver["actual_spf"], driver["actual_spf"]),
        "bqc_full_axis": axes.get("bqc_full_axis"),
        "spf_axis": axes.get("spf_axis"),
        "score_top_axis": (axes.get("score_axis") or {}).get("top_axis"),
        "score_weighted_axis": (axes.get("score_axis") or {}).get("weighted_axis"),
        "bqc_full_correct": driver.get("bqc_full_correct"),
        "spf_correct": driver.get("spf_correct"),
        "score_top_correct": driver.get("score_top_correct"),
        "score_weighted_correct": driver.get("score_weighted_correct"),
        "axis_driver": driver.get("axis_driver"),
        "risk_tags": driver.get("risk_tags") or [],
        "axis": {
            **axes,
            "expected_margin": driver.get("expected_margin"),
        },
    }


def save_item(conn: sqlite3.Connection, row: sqlite3.Row, item: Dict[str, Any], version_tag: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO bqc_full_time_axis_audits (
            audit_id, lottery_match_id, report_id, match_date, match_num, league_name_cn,
            home_team_cn, away_team_cn, actual_spf, actual_score,
            bqc_full_axis, spf_axis, score_top_axis, score_weighted_axis,
            bqc_full_correct, spf_correct, score_top_correct, score_weighted_correct,
            axis_driver, risk_tags_json, axis_json, version_tag, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            compact_id("bqcfta", row["lottery_match_id"], version_tag),
            str(row["lottery_match_id"]),
            row["report_id"],
            row["match_date"],
            row["match_num"],
            row["league_name_cn"],
            row["home_team_cn"],
            row["away_team_cn"],
            item.get("actual_spf"),
            item.get("actual_score"),
            item.get("bqc_full_axis"),
            item.get("spf_axis"),
            item.get("score_top_axis"),
            item.get("score_weighted_axis"),
            None if item.get("bqc_full_correct") is None else int(bool(item.get("bqc_full_correct"))),
            None if item.get("spf_correct") is None else int(bool(item.get("spf_correct"))),
            None if item.get("score_top_correct") is None else int(bool(item.get("score_top_correct"))),
            None if item.get("score_weighted_correct") is None else int(bool(item.get("score_weighted_correct"))),
            item.get("axis_driver"),
            dumps_json(item.get("risk_tags") or []),
            dumps_json(item.get("axis") or {}),
            version_tag,
        ),
    )


def summarize(items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    by_driver: Dict[str, int] = {}
    tag_counts: Dict[str, int] = {}
    scored = [item for item in items if item.get("actual_spf")]
    for item in items:
        driver = str(item.get("axis_driver") or "unknown")
        by_driver[driver] = by_driver.get(driver, 0) + 1
        for tag in item.get("risk_tags") or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return {
        "targets": len(items),
        "scored_matches": len(scored),
        "bqc_full_correct": sum(1 for item in scored if item.get("bqc_full_correct") is True),
        "spf_correct": sum(1 for item in scored if item.get("spf_correct") is True),
        "score_top_correct": sum(1 for item in scored if item.get("score_top_correct") is True),
        "score_weighted_correct": sum(1 for item in scored if item.get("score_weighted_correct") is True),
        "drivers": sorted(by_driver.items(), key=lambda pair: (-pair[1], pair[0])),
        "risk_tags": sorted(tag_counts.items(), key=lambda pair: (-pair[1], pair[0])),
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    version_tag = args.version_tag or DEFAULT_VERSION
    with connect(db_path) as conn:
        rows = active_report_rows(conn, args)
        items = [build_item(row) for row in rows if row["report_data"]]
        saved = 0
        if args.apply:
            ensure_table(conn)
            for row, item in zip([row for row in rows if row["report_data"]], items):
                save_item(conn, row, item, version_tag)
                saved += 1
            conn.commit()
    summary = summarize(items)
    examples = [item for item in items if item.get("axis_driver") != "bqc_full_positive"][: args.examples_limit]
    return {
        "success": True,
        "mode": "apply" if args.apply else "dry_run",
        "version_tag": version_tag,
        "settings": {
            "date_from": args.date_from,
            "date_to": args.date_to,
            "league": args.league,
            "only_bqc_full_miss": args.only_bqc_full_miss,
        },
        "summary": summary,
        "saved": saved,
        "examples": examples,
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--from", dest="date_from", default="1900-01-01")
    parser.add_argument("--to", dest="date_to", default="2100-12-31")
    parser.add_argument("--league", default="")
    parser.add_argument("--match-nums", default="")
    parser.add_argument("--report-type", default="prediction")
    parser.add_argument("--version-tag", default=DEFAULT_VERSION)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--examples-limit", type=int, default=8)
    parser.add_argument("--all-bqc", dest="only_bqc_full_miss", action="store_false", default=True)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    result = run(args)
    if args.summary_only:
        result = {
            "success": result.get("success"),
            "mode": result.get("mode"),
            "version_tag": result.get("version_tag"),
            "settings": result.get("settings"),
            "summary": result.get("summary"),
            "saved": result.get("saved"),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("success") is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
