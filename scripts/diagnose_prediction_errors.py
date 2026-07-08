"""Diagnose prediction errors into missing factors and next collection actions.

This script does not use final scores to re-predict a match. Final scores are
used only after the fact to explain which pre-match assumptions failed and what
data/model axis should be improved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PLAY_LABELS = {
    "spf": "胜平负",
    "rqspf": "让球胜平负",
    "bqc": "半全场",
    "ou": "大小球",
    "bf": "比分",
}

CN_TO_CODE = {
    "主胜": "3",
    "胜": "3",
    "平局": "1",
    "平": "1",
    "客胜": "0",
    "负": "0",
    "让胜": "3",
    "让平": "1",
    "让负": "0",
}

BQC_TO_CODE = {
    "hh": "33",
    "hd": "31",
    "ha": "30",
    "dh": "13",
    "dd": "11",
    "da": "10",
    "ah": "03",
    "ad": "01",
    "aa": "00",
    "\u80dc\u80dc": "33",
    "\u80dc\u5e73": "31",
    "\u80dc\u8d1f": "30",
    "\u5e73\u80dc": "13",
    "\u5e73\u5e73": "11",
    "\u5e73\u8d1f": "10",
    "\u8d1f\u80dc": "03",
    "\u8d1f\u5e73": "01",
    "\u8d1f\u8d1f": "00",
}

RESULT_CODE_TO_CN = {
    "3": "\u4e3b\u80dc",
    "1": "\u5e73\u5c40",
    "0": "\u5ba2\u80dc",
}

HANDICAP_CODE_TO_CN = {
    "3": "\u8ba9\u80dc",
    "1": "\u8ba9\u5e73",
    "0": "\u8ba9\u8d1f",
}

BQC_CODE_TO_CN = {
    "33": "\u80dc\u80dc",
    "31": "\u80dc\u5e73",
    "30": "\u80dc\u8d1f",
    "13": "\u5e73\u80dc",
    "11": "\u5e73\u5e73",
    "10": "\u5e73\u8d1f",
    "03": "\u8d1f\u80dc",
    "01": "\u8d1f\u5e73",
    "00": "\u8d1f\u8d1f",
}


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> List[str]:
    if not table_exists(conn, table):
        return []
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def placeholders(values: Sequence[Any]) -> str:
    return ",".join(["?"] * len(values))


def loads_json(value: Any, default: Any = None) -> Any:
    if default is None:
        default = {}
    try:
        if isinstance(value, str) and value:
            return json.loads(value)
        if isinstance(value, (dict, list)):
            return value
    except Exception:
        pass
    return default


def compact_id(prefix: str, *parts: Any) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]}"


def normalize_result(value: Any) -> str:
    value = "" if value is None else str(value).strip()
    return CN_TO_CODE.get(value, value)


def normalize_bqc(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in BQC_TO_CODE:
        return BQC_TO_CODE[lowered]
    if text in BQC_TO_CODE:
        return BQC_TO_CODE[text]
    if len(text) == 2 and set(text) <= {"0", "1", "3"}:
        return text
    return text


def ou_side(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if text.startswith("大"):
        return "大"
    if text.startswith("小"):
        return "小"
    if text.startswith("走"):
        return "走"
    return text


def score_text(item: Any) -> Optional[str]:
    if isinstance(item, dict):
        if item.get("score"):
            return str(item["score"]).replace("-", ":")
        hg = item.get("home_goals")
        ag = item.get("away_goals")
        if hg is not None and ag is not None:
            return f"{hg}:{ag}"
    elif item:
        return str(item).replace("-", ":")
    return None


def active_report(conn: sqlite3.Connection, match_id: str) -> tuple[Dict[str, Any], Optional[str]]:
    cols = columns(conn, "lottery_analysis_reports")
    stale_clause = "AND COALESCE(is_stale, 0) = 0" if "is_stale" in cols else ""
    row = conn.execute(
        f"""
        SELECT report_data, created_at
        FROM lottery_analysis_reports
        WHERE lottery_match_id = ?
          AND report_type = 'prediction'
          {stale_clause}
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (match_id,),
    ).fetchone()
    if not row:
        return {}, None
    return loads_json(row["report_data"], {}), row["created_at"]


def prediction_payload(report: Dict[str, Any]) -> Dict[str, Any]:
    plays = report.get("play_predictions") or {}
    final = report.get("final_prediction") or {}
    spf = plays.get("spf") or {}
    rqspf = plays.get("rqspf") or {}
    bqc = plays.get("bqc") or {}
    ou = plays.get("ou") or {}
    scores = plays.get("top3_scores") or final.get("most_likely_scores") or []
    score_candidates = [score for score in (score_text(item) for item in scores[:3]) if score]
    return {
        "spf": spf.get("direction_cn") or spf.get("recommendation_cn") or spf.get("recommendation"),
        "spf_probabilities": final.get("probabilities") or spf.get("probabilities") or {},
        "rqspf": rqspf.get("recommendation_cn") or rqspf.get("recommendation"),
        "rqspf_line": rqspf.get("goal_line_label"),
        "rqspf_probabilities": rqspf.get("probabilities") or rqspf.get("handicap_probs") or {},
        "bqc": bqc.get("recommendation_cn") or bqc.get("recommendation"),
        "ou": ou.get("recommendation"),
        "ou_line": ou.get("line") or ou.get("best_line"),
        "ou_confidence": ou.get("confidence"),
        "ou_model_edge": ou.get("model_edge"),
        "ou_market": ou.get("market_recommendation"),
        "ou_probabilities": ou.get("best_line_probs") or {},
        "total_goals_distribution": ou.get("total_goals_distribution") or {},
        "expected_score": final.get("expected_score") or {},
        "score_candidates": score_candidates,
        "both_teams_to_score": final.get("both_teams_to_score") or {},
        "world_cup_context": compact_world_cup_context(report.get("world_cup_context") or {}),
        "intelligence": compact_intelligence(report.get("intelligence_adjustment") or {}),
        "factor_breakdown": compact_factor_breakdown(report.get("factor_breakdown") or {}),
    }


def compact_world_cup_context(ctx: Dict[str, Any]) -> Dict[str, Any]:
    pressure = ctx.get("pressure") or {}
    teams = ctx.get("teams") or {}
    group = ctx.get("group") or {}
    return {
        "group": group.get("group") or group.get("name_cn"),
        "matchday": (ctx.get("match") or {}).get("matchday"),
        "group_finished": (ctx.get("group_stage_context") or {}).get("group_matches_finished"),
        "group_total": (ctx.get("group_stage_context") or {}).get("group_matches_total"),
        "home_pressure": pressure.get("home"),
        "away_pressure": pressure.get("away"),
        "home_table": compact_table_row(teams.get("home") or {}),
        "away_table": compact_table_row(teams.get("away") or {}),
    }


def compact_table_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "group": row.get("group"),
        "position": row.get("position"),
        "played": row.get("played"),
        "points": row.get("points"),
        "goal_diff": row.get("goal_diff"),
        "qualification": row.get("qualification"),
    }


def compact_intelligence(intel: Dict[str, Any]) -> Dict[str, Any]:
    factors = []
    for factor in intel.get("factors") or []:
        factors.append(
            {
                "key": factor.get("key"),
                "title": factor.get("title"),
                "applied": factor.get("applied"),
                "confidence": factor.get("confidence"),
                "reason": factor.get("reason"),
                "evidence": (factor.get("evidence") or [])[:3],
            }
        )
    return {
        "applied": intel.get("applied"),
        "package_status": intel.get("package_status"),
        "package_completeness": intel.get("package_completeness"),
        "direction_before": intel.get("direction_before"),
        "direction_after": intel.get("direction_after"),
        "direction_changed": intel.get("direction_changed"),
        "factors": factors,
    }


def compact_factor_breakdown(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "weights": data.get("weights") or {},
        "final": data.get("final") or {},
        "odds": (data.get("factors") or {}).get("odds") or {},
    }


def target_matches(conn: sqlite3.Connection, args: argparse.Namespace) -> List[sqlite3.Row]:
    where = ["1=1"]
    params: List[Any] = []
    if args.date_from:
        where.append("substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) >= ?")
        params.append(args.date_from)
    if args.date_to:
        where.append("substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) <= ?")
        params.append(args.date_to)
    if args.league:
        where.append("lm.league_name_cn = ?")
        params.append(args.league)
    if args.match_nums:
        nums = [item.strip() for item in args.match_nums.split(",") if item.strip()]
        where.append(f"lm.match_num IN ({placeholders(nums)})")
        params.extend(nums)

    limit_sql = " LIMIT ?" if args.limit else ""
    if args.limit:
        params.append(args.limit)

    return conn.execute(
        f"""
        SELECT lm.lottery_match_id, lm.match_num,
               substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) AS match_date,
               lm.match_time,
               lm.league_name_cn, lm.home_team_cn, lm.away_team_cn,
               lm.handicap_line, lm.oddsfe_event_id,
               lr.home_goals_ft, lr.away_goals_ft, lr.home_goals_ht, lr.away_goals_ht,
               lr.spf_result, lr.rqspf_result, lr.bqc_result, lr.ou_result, lr.bf_result
        FROM lottery_matches lm
        JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
        WHERE {" AND ".join(where)}
          AND lr.home_goals_ft IS NOT NULL
          AND lr.away_goals_ft IS NOT NULL
        ORDER BY lm.match_date DESC, lm.match_time DESC, lm.match_num
        {limit_sql}
        """,
        params,
    ).fetchall()


def source_status(conn: sqlite3.Connection, row: sqlite3.Row) -> Dict[str, Any]:
    match_id = row["lottery_match_id"]
    status: Dict[str, Any] = {}
    if table_exists(conn, "intelligence_jobs") and table_exists(conn, "intelligence_packages"):
        package_cols = set(columns(conn, "intelligence_packages"))
        completeness_expr = (
            "ip.completeness_score"
            if "completeness_score" in package_cols
            else "ip.completeness"
            if "completeness" in package_cols
            else "NULL"
        )
        package_status_expr = "ip.status" if "status" in package_cols else "NULL"
        intel = conn.execute(
            f"""
            SELECT ij.job_id, ij.status AS job_status,
                   {package_status_expr} AS package_status,
                   {completeness_expr} AS completeness_score,
                   ip.updated_at
            FROM intelligence_jobs ij
            LEFT JOIN intelligence_packages ip ON ip.job_id = ij.job_id
            WHERE ij.lottery_match_id = ?
            ORDER BY ij.created_at DESC
            LIMIT 1
            """,
            (match_id,),
        ).fetchone()
        status["intelligence"] = dict(intel) if intel else None
    if table_exists(conn, "source_artifacts"):
        status["source_artifacts"] = [
            dict(item)
            for item in conn.execute(
                """
                SELECT source_name, source_type, entity_type, COUNT(*) AS count,
                       MAX(captured_at) AS latest_at,
                       ROUND(AVG(confidence), 3) AS avg_confidence
                FROM source_artifacts
                WHERE entity_id IN (?, ?)
                   OR entity_id = ?
                GROUP BY source_name, source_type, entity_type
                ORDER BY latest_at DESC
                LIMIT 8
                """,
                (match_id, str(row["oddsfe_event_id"] or ""), row["match_num"]),
            ).fetchall()
        ]
    if table_exists(conn, "bqc_phase_error_patterns"):
        pattern = conn.execute(
            """
            SELECT pattern_type, profile_role, half_axis_error, full_axis_error,
                   path_flip, current_bqc, profile_bqc, actual_bqc,
                   signal_reason, signal_confidence, notes_json, version_tag, created_at
            FROM bqc_phase_error_patterns
            WHERE lottery_match_id = ?
            ORDER BY datetime(created_at) DESC
            LIMIT 1
            """,
            (match_id,),
        ).fetchone()
        if pattern:
            payload = dict(pattern)
            payload["notes"] = loads_json(payload.pop("notes_json", None), {})
            status["bqc_phase_pattern"] = payload
    if table_exists(conn, "bqc_full_time_axis_audits"):
        full_axis = conn.execute(
            """
            SELECT actual_spf, actual_score,
                   bqc_full_axis, spf_axis, score_top_axis, score_weighted_axis,
                   bqc_full_correct, spf_correct, score_top_correct, score_weighted_correct,
                   axis_driver, risk_tags_json, axis_json, version_tag, created_at
            FROM bqc_full_time_axis_audits
            WHERE lottery_match_id = ?
            ORDER BY datetime(created_at) DESC
            LIMIT 1
            """,
            (match_id,),
        ).fetchone()
        if full_axis:
            payload = dict(full_axis)
            payload["risk_tags"] = loads_json(payload.pop("risk_tags_json", None), [])
            payload["axis"] = loads_json(payload.pop("axis_json", None), {})
            status["bqc_full_time_axis"] = payload
    return status


def actual_payload(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "score": f"{row['home_goals_ft']}:{row['away_goals_ft']}",
        "half_score": (
            f"{row['home_goals_ht']}:{row['away_goals_ht']}"
            if row["home_goals_ht"] is not None and row["away_goals_ht"] is not None
            else None
        ),
        "total_goals": int(row["home_goals_ft"] or 0) + int(row["away_goals_ft"] or 0),
        "margin": int(row["home_goals_ft"] or 0) - int(row["away_goals_ft"] or 0),
        "spf": row["spf_result"],
        "rqspf": row["rqspf_result"],
        "bqc": row["bqc_result"],
        "ou": row["ou_result"],
        "bf": row["bf_result"],
    }


def load_validation_map(
    conn: sqlite3.Connection,
    match_ids: Sequence[str],
) -> Dict[tuple[str, str], Dict[str, Any]]:
    if not match_ids or not table_exists(conn, "lottery_validation"):
        return {}
    result: Dict[tuple[str, str], Dict[str, Any]] = {}
    for row in conn.execute(
        f"""
        SELECT lottery_match_id, play_type, predicted_result, actual_result, is_correct
        FROM lottery_validation
        WHERE lottery_match_id IN ({placeholders(match_ids)})
        """,
        list(match_ids),
    ).fetchall():
        result[(str(row["lottery_match_id"]), str(row["play_type"]))] = {
            "predicted_result": row["predicted_result"],
            "actual_result": row["actual_result"],
            "is_correct": bool(row["is_correct"]),
        }
    return result


def validation_value(validation: Optional[Dict[str, Any]], key: str) -> Optional[str]:
    if not validation:
        return None
    value = validation.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def display_play_value(play_type: str, value: Any) -> Any:
    if value is None:
        return value
    text = str(value).strip()
    if play_type == "spf":
        return RESULT_CODE_TO_CN.get(normalize_result(text), text)
    if play_type == "rqspf":
        return HANDICAP_CODE_TO_CN.get(normalize_result(text), text)
    if play_type == "bqc":
        return BQC_CODE_TO_CN.get(normalize_bqc(text), text)
    return text


def is_play_correct(play_type: str, pred: Dict[str, Any], actual: Dict[str, Any]) -> bool:
    if play_type == "spf":
        return normalize_result(pred.get("spf")) == normalize_result(actual.get("spf"))
    if play_type == "rqspf":
        return normalize_result(pred.get("rqspf")) == normalize_result(actual.get("rqspf"))
    if play_type == "bqc":
        return normalize_bqc(pred.get("bqc")) == normalize_bqc(actual.get("bqc"))
    if play_type == "ou":
        return ou_side(pred.get("ou")) == ou_side(actual.get("ou"))
    if play_type == "bf":
        return str(actual.get("bf") or "").replace("-", ":") in set(pred.get("score_candidates") or [])
    return False


def diagnose_play(
    play_type: str,
    pred: Dict[str, Any],
    actual: Dict[str, Any],
    row: sqlite3.Row,
    source: Dict[str, Any],
    validation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if validation and "is_correct" in validation:
        correct = bool(validation["is_correct"])
    else:
        correct = is_play_correct(play_type, pred, actual)
    display_predicted = display_play_value(
        play_type,
        validation_value(validation, "predicted_result") or predicted_value(play_type, pred),
    )
    display_actual = display_play_value(
        play_type,
        validation_value(validation, "actual_result") or actual.get(play_type),
    )
    error_categories: List[str] = []
    observations: List[str] = []
    missing_factors: List[Dict[str, Any]] = []
    collection_actions: List[Dict[str, Any]] = []
    model_actions: List[Dict[str, Any]] = []

    expected = pred.get("expected_score") or {}
    exp_home = safe_float(expected.get("home"))
    exp_away = safe_float(expected.get("away"))
    exp_total = exp_home + exp_away
    exp_margin = exp_home - exp_away
    actual_total = safe_float(actual.get("total_goals"))
    actual_margin = safe_float(actual.get("margin"))
    hcp_raw = pred.get("rqspf_line") if pred.get("rqspf_line") not in (None, "") else row["handicap_line"]
    hcp = safe_float(hcp_raw)
    wc = pred.get("world_cup_context") or {}
    intel = pred.get("intelligence") or {}

    if abs(actual_total - exp_total) >= 2:
        error_categories.append("goal_total_large_deviation")
        observations.append(f"预期总进球约{exp_total:.1f}，实际{actual_total:.0f}，偏差超过2球")
    if abs(actual_margin - exp_margin) >= 2:
        error_categories.append("margin_large_deviation")
        observations.append(f"预期净胜约{exp_margin:.1f}，实际净胜{actual_margin:.0f}")

    if play_type == "spf":
        observations.append(f"预测{display_predicted}，实际{display_actual}")
        if not correct:
            model_actions.append(
                action("direction_axis", "降低低置信胜平负的单轴输出权重，强制检查盘口主方向和比分矩阵是否一致")
            )
            if pred.get("ou_market") and pred.get("ou") and ou_side(pred.get("ou_market")) != ou_side(pred.get("ou")):
                model_actions.append(action("market_disagreement", "模型与市场分歧时进入二次校验，不直接提升置信"))

    if play_type == "rqspf":
        observations.append(
            f"让球{hcp_raw}，预测{display_predicted}，实际{display_actual}"
        )
        threshold_gap = abs((actual_margin + hcp) - 0)
        if not correct:
            if abs(exp_margin + hcp) <= 0.35:
                error_categories.append("handicap_boundary_case")
                observations.append("预期让球后接近临界点，属于让胜/让平/让负边界盘")
            if threshold_gap <= 1:
                error_categories.append("one_goal_margin_sensitivity")
            model_actions.append(
                action("handicap_axis", "让球胜平负必须从同一比分矩阵推导，并输出主胜1球/2球以上/不胜概率")
            )

    if play_type == "bqc":
        observations.append(f"预测{display_predicted}，实际{display_actual}，半场{actual.get('half_score')}")
        if not correct:
            phase_pattern = source.get("bqc_phase_pattern") if isinstance(source.get("bqc_phase_pattern"), dict) else {}
            full_axis_audit = source.get("bqc_full_time_axis") if isinstance(source.get("bqc_full_time_axis"), dict) else {}
            pattern_type = str(phase_pattern.get("pattern_type") or "")
            profile_role = str(phase_pattern.get("profile_role") or "")
            notes = phase_pattern.get("notes") if isinstance(phase_pattern.get("notes"), dict) else {}
            if pattern_type:
                error_categories.append(pattern_type)
                observations.append(f"BQC阶段归因：{pattern_type} / 画像角色：{profile_role or '--'}")
                if notes.get("takeaway"):
                    observations.append(str(notes.get("takeaway")))

            if pattern_type == "full_time_axis_miss":
                error_categories.append("bqc_full_time_axis_misread")
                axis_driver = str(full_axis_audit.get("axis_driver") or "")
                risk_tags = full_axis_audit.get("risk_tags") if isinstance(full_axis_audit.get("risk_tags"), list) else []
                if axis_driver:
                    error_categories.append(axis_driver)
                    observations.append(
                        f"BQC全场轴审计：{axis_driver}"
                        + (f"；标签：{'/'.join(str(tag) for tag in risk_tags[:4])}" if risk_tags else "")
                    )
                missing_factors.append(factor("full_time_path_axis", "全场方向腿误判", "direction_score_axis"))
                model_actions.append(
                    action("bqc_full_time_axis", "BQC全场腿错时不要继续加半场权重，先回查胜平负、比分矩阵、让球区间是否同轴")
                )
                model_actions.append(
                    action("score_axis", "用同一比分矩阵约束胜平负、让球胜平负和BQC全场腿，避免路径互相打架")
                )
                if axis_driver == "spf_dragged_bqc_ignored_score_axis":
                    model_actions.append(
                        action("spf_score_axis_arbitration", "胜平负主轴与比分轴冲突时，用比分分布和让球边界做二次仲裁")
                    )
                    model_actions.append(
                        action("score_axis_should_enter_bqc_full_leg", "比分轴已经指向实际全场方向时，必须进入BQC全场腿决策")
                    )
                elif axis_driver == "spf_dragged_bqc_global_direction_miss":
                    model_actions.append(
                        action("direction_axis_recalibration", "胜平负、比分轴、BQC全场腿同时错时，回查实力差、盘口、动机和防守尾部风险")
                    )
                elif axis_driver == "bqc_detached_from_correct_spf":
                    model_actions.append(
                        action("bqc_spf_full_leg_consistency", "胜平负轴正确时，BQC全场腿不得无证据反向偏离")
                    )
                elif axis_driver == "score_axis_signal_ignored":
                    model_actions.append(
                        action("score_axis_should_enter_bqc_full_leg", "比分轴命中全场方向但BQC忽略时，提高比分轴在BQC全场腿中的约束权重")
                    )
                if "draw_risk_underweighted" in risk_tags:
                    model_actions.append(
                        action("draw_risk_tie_breaker", "强弱不稳或低比分区间时，必须单独评估平局风险再决定BQC全场腿")
                    )
                if "thin_spf_gap" in risk_tags or "low_spf_top_probability" in risk_tags:
                    model_actions.append(
                        action("low_confidence_direction_guard", "胜平负最高概率不厚或差距过窄时，禁止把BQC写成强确定路径")
                    )
            elif pattern_type == "half_time_axis_miss":
                error_categories.append("first_half_tempo_misread")
                missing_factors.append(factor("first_half_goal_profile", "缺少或权重不足", "half_time_axis"))
                collection_actions.append(
                    action("collect_half_time_profiles", "从 oddsfe score_details 和历史比赛补每队近10场半场进/失球、0-0半场率")
                )
                model_actions.append(
                    action("bqc_half_time_axis", "全场腿正确但半场腿错误时，单独校准上半场进球率、半场平局率和慢热/早进球特征")
                )
            elif pattern_type == "profile_helped":
                model_actions.append(
                    action("bqc_profile_positive_case", "半场画像在该形态有帮助，先沉淀相似样本，达到正收益阈值后再进入gate")
                )
            else:
                error_categories.append("first_half_tempo_misread")
                missing_factors.append(factor("first_half_goal_profile", "缺少或权重不足", "half_time_axis"))
                collection_actions.append(
                    action("collect_half_time_profiles", "从 oddsfe score_details 和历史比赛补每队近10场半场进/失球、0-0半场率")
                )
                model_actions.append(
                    action("bqc_axis", "半全场不要机械跟随全场方向，先独立计算半场进球和半场胜平负分布")
                )

    if play_type == "ou":
        observations.append(
            f"预测{display_predicted}，实际{display_actual}，预期总进球{exp_total:.1f}，实际{actual_total:.0f}"
        )
        if not correct:
            if actual_total >= 4 and exp_total < 3.2:
                error_categories.append("tail_risk_underestimated")
                missing_factors.append(factor("defensive_collapse_risk", "缺少或权重不足", "goal_axis"))
                collection_actions.append(
                    action("collect_recent_defense_split", "补球队近10场失球、被射门、被射正、xGA；国家队优先 oddsfe/API-Sports/已有matches")
                )
                model_actions.append(
                    action("goal_tail_distribution", "比分矩阵加入大比分尾部惩罚/奖励，不只看均值和盘口线")
                )
            if actual_total <= 1 and exp_total > 2.6:
                error_categories.append("low_tempo_underestimated")
                missing_factors.append(factor("low_tempo_match_profile", "缺少或权重不足", "goal_axis"))
                collection_actions.append(
                    action("collect_team_tempo", "补两队近期总进球中位数、半场0-0率、领先后降速率")
                )
            if pred.get("ou_market") and ou_side(pred.get("ou_market")) != ou_side(pred.get("ou")):
                error_categories.append("model_market_ou_divergence")
                model_actions.append(
                    action("ou_tie_breaker", "盘口方向与模型方向冲突且模型优势薄时，用市场作二次校验")
                )

    if play_type == "bf":
        observations.append(
            f"候选比分{'/'.join(pred.get('score_candidates') or []) or '--'}，实际{display_actual}"
        )
        if not correct:
            error_categories.append("score_candidate_miss")
            if actual_total >= 4:
                error_categories.append("score_tail_missing")
            model_actions.append(
                action("score_axis", "比分候选不只取前三最高概率，还要加入一个与主判断/大小球一致的尾部候选")
            )

    intel_status = source.get("intelligence") or {}
    if not intel_status or safe_float(intel_status.get("completeness_score")) < 90:
        missing_factors.append(factor("intelligence_package", "缺失或覆盖不足", "all_axes"))
        collection_actions.append(
            action("fill_intelligence_package", "自动补齐天气、伤停、预计首发、新闻、赛程休息和世界杯形势证据")
        )

    low_conf_titles = [
        item.get("title") or item.get("key")
        for item in intel.get("factors") or []
        if safe_float(item.get("confidence")) < 0.5
    ]
    if low_conf_titles:
        missing_factors.append(
            {
                "factor": "low_confidence_intelligence",
                "status": "低置信证据",
                "axis": "all_axes",
                "detail": " / ".join(str(item) for item in low_conf_titles[:4]),
            }
        )

    if wc:
        home_pressure = ((wc.get("home_pressure") or {}).get("level") or "")
        away_pressure = ((wc.get("away_pressure") or {}).get("level") or "")
        observations.append(f"世界杯压力：{home_pressure or '--'} / {away_pressure or '--'}")
    else:
        missing_factors.append(factor("world_cup_context", "缺失", "motivation_axis"))
        collection_actions.append(
            action("refresh_world_cup_context", "从世界杯实时API刷新小组积分、第三名池、晋级路径和末轮形势")
        )

    if correct:
        if not error_categories:
            error_categories.append("positive_case")
        model_actions.append(action("keep_positive_pattern", "沉淀为相似案例，作为同盘口/同形势正样本"))
    else:
        if not error_categories:
            error_categories.append("unclassified_error")
        model_actions.append(action("similar_case_review", "检索相似历史案例，确认同盘口同强弱是否同样误判"))

    return {
        "play_type": play_type,
        "play_label": PLAY_LABELS.get(play_type, play_type),
        "is_correct": correct,
        "predicted": display_predicted,
        "actual": display_actual,
        "error_categories": sorted(set(error_categories)),
        "observations": observations[:8],
        "missing_factors": dedupe_dicts(missing_factors),
        "collection_actions": dedupe_dicts(collection_actions),
        "model_actions": dedupe_dicts(model_actions),
    }


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def factor(name: str, status: str, axis: str, detail: str = "") -> Dict[str, Any]:
    return {"factor": name, "status": status, "axis": axis, "detail": detail}


def action(name: str, detail: str) -> Dict[str, Any]:
    return {"action": name, "detail": detail}


def dedupe_dicts(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def predicted_value(play_type: str, pred: Dict[str, Any]) -> Any:
    if play_type == "bf":
        return " / ".join(pred.get("score_candidates") or [])
    return pred.get(play_type)


def ensure_diagnosis_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS prediction_error_diagnoses (
            diagnosis_id TEXT PRIMARY KEY,
            match_key TEXT NOT NULL,
            match_date TEXT,
            match_num TEXT,
            league_name_cn TEXT,
            play_type TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            predicted TEXT,
            actual TEXT,
            error_categories_json TEXT,
            diagnosis_json TEXT,
            missing_factors_json TEXT,
            collection_actions_json TEXT,
            model_actions_json TEXT,
            version_tag TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prediction_error_diagnoses_match
        ON prediction_error_diagnoses(match_key, play_type)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prediction_error_diagnoses_date
        ON prediction_error_diagnoses(match_date, play_type, is_correct)
        """
    )


def save_diagnoses(
    conn: sqlite3.Connection,
    match: sqlite3.Row,
    play_items: Sequence[Dict[str, Any]],
    version_tag: str,
) -> int:
    ensure_diagnosis_table(conn)
    count = 0
    for item in play_items:
        diagnosis_id = compact_id("diag", match["lottery_match_id"], item["play_type"], version_tag)
        conn.execute(
            """
            INSERT OR REPLACE INTO prediction_error_diagnoses
            (diagnosis_id, match_key, match_date, match_num, league_name_cn,
             play_type, is_correct, predicted, actual, error_categories_json,
             diagnosis_json, missing_factors_json, collection_actions_json,
             model_actions_json, version_tag, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                diagnosis_id,
                match["lottery_match_id"],
                match["match_date"],
                match["match_num"],
                match["league_name_cn"],
                item["play_type"],
                1 if item["is_correct"] else 0,
                "" if item.get("predicted") is None else str(item.get("predicted")),
                "" if item.get("actual") is None else str(item.get("actual")),
                json.dumps(item.get("error_categories") or [], ensure_ascii=False, sort_keys=True),
                json.dumps(item, ensure_ascii=False, sort_keys=True, default=str),
                json.dumps(item.get("missing_factors") or [], ensure_ascii=False, sort_keys=True),
                json.dumps(item.get("collection_actions") or [], ensure_ascii=False, sort_keys=True),
                json.dumps(item.get("model_actions") or [], ensure_ascii=False, sort_keys=True),
                version_tag,
            ),
        )
        count += 1
    return count


def summarize(items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "matches": len(items),
        "plays": 0,
        "wrong": 0,
        "by_play_type": {},
        "top_error_categories": {},
        "collection_actions": {},
        "model_actions": {},
    }
    for match in items:
        for play in match.get("plays") or []:
            summary["plays"] += 1
            bucket = summary["by_play_type"].setdefault(
                play["play_type"], {"total": 0, "wrong": 0, "accuracy": 0}
            )
            bucket["total"] += 1
            if not play.get("is_correct"):
                summary["wrong"] += 1
                bucket["wrong"] += 1
            for category in play.get("error_categories") or []:
                summary["top_error_categories"][category] = summary["top_error_categories"].get(category, 0) + 1
            for action_item in play.get("collection_actions") or []:
                key = action_item.get("action")
                summary["collection_actions"][key] = summary["collection_actions"].get(key, 0) + 1
            for action_item in play.get("model_actions") or []:
                key = action_item.get("action")
                summary["model_actions"][key] = summary["model_actions"].get(key, 0) + 1
    for bucket in summary["by_play_type"].values():
        total = bucket["total"]
        bucket["accuracy"] = round((total - bucket["wrong"]) * 100 / total, 1) if total else 0
    summary["top_error_categories"] = sorted(
        summary["top_error_categories"].items(), key=lambda item: (-item[1], item[0])
    )
    summary["collection_actions"] = sorted(summary["collection_actions"].items(), key=lambda item: (-item[1], item[0]))
    summary["model_actions"] = sorted(summary["model_actions"].items(), key=lambda item: (-item[1], item[0]))
    return summary


def summarize_validations(validation_map: Dict[tuple[str, str], Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "plays": 0,
        "wrong": 0,
        "by_play_type": {},
    }
    for (_, play_type), validation in validation_map.items():
        summary["plays"] += 1
        bucket = summary["by_play_type"].setdefault(
            play_type,
            {"total": 0, "wrong": 0, "accuracy": 0},
        )
        bucket["total"] += 1
        if not bool(validation.get("is_correct")):
            summary["wrong"] += 1
            bucket["wrong"] += 1
    for bucket in summary["by_play_type"].values():
        total = bucket["total"]
        bucket["accuracy"] = round((total - bucket["wrong"]) * 100 / total, 1) if total else 0
    return summary


def validation_consistency(
    diagnosis_summary: Dict[str, Any],
    validation_summary: Dict[str, Any],
) -> Dict[str, Any]:
    if not validation_summary.get("plays"):
        return {
            "ok": True,
            "skipped": True,
            "reason": "no lottery_validation rows for selected matches",
            "mismatches": [],
        }
    mismatches = []
    # Total plays comparison: diagnosis naturally has more (includes matches without reports)
    # Only flag if validation has MORE than diagnosis (indicates real inconsistency)
    diag_plays = diagnosis_summary.get("plays", 0)
    val_plays = validation_summary.get("plays", 0)
    if val_plays > diag_plays:
        mismatches.append(
            {
                "scope": "total",
                "field": "plays",
                "diagnosis": diag_plays,
                "validation": val_plays,
            }
        )
    diag_wrong = diagnosis_summary.get("wrong", 0)
    val_wrong = validation_summary.get("wrong", 0)
    if val_wrong > diag_wrong:
        mismatches.append(
            {
                "scope": "total",
                "field": "wrong",
                "diagnosis": diag_wrong,
                "validation": val_wrong,
            }
        )
    diagnosis_by_type = diagnosis_summary.get("by_play_type") or {}
    validation_by_type = validation_summary.get("by_play_type") or {}
    for play_type in sorted(set(diagnosis_by_type) & set(validation_by_type)):
        left = diagnosis_by_type.get(play_type) or {}
        right = validation_by_type.get(play_type) or {}
        # Only compare if validation has entries for this play type
        if not right.get("total"):
            continue
        for field in ("total", "wrong"):
            if left.get(field) != right.get(field):
                mismatches.append(
                    {
                        "scope": play_type,
                        "field": field,
                        "diagnosis": left.get(field),
                        "validation": right.get(field),
                    }
                )
    return {
        "ok": not mismatches,
        "mismatches": mismatches,
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    version_tag = args.version_tag or f"error_diag_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    with connect(db_path) as conn:
        matches = target_matches(conn, args)
        validation_map = load_validation_map(conn, [str(row["lottery_match_id"]) for row in matches])
        result_items = []
        saved = 0
        for row in matches:
            report, report_created_at = active_report(conn, row["lottery_match_id"])
            pred = prediction_payload(report)
            actual = actual_payload(row)
            source = source_status(conn, row)
            plays = [
                diagnose_play(
                    play_type,
                    pred,
                    actual,
                    row,
                    source,
                    validation_map.get((str(row["lottery_match_id"]), play_type)),
                )
                for play_type in ("spf", "rqspf", "bqc", "ou", "bf")
            ]
            item = {
                "match_key": row["lottery_match_id"],
                "match_num": row["match_num"],
                "match_date": row["match_date"],
                "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
                "score": actual["score"],
                "half_score": actual["half_score"],
                "report_created_at": report_created_at,
                "prediction_brief": {
                    "spf": pred.get("spf"),
                    "rqspf": pred.get("rqspf"),
                    "rqspf_line": pred.get("rqspf_line"),
                    "bqc": pred.get("bqc"),
                    "ou": pred.get("ou"),
                    "expected_score": pred.get("expected_score"),
                    "score_candidates": pred.get("score_candidates"),
                },
                "source_status": source,
                "plays": plays,
            }
            result_items.append(item)
            if args.apply:
                saved += save_diagnoses(conn, row, plays, version_tag)
        if args.apply:
            conn.commit()
    summary = summarize(result_items)
    validation_summary = summarize_validations(validation_map)
    consistency = validation_consistency(summary, validation_summary)
    return {
        "success": bool(consistency.get("ok")),
        "mode": "apply" if args.apply else "dry_run",
        "version_tag": version_tag,
        "saved": saved,
        "summary": summary,
        "validation_summary": validation_summary,
        "validation_consistency": consistency,
        "matches": result_items,
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--from", dest="date_from", default=None)
    parser.add_argument("--to", dest="date_to", default=None)
    parser.add_argument("--league", default="")
    parser.add_argument("--match-nums", default="", help="Comma-separated lottery match numbers")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--version-tag", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--compact", action="store_true", help="Print only summary and compact match findings")
    parser.add_argument("--summary-only", action="store_true", help="Print only summary and validation consistency")
    return parser.parse_args(argv)


def compact_output(result: Dict[str, Any]) -> Dict[str, Any]:
    compact_matches = []
    for match in result.get("matches") or []:
        wrong = [play for play in match.get("plays") or [] if not play.get("is_correct")]
        compact_matches.append(
            {
                "match_num": match.get("match_num"),
                "teams": match.get("teams"),
                "score": match.get("score"),
                "prediction_brief": match.get("prediction_brief"),
                "wrong_plays": [
                    {
                        "play": play.get("play_label"),
                        "predicted": play.get("predicted"),
                        "actual": play.get("actual"),
                        "error_categories": play.get("error_categories"),
                        "observations": play.get("observations"),
                        "missing_factors": play.get("missing_factors"),
                        "collection_actions": play.get("collection_actions"),
                        "model_actions": play.get("model_actions"),
                    }
                    for play in wrong
                ],
            }
        )
    return {
        "success": result.get("success"),
        "mode": result.get("mode"),
        "version_tag": result.get("version_tag"),
        "saved": result.get("saved"),
        "summary": result.get("summary"),
        "validation_summary": result.get("validation_summary"),
        "validation_consistency": result.get("validation_consistency"),
        "matches": compact_matches,
    }


def main() -> int:
    args = parse_args()
    result = run(args)
    if args.summary_only:
        output = {
            "success": result.get("success"),
            "mode": result.get("mode"),
            "version_tag": result.get("version_tag"),
            "saved": result.get("saved"),
            "summary": result.get("summary"),
            "validation_summary": result.get("validation_summary"),
            "validation_consistency": result.get("validation_consistency"),
        }
    else:
        output = compact_output(result) if args.compact else result
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
