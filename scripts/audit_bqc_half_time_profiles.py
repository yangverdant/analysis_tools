"""Build and audit pre-match half-time profiles for BQC decisions.

The script is deliberately diagnostic. It uses only team facts before the
target match date to build a half-time profile, then compares the profile-based
half-time leg with the active BQC recommendation after the match is settled.
It does not rewrite predictions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"
DEFAULT_VERSION = "bqc_half_time_profile_v1"

BQC_LATIN_TO_CODE = {
    "hh": "33", "hd": "31", "ha": "30",
    "dh": "13", "dd": "11", "da": "10",
    "ah": "03", "ad": "01", "aa": "00",
}
BQC_CODE_TO_LATIN = {value: key for key, value in BQC_LATIN_TO_CODE.items()}
BQC_CN_TO_CODE = {
    "\u80dc\u80dc": "33", "\u80dc\u5e73": "31", "\u80dc\u8d1f": "30",
    "\u5e73\u80dc": "13", "\u5e73\u5e73": "11", "\u5e73\u8d1f": "10",
    "\u8d1f\u80dc": "03", "\u8d1f\u5e73": "01", "\u8d1f\u8d1f": "00",
}
BQC_CODE_TO_CN = {value: key for key, value in BQC_CN_TO_CODE.items()}
SPF_TO_CODE = {
    "home_win": "3", "draw": "1", "away_win": "0",
    "\u4e3b\u80dc": "3", "\u80dc": "3",
    "\u5e73\u5c40": "1", "\u5e73": "1",
    "\u5ba2\u80dc": "0", "\u8d1f": "0",
}


CREATE_PROFILE_SQL = """
CREATE TABLE IF NOT EXISTS bqc_half_time_profiles (
    profile_id TEXT PRIMARY KEY,
    lottery_match_id TEXT NOT NULL,
    match_date TEXT,
    team_side TEXT NOT NULL,
    team_id TEXT,
    opponent_team_id TEXT,
    team_name TEXT,
    opponent_name TEXT,
    fact_table TEXT NOT NULL,
    version_tag TEXT NOT NULL,
    sample_limit INTEGER,
    sample_size INTEGER,
    source_window_start TEXT,
    source_window_end TEXT,
    ht_goals_for_avg REAL,
    ht_goals_against_avg REAL,
    ht_total_goals_avg REAL,
    ht_score_rate REAL,
    ht_concede_rate REAL,
    ht_zero_zero_rate REAL,
    ht_under_1_5_rate REAL,
    ht_win_rate REAL,
    ht_draw_rate REAL,
    ht_loss_rate REAL,
    profile_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_AUDIT_SQL = """
CREATE TABLE IF NOT EXISTS bqc_half_time_profile_audits (
    audit_id TEXT PRIMARY KEY,
    lottery_match_id TEXT NOT NULL,
    report_id INTEGER,
    match_date TEXT,
    match_num TEXT,
    league_name_cn TEXT,
    home_team_cn TEXT,
    away_team_cn TEXT,
    current_bqc TEXT,
    profile_bqc TEXT,
    actual_bqc TEXT,
    current_correct INTEGER,
    profile_correct INTEGER,
    changed INTEGER,
    signal_json TEXT,
    version_tag TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_PATTERN_SQL = """
CREATE TABLE IF NOT EXISTS bqc_phase_error_patterns (
    pattern_id TEXT PRIMARY KEY,
    lottery_match_id TEXT NOT NULL,
    report_id INTEGER,
    match_date TEXT,
    match_num TEXT,
    league_name_cn TEXT,
    pattern_type TEXT NOT NULL,
    profile_role TEXT,
    half_axis_error INTEGER,
    full_axis_error INTEGER,
    path_flip INTEGER,
    current_bqc TEXT,
    profile_bqc TEXT,
    actual_bqc TEXT,
    signal_reason TEXT,
    signal_confidence REAL,
    notes_json TEXT,
    version_tag TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_bqc_ht_profiles_match ON bqc_half_time_profiles(lottery_match_id, version_tag);",
    "CREATE INDEX IF NOT EXISTS idx_bqc_ht_profiles_team ON bqc_half_time_profiles(team_id, match_date);",
    "CREATE INDEX IF NOT EXISTS idx_bqc_ht_audits_date ON bqc_half_time_profile_audits(match_date, version_tag);",
    "CREATE INDEX IF NOT EXISTS idx_bqc_ht_audits_match ON bqc_half_time_profile_audits(lottery_match_id, version_tag);",
    "CREATE INDEX IF NOT EXISTS idx_bqc_phase_patterns_date ON bqc_phase_error_patterns(match_date, version_tag, pattern_type);",
    "CREATE INDEX IF NOT EXISTS idx_bqc_phase_patterns_match ON bqc_phase_error_patterns(lottery_match_id, version_tag);",
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


def safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value or ""):
        raise ValueError(f"unsafe table name: {value!r}")
    return value


def to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_spf(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return SPF_TO_CODE.get(text, SPF_TO_CODE.get(text.lower(), text))


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


def bqc_display(code: str) -> str:
    return BQC_CODE_TO_CN.get(code, code)


def active_bqc_from_report(report: Dict[str, Any]) -> str:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    bqc = plays.get("bqc") if isinstance(plays.get("bqc"), dict) else {}
    return normalize_bqc(bqc.get("recommendation_cn") or bqc.get("recommendation"))


def active_spf_from_report(report: Dict[str, Any]) -> str:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    spf = plays.get("spf") if isinstance(plays.get("spf"), dict) else {}
    final = report.get("final_prediction") if isinstance(report.get("final_prediction"), dict) else {}
    return normalize_spf(
        spf.get("direction")
        or spf.get("direction_cn")
        or spf.get("recommendation_cn")
        or spf.get("recommendation")
        or final.get("predicted_result")
    )


def choose_fact_table(conn: sqlite3.Connection, requested: str) -> str:
    if requested:
        table = safe_identifier(requested)
        if table_exists(conn, table):
            return table
        return table
    candidate = "team_match_facts_candidate_full_20260624"
    if table_exists(conn, candidate):
        return candidate
    return "team_match_facts"


def ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_PROFILE_SQL)
    conn.execute(CREATE_AUDIT_SQL)
    conn.execute(CREATE_PATTERN_SQL)
    for statement in INDEX_SQL:
        conn.execute(statement)


def target_matches(conn: sqlite3.Connection, args: argparse.Namespace) -> List[sqlite3.Row]:
    report_cols = table_columns(conn, "lottery_analysis_reports")
    stale_filter = "AND COALESCE(ar2.is_stale, 0) = 0" if "is_stale" in report_cols else ""
    where = [
        "substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?",
        "lm.home_team_id IS NOT NULL",
        "lm.away_team_id IS NOT NULL",
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
    if args.finished_only:
        where.append("lr.home_goals_ft IS NOT NULL")
        where.append("lr.away_goals_ft IS NOT NULL")
    if args.limit:
        params.append(args.limit)
    limit_sql = " LIMIT ?" if args.limit else ""
    return conn.execute(
        f"""
        SELECT lm.lottery_match_id, lm.match_id, lm.match_num,
               substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) AS match_date,
               lm.match_time, lm.league_name_cn,
               lm.home_team_id, lm.away_team_id, lm.home_team_cn, lm.away_team_cn,
               lr.home_goals_ft, lr.away_goals_ft, lr.home_goals_ht, lr.away_goals_ht,
               lr.bqc_result,
               ar.report_id, ar.report_data, ar.created_at AS report_created_at
        FROM lottery_matches lm
        LEFT JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
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


def half_profile(
    conn: sqlite3.Connection,
    fact_table: str,
    team_id: Any,
    target_date: str,
    sample_limit: int,
) -> Dict[str, Any]:
    table = safe_identifier(fact_table)
    if team_id in (None, "") or not table_exists(conn, table):
        return {"sample_size": 0}
    cols = table_columns(conn, table)
    required = {"team_id", "match_date", "goals_ht_for", "goals_ht_against"}
    if not required.issubset(cols):
        return {"sample_size": 0, "missing_columns": sorted(required - cols)}

    rows = conn.execute(
        f"""
        SELECT COUNT(*) AS sample_size,
               MIN(match_date) AS source_window_start,
               MAX(match_date) AS source_window_end,
               AVG(goals_ht_for * 1.0) AS ht_goals_for_avg,
               AVG(goals_ht_against * 1.0) AS ht_goals_against_avg,
               AVG((goals_ht_for + goals_ht_against) * 1.0) AS ht_total_goals_avg,
               AVG(CASE WHEN goals_ht_for > 0 THEN 1.0 ELSE 0.0 END) AS ht_score_rate,
               AVG(CASE WHEN goals_ht_against > 0 THEN 1.0 ELSE 0.0 END) AS ht_concede_rate,
               AVG(CASE WHEN goals_ht_for = 0 AND goals_ht_against = 0 THEN 1.0 ELSE 0.0 END) AS ht_zero_zero_rate,
               AVG(CASE WHEN goals_ht_for + goals_ht_against <= 1 THEN 1.0 ELSE 0.0 END) AS ht_under_1_5_rate,
               AVG(CASE WHEN goals_ht_for > goals_ht_against THEN 1.0 ELSE 0.0 END) AS ht_win_rate,
               AVG(CASE WHEN goals_ht_for = goals_ht_against THEN 1.0 ELSE 0.0 END) AS ht_draw_rate,
               AVG(CASE WHEN goals_ht_for < goals_ht_against THEN 1.0 ELSE 0.0 END) AS ht_loss_rate
        FROM (
            SELECT substr(match_date, 1, 10) AS match_date,
                   COALESCE(opponent_team_id, '') AS opponent_team_id,
                   goals_for, goals_against, goals_ht_for, goals_ht_against
            FROM {table}
            WHERE CAST(team_id AS TEXT) = CAST(? AS TEXT)
              AND date(substr(match_date, 1, 10)) < date(?)
              AND goals_ht_for IS NOT NULL
              AND goals_ht_against IS NOT NULL
            GROUP BY substr(match_date, 1, 10), COALESCE(opponent_team_id, ''),
                     goals_for, goals_against, goals_ht_for, goals_ht_against
            ORDER BY date(substr(match_date, 1, 10)) DESC
            LIMIT ?
        )
        """,
        (str(team_id), target_date, int(sample_limit)),
    ).fetchone()
    profile = dict(rows) if rows else {"sample_size": 0}
    for key, value in list(profile.items()):
        if key == "sample_size":
            profile[key] = int(value or 0)
        elif key not in {"source_window_start", "source_window_end", "missing_columns"}:
            profile[key] = round(float(value), 4) if value is not None else None
    return profile


def avg(*values: Optional[float]) -> Optional[float]:
    usable = [float(v) for v in values if v is not None]
    if not usable:
        return None
    return sum(usable) / len(usable)


def profile_signal(
    home: Dict[str, Any],
    away: Dict[str, Any],
    *,
    min_sample: int,
    draw_edge: float,
    draw_threshold: float,
    max_draw_edge: float,
) -> Dict[str, Any]:
    home_n = int(home.get("sample_size") or 0)
    away_n = int(away.get("sample_size") or 0)
    if min(home_n, away_n) < min_sample:
        return {
            "eligible": False,
            "reason": "sample_below_minimum",
            "home_sample": home_n,
            "away_sample": away_n,
            "min_sample": min_sample,
        }

    home_ht_goal_rate = avg(to_float(home.get("ht_score_rate")), to_float(away.get("ht_concede_rate")))
    away_ht_goal_rate = avg(to_float(away.get("ht_score_rate")), to_float(home.get("ht_concede_rate")))
    zero_zero_rate = avg(to_float(home.get("ht_zero_zero_rate")), to_float(away.get("ht_zero_zero_rate")))
    under_1_5_rate = avg(to_float(home.get("ht_under_1_5_rate")), to_float(away.get("ht_under_1_5_rate")))
    draw_rate = avg(to_float(home.get("ht_draw_rate")), to_float(away.get("ht_draw_rate")))

    if home_ht_goal_rate is None or away_ht_goal_rate is None:
        return {"eligible": False, "reason": "missing_goal_rates", "home_sample": home_n, "away_sample": away_n}

    edge = home_ht_goal_rate - away_ht_goal_rate
    draw_pressure = (
        0.45 * (zero_zero_rate or 0.0)
        + 0.35 * (draw_rate or 0.0)
        + 0.20 * (under_1_5_rate or 0.0)
    )
    if abs(edge) <= draw_edge or (draw_pressure >= draw_threshold and abs(edge) <= max_draw_edge):
        half_axis = "1"
        reason = "draw_tempo_profile"
    elif edge > 0:
        half_axis = "3"
        reason = "home_first_half_edge"
    else:
        half_axis = "0"
        reason = "away_first_half_edge"

    confidence = 0.45 + min(abs(edge), 0.45) * 0.7 + min(min(home_n, away_n), 40) / 40 * 0.10
    if half_axis == "1":
        confidence += max(0.0, draw_pressure - 0.50) * 0.35
    confidence = max(0.0, min(0.82, confidence))

    return {
        "eligible": True,
        "half_axis": half_axis,
        "reason": reason,
        "confidence": round(confidence, 4),
        "home_sample": home_n,
        "away_sample": away_n,
        "home_ht_goal_rate": round(home_ht_goal_rate, 4),
        "away_ht_goal_rate": round(away_ht_goal_rate, 4),
        "edge": round(edge, 4),
        "zero_zero_rate": round(zero_zero_rate or 0.0, 4),
        "under_1_5_rate": round(under_1_5_rate or 0.0, 4),
        "draw_rate": round(draw_rate or 0.0, 4),
        "draw_pressure": round(draw_pressure, 4),
    }


def save_profile_row(
    conn: sqlite3.Connection,
    *,
    row: sqlite3.Row,
    side: str,
    profile: Dict[str, Any],
    fact_table: str,
    sample_limit: int,
    version_tag: str,
) -> None:
    is_home = side == "home"
    team_id = row["home_team_id"] if is_home else row["away_team_id"]
    opponent_team_id = row["away_team_id"] if is_home else row["home_team_id"]
    team_name = row["home_team_cn"] if is_home else row["away_team_cn"]
    opponent_name = row["away_team_cn"] if is_home else row["home_team_cn"]
    conn.execute(
        """
        INSERT OR REPLACE INTO bqc_half_time_profiles (
            profile_id, lottery_match_id, match_date, team_side, team_id, opponent_team_id,
            team_name, opponent_name, fact_table, version_tag, sample_limit, sample_size,
            source_window_start, source_window_end, ht_goals_for_avg, ht_goals_against_avg,
            ht_total_goals_avg, ht_score_rate, ht_concede_rate, ht_zero_zero_rate,
            ht_under_1_5_rate, ht_win_rate, ht_draw_rate, ht_loss_rate,
            profile_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            compact_id("bqchtp", row["lottery_match_id"], side, version_tag),
            str(row["lottery_match_id"]),
            row["match_date"],
            side,
            None if team_id is None else str(team_id),
            None if opponent_team_id is None else str(opponent_team_id),
            team_name,
            opponent_name,
            fact_table,
            version_tag,
            sample_limit,
            int(profile.get("sample_size") or 0),
            profile.get("source_window_start"),
            profile.get("source_window_end"),
            profile.get("ht_goals_for_avg"),
            profile.get("ht_goals_against_avg"),
            profile.get("ht_total_goals_avg"),
            profile.get("ht_score_rate"),
            profile.get("ht_concede_rate"),
            profile.get("ht_zero_zero_rate"),
            profile.get("ht_under_1_5_rate"),
            profile.get("ht_win_rate"),
            profile.get("ht_draw_rate"),
            profile.get("ht_loss_rate"),
            dumps_json(profile),
        ),
    )


def build_item(row: sqlite3.Row, home_profile: Dict[str, Any], away_profile: Dict[str, Any], signal: Dict[str, Any]) -> Dict[str, Any]:
    report = loads_json(row["report_data"], {})
    current_bqc = active_bqc_from_report(report)
    spf_axis = active_spf_from_report(report)
    current_full_axis = current_bqc[1] if len(current_bqc) == 2 and current_bqc[1] in {"3", "1", "0"} else ""
    full_axis = current_full_axis or (spf_axis if spf_axis in {"3", "1", "0"} else "")
    profile_bqc = ""
    if signal.get("eligible") and signal.get("half_axis") in {"3", "1", "0"} and full_axis:
        profile_bqc = f"{signal['half_axis']}{full_axis}"

    actual_bqc = normalize_bqc(row["bqc_result"])
    current_correct = current_bqc == actual_bqc if current_bqc and actual_bqc else None
    profile_correct = profile_bqc == actual_bqc if profile_bqc and actual_bqc else None
    return {
        "lottery_match_id": str(row["lottery_match_id"]),
        "report_id": row["report_id"],
        "match_date": row["match_date"],
        "match_num": row["match_num"],
        "league_name_cn": row["league_name_cn"],
        "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
        "score": (
            f"{row['home_goals_ft']}:{row['away_goals_ft']}"
            if row["home_goals_ft"] is not None and row["away_goals_ft"] is not None
            else None
        ),
        "half_score": (
            f"{row['home_goals_ht']}:{row['away_goals_ht']}"
            if row["home_goals_ht"] is not None and row["away_goals_ht"] is not None
            else None
        ),
        "current_bqc": current_bqc,
        "current_bqc_cn": bqc_display(current_bqc),
        "profile_bqc": profile_bqc,
        "profile_bqc_cn": bqc_display(profile_bqc),
        "actual_bqc": actual_bqc,
        "actual_bqc_cn": bqc_display(actual_bqc),
        "current_correct": current_correct,
        "profile_correct": profile_correct,
        "changed": bool(profile_bqc and current_bqc and profile_bqc != current_bqc),
        "full_axis_source": "current_bqc" if current_full_axis else ("spf_axis" if full_axis else "missing"),
        "signal": signal,
        "home_profile": home_profile,
        "away_profile": away_profile,
    }


def bqc_leg(code: Any, index: int) -> str:
    text = normalize_bqc(code)
    if len(text) == 2 and set(text) <= {"0", "1", "3"}:
        return text[index]
    return ""


def classify_bqc_pattern(item: Dict[str, Any]) -> Dict[str, Any]:
    current = normalize_bqc(item.get("current_bqc"))
    profile = normalize_bqc(item.get("profile_bqc"))
    actual = normalize_bqc(item.get("actual_bqc"))
    signal = item.get("signal") if isinstance(item.get("signal"), dict) else {}
    current_half = bqc_leg(current, 0)
    current_full = bqc_leg(current, 1)
    profile_half = bqc_leg(profile, 0)
    profile_full = bqc_leg(profile, 1)
    actual_half = bqc_leg(actual, 0)
    actual_full = bqc_leg(actual, 1)

    current_correct = current == actual if current and actual else None
    profile_correct = profile == actual if profile and actual else None
    half_axis_error = bool(current_half and actual_half and current_half != actual_half)
    full_axis_error = bool(current_full and actual_full and current_full != actual_full)
    path_flip = bool(actual_half and actual_full and actual_half != actual_full)

    if not actual:
        pattern_type = "unscored"
    elif current_correct:
        pattern_type = "positive_case"
    elif profile_correct:
        pattern_type = "profile_helped"
    elif full_axis_error:
        pattern_type = "full_time_axis_miss"
    elif half_axis_error:
        pattern_type = "half_time_axis_miss"
    else:
        pattern_type = "unclassified_bqc_miss"

    changed = bool(profile and current and profile != current)
    if not profile:
        profile_role = "no_candidate"
    elif profile_correct is True and current_correct is False:
        profile_role = "helped"
    elif profile_correct is False and current_correct is True:
        profile_role = "regressed"
    elif not changed:
        profile_role = "same_as_current"
    else:
        profile_role = "changed_no_gain"

    tags: List[str] = []
    if path_flip:
        tags.append("actual_half_full_flip")
    if actual_half == "1":
        tags.append("actual_half_draw")
    if current_half == "1" and actual_half and actual_half != "1":
        tags.append("false_half_draw")
    if current_half and current_half != "1" and actual_half == "1":
        tags.append("missed_half_draw")
    if signal.get("reason") == "draw_tempo_profile" and actual_half and actual_half != "1":
        tags.append("draw_profile_false_positive")
    if signal.get("reason") in {"home_first_half_edge", "away_first_half_edge"} and actual_half == "1":
        tags.append("edge_profile_missed_draw")
    if full_axis_error:
        tags.append("not_solved_by_half_profile")

    if pattern_type == "full_time_axis_miss":
        takeaway = "BQC error mainly follows full-time axis; fix SPF/score/full-time path before half-time profile."
    elif pattern_type == "half_time_axis_miss":
        takeaway = "Full-time leg was right but first-half leg was wrong; improve half-time tempo and early-goal profile."
    elif profile_role == "regressed":
        takeaway = "Half-time profile is noisy for this shape; use as risk evidence, not direct replacement."
    elif profile_role == "helped":
        takeaway = "Half-time profile can help this shape; collect more similar cases before gating."
    elif pattern_type == "positive_case":
        takeaway = "Keep as positive BQC path sample."
    else:
        takeaway = "Needs similar-case review before model action."

    return {
        "pattern_type": pattern_type,
        "profile_role": profile_role,
        "half_axis_error": half_axis_error,
        "full_axis_error": full_axis_error,
        "path_flip": path_flip,
        "signal_reason": signal.get("reason"),
        "signal_confidence": to_float(signal.get("confidence"), None),
        "tags": tags,
        "takeaway": takeaway,
        "legs": {
            "current_half": current_half,
            "current_full": current_full,
            "profile_half": profile_half,
            "profile_full": profile_full,
            "actual_half": actual_half,
            "actual_full": actual_full,
        },
    }


def save_audit_row(conn: sqlite3.Connection, row: sqlite3.Row, item: Dict[str, Any], version_tag: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO bqc_half_time_profile_audits (
            audit_id, lottery_match_id, report_id, match_date, match_num, league_name_cn,
            home_team_cn, away_team_cn, current_bqc, profile_bqc, actual_bqc,
            current_correct, profile_correct, changed, signal_json, version_tag, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            compact_id("bqchta", row["lottery_match_id"], version_tag),
            str(row["lottery_match_id"]),
            row["report_id"],
            row["match_date"],
            row["match_num"],
            row["league_name_cn"],
            row["home_team_cn"],
            row["away_team_cn"],
            item.get("current_bqc"),
            item.get("profile_bqc"),
            item.get("actual_bqc"),
            None if item.get("current_correct") is None else int(bool(item.get("current_correct"))),
            None if item.get("profile_correct") is None else int(bool(item.get("profile_correct"))),
            int(bool(item.get("changed"))),
            dumps_json({
                "signal": item.get("signal"),
                "full_axis_source": item.get("full_axis_source"),
                "score": item.get("score"),
                "half_score": item.get("half_score"),
                "current_bqc_cn": item.get("current_bqc_cn"),
                "profile_bqc_cn": item.get("profile_bqc_cn"),
                "actual_bqc_cn": item.get("actual_bqc_cn"),
            }),
            version_tag,
        ),
    )


def save_pattern_row(conn: sqlite3.Connection, row: sqlite3.Row, item: Dict[str, Any], pattern: Dict[str, Any], version_tag: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO bqc_phase_error_patterns (
            pattern_id, lottery_match_id, report_id, match_date, match_num, league_name_cn,
            pattern_type, profile_role, half_axis_error, full_axis_error, path_flip,
            current_bqc, profile_bqc, actual_bqc, signal_reason, signal_confidence,
            notes_json, version_tag, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            compact_id("bqcpat", row["lottery_match_id"], version_tag),
            str(row["lottery_match_id"]),
            row["report_id"],
            row["match_date"],
            row["match_num"],
            row["league_name_cn"],
            pattern.get("pattern_type"),
            pattern.get("profile_role"),
            int(bool(pattern.get("half_axis_error"))),
            int(bool(pattern.get("full_axis_error"))),
            int(bool(pattern.get("path_flip"))),
            item.get("current_bqc"),
            item.get("profile_bqc"),
            item.get("actual_bqc"),
            pattern.get("signal_reason"),
            pattern.get("signal_confidence"),
            dumps_json({
                "teams": item.get("teams"),
                "score": item.get("score"),
                "half_score": item.get("half_score"),
                "tags": pattern.get("tags") or [],
                "takeaway": pattern.get("takeaway"),
                "legs": pattern.get("legs") or {},
                "current_bqc_cn": item.get("current_bqc_cn"),
                "profile_bqc_cn": item.get("profile_bqc_cn"),
                "actual_bqc_cn": item.get("actual_bqc_cn"),
            }),
            version_tag,
        ),
    )


def summarize(items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    scored = [item for item in items if item.get("actual_bqc")]
    profile_scored = [item for item in scored if item.get("profile_correct") is not None]
    changed = [item for item in profile_scored if item.get("changed")]
    current_correct = sum(1 for item in profile_scored if item.get("current_correct") is True)
    profile_correct = sum(1 for item in profile_scored if item.get("profile_correct") is True)
    changed_improved = sum(1 for item in changed if item.get("current_correct") is False and item.get("profile_correct") is True)
    changed_regressed = sum(1 for item in changed if item.get("current_correct") is True and item.get("profile_correct") is False)
    reasons: Dict[str, int] = {}
    patterns: Dict[str, int] = {}
    profile_roles: Dict[str, int] = {}
    half_axis_errors = 0
    full_axis_errors = 0
    path_flips = 0
    for item in items:
        reason = str((item.get("signal") or {}).get("reason") or "unknown")
        reasons[reason] = reasons.get(reason, 0) + 1
        pattern = classify_bqc_pattern(item)
        pattern_type = str(pattern.get("pattern_type") or "unknown")
        profile_role = str(pattern.get("profile_role") or "unknown")
        patterns[pattern_type] = patterns.get(pattern_type, 0) + 1
        profile_roles[profile_role] = profile_roles.get(profile_role, 0) + 1
        half_axis_errors += int(bool(pattern.get("half_axis_error")))
        full_axis_errors += int(bool(pattern.get("full_axis_error")))
        path_flips += int(bool(pattern.get("path_flip")))
    return {
        "targets": len(items),
        "scored_matches": len(profile_scored),
        "eligible": sum(1 for item in items if (item.get("signal") or {}).get("eligible")),
        "changed_candidates": len(changed),
        "current_correct": current_correct,
        "profile_correct": profile_correct,
        "delta_correct": profile_correct - current_correct,
        "changed_improved": changed_improved,
        "changed_regressed": changed_regressed,
        "accuracy_current": round(current_correct * 100 / len(profile_scored), 1) if profile_scored else 0,
        "accuracy_profile": round(profile_correct * 100 / len(profile_scored), 1) if profile_scored else 0,
        "half_axis_errors": half_axis_errors,
        "full_axis_errors": full_axis_errors,
        "path_flips": path_flips,
        "patterns": sorted(patterns.items(), key=lambda pair: (-pair[1], pair[0])),
        "profile_roles": sorted(profile_roles.items(), key=lambda pair: (-pair[1], pair[0])),
        "reasons": sorted(reasons.items(), key=lambda pair: (-pair[1], pair[0])),
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    version_tag = args.version_tag or DEFAULT_VERSION
    with connect(db_path) as conn:
        fact_table = choose_fact_table(conn, args.fact_table)
        if not table_exists(conn, fact_table):
            return {
                "success": True,
                "skipped": True,
                "reason": "fact_table_missing",
                "fact_table": fact_table,
                "summary": {"targets": 0},
            }
        rows = target_matches(conn, args)
        items: List[Dict[str, Any]] = []
        for row in rows:
            home = half_profile(conn, fact_table, row["home_team_id"], row["match_date"], args.sample_limit)
            away = half_profile(conn, fact_table, row["away_team_id"], row["match_date"], args.sample_limit)
            signal = profile_signal(
                home,
                away,
                min_sample=args.min_sample,
                draw_edge=args.draw_edge,
                draw_threshold=args.draw_threshold,
                max_draw_edge=args.max_draw_edge,
            )
            items.append(build_item(row, home, away, signal))

        saved_profiles = 0
        saved_audits = 0
        saved_patterns = 0
        if args.apply:
            ensure_tables(conn)
            for row, item in zip(rows, items):
                save_profile_row(
                    conn,
                    row=row,
                    side="home",
                    profile=item["home_profile"],
                    fact_table=fact_table,
                    sample_limit=args.sample_limit,
                    version_tag=version_tag,
                )
                save_profile_row(
                    conn,
                    row=row,
                    side="away",
                    profile=item["away_profile"],
                    fact_table=fact_table,
                    sample_limit=args.sample_limit,
                    version_tag=version_tag,
                )
                saved_profiles += 2
                if item.get("profile_bqc") or item.get("actual_bqc"):
                    save_audit_row(conn, row, item, version_tag)
                    saved_audits += 1
                    pattern = classify_bqc_pattern(item)
                    save_pattern_row(conn, row, item, pattern, version_tag)
                    saved_patterns += 1
            conn.commit()

    summary = summarize(items)
    examples = [item for item in items if item.get("changed")][: args.examples_limit]
    return {
        "success": True,
        "mode": "apply" if args.apply else "dry_run",
        "version_tag": version_tag,
        "fact_table": fact_table,
        "settings": {
            "date_from": args.date_from,
            "date_to": args.date_to,
            "league": args.league,
            "sample_limit": args.sample_limit,
            "min_sample": args.min_sample,
            "draw_edge": args.draw_edge,
            "draw_threshold": args.draw_threshold,
            "max_draw_edge": args.max_draw_edge,
        },
        "summary": summary,
        "saved_profiles": saved_profiles,
        "saved_audits": saved_audits,
        "saved_patterns": saved_patterns,
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
    parser.add_argument("--fact-table", default="")
    parser.add_argument("--sample-limit", type=int, default=40)
    parser.add_argument("--min-sample", type=int, default=12)
    parser.add_argument("--draw-edge", type=float, default=0.10)
    parser.add_argument("--draw-threshold", type=float, default=0.62)
    parser.add_argument("--max-draw-edge", type=float, default=0.18)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--version-tag", default=DEFAULT_VERSION)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--finished-only", action="store_true", default=True)
    parser.add_argument("--include-unfinished", dest="finished_only", action="store_false")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--examples-limit", type=int, default=8)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    result = run(args)
    if args.summary_only:
        result = {
            "success": result.get("success"),
            "mode": result.get("mode"),
            "version_tag": result.get("version_tag"),
            "fact_table": result.get("fact_table"),
            "settings": result.get("settings"),
            "summary": result.get("summary"),
            "saved_profiles": result.get("saved_profiles"),
            "saved_audits": result.get("saved_audits"),
            "saved_patterns": result.get("saved_patterns"),
            "skipped": result.get("skipped"),
            "reason": result.get("reason"),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("success") is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
