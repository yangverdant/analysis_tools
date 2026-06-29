"""Export and compare match analysis input fingerprints.

This script answers a practical question: when local and cloud recommend
different outcomes for the same match, which inputs are actually different?
It is read-only. Run it against any football_v2.db to produce a compact JSON
fingerprint, then compare two exports.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "football_v2.db"
DEFAULT_LEAGUE = "\u4e16\u754c\u676f"
DEFAULT_PLAYS = ("spf", "rqspf", "ttg", "bf", "bqc")


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def loads(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) and value else default
    except Exception:
        return default


def round_float(value: Any, digits: int = 4) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), digits)
    return value


def compact_probs(value: Any, digits: int = 4) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): round_float(item, digits)
        for key, item in sorted(value.items())
        if isinstance(item, (int, float))
    }


def first_present(data: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, "", {}):
            return data[key]
    return None


def fetch_match_ids(
    conn: sqlite3.Connection,
    ids: List[str],
    date_from: str,
    date_to: str,
    league: str,
    limit: int,
) -> List[str]:
    if ids:
        return ids
    where = ["1=1"]
    params: List[Any] = []
    if date_from:
        where.append("date(match_date) >= date(?)")
        params.append(date_from)
    if date_to:
        where.append("date(match_date) <= date(?)")
        params.append(date_to)
    if league:
        where.append("league_name_cn = ?")
        params.append(league)
    sql = f"""
        SELECT lottery_match_id
        FROM lottery_matches
        WHERE {' AND '.join(where)}
        ORDER BY date(match_date), beijing_time, lottery_match_id
        LIMIT ?
    """
    params.append(limit)
    return [str(row["lottery_match_id"]) for row in conn.execute(sql, params)]


def latest_odds(conn: sqlite3.Connection, match_id: str, play_type: str) -> Dict[str, Any]:
    if not table_exists(conn, "lottery_odds"):
        return {}
    row = conn.execute(
        """
        SELECT snapshot_type, odds_data, created_at
        FROM lottery_odds
        WHERE lottery_match_id=? AND play_type=?
        ORDER BY
          CASE snapshot_type
            WHEN 'latest' THEN 0
            WHEN 'current' THEN 1
            WHEN 'midday' THEN 2
            WHEN 'opening' THEN 3
            ELSE 4
          END,
          datetime(created_at) DESC
        LIMIT 1
        """,
        (match_id, play_type),
    ).fetchone()
    if not row:
        return {}
    data = loads(row["odds_data"], {})
    if not isinstance(data, dict):
        data = {}
    keep_keys = ("3", "1", "0", "goal_line", "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7")
    return {
        "snapshot": row["snapshot_type"],
        "created_at": row["created_at"],
        "data": {key: data.get(key) for key in keep_keys if key in data},
    }


def latest_report(conn: sqlite3.Connection, match_id: str, report_type: str) -> Dict[str, Any]:
    if not table_exists(conn, "lottery_analysis_reports"):
        return {}
    report_cols = columns(conn, "lottery_analysis_reports")
    stale_filter = "AND COALESCE(is_stale, 0)=0" if "is_stale" in report_cols else ""
    row = conn.execute(
        f"""
        SELECT report_id, report_data, created_at
        FROM lottery_analysis_reports
        WHERE lottery_match_id=? AND report_type=?
          {stale_filter}
        ORDER BY datetime(created_at) DESC, report_id DESC
        LIMIT 1
        """,
        (match_id, report_type),
    ).fetchone()
    if not row:
        return {}
    data = loads(row["report_data"], {})
    return {
        "report_id": row["report_id"],
        "created_at": row["created_at"],
        "data": data if isinstance(data, dict) else {},
    }


def latest_intelligence(conn: sqlite3.Connection, match_id: str) -> Dict[str, Any]:
    if not (table_exists(conn, "intelligence_jobs") and table_exists(conn, "intelligence_packages")):
        return {}
    package_cols = columns(conn, "intelligence_packages")
    select_cols = [
        "ij.status AS job_status",
        "ij.created_at AS job_created_at",
        "ij.updated_at AS job_updated_at",
    ]
    for col in ("evidence_coverage", "strict_coverage", "average_confidence", "missing_critical_count"):
        if col in package_cols:
            select_cols.append(f"ip.{col} AS {col}")
    if "summary_json" in package_cols:
        select_cols.append("ip.summary_json AS summary_json")
    row = conn.execute(
        f"""
        SELECT {', '.join(select_cols)}
        FROM intelligence_jobs ij
        LEFT JOIN intelligence_packages ip ON ip.job_id=ij.job_id
        WHERE ij.lottery_match_id=?
        ORDER BY datetime(COALESCE(ij.updated_at, ij.created_at)) DESC, ij.job_id DESC
        LIMIT 1
        """,
        (match_id,),
    ).fetchone()
    if not row:
        return {}
    result = {key: row[key] for key in row.keys() if key != "summary_json"}
    summary = loads(row["summary_json"], {}) if "summary_json" in row.keys() else {}
    if isinstance(summary, dict):
        result["summary_keys"] = sorted(summary.keys())[:12]
    return result


def latest_result(conn: sqlite3.Connection, match_id: str) -> Dict[str, Any]:
    if not table_exists(conn, "lottery_results"):
        return {}
    row = conn.execute(
        """
        SELECT home_goals_ft, away_goals_ft, home_goals_ht, away_goals_ht,
               spf_result, rqspf_result, bqc_result, bf_result, ou_result,
               draw_time, created_at
        FROM lottery_results
        WHERE lottery_match_id=?
        ORDER BY datetime(COALESCE(draw_time, created_at)) DESC
        LIMIT 1
        """,
        (match_id,),
    ).fetchone()
    if not row:
        return {}
    return {
        "ft": (
            f"{row['home_goals_ft']}:{row['away_goals_ft']}"
            if row["home_goals_ft"] is not None and row["away_goals_ft"] is not None
            else None
        ),
        "ht": (
            f"{row['home_goals_ht']}:{row['away_goals_ht']}"
            if row["home_goals_ht"] is not None and row["away_goals_ht"] is not None
            else None
        ),
        "spf": row["spf_result"],
        "rqspf": row["rqspf_result"],
        "bqc": row["bqc_result"],
        "bf": row["bf_result"],
        "ou": row["ou_result"],
        "draw_time": row["draw_time"],
        "created_at": row["created_at"],
    }


def compact_world_cup(context: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(context, dict):
        return {}
    group = context.get("group") if isinstance(context.get("group"), dict) else {}
    teams = context.get("teams") if isinstance(context.get("teams"), dict) else {}
    compact_teams = {}
    for side, item in teams.items():
        if not isinstance(item, dict):
            continue
        compact_teams[side] = {
            "team": item.get("team_name_cn") or item.get("team_name"),
            "group": item.get("group"),
            "position": item.get("position"),
            "played": item.get("played"),
            "points": item.get("points"),
            "goal_diff": item.get("goal_diff"),
            "pressure": item.get("pressure_level"),
            "qualification": item.get("qualification"),
        }
    return {
        "freshness": context.get("context_freshness"),
        "round": context.get("round") or context.get("group_round"),
        "group": group.get("group"),
        "matches_finished": group.get("matches_finished"),
        "matches_total": group.get("matches_total"),
        "teams": compact_teams,
    }


def compact_report(report: Dict[str, Any]) -> Dict[str, Any]:
    if not report:
        return {}
    fp = report.get("final_prediction") if isinstance(report.get("final_prediction"), dict) else {}
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    mvo = report.get("model_vs_odds") if isinstance(report.get("model_vs_odds"), dict) else {}
    intel = report.get("intelligence_summary") if isinstance(report.get("intelligence_summary"), dict) else {}
    wc = report.get("world_cup_context") or (report.get("competition_context") or {}).get("world_cup_2026")

    spf = plays.get("spf") if isinstance(plays.get("spf"), dict) else {}
    rqspf = plays.get("rqspf") if isinstance(plays.get("rqspf"), dict) else {}
    ou = plays.get("ou") if isinstance(plays.get("ou"), dict) else {}
    bqc = plays.get("bqc") if isinstance(plays.get("bqc"), dict) else {}
    rq_axis = rqspf.get("axis_projection") if isinstance(rqspf.get("axis_projection"), dict) else {}
    ou_diag = ou.get("diagnostics") if isinstance(ou.get("diagnostics"), dict) else {}
    goal_axis = ou.get("goal_axis") if isinstance(ou.get("goal_axis"), dict) else {}

    return {
        "final": {
            "predicted_result": fp.get("predicted_result"),
            "confidence": round_float(fp.get("confidence"), 4),
            "confidence_level": fp.get("confidence_level"),
            "probabilities": compact_probs(fp.get("probabilities")),
            "expected_score": compact_probs(fp.get("expected_score"), 3),
        },
        "model_vs_odds": {
            "model_rec": mvo.get("model_rec"),
            "odds_rec": mvo.get("odds_rec"),
            "agreement": mvo.get("agreement"),
            "edge": compact_probs(mvo.get("edge")),
        },
        "plays": {
            "spf": {
                "direction": spf.get("direction"),
                "probabilities": compact_probs(spf.get("probabilities")),
            },
            "rqspf": {
                "direction": rqspf.get("direction"),
                "label": rqspf.get("recommendation_cn"),
                "goal_line": first_present(rqspf, "goal_line_label", "goal_line"),
                "margin_requirement": rqspf.get("margin_requirement"),
                "display_source": rqspf.get("display_source"),
                "probabilities": compact_probs(rqspf.get("probabilities")),
                "unconditional": compact_probs(rqspf.get("unconditional_probabilities")),
                "axis": {
                    "direction": rq_axis.get("direction"),
                    "basis": rq_axis.get("basis"),
                    "mass": round_float(rq_axis.get("mass"), 4),
                    "probabilities": compact_probs(rq_axis.get("probabilities")),
                },
            },
            "ou": {
                "recommendation": ou.get("recommendation"),
                "line": first_present(ou, "best_line", "line"),
                "confidence": round_float(ou.get("confidence"), 4),
                "confidence_level": ou.get("confidence_level"),
                "probs": compact_probs(ou.get("best_line_probs")),
                "market_recommendation": ou.get("market_recommendation"),
                "market_probs": compact_probs(ou.get("market_best_line_probs")),
                "diagnostic_summary": ou_diag.get("summary"),
                "goal_axis": {
                    "side": goal_axis.get("side"),
                    "risk_level": goal_axis.get("risk_level"),
                    "market_alignment": goal_axis.get("market_alignment"),
                    "expected_total": round_float(goal_axis.get("expected_total"), 3),
                },
            },
            "bqc": {
                "recommendation": bqc.get("recommendation"),
                "label": bqc.get("recommendation_cn"),
                "probabilities": compact_probs(bqc.get("probabilities")),
            },
        },
        "intelligence_summary": {
            "coverage": first_present(intel, "coverage", "evidence_coverage"),
            "strict_coverage": intel.get("strict_coverage"),
            "average_confidence": intel.get("average_confidence"),
            "missing_critical": intel.get("missing_critical"),
        },
        "world_cup": compact_world_cup(wc if isinstance(wc, dict) else {}),
    }


def build_fingerprint(conn: sqlite3.Connection, match_id: str, report_type: str) -> Dict[str, Any]:
    row = conn.execute(
        """
        SELECT lottery_match_id, match_id, league_name_cn, match_date, beijing_time,
               home_team_cn, away_team_cn, home_team_id, away_team_id,
               handicap_line, play_types, sell_status, oddsfe_event_id
        FROM lottery_matches
        WHERE lottery_match_id=?
        """,
        (match_id,),
    ).fetchone()
    if not row:
        return {"lottery_match_id": match_id, "missing": True}
    report_row = latest_report(conn, match_id, report_type)
    odds = {play: latest_odds(conn, match_id, play) for play in DEFAULT_PLAYS}
    return {
        "lottery_match_id": match_id,
        "match": {key: row[key] for key in row.keys()},
        "result": latest_result(conn, match_id),
        "odds": {key: value for key, value in odds.items() if value},
        "analysis_report": {
            "report_id": report_row.get("report_id"),
            "created_at": report_row.get("created_at"),
            **compact_report(report_row.get("data", {})),
        } if report_row else {},
        "intelligence_job": latest_intelligence(conn, match_id),
    }


def flatten(value: Any, prefix: str = "") -> Dict[str, Any]:
    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            result.update(flatten(item, child))
        return result
    if isinstance(value, list):
        return {prefix: json.dumps(value, ensure_ascii=False, sort_keys=True)}
    return {prefix: value}


def values_equal(a: Any, b: Any, tolerance: float) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tolerance
    return a == b


def compare_exports(
    left: Dict[str, Any],
    right: Dict[str, Any],
    tolerance: float,
    limit: int,
    input_only: bool = False,
    ignore_volatile: bool = True,
) -> Dict[str, Any]:
    left_matches = {item["lottery_match_id"]: item for item in left.get("matches", []) if isinstance(item, dict)}
    right_matches = {item["lottery_match_id"]: item for item in right.get("matches", []) if isinstance(item, dict)}
    all_ids = sorted(set(left_matches) | set(right_matches))
    rows = []
    path_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}

    def ignored(path: str) -> bool:
        if input_only and path.startswith("analysis_report."):
            return True
        if not ignore_volatile:
            return False
        volatile_tokens = (
            ".created_at",
            ".updated_at",
            ".job_created_at",
            ".job_updated_at",
            ".report_id",
            ".created_at",
        )
        return any(path.endswith(token) for token in volatile_tokens)

    for match_id in all_ids:
        if match_id not in left_matches or match_id not in right_matches:
            rows.append({
                "lottery_match_id": match_id,
                "status": "missing_in_left" if match_id not in left_matches else "missing_in_right",
            })
            continue
        lf = flatten(left_matches[match_id])
        rf = flatten(right_matches[match_id])
        diffs = []
        for path in sorted(set(lf) | set(rf)):
            if ignored(path):
                continue
            lv = lf.get(path)
            rv = rf.get(path)
            if not values_equal(lv, rv, tolerance):
                diffs.append({"path": path, "left": lv, "right": rv})
                path_counts[path] = path_counts.get(path, 0) + 1
                category = path.split(".", 1)[0] if "." in path else path
                category_counts[category] = category_counts.get(category, 0) + 1
        if diffs:
            rows.append({
                "lottery_match_id": match_id,
                "teams": f"{left_matches[match_id].get('match', {}).get('home_team_cn')} vs {left_matches[match_id].get('match', {}).get('away_team_cn')}",
                "differences": len(diffs),
                "preview": diffs[:limit],
            })
    return {
        "left_source": left.get("source"),
        "right_source": right.get("source"),
        "matches_compared": len(all_ids),
        "matches_with_differences": len(rows),
        "input_only": input_only,
        "ignore_volatile": ignore_volatile,
        "category_counts": dict(sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))),
        "top_paths": [
            {"path": path, "count": count}
            for path, count in sorted(path_counts.items(), key=lambda item: (-item[1], item[0]))[:30]
        ],
        "rows": rows[:limit],
    }


def run_export(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    conn = connect(db_path)
    ids = fetch_match_ids(
        conn,
        [item.strip() for item in (args.ids or "").split(",") if item.strip()],
        args.date_from,
        args.date_to,
        args.league,
        args.limit,
    )
    matches = [build_fingerprint(conn, match_id, args.report_type) for match_id in ids]
    conn.close()
    return {
        "source": args.source or str(db_path),
        "db": str(db_path),
        "report_type": args.report_type,
        "date_from": args.date_from,
        "date_to": args.date_to,
        "league": args.league,
        "count": len(matches),
        "matches": matches,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--ids", default="", help="Comma-separated lottery_match_id list")
    parser.add_argument("--date-from", "--from", dest="date_from", default="2026-06-11")
    parser.add_argument("--date-to", "--to", dest="date_to", default="2026-07-19")
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--report-type", default="prediction")
    parser.add_argument("--source", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--compare", nargs=2, metavar=("LEFT_JSON", "RIGHT_JSON"))
    parser.add_argument("--tolerance", type=float, default=0.0001)
    parser.add_argument("--diff-limit", type=int, default=30)
    parser.add_argument("--input-only", action="store_true", help="When comparing, ignore analysis_report.* output fields")
    parser.add_argument("--include-volatile", action="store_true", help="Keep timestamps/report ids in comparisons")
    parser.add_argument("--summary-only", action="store_true", help="When comparing, omit per-match rows")
    args = parser.parse_args()

    if args.compare:
        left = json.loads(Path(args.compare[0]).read_text(encoding="utf-8-sig"))
        right = json.loads(Path(args.compare[1]).read_text(encoding="utf-8-sig"))
        result = compare_exports(
            left,
            right,
            args.tolerance,
            args.diff_limit,
            input_only=args.input_only,
            ignore_volatile=not args.include_volatile,
        )
        if args.summary_only:
            result = {key: value for key, value in result.items() if key != "rows"}
    else:
        result = run_export(args)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
