"""Apply a national-team O/U conflict gate to existing lottery reports.

Dry-run by default. This script is intentionally independent from
backend/app/core/analyze.py so cloud production can test the gate without
syncing a large local candidate analyze.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"
BACKUP_DIR = Path(os.environ.get("FOOTBALL_BACKUP_DIR", ROOT.parent / "football_backups")) / "national_ou_gate"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core import analyze as analyze_core  # noqa: E402
from backend.app.core.validate import _validate_predictions  # noqa: E402


NATIONAL_KEYWORDS = (
    "\u4e16\u754c\u676f", "\u56fd\u9645\u53cb\u8c0a", "\u56fd\u9645\u8d5b", "\u53cb\u8c0a\u8d5b",
    "\u6b27\u6d32\u676f", "\u6b27\u56fd\u8054", "\u7f8e\u6d32\u676f", "\u4e9a\u6d32\u676f", "\u975e\u6d32\u676f",
    "\u9884\u9009\u8d5b", "\u4e16\u9884\u8d5b", "\u4e16\u754c\u676f\u9884\u9009",
    "FIFA World Cup", "World Cup", "World Cup Qualification",
    "World Cup Qualifying", "International Friendly", "Friendly", "Friendlies",
    "UEFA Nations League", "Nations League", "UEFA Euro", "European Championship",
    "Copa America", "Copa Am\u00e9rica", "AFC Asian Cup", "Asian Cup",
    "Africa Cup of Nations", "Africa Cup", "CAF Africa Cup",
    "CONCACAF Gold Cup", "Gold Cup", "CONCACAF Nations League", "International",
)

EXCLUDED_KEYWORDS = (
    "\u5973", "U16", "U17", "U18", "U19", "U20", "U21", "U23",
    "Youth", "Women", "Libertadores", "Sudamericana",
    "Champions League", "Europa League", "Conference League",
    "\u4ff1\u4e50\u90e8", "\u89e3\u653e\u8005\u676f", "\u5357\u7403\u676f",
    "\u6b27\u51a0", "\u6b27\u8054", "\u6b27\u534f\u8054",
)


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
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({quote_ident(table)})")}


def quote_ident(name: str) -> str:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name or ""):
        raise ValueError(f"invalid identifier: {name!r}")
    return '"' + name.replace('"', '""') + '"'


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


def parse_ou_side(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "\u5927" in text or text.startswith("over") or text.startswith("o"):
        return "over"
    if "\u5c0f" in text or text.startswith("under") or text.startswith("u"):
        return "under"
    return ""


def parse_line(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
    return to_float(match.group(1)) if match else None


def format_line(value: float) -> str:
    if abs(float(value) - round(float(value))) < 0.0001:
        return str(int(round(float(value))))
    return f"{float(value):g}"


def format_ou(side: str, line: float) -> str:
    prefix = "\u5927" if side == "over" else "\u5c0f"
    return f"{prefix}{format_line(line)}"


def actual_ou_side(home_goals: Any, away_goals: Any, line: Optional[float]) -> str:
    if line is None:
        return ""
    home = to_int(home_goals)
    away = to_int(away_goals)
    if home is None or away is None:
        return ""
    total = home + away
    if total > float(line):
        return "over"
    if total < float(line):
        return "under"
    return "push"


def score_total_side(score: Any, line: Optional[float]) -> str:
    if line is None:
        return ""
    text = str(score or "")
    match = re.search(r"(\d+)\s*[-:]\s*(\d+)", text)
    if not match:
        return ""
    total = int(match.group(1)) + int(match.group(2))
    if total > float(line):
        return "over"
    if total < float(line):
        return "under"
    return "push"


def national_filter_sql(column: str) -> Tuple[str, List[Any]]:
    include = " OR ".join([f"COALESCE({column}, '') LIKE ?" for _ in NATIONAL_KEYWORDS])
    exclude = " OR ".join([f"COALESCE({column}, '') LIKE ?" for _ in EXCLUDED_KEYWORDS])
    params: List[Any] = [f"%{item}%" for item in NATIONAL_KEYWORDS]
    params.extend([f"%{item}%" for item in EXCLUDED_KEYWORDS])
    return f"AND ({include}) AND NOT ({exclude})", params


def fetch_latest_reports(
    conn: sqlite3.Connection,
    date_from: Optional[str],
    date_to: Optional[str],
    league: Optional[str],
    report_type: str,
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

    return conn.execute(
        f"""
        SELECT ar.report_id, ar.report_data, ar.report_type, ar.created_at AS report_created_at,
               lm.lottery_match_id, lm.match_id, lm.match_num, lm.home_team_id, lm.away_team_id,
               lm.home_team_cn, lm.away_team_cn, lm.league_name_cn, lm.match_date, lm.beijing_time,
               lr.home_goals_ft, lr.away_goals_ft
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
        """,
        params,
    ).fetchall()


def fact_profile(
    conn: sqlite3.Connection,
    fact_table: str,
    team_id: Any,
    before_date: Any,
    limit: int,
) -> Dict[str, Any]:
    if team_id in (None, ""):
        return {}
    table = quote_ident(fact_table)
    columns = table_columns(conn, fact_table)
    required = {"team_id", "match_date", "goals_for", "goals_against"}
    if not required.issubset(columns):
        return {}
    clauses = [
        "team_id = ?",
        "date(match_date) < date(?)",
        "goals_for IS NOT NULL",
        "goals_against IS NOT NULL",
    ]
    params: List[Any] = [str(team_id), str(before_date or "")[:10]]
    if "league_name_cn" in columns:
        scope_sql, scope_params = national_filter_sql("league_name_cn")
        clauses.append(scope_sql.replace("AND ", "", 1))
        params.extend(scope_params)
    source_order = ", source_match_id DESC" if "source_match_id" in columns else ""
    params.append(max(limit * 2, limit))
    rows = conn.execute(
        f"""
        SELECT team_id, goals_for, goals_against, match_date
        FROM {table}
        WHERE {" AND ".join(clauses)}
        ORDER BY date(match_date) DESC{source_order}
        LIMIT ?
        """,
        params,
    ).fetchall()

    seen = set()
    items: List[Dict[str, float]] = []
    for row in rows:
        gf = to_float(row["goals_for"])
        ga = to_float(row["goals_against"])
        if gf is None or ga is None:
            continue
        key = (str(row["team_id"]), str(row["match_date"])[:10], gf, ga)
        if key in seen:
            continue
        seen.add(key)
        items.append({"gf": gf, "ga": ga})
        if len(items) >= limit:
            break
    if not items:
        return {"sample": 0}
    n = len(items)

    def rate(fn) -> float:
        return round(sum(1 for item in items if fn(item)) / n, 4)

    return {
        "sample": n,
        "avg_for": round(mean(item["gf"] for item in items), 3),
        "avg_against": round(mean(item["ga"] for item in items), 3),
        "clean_sheet_rate": rate(lambda item: item["ga"] == 0),
        "blank_rate": rate(lambda item: item["gf"] == 0),
        "big_score_rate": rate(lambda item: item["gf"] >= 3),
        "big_concede_rate": rate(lambda item: item["ga"] >= 3),
        "high_total_rate": rate(lambda item: item["gf"] + item["ga"] >= 4),
        "low_total_rate": rate(lambda item: item["gf"] + item["ga"] <= 2),
    }


def goal_signal(attack: Dict[str, Any], defense: Dict[str, Any]) -> Optional[float]:
    attack_avg = to_float(attack.get("avg_for"))
    defense_avg = to_float(defense.get("avg_against"))
    if attack_avg is None or defense_avg is None:
        return None
    signal = attack_avg * 0.62 + defense_avg * 0.38
    signal += max(0.0, (to_float(attack.get("big_score_rate"), 0.0) or 0.0) - 0.25) * 0.28
    signal += max(0.0, (to_float(defense.get("big_concede_rate"), 0.0) or 0.0) - 0.15) * 0.24
    signal -= max(0.0, (to_float(defense.get("clean_sheet_rate"), 0.0) or 0.0) - 0.34) * 0.22
    signal -= max(0.0, (to_float(attack.get("blank_rate"), 0.0) or 0.0) - 0.28) * 0.18
    return round(max(0.12, min(4.8, signal)), 3)


def national_ou_signal(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    fact_table: str,
    line: float,
    limit: int,
    min_sample: int,
    band: float,
) -> Dict[str, Any]:
    before_date = row["beijing_time"] or row["match_date"]
    home = fact_profile(conn, fact_table, row["home_team_id"], before_date, limit)
    away = fact_profile(conn, fact_table, row["away_team_id"], before_date, limit)
    if not home or not away:
        return {"eligible": False, "reason": "missing_profile", "home_sample": home.get("sample", 0), "away_sample": away.get("sample", 0)}
    home_goal = goal_signal(home, away)
    away_goal = goal_signal(away, home)
    if home_goal is None or away_goal is None:
        return {"eligible": False, "reason": "missing_signal", "home_sample": home.get("sample", 0), "away_sample": away.get("sample", 0)}
    total_signal = round(home_goal + away_goal, 3)
    gap = round(total_signal - float(line), 3)
    min_actual_sample = min(int(home.get("sample") or 0), int(away.get("sample") or 0))
    side = None
    eligible = False
    reason = "inside_neutral_band"
    if min_actual_sample < min_sample:
        reason = "insufficient_sample"
    elif gap >= band:
        side = "over"
        eligible = True
        reason = "above_line_band"
    elif gap <= -band:
        side = "under"
        eligible = True
        reason = "below_line_band"
    return {
        "eligible": eligible,
        "reason": reason,
        "side": side,
        "line": round(float(line), 3),
        "band": band,
        "total_signal": total_signal,
        "total_gap": gap,
        "home_signal": home_goal,
        "away_signal": away_goal,
        "home_sample": home.get("sample"),
        "away_sample": away.get("sample"),
        "min_sample_required": min_sample,
        "source_table": fact_table,
        "home_profile": home,
        "away_profile": away,
    }


def report_ou(report: Dict[str, Any]) -> Dict[str, Any]:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    ou = plays.get("ou") if isinstance(plays.get("ou"), dict) else {}
    return ou


def score_axis_note(report: Dict[str, Any], side: str, line: float, top3_override: Optional[List[Dict[str, Any]]] = None) -> str:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    top3 = top3_override if isinstance(top3_override, list) else (plays.get("top3_scores") or ((report.get("final_prediction") or {}).get("most_likely_scores") or []))
    if not isinstance(top3, list):
        top3 = []
    sides = []
    for item in top3[:3]:
        if not isinstance(item, dict):
            continue
        score = item.get("score")
        if not score and item.get("home_goals") is not None and item.get("away_goals") is not None:
            score = f"{item.get('home_goals')}-{item.get('away_goals')}"
        side_at_score = score_total_side(score, line)
        if side_at_score:
            sides.append(side_at_score)
    opposite = "under" if side == "over" else "over"
    side_cn = "\u5927\u7403" if side == "over" else "\u5c0f\u7403"
    if sides.count(opposite) >= 2:
        return (
            f"\u5927\u5c0f\u7403\u662f\u603b\u8fdb\u7403\u6982\u7387\u8f74\uff0c\u63a8\u8350\u6bd4\u5206\u662f\u5355\u70b9\u843d\u70b9\u3002"
            f"\u672c\u573a{side_cn}\u7531\u56fd\u5bb6\u961f\u5386\u53f2\u8fdb\u5931\u7403\u6837\u672c\u6821\u51c6\uff1b"
            f"Top3\u6bd4\u5206\u4ecd\u504f\u5bf9\u4fa7\uff0c\u8bf4\u660e\u9ad8\u603b\u8fdb\u7403\u60c5\u5f62\u66f4\u5206\u6563\uff0c\u6bd4\u5206\u53ea\u4f5c\u4f4e\u7f6e\u4fe1\u53c2\u8003\u3002"
        )
    return (
        f"\u672c\u573a{side_cn}\u7531\u56fd\u5bb6\u961f\u5386\u53f2\u8fdb\u5931\u7403\u6837\u672c\u6821\u51c6\uff1b"
        f"\u6bd4\u5206\u662f\u5355\u70b9\u6982\u7387\uff0c\u4e0d\u7b49\u540c\u4e8e\u603b\u8fdb\u7403\u533a\u95f4\u6982\u7387\u3002"
    )


def preview_score_axis(report: Dict[str, Any], side: str, line: float) -> Dict[str, Any]:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    if not isinstance(plays, dict):
        return {}
    score_matrix = (((report.get("base_prediction") or {}).get("poisson") or {}).get("score_matrix"))
    if not score_matrix:
        return {}
    preview = json.loads(json.dumps(report, ensure_ascii=False, default=str))
    preview_plays = preview.get("play_predictions") if isinstance(preview.get("play_predictions"), dict) else {}
    preview_ou = preview_plays.get("ou") if isinstance(preview_plays.get("ou"), dict) else {}
    if not preview_ou:
        return {}
    preview_ou["recommendation"] = analyze_core._format_ou_recommendation(side, line)
    scores = analyze_core._enhance_score_candidates(score_matrix, preview_plays)
    opposite = "under" if side == "over" else "over"
    sides = []
    for item in scores[:3]:
        if not isinstance(item, dict):
            continue
        score = item.get("score")
        if not score and item.get("home_goals") is not None and item.get("away_goals") is not None:
            score = f"{item.get('home_goals')}-{item.get('away_goals')}"
        side_at_score = score_total_side(score, line)
        if side_at_score:
            sides.append(side_at_score)
    coherent = sum(1 for item in sides if item == side)
    conflicting = sum(1 for item in sides if item == opposite)
    return {
        "scores": scores,
        "sides": sides,
        "coherent": coherent,
        "conflicting": conflicting,
        "blocked": conflicting >= 2,
    }


def evaluate_change(row: sqlite3.Row, report: Dict[str, Any], signal: Dict[str, Any], refresh_notes: bool = False) -> Optional[Dict[str, Any]]:
    ou = report_ou(report)
    if not ou:
        return None
    line = parse_line(ou.get("best_line") or ou.get("line") or ou.get("recommendation"))
    if line is None:
        return None
    current_side = parse_ou_side(ou.get("recommendation")) or parse_ou_side(ou.get("model_recommendation"))
    national_side = signal.get("side")
    if not signal.get("eligible") or national_side not in {"over", "under"} or current_side not in {"over", "under"}:
        return None
    if national_side == current_side:
        if not (
            refresh_notes
            and ou.get("recommendation_basis") == "national_reference_conflict_gate"
            and not ou.get("score_axis_note")
        ):
            return None
    preview = preview_score_axis(report, national_side, line) if national_side in {"over", "under"} else {}
    if national_side != current_side and isinstance(preview, dict) and preview.get("blocked"):
        return None
    actual = actual_ou_side(row["home_goals_ft"], row["away_goals_ft"], line)
    before_correct = current_side == actual if actual in {"over", "under"} else None
    after_correct = national_side == actual if actual in {"over", "under"} else None
    return {
        "lottery_match_id": str(row["lottery_match_id"]),
        "report_id": int(row["report_id"]),
        "match_num": row["match_num"],
        "date": str(row["beijing_time"] or row["match_date"])[:10],
        "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
        "score": f"{row['home_goals_ft']}:{row['away_goals_ft']}",
        "line": line,
        "before_side": current_side,
        "after_side": national_side,
        "before": format_ou(current_side, line),
        "after": format_ou(national_side, line),
        "actual": format_ou(actual, line) if actual in {"over", "under"} else actual,
        "before_correct": before_correct,
        "after_correct": after_correct,
        "direction": (
            "metadata" if national_side == current_side
            else "improved" if before_correct is False and after_correct is True
            else "regressed" if before_correct is True and after_correct is False
            else "changed"
        ),
        "signal": signal,
        "preview": preview,
    }


def build_display_probs(ou: Dict[str, Any], side: str, signal: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    probs = ou.get("best_line_probs") if isinstance(ou.get("best_line_probs"), dict) else {}
    over = to_float(probs.get("over"), 0.5) or 0.5
    under = to_float(probs.get("under"), 0.5) or 0.5
    sample_bonus = min(
        0.035,
        max(
            0.0,
            (min(to_float(signal.get("home_sample"), 0.0) or 0.0, to_float(signal.get("away_sample"), 0.0) or 0.0)
             - (to_float(signal.get("min_sample_required"), 16.0) or 16.0)) * 0.003,
        ),
    )
    gap_bonus = min(0.055, abs(to_float(signal.get("total_gap"), 0.0) or 0.0) * 0.055)
    selected = round(max(0.535, min(0.64, 0.535 + sample_bonus + gap_bonus)), 4)
    display = {
        "over": selected if side == "over" else round(1.0 - selected, 4),
        "under": selected if side == "under" else round(1.0 - selected, 4),
        "source": "national_reference_conflict_gate",
    }
    raw = {
        "over": round(over, 4),
        "under": round(under, 4),
        "source": "pre_national_reference_gate",
    }
    return raw, display


def apply_to_report(report: Dict[str, Any], change: Dict[str, Any]) -> Dict[str, Any]:
    updated = json.loads(json.dumps(report, ensure_ascii=False, default=str))
    plays = updated.setdefault("play_predictions", {})
    ou = plays.setdefault("ou", {})
    line = float(change["line"])
    national_side = change["after_side"]
    preview = change.get("preview") if isinstance(change.get("preview"), dict) else {}
    raw_probs, display_probs = build_display_probs(ou, national_side, change["signal"])
    previous_basis = ou.get("recommendation_basis")
    before = ou.get("recommendation") or change["before"]
    after = change["after"]

    ou.setdefault("model_recommendation", before)
    ou["pre_national_recommendation"] = before
    ou["recommendation"] = after
    ou["recommendation_basis"] = "national_reference_conflict_gate"
    ou["confidence"] = max(display_probs["over"], display_probs["under"])
    ou["confidence_level"] = "medium" if ou["confidence"] < 0.58 else "high"
    ou["national_reference_signal"] = change["signal"]
    ou["raw_best_line_probs"] = raw_probs
    ou["best_line_probs"] = display_probs
    ou["display_probability_override"] = {
        "raw_best_line_probs": raw_probs,
        "best_line_probs": display_probs,
    }
    ou["recommendation_adjustment"] = {
        "from": before,
        "to": after,
        "reason": "national_reference_conflict_gate",
        "previous_basis": previous_basis,
        "model_side": change["before_side"],
        "national_reference_side": national_side,
        "national_reference_total_gap": change["signal"].get("total_gap"),
        "national_reference_source_table": change["signal"].get("source_table"),
    }
    preview_scores = preview.get("scores") if isinstance(preview.get("scores"), list) else []
    if preview_scores:
        plays["top3_scores"] = preview_scores
    ou["score_axis_note"] = score_axis_note(updated, national_side, line, top3_override=preview_scores)
    ou["national_gate_guard"] = {
        "blocked": False,
        "reason": "score_axis_refreshed_after_gate",
        "target_side": national_side,
        "top_score_sides": preview.get("sides") or [],
        "preview_scores": [
            item.get("score")
            for item in preview_scores[:3]
            if isinstance(item, dict) and item.get("score")
        ],
    }

    analyses = updated.get("analyses")
    if isinstance(analyses, dict) and isinstance(analyses.get("ou"), dict):
        analyses["ou"].update(ou)
    return updated


def make_backup(conn: sqlite3.Connection, changes: Sequence[Dict[str, Any]], dates: Sequence[str]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / f"national_ou_gate_rows_{stamp}.json"
    match_ids = sorted({item["lottery_match_id"] for item in changes})
    report_ids = sorted({item["report_id"] for item in changes})
    backup: Dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "match_ids": match_ids,
        "report_ids": report_ids,
        "dates": list(dates),
        "tables": {},
    }

    if report_ids:
        backup["tables"]["lottery_analysis_reports"] = [
            dict(row) for row in conn.execute(
                f"SELECT * FROM lottery_analysis_reports WHERE report_id IN ({placeholders(report_ids)})",
                report_ids,
            ).fetchall()
        ]
    if match_ids and table_exists(conn, "lottery_predictions"):
        backup["tables"]["lottery_predictions"] = [
            dict(row) for row in conn.execute(
                f"SELECT * FROM lottery_predictions WHERE lottery_match_id IN ({placeholders(match_ids)})",
                match_ids,
            ).fetchall()
        ]
    if dates and table_exists(conn, "lottery_validation"):
        backup["tables"]["lottery_validation"] = [
            dict(row) for row in conn.execute(
                f"""
                SELECT lv.*
                FROM lottery_validation lv
                JOIN lottery_matches lm ON lm.lottery_match_id = lv.lottery_match_id
                WHERE substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) IN ({placeholders(dates)})
                """,
                list(dates),
            ).fetchall()
        ]
    if dates and table_exists(conn, "post_match_reviews"):
        backup["tables"]["post_match_reviews"] = [
            dict(row) for row in conn.execute(
                f"""
                SELECT pr.*
                FROM post_match_reviews pr
                JOIN lottery_matches lm ON lm.lottery_match_id = pr.match_key
                WHERE substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) IN ({placeholders(dates)})
                """,
                list(dates),
            ).fetchall()
        ]
    path.write_text(dumps_json(backup), encoding="utf-8")
    return path


def update_prediction_rows(conn: sqlite3.Connection, change: Dict[str, Any], updated_ou: Dict[str, Any]) -> int:
    if not table_exists(conn, "lottery_predictions"):
        return 0
    rows = conn.execute(
        """
        SELECT prediction_id, predictions
        FROM lottery_predictions
        WHERE lottery_match_id = ? AND play_type = 'ou'
        """,
        (change["lottery_match_id"],),
    ).fetchall()
    count = 0
    for row in rows:
        pred = loads_json(row["predictions"], {})
        if isinstance(pred, dict):
            pred.update(updated_ou)
        else:
            pred = updated_ou
        conn.execute(
            """
            UPDATE lottery_predictions
            SET predictions = ?, recommendation = ?, confidence = ?, confidence_level = ?
            WHERE prediction_id = ?
            """,
            (
                dumps_json(pred),
                updated_ou.get("recommendation"),
                to_float(updated_ou.get("confidence"), None),
                updated_ou.get("confidence_level"),
                row["prediction_id"],
            ),
        )
        count += 1
    return count


def apply_changes(conn: sqlite3.Connection, report_rows: Dict[int, sqlite3.Row], changes: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counters = {"reports": 0, "prediction_rows": 0}
    for change in changes:
        row = report_rows[int(change["report_id"])]
        report = loads_json(row["report_data"], {})
        updated = apply_to_report(report, change)
        conn.execute(
            "UPDATE lottery_analysis_reports SET report_data = ? WHERE report_id = ?",
            (dumps_json(updated), change["report_id"]),
        )
        counters["reports"] += 1
        updated_ou = ((updated.get("play_predictions") or {}).get("ou") or {})
        counters["prediction_rows"] += update_prediction_rows(conn, change, updated_ou)
    return counters


def delete_validation_rows_for_dates(conn: sqlite3.Connection, dates: Sequence[str]) -> Dict[str, int]:
    deleted = {"lottery_validation": 0, "post_match_reviews": 0}
    if not dates:
        return deleted
    match_ids = [
        str(row["lottery_match_id"])
        for row in conn.execute(
            f"""
            SELECT lottery_match_id
            FROM lottery_matches
            WHERE substr(COALESCE(beijing_time, match_date), 1, 10) IN ({placeholders(dates)})
            """,
            list(dates),
        ).fetchall()
    ]
    if not match_ids:
        return deleted
    if table_exists(conn, "lottery_validation"):
        deleted["lottery_validation"] = conn.execute(
            f"SELECT COUNT(*) FROM lottery_validation WHERE lottery_match_id IN ({placeholders(match_ids)})",
            match_ids,
        ).fetchone()[0]
        conn.execute(
            f"DELETE FROM lottery_validation WHERE lottery_match_id IN ({placeholders(match_ids)})",
            match_ids,
        )
    if table_exists(conn, "post_match_reviews"):
        deleted["post_match_reviews"] = conn.execute(
            f"SELECT COUNT(*) FROM post_match_reviews WHERE match_key IN ({placeholders(match_ids)})",
            match_ids,
        ).fetchone()[0]
        conn.execute(
            f"DELETE FROM post_match_reviews WHERE match_key IN ({placeholders(match_ids)})",
            match_ids,
        )
    return deleted


def summarize_changes(changes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    counts = defaultdict(int)
    before_correct = 0
    after_correct = 0
    scored = 0
    for item in changes:
        counts[item["direction"]] += 1
        if item.get("before_correct") is not None and item.get("after_correct") is not None:
            scored += 1
            before_correct += int(bool(item["before_correct"]))
            after_correct += int(bool(item["after_correct"]))
    return {
        "changes": len(changes),
        "improved": counts["improved"],
        "regressed": counts["regressed"],
        "changed_only": counts["changed"],
        "metadata_only": counts["metadata"],
        "scored": scored,
        "before_correct": before_correct,
        "after_correct": after_correct,
        "delta_correct": after_correct - before_correct,
        "before_accuracy": round(before_correct * 100 / scored, 1) if scored else 0.0,
        "after_accuracy": round(after_correct * 100 / scored, 1) if scored else 0.0,
    }


def build_plan(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    with connect(db_path) as conn:
        if not table_exists(conn, args.fact_table):
            raise SystemExit(f"fact table not found: {args.fact_table}")
        rows = fetch_latest_reports(conn, args.date_from, args.date_to, args.league, args.report_type)
        report_rows = {int(row["report_id"]): row for row in rows}
        changes: List[Dict[str, Any]] = []
        skipped = defaultdict(int)
        for row in rows:
            report = loads_json(row["report_data"], {})
            ou = report_ou(report)
            line = parse_line(ou.get("best_line") or ou.get("line") or ou.get("recommendation"))
            if line is None:
                skipped["missing_line"] += 1
                continue
            signal = national_ou_signal(conn, row, args.fact_table, line, args.limit, args.min_sample, args.band)
            change = evaluate_change(row, report, signal, refresh_notes=args.refresh_notes)
            if change:
                changes.append(change)
            else:
                skipped[signal.get("reason") or "no_conflict"] += 1

    dates = sorted({item["date"] for item in changes})
    return {
        "mode": "apply" if args.apply else "dry_run",
        "db": str(db_path),
        "fact_table": args.fact_table,
        "settings": {
            "date_from": args.date_from,
            "date_to": args.date_to,
            "league": args.league,
            "report_type": args.report_type,
            "limit": args.limit,
            "min_sample": args.min_sample,
            "band": args.band,
        },
        "reports_checked": len(report_rows),
        "changed_dates": dates,
        "summary": summarize_changes(changes),
        "skipped": dict(sorted(skipped.items())),
        "changes": changes,
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    plan = build_plan(args)
    if not args.apply:
        return plan

    summary = plan["summary"]
    if args.rollback_on_worse and summary["delta_correct"] < 0:
        plan["accepted"] = False
        plan["abort_reason"] = "candidate_ou_delta_worse"
        return plan
    if not plan["changes"]:
        plan["accepted"] = True
        plan["apply_result"] = {"reports": 0, "prediction_rows": 0}
        return plan

    db_path = Path(args.db)
    with connect(db_path) as conn:
        report_ids = [int(item["report_id"]) for item in plan["changes"]]
        report_rows = {
            int(row["report_id"]): row
            for row in conn.execute(
                f"SELECT * FROM lottery_analysis_reports WHERE report_id IN ({placeholders(report_ids)})",
                report_ids,
            ).fetchall()
        }
        backup_path = make_backup(conn, plan["changes"], plan["changed_dates"])
        apply_result = apply_changes(conn, report_rows, plan["changes"])
        deleted = {"lottery_validation": 0, "post_match_reviews": 0}
        conn.commit()
        if args.rebuild_validation and plan["changed_dates"]:
            deleted = delete_validation_rows_for_dates(conn, plan["changed_dates"])
            conn.commit()

    validation_result = None
    if args.rebuild_validation and plan["changed_dates"]:
        validation_result = _validate_predictions(str(db_path), plan["changed_dates"])

    plan["accepted"] = True
    plan["backup_path"] = str(backup_path)
    plan["apply_result"] = apply_result
    plan["deleted_for_validation_rebuild"] = deleted
    plan["validation_result"] = validation_result
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply national-team O/U conflict gate to existing reports")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--fact-table", default=os.environ.get("FOOTBALL_NATIONAL_REFERENCE_FACT_TABLE", "team_match_facts"))
    parser.add_argument("--date-from", dest="date_from", default=None)
    parser.add_argument("--date-to", dest="date_to", default=None)
    parser.add_argument("--league", default="\u4e16\u754c\u676f")
    parser.add_argument("--report-type", default="prediction")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--min-sample", type=int, default=16)
    parser.add_argument("--band", type=float, default=0.25)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback-on-worse", action="store_true")
    parser.add_argument("--rebuild-validation", action="store_true")
    parser.add_argument("--refresh-notes", action="store_true", help="Only add score-axis explanation notes to already gated reports")
    parser.add_argument("--examples-limit", type=int, default=20)
    args = parser.parse_args()

    result = run(args)
    if args.examples_limit >= 0 and len(result.get("changes") or []) > args.examples_limit:
        result["changes"] = result["changes"][: args.examples_limit]
        result["changes_truncated"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
