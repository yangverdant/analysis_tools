"""
体彩API路由

提供体彩数据查询、分析、同步等API接口

所有接口前缀: /api/v1/lottery
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Dict, List, Optional, Any
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta
import sqlite3
import json
import logging
import os
import time
import uuid
import requests as http_requests
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lottery", tags=["lottery"])

# 体彩核心在售联赛白名单 — 仅这些联赛在体彩中心展示。
# 其他联赛(oddsfe采集的美乙/智杯/厄甲/瑞甲/挪甲/芬甲/韩乙/中乙等)继续作为
# 后端分析养料(进 predictions/results/learning), 但不展示在体彩中心。
# 来源: sporttery历史返回 + 体彩官网公开在售清单(2026)。
LOTTERY_CORE_LEAGUES = {
    # 国际赛
    "世界杯", "欧洲杯", "亚洲杯", "非洲杯", "美洲杯",
    "国际赛", "俱乐部友谊赛",
    # 五大联赛
    "英超", "西甲", "德甲", "意甲", "法甲",
    # 五大次级
    "英冠", "英甲", "英乙", "西乙", "德乙", "德丙", "意乙", "法乙",
    # 五大杯赛
    "英联杯", "足总杯", "社区盾杯", "国王杯", "德国杯", "意大利杯",
    "法国杯", "法联杯",
    # 欧洲主流
    "荷甲", "荷乙", "比甲", "葡超", "葡甲", "苏超", "苏冠",
    "奥甲", "瑞士超", "丹超", "捷甲", "波超", "希腊超",
    "土超", "土甲", "俄超", "乌超", "克甲", "塞超", "罗甲", "匈甲", "以超",
    # 欧洲杯赛
    "欧冠", "欧联", "欧协联", "欧超杯",
    # 美洲主流
    "美职", "美乙", "美职联杯", "墨超", "巴甲", "巴乙",
    "阿甲", "哥伦甲", "厄甲", "智利甲", "智利杯",
    "秘鲁甲", "乌拉甲", "巴拉甲", "阿根廷杯",
    # 亚洲主流
    "日职", "日乙", "日联杯", "韩职", "韩乙", "韩联杯",
    "澳超", "中超", "中甲", "中乙", "足协杯",
    "沙特联", "卡塔尔联", "阿联酋联", "伊朗超",
    "泰超", "泰甲", "越南联", "印尼甲",
    # 亚洲杯赛
    "亚冠", "亚联杯",
    # 北欧
    "瑞超", "瑞甲", "挪超", "挪甲", "芬超", "芬甲", "冰岛超", "丹甲",
}

# 数据库路径 - 云端优先使用环境变量，本地使用项目相对路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
DB_PATH = os.environ.get('DB_PATH', os.path.join(PROJECT_ROOT, 'data', 'football_v2.db'))
ODDSFE_DB_PATH = os.environ.get(
    'ODDSFE_DB_PATH',
    os.path.join(PROJECT_ROOT, 'fetchers', 'odds_feed_api', 'oddsfe_merged.db'),
)


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_table_columns(cursor, table_name: str) -> set:
    """Return column names for a table; missing tables produce an empty set."""
    try:
        return {row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()}
    except sqlite3.Error:
        return set()


def column_or_null(columns: set, column_name: str) -> str:
    """Build a SELECT expression that tolerates older local/cloud schemas."""
    return column_name if column_name in columns else f"NULL AS {column_name}"


def _loads_json(value: Any, default: Any = None) -> Any:
    if default is None:
        default = {}
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _table_exists(cursor, table_name: str) -> bool:
    try:
        return cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone() is not None
    except sqlite3.Error:
        return False


def _clean_display_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if set(text) <= {"?"}:
        return None
    if text.count("?") >= max(3, len(text) // 2):
        return None
    return text


def _clean_report_id(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text or text.lower() in {"none", "null", "undefined", "nan"}:
        return None
    return text


def _compact_counter(counter: Counter, total: int = 0, limit: int = 12) -> List[Dict[str, Any]]:
    rows = []
    for key, count in counter.most_common(limit):
        rows.append({
            "key": key,
            "count": int(count),
            "rate": round(count * 100 / total, 1) if total else 0,
        })
    return rows


def _ensure_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _latest_learning_payload(cursor, lottery_match_id: str) -> Dict[str, Any]:
    """Return compact feature/review/similar-case learning data for one match."""
    payload: Dict[str, Any] = {
        "feature_snapshot": None,
        "context_snapshot": None,
        "reviews": [],
        "similar_cases": [],
        "summary": {
            "review_total": 0,
            "similar_total": 0,
            "similar_correct": 0,
            "similar_accuracy": None,
        },
    }

    if not lottery_match_id:
        return payload

    if _table_exists(cursor, "match_feature_snapshots"):
        row = cursor.execute(
            """
            SELECT snapshot_id, snapshot_time, feature_json, model_version, source_report_id
            FROM match_feature_snapshots
            WHERE match_key = ?
            ORDER BY snapshot_time DESC, CAST(source_report_id AS INTEGER) DESC, rowid DESC
            LIMIT 1
            """,
            (lottery_match_id,),
        ).fetchone()
        if row:
            features = _loads_json(row["feature_json"], {})
            final_prediction = features.get("final_prediction") or {}
            play_predictions = features.get("play_predictions") or {}
            payload["feature_snapshot"] = {
                "snapshot_id": row["snapshot_id"],
                "snapshot_time": row["snapshot_time"],
                "model_version": row["model_version"],
                "source_report_id": row["source_report_id"],
                "final_prediction": final_prediction,
                "play_types": sorted([key for key, value in play_predictions.items() if value and key != "derivation_axes"]),
                "model_vs_odds": features.get("model_vs_odds") or {},
            }

    if _table_exists(cursor, "match_context_snapshots"):
        context_rows = cursor.execute(
            """
            SELECT snapshot_id, snapshot_time, data_quality_json, odds_context_json
            FROM match_context_snapshots
            WHERE match_key = ?
            ORDER BY snapshot_time DESC, rowid DESC
            LIMIT 200
            """,
            (lottery_match_id,),
        ).fetchall()
        feature_report_id = _clean_report_id(
            (payload.get("feature_snapshot") or {}).get("source_report_id")
        )
        row = None
        if feature_report_id:
            for candidate in context_rows:
                quality = _loads_json(candidate["data_quality_json"], {})
                if _clean_report_id(quality.get("source_report_id")) == feature_report_id:
                    row = candidate
                    break
        if row is None and context_rows:
            row = context_rows[0]
        if row:
            data_quality = _loads_json(row["data_quality_json"], {})
            payload["context_snapshot"] = {
                "snapshot_id": row["snapshot_id"],
                "snapshot_time": row["snapshot_time"],
                "source_report_id": _clean_report_id(data_quality.get("source_report_id")),
                "data_quality": data_quality,
                "odds_context": _loads_json(row["odds_context_json"], {}),
            }

    if _table_exists(cursor, "post_match_reviews"):
        rows = cursor.execute(
            """
            SELECT review_id, play_type, predicted_result, actual_result,
                   is_correct, attribution, review_json, created_at
            FROM post_match_reviews
            WHERE match_key = ?
            ORDER BY created_at DESC
            LIMIT 8
            """,
            (lottery_match_id,),
        ).fetchall()
        if not rows and _table_exists(cursor, "lottery_validation"):
            rows = cursor.execute(
                """
                SELECT validation_id AS review_id, play_type, predicted_result,
                       actual_result, is_correct, attribution,
                       attribution_detail, validated_at AS created_at
                FROM lottery_validation
                WHERE lottery_match_id = ?
                ORDER BY validated_at DESC
                LIMIT 8
                """,
                (lottery_match_id,),
            ).fetchall()
        reviews = []
        for row in rows:
            row_keys = row.keys()
            review_json = _loads_json(row["review_json"], {}) if "review_json" in row_keys else {}
            if not isinstance(review_json, dict):
                review_json = {}
            validation = review_json.get("validation") or {}
            if not isinstance(validation, dict):
                validation = {}
            structured_review = review_json.get("structured_review") or {}
            if not isinstance(structured_review, dict):
                structured_review = {}
            attribution = review_json.get("attribution") or {}
            attribution_text = attribution if isinstance(attribution, str) else None
            if not isinstance(attribution, dict):
                attribution = {}
            reviews.append({
                "review_id": row["review_id"],
                "play_type": row["play_type"],
                "predicted_result": row["predicted_result"],
                "actual_result": row["actual_result"],
                "is_correct": None if row["is_correct"] is None else bool(row["is_correct"]),
                "attribution": row["attribution"],
                "attribution_detail": (
                    attribution.get("detail")
                    or attribution_text
                    or validation.get("attribution_detail")
                    or (row["attribution_detail"] if "attribution_detail" in row_keys else None)
                ),
                "reason_text": (
                    structured_review.get("reason_text")
                    or review_json.get("reason_text")
                    or validation.get("reason_text")
                ),
                "learning_tags": (
                    structured_review.get("learning_tags")
                    or review_json.get("learning_tags")
                    or []
                )[:8],
                "action_items": (
                    structured_review.get("action_items")
                    or review_json.get("action_items")
                    or []
                )[:8],
                "factor_checks": (structured_review.get("factor_checks") or [])[:4],
                "next_data_requirements": attribution.get("next_data_requirements", []),
                "created_at": row["created_at"],
            })
        payload["reviews"] = reviews
        payload["summary"]["review_total"] = len(reviews)

    if _table_exists(cursor, "similar_match_cases"):
        similar_columns = get_table_columns(cursor, "similar_match_cases")
        play_type_select = "smc.play_type AS case_play_type," if "play_type" in similar_columns else "NULL AS case_play_type,"
        rows = cursor.execute(
            f"""
            SELECT smc.similar_match_key, smc.similarity_score,
                   {play_type_select}
                   smc.similarity_json, smc.outcome_json, smc.created_at,
                   lm.home_team_cn, lm.away_team_cn, lm.match_date, lm.league_name_cn,
                   lr.home_goals_ft, lr.away_goals_ft, lr.bf_result
            FROM similar_match_cases smc
            LEFT JOIN lottery_matches lm ON lm.lottery_match_id = smc.similar_match_key
            LEFT JOIN lottery_results lr ON lr.lottery_match_id = smc.similar_match_key
            WHERE smc.match_key = ?
            ORDER BY smc.similarity_score DESC, smc.created_at DESC
            LIMIT 6
            """,
            (lottery_match_id,),
        ).fetchall()
        similar_cases = []
        correct_count = 0
        known_count = 0
        for row in rows:
            similarity = _loads_json(row["similarity_json"], {})
            outcome = _loads_json(row["outcome_json"], {})
            reasons = similarity.get("reasons") or {}
            is_correct = outcome.get("is_correct")
            if is_correct is not None:
                known_count += 1
                correct_count += 1 if bool(is_correct) else 0
            similar_cases.append({
                "similar_match_key": row["similar_match_key"],
                "similarity_score": row["similarity_score"],
                "home_team": _clean_display_text(row["home_team_cn"]),
                "away_team": _clean_display_text(row["away_team_cn"]),
                "match_date": row["match_date"],
                "league": _clean_display_text(row["league_name_cn"]),
                "home_goals_ft": row["home_goals_ft"],
                "away_goals_ft": row["away_goals_ft"],
                "score": row["bf_result"] or (
                    f"{row['home_goals_ft']}:{row['away_goals_ft']}"
                    if row["home_goals_ft"] is not None and row["away_goals_ft"] is not None
                    else None
                ),
                "play_type": row["case_play_type"] or outcome.get("play_type") or similarity.get("play_type"),
                "predicted_result": outcome.get("predicted_result"),
                "actual_result": outcome.get("actual_result"),
                "is_correct": None if is_correct is None else bool(is_correct),
                "attribution": outcome.get("attribution"),
                "reasons": reasons,
                "created_at": row["created_at"],
            })
        payload["similar_cases"] = similar_cases
        payload["summary"]["similar_total"] = len(similar_cases)
        payload["summary"]["similar_correct"] = correct_count
        payload["summary"]["similar_accuracy"] = (
            round(correct_count / known_count * 100, 1) if known_count else None
        )

    return payload


def parse_play_types(value: Any) -> List[str]:
    """Normalize stored play_types from JSON/list/comma text."""
    if not value:
        return []
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            parsed = [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(parsed, str):
        parsed = [part.strip() for part in parsed.split(",") if part.strip()]
    if not isinstance(parsed, list):
        return []
    normalized = []
    for item in parsed:
        pt = str(item).strip()
        if pt and pt not in normalized:
            normalized.append(pt)
    return normalized


def merge_play_types(current: List[str], extra: List[str]) -> List[str]:
    """Keep stored order while adding play types inferred from odds."""
    merged = list(current or [])
    for pt in extra:
        if pt and pt not in merged:
            merged.append(pt)
    return merged


def derive_rqspf_rec_from_odds(rqspf_odds: Optional[Dict]) -> str:
    """Fallback recommendation: lowest decimal odds = highest implied probability."""
    if not isinstance(rqspf_odds, dict):
        return ""
    labels = {"3": "让胜", "1": "让平", "0": "让负"}
    candidates = []
    for code in ("3", "1", "0"):
        try:
            odds = float(rqspf_odds.get(code))
            if odds > 1:
                candidates.append((odds, code))
        except (TypeError, ValueError):
            continue
    if not candidates:
        return ""
    _, code = min(candidates, key=lambda item: item[0])
    return labels.get(code, "")


def normalize_rqspf_rec(value: Any) -> str:
    labels = {
        "3": "让胜",
        "1": "让平",
        "0": "让负",
        "home_win": "让胜",
        "draw": "让平",
        "away_win": "让负",
    }
    if value is None:
        return ""
    raw = str(value).strip()
    return labels.get(raw, raw)


def _format_spf_result(code: Optional[str]) -> Optional[str]:
    return {"3": "主胜", "1": "平局", "0": "客胜"}.get(str(code), code) if code is not None else None


def _format_bqc_result(code: Optional[str]) -> Optional[str]:
    labels = {
        "33": "胜胜", "31": "胜平", "30": "胜负",
        "13": "平胜", "11": "平平", "10": "平负",
        "03": "负胜", "01": "负平", "00": "负负",
    }
    text_to_code = {
        "hh": "33", "hd": "31", "ha": "30",
        "dh": "13", "dd": "11", "da": "10",
        "ah": "03", "ad": "01", "aa": "00",
        "\u80dc\u80dc": "33", "\u80dc\u5e73": "31", "\u80dc\u8d1f": "30",
        "\u5e73\u80dc": "13", "\u5e73\u5e73": "11", "\u5e73\u8d1f": "10",
        "\u8d1f\u80dc": "03", "\u8d1f\u5e73": "01", "\u8d1f\u8d1f": "00",
    }
    if code is None:
        return None
    raw = str(code).strip()
    if not raw or raw.lower() in {"-", "--", "none", "null", "nan", "unknown"}:
        return None
    normalized = labels.get(raw) or labels.get(text_to_code.get(raw.lower(), "")) or labels.get(text_to_code.get(raw, ""))
    return normalized or raw



def _is_world_cup_match(match: Dict[str, Any]) -> bool:
    text = " ".join(str(match.get(key) or "") for key in (
        "league_name_cn", "league_name", "competition", "data_source"
    )).lower()
    return (
        "世界杯" in text
        or "world cup" in text
        or str(match.get("lottery_match_id") or "").startswith("wc2026_")
        or str(match.get("match_num") or "").upper().startswith("WC")
    )


def _world_cup_schedule_index() -> Optional[Dict[str, Any]]:
    try:
        from backend.app.worldcup.service import WorldCupContextService

        service = WorldCupContextService()
        context = service.get_context(live=True, include_matches=True)
        by_pair: Dict[tuple, Dict[str, Any]] = {}
        for item in context.get("matches", []):
            home = item.get("home_team") or {}
            away = item.get("away_team") or {}
            home_aliases = service._team_aliases(home) | {service._norm_name(service._display_team_name(home))}
            away_aliases = service._team_aliases(away) | {service._norm_name(service._display_team_name(away))}
            for home_key in {key for key in home_aliases if key}:
                for away_key in {key for key in away_aliases if key}:
                    by_pair[(home_key, away_key)] = item
        return {"service": service, "context": context, "by_pair": by_pair}
    except Exception as exc:
        logger.debug("world cup schedule index skipped: %s", exc)
        return None


def _world_cup_schedule_match(match: Dict[str, Any], schedule_index: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not schedule_index or not _is_world_cup_match(match):
        return None
    service = schedule_index["service"]
    home_key = service._norm_name(match.get("home_team_cn") or match.get("home_team") or "")
    away_key = service._norm_name(match.get("away_team_cn") or match.get("away_team") or "")
    return schedule_index["by_pair"].get((home_key, away_key))


def _world_cup_aliases(service: Any, team: Dict[str, Any]) -> set:
    aliases = set(service._team_aliases(team))
    for value in (
        team.get("name"),
        team.get("short_name"),
        team.get("name_cn"),
        team.get("team_name"),
        team.get("team_name_cn"),
    ):
        norm = service._norm_name(value)
        if norm:
            aliases.add(norm)
    manual = {
        "波黑": ["Bosnia & Herzegovina", "Bosnia-Herzegovina", "Bosnia and Herzegovina", "Bosnia-H."],
        "捷克": ["Czech Republic", "Czechia"],
        "韩国": ["South Korea", "Korea Republic"],
        "刚果（金）": ["D.R. Congo", "DR Congo", "Congo DR", "Democratic Republic of the Congo"],
        "刚果(金)": ["D.R. Congo", "DR Congo", "Congo DR", "Democratic Republic of the Congo"],
        "科特迪瓦": ["Ivory Coast", "Cote d'Ivoire"],
        "美国": ["USA", "United States", "United States of America"],
    }
    for key in list(manual.keys()):
        if service._norm_name(key) in aliases:
            aliases.update(service._norm_name(item) for item in manual[key])
    return {item for item in aliases if item}


def _parse_period_scores(score_details: Optional[str]) -> Dict[str, Any]:
    if not score_details:
        return {}
    text = str(score_details).strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    periods = []
    for part in text.split(","):
        if ":" not in part:
            continue
        pieces = part.strip().split(":")
        if len(pieces) != 2:
            continue
        try:
            periods.append((int(pieces[0]), int(pieces[1])))
        except ValueError:
            continue
    if not periods:
        return {}
    parsed: Dict[str, Any] = {"periods": periods, "ft": periods[0]}
    if len(periods) >= 2:
        parsed["ht"] = periods[0]
        parsed["ft"] = (periods[0][0] + periods[1][0], periods[0][1] + periods[1][1])
    return parsed


def _derive_result_labels(home_ft: int, away_ft: int, home_ht: Optional[int] = None, away_ht: Optional[int] = None) -> Dict[str, Any]:
    spf = "3" if home_ft > away_ft else ("1" if home_ft == away_ft else "0")
    result = {
        "home_goals_ft": home_ft,
        "away_goals_ft": away_ft,
        "bf_result": f"{home_ft}:{away_ft}",
        "spf_result": _format_spf_result(spf),
    }
    if home_ht is not None and away_ht is not None:
        ht = "3" if home_ht > away_ht else ("1" if home_ht == away_ht else "0")
        result["home_goals_ht"] = home_ht
        result["away_goals_ht"] = away_ht
        result["bqc_result"] = _format_bqc_result(ht + spf)
    try:
        from backend.app.lottery.services.ou_calculator import compute_ou_result

        result["ou_result"] = compute_ou_result(home_ft + away_ft, 2.5)
    except Exception:
        pass
    return result


def _derive_result_codes(
    home_ft: int,
    away_ft: int,
    home_ht: Optional[int] = None,
    away_ht: Optional[int] = None,
    handicap_line: Optional[float] = None,
    lottery_match_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Derive stored lottery result codes from a corrected score."""
    result: Dict[str, Any] = {
        "home_goals_ft": home_ft,
        "away_goals_ft": away_ft,
        "bf_result": f"{home_ft}:{away_ft}",
    }
    try:
        from backend.app.lottery.services.sync_service import _derive_play_types, _effective_handicap

        effective_handicap = _effective_handicap(DB_PATH, lottery_match_id or "", handicap_line or 0)
        result.update(_derive_play_types(home_ft, away_ft, home_ht, away_ht, effective_handicap))
    except Exception:
        spf = "3" if home_ft > away_ft else ("1" if home_ft == away_ft else "0")
        result["spf_result"] = spf
        if home_ht is not None and away_ht is not None:
            ht = "3" if home_ht > away_ht else ("1" if home_ht == away_ht else "0")
            result["home_goals_ht"] = home_ht
            result["away_goals_ht"] = away_ht
            result["bqc_result"] = ht + spf
    try:
        from backend.app.lottery.services.ou_calculator import compute_ou_result

        result["ou_result"] = compute_ou_result(home_ft + away_ft, 2.5)
    except Exception:
        pass
    return result


def _align_ou_result_to_prediction(match: Dict[str, Any]) -> None:
    """Use the card prediction line when displaying O/U actual result."""
    if not match.get("ou_rec"):
        return
    if match.get("home_goals_ft") is None or match.get("away_goals_ft") is None:
        return
    try:
        from backend.app.lottery.services.ou_calculator import compute_ou_result_from_prediction

        # For AET/AP matches, O/U settles on 90-minute goals
        end_type = match.get("match_end_type")
        h_90 = match.get("home_goals_90min")
        a_90 = match.get("away_goals_90min")
        if end_type in ("AET", "AP") and h_90 is not None and a_90 is not None:
            total_goals = int(h_90) + int(a_90)
        else:
            total_goals = int(match.get("home_goals_ft") or 0) + int(match.get("away_goals_ft") or 0)
        match["ou_result"] = compute_ou_result_from_prediction(total_goals, match.get("ou_rec"))
    except Exception:
        return


def _ensure_result_correction_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lottery_result_corrections (
            correction_id TEXT PRIMARY KEY,
            lottery_match_id TEXT NOT NULL,
            result_id TEXT,
            source TEXT NOT NULL DEFAULT 'manual',
            corrected_by TEXT,
            reason TEXT,
            before_json TEXT NOT NULL,
            after_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lottery_revalidation_queue (
            queue_id TEXT PRIMARY KEY,
            correction_id TEXT NOT NULL,
            lottery_match_id TEXT NOT NULL,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            processed_at TEXT
        )
        """
    )


def _cached_oddsfe_schedule_events(cursor, date_strs: List[str]) -> List[Dict[str, Any]]:
    """Read latest oddsfe schedule artifacts from the local evidence cache."""
    if cursor is None:
        return []

    events: List[Dict[str, Any]] = []
    for date_str in date_strs:
        try:
            row = cursor.execute(
                """
                SELECT payload_json
                FROM source_artifacts
                WHERE source_name = 'oddsfe'
                  AND entity_type = 'schedule'
                  AND entity_id = ?
                ORDER BY captured_at DESC
                LIMIT 1
                """,
                (date_str,),
            ).fetchone()
        except sqlite3.Error:
            continue

        if not row:
            continue
        try:
            payload = json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            continue

        if isinstance(payload, dict):
            payload = payload.get("data") or payload.get("events") or []
        if not isinstance(payload, list):
            continue

        for event in payload:
            if isinstance(event, dict):
                cached_event = dict(event)
                cached_event.setdefault("_score_source", "oddsfe_schedule_cache")
                events.append(cached_event)

    return events


def _cached_oddsfe_event_detail(cursor, event_id: str) -> Optional[Dict[str, Any]]:
    """Read latest oddsfe event detail artifact from the local evidence cache."""
    if cursor is None or not event_id:
        return None
    try:
        row = cursor.execute(
            """
            SELECT payload_json
            FROM source_artifacts
            WHERE source_name = 'oddsfe'
              AND entity_type = 'event'
              AND entity_id = ?
            ORDER BY captured_at DESC
            LIMIT 1
            """,
            (str(event_id),),
        ).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    try:
        payload = json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict):
        payload["_score_source"] = "oddsfe_event_cache"
        return payload
    return None





def _apply_world_cup_time_correction(match: Dict[str, Any], schedule_index: Optional[Dict[str, Any]]) -> None:
    """Use World Cup UTC fixtures for display time, keeping raw lottery fields as evidence."""
    schedule_match = _world_cup_schedule_match(match, schedule_index)
    if not schedule_match or not schedule_match.get("beijing_time"):
        return

    raw_beijing_time = match.get("beijing_time")
    raw_match_date = match.get("match_date")
    raw_match_time = match.get("match_time")
    corrected_beijing_time = schedule_match["beijing_time"]
    corrected_date = corrected_beijing_time[:10]
    corrected_time = corrected_beijing_time[11:19]

    # Always preserve original lottery date for grouping, even if time already matches
    if raw_match_date and raw_match_date != corrected_date:
        match["source_match_date"] = raw_match_date
        match["time_corrected"] = True

    if raw_beijing_time and raw_beijing_time[:16] != corrected_beijing_time[:16]:
        match["source_beijing_time"] = raw_beijing_time
        match["source_match_time"] = raw_match_time
        match["data_quality_note"] = (
            "已按世界杯赛程 UTC→北京时间校正展示时间；体彩原始时间保留在 source_* 字段。"
        )

    match["match_id"] = match.get("match_id") or schedule_match.get("match_id")
    match["match_date"] = corrected_date
    match["match_time"] = corrected_time
    match["beijing_time"] = corrected_beijing_time
    match["display_timezone"] = "Asia/Shanghai"
    match["time_basis"] = "world_cup_utc_converted_to_beijing"
    match["world_cup_match_id"] = schedule_match.get("match_id")
    match["world_cup_matchday"] = schedule_match.get("matchday")
    match["world_cup_group"] = schedule_match.get("group")
    match["world_cup_source_date"] = schedule_match.get("source_date")
    match["world_cup_source_time"] = schedule_match.get("source_time")
    match["source_utc_date"] = schedule_match.get("utc_date")


def _display_match_date(match: Dict[str, Any]) -> str:
    # Use original match_date for date grouping (lottery sell date),
    # not corrected beijing_time which may shift to a different calendar day
    return str(match.get("source_match_date") or match.get("match_date") or match.get("beijing_time") or "")[:10]


def _now_beijing_naive() -> datetime:
    try:
        from backend.app.core.time_utils import now_beijing

        return now_beijing().replace(tzinfo=None)
    except Exception:
        return datetime.now()


def _estimated_runtime_minutes(match: Optional[Dict[str, Any]] = None) -> int:
    """Estimate when a football match should stop showing as live.

    Normal group/league match: 90 + 15 halftime + stoppage/buffer ~= 130 min.
    Knockout match with extra time/penalties: allow a longer 185 min window.
    """
    match = match or {}
    text = " ".join(str(match.get(key) or "") for key in (
        "league_name_cn", "league_name", "stage", "world_cup_stage", "round_stage"
    )).lower()
    match_date = str(match.get("match_date") or (match.get("beijing_time") or "")[:10] or "")

    knockout_markers = (
        "knockout", "round_of_32", "round_of_16", "quarter", "semi", "final",
        "淘汰", "决赛", "半决赛", "1/4", "1/8", "32强", "16强"
    )
    if any(marker in text for marker in knockout_markers):
        return 185
    if ("世界杯" in text or "world cup" in text) and match_date >= "2026-06-28":
        return 185
    return 130


def _status_from_beijing_time(
    beijing_time: Optional[str],
    default_status: str = "scheduled",
    match: Optional[Dict[str, Any]] = None,
) -> str:
    if not beijing_time:
        return default_status
    try:
        match_dt = datetime.strptime(beijing_time[:16], "%Y-%m-%d %H:%M")
        now = _now_beijing_naive()
        if now <= match_dt:
            return default_status
        minutes_since = (now - match_dt).total_seconds() / 60
        return "finished_pending" if minutes_since > _estimated_runtime_minutes(match) else "started"
    except (TypeError, ValueError):
        return default_status




def _safe_json_loads(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _load_intelligence_index(
    cursor,
    target_date: str,
    lottery_match_ids: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Load intelligence package status keyed by lottery_match_id."""
    if not get_table_columns(cursor, "intelligence_jobs"):
        return {}
    ids = [str(item) for item in (lottery_match_ids or []) if item]
    id_clause = ""
    params: List[Any] = [target_date]
    if ids:
        id_clause = f" OR j.lottery_match_id IN ({','.join(['?'] * len(ids))})"
        params.extend(ids)
    package_cols = get_table_columns(cursor, "intelligence_packages")
    if package_cols:
        rows = cursor.execute(
            f"""
            SELECT j.lottery_match_id, j.job_id, j.status,
                   p.completeness, p.missing_required_json, p.updated_at AS package_updated_at
            FROM intelligence_jobs j
            LEFT JOIN intelligence_packages p ON p.job_id = j.job_id
            WHERE j.match_date = ?{id_clause}
              AND j.lottery_match_id IS NOT NULL
            """,
            params,
        ).fetchall()
    else:
        rows = cursor.execute(
            f"""
            SELECT lottery_match_id, job_id, status,
                   NULL AS completeness, NULL AS missing_required_json, NULL AS package_updated_at
            FROM intelligence_jobs
            WHERE match_date = ?{id_clause.replace('j.', '')}
              AND lottery_match_id IS NOT NULL
            """,
            params,
        ).fetchall()

    index: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        missing_required = _safe_json_loads(row["missing_required_json"], []) or []
        index[str(row["lottery_match_id"])] = {
            "job_id": row["job_id"],
            "status": row["status"],
            "completeness": row["completeness"],
            "missing_required": missing_required,
            "package_updated_at": row["package_updated_at"],
            "has_package": row["package_updated_at"] is not None or row["completeness"] is not None,
        }
    return index


def _latest_oddsfe_event_artifacts(cursor, event_ids: List[str]) -> set:
    if not event_ids or not get_table_columns(cursor, "source_artifacts"):
        return set()
    placeholders = ",".join(["?"] * len(event_ids))
    rows = cursor.execute(
        f"""
        SELECT DISTINCT entity_id
        FROM source_artifacts
        WHERE source_name = 'oddsfe'
          AND entity_type = 'event'
          AND entity_id IN ({placeholders})
        """,
        event_ids,
    ).fetchall()
    return {str(row[0]) for row in rows if row[0] is not None}


def _latest_oddsfe_ou_line_events(cursor, event_ids: List[str]) -> set:
    if not event_ids or not get_table_columns(cursor, "oddsfe_matches"):
        return set()
    cols = get_table_columns(cursor, "oddsfe_matches")
    if "event_id" not in cols or "ou_pinnacle_line" not in cols:
        return set()
    placeholders = ",".join(["?"] * len(event_ids))
    rows = cursor.execute(
        f"""
        SELECT DISTINCT event_id
        FROM oddsfe_matches
        WHERE CAST(event_id AS TEXT) IN ({placeholders})
          AND ou_pinnacle_line IS NOT NULL
          AND ou_pinnacle_line != ''
          AND ou_pinnacle_over IS NOT NULL
          AND ou_pinnacle_over != ''
          AND ou_pinnacle_under IS NOT NULL
          AND ou_pinnacle_under != ''
        """,
        event_ids,
    ).fetchall()
    return {str(row[0]) for row in rows if row[0] is not None}


def _load_validation_index(cursor, lottery_match_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not lottery_match_ids or not get_table_columns(cursor, "lottery_validation"):
        return {}
    placeholders = ",".join(["?"] * len(lottery_match_ids))
    rows = cursor.execute(
        f"""
        SELECT lottery_match_id, COUNT(*) AS total,
               GROUP_CONCAT(DISTINCT play_type) AS play_types,
               MAX(validated_at) AS latest_validated_at
        FROM lottery_validation
        WHERE lottery_match_id IN ({placeholders})
        GROUP BY lottery_match_id
        """,
        lottery_match_ids,
    ).fetchall()
    return {
        str(row["lottery_match_id"]): {
            "total": int(row["total"] or 0),
            "play_types": [item for item in str(row["play_types"] or "").split(",") if item],
            "latest_validated_at": row["latest_validated_at"],
        }
        for row in rows
        if row["lottery_match_id"] is not None
    }


def _load_post_review_index(cursor, lottery_match_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not lottery_match_ids or not get_table_columns(cursor, "post_match_reviews"):
        return {}
    placeholders = ",".join(["?"] * len(lottery_match_ids))
    rows = cursor.execute(
        f"""
        SELECT match_key, COUNT(*) AS total, MAX(created_at) AS latest_review_at
        FROM post_match_reviews
        WHERE match_key IN ({placeholders})
        GROUP BY match_key
        """,
        lottery_match_ids,
    ).fetchall()
    return {
        str(row["match_key"]): {
            "total": int(row["total"] or 0),
            "latest_review_at": row["latest_review_at"],
        }
        for row in rows
        if row["match_key"] is not None
    }


def _collection_run_status(cursor, run_type: str, limit: int = 5) -> Dict[str, Any]:
    if not get_table_columns(cursor, "collection_runs"):
        return {"running": 0, "latest": []}
    running = cursor.execute(
        """
        SELECT COUNT(*)
        FROM collection_runs
        WHERE run_type = ?
          AND status = 'running'
        """,
        (run_type,),
    ).fetchone()[0]
    latest = cursor.execute(
        """
        SELECT run_id, trigger_source, run_type, match_date, status,
               started_at, finished_at, summary_json, error
        FROM collection_runs
        WHERE run_type = ?
        ORDER BY started_at DESC
        LIMIT ?
        """,
        (run_type, limit),
    ).fetchall()
    return {
        "running": running,
        "latest": [dict(row) for row in latest],
    }


def _is_result_due(match: Dict[str, Any]) -> bool:
    status = str(match.get("match_status") or match.get("sell_status") or "").lower()
    return status in {"finished", "finished_pending"}


def _compute_analysis_status(match: Dict[str, Any]) -> str:
    """Compute a human-readable analysis status for frontend display.

    Returns one of:
      analysis_done       — analysis exists and is current
      analysis_stale      — analysis exists but stale (new data arrived)
      missing_odds        — cannot analyze without odds
      missing_ou          — missing O/U line (partial analysis possible)
      analysis_ready      — data available, waiting for analysis
      waiting_result      — match finished, waiting for score
      validated           — analysis validated against result
      new_match           — just synced, no processing yet
    """
    has_analysis = bool(match.get('has_analysis'))
    has_odds = bool(match.get('spf_odds') or match.get('rqspf_odds'))
    has_ou = bool(match.get('has_ou_line'))
    has_score = match.get('home_goals_ft') is not None
    match_status = str(match.get('match_status') or match.get('sell_status') or '').lower()
    is_finished = match_status in ('finished', 'finished_pending')

    if is_finished and has_score and has_analysis:
        return 'validated'
    if is_finished and not has_score:
        return 'waiting_result'
    if has_analysis:
        return 'analysis_done'
    if not has_odds:
        return 'missing_odds'
    if not has_ou:
        return 'missing_ou'
    if has_odds:
        return 'analysis_ready'
    return 'new_match'


def _build_completeness_row(
    match: Dict[str, Any],
    intel: Optional[Dict[str, Any]],
    event_cache_ids: set,
    ou_line_event_ids: Optional[set] = None,
    validation: Optional[Dict[str, Any]] = None,
    post_review: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    event_id = str(match.get("oddsfe_event_id") or "")
    is_schedule_fallback = bool(match.get("is_schedule_fallback"))
    has_odds = bool(match.get("spf_odds") or match.get("rqspf_odds") or match.get("odds"))
    has_score = match.get("home_goals_ft") is not None and match.get("away_goals_ft") is not None
    has_half = match.get("home_goals_ht") is not None and match.get("away_goals_ht") is not None
    has_analysis = bool(match.get("has_analysis"))
    has_intel = bool(intel and intel.get("has_package"))
    has_event_cache = bool(event_id and event_id in event_cache_ids) or match.get("score_source") == "oddsfe_event_cache"
    has_ou_line = bool(event_id and event_id in (ou_line_event_ids or set()))
    has_validation = bool(validation and validation.get("total"))
    has_post_review = bool(post_review and post_review.get("total"))
    result_due = _is_result_due(match)

    missing: List[str] = []
    actions: List[str] = []
    if not is_schedule_fallback and not has_odds:
        missing.append("odds")
        actions.append("collect_odds")
    if not is_schedule_fallback and result_due and not has_score:
        missing.append("score")
        if event_id:
            actions.append("sync_event_detail")
    if not is_schedule_fallback and result_due and not has_half:
        missing.append("half_score")
        if event_id and "sync_event_detail" not in actions:
            actions.append("sync_event_detail")
    if not is_schedule_fallback and not has_analysis:
        missing.append("analysis")
        actions.append("analyze")
    if not is_schedule_fallback and not has_intel:
        missing.append("intelligence")
        actions.append("collect_intelligence")
    if not is_schedule_fallback and result_due and has_score and has_analysis and not has_validation:
        missing.append("validation")
        actions.append("validate")
    if not is_schedule_fallback and result_due and has_score and has_validation and not has_post_review:
        missing.append("post_review")
        actions.append("refresh_learning")

    quality_flags = []
    if event_id and not has_event_cache:
        quality_flags.append("oddsfe_event_not_cached")
        if not is_schedule_fallback and "sync_event_detail" not in actions:
            actions.append("sync_event_detail")
    if is_schedule_fallback:
        quality_flags.append("world_cup_schedule_fallback")
    if match.get("time_corrected"):
        quality_flags.append("world_cup_time_corrected")
    if event_id and not has_ou_line and not is_schedule_fallback:
        quality_flags.append("oddsfe_ou_line_missing")
        if "sync_ou_line" not in actions:
            actions.append("sync_ou_line")

    return {
        "lottery_match_id": match.get("lottery_match_id"),
        "match_num": match.get("match_num"),
        "league_name_cn": match.get("league_name_cn"),
        "home_team_cn": match.get("home_team_cn"),
        "away_team_cn": match.get("away_team_cn"),
        "beijing_time": match.get("beijing_time"),
        "match_status": match.get("match_status") or match.get("sell_status"),
        "oddsfe_event_id": event_id or None,
        "is_schedule_fallback": is_schedule_fallback,
        "result_due": result_due,
        "has_odds": has_odds,
        "has_score": has_score,
        "has_half_score": has_half,
        "has_analysis": has_analysis,
        "has_intelligence": has_intel,
        "has_event_cache": has_event_cache,
        "has_ou_line": has_ou_line,
        "has_validation": has_validation,
        "has_post_review": has_post_review,
        "missing": missing,
        "next_actions": actions,
        "quality_flags": quality_flags,
        "intelligence": intel or None,
        "validation": validation or None,
        "post_review": post_review or None,
        "score_source": match.get("score_source"),
    }


GAP_ACTION_META: Dict[str, Dict[str, Any]] = {
    "sync_event_detail": {
        "label": "同步oddsfe证据",
        "auto_job": "rolling_collection / historical_backfill",
        "priority": 10,
        "detail": "补赛程、赛果、半场和原始API证据",
    },
    "sync_ou_line": {
        "label": "补真实大小球盘",
        "auto_job": "rolling_collection / historical_backfill",
        "priority": 15,
        "detail": "按 oddsfe event_id 补 Pinnacle O/U 盘口，并触发分析重算",
    },
    "collect_odds": {
        "label": "补赔率盘口",
        "auto_job": "rolling_collection",
        "priority": 20,
        "detail": "补胜平负、让球、大小球盘口",
    },
    "analyze": {
        "label": "生成/重算分析",
        "auto_job": "rolling_collection / historical_backfill",
        "priority": 30,
        "detail": "缺分析或情报更新后重新计算",
    },
    "collect_intelligence": {
        "label": "补情报包",
        "auto_job": "intelligence_gap_fill",
        "priority": 40,
        "detail": "补天气、新闻、伤停、预计阵容等证据",
    },
    "validate": {
        "label": "赛后验证",
        "auto_job": "validate_cycle / historical_backfill",
        "priority": 50,
        "detail": "有赛果后验证预测正确/错误",
    },
    "refresh_learning": {
        "label": "沉淀学习库",
        "auto_job": "learning_refresh",
        "priority": 60,
        "detail": "生成复盘归因和相似历史案例",
    },
}


def _build_gap_plan(
    rows: List[Dict[str, Any]],
    action_counts: Dict[str, int],
    max_examples: int = 5,
) -> List[Dict[str, Any]]:
    plan = []
    for action, count in action_counts.items():
        meta = GAP_ACTION_META.get(action, {})
        examples = []
        for row in rows:
            if action not in (row.get("next_actions") or []):
                continue
            examples.append({
                "lottery_match_id": row.get("lottery_match_id"),
                "match_num": row.get("match_num"),
                "teams": f"{row.get('home_team_cn') or '-'} vs {row.get('away_team_cn') or '-'}",
                "beijing_time": row.get("beijing_time"),
                "match_status": row.get("match_status"),
                "missing": row.get("missing") or [],
                "quality_flags": row.get("quality_flags") or [],
            })
            if len(examples) >= max_examples:
                break
        plan.append({
            "action": action,
            "label": meta.get("label", action),
            "count": int(count or 0),
            "auto_job": meta.get("auto_job", "scheduler"),
            "priority": int(meta.get("priority", 999)),
            "detail": meta.get("detail", ""),
            "examples": examples,
        })
    plan.sort(key=lambda item: (item["priority"], -item["count"], item["action"]))
    return plan


def get_oddsfe_ou_line(oddsfe_event_id: str) -> Optional[Dict]:
    """从oddsfe获取Pinnacle大小球盘口线数据

    优先从展开列(OVER_UNDER_prematch_PINNACLE_line/over/under)读取，
    如果为空则解析OVER_UNDER_prematch_lines字段。
    返回: {'line': float, 'over_odds': float, 'under_odds': float}
    """
    if not oddsfe_event_id:
        return None
    try:
        conn = sqlite3.connect(ODDSFE_DB_PATH)
        c = conn.cursor()

        # Priority 1: 展开列 (由oddsfe_ou_concurrent直接写入)
        c.execute("""SELECT OVER_UNDER_prematch_PINNACLE_line,
                            OVER_UNDER_prematch_PINNACLE_over,
                            OVER_UNDER_prematch_PINNACLE_under
            FROM oddsfe WHERE event_id=?""",
            (str(oddsfe_event_id),))
        row = c.fetchone()
        if row and row[0] and row[1] and row[2]:
            try:
                line = float(row[0])
                over = float(row[1])
                under = float(row[2])
                if line > 0 and over > 1 and under > 1:
                    conn.close()
                    return {
                        'line': line,
                        'over_odds': over,
                        'under_odds': under,
                        'over_prob': 1 / over if over > 0 else 0,
                        'under_prob': 1 / under if under > 0 else 0,
                        'all_lines': {str(line): {'over': over, 'under': under}},
                    }
            except (ValueError, TypeError):
                pass

        # Priority 2: 解析OVER_UNDER_prematch_lines字段
        c.execute("""SELECT OVER_UNDER_prematch_lines FROM oddsfe
            WHERE event_id=? AND OVER_UNDER_prematch_lines IS NOT NULL
            AND OVER_UNDER_prematch_lines != ''""",
            (str(oddsfe_event_id),))
        row = c.fetchone()
        conn.close()
        if not row or not row[0]:
            return None

        lines_str = row[0]
        # 解析格式: line:over/under:volume|bookmaker:over:under:timestamp;...
        # 找Pinnacle的数据
        pinnacle_data = {}  # {line_val: {'over': odds, 'under': odds}}
        for segment in lines_str.split('||'):
            if not segment.strip():
                continue
            parts = segment.split('|')
            line_info = parts[0]
            line_parts = line_info.split(':')
            line_val = line_parts[0]

            # 找Pinnacle在bookmaker数据中
            for bm in parts[1:]:
                bm_parts = bm.split(':')
                if len(bm_parts) >= 3 and bm_parts[0] == 'PINNACLE':
                    pinnacle_data[line_val] = {
                        'over': float(bm_parts[1]),
                        'under': float(bm_parts[2])
                    }

        if not pinnacle_data:
            # Fallback: 从line_info中取（默认盘口线）
            for segment in lines_str.split('||'):
                if not segment.strip():
                    continue
                parts = segment.split('|')
                line_info = parts[0]
                line_parts = line_info.split(':')
                line_val = line_parts[0]
                ou_str = line_parts[1] if len(line_parts) > 1 else ''
                over_under = ou_str.split('/')
                if len(over_under) >= 2:
                    pinnacle_data[line_val] = {
                        'over': float(over_under[0]),
                        'under': float(over_under[1])
                    }

        if not pinnacle_data:
            return None

        # 选最佳盘口线: over和under赔率差距最小的(盘口定价最精准)
        best_line = None
        best_gap = float('inf')
        for line_val, odds in pinnacle_data.items():
            try:
                line = float(line_val)
                gap = abs(odds['over'] - odds['under'])
                if gap < best_gap:
                    best_gap = gap
                    best_line = line
                    best_over = odds['over']
                    best_under = odds['under']
            except (ValueError, KeyError):
                continue

        if best_line is None:
            return None

        return {
            'line': best_line,
            'over_odds': best_over,
            'under_odds': best_under,
            'over_prob': 1 / best_over if best_over > 0 else 0,
            'under_prob': 1 / best_under if best_under > 0 else 0,
            'all_lines': pinnacle_data
        }
    except Exception as e:
        logger.debug(f'oddsfe O/U查询失败: {e}')
        return None


# ==================== 比赛列表 ====================

@router.get("/matches")
async def get_lottery_matches(
    date: Optional[str] = Query(None, description="日期 (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="销售状态 (selling/stopped/closed)"),
    play_type: Optional[str] = Query(None, description="玩法筛选 (spf/bf/bqc/rqspf)"),
    league: Optional[str] = Query(None, description="联赛筛选 (league_name_cn)"),
    include_all: bool = Query(False, description="包含非体彩在售联赛(默认仅核心联赛)"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    获取体彩开售比赛列表
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        query = "SELECT * FROM lottery_matches WHERE 1=1"
        params = []

        # 默认只展示体彩核心在售联赛, 其他联赛(oddsfe采集的非常规联赛)继续
        # 在后端跑分析/赛果复盘/模型训练, 但不显示在体彩中心。
        if not include_all:
            placeholders = ",".join(["?" for _ in LOTTERY_CORE_LEAGUES])
            query += f" AND league_name_cn IN ({placeholders})"
            params.extend(sorted(LOTTERY_CORE_LEAGUES))

        if date:
            # Filter by Beijing-time date (single day). beijing_time is stored
            # as 'YYYY-MM-DD HH:MM:SS' so substr(..,1,10) gives the Beijing date.
            # If beijing_time is NULL, fall back to match_date.
            query += """
            AND (
                substr(beijing_time, 1, 10) = ?
                OR (beijing_time IS NULL AND match_date = ?)
            )
            """
            params.extend([date, date])
        else:
            # 默认今天和未来7天 (based on beijing_time or match_date)
            # beijing_time is stored in Beijing time, so compare against Beijing now
            from backend.app.core.time_utils import now_beijing
            from datetime import timedelta as _td
            bj_cutoff = (now_beijing() - _td(hours=6)).strftime('%Y-%m-%d %H:%M:%S')
            bj_today = now_beijing().strftime('%Y-%m-%d')
            query += " AND (beijing_time >= ? OR (beijing_time IS NULL AND match_date >= ?))"
            params.extend([bj_cutoff, bj_today])

        if status:
            query += " AND sell_status = ?"
            params.append(status)

        if league:
            query += " AND league_name_cn = ?"
            params.append(league)

        query += " ORDER BY CASE WHEN beijing_time IS NOT NULL THEN beijing_time ELSE match_date || ' ' || COALESCE(match_time, '99:99') END ASC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        raw_matches = [dict(row) for row in cursor.fetchall()]

        # Dedup: same (home, away, date) from different sources → keep latest
        seen_keys = {}
        matches = []
        for match in raw_matches:
            home = (match.get('home_team_cn') or '').strip()
            away = (match.get('away_team_cn') or '').strip()
            mdate = match.get('match_date') or ''
            key = (home, away, mdate)
            if key in seen_keys:
                # Keep the one with oddsfe_event_id (preferred) or later created_at
                prev_idx = seen_keys[key]
                prev = matches[prev_idx]
                prev_has_eid = bool(prev.get('oddsfe_event_id'))
                cur_has_eid = bool(match.get('oddsfe_event_id'))
                if cur_has_eid and not prev_has_eid:
                    matches[prev_idx] = match
                continue
            seen_keys[key] = len(matches)
            matches.append(match)

        # 补全beijing_time: 体彩match_date+match_time就是北京时间
        # 如果beijing_time为空或与match_date+match_time不一致，用match_date+match_time
        for match in matches:
            md = match.get('match_date', '')
            mt = match.get('match_time', '')
            if md and mt:
                mt_short = mt[:5] if len(mt) > 5 else mt
                derived_bt = f"{md} {mt_short}"
                if not match.get('beijing_time'):
                    match['beijing_time'] = derived_bt

        world_cup_index = _world_cup_schedule_index()
        for match in matches:
            _apply_world_cup_time_correction(match, world_cup_index)

        if date:
            matches = [match for match in matches if _display_match_date(match) == date]

        # 队名中文化: 英文名→中文名
        try:
            from backend.app.core.name_service import NameService
            ns = NameService()
            for match in matches:
                h_cn = match.get('home_team_cn') or ''
                a_cn = match.get('away_team_cn') or ''
                if h_cn and not ns.is_chinese(h_cn):
                    translated = ns.to_cn(h_cn)
                    if translated:
                        match['home_team_cn'] = translated
                if a_cn and not ns.is_chinese(a_cn):
                    translated = ns.to_cn(a_cn)
                    if translated:
                        match['away_team_cn'] = translated
        except Exception as e:
            import logging
            logging.getLogger(__name__).error('NameService translation failed: %s', e)

        # 处理 play_types JSON，并检查分析状态
        analyzed_ids = set()
        report_cols = get_table_columns(cursor, "lottery_analysis_reports")
        stale_filter_analyzed = "AND COALESCE(is_stale, 0) = 0" if "is_stale" in report_cols else ""
        cursor.execute(f"SELECT DISTINCT lottery_match_id FROM lottery_analysis_reports WHERE report_type IN ('prediction', 'full') {stale_filter_analyzed}")
        for row in cursor.fetchall():
            analyzed_ids.add(row[0])
        # Also include matches that have predictions in lottery_predictions table
        pred_cols = get_table_columns(cursor, "lottery_predictions")
        if pred_cols:
            cursor.execute("SELECT DISTINCT lottery_match_id FROM lottery_predictions")
            for row in cursor.fetchall():
                analyzed_ids.add(row[0])

        # 获取已结束比赛的结果数据
        result_ids = set()
        results_map = {}
        result_columns = get_table_columns(cursor, 'lottery_results')
        result_select = ", ".join([
            column_or_null(result_columns, 'lottery_match_id'),
            column_or_null(result_columns, 'home_goals_ft'),
            column_or_null(result_columns, 'away_goals_ft'),
            column_or_null(result_columns, 'home_goals_ht'),
            column_or_null(result_columns, 'away_goals_ht'),
            column_or_null(result_columns, 'spf_result'),
            column_or_null(result_columns, 'bf_result'),
            column_or_null(result_columns, 'bqc_result'),
            column_or_null(result_columns, 'rqspf_result'),
            column_or_null(result_columns, 'ou_result'),
            column_or_null(result_columns, 'home_goals_90min'),
            column_or_null(result_columns, 'away_goals_90min'),
            column_or_null(result_columns, 'match_end_type'),
            column_or_null(result_columns, 'penalty_home'),
            column_or_null(result_columns, 'penalty_away'),
        ])
        result_order = []
        if 'updated_at' in result_columns:
            result_order.append("COALESCE(updated_at, '') DESC")
        if 'created_at' in result_columns:
            result_order.append("COALESCE(created_at, '') DESC")
        if 'draw_time' in result_columns:
            result_order.append("COALESCE(draw_time, '') DESC")
        if 'result_id' in result_columns:
            result_order.append("COALESCE(result_id, 0) DESC")
        result_order.append("rowid DESC")
        cursor.execute(
            f"SELECT rowid AS _rowid, {result_select} FROM lottery_results "
            f"ORDER BY lottery_match_id ASC, {', '.join(result_order)}"
        )
        for row in cursor.fetchall():
            lottery_match_id = row[1]
            if not lottery_match_id or lottery_match_id in results_map:
                continue
            result_ids.add(lottery_match_id)
            results_map[lottery_match_id] = {
                'home_goals_ft': row[2],
                'away_goals_ft': row[3],
                'home_goals_ht': row[4],
                'away_goals_ht': row[5],
                'spf_result': row[6],
                'bf_result': row[7],
                'bqc_result': row[8],
                'rqspf_result': row[9],
                'ou_result': row[10],
                'home_goals_90min': row[11],
                'away_goals_90min': row[12],
                'match_end_type': row[13],
                'penalty_home': row[14],
                'penalty_away': row[15],
            }

        # 获取SPF/RQSPF/OU赔率(最新一条)
        odds_map = {}
        cursor.execute("""
            SELECT lottery_match_id, play_type, odds_data FROM lottery_odds o1
            WHERE play_type IN ('spf', 'rqspf', 'ou')
            AND update_time = (
                SELECT MAX(update_time) FROM lottery_odds o2
                WHERE o2.lottery_match_id = o1.lottery_match_id AND o2.play_type = o1.play_type
            )
        """)
        for row in cursor.fetchall():
            mid, pt, od = row[0], row[1], row[2]
            if mid not in odds_map:
                odds_map[mid] = {}
            try:
                odds_map[mid][pt] = json.loads(od)
            except:
                pass

        for match in matches:
            match['play_types'] = parse_play_types(match.get('play_types'))

            # play_types为空时从lottery_odds推断
            if not match['play_types']:
                cursor.execute("""
                    SELECT DISTINCT play_type FROM lottery_odds
                    WHERE lottery_match_id = ?
                """, (match['lottery_match_id'],))
                odds_types = [r[0] for r in cursor.fetchall()]
                if odds_types:
                    match['play_types'] = odds_types

            # 添加分析状态
            match['has_analysis'] = match['lottery_match_id'] in analyzed_ids

            # 添加赔率
            match_odds = odds_map.get(match['lottery_match_id'], {})
            if match_odds.get('spf'):
                match['spf_odds'] = match_odds['spf']
            if match_odds.get('rqspf'):
                match['rqspf_odds'] = match_odds['rqspf']
            match['play_types'] = merge_play_types(match['play_types'], list(match_odds.keys()))

            # 添加比赛结果
            if match['lottery_match_id'] in results_map:
                result = results_map[match['lottery_match_id']]
                match['home_goals_ft'] = result['home_goals_ft']
                match['away_goals_ft'] = result['away_goals_ft']
                match['home_goals_ht'] = result['home_goals_ht']
                match['away_goals_ht'] = result['away_goals_ht']
                match['home_goals_90min'] = result.get('home_goals_90min')
                match['away_goals_90min'] = result.get('away_goals_90min')
                match['match_end_type'] = result.get('match_end_type')
                match['penalty_home'] = result.get('penalty_home')
                match['penalty_away'] = result.get('penalty_away')
                match['bf_result'] = result['bf_result']
                # 已有结果的比赛标记为 finished
                match['match_status'] = 'finished'

                # 从比分计算中文赛果(所有已结束比赛统一处理)
                h_ft = result['home_goals_ft']
                a_ft = result['away_goals_ft']
                h_ht = result['home_goals_ht']
                a_ht = result['away_goals_ht']
                h_90 = result.get('home_goals_90min')
                a_90 = result.get('away_goals_90min')
                end_type = result.get('match_end_type') or 'FT'
                handicap = match.get('handicap_line', 0) or 0

                # For SPF/BQC/OU: use 90min scores (AET/AP settle on 90min)
                spf_h = h_90 if h_90 is not None else h_ft
                spf_a = a_90 if a_90 is not None else a_ft

                if h_ft is not None and a_ft is not None:
                    # For AET/AP: derive SPF/BQC from 90min scores, not from DB spf_result
                    if end_type in ('AET', 'AP') and h_90 is not None and a_90 is not None:
                        spf_code = '3' if h_90 > a_90 else ('1' if h_90 == a_90 else '0')
                    else:
                        spf_code = result.get('spf_result') or ('3' if h_ft > a_ft else ('1' if h_ft == a_ft else '0'))
                    spf_map = {'3': '主胜', '1': '平局', '0': '客胜'}
                    match['spf_result'] = spf_map.get(spf_code, spf_code)

                    # Score display for AET/AP: structured period data
                    if end_type in ('AET', 'AP') and h_90 is not None and a_90 is not None:
                        et_h = (h_ft - h_90) if (h_ft is not None and h_90 is not None) else None
                        et_a = (a_ft - a_90) if (a_ft is not None and a_90 is not None) else None
                        pen_h = result.get('penalty_home')
                        pen_a = result.get('penalty_away')
                        match['score_display'] = f"{h_90}-{a_90}"
                        score_detail = {
                            'regular': f"{h_90}-{a_90}",
                            'ht': f"{h_ht}-{a_ht}" if h_ht is not None and a_ht is not None else None,
                            'second_half': f"{h_90 - (h_ht or 0)}-{a_90 - (a_ht or 0)}" if h_ht is not None and a_ht is not None else None,
                            'extra_time': f"{et_h}-{et_a}" if et_h is not None and et_a is not None else None,
                            'aggregate': f"{h_ft}-{a_ft}",
                            'end_type': end_type,
                        }
                        if pen_h is not None and pen_a is not None:
                            score_detail['penalties'] = f"{pen_h}-{pen_a}"
                        match['score_detail'] = score_detail
                    else:
                        match['score_display'] = f"{h_ft}-{a_ft}"
                        match['score_detail'] = None

                    # RQSPF: use 90min scores for AET/AP
                    rqspf_odds_data = match_odds.get('rqspf', {})
                    goal_line_str = rqspf_odds_data.get('goal_line', '') if rqspf_odds_data else ''
                    if goal_line_str:
                        try:
                            gl_val = float(goal_line_str)
                            h_adj = spf_h + gl_val
                        except ValueError:
                            h_adj = spf_h - handicap
                    else:
                        h_adj = spf_h - handicap
                    if h_adj > spf_a:
                        match['rqspf_result'] = '让胜'
                    elif h_adj == spf_a:
                        match['rqspf_result'] = '让平'
                    else:
                        match['rqspf_result'] = '让负'

                    # BQC: use 90min for FT direction, HT unchanged
                    if h_ht is not None and a_ht is not None:
                        ht_code = '3' if h_ht > a_ht else ('1' if h_ht == a_ht else '0')
                        ft_code = '3' if spf_h > spf_a else ('1' if spf_h == spf_a else '0')
                        match['bqc_result'] = _format_bqc_result(ht_code + ft_code)
                    elif result.get('bqc_result'):
                        match['bqc_result'] = _format_bqc_result(result['bqc_result'])

                    # 大小球赛果 — AET/AP用90min进球数, FT用DB值或重新计算
                    if end_type in ('AET', 'AP') and h_90 is not None and a_90 is not None:
                        from backend.app.lottery.services.ou_calculator import compute_ou_result
                        total_90 = h_90 + a_90
                        ou_line = 2.5
                        # Try to get actual O/U line from odds
                        ou_odds = match_odds.get('ou', {})
                        if ou_odds:
                            goal_line = ou_odds.get('goal_line', '')
                            if goal_line:
                                try:
                                    ou_line = float(goal_line)
                                except ValueError:
                                    pass
                        match['ou_result'] = compute_ou_result(total_90, ou_line)
                    elif result.get('ou_result'):
                        match['ou_result'] = result['ou_result']
                    else:
                        total_goals = spf_h + spf_a
                        from backend.app.lottery.services.ou_calculator import compute_ou_result
                        match['ou_result'] = compute_ou_result(total_goals, 2.5)
                else:
                    match['spf_result'] = result['spf_result']
                    match['rqspf_result'] = result['rqspf_result']
                    match['bqc_result'] = result['bqc_result']
            else:
                # 根据时间判断状态：如果比赛时间已过，标记为 started 或 finished_pending
                status_guess = _status_from_beijing_time(match.get('beijing_time'), None, match)
                if status_guess:
                    match['match_status'] = status_guess

            # 裁剪match_time: "03:00:00" -> "03:00"
            if match.get('match_time') and len(match['match_time']) > 5:
                match['match_time'] = match['match_time'][:5]

            # 如果有分析，获取简要推荐信息
            if match['has_analysis']:
                report_cols = get_table_columns(cursor, "lottery_analysis_reports")
                stale_filter = "AND COALESCE(is_stale, 0) = 0" if "is_stale" in report_cols else ""
                cursor.execute(f"""
                    SELECT report_data FROM lottery_analysis_reports
                    WHERE lottery_match_id = ? AND report_type IN ('prediction', 'full')
                    {stale_filter}
                    ORDER BY datetime(created_at) DESC, rowid DESC
                    LIMIT 1
                """, (match['lottery_match_id'],))
                report_row = cursor.fetchone()
                if report_row:
                    try:
                        report = json.loads(report_row[0])
                        # 优先从final_prediction取，兼容summary
                        fp = report.get('final_prediction', {})
                        summary = report.get('summary', {})
                        result_labels = {'home_win': '主胜', 'draw': '平局', 'away_win': '客胜'}
                        spf_labels = {'3': '主胜', '1': '平局', '0': '客胜'}
                        pred = fp.get('predicted_result') or summary.get('main_recommendation')
                        match['main_recommendation'] = result_labels.get(pred, pred) or '--'
                        conf = fp.get('confidence', 0) or (summary.get('confidence') or 0)
                        match['confidence_level'] = fp.get('confidence_level') or ('high' if conf >= 0.6 else ('medium' if conf >= 0.35 else 'low'))
                        match['confidence_tier'] = fp.get('confidence_tier') or (summary.get('confidence_tier') if isinstance(summary, dict) else None)

                        # Extract multi-play recommendations
                        # Support both play_predictions (core/analyze) and analyses (analysis_service) formats
                        pp = report.get('play_predictions', {})
                        analyses = report.get('analyses', {})
                        # RQSPF
                        rqspf_data = pp.get('rqspf') or analyses.get('rqspf') or {}
                        if rqspf_data:
                            rq_dir = rqspf_data.get('direction', '')
                            if not rq_dir:
                                # analyses format: adjusted_probs → derive direction
                                adj = rqspf_data.get('adjusted_probs', {})
                                if adj:
                                    rq_dir = max(adj, key=adj.get)
                                    rq_dir = {'home_win': '3', 'draw': '1', 'away_win': '0'}.get(rq_dir, rq_dir)
                            rq_rec = (
                                rqspf_data.get('recommendation_cn')
                                or rqspf_data.get('recommendation')
                                or rqspf_data.get('predicted_result')
                            )
                            match['rqspf_rec'] = normalize_rqspf_rec(rq_dir or rq_rec) or '--'
                        # BQC
                        bqc_data = pp.get('bqc') or analyses.get('bqc') or {}
                        if bqc_data:
                            bqc_rec_cn = bqc_data.get('recommendation_cn')
                            if bqc_rec_cn:
                                match['bqc_rec'] = bqc_rec_cn
                            elif bqc_data.get('recommendation'):
                                # Could be "半场主胜+全场主胜" format or "胜胜" format
                                rec = bqc_data['recommendation']
                                bqc_cn_map = {
                                    '半场主胜+全场主胜': '胜胜', '半场主胜+全场平局': '胜平',
                                    '半场主胜+全场客胜': '胜负', '半场平局+全场主胜': '平胜',
                                    '半场平局+全场平局': '平平', '半场平局+全场客胜': '平负',
                                    '半场客胜+全场主胜': '负胜', '半场客胜+全场平局': '负平',
                                    '半场客胜+全场客胜': '负负',
                                }
                                match['bqc_rec'] = bqc_cn_map.get(rec, rec)
                            else:
                                bqc_dir = bqc_data.get('direction', '')
                                bqc_labels = {'33': '胜胜', '31': '胜平', '30': '胜负',
                                              '13': '平胜', '11': '平平', '10': '平负',
                                              '03': '负胜', '01': '负平', '00': '负负',
                                              'hh': '胜胜', 'hd': '胜平', 'ha': '胜负',
                                              'dh': '平胜', 'dd': '平平', 'da': '平负',
                                              'ah': '负胜', 'ad': '负平', 'aa': '负负'}
                                match['bqc_rec'] = bqc_labels.get(bqc_dir, bqc_dir) or '--'
                        # Over/Under — support both ou and over_under keys
                        ou_data = pp.get('ou') or pp.get('over_under') or analyses.get('ou') or {}
                        if ou_data:
                            match['ou_rec'] = ou_data.get('recommendation', '') or '--'
                    except:
                        pass

                # Fallback: if no report found, try lottery_predictions table
                if not report_row or not match.get('main_recommendation') or match.get('main_recommendation') == '--':
                    cursor.execute("""
                        SELECT play_type, recommendation, confidence, confidence_level, predictions
                        FROM lottery_predictions
                        WHERE lottery_match_id = ?
                        ORDER BY datetime(created_at) DESC
                    """, (match['lottery_match_id'],))
                    pred_rows = cursor.fetchall()
                    if pred_rows:
                        spf_labels = {'3': '主胜', '1': '平局', '0': '客胜'}
                        bqc_labels = {'33': '胜胜', '31': '胜平', '30': '胜负',
                                      '13': '平胜', '11': '平平', '10': '平负',
                                      '03': '负胜', '01': '负平', '00': '负负',
                                      'hh': '胜胜', 'hd': '胜平', 'ha': '胜负',
                                      'dh': '平胜', 'dd': '平平', 'da': '平负',
                                      'ah': '负胜', 'ad': '负平', 'aa': '负负'}
                        for prow in pred_rows:
                            pt, rec, conf, conf_level, preds_json = prow
                            if pt == 'spf' and (not match.get('main_recommendation') or match['main_recommendation'] == '--'):
                                match['main_recommendation'] = spf_labels.get(rec, rec) or rec or '--'
                                if conf:
                                    match['confidence_level'] = conf_level or ('high' if conf >= 0.6 else ('medium' if conf >= 0.35 else 'low'))
                            elif pt == 'rqspf' and not match.get('rqspf_rec'):
                                match['rqspf_rec'] = normalize_rqspf_rec(rec) or '--'
                            elif pt == 'bqc' and not match.get('bqc_rec'):
                                match['bqc_rec'] = bqc_labels.get(rec, rec) or rec or '--'
                            elif pt == 'ou' and not match.get('ou_rec'):
                                match['ou_rec'] = rec or '--'

            if not match.get('rqspf_rec') and match.get('rqspf_odds'):
                match['rqspf_rec'] = derive_rqspf_rec_from_odds(match['rqspf_odds'])

            _align_ou_result_to_prediction(match)

        if date and not play_type:
            matches.sort(key=lambda item: item.get('beijing_time') or f"{item.get('match_date', '')} {item.get('match_time', '')}")

        # Add computed analysis_status for each match
        for match in matches:
            match['analysis_status'] = _compute_analysis_status(match)

        return {
            "success": True,
            "total": len(matches),
            "matches": matches
        }

    finally:
        conn.close()


@router.get("/data-completeness")
async def get_data_completeness(
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
    limit: int = Query(200, ge=1, le=300),
):
    """Return the backend data-quality view for the lottery hub."""
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    match_payload = await get_lottery_matches(
        date=target_date,
        status=None,
        play_type=None,
        limit=limit,
    )
    matches = match_payload.get("matches", []) if isinstance(match_payload, dict) else []

    conn = get_db()
    cursor = conn.cursor()
    try:
        event_ids = sorted({
            str(match.get("oddsfe_event_id"))
            for match in matches
            if match.get("oddsfe_event_id")
        })
        match_ids = sorted({
            str(match.get("lottery_match_id"))
            for match in matches
            if match.get("lottery_match_id")
        })
        intelligence_index = _load_intelligence_index(cursor, target_date, match_ids)
        event_cache_ids = _latest_oddsfe_event_artifacts(cursor, event_ids)
        ou_line_event_ids = _latest_oddsfe_ou_line_events(cursor, event_ids)
        validation_index = _load_validation_index(cursor, match_ids)
        post_review_index = _load_post_review_index(cursor, match_ids)
        event_run_status = _collection_run_status(cursor, "oddsfe_event_details")
        ou_line_run_status = _collection_run_status(cursor, "oddsfe_ou_lines")
    finally:
        conn.close()

    rows = []
    summary = {
        "total": 0,
        "actionable_total": 0,
        "with_odds": 0,
        "missing_odds": 0,
        "result_due": 0,
        "with_score": 0,
        "missing_score": 0,
        "with_half_score": 0,
        "missing_half_score": 0,
        "with_analysis": 0,
        "missing_analysis": 0,
        "with_intelligence": 0,
        "missing_intelligence": 0,
        "with_event_cache": 0,
        "missing_event_cache": 0,
        "with_ou_line": 0,
        "missing_ou_line": 0,
        "with_validation": 0,
        "missing_validation": 0,
        "with_post_review": 0,
        "missing_post_review": 0,
        "schedule_fallback": 0,
    }
    action_counts: Dict[str, int] = {}

    for match in matches:
        mid = str(match.get("lottery_match_id"))
        row = _build_completeness_row(
            match,
            intelligence_index.get(mid),
            event_cache_ids,
            ou_line_event_ids,
            validation_index.get(mid),
            post_review_index.get(mid),
        )
        rows.append(row)
        summary["total"] += 1
        if row["is_schedule_fallback"]:
            summary["schedule_fallback"] += 1
            continue
        summary["actionable_total"] += 1
        if row["has_odds"]:
            summary["with_odds"] += 1
        else:
            summary["missing_odds"] += 1
        if row["result_due"]:
            summary["result_due"] += 1
            if row["has_score"]:
                summary["with_score"] += 1
            else:
                summary["missing_score"] += 1
            if row["has_half_score"]:
                summary["with_half_score"] += 1
            else:
                summary["missing_half_score"] += 1
        if row["has_analysis"]:
            summary["with_analysis"] += 1
        else:
            summary["missing_analysis"] += 1
        if row["has_intelligence"]:
            summary["with_intelligence"] += 1
        else:
            summary["missing_intelligence"] += 1
        if row["has_event_cache"]:
            summary["with_event_cache"] += 1
        elif row["oddsfe_event_id"] and not row["is_schedule_fallback"]:
            summary["missing_event_cache"] += 1
        if row["has_ou_line"]:
            summary["with_ou_line"] += 1
        elif row["oddsfe_event_id"] and not row["is_schedule_fallback"]:
            summary["missing_ou_line"] += 1
        if row["result_due"] and row["has_score"] and row["has_analysis"]:
            if row["has_validation"]:
                summary["with_validation"] += 1
            else:
                summary["missing_validation"] += 1
        if row["result_due"] and row["has_score"] and row["has_validation"]:
            if row["has_post_review"]:
                summary["with_post_review"] += 1
            else:
                summary["missing_post_review"] += 1
        for action in row["next_actions"]:
            action_counts[action] = action_counts.get(action, 0) + 1

    summary.update({
        "missing_total": (
            summary["missing_odds"]
            + summary["missing_score"]
            + summary["missing_half_score"]
            + summary["missing_analysis"]
            + summary["missing_intelligence"]
            + summary["missing_event_cache"]
            + summary["missing_ou_line"]
            + summary["missing_validation"]
            + summary["missing_post_review"]
        ),
        "complete": (
            summary["missing_odds"]
            + summary["missing_score"]
            + summary["missing_half_score"]
            + summary["missing_analysis"]
            + summary["missing_intelligence"]
            + summary["missing_event_cache"]
            + summary["missing_ou_line"]
            + summary["missing_validation"]
            + summary["missing_post_review"]
        ) == 0,
        "missingOdds": summary["missing_odds"],
        "missingScore": summary["missing_score"],
        "missingHalf": summary["missing_half_score"],
        "missingAnalysis": summary["missing_analysis"],
        "missingIntel": summary["missing_intelligence"],
        "missingOuLine": summary["missing_ou_line"],
        "missingValidation": summary["missing_validation"],
        "missingPostReview": summary["missing_post_review"],
    })

    return {
        "success": True,
        "date": target_date,
        "total": len(rows),
        "summary": summary,
        "matches": rows,
        "action_counts": action_counts,
        "gap_plan": _build_gap_plan(rows, action_counts),
        "collection_runs": {
            "oddsfe_event_details": event_run_status,
            "oddsfe_ou_lines": ou_line_run_status,
        },
    }


@router.get("/data-completeness/range")
async def get_data_completeness_range(
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
    limit_per_day: int = Query(200, ge=1, le=300),
):
    """Return a date-by-date data completeness summary for the lottery hub."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid date format, expected YYYY-MM-DD") from exc
    if end < start:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")
    if (end - start).days > 45:
        raise HTTPException(status_code=400, detail="date range is too large; max 46 days")

    days = []
    totals = {
        "dates": 0,
        "total": 0,
        "actionable_total": 0,
        "with_odds": 0,
        "missing_odds": 0,
        "result_due": 0,
        "with_score": 0,
        "missing_score": 0,
        "with_half_score": 0,
        "missing_half_score": 0,
        "with_analysis": 0,
        "missing_analysis": 0,
        "with_intelligence": 0,
        "missing_intelligence": 0,
        "with_event_cache": 0,
        "missing_event_cache": 0,
        "with_ou_line": 0,
        "missing_ou_line": 0,
        "with_validation": 0,
        "missing_validation": 0,
        "with_post_review": 0,
        "missing_post_review": 0,
        "schedule_fallback": 0,
    }
    action_counts: Dict[str, int] = {}
    range_problem_rows: List[Dict[str, Any]] = []

    cursor_date = start
    while cursor_date <= end:
        day_text = cursor_date.isoformat()
        day = await get_data_completeness(date=day_text, limit=limit_per_day)
        summary = day.get("summary", {}) if isinstance(day, dict) else {}
        matches = day.get("matches", []) if isinstance(day, dict) else []
        day_actions = day.get("action_counts", {}) if isinstance(day, dict) else {}
        missing_total = (
            int(summary.get("missing_odds") or 0)
            + int(summary.get("missing_score") or 0)
            + int(summary.get("missing_half_score") or 0)
            + int(summary.get("missing_analysis") or 0)
            + int(summary.get("missing_intelligence") or 0)
            + int(summary.get("missing_event_cache") or 0)
            + int(summary.get("missing_ou_line") or 0)
            + int(summary.get("missing_validation") or 0)
            + int(summary.get("missing_post_review") or 0)
        )
        problem_matches = [
            item for item in matches
            if item.get("missing")
            or (item.get("quality_flags") and not item.get("is_schedule_fallback"))
        ][:20]
        warning_matches = [
            item for item in matches
            if item.get("is_schedule_fallback")
        ][:20]
        range_problem_rows.extend(problem_matches)
        days.append({
            "date": day_text,
            "summary": summary,
            "total": summary.get("total", 0),
            "missing_total": missing_total,
            "complete": missing_total == 0,
            "action_counts": day_actions,
            "gap_plan": day.get("gap_plan", []) if isinstance(day, dict) else [],
            "problem_matches": problem_matches,
            "warning_matches": warning_matches,
        })
        totals["dates"] += 1
        for key in (
            "total", "with_odds", "missing_odds", "result_due", "with_score",
            "missing_score", "with_half_score", "missing_half_score",
            "with_analysis", "missing_analysis", "with_intelligence",
            "missing_intelligence", "with_event_cache", "missing_event_cache",
            "with_ou_line", "missing_ou_line",
            "with_validation", "missing_validation", "with_post_review",
            "missing_post_review", "schedule_fallback", "actionable_total",
        ):
            totals[key] += int(summary.get(key) or 0)
        for action, count in day_actions.items():
            action_counts[action] = action_counts.get(action, 0) + int(count or 0)
        cursor_date += timedelta(days=1)

    totals.update({
        "missing_total": (
            totals["missing_odds"]
            + totals["missing_score"]
            + totals["missing_half_score"]
            + totals["missing_analysis"]
            + totals["missing_intelligence"]
            + totals["missing_event_cache"]
            + totals["missing_ou_line"]
            + totals["missing_validation"]
            + totals["missing_post_review"]
        ),
        "complete_dates": sum(1 for item in days if item["complete"]),
        "problem_dates": sum(1 for item in days if not item["complete"]),
    })
    return {
        "success": True,
        "range": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "summary": totals,
        "days": days,
        "action_counts": action_counts,
        "gap_plan": _build_gap_plan(range_problem_rows, action_counts, max_examples=8),
    }


@router.post("/auto-fill-gaps")
async def auto_fill_lottery_gaps(
    background_tasks: BackgroundTasks,
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    days: int = Query(3, ge=1, le=14, description="Default rolling window when dates are omitted"),
    dry_run: bool = Query(True, description="Plan only; do not write data"),
    background: bool = Query(True, description="Run writes in background"),
    max_events: int = Query(8, ge=1, le=50, description="Max oddsfe event/O-U candidates per run"),
    max_analysis: int = Query(12, ge=1, le=80, description="Max matches to analyze per run"),
    max_intelligence: int = Query(8, ge=1, le=50, description="Max intelligence jobs per run"),
    max_validation_dates: int = Query(4, ge=1, le=14, description="Max dates to validate per run"),
    fetch_live_ou: bool = Query(True, description="Fetch live oddsfe market pages when local cache lacks O/U"),
    network_intelligence: bool = Query(True, description="Allow external intelligence collectors"),
    league: Optional[str] = Query(None, description="Optional league_name_cn filter, e.g. 世界杯"),
):
    """Plan or execute bounded automatic gap filling for the lottery cockpit."""
    from backend.app.lottery.services.auto_gap_runner import (
        LotteryAutoGapRunner,
        action_counts_from_plan,
        date_window,
    )

    if not date_from or not date_to:
        date_from, date_to = date_window(days)

    plan = await get_data_completeness_range(
        start_date=date_from,
        end_date=date_to,
        limit_per_day=200,
    )
    runner = LotteryAutoGapRunner(DB_PATH, ODDSFE_DB_PATH)
    league_filter = (league or "").strip() or None
    action_counts = (
        runner.infer_action_counts(date_from, date_to, league=league_filter)
        if league_filter
        else action_counts_from_plan(plan.get("gap_plan", []))
    )
    response_base = {
        "success": True,
        "dry_run": dry_run,
        "background": background and not dry_run,
        "league": league_filter or "",
        "range": plan.get("range"),
        "summary": plan.get("summary", {}),
        "action_counts": action_counts,
        "gap_plan": plan.get("gap_plan", []),
    }

    if dry_run:
        return {
            **response_base,
            "message": "auto gap fill dry-run only",
        }

    if not any(int(value or 0) > 0 for value in action_counts.values()):
        return {
            **response_base,
            "message": "no actionable gaps in selected range",
            "result": {"skipped": True},
        }

    runner_kwargs = {
        "date_from": date_from,
        "date_to": date_to,
        "action_counts": action_counts,
        "max_events": max_events,
        "max_analysis": max_analysis,
        "max_intelligence": max_intelligence,
        "max_validation_dates": max_validation_dates,
        "fetch_live_ou": fetch_live_ou,
        "network_intelligence": network_intelligence,
        "league": league_filter,
    }

    if background:
        background_tasks.add_task(run_auto_gap_fill_task, **runner_kwargs)
        return {
            **response_base,
            "message": "auto gap fill started in background",
            "limits": {
                "max_events": max_events,
                "max_analysis": max_analysis,
                "max_intelligence": max_intelligence,
                "max_validation_dates": max_validation_dates,
            },
        }

    result = runner.run(
        **runner_kwargs,
        trigger_source="manual_auto_gap_fill_api",
    )
    return {
        **response_base,
        "message": "auto gap fill completed",
        "result": result,
    }


@router.get("/automation-audit")
async def get_automation_audit(
    date_from: Optional[str] = Query(None, description="Completeness start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="Completeness end date YYYY-MM-DD"),
    recent_hours: int = Query(24, ge=1, le=168, description="Recent run/report audit window"),
    stale_running_hours: int = Query(6, ge=1, le=72, description="Running job stale threshold"),
    duplicate_threshold: int = Query(10, ge=1, le=200, description="Duplicate report threshold per match"),
):
    """Read-only automation health audit for long-running collection loops."""
    try:
        from scripts.audit_auto_loop_health import audit_auto_loop_health

        return audit_auto_loop_health(
            Path(DB_PATH),
            date_from=date_from,
            date_to=date_to,
            recent_hours=recent_hours,
            stale_running_hours=stale_running_hours,
            duplicate_threshold=duplicate_threshold,
        )
    except Exception as exc:
        logger.error("automation audit failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _automation_accuracy_snapshot(cursor, date_from: str, date_to: str, league: str = "") -> Dict[str, Any]:
    where = ["substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?"]
    params: List[Any] = [date_from, date_to]
    if league:
        where.append("COALESCE(lm.league_name_cn, '') = ?")
        params.append(league)
    rows = cursor.execute(
        f"""
        SELECT v.play_type,
               COUNT(*) AS total,
               SUM(CASE WHEN v.is_correct THEN 1 ELSE 0 END) AS correct
        FROM lottery_validation v
        JOIN lottery_matches lm ON lm.lottery_match_id = v.lottery_match_id
        WHERE {' AND '.join(where)}
          AND v.predicted_result IS NOT NULL
          AND v.actual_result IS NOT NULL
          AND TRIM(v.predicted_result) NOT IN ('', '--', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
          AND TRIM(v.actual_result) NOT IN ('', '--', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
        GROUP BY v.play_type
        ORDER BY v.play_type
        """,
        params,
    ).fetchall()
    by_play: Dict[str, Any] = {}
    total = 0
    correct = 0
    for row in rows:
        count = int(row["total"] or 0)
        hits = int(row["correct"] or 0)
        by_play[row["play_type"] or "unknown"] = {
            "total": count,
            "correct": hits,
            "accuracy": round(hits * 100 / count, 1) if count else 0,
        }
        total += count
        correct += hits
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct * 100 / total, 1) if total else 0,
        "by_play_type": by_play,
    }


def _automation_run_payload(row) -> Dict[str, Any]:
    summary = _loads_json(row["summary_json"], {})
    if not isinstance(summary, dict):
        summary = {}
    task_payload = summary.get("payload") if isinstance(summary.get("payload"), dict) else {}
    compact_payload: Dict[str, Any] = {}
    if task_payload:
        for key in (
            "success", "skipped", "reason", "error", "changes", "changed_reports",
            "prediction_rows", "delta_correct", "validated", "accuracy",
            "prediction_consistency_ok", "hard_prediction_issues", "prediction_parse_errors",
            "post_prediction_consistency_ok", "post_prediction_hard_issues", "post_prediction_parse_errors",
        ):
            if key in task_payload:
                compact_payload[key] = task_payload.get(key)
        for key in ("prediction_consistency", "post_prediction_consistency"):
            value = task_payload.get(key)
            if isinstance(value, dict):
                compact_payload[key] = {
                    "date_from": value.get("date_from"),
                    "date_to": value.get("date_to"),
                    "league": value.get("league"),
                    "reports_checked": value.get("reports_checked"),
                    "hard_issues": value.get("hard_issues"),
                    "parse_errors": value.get("parse_errors"),
                    "issue_counts": value.get("issue_counts") or {},
                }
        for key in ("prediction_remediation", "post_prediction_remediation"):
            value = task_payload.get(key)
            if isinstance(value, dict):
                compact_payload[key] = {
                    "attempted": value.get("attempted"),
                    "targets": value.get("targets"),
                    "analyzed": value.get("analyzed"),
                    "failed": value.get("failed"),
                }
    return {
        "run_id": row["run_id"],
        "trigger_source": row["trigger_source"],
        "run_type": row["run_type"],
        "match_date": row["match_date"],
        "status": row["status"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "error": row["error"],
        "summary": {
            "date_from": summary.get("date_from"),
            "date_to": summary.get("date_to"),
            "league": summary.get("league"),
            "task_count": summary.get("task_count"),
            "failed_tasks": summary.get("failed_tasks"),
            "stage": summary.get("stage"),
            "progress": summary.get("progress") if isinstance(summary.get("progress"), dict) else {},
            "action_counts": summary.get("action_counts"),
            "steps": summary.get("steps"),
            "accuracy_snapshot": summary.get("accuracy_snapshot"),
            "targets": summary.get("targets"),
            "analyzed": summary.get("analyzed"),
            "changed_reports": summary.get("changed_reports"),
            "prediction_changed": summary.get("prediction_changed"),
            "change_rows_saved": summary.get("change_rows_saved"),
            "unchanged": summary.get("unchanged"),
            "failed": summary.get("failed"),
            "changed_examples": (summary.get("changed_examples") or [])[:6],
            "payload": compact_payload,
        },
    }


def _automation_recent_runs(cursor, limit: int = 16) -> List[Dict[str, Any]]:
    if not _table_exists(cursor, "collection_runs"):
        return []
    rows = cursor.execute(
        """
        SELECT run_id, trigger_source, run_type, match_date, status,
               started_at, finished_at, summary_json, error
        FROM collection_runs
        ORDER BY datetime(started_at) DESC, rowid DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_automation_run_payload(row) for row in rows]


def _automation_latest_run(
    cursor,
    run_type: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    league: str = "",
) -> Optional[Dict[str, Any]]:
    if not _table_exists(cursor, "collection_runs"):
        return None
    rows = cursor.execute(
        """
        SELECT run_id, trigger_source, run_type, match_date, status,
               started_at, finished_at, summary_json, error
        FROM collection_runs
        WHERE run_type = ?
        ORDER BY datetime(started_at) DESC, rowid DESC
        LIMIT 80
        """,
        (run_type,),
    ).fetchall()
    payloads = [_automation_run_payload(row) for row in rows]
    if not date_from or not date_to:
        return payloads[0] if payloads else None

    matched: List[Dict[str, Any]] = []
    for payload in payloads:
        summary = payload.get("summary") or {}
        run_from = str(summary.get("date_from") or payload.get("match_date") or "")[:10]
        run_to = str(summary.get("date_to") or run_from or "")[:10]
        if not run_from or not run_to:
            continue
        if run_from > date_to or run_to < date_from:
            continue
        run_league = str(summary.get("league") or "").strip()
        if league and run_league and run_league != league:
            continue
        matched.append(payload)
    if not matched:
        return payloads[0] if payloads else None
    for payload in matched:
        summary = payload.get("summary") or {}
        if int(summary.get("targets") or 0) > 0:
            return payload
    return matched[0]


def _automation_recent_reanalysis_changes(cursor, limit: int = 8) -> List[Dict[str, Any]]:
    if not _table_exists(cursor, "prediction_reanalysis_changes"):
        return []
    rows = cursor.execute(
        """
        SELECT change_id, run_id, trigger_source, lottery_match_id, match_date,
               match_num, league_name_cn, home_team_cn, away_team_cn,
               before_report_id, after_report_id, prediction_changed,
               change_json, created_at, settled_at, validation_json
        FROM prediction_reanalysis_changes
        ORDER BY datetime(created_at) DESC, rowid DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    result = []
    for row in rows:
        change_json = _loads_json(row["change_json"], {})
        validation_json = _loads_json(row["validation_json"], {}) if row["validation_json"] else {}
        if not isinstance(change_json, dict):
            change_json = {}
        if not isinstance(validation_json, dict):
            validation_json = {}
        result.append({
            "change_id": row["change_id"],
            "run_id": row["run_id"],
            "trigger_source": row["trigger_source"],
            "lottery_match_id": row["lottery_match_id"],
            "match_date": row["match_date"],
            "match_num": row["match_num"],
            "league_name_cn": row["league_name_cn"],
            "home_team_cn": row["home_team_cn"],
            "away_team_cn": row["away_team_cn"],
            "match": change_json.get("match") or f"{row['home_team_cn']} vs {row['away_team_cn']}",
            "before_report_id": row["before_report_id"],
            "after_report_id": row["after_report_id"],
            "prediction_changed": bool(row["prediction_changed"]),
            "prediction_changes": (change_json.get("prediction_changes") or [])[:8],
            "before_prediction_summary": change_json.get("before_prediction_summary") or {},
            "after_prediction_summary": change_json.get("after_prediction_summary") or {},
            "created_at": row["created_at"],
            "settled_at": row["settled_at"],
            "validation": validation_json,
        })
    return result


def _automation_control_config_patch(
    *,
    workers: Optional[int] = None,
    historical_dates: Optional[int] = None,
    max_events: Optional[int] = None,
    max_analysis: Optional[int] = None,
    max_intelligence: Optional[int] = None,
    max_validation_dates: Optional[int] = None,
    fetch_live_ou: Optional[bool] = None,
    network_intelligence: Optional[bool] = None,
    include_learning: Optional[bool] = None,
) -> Dict[str, Any]:
    patch: Dict[str, Any] = {}
    for key, value in {
        "workers": workers,
        "historical_dates": historical_dates,
        "max_events": max_events,
        "max_analysis": max_analysis,
        "max_intelligence": max_intelligence,
        "max_validation_dates": max_validation_dates,
        "fetch_live_ou": fetch_live_ou,
        "network_intelligence": network_intelligence,
        "include_learning": include_learning,
    }.items():
        if value is not None:
            patch[key] = value
    return patch


@router.get("/automation-control")
async def get_automation_control():
    """Persistent start/pause/stop state for the automation center."""
    try:
        from backend.app.lottery.services.automation_control import get_automation_control_state

        return {"success": True, "control": get_automation_control_state(DB_PATH)}
    except Exception as exc:
        logger.error("automation control status failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/automation-control/start")
async def start_automation_control(
    background_tasks: BackgroundTasks,
    run_now: bool = Query(True, description="Queue one automation center run immediately"),
    workers: Optional[int] = Query(None, ge=1, le=8),
    historical_dates: Optional[int] = Query(None, ge=0, le=14),
    max_events: Optional[int] = Query(None, ge=1, le=50),
    max_analysis: Optional[int] = Query(None, ge=1, le=100),
    max_intelligence: Optional[int] = Query(None, ge=1, le=50),
    max_validation_dates: Optional[int] = Query(None, ge=1, le=14),
    fetch_live_ou: Optional[bool] = Query(None),
    network_intelligence: Optional[bool] = Query(None),
    include_learning: Optional[bool] = Query(None),
):
    """Enable persistent automation; optionally queue one immediate center run."""
    try:
        from backend.app.lottery.services.automation_control import (
            automation_center_kwargs_from_state,
            set_automation_control_state,
        )

        state = set_automation_control_state(
            DB_PATH,
            enabled=True,
            state="active",
            config_patch=_automation_control_config_patch(
                workers=workers,
                historical_dates=historical_dates,
                max_events=max_events,
                max_analysis=max_analysis,
                max_intelligence=max_intelligence,
                max_validation_dates=max_validation_dates,
                fetch_live_ou=fetch_live_ou,
                network_intelligence=network_intelligence,
                include_learning=include_learning,
            ),
            updated_by="frontend",
            reason="operator_start",
        )
        queued = False
        if run_now:
            kwargs = automation_center_kwargs_from_state(state, trigger_source="automation_control_start")
            background_tasks.add_task(run_automation_center_task, **kwargs)
            queued = True
        return {"success": True, "control": state, "queued": queued}
    except Exception as exc:
        logger.error("automation control start failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/automation-control/pause")
async def pause_automation_control():
    """Pause future automation-center cycles without stopping other scheduler jobs."""
    try:
        from backend.app.lottery.services.automation_control import set_automation_control_state

        state = set_automation_control_state(
            DB_PATH,
            enabled=False,
            state="paused",
            updated_by="frontend",
            reason="operator_pause",
        )
        return {"success": True, "control": state}
    except Exception as exc:
        logger.error("automation control pause failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/automation-control/stop")
async def stop_automation_control():
    """Stop future automation-center cycles. Running subprocesses finish naturally."""
    try:
        from backend.app.lottery.services.automation_control import set_automation_control_state

        state = set_automation_control_state(
            DB_PATH,
            enabled=False,
            state="stopped",
            updated_by="frontend",
            reason="operator_stop",
        )
        return {"success": True, "control": state}
    except Exception as exc:
        logger.error("automation control stop failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/automation-dashboard")
async def get_automation_dashboard(
    date_from: Optional[str] = Query(None, description="Dashboard window start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="Dashboard window end date YYYY-MM-DD"),
    league: str = Query("世界杯", description="Optional league_name_cn filter"),
    recent_hours: int = Query(24, ge=1, le=168),
):
    """Compact automation dashboard for the lottery center frontend."""
    try:
        from backend.app.data_access.task_lock import inspect_task_lock
        from backend.app.lottery.services.automation_control import get_automation_control_state
        from scripts.audit_auto_loop_health import audit_auto_loop_health

        if not date_from or not date_to:
            today = datetime.now().date()
            date_from = (today - timedelta(days=1)).isoformat()
            date_to = (today + timedelta(days=2)).isoformat()

        audit = audit_auto_loop_health(
            Path(DB_PATH),
            date_from=date_from,
            date_to=date_to,
            league=league or "",
            recent_hours=recent_hours,
            stale_running_hours=2,
            duplicate_threshold=10,
        )
        conn = get_db()
        try:
            cursor = conn.cursor()
            runs = _automation_recent_runs(cursor)
            latest_future_reanalysis = _automation_latest_run(
                cursor,
                "post_learning_future_reanalysis",
                date_from,
                date_to,
                league or "",
            )
            recent_reanalysis_changes = _automation_recent_reanalysis_changes(cursor)
            accuracy = _automation_accuracy_snapshot(cursor, date_from, date_to, league or "")
        finally:
            conn.close()

        collection_runs = audit.get("collection_runs") or {}
        completeness = (audit.get("completeness") or {}).get("summary") or {}
        findings = audit.get("findings") or []
        running = collection_runs.get("active_running") or []
        recent_failures = collection_runs.get("recent_failures") or []
        stale_running = collection_runs.get("stale_running") or []
        learning_lock = inspect_task_lock("learning", DB_PATH)
        automation_lock = inspect_task_lock("automation_center", DB_PATH)
        control = get_automation_control_state(DB_PATH)
        health_level = "ok"
        if any(item.get("severity") == "high" for item in findings) or stale_running:
            health_level = "bad"
        elif findings or recent_failures or int(completeness.get("missing_total") or 0) > 0:
            health_level = "warn"

        return {
            "success": True,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "window": {
                "date_from": date_from,
                "date_to": date_to,
                "league": league or "",
                "recent_hours": recent_hours,
            },
            "status": {
                "health": health_level,
                "running_count": len(running),
                "recent_failure_count": len(recent_failures),
                "stale_running_count": len(stale_running),
                "missing_total": int(completeness.get("missing_total") or 0),
                "finding_count": len(findings),
                "learning_locked": bool(learning_lock.get("locked")),
                "learning_lock_stale": bool(learning_lock.get("stale")),
                "automation_locked": bool(automation_lock.get("locked")),
                "automation_lock_stale": bool(automation_lock.get("stale")),
                "automation_enabled": bool(control.get("enabled")),
                "automation_state": control.get("state"),
            },
            "control": control,
            "automation_lock": automation_lock,
            "accuracy": accuracy,
            "learning_lock": learning_lock,
            "latest_future_reanalysis": latest_future_reanalysis,
            "recent_reanalysis_changes": recent_reanalysis_changes,
            "recent_runs": runs,
            "audit": audit,
        }
    except Exception as exc:
        logger.error("automation dashboard failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/automation-center/run")
async def run_automation_center(
    background_tasks: BackgroundTasks,
    mode: str = Query("rolling", description="rolling/range/historical/mixed"),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD for range mode"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD for range mode"),
    league: Optional[str] = Query(None, description="Optional league_name_cn filter, e.g. 世界杯"),
    historical_dates: int = Query(0, ge=0, le=14, description="Extra reverse historical dates for mixed/historical mode"),
    historical_lookback_days: int = Query(180, ge=1, le=3650),
    workers: int = Query(3, ge=1, le=8, description="Concurrent task workers"),
    task_timeout: int = Query(300, ge=60, le=1800, description="Per-task timeout seconds"),
    max_events: int = Query(6, ge=1, le=50),
    max_analysis: int = Query(10, ge=1, le=100),
    max_intelligence: int = Query(6, ge=1, le=50),
    max_validation_dates: int = Query(1, ge=1, le=14),
    fetch_live_ou: bool = Query(True),
    network_intelligence: bool = Query(True),
    include_learning: bool = Query(True),
    force_analysis: bool = Query(False, description="Re-run analysis even when reports already exist"),
    force_validation: bool = Query(False, description="Rebuild validation even when records already exist"),
    force_learning: bool = Query(False, description="Run final learning refresh even without explicit gaps"),
    dry_run: bool = Query(False, description="Only return planned tasks"),
    background: bool = Query(True, description="Run in FastAPI background task"),
):
    """Central parallel automation runner: split by date/type, run bounded task waves."""
    try:
        from backend.app.lottery.services.automation_center import AutomationCenter

        center = AutomationCenter(DB_PATH, ODDSFE_DB_PATH)
        league_filter = (league or "").strip()
        if dry_run:
            return center.plan(
                mode=mode,
                date_from=date_from,
                date_to=date_to,
                league=league_filter,
                historical_dates=historical_dates,
                historical_lookback_days=historical_lookback_days,
                include_learning=include_learning,
                force_analysis=force_analysis,
                force_validation=force_validation,
                force_learning=force_learning,
            )

        kwargs = {
            "mode": mode,
            "date_from": date_from,
            "date_to": date_to,
            "league": league_filter,
            "historical_dates": historical_dates,
            "historical_lookback_days": historical_lookback_days,
            "include_learning": include_learning,
            "workers": workers,
            "task_timeout_seconds": task_timeout,
            "max_events": max_events,
            "max_analysis": max_analysis,
            "max_intelligence": max_intelligence,
            "max_validation_dates": max_validation_dates,
            "fetch_live_ou": fetch_live_ou,
            "network_intelligence": network_intelligence,
            "force_analysis": force_analysis,
            "force_validation": force_validation,
            "force_learning": force_learning,
            "trigger_source": "manual_automation_center_api",
        }
        if background:
            background_tasks.add_task(run_automation_center_task, **kwargs)
            plan = center.plan(
                mode=mode,
                date_from=date_from,
                date_to=date_to,
                league=league_filter,
                historical_dates=historical_dates,
                historical_lookback_days=historical_lookback_days,
                include_learning=include_learning,
                force_analysis=force_analysis,
                force_validation=force_validation,
                force_learning=force_learning,
            )
            return {
                "success": True,
                "background": True,
                "message": "automation center started in background",
                "plan": {
                    "dates": plan.get("dates", []),
                    "task_count": plan.get("task_count", 0),
                    "by_wave": plan.get("by_wave", {}),
                    "by_kind": plan.get("by_kind", {}),
                },
            }
        return center.run(**kwargs)
    except Exception as exc:
        logger.error("automation center run failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/automation-center/retry-failed")
async def retry_automation_center_failed(
    background_tasks: BackgroundTasks,
    run_id: str = Query(..., description="automation_center run_id to retry failed tasks from"),
    task_key: Optional[str] = Query(None, description="optional task key wave:kind:date_from:date_to"),
    task_index: Optional[int] = Query(None, ge=0, description="optional source task index in the run summary"),
    background: bool = Query(True),
    workers: Optional[int] = Query(None, ge=1, le=8),
):
    """Retry failed tasks from one automation-center run."""
    try:
        from backend.app.lottery.services.automation_center import AutomationCenter

        if background:
            background_tasks.add_task(
                run_automation_retry_task,
                run_id=run_id,
                workers=workers,
                task_key=task_key,
                task_index=task_index,
            )
            return {
                "success": True,
                "background": True,
                "message": "automation retry started in background",
                "source_run_id": run_id,
                "task_key": task_key,
                "task_index": task_index,
            }
        return AutomationCenter(DB_PATH, ODDSFE_DB_PATH).retry_failed_tasks(
            run_id,
            trigger_source="manual_automation_retry_api",
            workers=workers,
            task_key=task_key,
            task_index=task_index,
        )
    except Exception as exc:
        logger.error("automation retry failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/matches/leagues")
async def get_lottery_match_leagues(
    date: Optional[str] = Query(None, description="日期 (YYYY-MM-DD)"),
    include_all: bool = Query(False, description="包含非体彩在售联赛"),
):
    """获取当前可选联赛列表(含每联赛比赛数)"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = "SELECT league_name_cn, COUNT(*) as cnt FROM lottery_matches WHERE 1=1"
        params = []

        if not include_all:
            placeholders = ",".join(["?" for _ in LOTTERY_CORE_LEAGUES])
            query += f" AND league_name_cn IN ({placeholders})"
            params.extend(sorted(LOTTERY_CORE_LEAGUES))

        if date:
            query += " AND (substr(beijing_time, 1, 10) = ? OR (beijing_time IS NULL AND match_date = ?))"
            params.extend([date, date])
        else:
            from backend.app.core.time_utils import now_beijing
            from datetime import timedelta as _td
            bj_cutoff = (now_beijing() - _td(hours=6)).strftime('%Y-%m-%d %H:%M:%S')
            bj_today = now_beijing().strftime('%Y-%m-%d')
            query += " AND (beijing_time >= ? OR (beijing_time IS NULL AND match_date >= ?))"
            params.extend([bj_cutoff, bj_today])

        query += " GROUP BY league_name_cn ORDER BY cnt DESC"
        cursor.execute(query, params)
        leagues = [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]
        return {"leagues": leagues}
    finally:
        conn.close()


@router.get("/matches/{lottery_match_id}")
async def get_lottery_match_detail(lottery_match_id: str):
    """
    获取单场比赛详情
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT lm.*,
                   ht.name_en as home_team_name_en,
                   ht.name_cn as home_team_name_cn,
                   at.name_en as away_team_name_en,
                   at.name_cn as away_team_name_cn
            FROM lottery_matches lm
            LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
            LEFT JOIN teams at ON lm.away_team_id = at.team_id
            WHERE lm.lottery_match_id = ?
        """, (lottery_match_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Match not found")

        match = dict(row)

        # 处理 play_types
        match['play_types'] = parse_play_types(match.get('play_types'))

        # play_types为空时从lottery_odds推断
        if not match['play_types']:
            cursor.execute(f"""
                SELECT DISTINCT play_type FROM lottery_odds
                WHERE lottery_match_id = ?
            """, (lottery_match_id,))
            odds_types = [r[0] for r in cursor.fetchall()]
            if odds_types:
                match['play_types'] = odds_types

        # 获取赔率
        cursor.execute("""
            SELECT play_type, odds_data FROM lottery_odds
            WHERE lottery_match_id = ?
        """, (lottery_match_id,))

        odds = {}
        for row in cursor.fetchall():
            try:
                odds[row['play_type']] = json.loads(row['odds_data'])
            except:
                odds[row['play_type']] = {}

        match['odds'] = odds
        match['play_types'] = merge_play_types(match['play_types'], list(odds.keys()))
        if odds.get('spf'):
            match['spf_odds'] = odds['spf']
        if odds.get('rqspf'):
            match['rqspf_odds'] = odds['rqspf']
            match['rqspf_rec'] = derive_rqspf_rec_from_odds(odds['rqspf'])

        return {
            "success": True,
            "match": match
        }

    finally:
        conn.close()


# ==================== 分析报告 ====================

@router.post("/analyze/{lottery_match_id}")
async def analyze_lottery_match(
    lottery_match_id: str,
    background_tasks: BackgroundTasks,
    play_types: Optional[str] = Query(None, description="玩法列表，逗号分隔"),
    force: bool = Query(False, description="强制重新分析"),
    sync: bool = Query(True, description="同步执行分析并等待结果")
):
    """
    分析指定比赛

    如果已有分析报告，直接返回；
    否则执行分析（默认同步等待结果）
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 检查比赛是否存在
        cursor.execute("""
            SELECT lottery_match_id FROM lottery_matches
            WHERE lottery_match_id = ?
        """, (lottery_match_id,))

        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Match not found")

        # 检查是否有分析报告
        if not force:
            report_cols = get_table_columns(cursor, "lottery_analysis_reports")
            stale_filter = "AND COALESCE(is_stale, 0) = 0" if "is_stale" in report_cols else ""
            cursor.execute(f"""
                SELECT report_data, created_at FROM lottery_analysis_reports
                WHERE lottery_match_id = ? AND report_type IN ('prediction', 'full')
                  {stale_filter}
                ORDER BY datetime(created_at) DESC, rowid DESC
                LIMIT 1
            """, (lottery_match_id,))

            row = cursor.fetchone()
            if row:
                report = json.loads(row['report_data'])
                learning = _latest_learning_payload(cursor, lottery_match_id)
                if isinstance(report, dict):
                    report['_learning'] = learning
                return {
                    "success": True,
                    "cached": True,
                    "report": report,
                    "learning": learning,
                    "generated_at": row['created_at']
                }

        if sync:
            # 同步执行分析 — 委托给统一管道 (core/analyze.py)
            try:
                from ...core.analyze import analyze_single
                result = analyze_single(DB_PATH, lottery_match_id)
                if result:
                    learning = _latest_learning_payload(cursor, lottery_match_id)
                    if isinstance(result, dict):
                        result['_learning'] = learning
                    return {
                        "success": True,
                        "cached": False,
                        "report": result,
                        "learning": learning
                    }
                else:
                    return {
                        "success": False,
                        "message": "Analysis returned empty result"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Analysis failed: {str(e)}"
                }
        else:
            # 后台执行分析
            from ..services.analysis_service import AnalysisService
            background_tasks.add_task(
                run_analysis_task,
                lottery_match_id,
                play_types
            )

            return {
                "success": True,
                "cached": False,
                "message": "Analysis started in background"
            }

    finally:
        conn.close()


@router.post("/analyze-batch")
async def analyze_batch(
    background_tasks: BackgroundTasks,
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD, 默认今天"),
    match_ids: Optional[str] = Query(None, description="比赛ID列表，逗号分隔"),
    force: bool = Query(False, description="强制重新分析"),
):
    """批量分析：对指定或全部未分析的比赛执行分析

    如果match_ids为空，自动查当天所有未分析比赛。
    跳过无team_id的比赛（标记为skipped）。
    """
    import asyncio
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Determine target match IDs
        target_ids = []
        skipped = 0
        if match_ids:
            target_ids = [mid.strip() for mid in match_ids.split(',') if mid.strip()]
        else:
            target_date = date or datetime.now().strftime('%Y-%m-%d')
            report_cols = get_table_columns(cursor, "lottery_analysis_reports")
            stale_condition = (
                "OR COALESCE(r.is_stale, 0) = 1"
                if "is_stale" in report_cols and not force
                else ""
            )
            analysis_condition = "1 = 1" if force else f"(r.lottery_match_id IS NULL {stale_condition})"
            # Analyze matches without reports, plus stale reports after data backfill.
            cursor.execute(f"""
                SELECT m.lottery_match_id
                FROM lottery_matches m
                LEFT JOIN lottery_analysis_reports r
                    ON m.lottery_match_id = r.lottery_match_id
                    AND r.report_type = 'prediction'
                WHERE m.match_date = ?
                AND {analysis_condition}
                AND m.home_team_id IS NOT NULL
                AND m.away_team_id IS NOT NULL
                ORDER BY m.match_time ASC
            """, (target_date,))
            target_ids = [row['lottery_match_id'] for row in cursor.fetchall()]

            # 统计被跳过的（无team_id）
            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM lottery_matches m
                LEFT JOIN lottery_analysis_reports r
                    ON m.lottery_match_id = r.lottery_match_id
                    AND r.report_type = 'prediction'
                WHERE m.match_date = ?
                AND r.lottery_match_id IS NULL
                AND (m.home_team_id IS NULL OR m.away_team_id IS NULL)
            """, (target_date,))
            skip_row = cursor.fetchone()
            skipped = skip_row['cnt'] if skip_row else 0

        if not target_ids and skipped == 0:
            return {"success": True, "total": 0, "succeeded": 0, "failed": 0,
                    "skipped": 0, "results": []}

        if not target_ids:
            return {"success": True, "total": skipped, "succeeded": 0, "failed": 0,
                    "skipped": skipped, "results": []}

        # Analyze each match using unified pipeline
        from ...core.analyze import analyze_single

        results = []
        succeeded = 0
        failed = 0
        for mid in target_ids[:50]:
            try:
                report = analyze_single(DB_PATH, mid)
                if report:
                    succeeded += 1
                    results.append({"lottery_match_id": mid, "success": True})
                else:
                    failed += 1
                    results.append({"lottery_match_id": mid, "success": False, "error": "empty result"})
            except Exception as e:
                failed += 1
                results.append({"lottery_match_id": mid, "success": False, "error": str(e)})
            # 让出事件循环，避免阻塞整个服务
            await asyncio.sleep(0)

        return {
            "success": True,
            "total": len(target_ids) + skipped,
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "results": results,
        }

    finally:
        conn.close()


@router.get("/report/{lottery_match_id}")
async def get_analysis_report(lottery_match_id: str):
    """
    获取分析报告 — 优先返回prediction格式(有final_prediction+play_predictions)
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Prefer 'prediction' report (has final_prediction + play_predictions)
        # Fall back to 'full' report only if no prediction report exists
        report_cols = get_table_columns(cursor, "lottery_analysis_reports")
        stale_filter = "AND COALESCE(is_stale, 0) = 0" if "is_stale" in report_cols else ""
        cursor.execute(f"""
            SELECT report_data, created_at FROM lottery_analysis_reports
            WHERE lottery_match_id = ? AND report_type = 'prediction'
              {stale_filter}
            ORDER BY datetime(created_at) DESC, rowid DESC
            LIMIT 1
        """, (lottery_match_id,))

        row = cursor.fetchone()
        if not row:
            cursor.execute(f"""
                SELECT report_data, created_at FROM lottery_analysis_reports
                WHERE lottery_match_id = ? AND report_type = 'full'
                  {stale_filter}
                ORDER BY datetime(created_at) DESC, rowid DESC
                LIMIT 1
            """, (lottery_match_id,))
            row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Report not found")

        report = json.loads(row['report_data'])
        learning = _latest_learning_payload(cursor, lottery_match_id)
        if isinstance(report, dict):
            report['_learning'] = learning

        return {
            "success": True,
            "report": report,
            "learning": learning,
            "generated_at": row['created_at']
        }

    finally:
        conn.close()


@router.get("/reanalysis-changes/{lottery_match_id}")
async def get_reanalysis_changes(lottery_match_id: str):
    """获取某场比赛的重分析变更历史"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        if not _table_exists(cursor, "prediction_reanalysis_changes"):
            return {"success": True, "changes": []}
        rows = cursor.execute(
            """
            SELECT change_id, run_id, trigger_source, lottery_match_id, match_date,
                   match_num, league_name_cn, home_team_cn, away_team_cn,
                   before_report_id, after_report_id, prediction_changed,
                   change_json, created_at, settled_at, validation_json
            FROM prediction_reanalysis_changes
            WHERE lottery_match_id = ?
            ORDER BY datetime(created_at) DESC, rowid DESC
            """,
            (lottery_match_id,),
        ).fetchall()
        result = []
        for row in rows:
            change_json = _loads_json(row["change_json"], {})
            validation_json = _loads_json(row["validation_json"], {}) if row["validation_json"] else {}
            if not isinstance(change_json, dict):
                change_json = {}
            if not isinstance(validation_json, dict):
                validation_json = {}
            result.append({
                "change_id": row["change_id"],
                "run_id": row["run_id"],
                "trigger_source": row["trigger_source"],
                "prediction_changed": bool(row["prediction_changed"]),
                "prediction_changes": (change_json.get("prediction_changes") or [])[:8],
                "before_prediction_summary": change_json.get("before_prediction_summary") or {},
                "after_prediction_summary": change_json.get("after_prediction_summary") or {},
                "created_at": row["created_at"],
                "settled_at": row["settled_at"],
                "validation": validation_json,
            })
        return {"success": True, "changes": result}
    finally:
        conn.close()


# ==================== 赔率 ====================

@router.get("/odds/{lottery_match_id}")
async def get_lottery_odds(lottery_match_id: str):
    """
    获取比赛赔率
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT play_type, odds_data, opening_odds, latest_odds, update_time
            FROM lottery_odds
            WHERE lottery_match_id = ?
        """, (lottery_match_id,))

        odds = {}
        for row in cursor.fetchall():
            play_type = row['play_type']
            odds[play_type] = {
                'current': json.loads(row['odds_data']) if row['odds_data'] else {},
                'opening': json.loads(row['opening_odds']) if row['opening_odds'] else {},
                'latest': json.loads(row['latest_odds']) if row['latest_odds'] else {},
                'update_time': row['update_time']
            }

        if not odds:
            raise HTTPException(status_code=404, detail="Odds not found")

        return {
            "success": True,
            "lottery_match_id": lottery_match_id,
            "odds": odds
        }

    finally:
        conn.close()


# ==================== 价值投注 ====================

@router.get("/value-bets/{lottery_match_id}")
async def get_value_bets(lottery_match_id: str):
    """
    获取价值投注推荐
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT prediction_id, play_type, value_bets, confidence
            FROM lottery_predictions
            WHERE lottery_match_id = ?
        """, (lottery_match_id,))

        value_bets = []
        for row in cursor.fetchall():
            if row['value_bets']:
                try:
                    vbs = json.loads(row['value_bets'])
                    for vb in vbs:
                        vb['play_type'] = row['play_type']
                        vb['confidence'] = row['confidence']
                        value_bets.append(vb)
                except:
                    pass

        return {
            "success": True,
            "lottery_match_id": lottery_match_id,
            "value_bets": value_bets,
            "total": len(value_bets)
        }

    finally:
        conn.close()


# ==================== 准确率追踪 ====================

@router.get("/accuracy")
async def get_accuracy_stats(
    days: int = Query(30, ge=1, le=365),
    play_type: Optional[str] = Query(None)
):
    """
    获取预测准确率统计
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 查询各玩法的准确率
        query = """
            SELECT
                play_type,
                COUNT(*) as total,
                SUM(is_correct) as correct
            FROM lottery_validation
            WHERE validated_at >= date('now', ?)
        """
        params = [f'-{days} days']
        valid_prediction_filter = """
            AND predicted_result IS NOT NULL
            AND actual_result IS NOT NULL
            AND TRIM(predicted_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
            AND TRIM(actual_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
        """
        valid_prediction_filter_v = """
            AND v.predicted_result IS NOT NULL
            AND v.actual_result IS NOT NULL
            AND TRIM(v.predicted_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
            AND TRIM(v.actual_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
        """
        query += valid_prediction_filter

        if play_type:
            query += " AND play_type = ?"
            params.append(play_type)

        query += " GROUP BY play_type"

        cursor.execute(query, params)

        # 初始化结果
        result = {
            'spf_accuracy': 0,
            'spf_count': 0,
            'bf_accuracy': 0,
            'bf_count': 0,
            'ou_accuracy': 0,
            'ou_count': 0,
            'bqc_accuracy': 0,
            'bqc_count': 0,
            'rqspf_accuracy': 0,
            'rqspf_count': 0,
            'overall_accuracy': 0,
            'total_count': 0,
            'trend': 0
        }

        total_correct = 0
        total_predictions = 0

        for row in cursor.fetchall():
            pt = row['play_type']
            count = row['total'] or 0
            correct = row['correct'] or 0
            accuracy = (correct / count * 100) if count > 0 else 0

            if pt == 'spf':
                result['spf_accuracy'] = round(accuracy, 1)
                result['spf_count'] = count
            elif pt == 'bf':
                result['bf_accuracy'] = round(accuracy, 1)
                result['bf_count'] = count
            elif pt == 'ou':
                result['ou_accuracy'] = round(accuracy, 1)
                result['ou_count'] = count
            elif pt == 'bqc':
                result['bqc_accuracy'] = round(accuracy, 1)
                result['bqc_count'] = count
            elif pt == 'rqspf':
                result['rqspf_accuracy'] = round(accuracy, 1)
                result['rqspf_count'] = count

            total_correct += correct
            total_predictions += count

        # 计算整体准确率
        if total_predictions > 0:
            result['overall_accuracy'] = round(total_correct / total_predictions * 100, 1)
            result['total_count'] = total_predictions

        # 计算趋势（最近7天与之前7天对比）
        cursor.execute("""
            SELECT
                SUM(is_correct) as correct,
                COUNT(*) as total
            FROM lottery_validation
            WHERE validated_at >= date('now', '-7 days')
              AND predicted_result IS NOT NULL
              AND actual_result IS NOT NULL
              AND TRIM(predicted_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
              AND TRIM(actual_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
        """)
        recent = cursor.fetchone()

        cursor.execute("""
            SELECT
                SUM(is_correct) as correct,
                COUNT(*) as total
            FROM lottery_validation
            WHERE validated_at >= date('now', '-14 days')
              AND validated_at < date('now', '-7 days')
              AND predicted_result IS NOT NULL
              AND actual_result IS NOT NULL
              AND TRIM(predicted_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
              AND TRIM(actual_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
        """)
        previous = cursor.fetchone()

        if recent and previous:
            recent_acc = (recent['correct'] / recent['total']) if recent['total'] > 0 else 0
            prev_acc = (previous['correct'] / previous['total']) if previous['total'] > 0 else 0
            result['trend'] = round((recent_acc - prev_acc) * 100, 1)

        # Fetch recent validation records for display
        recent_records = []
        try:
            cursor.execute("""
                SELECT
                    v.validation_id as id,
                    v.play_type,
                    v.is_correct,
                    v.predicted_result,
                    v.actual_result,
                    v.scenario_type,
                    v.validated_at,
                    v.attribution,
                    m.home_team_cn as home_team,
                    m.away_team_cn as away_team,
                    p.confidence
                FROM lottery_validation v
                LEFT JOIN lottery_matches m ON v.lottery_match_id = m.lottery_match_id
                LEFT JOIN lottery_predictions p ON v.prediction_id = p.prediction_id
                WHERE v.validated_at >= date('now', ?)
            """ + valid_prediction_filter_v + """
                ORDER BY v.validated_at DESC
                LIMIT 20
            """, [f'-{days} days'])
            for row in cursor.fetchall():
                recent_records.append({
                    'id': row['id'],
                    'play_type': row['play_type'],
                    'is_correct': bool(row['is_correct']),
                    'predicted': row['predicted_result'] or '',
                    'actual': row['actual_result'] or '',
                    'scenario': row['scenario_type'] or '',
                    'attribution': row['attribution'] or '',
                    'validated_at': row['validated_at'] or '',
                    'home_team': row['home_team'] or '',
                    'away_team': row['away_team'] or '',
                    'confidence': round((row['confidence'] or 0) * 100, 1)
                })
        except Exception as e:
            import logging
            logging.warning(f"Failed to fetch recent validations: {e}")

        return {
            "success": True,
            "days": days,
            "recent": recent_records,
            **result
        }

    finally:
        conn.close()


@router.get("/automation-timeline")
async def get_automation_timeline(hours: int = Query(24, ge=1, le=168)):
    """最近N小时任务执行时间线 — 从真实运行表聚合"""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cutoff_sql = "datetime('now', ?)"
        cutoff_arg = f"-{hours} hours"
        events = []

        # 1. 日循环节点 (daily_cycle_state)
        try:
            cursor.execute(f"""
                SELECT date, current_node, status, started_at, updated_at, error_message,
                       perceive_result, collect_result, intel_result, classify_result,
                       analyze_result, push_result, learn_result
                FROM daily_cycle_state
                WHERE COALESCE(updated_at, started_at) IS NOT NULL
                  AND COALESCE(updated_at, started_at) >= {cutoff_sql}
                ORDER BY COALESCE(updated_at, started_at) DESC
                LIMIT 50
            """, (cutoff_arg,))
            for row in cursor.fetchall():
                r = dict(row)
                ts = (r.get('updated_at') or r.get('started_at') or '')[:19]
                events.append({
                    'id': f"cycle_{r.get('date', '')}",
                    'name': f"日循环 · {r.get('current_node', '?')}",
                    'status': r.get('status', ''),
                    'time': ts,
                    'duration': None,
                    'category': 'cycle',
                    'detail': r.get('date', ''),
                    'error': r.get('error_message') or '',
                })
        except Exception as e:
            logger.warning('timeline daily_cycle_state查询失败: %s', e)

        # 2. 采集任务 (collection_runs)
        try:
            cursor.execute(f"""
                SELECT run_id, trigger_source, run_type, match_date, status,
                       started_at, finished_at, error, summary_json
                FROM collection_runs
                WHERE started_at IS NOT NULL
                  AND started_at >= {cutoff_sql}
                ORDER BY started_at DESC
                LIMIT 80
            """, (cutoff_arg,))
            for row in cursor.fetchall():
                r = dict(row)
                duration = None
                if r.get('started_at') and r.get('finished_at'):
                    try:
                        s = datetime.fromisoformat(r['started_at'])
                        e = datetime.fromisoformat(r['finished_at'])
                        duration = round((e - s).total_seconds(), 1)
                    except Exception:
                        pass
                events.append({
                    'id': r.get('run_id', ''),
                    'name': f"采集 · {r.get('run_type', '?')}",
                    'status': r.get('status', ''),
                    'time': (r.get('started_at') or '')[:19],
                    'duration': duration,
                    'category': 'collect',
                    'detail': f"{r.get('trigger_source', '')} · {r.get('match_date', '')}",
                    'error': r.get('error') or '',
                })
        except Exception as e:
            logger.warning('timeline collection_runs查询失败: %s', e)

        # 3. 情报任务 (intelligence_runs)
        try:
            cursor.execute(f"""
                SELECT run_id, run_date, trigger_source, status,
                       started_at, finished_at, error, summary_json
                FROM intelligence_runs
                WHERE started_at IS NOT NULL
                  AND started_at >= {cutoff_sql}
                ORDER BY started_at DESC
                LIMIT 50
            """, (cutoff_arg,))
            for row in cursor.fetchall():
                r = dict(row)
                duration = None
                if r.get('started_at') and r.get('finished_at'):
                    try:
                        s = datetime.fromisoformat(r['started_at'])
                        e = datetime.fromisoformat(r['finished_at'])
                        duration = round((e - s).total_seconds(), 1)
                    except Exception:
                        pass
                events.append({
                    'id': r.get('run_id', ''),
                    'name': f"情报 · {r.get('run_date', '?')}",
                    'status': r.get('status', ''),
                    'time': (r.get('started_at') or '')[:19],
                    'duration': duration,
                    'category': 'intel',
                    'detail': r.get('trigger_source', ''),
                    'error': r.get('error') or '',
                })
        except Exception as e:
            logger.warning('timeline intelligence_runs查询失败: %s', e)

        # 按时间倒序合并
        events.sort(key=lambda x: x.get('time', ''), reverse=True)
        return {'events': events[:100], 'hours': hours, 'total': len(events)}
    except Exception as e:
        return {'events': [], 'error': str(e)}
    finally:
        conn.close()


@router.get("/discovered-segments")
async def get_discovered_segments():
    """获取自动挖掘的场景偏差segment"""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT param_name, old_value, new_value, change_reason, sample_size, changed_at
            FROM model_params_history
            WHERE param_name LIKE 'segment:%'
            ORDER BY changed_at DESC
            LIMIT 20
        """)
        segments = []
        for row in cursor.fetchall():
            r = dict(row)
            # 解析 segment key
            key = r.get('param_name', '').replace('segment:', '')
            reason = r.get('change_reason', '')
            segments.append({
                'key': key,
                'model_accuracy': r.get('new_value'),
                'odds_accuracy': r.get('old_value'),
                'sample': r.get('sample_size', 0),
                'gap': (r.get('new_value') or 0) - (r.get('old_value') or 0),
                'reason': reason,
                'changed_at': r.get('changed_at'),
            })
        return {'segments': segments}
    except Exception as e:
        return {'segments': [], 'error': str(e)}
    finally:
        conn.close()


@router.get("/calibration-backtest")
async def get_calibration_backtest(days: int = Query(60, ge=7, le=180)):
    """校准效果回测 — 量化校准作为信心分层的价值

    对比 raw_prob vs calibrated_prob 按高/中/低信心档分组的准确率,
    计算 separation_lift = (cal高-低) - (raw高-低), 正值=校准提升区分度.
    """
    try:
        from backend.app.core.calibration_backtest import backtest_summary
        summary = backtest_summary(DB_PATH, days=days)
        return {'days': days, 'summary': summary}
    except Exception as e:
        return {'days': days, 'summary': {}, 'error': str(e)}


@router.get("/scene-accuracy")
async def get_scene_accuracy(days: int = Query(30, ge=1, le=180)):
    """场景×玩法准确率矩阵 — 驾驶舱热力图数据源

    返回每个 (scenario_type, play_type) 组合的准确率、样本数、与基线差距。
    用于在驾驶舱"学习进度"标签页展示热力图。
    """
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT scenario_type, play_type,
                   COUNT(*) as sample,
                   SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) as correct,
                   ROUND(AVG(CASE WHEN is_correct=1 THEN 1.0 ELSE 0 END)*100, 1) as accuracy
            FROM lottery_validation
            WHERE validated_at >= datetime('now', ?)
              AND scenario_type IS NOT NULL
              AND play_type IS NOT NULL
            GROUP BY scenario_type, play_type
            ORDER BY scenario_type, sample DESC
        """, (f'-{days} days',))
        rows = [dict(r) for r in cursor.fetchall()]

        # 整体基线
        cursor.execute("""
            SELECT ROUND(AVG(CASE WHEN is_correct=1 THEN 1.0 ELSE 0 END)*100, 1) as baseline
            FROM lottery_validation
            WHERE validated_at >= datetime('now', ?)
        """, (f'-{days} days',))
        baseline_row = cursor.fetchone()
        baseline = baseline_row['baseline'] if baseline_row else 0

        # 按 scenario 汇总
        scenarios = {}
        for r in rows:
            sc = r['scenario_type']
            if sc not in scenarios:
                scenarios[sc] = {'scenario': sc, 'plays': [], 'total_sample': 0, 'total_correct': 0}
            r['gap_vs_baseline'] = round(r['accuracy'] - baseline, 1)
            r['status'] = (
                'strong' if r['accuracy'] >= baseline + 5 and r['sample'] >= 10 else
                'weak' if r['accuracy'] <= baseline - 5 and r['sample'] >= 10 else
                'normal'
            )
            scenarios[sc]['plays'].append(r)
            scenarios[sc]['total_sample'] += r['sample']
            scenarios[sc]['total_correct'] += r['correct']

        for sc in scenarios.values():
            sc['overall_accuracy'] = round(
                sc['total_correct'] / sc['total_sample'] * 100, 1
            ) if sc['total_sample'] else 0

        return {
            'baseline': baseline,
            'days': days,
            'scenarios': list(scenarios.values()),
            'total_samples': sum(r['sample'] for r in rows),
        }
    except Exception as e:
        return {'baseline': 0, 'scenarios': [], 'error': str(e)}
    finally:
        conn.close()


@router.get("/push-history")
async def get_push_history(limit: int = Query(10, ge=1, le=50)):
    """获取推送历史（含Agent早报）"""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # 确保表存在
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS push_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                push_date TEXT NOT NULL,
                mode TEXT,
                predictions_count INTEGER,
                top3_json TEXT,
                stop_loss_json TEXT,
                roi_summary_json TEXT,
                agent_report_text TEXT,
                agent_decision_json TEXT,
                channels_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("""
            SELECT id, push_date, mode, predictions_count,
                   agent_report_text, roi_summary_json, stop_loss_json,
                   agent_decision_json, created_at
            FROM push_history
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
        return {'history': rows}
    except Exception as e:
        return {'history': [], 'error': str(e)}
    finally:
        conn.close()


@router.get("/learning-history")
async def get_learning_history(limit: int = Query(20, ge=1, le=200)):
    """模型参数变更历史"""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, model_version, param_name, old_value, new_value,
                   change_reason, accuracy_before, accuracy_after, sample_size, changed_at
            FROM model_params_history
            ORDER BY changed_at DESC
            LIMIT ?
        """, (limit,))
        changes = [dict(r) for r in cursor.fetchall()]
        return {'changes': changes}
    except Exception as e:
        return {'changes': [], 'error': str(e)}
    finally:
        conn.close()


@router.get("/roi-trend")
async def get_roi_trend(days: int = Query(30, ge=1, le=180)):
    """ROI时序数据（按天）"""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT DATE(created_at) as d,
                   COUNT(*) as bets,
                   SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(profit) as pnl,
                   SUM(stake) as staked
            FROM bet_records
            WHERE created_at >= date('now', ?)
            GROUP BY DATE(created_at)
            ORDER BY d
        """, (f'-{days} days',))
        rows = [dict(r) for r in cursor.fetchall()]
        trend = []
        cum_pnl = 0
        for r in rows:
            staked = r.get('staked') or 0
            pnl = r.get('pnl') or 0
            cum_pnl += pnl
            roi = (pnl / staked * 100) if staked > 0 else 0
            cum_roi = (cum_pnl / sum(x.get('staked') or 0 for x in rows[:rows.index(r)+1]) * 100) if any(x.get('staked') for x in rows[:rows.index(r)+1]) else 0
            trend.append({
                'date': r.get('d'),
                'bets': r.get('bets'),
                'wins': r.get('wins'),
                'pnl': round(pnl, 2),
                'roi': round(roi, 2),
                'cum_roi': round(cum_roi, 2),
            })
        return {'trend': trend}
    except Exception as e:
        return {'trend': [], 'error': str(e)}
    finally:
        conn.close()


@router.get("/roi")
async def get_roi_summary():
    """ROI概况 — 7d/30d/all + 近期结算记录"""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        def _summary(days):
            if days is None:
                where = "WHERE profit IS NOT NULL"
            else:
                where = f"WHERE created_at >= date('now', '-{days} days') AND profit IS NOT NULL"
            row = cursor.execute(f"""
                SELECT COUNT(*) as matches,
                       SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                       COALESCE(SUM(profit), 0) as profit,
                       COALESCE(SUM(stake), 0) as staked
                FROM bet_records {where}
            """).fetchone()
            matches = row['matches'] or 0
            wins = row['wins'] or 0
            profit = row['profit'] or 0
            staked = row['staked'] or 0
            roi = (profit / staked * 100) if staked > 0 else 0
            return {
                'matches': matches,
                'wins': wins,
                'profit': round(profit, 2),
                'roi': f'{roi:.1f}%',
            }

        summary = {
            '7d': _summary(7),
            '30d': _summary(30),
            'all': _summary(None),
        }

        cursor.execute("""
            SELECT id, lottery_match_id, play_type, selection, odds,
                   stake, profit, result, created_at
            FROM bet_records
            WHERE profit IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 10
        """)
        recent = [dict(r) for r in cursor.fetchall()]

        return {'summary': summary, 'recent_bets': recent}
    except Exception as e:
        return {'summary': {}, 'recent_bets': [], 'error': str(e)}
    finally:
        conn.close()


@router.get("/model-status")
async def get_model_status():
    """当前模型版本、权重、学习历史和gate状态"""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    try:
        # Active weights
        row = conn.execute("SELECT * FROM model_weights WHERE is_active = 1 LIMIT 1").fetchone()
        active_weights = dict(row) if row else {}

        # Model version
        version = active_weights.get('version', 'unknown')
        created_at = active_weights.get('created_at', '')

        # Recent param changes (last 5)
        changes = conn.execute("""
            SELECT param_name, old_value, new_value, change_reason, changed_at
            FROM model_params_history
            ORDER BY changed_at DESC
            LIMIT 5
        """).fetchall()
        recent_changes = [dict(r) for r in changes]

        # Current accuracy (30d SPF)
        acc_row = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct
            FROM lottery_validation
            WHERE play_type = 'spf'
              AND validated_at >= date('now', '-30 days')
              AND predicted_result IS NOT NULL AND actual_result IS NOT NULL
        """).fetchone()
        accuracy = round(acc_row['correct'] / acc_row['total'], 4) if acc_row and acc_row['total'] > 0 else 0

        # Per-play-type accuracy vs targets
        ACCURACY_TARGETS = {'spf': 0.60, 'ou': 0.56, 'rqspf': 0.54, 'bqc': 0.45, 'bf': 0.25}
        play_accuracy = {}
        for pt, target in ACCURACY_TARGETS.items():
            row = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct
                FROM lottery_validation
                WHERE play_type = ?
                  AND predicted_result IS NOT NULL AND actual_result IS NOT NULL
            """, (pt,)).fetchone()
            cur = round(row['correct'] / row['total'], 4) if row and row['total'] > 0 else 0
            play_accuracy[pt] = {
                'current': cur,
                'target': target,
                'gap_pp': round((cur - target) * 100, 1),
                'met': cur >= target,
            }

        return {
            "model_version": version,
            "weights_created_at": created_at,
            "active_weights": {
                k.replace('_weight', ''): round(v, 4)
                for k, v in active_weights.items()
                if k.endswith('_weight') and v is not None
            } if active_weights else {},
            "current_accuracy_30d": accuracy,
            "play_accuracy_targets": play_accuracy,
            "recent_changes": recent_changes,
            "gate": {
                "enabled": True,
                "overall_tolerance_pp": 1.0,
                "rollback_supported": True,
            },
        }
    finally:
        conn.close()


@router.get("/accuracy-trend")
async def get_accuracy_trend(
    days: int = Query(30, ge=7, le=365),
    play_type: Optional[str] = Query(None),
    granularity: str = Query("day", regex="^(day|week)$")
):
    """
    获取准确率趋势数据（按日/周聚合）
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Build date grouping based on granularity
        if granularity == "week":
            date_group = "strftime('%Y-W%W', validated_at)"
        else:
            date_group = "DATE(validated_at)"

        query = f"""
            SELECT
                {date_group} as period,
                play_type,
                COUNT(*) as total,
                SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct
            FROM lottery_validation
            WHERE validated_at >= date('now', ?)
            AND predicted_result IS NOT NULL
            AND actual_result IS NOT NULL
            AND TRIM(predicted_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
            AND TRIM(actual_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
        """
        params = [f'-{days} days']

        if play_type:
            query += " AND play_type = ?"
            params.append(play_type)

        query += f" GROUP BY {date_group}, play_type ORDER BY {date_group} ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Aggregate by period
        trend_data = {}
        for row in rows:
            period = row["period"]
            pt = row["play_type"] or "spf"
            total = row["total"] or 0
            correct = row["correct"] or 0
            acc = round((correct / total * 100) if total > 0 else 0, 1)

            if period not in trend_data:
                trend_data[period] = {"period": period, "total": 0, "correct": 0, "play_types": {}}
            trend_data[period]["total"] += total
            trend_data[period]["correct"] += correct
            trend_data[period]["play_types"][pt] = {"total": total, "correct": correct, "accuracy": acc}

        # Calculate overall accuracy per period
        result = []
        for period in sorted(trend_data.keys()):
            data = trend_data[period]
            overall_acc = round((data["correct"] / data["total"] * 100) if data["total"] > 0 else 0, 1)
            result.append({
                "period": period,
                "accuracy": overall_acc,
                "total": data["total"],
                "correct": data["correct"],
                "play_types": data["play_types"]
            })

        return {"success": True, "trend": result, "granularity": granularity, "days": days}

    finally:
        conn.close()


@router.get("/baseline-comparison")
async def get_baseline_comparison(
    play_type: str = Query("spf", regex="^(spf|rqspf|ou|bqc|bf)$"),
    days: int = Query(30, ge=7, le=365),
):
    """模型基线对比：market_favorite / poisson / elo / recent_form / hybrid_current"""
    try:
        from backend.app.core.model_baselines import query_baseline_comparison, ensure_table
        conn = sqlite3.connect(DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        ensure_table(conn)
        result = query_baseline_comparison(conn, play_type=play_type, days=days)
        conn.close()
        return {"success": True, **result}
    except Exception as exc:
        return {"success": False, "error": str(exc), "play_type": play_type}


@router.get("/time-split-comparison")
async def get_time_split_comparison(
    play_type: str = Query("spf", regex="^(spf|rqspf|ou|bqc|bf)$"),
    total_days: int = Query(90, ge=30, le=365),
):
    """时间分割基线对比：train(60%)/validation(20%)/test(20%)，检测过拟合"""
    try:
        from backend.app.core.model_baselines import query_time_split_comparison, ensure_table
        conn = sqlite3.connect(DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        ensure_table(conn)
        result = query_time_split_comparison(conn, play_type=play_type, total_days=total_days)
        conn.close()
        return {"success": True, **result}
    except Exception as exc:
        return {"success": False, "error": str(exc), "play_type": play_type}


@router.get("/competition-split-comparison")
async def get_competition_split_comparison(
    play_type: str = Query("spf", regex="^(spf|rqspf|ou|bqc|bf)$"),
    days: int = Query(90, ge=30, le=365),
):
    """按赛事类型基线对比：联赛/杯赛/国家队/友谊赛等分组"""
    try:
        from backend.app.core.model_baselines import query_competition_split_comparison, ensure_table
        conn = sqlite3.connect(DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        ensure_table(conn)
        result = query_competition_split_comparison(conn, play_type=play_type, days=days)
        conn.close()
        return {"success": True, **result}
    except Exception as exc:
        return {"success": False, "error": str(exc), "play_type": play_type}


@router.get("/match-script/{lottery_match_id}")
async def get_match_script(lottery_match_id: str):
    """获取某场比赛的match_script(方向轴/边界轴/进球轴/BTTS/半场节奏/一致性)"""
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT report_json FROM lottery_analysis_reports
               WHERE lottery_match_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (lottery_match_id,),
        ).fetchone()
        if not row:
            return {"success": False, "error": "no_analysis_report"}

        report = json.loads(row["report_json"] or "{}")
        plays = report.get("play_predictions", {})
        match_script_data = report.get("match_script")

        if not match_script_data:
            # Build on-the-fly from stored report
            try:
                from backend.app.core.match_script import build_match_script
                match_script_data = build_match_script(plays, report)
            except Exception:
                return {"success": False, "error": "match_script_not_available"}

        return {"success": True, "lottery_match_id": lottery_match_id, "match_script": match_script_data}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    finally:
        conn.close()


@router.get("/accuracy/by-confidence")
async def get_accuracy_by_confidence(days: int = Query(30)):
    """
    按置信度分组获取准确率
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                p.confidence_level,
                COUNT(*) as total,
                SUM(v.is_correct) as correct,
                AVG(v.brier_score) as avg_brier_score
            FROM lottery_predictions p
            JOIN lottery_validation v ON p.prediction_id = v.prediction_id
            WHERE v.validated_at >= date('now', ?)
            GROUP BY p.confidence_level
        """, (f'-{days} days',))

        stats = []
        for row in cursor.fetchall():
            accuracy = row['correct'] / row['total'] if row['total'] > 0 else 0
            stats.append({
                'confidence_level': row['confidence_level'],
                'total_predictions': row['total'],
                'accuracy': round(accuracy * 100, 2),
                'avg_brier_score': round(row['avg_brier_score'], 4) if row['avg_brier_score'] else None
            })

        return {
            "success": True,
            "days": days,
            "stats": stats
        }

    finally:
        conn.close()


@router.get("/accuracy-by-tier")
async def get_accuracy_by_tier(days: int = Query(30)):
    """按置信度分层(strong/medium/low/avoid)获取准确率"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # By tier
        cursor.execute("""
            SELECT confidence_tier, play_type,
                   COUNT(*) as total,
                   SUM(is_correct) as correct,
                   AVG(brier_score) as avg_brier
            FROM lottery_validation
            WHERE validated_at >= date('now', ?)
              AND confidence_tier IS NOT NULL
              AND confidence > 0
            GROUP BY confidence_tier, play_type
            ORDER BY confidence_tier, play_type
        """, (f'-{days} days',))
        by_tier_play = []
        for row in cursor.fetchall():
            acc = row['correct'] / row['total'] if row['total'] > 0 else 0
            by_tier_play.append({
                'tier': row['confidence_tier'],
                'play_type': row['play_type'],
                'total': row['total'],
                'correct': row['correct'],
                'accuracy': round(acc * 100, 1),
                'avg_brier': round(row['avg_brier'], 4) if row['avg_brier'] else None,
            })

        # Overall by tier
        cursor.execute("""
            SELECT confidence_tier,
                   COUNT(*) as total,
                   SUM(is_correct) as correct
            FROM lottery_validation
            WHERE validated_at >= date('now', ?)
              AND confidence_tier IS NOT NULL
              AND confidence > 0
            GROUP BY confidence_tier
            ORDER BY confidence_tier
        """, (f'-{days} days',))
        by_tier = []
        for row in cursor.fetchall():
            acc = row['correct'] / row['total'] if row['total'] > 0 else 0
            by_tier.append({
                'tier': row['confidence_tier'],
                'total': row['total'],
                'correct': row['correct'],
                'accuracy': round(acc * 100, 1),
            })

        # Settlement grade distribution
        cursor.execute("""
            SELECT play_type, settlement_grade, COUNT(*) as total,
                   SUM(is_correct) as correct
            FROM lottery_validation
            WHERE validated_at >= date('now', ?)
              AND settlement_grade IS NOT NULL
            GROUP BY play_type, settlement_grade
            ORDER BY play_type, settlement_grade
        """, (f'-{days} days',))
        settlement = []
        for row in cursor.fetchall():
            settlement.append({
                'play_type': row['play_type'],
                'grade': row['settlement_grade'],
                'total': row['total'],
                'correct': row['correct'],
            })

        # Enriched BF metrics
        cursor.execute("""
            SELECT
                SUM(top3_score_hit) as top3_hits,
                SUM(goal_bucket_hit) as goal_bucket_hits,
                SUM(margin_bucket_hit) as margin_bucket_hits,
                SUM(btts_hit) as btts_hits,
                SUM(ou_consistency_hit) as ou_consistency_hits,
                COUNT(*) as total
            FROM lottery_validation
            WHERE play_type = 'bf' AND validated_at >= date('now', ?)
        """, (f'-{days} days',))
        bf_metrics = {}
        row = cursor.fetchone()
        if row and row['total']:
            bf_metrics = {
                'total': row['total'],
                'top3_score_hit_rate': round(row['top3_hits'] / row['total'] * 100, 1),
                'goal_bucket_hit_rate': round(row['goal_bucket_hits'] / row['total'] * 100, 1),
                'margin_bucket_hit_rate': round(row['margin_bucket_hits'] / row['total'] * 100, 1),
                'btts_hit_rate': round(row['btts_hits'] / row['total'] * 100, 1),
                'ou_consistency_hit_rate': round(row['ou_consistency_hits'] / row['total'] * 100, 1),
            }

        return {
            "success": True,
            "days": days,
            "by_tier": by_tier,
            "by_tier_play": by_tier_play,
            "settlement": settlement,
            "bf_enriched_metrics": bf_metrics,
        }
    finally:
        conn.close()


@router.get("/validation-metrics")
async def get_validation_metrics(days: int = Query(30)):
    """综合验证指标：accuracy + Brier + calibration + market_baseline_diff + high_conf_accuracy"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Per play-type metrics
        cursor.execute("""
            SELECT play_type,
                   COUNT(*) as total,
                   SUM(is_correct) as correct,
                   ROUND(AVG(is_correct), 4) as accuracy,
                   ROUND(AVG(brier_score), 4) as avg_brier,
                   ROUND(AVG(CASE WHEN confidence >= 0.75 THEN is_correct END), 4) as high_conf_accuracy,
                   ROUND(AVG(CASE WHEN confidence < 0.55 THEN 1 ELSE 0 END), 4) as low_conf_rate
            FROM lottery_validation
            WHERE validated_at >= date('now', ?)
            GROUP BY play_type
            ORDER BY play_type
        """, (f'-{days} days',))
        by_play = []
        for row in cursor.fetchall():
            by_play.append({
                'play_type': row['play_type'],
                'total': row['total'],
                'correct': row['correct'],
                'accuracy': row['accuracy'],
                'avg_brier': row['avg_brier'],
                'high_conf_accuracy': row['high_conf_accuracy'],
                'low_conf_rate': row['low_conf_rate'],
            })

        # Calibration data: group by confidence bucket
        cursor.execute("""
            SELECT
                CASE
                    WHEN confidence >= 0.80 THEN '0.80-1.00'
                    WHEN confidence >= 0.70 THEN '0.70-0.80'
                    WHEN confidence >= 0.60 THEN '0.60-0.70'
                    WHEN confidence >= 0.50 THEN '0.50-0.60'
                    WHEN confidence >= 0.40 THEN '0.40-0.50'
                    ELSE '0.00-0.40'
                END as conf_bucket,
                COUNT(*) as total,
                SUM(is_correct) as correct,
                ROUND(AVG(confidence), 4) as avg_confidence,
                ROUND(AVG(is_correct), 4) as actual_accuracy
            FROM lottery_validation
            WHERE validated_at >= date('now', ?) AND confidence > 0
            GROUP BY conf_bucket
            ORDER BY conf_bucket
        """, (f'-{days} days',))
        calibration = []
        for row in cursor.fetchall():
            calibration.append({
                'bucket': row['conf_bucket'],
                'total': row['total'],
                'avg_confidence': row['avg_confidence'],
                'actual_accuracy': row['actual_accuracy'],
                'calibration_gap': round((row['avg_confidence'] or 0) - (row['actual_accuracy'] or 0), 4),
            })

        # Market baseline diff: model accuracy vs market_favorite from model_baselines
        market_diff = {}
        try:
            cursor.execute("""
                SELECT mb.play_type,
                       ROUND(AVG(CASE WHEN mb.baseline = 'market_favorite' THEN mb.is_correct END), 4) as market_acc,
                       ROUND(AVG(CASE WHEN mb.baseline = 'hybrid_current' THEN mb.is_correct END), 4) as model_acc
                FROM model_baselines mb
                WHERE mb.is_correct IS NOT NULL
                  AND mb.created_at >= date('now', ?)
                GROUP BY mb.play_type
            """, (f'-{days} days',))
            for row in cursor.fetchall():
                m = row['market_acc'] or 0
                o = row['model_acc'] or 0
                market_diff[row['play_type']] = {
                    'market_accuracy': m,
                    'model_accuracy': o,
                    'delta_pp': round((o - m) * 100, 2),
                    'beats_market': o > m,
                }
        except Exception:
            pass

        # Settlement distribution
        cursor.execute("""
            SELECT play_type, settlement_grade, COUNT(*) as total
            FROM lottery_validation
            WHERE validated_at >= date('now', ?) AND settlement_grade IS NOT NULL
            GROUP BY play_type, settlement_grade
            ORDER BY play_type, settlement_grade
        """, (f'-{days} days',))
        settlement = []
        for row in cursor.fetchall():
            settlement.append({
                'play_type': row['play_type'],
                'grade': row['settlement_grade'],
                'total': row['total'],
            })

        # Leakage flag summary
        leakage_summary = {}
        try:
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN leakage_flag IS NOT NULL AND leakage_flag != '' THEN 1 ELSE 0 END) as flagged
                FROM lottery_validation
                WHERE validated_at >= date('now', ?)
            """, (f'-{days} days',))
            row = cursor.fetchone()
            if row:
                leakage_summary = {
                    'total': row['total'],
                    'flagged': row['flagged'],
                    'flag_rate': round(row['flagged'] / row['total'], 4) if row['total'] else 0,
                }
        except Exception:
            pass

        return {
            "success": True,
            "days": days,
            "by_play_type": by_play,
            "calibration": calibration,
            "market_baseline_diff": market_diff,
            "settlement": settlement,
            "leakage_summary": leakage_summary,
        }
    finally:
        conn.close()


@router.get("/next-data-requirements")
async def get_next_data_requirements(
    status: str = Query("pending", regex="^(pending|resolved|all)$"),
    limit: int = Query(50, ge=1, le=500),
):
    """错误归因产生的数据需求：pending=待采集, resolved=已满足"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        exists = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='next_data_requirements'"
        ).fetchone()
        if not exists:
            return {"success": True, "requirements": [], "total": 0}

        where = "1=1"
        params = []
        if status != "all":
            where += " AND status = ?"
            params.append(status)

        rows = cursor.execute(
            f"""SELECT lottery_match_id, play_type, error_category, requirement_key,
                       channel, reason, priority, status, created_at, resolved_at
                FROM next_data_requirements
                WHERE {where}
                ORDER BY priority DESC, created_at DESC
                LIMIT ?""",
            params + [limit],
        ).fetchall()

        total = cursor.execute(
            f"SELECT COUNT(*) FROM next_data_requirements WHERE {where}",
            params,
        ).fetchone()[0]

        return {
            "success": True,
            "requirements": [dict(r) for r in rows],
            "total": total,
        }
    finally:
        conn.close()


# ==================== 数据同步 ====================

@router.post("/sync")
async def sync_lottery_data():
    """
    手动触发数据同步（同步执行，返回详细结果）

    步骤:
    1. 采集体彩赛程+赔率
    2. 更新已过开赛时间的比赛状态 (selling → closed)
    3. 更新有结果的比赛状态 (closed → finished)
    """
    logger.info("Starting lottery data sync")

    try:
        from ..services.sync_service import LotterySyncService

        sync_service = LotterySyncService(DB_PATH)
        result = sync_service.sync_daily_matches(
            bridge_oddsfe=False,
            trigger_source='lottery_api_fast_sporttery',
        )
        sync_service.close()

        # 更新已过开赛时间的比赛状态
        conn = get_db()
        cursor = conn.cursor()

        # selling → closed: 比赛时间已过
        cursor.execute("""
            UPDATE lottery_matches SET sell_status = 'closed'
            WHERE sell_status = 'selling'
            AND (beijing_time IS NOT NULL AND datetime(beijing_time) < datetime('now', '+8 hours'))
        """)
        closed_count = cursor.rowcount

        # selling → closed: 用match_date+match_time判断（无beijing_time时）
        cursor.execute("""
            UPDATE lottery_matches SET sell_status = 'closed'
            WHERE sell_status = 'selling'
            AND beijing_time IS NULL
            AND match_date < date('now', '+8 hours')
        """)
        closed_count += cursor.rowcount

        # closed → finished: 已有结果数据
        cursor.execute("""
            UPDATE lottery_matches SET sell_status = 'finished'
            WHERE sell_status = 'closed'
            AND lottery_match_id IN (
                SELECT lottery_match_id FROM lottery_results
            )
        """)
        finished_count = cursor.rowcount

        conn.commit()
        conn.close()

        logger.info(f"Sync completed: {result}, closed={closed_count}, finished={finished_count}")

        return {
            "success": True,
            "saved": result.get('saved', 0),
            "odds_saved": result.get('odds_saved', 0),
            "bridged": result.get('bridged', 0),
            "closed": closed_count,
            "finished": finished_count,
            "message": f"同步完成：{result.get('saved', 0)} 场比赛, {closed_count} 场已闭, {finished_count} 场已结束"
        }

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_predictions(background_tasks: BackgroundTasks):
    """
    手动触发预测验证
    """
    background_tasks.add_task(run_validation_task)

    return {
        "success": True,
        "message": "Validation started in background"
    }


@router.post("/backfill-results")
async def backfill_results(
    background_tasks: BackgroundTasks,
    days: int = Query(7, ge=1, le=30, description="补齐最近N天的结果")
):
    """
    补齐已结束比赛的结果数据

    从sporttery/oddsfe/统一库同步过去N天的比赛结果，
    更新closed比赛的状态和比分。
    """
    background_tasks.add_task(run_backfill_task, days)

    return {
        "success": True,
        "message": f"Backfill started for past {days} days",
        "days": days
    }


@router.get("/backfill-results/status")
async def get_backfill_status():
    """
    获取结果补齐状态

    返回有多少closed比赛缺少结果数据
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # closed但没有结果的比赛数
        cursor.execute("""
            SELECT COUNT(*) FROM lottery_matches lm
            WHERE lm.sell_status = 'closed'
            AND NOT EXISTS (
                SELECT 1 FROM lottery_results lr
                WHERE lr.lottery_match_id = lm.lottery_match_id
            )
        """)
        missing_results = cursor.fetchone()[0]

        # 有结果的closed比赛数
        cursor.execute("""
            SELECT COUNT(*) FROM lottery_matches lm
            WHERE lm.sell_status IN ('closed', 'finished')
            AND EXISTS (
                SELECT 1 FROM lottery_results lr
                WHERE lr.lottery_match_id = lm.lottery_match_id
            )
        """)
        with_results = cursor.fetchone()[0]

        # 总closed比赛数
        cursor.execute("SELECT COUNT(*) FROM lottery_matches WHERE sell_status IN ('closed', 'finished')")
        total_closed = cursor.fetchone()[0]

        return {
            "success": True,
            "total_closed": total_closed,
            "with_results": with_results,
            "missing_results": missing_results
        }

    finally:
        conn.close()


# ==================== 球队映射 ====================

@router.post("/results/{lottery_match_id}/correct")
async def correct_lottery_result(lottery_match_id: str, data: Dict):
    """Manually correct a lottery result with an audit trail."""
    missing = [key for key in ("home_goals_ft", "away_goals_ft") if data.get(key) is None]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")

    try:
        home_ft = int(data.get("home_goals_ft"))
        away_ft = int(data.get("away_goals_ft"))
        home_ht = int(data["home_goals_ht"]) if data.get("home_goals_ht") is not None else None
        away_ht = int(data["away_goals_ht"]) if data.get("away_goals_ht") is not None else None
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Score fields must be integers") from exc

    conn = get_db()
    cursor = conn.cursor()
    try:
        _ensure_result_correction_table(cursor)
        match = cursor.execute(
            """
            SELECT lottery_match_id, match_id, home_team_cn, away_team_cn,
                   handicap_line, sell_status
            FROM lottery_matches
            WHERE lottery_match_id = ?
            """,
            (lottery_match_id,),
        ).fetchone()
        if not match:
            raise HTTPException(status_code=404, detail="lottery match not found")

        columns = get_table_columns(cursor, "lottery_results")
        order_clause = "created_at DESC" if "created_at" in columns else "rowid DESC"
        existing = cursor.execute(
            f"SELECT rowid AS _rowid, * FROM lottery_results WHERE lottery_match_id = ? ORDER BY {order_clause} LIMIT 1",
            (lottery_match_id,),
        ).fetchone()
        before = dict(existing) if existing else None
        after = _derive_result_codes(home_ft, away_ft, home_ht, away_ht, match["handicap_line"], lottery_match_id)
        after.update(
            {
                "lottery_match_id": lottery_match_id,
                "match_id": match["match_id"],
                "draw_time": data.get("draw_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

        if existing:
            update_cols = [
                col for col in (
                    "match_id",
                    "home_goals_ft",
                    "away_goals_ft",
                    "home_goals_ht",
                    "away_goals_ht",
                    "spf_result",
                    "bf_result",
                    "bqc_result",
                    "rqspf_result",
                    "ou_result",
                    "draw_time",
                    "created_at",
                )
                if col in columns
            ]
            cursor.execute(
                f"UPDATE lottery_results SET {', '.join(f'{col} = ?' for col in update_cols)} WHERE rowid = ?",
                tuple(after.get(col) for col in update_cols) + (existing["_rowid"],),
            )
            result_id = existing["result_id"] if "result_id" in columns else None
        else:
            next_id = None
            if "result_id" in columns:
                if data.get("result_id") is not None:
                    next_id = data.get("result_id")
                else:
                    next_id = cursor.execute("SELECT COALESCE(MAX(result_id), 0) + 1 FROM lottery_results").fetchone()[0]
            if "result_id" in columns:
                after["result_id"] = next_id
            insert_cols = [
                col for col in (
                    "result_id",
                    "lottery_match_id",
                    "match_id",
                    "home_goals_ft",
                    "away_goals_ft",
                    "home_goals_ht",
                    "away_goals_ht",
                    "spf_result",
                    "bf_result",
                    "bqc_result",
                    "rqspf_result",
                    "ou_result",
                    "draw_time",
                    "created_at",
                )
                if col in columns
            ]
            cursor.execute(
                f"INSERT INTO lottery_results ({', '.join(insert_cols)}) VALUES ({', '.join('?' for _ in insert_cols)})",
                tuple(after.get(col) for col in insert_cols),
            )
            result_id = next_id

        correction_id = "result_correction:" + uuid.uuid4().hex
        cursor.execute(
            """
            INSERT INTO lottery_result_corrections (
                correction_id, lottery_match_id, result_id, source,
                corrected_by, reason, before_json, after_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                correction_id,
                lottery_match_id,
                str(result_id) if result_id is not None else None,
                str(data.get("source") or "manual"),
                str(data.get("corrected_by") or "operator"),
                str(data.get("reason") or ""),
                json.dumps(before, ensure_ascii=False, default=str),
                json.dumps(after, ensure_ascii=False, default=str),
            ),
        )

        match_cols = get_table_columns(cursor, "lottery_matches")
        match_updates = []
        params: List[Any] = []
        if "sell_status" in match_cols:
            match_updates.append("sell_status = ?")
            params.append("finished")
        if "updated_at" in match_cols:
            match_updates.append("updated_at = CURRENT_TIMESTAMP")
        if match_updates:
            params.append(lottery_match_id)
            cursor.execute(
                f"UPDATE lottery_matches SET {', '.join(match_updates)} WHERE lottery_match_id = ?",
                tuple(params),
            )

        cursor.execute(
            """
            INSERT INTO lottery_revalidation_queue
            (queue_id, correction_id, lottery_match_id, reason)
            VALUES (?, ?, ?, ?)
            """,
            (
                "revalidate:" + uuid.uuid4().hex,
                correction_id,
                lottery_match_id,
                "result_corrected",
            ),
        )

        conn.commit()
        saved = cursor.execute(
            f"SELECT * FROM lottery_results WHERE lottery_match_id = ? ORDER BY {order_clause} LIMIT 1",
            (lottery_match_id,),
        ).fetchone()
        return {
            "success": True,
            "correction_id": correction_id,
            "lottery_match_id": lottery_match_id,
            "before": before,
            "after": dict(saved) if saved else after,
        }
    finally:
        conn.close()


@router.get("/results/{lottery_match_id}/corrections")
async def list_lottery_result_corrections(lottery_match_id: str):
    """List manual result corrections for a match."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        if "lottery_result_corrections" not in {
            row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }:
            return {"success": True, "lottery_match_id": lottery_match_id, "corrections": []}
        rows = cursor.execute(
            """
            SELECT *
            FROM lottery_result_corrections
            WHERE lottery_match_id = ?
            ORDER BY created_at DESC
            """,
            (lottery_match_id,),
        ).fetchall()
        corrections = []
        for row in rows:
            item = dict(row)
            for key in ("before_json", "after_json"):
                try:
                    item[key.replace("_json", "")] = json.loads(item.get(key) or "null")
                except (TypeError, json.JSONDecodeError):
                    item[key.replace("_json", "")] = item.get(key)
                item.pop(key, None)
            corrections.append(item)
        return {"success": True, "lottery_match_id": lottery_match_id, "corrections": corrections}
    finally:
        conn.close()


@router.post("/results/{lottery_match_id}/refresh")
async def refresh_lottery_result_from_source(
    lottery_match_id: str,
    overwrite: bool = Query(True, description="Overwrite existing result fields with source evidence"),
):
    """Refresh one match result from oddsfe event detail before falling back to manual correction."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        match = cursor.execute(
            """
            SELECT lm.lottery_match_id, lm.match_id, lm.home_team_cn, lm.away_team_cn,
                   lm.match_date, lm.beijing_time, lm.oddsfe_event_id, lm.handicap_line,
                   lr.home_goals_ft, lr.away_goals_ft, lr.home_goals_ht, lr.away_goals_ht,
                   lr.spf_result, lr.bf_result, lr.bqc_result, lr.rqspf_result, lr.ou_result
            FROM lottery_matches lm
            LEFT JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
            WHERE lm.lottery_match_id = ?
            """,
            (lottery_match_id,),
        ).fetchone()
        if not match:
            raise HTTPException(status_code=404, detail="lottery match not found")
        event_id = str(match["oddsfe_event_id"] or "").strip()
        if not event_id:
            raise HTTPException(status_code=400, detail="missing oddsfe_event_id, cannot refresh from source")
        before = {key: match[key] for key in match.keys() if key not in {"home_team_cn", "away_team_cn", "match_date", "beijing_time", "oddsfe_event_id", "handicap_line"}}
    finally:
        conn.close()

    try:
        from backend.app.data_access.foundation_dao import FoundationDAO
        from backend.app.lottery.services.oddsfe_event_sync import OddsfeEventDetailSync
        from backend.app.lottery.services.sync_service import _oddsfe_fetch_score_details

        event_data = _oddsfe_fetch_score_details(event_id)
        if not event_data:
            raise HTTPException(status_code=502, detail="oddsfe event detail returned empty")
        event_data = dict(event_data)
        event_data.setdefault("event_id", event_id)
        FoundationDAO(DB_PATH).record_artifact(
            source_name="oddsfe",
            source_type="api",
            entity_type="event",
            entity_id=event_id,
            payload={key: value for key, value in event_data.items() if not str(key).startswith("_")},
            confidence=0.92,
        )

        sync = OddsfeEventDetailSync(DB_PATH)
        result = sync._result_from_event(dict(match), event_data)
        if not result:
            return {
                "success": False,
                "lottery_match_id": lottery_match_id,
                "event_id": event_id,
                "event_status": event_data.get("event_status"),
                "message": "source has no final score yet",
            }

        with sync._connect() as write_conn:
            action, changed_cols = sync._upsert_result(write_conn, result, overwrite=overwrite)
            if action in {"inserted", "updated"}:
                write_conn.execute(
                    """
                    UPDATE lottery_matches
                    SET sell_status = 'finished', updated_at = CURRENT_TIMESTAMP
                    WHERE lottery_match_id = ?
                    """,
                    (lottery_match_id,),
                )
            write_conn.commit()

        conn = get_db()
        cursor = conn.cursor()
        try:
            after_row = cursor.execute(
                "SELECT * FROM lottery_results WHERE lottery_match_id = ? ORDER BY rowid DESC LIMIT 1",
                (lottery_match_id,),
            ).fetchone()
            after = dict(after_row) if after_row else result
            if action in {"inserted", "updated"}:
                _ensure_result_correction_table(cursor)
                correction_id = "result_correction:" + uuid.uuid4().hex
                cursor.execute(
                    """
                    INSERT INTO lottery_result_corrections (
                        correction_id, lottery_match_id, result_id, source,
                        corrected_by, reason, before_json, after_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        correction_id,
                        lottery_match_id,
                        str(after.get("result_id")) if after.get("result_id") is not None else None,
                        "oddsfe_refresh",
                        "collector",
                        "automatic source refresh",
                        json.dumps(before, ensure_ascii=False, default=str),
                        json.dumps(after, ensure_ascii=False, default=str),
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO lottery_revalidation_queue
                    (queue_id, correction_id, lottery_match_id, reason)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("revalidate:" + uuid.uuid4().hex, correction_id, lottery_match_id, "source_result_refreshed"),
                )
                conn.commit()
        finally:
            conn.close()

        return {
            "success": True,
            "lottery_match_id": lottery_match_id,
            "event_id": event_id,
            "event_status": event_data.get("event_status"),
            "action": action,
            "changed_cols": changed_cols,
            "result": after,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("refresh lottery result failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sync-oddsfe-event-details")
async def sync_oddsfe_event_details(
    background_tasks: BackgroundTasks,
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    days: int = Query(3, ge=1, le=14, description="Default range ending today when dates are omitted"),
    background: bool = Query(True, description="Run in background"),
    dry_run: bool = Query(False, description="Plan only, do not write"),
    refresh: bool = Query(False, description="Refetch event details even when cached"),
    fetch_schedule: bool = Query(True, description="Fetch oddsfe schedule before event details"),
    include_schedule_only: bool = Query(True, description="Include schedule-only World Cup fallback events"),
    max_events: Optional[int] = Query(None, ge=1, le=50, description="Maximum event candidates in this batch"),
    batches: int = Query(1, ge=1, le=20, description="Number of batches to run"),
    batch_gap_seconds: float = Query(0, ge=0, le=300, description="Pause between batches"),
    schedule_padding_days: int = Query(1, ge=0, le=2, description="Extra schedule days for UTC/Beijing offset"),
    overwrite: bool = Query(False, description="Overwrite existing non-empty result fields"),
):
    """Sync oddsfe event details into local evidence cache and lottery_results."""
    from backend.app.lottery.services.oddsfe_event_sync import (
        OddsfeEventDetailSync,
        default_date_range,
    )

    if not date_from or not date_to:
        date_from, date_to = default_date_range(days)

    if background and not dry_run:
        conn = get_db()
        try:
            run_status = _collection_run_status(conn.cursor(), "oddsfe_event_details")
        finally:
            conn.close()
        if run_status.get("running", 0) > 0:
            return {
                "success": True,
                "skipped": True,
                "message": "oddsfe event detail sync is already running",
                "date_from": date_from,
                "date_to": date_to,
                "running": run_status.get("running", 0),
                "latest": run_status.get("latest", [])[:3],
            }
        background_tasks.add_task(
            run_oddsfe_event_detail_task,
            date_from,
            date_to,
            refresh,
            fetch_schedule,
            include_schedule_only,
            max_events,
            batches,
            batch_gap_seconds,
            schedule_padding_days,
            overwrite,
        )
        return {
            "success": True,
            "message": "oddsfe event detail sync started in background",
            "date_from": date_from,
            "date_to": date_to,
        }

    sync = OddsfeEventDetailSync(DB_PATH)
    summaries = []
    for batch_index in range(max(batches, 1)):
        result = sync.run(
            date_from,
            date_to,
            apply=not dry_run,
            refresh=refresh,
            fetch_schedule=fetch_schedule,
            include_schedule_only=include_schedule_only,
            max_events=max_events,
            schedule_padding_days=schedule_padding_days,
            overwrite=overwrite,
            trigger_source="manual_api",
        )
        result["batch_index"] = batch_index + 1
        summaries.append(result)
        if not result.get("candidates_deferred"):
            break
        if batch_index < batches - 1 and batch_gap_seconds > 0:
            time.sleep(batch_gap_seconds)
    return summaries[0] if len(summaries) == 1 else {"success": all(item.get("success") for item in summaries), "batches": summaries}


@router.post("/sync-oddsfe-ou-lines")
async def sync_oddsfe_ou_lines(
    background_tasks: BackgroundTasks,
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    days: int = Query(21, ge=1, le=45, description="Default range ending today when dates are omitted"),
    background: bool = Query(True, description="Run in background"),
    dry_run: bool = Query(False, description="Audit only, do not write"),
    fetch_live: bool = Query(False, description="Fetch oddsfe market pages when local oddsfe_merged lacks O/U"),
    max_events: Optional[int] = Query(None, ge=1, le=50, description="Maximum missing events in this batch"),
    reanalyze: bool = Query(False, description="Immediately re-run analysis for updated matches"),
):
    """Sync exact-event Pinnacle O/U lines into oddsfe_matches."""
    from backend.app.lottery.services.oddsfe_ou_line_sync import (
        OddsfeOuLineSync,
        default_date_range,
    )

    if not date_from or not date_to:
        date_from, date_to = default_date_range(days)

    if background and not dry_run:
        conn = get_db()
        try:
            run_status = _collection_run_status(conn.cursor(), "oddsfe_ou_lines")
        finally:
            conn.close()
        if run_status.get("running", 0) > 0:
            return {
                "success": True,
                "skipped": True,
                "message": "oddsfe O/U line sync is already running",
                "date_from": date_from,
                "date_to": date_to,
                "running": run_status.get("running", 0),
                "latest": run_status.get("latest", [])[:3],
            }
        background_tasks.add_task(
            run_oddsfe_ou_line_task,
            date_from,
            date_to,
            fetch_live,
            max_events,
            reanalyze,
        )
        return {
            "success": True,
            "message": "oddsfe O/U line sync started in background",
            "date_from": date_from,
            "date_to": date_to,
        }

    sync = OddsfeOuLineSync(DB_PATH, ODDSFE_DB_PATH)
    if dry_run:
        return sync.audit(date_from, date_to)
    return sync.run(
        date_from,
        date_to,
        apply=True,
        fetch_live=fetch_live,
        max_events=max_events,
        reanalyze=reanalyze,
        trigger_source="manual_api",
    )


@router.get("/team-mappings")
async def list_team_mappings():
    """
    获取球队名称映射列表
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT tm.*, t.name_en, t.name_cn
            FROM team_name_mapping tm
            LEFT JOIN teams t ON tm.team_id = t.team_id
            ORDER BY tm.lottery_name
        """)

        mappings = []
        for row in cursor.fetchall():
            mappings.append({
                'lottery_name': row['lottery_name'],
                'team_id': row['team_id'],
                'team_name_en': row['name_en'],
                'team_name_cn': row['name_cn'],
                'match_confidence': row['match_confidence'],
                'match_method': row['match_method']
            })

        return {
            "success": True,
            "total": len(mappings),
            "mappings": mappings
        }

    finally:
        conn.close()


@router.post("/team-mappings")
async def create_team_mapping(data: Dict):
    """
    创建球队名称映射
    """
    lottery_name = data.get('lottery_name')
    team_id = data.get('team_id')

    if not lottery_name or not team_id:
        raise HTTPException(status_code=400, detail="Missing lottery_name or team_id")

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR REPLACE INTO team_name_mapping
            (lottery_name, team_id, match_confidence, match_method, updated_at)
            VALUES (?, ?, 1.0, 'manual', CURRENT_TIMESTAMP)
        """, (lottery_name, team_id))

        conn.commit()

        return {
            "success": True,
            "lottery_name": lottery_name,
            "team_id": team_id
        }

    finally:
        conn.close()


# ==================== 调度状态 ====================

@router.get("/scheduler/status")
async def get_scheduler_status():
    """
    获取调度任务状态
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT source_name, status, last_success, last_failure, success_rate
            FROM data_source_health
            ORDER BY updated_at DESC
        """)

        health = [dict(row) for row in cursor.fetchall()]

        return {
            "success": True,
            "health": health
        }

    finally:
        conn.close()


# ==================== 后台任务 ====================

def run_oddsfe_event_detail_task(
    date_from: str,
    date_to: str,
    refresh: bool = False,
    fetch_schedule: bool = True,
    include_schedule_only: bool = True,
    max_events: Optional[int] = None,
    batches: int = 1,
    batch_gap_seconds: float = 0,
    schedule_padding_days: int = 1,
    overwrite: bool = False,
):
    """Background task for oddsfe event detail sync."""
    logger.info("Starting oddsfe event detail sync: %s -> %s", date_from, date_to)
    try:
        from backend.app.lottery.services.oddsfe_event_sync import OddsfeEventDetailSync

        sync = OddsfeEventDetailSync(DB_PATH)
        results = []
        for batch_index in range(max(batches, 1)):
            result = sync.run(
                date_from,
                date_to,
                apply=True,
                refresh=refresh,
                fetch_schedule=fetch_schedule,
                include_schedule_only=include_schedule_only,
                max_events=max_events,
                schedule_padding_days=schedule_padding_days,
                overwrite=overwrite,
                trigger_source="background_api",
            )
            result["batch_index"] = batch_index + 1
            results.append(result)
            if not result.get("candidates_deferred"):
                break
            if batch_index < batches - 1 and batch_gap_seconds > 0:
                time.sleep(batch_gap_seconds)
        logger.info("oddsfe event detail sync completed: %s", results)
    except Exception as exc:
        logger.error("oddsfe event detail sync failed: %s", exc, exc_info=True)


def run_oddsfe_ou_line_task(
    date_from: str,
    date_to: str,
    fetch_live: bool = False,
    max_events: Optional[int] = None,
    reanalyze: bool = False,
):
    """Background task for exact oddsfe Pinnacle O/U line sync."""
    logger.info("Starting oddsfe O/U line sync: %s -> %s", date_from, date_to)
    try:
        from backend.app.lottery.services.oddsfe_ou_line_sync import OddsfeOuLineSync

        sync = OddsfeOuLineSync(DB_PATH, ODDSFE_DB_PATH)
        result = sync.run(
            date_from,
            date_to,
            apply=True,
            fetch_live=fetch_live,
            max_events=max_events,
            reanalyze=reanalyze,
            trigger_source="background_api",
        )
        logger.info("oddsfe O/U line sync completed: %s", result)
    except Exception as exc:
        logger.error("oddsfe O/U line sync failed: %s", exc, exc_info=True)


def run_auto_gap_fill_task(
    date_from: str,
    date_to: str,
    action_counts: Dict[str, int],
    max_events: int = 8,
    max_analysis: int = 12,
    max_intelligence: int = 8,
    max_validation_dates: int = 4,
    fetch_live_ou: bool = True,
    network_intelligence: bool = True,
    league: Optional[str] = None,
):
    """Background task for bounded automatic gap filling."""
    logger.info("Starting auto gap fill: %s -> %s actions=%s", date_from, date_to, action_counts)
    try:
        from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner

        result = LotteryAutoGapRunner(DB_PATH, ODDSFE_DB_PATH).run(
            date_from=date_from,
            date_to=date_to,
            action_counts=action_counts,
            max_events=max_events,
            max_analysis=max_analysis,
            max_intelligence=max_intelligence,
            max_validation_dates=max_validation_dates,
            fetch_live_ou=fetch_live_ou,
            network_intelligence=network_intelligence,
            league=league,
            trigger_source="background_auto_gap_fill_api",
        )
        logger.info("auto gap fill completed: %s", result)
    except Exception as exc:
        logger.error("auto gap fill failed: %s", exc, exc_info=True)


def run_automation_center_task(**kwargs):
    """Background task for the parallel automation center."""
    logger.info("Starting automation center: %s", kwargs)
    try:
        from backend.app.lottery.services.automation_center import AutomationCenter

        result = AutomationCenter(DB_PATH, ODDSFE_DB_PATH).run(**kwargs)
        logger.info("automation center completed: %s", result)
    except Exception as exc:
        logger.error("automation center failed: %s", exc, exc_info=True)


def run_automation_retry_task(
    run_id: str,
    workers: Optional[int] = None,
    task_key: Optional[str] = None,
    task_index: Optional[int] = None,
):
    """Background task for retrying failed automation-center tasks."""
    logger.info("Starting automation retry for run_id=%s task_key=%s task_index=%s", run_id, task_key, task_index)
    try:
        from backend.app.lottery.services.automation_center import AutomationCenter

        result = AutomationCenter(DB_PATH, ODDSFE_DB_PATH).retry_failed_tasks(
            run_id,
            trigger_source="manual_automation_retry_api",
            workers=workers,
            task_key=task_key,
            task_index=task_index,
        )
        logger.info("automation retry completed: %s", result)
    except Exception as exc:
        logger.error("automation retry failed: %s", exc, exc_info=True)


def run_analysis_task(lottery_match_id: str, play_types: Optional[str]):
    """后台分析任务 — 委托给统一管道"""
    logger.info(f"Starting analysis for {lottery_match_id}")

    try:
        from ...core.analyze import analyze_single

        report = analyze_single(DB_PATH, lottery_match_id)
        if report:
            logger.info(f"Analysis completed for {lottery_match_id}")
        else:
            logger.warning(f"Analysis returned None for {lottery_match_id}")
    except Exception as e:
        logger.error(f"Analysis failed for {lottery_match_id}: {e}")


def run_sync_task():
    """后台同步任务 - 真正调用 SyncService"""
    logger.info("Starting lottery data sync")

    try:
        from ..services.sync_service import LotterySyncService

        sync_service = LotterySyncService(DB_PATH)
        result = sync_service.sync_daily_matches(
            bridge_oddsfe=False,
            trigger_source='lottery_background_fast_sporttery',
        )
        sync_service.close()

        logger.info(f"Sync completed: {result}")

    except Exception as e:
        logger.error(f"Sync failed: {e}")


def _process_pending_revalidations(limit: int = 100) -> Dict[str, Any]:
    """Rebuild validation for result-refresh queue entries, then mark them processed."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        has_queue = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lottery_revalidation_queue'"
        ).fetchone()
        if not has_queue:
            return {"skipped": True, "reason": "queue_missing"}
        rows = conn.execute(
            """
            SELECT q.queue_id, q.lottery_match_id,
                   substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) AS match_date
            FROM lottery_revalidation_queue q
            JOIN lottery_matches lm ON lm.lottery_match_id = q.lottery_match_id
            WHERE q.status = 'pending'
            ORDER BY q.created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"pending": 0, "processed": 0}

    from backend.app.core.validate import _validate_predictions
    from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner

    dates = sorted({row["match_date"] for row in rows if row["match_date"]})
    results = []
    for date_value in dates:
        results.append({"date": date_value, **(_validate_predictions(DB_PATH, [date_value]) or {})})
    settlement = LotteryAutoGapRunner(DB_PATH, ODDSFE_DB_PATH).settle_reanalysis_changes(
        min(dates) if dates else None,
        max(dates) if dates else None,
        league=None,
    )

    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.executemany(
            """
            UPDATE lottery_revalidation_queue
            SET status = 'processed', processed_at = CURRENT_TIMESTAMP
            WHERE queue_id = ?
            """,
            [(row["queue_id"],) for row in rows],
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "pending": len(rows),
        "processed": len(rows),
        "dates": dates,
        "results": results,
        "reanalysis_change_settlement": settlement,
    }


def run_validation_task():
    """后台验证任务 - 真正调用 validate.py"""
    logger.info("Starting prediction validation")

    try:
        import sys
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from backend.app.core.validate import validate
        result = validate(state=None, db_path=DB_PATH)
        logger.info(f"Validation completed: {result}")
        queued = _process_pending_revalidations()
        logger.info("Pending revalidation completed: %s", queued)
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)


def run_backfill_task(days: int = 7):
    """后台补齐结果任务 — 调oddsfe API精准按日期采集，不加载全量DB

    流程: schedule API按日期拿赛果 → event API拿score_details(半全场)
    → 推导SPF/BF/BQC/RQSPF → INSERT OR REPLACE写入lottery_results
    """
    logger.info(f"Starting result backfill for past {days} days")

    try:
        import sys
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from backend.app.core.validate import _sync_results_oddsfe, _backfill_results_from_oddsfe
        from datetime import date, timedelta

        total_saved = 0
        today = date.today()

        # 1. 逐日从oddsfe API同步完整赛果(含半全场)
        for i in range(days):
            d = (today - timedelta(days=i)).isoformat()
            try:
                r = _sync_results_oddsfe(DB_PATH, d)
                saved = r.get('saved', 0)
                total_saved += saved
                logger.info(f"oddsfe sync {d}: saved={saved}")
            except Exception as e:
                logger.warning(f"oddsfe sync failed for {d}: {e}")

        # 2. 回填仍缺失的结果(按日期分组调API)
        try:
            r2 = _backfill_results_from_oddsfe(DB_PATH)
            saved2 = r2.get('saved', 0)
            total_saved += saved2
            logger.info(f"oddsfe backfill: saved={saved2}")
        except Exception as e:
            logger.warning(f"oddsfe backfill failed: {e}")

        # 3. 更新closed比赛的sell_status
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            UPDATE lottery_matches SET sell_status = 'finished'
            WHERE sell_status = 'closed'
            AND lottery_match_id IN (
                SELECT lottery_match_id FROM lottery_results
            )
        """)
        conn.commit()
        conn.close()

        logger.info(f"Backfill completed: {total_saved} results saved")
        return {'saved': total_saved}

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        return {'saved': 0, 'error': str(e)}


@router.get("/review")
async def get_review(
    days: int = Query(30, ge=1, le=365),
    play_type: Optional[str] = Query(None),
    correct: Optional[bool] = Query(None),
):
    """复盘视图：返回验证记录，含队伍名、预测、结果、归因

    用于前端复盘页面，展示历史预测的准确性。
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        has_post_reviews = _table_exists(cursor, "post_match_reviews")
        review_select = """
                , pr.review_json as review_json,
                pr.attribution as review_attribution,
                pr.created_at as review_created_at
        """ if has_post_reviews else """
                , NULL as review_json,
                NULL as review_attribution,
                NULL as review_created_at
        """
        review_join = (
            "LEFT JOIN post_match_reviews pr ON pr.match_key = v.lottery_match_id AND pr.play_type = v.play_type"
            if has_post_reviews else ""
        )

        query = f"""
            SELECT
                v.validation_id as id,
                v.lottery_match_id,
                v.play_type,
                v.is_correct,
                v.predicted_result,
                v.actual_result,
                v.scenario_type,
                v.attribution,
                v.validated_at,
                v.predicted_prob as pred_confidence,
                m.home_team_cn as home_team,
                m.away_team_cn as away_team,
                m.match_date,
                m.league_name_cn as league
                {review_select}
            FROM lottery_validation v
            LEFT JOIN lottery_matches m ON v.lottery_match_id = m.lottery_match_id
            {review_join}
            WHERE v.validated_at >= date('now', ?)
              AND v.predicted_result IS NOT NULL
              AND v.actual_result IS NOT NULL
              AND TRIM(v.predicted_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
              AND TRIM(v.actual_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', ':', '::')
        """
        params = [f'-{days} days']

        if play_type:
            query += " AND v.play_type = ?"
            params.append(play_type)
        if correct is not None:
            query += " AND v.is_correct = ?"
            params.append(1 if correct else 0)

        query += " ORDER BY v.validated_at DESC LIMIT 200"

        cursor.execute(query, params)
        records = []
        for row in cursor.fetchall():
            review_json = _loads_json(row['review_json'], {})
            if not isinstance(review_json, dict):
                review_json = {}
            structured_review = review_json.get('structured_review') or {}
            if not isinstance(structured_review, dict):
                structured_review = {}
            validation_json = review_json.get('validation') or {}
            if not isinstance(validation_json, dict):
                validation_json = {}
            records.append({
                'id': row['id'],
                'lottery_match_id': row['lottery_match_id'],
                'play_type': row['play_type'],
                'is_correct': bool(row['is_correct']),
                'predicted': row['predicted_result'] or '',
                'actual': row['actual_result'] or '',
                'scenario': row['scenario_type'] or '',
                'attribution': row['review_attribution'] or row['attribution'] or '',
                'validated_at': row['validated_at'] or '',
                'review_created_at': row['review_created_at'] or '',
                'home_team': row['home_team'] or '',
                'away_team': row['away_team'] or '',
                'match_date': row['match_date'] or '',
                'league': row['league'] or '',
                'confidence': round((row['pred_confidence'] or 0) * 100, 1),
                'reason_text': (
                    structured_review.get('reason_text')
                    or review_json.get('reason_text')
                    or validation_json.get('reason_text')
                    or ''
                ),
                'learning_tags': (
                    structured_review.get('learning_tags')
                    or review_json.get('learning_tags')
                    or []
                )[:8],
                'action_items': (
                    structured_review.get('action_items')
                    or review_json.get('action_items')
                    or []
                )[:8],
            })

        # Summary stats
        total = len(records)
        correct_count = sum(1 for r in records if r['is_correct'])
        by_play_type = {}
        for r in records:
            pt = r['play_type']
            if pt not in by_play_type:
                by_play_type[pt] = {'total': 0, 'correct': 0}
            by_play_type[pt]['total'] += 1
            if r['is_correct']:
                by_play_type[pt]['correct'] += 1

        return {
            "success": True,
            "records": records,
            "summary": {
                "total": total,
                "correct": correct_count,
                "accuracy": round(correct_count / total * 100, 1) if total > 0 else 0,
                "by_play_type": by_play_type,
            }
        }

    finally:
        conn.close()


@router.get("/review/insights")
async def get_review_insights(
    days: int = Query(30, ge=1, le=365),
    play_type: Optional[str] = Query(None),
):
    """Aggregate structured post-match reviews into model-learning diagnostics."""
    conn = get_db()
    cursor = conn.cursor()

    try:
        if not _table_exists(cursor, "post_match_reviews"):
            return {"success": True, "summary": {}, "by_play_type": [], "top_tags": [], "action_items": [], "high_confidence_errors": []}

        query = """
            SELECT pr.review_id, pr.match_key, pr.play_type, pr.predicted_result,
                   pr.actual_result, pr.is_correct, pr.attribution,
                   pr.review_json, pr.created_at,
                   lm.home_team_cn AS home_team, lm.away_team_cn AS away_team,
                   lm.match_date, lm.league_name_cn AS league
            FROM post_match_reviews pr
            LEFT JOIN lottery_matches lm ON lm.lottery_match_id = pr.match_key
            WHERE pr.created_at >= datetime('now', ?)
        """
        params: List[Any] = [f"-{days} days"]
        if play_type:
            query += " AND pr.play_type = ?"
            params.append(play_type)
        query += " ORDER BY pr.created_at DESC LIMIT 1000"

        rows = cursor.execute(query, params).fetchall()
        total = 0
        correct = 0
        wrong = 0
        reasoned = 0
        tag_counter: Counter = Counter()
        wrong_tag_counter: Counter = Counter()
        action_counter: Counter = Counter()
        attribution_counter: Counter = Counter()
        confidence_counter: Counter = Counter()
        play_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"total": 0, "correct": 0, "wrong": 0})
        high_confidence_errors: List[Dict[str, Any]] = []
        recent_errors: List[Dict[str, Any]] = []

        for row in rows:
            total += 1
            is_correct = bool(row["is_correct"])
            if is_correct:
                correct += 1
            else:
                wrong += 1

            play = row["play_type"] or "unknown"
            play_stats[play]["total"] += 1
            play_stats[play]["correct" if is_correct else "wrong"] += 1

            review_json = _loads_json(row["review_json"], {})
            if not isinstance(review_json, dict):
                review_json = {}
            structured = review_json.get("structured_review") or {}
            if not isinstance(structured, dict):
                structured = {}
            reason_text = structured.get("reason_text") or review_json.get("reason_text") or ""
            if reason_text:
                reasoned += 1
            tags = [str(tag) for tag in _ensure_list(structured.get("learning_tags") or review_json.get("learning_tags")) if tag]
            actions = [str(item) for item in _ensure_list(structured.get("action_items") or review_json.get("action_items")) if item]
            attribution = row["attribution"] or (structured.get("attribution") or {}).get("level")
            if attribution:
                attribution_counter[str(attribution)] += 1
            for tag in tags:
                tag_counter[tag] += 1
                if not is_correct:
                    wrong_tag_counter[tag] += 1
                if tag.startswith("confidence:"):
                    confidence_counter[tag.split(":", 1)[1]] += 1
            for item in actions:
                action_counter[item] += 1

            sample = {
                "review_id": row["review_id"],
                "match_key": row["match_key"],
                "play_type": play,
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "match_date": row["match_date"],
                "league": row["league"],
                "predicted_result": row["predicted_result"],
                "actual_result": row["actual_result"],
                "reason_text": reason_text,
                "learning_tags": tags[:8],
                "created_at": row["created_at"],
            }
            if not is_correct and len(recent_errors) < 8:
                recent_errors.append(sample)
            if not is_correct and "confidence:high" in tags and len(high_confidence_errors) < 8:
                high_confidence_errors.append(sample)

        by_play_type = []
        for play, stats in sorted(play_stats.items(), key=lambda item: item[1]["total"], reverse=True):
            play_total = int(stats["total"])
            play_correct = int(stats["correct"])
            play_wrong = int(stats["wrong"])
            by_play_type.append({
                "play_type": play,
                "total": play_total,
                "correct": play_correct,
                "wrong": play_wrong,
                "accuracy": round(play_correct * 100 / play_total, 1) if play_total else 0,
            })

        return {
            "success": True,
            "summary": {
                "days": days,
                "total": total,
                "correct": correct,
                "wrong": wrong,
                "accuracy": round(correct * 100 / total, 1) if total else 0,
                "reasoned": reasoned,
                "reasoned_rate": round(reasoned * 100 / total, 1) if total else 0,
                "high_confidence_errors": wrong_tag_counter.get("confidence:high", 0),
                "market_divergence_errors": wrong_tag_counter.get("market:diverged", 0),
                "low_intelligence_errors": wrong_tag_counter.get("intel:low_confidence", 0),
                "world_cup_context_errors": wrong_tag_counter.get("context:world_cup", 0),
            },
            "by_play_type": by_play_type,
            "top_tags": _compact_counter(tag_counter, total, 14),
            "wrong_tags": _compact_counter(wrong_tag_counter, wrong, 14),
            "action_items": _compact_counter(action_counter, total, 10),
            "attributions": _compact_counter(attribution_counter, total, 10),
            "confidence_buckets": _compact_counter(confidence_counter, total, 6),
            "high_confidence_errors": high_confidence_errors,
            "recent_errors": recent_errors,
        }

    finally:
        conn.close()


@router.get("/health")
async def get_health():
    """数据源健康检查：最后采集时间、覆盖率、O/U数据新鲜度"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        health = {}

        # 1. 今天的比赛数据
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) FROM lottery_matches WHERE match_date = ?", (today,))
        health['today_matches'] = cursor.fetchone()[0]

        # 2. 有赔率的比赛数
        cursor.execute("""
            SELECT COUNT(DISTINCT lottery_match_id) FROM lottery_odds
            WHERE lottery_match_id IN (
                SELECT lottery_match_id FROM lottery_matches WHERE match_date = ?
            )
        """, (today,))
        health['today_with_odds'] = cursor.fetchone()[0]

        # 3. 已分析的比赛数
        cursor.execute("""
            SELECT COUNT(DISTINCT lottery_match_id) FROM lottery_analysis_reports
            WHERE report_type = 'prediction'
            AND lottery_match_id IN (
                SELECT lottery_match_id FROM lottery_matches WHERE match_date = ?
            )
        """, (today,))
        health['today_analyzed'] = cursor.fetchone()[0]

        # 4. 最后采集时间
        cursor.execute("SELECT MAX(updated_at) FROM lottery_matches")
        row = cursor.fetchone()
        health['last_collection'] = row[0] if row else None

        # 5. 最后分析时间
        cursor.execute("SELECT MAX(created_at) FROM lottery_analysis_reports")
        row = cursor.fetchone()
        health['last_analysis'] = row[0] if row else None

        # 6. O/U数据新鲜度
        oddsfe_columns = get_table_columns(cursor, 'oddsfe_matches')
        if 'updated_at' in oddsfe_columns:
            ou_fresh_sql = """
                SELECT COUNT(*) FROM oddsfe_matches
                WHERE ou_pinnacle_line IS NOT NULL
                AND updated_at >= date('now', '-1 day')
            """
        elif 'ou_pinnacle_updated_at' in oddsfe_columns:
            ou_fresh_sql = """
                SELECT COUNT(*) FROM oddsfe_matches
                WHERE ou_pinnacle_line IS NOT NULL
                AND ou_pinnacle_updated_at >= date('now', '-1 day')
            """
        else:
            ou_fresh_sql = """
                SELECT COUNT(*) FROM oddsfe_matches
                WHERE ou_pinnacle_line IS NOT NULL
            """
        cursor.execute(ou_fresh_sql)
        health['ou_fresh_count'] = cursor.fetchone()[0]

        # 7. 验证记录数
        cursor.execute("SELECT COUNT(*) FROM lottery_validation")
        health['total_validations'] = cursor.fetchone()[0]

        # 8. 各play_type验证数
        cursor.execute("SELECT play_type, COUNT(*) FROM lottery_validation GROUP BY play_type")
        health['validation_by_type'] = {row[0]: row[1] for row in cursor.fetchall()}

        return {"success": True, "health": health}

    finally:
        conn.close()


@router.post("/pipeline")
async def run_full_pipeline(
    date: Optional[str] = Query(None, description="目标日期 YYYY-MM-DD, 默认今天"),
    backfill_days: int = Query(0, description="回填分析天数(0=只处理今天)"),
    skip_collect: bool = Query(False, description="跳过采集步骤"),
    skip_validate: bool = Query(False, description="跳过验证步骤"),
):
    """一键全流程: 采集→分析→验证

    自动化流程，防止手动处理导致的遗漏:
    1. 采集赛程+赔率 (sporttery + oddsfe)
    2. 同步赛果 (oddsfe优先, sporttery备选)
    3. 批量分析所有未分析比赛（跳过无team_id的）
    4. 验证预测+归因
    """
    import asyncio
    import subprocess
    import sys
    import time as time_mod
    results = {}

    target_date = date or datetime.now().strftime('%Y-%m-%d')

    # Step 1: 采集
    if not skip_collect:
        try:
            # 日循环采集
            p1 = subprocess.run(
                [sys.executable, '-m', 'backend.app.core.daily_runner', '--mode', 'collect'],
                cwd=os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'),
                capture_output=True, text=True, timeout=300
            )
            results['collect'] = {'success': p1.returncode == 0, 'output': (p1.stdout or '')[-200:]}

            # 体彩同步
            try:
                sync_res = http_requests.post('http://localhost:8000/api/v1/lottery/sync', timeout=60).json()
                results['sync'] = sync_res
            except Exception as e:
                results['sync'] = {'success': False, 'error': str(e)}
        except subprocess.TimeoutExpired:
            results['collect'] = {'success': False, 'error': '采集超时(300s)'}
        except Exception as e:
            results['collect'] = {'success': False, 'error': str(e)}

    # Step 2: 批量分析 (今天 + 回填天数) — 跳过无team_id的比赛
    from ...core.analyze import analyze_single
    conn = get_db()
    cursor = conn.cursor()

    # Find all unanalyzed matches in the date range (有team_id的)
    dates_to_analyze = [target_date]
    if backfill_days > 0:
        from datetime import timedelta
        for i in range(1, backfill_days + 1):
            d = str(datetime.now().date() - timedelta(days=i))
            dates_to_analyze.append(d)

    placeholders = ','.join(['?'] * len(dates_to_analyze))
    report_cols = get_table_columns(cursor, "lottery_analysis_reports")
    stale_condition = "OR COALESCE(r.is_stale, 0) = 1" if "is_stale" in report_cols else ""
    analysis_condition = f"(r.lottery_match_id IS NULL {stale_condition})"
    cursor.execute(f"""
        SELECT m.lottery_match_id
        FROM lottery_matches m
        LEFT JOIN lottery_analysis_reports r
            ON m.lottery_match_id = r.lottery_match_id AND r.report_type = 'prediction'
        WHERE m.match_date IN ({placeholders})
        AND {analysis_condition}
        AND m.home_team_id IS NOT NULL
        AND m.away_team_id IS NOT NULL
        ORDER BY m.match_date, m.match_time
    """, dates_to_analyze)

    unanalyzed = [row['lottery_match_id'] for row in cursor.fetchall()]

    # 统计被跳过的
    cursor.execute(f"""
        SELECT COUNT(*) as cnt
        FROM lottery_matches m
        LEFT JOIN lottery_analysis_reports r
            ON m.lottery_match_id = r.lottery_match_id AND r.report_type = 'prediction'
        WHERE m.match_date IN ({placeholders})
        AND r.lottery_match_id IS NULL
        AND (m.home_team_id IS NULL OR m.away_team_id IS NULL)
    """, dates_to_analyze)
    skip_row = cursor.fetchone()
    skipped = skip_row['cnt'] if skip_row else 0

    analyzed_count = 0
    analysis_errors = []
    analysis_start = time_mod.time()
    ANALYSIS_TIMEOUT = 300  # 5分钟分析超时

    for mid in unanalyzed[:50]:
        # 超时检查
        if time_mod.time() - analysis_start > ANALYSIS_TIMEOUT:
            analysis_errors.append(f"超时: 剩余{len(unanalyzed) - analyzed_count - len(analysis_errors)}场未分析")
            break
        try:
            report = analyze_single(DB_PATH, mid)
            if report:
                analyzed_count += 1
            else:
                analysis_errors.append(mid)
        except Exception as e:
            analysis_errors.append(f"{mid}: {str(e)[:50]}")
        # 让出事件循环
        await asyncio.sleep(0)

    results['analyze'] = {
        'total': len(unanalyzed),
        'succeeded': analyzed_count,
        'failed': len(analysis_errors),
        'skipped': skipped,
        'errors': analysis_errors[:5],
    }
    conn.close()

    # Step 3: 验证
    if not skip_validate:
        try:
            p3 = subprocess.run(
                [sys.executable, '-m', 'backend.app.core.daily_runner', '--mode', 'validate'],
                cwd=os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'),
                capture_output=True, text=True, timeout=300
            )
            results['validate'] = {'success': p3.returncode == 0, 'output': (p3.stdout or '')[-200:]}
        except subprocess.TimeoutExpired:
            results['validate'] = {'success': False, 'error': '验证超时(300s)'}
        except Exception as e:
            results['validate'] = {'success': False, 'error': str(e)}

    return {"success": True, "pipeline": results}
