"""Build rule-based similar match cases from feature snapshots and reviews.

This is the first durable version of "seen this market shape before". It uses
simple, explainable features so the result can be audited before adding vector
search or a learned model.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "football_v2.db"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.data_access.foundation_dao import FoundationDAO


PROB_KEYS = ("home_win", "draw", "away_win")
PRESSURE_SCORE = {
    "unknown": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "very_high": 4,
}


def loads(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) and value else default
    except Exception:
        return default


def clean_report_id(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text or text.lower() in {"none", "null", "undefined", "nan"}:
        return None
    return text


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    if not table_exists(conn, table_name):
        return set()
    return {row["name"] for row in conn.execute(f'PRAGMA table_info("{table_name}")')}


def ensure_similar_cases_schema(conn: sqlite3.Connection) -> None:
    if not table_exists(conn, "similar_match_cases"):
        return
    columns = table_columns(conn, "similar_match_cases")
    if "play_type" not in columns:
        conn.execute("ALTER TABLE similar_match_cases ADD COLUMN play_type TEXT")
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_similar_match_cases_play
        ON similar_match_cases(play_type, match_key, similarity_score)
        """
    )
    conn.commit()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def prob_vector(value: Dict[str, Any]) -> Dict[str, float]:
    return {key: safe_float((value or {}).get(key), 0.0) for key in PROB_KEYS}


def prob_distance(a: Dict[str, float], b: Dict[str, float]) -> Optional[float]:
    if not a or not b:
        return None
    if sum(abs(a.get(key, 0.0)) for key in PROB_KEYS) <= 0:
        return None
    if sum(abs(b.get(key, 0.0)) for key in PROB_KEYS) <= 0:
        return None
    return sum(abs(a.get(key, 0.0) - b.get(key, 0.0)) for key in PROB_KEYS) / len(PROB_KEYS)


def market_bucket(probs: Dict[str, float]) -> str:
    favorite = max((probs or {}).values() or [0.0])
    if favorite >= 0.68:
        return "heavy_favorite"
    if favorite >= 0.56:
        return "favorite"
    if favorite >= 0.45:
        return "lean"
    if favorite > 0:
        return "balanced"
    return "unknown"


def ou_direction(ou: Dict[str, Any], final: Dict[str, Any]) -> str:
    rec = str((ou or {}).get("recommendation") or "").lower()
    if "大" in rec or "over" in rec:
        return "over"
    if "小" in rec or "under" in rec:
        return "under"
    final_ou = (final or {}).get("over_under_2_5") or {}
    over = safe_float(final_ou.get("over"), 0.0)
    under = safe_float(final_ou.get("under"), 0.0)
    if over > under:
        return "over"
    if under > over:
        return "under"
    return "unknown"


def ou_side_from_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    if "大" in text or "over" in text:
        return "over"
    if "小" in text or "under" in text:
        return "under"
    return "unknown"


def pressure_value(value: Any) -> int:
    return PRESSURE_SCORE.get(str(value or "unknown"), 0)


def closeness(gap: float, max_gap: float) -> float:
    if max_gap <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - abs(gap) / max_gap))


def latest_feature_rows(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT match_key, feature_json, model_version, source_report_id, snapshot_time
        FROM match_feature_snapshots
        ORDER BY snapshot_time DESC, CAST(source_report_id AS INTEGER) DESC, rowid DESC
        """
    ).fetchall()
    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if row["match_key"] not in result:
            result[row["match_key"]] = dict(row)
    return result


def latest_context_indexes(
    conn: sqlite3.Connection,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[Tuple[str, str], Dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT match_key, competition_context_json, odds_context_json,
               intel_context_json, data_quality_json, snapshot_time
        FROM match_context_snapshots
        ORDER BY snapshot_time DESC, rowid DESC
        """
    ).fetchall()
    by_match: Dict[str, Dict[str, Any]] = {}
    by_report: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        match_key = str(row["match_key"])
        quality = loads(row["data_quality_json"], {})
        report_id = clean_report_id(quality.get("source_report_id"))
        item["source_report_id"] = report_id
        if match_key not in by_match:
            by_match[match_key] = item
        if report_id and (match_key, report_id) not in by_report:
            by_report[(match_key, report_id)] = item
    return by_match, by_report


def review_rows(conn: sqlite3.Connection, play_type: str) -> Dict[str, Dict[str, Any]]:
    rows = []
    if table_exists(conn, "post_match_reviews"):
        rows = conn.execute(
            """
            SELECT match_key, play_type, predicted_result, actual_result,
                   is_correct, attribution, review_json
            FROM post_match_reviews
            WHERE play_type = ?
            """,
            (play_type,),
        ).fetchall()
    if rows:
        return {row["match_key"]: dict(row) for row in rows}

    # Cloud deployments may already have lottery_validation while durable
    # post_match_reviews is new. Use validation as a real reviewed reference.
    if not table_exists(conn, "lottery_validation"):
        return {}

    rows = conn.execute(
        """
        SELECT lottery_match_id AS match_key, play_type, predicted_result,
               actual_result, is_correct, attribution, attribution_detail,
               brier_score, predicted_prob, scenario_type, actionable, validated_at
        FROM lottery_validation
        WHERE play_type = ?
        """,
        (play_type,),
    ).fetchall()
    reviews: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        item["review_json"] = json.dumps({
            "validation": {
                "lottery_match_id": item.get("match_key"),
                "play_type": item.get("play_type"),
                "predicted_result": item.get("predicted_result"),
                "actual_result": item.get("actual_result"),
                "is_correct": item.get("is_correct"),
                "predicted_prob": item.get("predicted_prob"),
                "brier_score": item.get("brier_score"),
                "scenario_type": item.get("scenario_type"),
                "validated_at": item.get("validated_at"),
            },
            "attribution": {
                "level": item.get("attribution"),
                "detail": item.get("attribution_detail"),
                "actionable": item.get("actionable"),
            },
            "source": "lottery_validation_fallback",
        }, ensure_ascii=False, default=str)
        reviews[item["match_key"]] = item
    return reviews


def _infer_case_play_type(row: sqlite3.Row) -> str:
    if "play_type" in row.keys() and row["play_type"]:
        return str(row["play_type"])
    similarity = loads(row["similarity_json"], {})
    outcome = loads(row["outcome_json"], {})
    return str(
        outcome.get("play_type")
        or similarity.get("play_type")
        or "unknown"
    )


def clear_existing_cases(db_path: Path, match_keys: List[str], play_type: str) -> int:
    if not match_keys:
        return 0
    deleted = 0
    conn = connect(db_path)
    try:
        ensure_similar_cases_schema(conn)
        for start in range(0, len(match_keys), 200):
            chunk = match_keys[start:start + 200]
            placeholders = ",".join(["?"] * len(chunk))
            rows = conn.execute(
                f"""
                SELECT case_id, play_type, similarity_json, outcome_json
                FROM similar_match_cases
                WHERE match_key IN ({placeholders})
                """,
                chunk,
            ).fetchall()
            case_ids = [
                row["case_id"]
                for row in rows
                if _infer_case_play_type(row) == play_type
            ]
            if not case_ids:
                continue
            id_placeholders = ",".join(["?"] * len(case_ids))
            cursor = conn.execute(
                f"DELETE FROM similar_match_cases WHERE case_id IN ({id_placeholders})",
                case_ids,
            )
            deleted += cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
        conn.commit()
    finally:
        conn.close()
    return deleted


def vector(feature_row: Dict[str, Any], context_row: Dict[str, Any]) -> Dict[str, Any]:
    features = loads(feature_row.get("feature_json"), {})
    context = loads(context_row.get("competition_context_json"), {}) if context_row else {}
    odds = loads(context_row.get("odds_context_json"), {}) if context_row else {}
    intel = loads(context_row.get("intel_context_json"), {}) if context_row else {}
    quality = loads(context_row.get("data_quality_json"), {}) if context_row else {}

    final = features.get("final_prediction", {}) or {}
    probs = prob_vector(final.get("probabilities", {}) or {})
    play_predictions = features.get("play_predictions", {}) or {}
    odds_play_predictions = odds.get("play_predictions", {}) or {}
    spf = play_predictions.get("spf", {}) or odds_play_predictions.get("spf", {}) or {}
    rqspf = play_predictions.get("rqspf", {}) or odds_play_predictions.get("rqspf", {}) or {}
    ou = play_predictions.get("ou", {}) or odds_play_predictions.get("ou", {}) or {}
    ou_diagnostics = ou.get("diagnostics") if isinstance(ou.get("diagnostics"), dict) else {}
    goal_axis = ou.get("goal_axis") if isinstance(ou.get("goal_axis"), dict) else {}
    attack_defense = (
        goal_axis.get("attack_defense_profile")
        if isinstance(goal_axis.get("attack_defense_profile"), dict)
        else {}
    )
    model_vs_odds = features.get("model_vs_odds", {}) or odds.get("model_vs_odds", {}) or {}
    match = context.get("match", {}) or {}
    profile = context.get("profile", {}) or {}
    odds_probs = prob_vector(odds.get("odds_baseline", {}) or {})
    expected_score = final.get("expected_score") or {}
    wc = context.get("world_cup_2026") or {}
    wc_stage = wc.get("group_stage_context") or {}
    wc_pressure = wc.get("pressure") or {}
    home_pressure = wc_pressure.get("home") or {}
    away_pressure = wc_pressure.get("away") or {}
    group = wc.get("group") or {}
    intel_missing = intel.get("missing_required") or []
    if not isinstance(intel_missing, list):
        intel_missing = []
    intel_completeness = safe_float(intel.get("completeness"), 0.0)
    strict_completeness = safe_float(intel.get("strict_completeness"), 0.0)
    has_world_cup = bool(wc) or "世界杯" in str(match.get("league_name_cn") or "").lower()

    return {
        "probabilities": probs,
        "odds_probabilities": odds_probs,
        "market_bucket": market_bucket(odds_probs),
        "model_bucket": market_bucket(probs),
        "predicted_result": final.get("predicted_result") or spf.get("direction"),
        "spf_direction": spf.get("direction"),
        "rqspf_direction": rqspf.get("direction"),
        "handicap": safe_float(rqspf.get("handicap", match.get("handicap_line") or 0), 0.0),
        "league_name": match.get("league_name_cn") or "",
        "competition_type": profile.get("competition_type") or "",
        "participant_type": profile.get("participant_type") or "",
        "odds_rec": model_vs_odds.get("odds_rec"),
        "model_rec": model_vs_odds.get("model_rec"),
        "agreement": model_vs_odds.get("agreement"),
        "confidence": safe_float(final.get("confidence"), 0.0),
        "expected_total": safe_float(expected_score.get("home"), 0.0) + safe_float(expected_score.get("away"), 0.0),
        "ou_direction": ou_direction(ou, final),
        "ou_line": safe_float(ou.get("best_line", ou.get("line")), 0.0),
        "goal_axis_side": goal_axis.get("side") or ou_side_from_text(ou.get("recommendation")),
        "goal_axis_confidence": safe_float(goal_axis.get("confidence_score"), 0.0),
        "goal_axis_probability_gap": safe_float(goal_axis.get("probability_gap"), 0.0),
        "goal_axis_line_gap": safe_float(goal_axis.get("line_gap"), 0.0),
        "goal_axis_market_alignment": goal_axis.get("market_alignment") or ou_diagnostics.get("market_alignment"),
        "goal_axis_risk_level": goal_axis.get("risk_level"),
        "home_goal_probability": safe_float(
            ou_diagnostics.get("home_goal_probability")
            or attack_defense.get("home_score_signal"),
            0.0,
        ),
        "away_goal_probability": safe_float(
            ou_diagnostics.get("away_goal_probability")
            or attack_defense.get("away_score_signal"),
            0.0,
        ),
        "btts_probability": safe_float(ou_diagnostics.get("both_teams_score_probability"), 0.0),
        "is_world_cup": has_world_cup,
        "wc_group": wc_stage.get("group") or group.get("group"),
        "wc_matchday": safe_int(wc_stage.get("matchday"), 0),
        "wc_group_finished": safe_int(wc_stage.get("group_matches_finished") or group.get("matches_finished"), 0),
        "wc_home_points": safe_int(home_pressure.get("points"), 0),
        "wc_away_points": safe_int(away_pressure.get("points"), 0),
        "wc_home_position": safe_int(home_pressure.get("current_position"), 0),
        "wc_away_position": safe_int(away_pressure.get("current_position"), 0),
        "wc_home_pressure": home_pressure.get("level") or "unknown",
        "wc_away_pressure": away_pressure.get("level") or "unknown",
        "wc_home_qualification": home_pressure.get("current_qualification") or "unknown",
        "wc_away_qualification": away_pressure.get("current_qualification") or "unknown",
        "intel_completeness": intel_completeness,
        "strict_completeness": strict_completeness,
        "missing_required": sorted(str(item) for item in intel_missing),
        "quality_flags": {key: bool(value) for key, value in (quality or {}).items() if key.startswith("has_")},
    }


def category(vec: Dict[str, Any]) -> str:
    if vec.get("is_world_cup"):
        return "world_cup"
    text = f"{vec.get('league_name', '')} {vec.get('competition_type', '')}".lower()
    if "world cup" in text or "世界杯" in text:
        return "world_cup"
    if "friendly" in text or "友谊" in text:
        return "friendly_intl"
    if "国际" in text or "national" in str(vec.get("participant_type", "")).lower():
        return "national"
    return vec.get("competition_type") or "league"


def similarity(a: Dict[str, Any], b: Dict[str, Any], play_type: str = "spf") -> Tuple[float, Dict[str, Any]]:
    prob_diff = prob_distance(a["probabilities"], b["probabilities"]) or 1.0
    odds_diff = prob_distance(a.get("odds_probabilities", {}), b.get("odds_probabilities", {}))
    expected_total_gap = abs(a.get("expected_total", 0.0) - b.get("expected_total", 0.0))
    confidence_gap = abs(a.get("confidence", 0.0) - b.get("confidence", 0.0))
    ou_line_gap = abs(a.get("ou_line", 0.0) - b.get("ou_line", 0.0))
    goal_axis_confidence_gap = abs(a.get("goal_axis_confidence", 0.0) - b.get("goal_axis_confidence", 0.0))
    goal_axis_line_gap_delta = abs(a.get("goal_axis_line_gap", 0.0) - b.get("goal_axis_line_gap", 0.0))
    home_goal_gap = abs(a.get("home_goal_probability", 0.0) - b.get("home_goal_probability", 0.0))
    away_goal_gap = abs(a.get("away_goal_probability", 0.0) - b.get("away_goal_probability", 0.0))
    btts_gap = abs(a.get("btts_probability", 0.0) - b.get("btts_probability", 0.0))
    home_pressure_gap = abs(pressure_value(a.get("wc_home_pressure")) - pressure_value(b.get("wc_home_pressure")))
    away_pressure_gap = abs(pressure_value(a.get("wc_away_pressure")) - pressure_value(b.get("wc_away_pressure")))
    pressure_gap = home_pressure_gap + away_pressure_gap
    matchday_gap = abs(safe_int(a.get("wc_matchday"), 0) - safe_int(b.get("wc_matchday"), 0))
    missing_overlap = sorted(set(a.get("missing_required") or []) & set(b.get("missing_required") or []))
    reasons = {
        "probability_distance": round(prob_diff, 4),
        "odds_probability_distance": None if odds_diff is None else round(odds_diff, 4),
        "same_prediction": a.get("predicted_result") == b.get("predicted_result"),
        "same_spf_direction": a.get("spf_direction") == b.get("spf_direction"),
        "same_category": category(a) == category(b),
        "handicap_gap": round(abs(a.get("handicap", 0) - b.get("handicap", 0)), 3),
        "same_odds_rec": a.get("odds_rec") == b.get("odds_rec"),
        "same_agreement": a.get("agreement") == b.get("agreement"),
        "same_market_bucket": a.get("market_bucket") == b.get("market_bucket"),
        "same_model_bucket": a.get("model_bucket") == b.get("model_bucket"),
        "confidence_gap": round(confidence_gap, 4),
        "expected_total_gap": round(expected_total_gap, 3),
        "ou_line_gap": round(ou_line_gap, 3),
        "same_ou_line": ou_line_gap <= 0.001 and a.get("ou_line", 0.0) > 0,
        "same_ou_direction": a.get("ou_direction") == b.get("ou_direction") and a.get("ou_direction") != "unknown",
        "same_goal_axis_side": a.get("goal_axis_side") == b.get("goal_axis_side") and a.get("goal_axis_side") != "unknown",
        "goal_axis_confidence_gap": round(goal_axis_confidence_gap, 4),
        "goal_axis_line_gap_delta": round(goal_axis_line_gap_delta, 4),
        "same_goal_axis_market_alignment": (
            a.get("goal_axis_market_alignment") == b.get("goal_axis_market_alignment")
            and bool(a.get("goal_axis_market_alignment"))
        ),
        "same_goal_axis_risk_level": (
            a.get("goal_axis_risk_level") == b.get("goal_axis_risk_level")
            and bool(a.get("goal_axis_risk_level"))
        ),
        "home_goal_probability_gap": round(home_goal_gap, 4),
        "away_goal_probability_gap": round(away_goal_gap, 4),
        "btts_probability_gap": round(btts_gap, 4),
        "same_world_cup_context": bool(a.get("is_world_cup")) and bool(b.get("is_world_cup")),
        "wc_matchday_gap": matchday_gap if a.get("is_world_cup") and b.get("is_world_cup") else None,
        "same_wc_pressure_pair": (
            a.get("wc_home_pressure") == b.get("wc_home_pressure")
            and a.get("wc_away_pressure") == b.get("wc_away_pressure")
            and a.get("is_world_cup")
            and b.get("is_world_cup")
        ),
        "wc_pressure_gap": pressure_gap if a.get("is_world_cup") and b.get("is_world_cup") else None,
        "same_wc_qualification_pair": (
            a.get("wc_home_qualification") == b.get("wc_home_qualification")
            and a.get("wc_away_qualification") == b.get("wc_away_qualification")
            and a.get("is_world_cup")
            and b.get("is_world_cup")
        ),
        "intel_completeness_gap": round(abs(a.get("intel_completeness", 0.0) - b.get("intel_completeness", 0.0)), 2),
        "shared_missing_required": missing_overlap[:5],
    }
    model_score = closeness(prob_diff, 0.34)
    odds_score = closeness(odds_diff, 0.30) if odds_diff is not None else 0.5
    direction_score = sum([
        1.0 if reasons["same_prediction"] else 0.0,
        1.0 if reasons["same_spf_direction"] else 0.0,
        1.0 if reasons["same_odds_rec"] else 0.0,
        1.0 if reasons["same_agreement"] else 0.0,
    ]) / 4
    handicap_score = closeness(reasons["handicap_gap"], 2.5)
    known_ou = a.get("ou_direction") != "unknown" and b.get("ou_direction") != "unknown"
    market_items = [
        1.0 if reasons["same_market_bucket"] else 0.0,
        1.0 if reasons["same_model_bucket"] else 0.0,
    ]
    if known_ou:
        market_items.append(1.0 if reasons["same_ou_direction"] else 0.0)
    market_score = sum(market_items) / len(market_items)

    if reasons["same_world_cup_context"]:
        context_score = 0.30
        context_score += 0.22 * closeness(matchday_gap, 2)
        context_score += 0.25 * closeness(pressure_gap, 6)
        context_score += 0.15 if reasons["same_wc_qualification_pair"] else 0.0
        context_score += 0.08 if a.get("wc_group") == b.get("wc_group") and a.get("wc_group") else 0.0
    elif reasons["same_category"]:
        context_score = 0.72
    else:
        context_score = 0.18

    expected_score = closeness(expected_total_gap, 1.8) if a.get("expected_total") and b.get("expected_total") else 0.5
    confidence_score = closeness(confidence_gap, 0.45)
    intel_score = (
        closeness(reasons["intel_completeness_gap"], 40)
        if (a.get("intel_completeness") or b.get("intel_completeness"))
        else 0.5
    )
    secondary_score = (expected_score + confidence_score + intel_score) / 3

    components = {
        "model": model_score,
        "odds": odds_score,
        "direction": direction_score,
        "handicap": handicap_score,
        "market": market_score,
        "context": context_score,
        "secondary": secondary_score,
    }

    if play_type == "ou":
        ou_line_score = closeness(ou_line_gap, 1.0) if a.get("ou_line") and b.get("ou_line") else 0.35
        expected_goal_score = closeness(expected_total_gap, 1.25) if a.get("expected_total") and b.get("expected_total") else 0.45
        goal_axis_side_score = 1.0 if reasons["same_goal_axis_side"] else 0.0
        ou_direction_score = 1.0 if reasons["same_ou_direction"] else 0.0
        goal_axis_shape_score = sum([
            closeness(goal_axis_confidence_gap, 0.35),
            closeness(goal_axis_line_gap_delta, 1.0),
            closeness(home_goal_gap, 0.35) if a.get("home_goal_probability") and b.get("home_goal_probability") else 0.45,
            closeness(away_goal_gap, 0.35) if a.get("away_goal_probability") and b.get("away_goal_probability") else 0.45,
            closeness(btts_gap, 0.35) if a.get("btts_probability") and b.get("btts_probability") else 0.45,
            1.0 if reasons["same_goal_axis_market_alignment"] else 0.0,
            1.0 if reasons["same_goal_axis_risk_level"] else 0.0,
        ]) / 7
        ou_market_score = sum([
            1.0 if reasons["same_market_bucket"] else 0.0,
            1.0 if reasons["same_model_bucket"] else 0.0,
            ou_direction_score,
        ]) / 3
        components = {
            "ou_line": ou_line_score,
            "expected_goals": expected_goal_score,
            "goal_axis_side": goal_axis_side_score,
            "goal_axis_shape": goal_axis_shape_score,
            "ou_market": ou_market_score,
            "odds": odds_score,
            "context": context_score,
            "spf_model_aux": model_score,
        }
        score = (
            0.18 * ou_line_score
            + 0.18 * expected_goal_score
            + 0.18 * goal_axis_side_score
            + 0.18 * goal_axis_shape_score
            + 0.12 * ou_market_score
            + 0.06 * odds_score
            + 0.06 * context_score
            + 0.04 * model_score
        )
    else:
        score = (
            0.24 * model_score
            + 0.18 * odds_score
            + 0.16 * direction_score
            + 0.12 * handicap_score
            + 0.08 * market_score
            + 0.14 * context_score
            + 0.08 * secondary_score
        )
    reasons["component_scores"] = {key: round(value, 4) for key, value in components.items()}

    return round(max(0.0, min(score, 1.0)), 4), reasons


def build_cases(db_path: Path, play_type: str, top_k: int, min_score: float) -> Dict[str, int]:
    dao = FoundationDAO(str(db_path))
    conn = connect(db_path)
    try:
        ensure_similar_cases_schema(conn)
        features = latest_feature_rows(conn)
        contexts_by_match, contexts_by_report = latest_context_indexes(conn)
        reviews = review_rows(conn, play_type)
    finally:
        conn.close()

    contexts = {
        key: contexts_by_report.get((key, clean_report_id(feature.get("source_report_id"))))
        or contexts_by_match.get(key, {})
        for key, feature in features.items()
    }
    vectors = {
        key: vector(feature, contexts.get(key, {}))
        for key, feature in features.items()
    }
    reviewed_vectors = {
        key: vectors[key]
        for key in reviews
        if key in vectors
    }
    cleared = clear_existing_cases(db_path, list(vectors.keys()), play_type)

    written = 0
    targets = 0
    for match_key, vec in vectors.items():
        scored = []
        for case_key, case_vec in reviewed_vectors.items():
            if case_key == match_key:
                continue
            score, reasons = similarity(vec, case_vec, play_type=play_type)
            if score >= min_score:
                scored.append((score, case_key, reasons))
        scored.sort(reverse=True, key=lambda item: item[0])
        if not scored:
            continue
        targets += 1
        for score, case_key, reasons in scored[:top_k]:
            review = reviews[case_key]
            outcome = {
                "play_type": review.get("play_type"),
                "predicted_result": review.get("predicted_result"),
                "actual_result": review.get("actual_result"),
                "is_correct": review.get("is_correct"),
                "attribution": review.get("attribution"),
                "review": loads(review.get("review_json"), {}),
            }
            similarity_json = {
                "method": "rule_v2_context_market",
                "play_type": play_type,
                "reasons": reasons,
                "target_vector": vec,
                "case_vector": reviewed_vectors[case_key],
            }
            if dao.save_similar_case(match_key, case_key, score, similarity_json, outcome, play_type=play_type):
                written += 1

    return {
        "targets_with_cases": targets,
        "cases_written": written,
        "cases_cleared": cleared,
        "reference_reviews": len(reviewed_vectors),
        "feature_snapshots": len(vectors),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build rule-based similar match cases")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to football_v2.db")
    parser.add_argument("--play-type", default="spf", help="Review play type to use as reference. Use comma list or 'all'.")
    parser.add_argument("--top-k", type=int, default=5, help="Similar cases per target match")
    parser.add_argument("--min-score", type=float, default=0.68, help="Minimum similarity score")
    args = parser.parse_args()

    if args.play_type == "all":
        play_types = ["spf", "rqspf", "bqc", "ou", "bf"]
    else:
        play_types = [item.strip() for item in str(args.play_type).split(",") if item.strip()]

    summary = {
        play_type: build_cases(Path(args.db), play_type, args.top_k, args.min_score)
        for play_type in play_types
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
