"""Audit whether national-team historical facts help World Cup predictions.

This is an offline calibration script. It does not rewrite predictions or
facts. It compares a candidate fact table against settled lottery matches and
answers whether national-team/friendly history would have helped or hurt the
current model axes.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"


NATIONAL_KEYWORDS = (
    "世界杯", "国际友谊", "国际赛", "友谊赛",
    "欧洲杯", "欧国联", "美洲杯", "亚洲杯", "非洲杯",
    "中北美国家联赛", "中北美金杯", "金杯",
    "预选赛", "世预赛", "世界杯预选",
    "FIFA World Cup", "World Cup", "World Cup Qualification",
    "World Cup Qualifying", "International Friendly", "Friendly",
    "Friendlies", "UEFA Nations League", "Nations League",
    "UEFA Euro", "European Championship", "Copa America",
    "Copa América", "AFC Asian Cup", "Asian Cup",
    "Africa Cup of Nations", "Africa Cup", "CAF Africa Cup",
    "CONCACAF Gold Cup", "Gold Cup", "CONCACAF Nations League",
    "International",
)

EXCLUDED_KEYWORDS = (
    "女", "U16", "U17", "U18", "U19", "U20", "U21", "U23",
    "Youth", "Women", "Libertadores", "Sudamericana",
    "Champions League", "Europa League", "Conference League",
    "俱乐部", "解放者杯", "南球杯", "欧冠", "欧联", "欧协联",
)


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


def quote_ident(name: str) -> str:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name or ""):
        raise ValueError(f"invalid table name: {name!r}")
    return '"' + name.replace('"', '""') + '"'


def placeholders(values: Sequence[Any]) -> str:
    return ",".join(["?"] * len(values))


def loads_json(value: Any, default: Any = None) -> Any:
    if default is None:
        default = {}
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        return json.loads(str(value))
    except Exception:
        return default


def to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def is_national_label(label: Any) -> bool:
    text = str(label or "").strip()
    if not text:
        return False
    lower = text.lower()
    if any(item.lower() in lower for item in EXCLUDED_KEYWORDS):
        return False
    return any(item.lower() in lower for item in NATIONAL_KEYWORDS)


def comp_kind(label: Any) -> str:
    text = str(label or "")
    lower = text.lower()
    if "友谊" in text or "friendly" in lower or text in {"国际赛", "International"}:
        return "friendly"
    if "世界杯" in text or "world cup" in lower:
        return "world_cup"
    if "预选" in text or "qualif" in lower or "世预" in text:
        return "qualifier"
    if any(x in text for x in ("欧洲杯", "欧国联", "美洲杯", "亚洲杯", "非洲杯", "金杯")):
        return "continental"
    if any(x in lower for x in ("nations league", "euro", "copa america", "asian cup", "africa cup", "gold cup")):
        return "continental"
    return "other"


def active_report(conn: sqlite3.Connection, match_id: str) -> Dict[str, Any]:
    row = conn.execute(
        """
        SELECT report_data
        FROM lottery_analysis_reports
        WHERE lottery_match_id = ?
          AND report_type = 'prediction'
          AND COALESCE(is_stale, 0) = 0
        ORDER BY datetime(created_at) DESC, report_id DESC
        LIMIT 1
        """,
        (match_id,),
    ).fetchone()
    return loads_json(row["report_data"], {}) if row else {}


def parse_ou_side(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("大"):
        return "over"
    if text.startswith("小"):
        return "under"
    return ""


def parse_ou_line(value: Any) -> Optional[float]:
    if value is None:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(value))
    if not match:
        return None
    return to_float(match.group(1))


def parse_signed_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    match = re.search(r"([+-]?\d+(?:\.\d+)?)", str(value))
    if not match:
        return None
    return to_float(match.group(1))


def actual_ou_side(total_goals: int, line: Optional[float]) -> str:
    if line is None:
        return ""
    if total_goals > line:
        return "over"
    if total_goals < line:
        return "under"
    return "push"


def actual_spf(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "3"
    if home_goals < away_goals:
        return "0"
    return "1"


def actual_rqspf(home_goals: int, away_goals: int, handicap: Optional[float]) -> str:
    adjusted = home_goals + float(handicap or 0)
    if adjusted > away_goals:
        return "3"
    if adjusted < away_goals:
        return "0"
    return "1"


def actual_bqc(home_ht: Optional[int], away_ht: Optional[int], home_ft: int, away_ft: int) -> str:
    if home_ht is None or away_ht is None:
        return ""
    return actual_spf(home_ht, away_ht) + actual_spf(home_ft, away_ft)


def normalize_play_result(play_type: str, value: Any) -> str:
    text = str(value or "").strip()
    if play_type in {"spf", "rqspf"}:
        return {
            "主胜": "3", "胜": "3", "让胜": "3",
            "平局": "1", "平": "1", "让平": "1",
            "客胜": "0", "负": "0", "让负": "0",
        }.get(text, text)
    if play_type == "bqc":
        mapping = {
            "胜胜": "33", "胜平": "31", "胜负": "30",
            "平胜": "13", "平平": "11", "平负": "10",
            "负胜": "03", "负平": "01", "负负": "00",
            "hh": "33", "hd": "31", "ha": "30",
            "dh": "13", "dd": "11", "da": "10",
            "ah": "03", "ad": "01", "aa": "00",
        }
        return mapping.get(text, mapping.get(text.lower(), text))
    if play_type == "ou":
        return parse_ou_side(text)
    return text


def prediction_payload(report: Dict[str, Any]) -> Dict[str, Any]:
    plays = report.get("play_predictions") if isinstance(report.get("play_predictions"), dict) else {}
    final = report.get("final_prediction") if isinstance(report.get("final_prediction"), dict) else {}
    expected = final.get("expected_score") if isinstance(final.get("expected_score"), dict) else {}
    spf = plays.get("spf") if isinstance(plays.get("spf"), dict) else {}
    rqspf = plays.get("rqspf") if isinstance(plays.get("rqspf"), dict) else {}
    bqc = plays.get("bqc") if isinstance(plays.get("bqc"), dict) else {}
    ou = plays.get("ou") if isinstance(plays.get("ou"), dict) else {}
    return {
        "spf": normalize_play_result("spf", spf.get("direction_cn") or spf.get("recommendation_cn") or spf.get("recommendation")),
        "rqspf": normalize_play_result("rqspf", rqspf.get("recommendation_cn") or rqspf.get("direction_cn") or rqspf.get("recommendation")),
        "rqspf_line": (
            parse_signed_number(rqspf.get("goal_line"))
            if parse_signed_number(rqspf.get("goal_line")) is not None
            else parse_signed_number(rqspf.get("goal_line_label") or rqspf.get("handicap"))
        ),
        "bqc": normalize_play_result("bqc", bqc.get("recommendation_cn") or bqc.get("recommendation")),
        "ou": normalize_play_result("ou", ou.get("recommendation")),
        "ou_line": parse_ou_line(ou.get("line") or ou.get("best_line") or ou.get("recommendation")),
        "expected_total": (
            to_float(expected.get("home"), 0.0) or 0.0
        ) + (
            to_float(expected.get("away"), 0.0) or 0.0
        ) if expected else None,
    }


def fetch_matches(conn: sqlite3.Connection, date_from: str, date_to: str, league: str) -> List[sqlite3.Row]:
    clauses = [
        "lr.home_goals_ft IS NOT NULL",
        "lr.away_goals_ft IS NOT NULL",
        "substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) >= ?",
        "substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) <= ?",
    ]
    params: List[Any] = [date_from, date_to]
    if league:
        clauses.append("lm.league_name_cn = ?")
        params.append(league)
    return conn.execute(
        f"""
        SELECT lm.lottery_match_id, lm.match_num, lm.league_name_cn,
               lm.home_team_id, lm.away_team_id, lm.home_team_cn, lm.away_team_cn,
               lm.handicap_line, COALESCE(lm.beijing_time, lm.match_date) AS kickoff,
               lr.home_goals_ft, lr.away_goals_ft, lr.home_goals_ht, lr.away_goals_ht,
               lr.spf_result, lr.rqspf_result, lr.bqc_result, lr.ou_result
        FROM lottery_matches lm
        JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
        WHERE {" AND ".join(clauses)}
        ORDER BY kickoff, lm.lottery_match_id
        """,
        params,
    ).fetchall()


def fetch_team_rows(
    conn: sqlite3.Connection,
    fact_table: str,
    team_id: Any,
    before_date: str,
    limit: int,
    national_only: bool,
) -> List[sqlite3.Row]:
    table = quote_ident(fact_table)
    clauses = [
        "team_id = ?",
        "date(match_date) < date(?)",
        "goals_for IS NOT NULL",
        "goals_against IS NOT NULL",
    ]
    params: List[Any] = [str(team_id), before_date[:10]]
    if national_only:
        include = " OR ".join(["COALESCE(league_name_cn, '') LIKE ?" for _ in NATIONAL_KEYWORDS])
        exclude = " OR ".join(["COALESCE(league_name_cn, '') LIKE ?" for _ in EXCLUDED_KEYWORDS])
        clauses.append(f"({include})")
        clauses.append(f"NOT ({exclude})")
        params.extend([f"%{item}%" for item in NATIONAL_KEYWORDS])
        params.extend([f"%{item}%" for item in EXCLUDED_KEYWORDS])
    params.append(limit)
    return conn.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE {" AND ".join(clauses)}
        ORDER BY date(match_date) DESC, source_match_id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()


def profile(rows: Iterable[sqlite3.Row]) -> Dict[str, Any]:
    items = [dict(row) for row in rows]
    n = len(items)
    if not n:
        return {"sample": 0}
    kinds: Dict[str, int] = defaultdict(int)
    for row in items:
        kinds[comp_kind(row.get("league_name_cn"))] += 1

    def avg(key: str) -> Optional[float]:
        vals = [to_float(row.get(key)) for row in items if to_float(row.get(key)) is not None]
        return round(mean(vals), 3) if vals else None

    def rate(fn) -> float:
        return round(sum(1 for row in items if fn(row)) / n, 4)

    return {
        "sample": n,
        "avg_for": avg("goals_for"),
        "avg_against": avg("goals_against"),
        "ht_avg_for": avg("goals_ht_for"),
        "ht_avg_against": avg("goals_ht_against"),
        "score_rate": rate(lambda r: to_int(r.get("goals_for"), 0) > 0),
        "concede_rate": rate(lambda r: to_int(r.get("goals_against"), 0) > 0),
        "clean_sheet_rate": rate(lambda r: to_int(r.get("goals_against"), 0) == 0),
        "blank_rate": rate(lambda r: to_int(r.get("goals_for"), 0) == 0),
        "big_score_rate": rate(lambda r: to_int(r.get("goals_for"), 0) >= 3),
        "big_concede_rate": rate(lambda r: to_int(r.get("goals_against"), 0) >= 3),
        "high_total_rate": rate(lambda r: (to_int(r.get("goals_for"), 0) + to_int(r.get("goals_against"), 0)) >= 4),
        "low_total_rate": rate(lambda r: (to_int(r.get("goals_for"), 0) + to_int(r.get("goals_against"), 0)) <= 2),
        "ht_score_rate": rate(lambda r: to_int(r.get("goals_ht_for"), 0) > 0),
        "ht_concede_rate": rate(lambda r: to_int(r.get("goals_ht_against"), 0) > 0),
        "kinds": dict(sorted(kinds.items())),
        "friendly_ratio": round(kinds.get("friendly", 0) / n, 4),
        "official_ratio": round((n - kinds.get("friendly", 0) - kinds.get("other", 0)) / n, 4),
        "other_ratio": round(kinds.get("other", 0) / n, 4),
    }


def goal_signal(attack: Dict[str, Any], defense: Dict[str, Any]) -> Optional[float]:
    af = to_float(attack.get("avg_for"))
    da = to_float(defense.get("avg_against"))
    if af is None or da is None:
        return None
    signal = af * 0.62 + da * 0.38
    signal += max(0.0, to_float(attack.get("big_score_rate"), 0.0) - 0.25) * 0.28
    signal += max(0.0, to_float(defense.get("big_concede_rate"), 0.0) - 0.15) * 0.24
    signal -= max(0.0, to_float(defense.get("clean_sheet_rate"), 0.0) - 0.34) * 0.22
    signal -= max(0.0, to_float(attack.get("blank_rate"), 0.0) - 0.28) * 0.18
    return round(max(0.12, min(4.8, signal)), 3)


def ht_signal(attack: Dict[str, Any], defense: Dict[str, Any]) -> Optional[float]:
    ar = to_float(attack.get("ht_score_rate"))
    dr = to_float(defense.get("ht_concede_rate"))
    if ar is None or dr is None:
        return None
    return round(ar * 0.58 + dr * 0.42, 4)


def side_from_margin(margin: Optional[float], neutral_band: float = 0.22) -> str:
    if margin is None:
        return ""
    if margin > neutral_band:
        return "3"
    if margin < -neutral_band:
        return "0"
    return "1"


def ou_from_total(total: Optional[float], line: Optional[float], neutral_band: float) -> str:
    if total is None or line is None:
        return ""
    if total > line + neutral_band:
        return "over"
    if total < line - neutral_band:
        return "under"
    return "neutral"


def line_bucket(line: Optional[float]) -> str:
    if line is None:
        return "unknown"
    return f"{line:g}"


def add_stat(bucket: Dict[str, Dict[str, int]], key: str, correct: bool) -> None:
    item = bucket.setdefault(key, {"total": 0, "correct": 0})
    item["total"] += 1
    item["correct"] += 1 if correct else 0


def add_overlay(
    bucket: Dict[str, Dict[str, int]],
    key: str,
    *,
    model_correct: bool,
    overlay_correct: bool,
    changed: bool,
) -> None:
    item = bucket.setdefault(
        key,
        {
            "total": 0,
            "model_correct": 0,
            "overlay_correct": 0,
            "changed": 0,
            "improved": 0,
            "regressed": 0,
        },
    )
    item["total"] += 1
    item["model_correct"] += 1 if model_correct else 0
    item["overlay_correct"] += 1 if overlay_correct else 0
    item["changed"] += 1 if changed else 0
    item["improved"] += 1 if overlay_correct and not model_correct else 0
    item["regressed"] += 1 if model_correct and not overlay_correct else 0


def finish_stats(bucket: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    result = {}
    for key, item in sorted(bucket.items()):
        total = item["total"]
        correct = item["correct"]
        result[key] = {
            "total": total,
            "correct": correct,
            "accuracy": round(correct * 100 / total, 1) if total else 0.0,
        }
    return result


def finish_overlay(bucket: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    result = {}
    for key, item in sorted(bucket.items()):
        total = item["total"]
        model_correct = item["model_correct"]
        overlay_correct = item["overlay_correct"]
        result[key] = {
            "total": total,
            "changed": item["changed"],
            "model_correct": model_correct,
            "overlay_correct": overlay_correct,
            "model_accuracy": round(model_correct * 100 / total, 1) if total else 0.0,
            "overlay_accuracy": round(overlay_correct * 100 / total, 1) if total else 0.0,
            "delta_correct": overlay_correct - model_correct,
            "improved": item["improved"],
            "regressed": item["regressed"],
        }
    return result


def build_audit(
    db_path: Path,
    fact_table: str,
    date_from: str,
    date_to: str,
    league: str,
    limit: int,
    neutral_band: float,
    examples_limit: int,
) -> Dict[str, Any]:
    with connect(db_path) as conn:
        if not table_exists(conn, fact_table):
            raise SystemExit(f"fact table not found: {fact_table}")
        matches = fetch_matches(conn, date_from, date_to, league)
        rows_out: List[Dict[str, Any]] = []
        stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0})
        by_line: Dict[str, Dict[str, int]] = {}
        by_relation: Dict[str, Dict[str, int]] = {}
        by_sample: Dict[str, Dict[str, int]] = {}
        bqc_ht_stats: Dict[str, Dict[str, int]] = {}
        spf_stats: Dict[str, Dict[str, int]] = {}
        rqspf_stats: Dict[str, Dict[str, int]] = {}
        model_stats: Dict[str, Dict[str, int]] = {}
        overlay_stats: Dict[str, Dict[str, int]] = {}
        helped: List[Dict[str, Any]] = []
        hurt: List[Dict[str, Any]] = []

        for match in matches:
            report = active_report(conn, str(match["lottery_match_id"]))
            pred = prediction_payload(report)
            home_goals = int(match["home_goals_ft"])
            away_goals = int(match["away_goals_ft"])
            total_goals = home_goals + away_goals
            line = pred.get("ou_line")
            actual_ou = actual_ou_side(total_goals, line)

            home_nat = profile(fetch_team_rows(conn, fact_table, match["home_team_id"], match["kickoff"], limit, True))
            away_nat = profile(fetch_team_rows(conn, fact_table, match["away_team_id"], match["kickoff"], limit, True))
            if not home_nat.get("sample") or not away_nat.get("sample"):
                continue

            home_goal = goal_signal(home_nat, away_nat)
            away_goal = goal_signal(away_nat, home_nat)
            total_signal = round((home_goal or 0.0) + (away_goal or 0.0), 3) if home_goal is not None and away_goal is not None else None
            margin_signal = round((home_goal or 0.0) - (away_goal or 0.0), 3) if home_goal is not None and away_goal is not None else None
            nat_ou = ou_from_total(total_signal, line, neutral_band)
            model_ou = pred.get("ou")

            min_sample = min(int(home_nat.get("sample") or 0), int(away_nat.get("sample") or 0))
            sample_bucket = "sample>=16" if min_sample >= 16 else "sample>=8" if min_sample >= 8 else "sample<8"

            if nat_ou in {"over", "under"} and actual_ou in {"over", "under"}:
                nat_correct = nat_ou == actual_ou
                add_stat(stats, "national_ou_decisive", nat_correct)
                add_stat(by_line, line_bucket(line), nat_correct)
                add_stat(by_sample, sample_bucket, nat_correct)
                if model_ou in {"over", "under"}:
                    model_correct = model_ou == actual_ou
                    add_stat(model_stats, "model_ou", model_correct)
                    add_overlay(
                        overlay_stats,
                        "ou_replace_when_national_decisive",
                        model_correct=model_correct,
                        overlay_correct=nat_correct,
                        changed=nat_ou != model_ou,
                    )
                    relation = "agree" if model_ou == nat_ou else "disagree"
                    add_stat(by_relation, relation, nat_correct)
                    if relation == "disagree":
                        add_overlay(
                            overlay_stats,
                            "ou_replace_only_on_conflict",
                            model_correct=model_correct,
                            overlay_correct=nat_correct,
                            changed=True,
                        )
                    if model_correct and not nat_correct:
                        hurt.append(match_example(match, pred, actual_ou, nat_ou, total_signal, margin_signal, home_nat, away_nat))
                    elif nat_correct and not model_correct:
                        helped.append(match_example(match, pred, actual_ou, nat_ou, total_signal, margin_signal, home_nat, away_nat))
            elif model_ou in {"over", "under"} and actual_ou in {"over", "under"}:
                add_stat(model_stats, "model_ou", model_ou == actual_ou)

            h_ht = ht_signal(home_nat, away_nat)
            a_ht = ht_signal(away_nat, home_nat)
            actual_ht = actual_bqc(
                to_int(match["home_goals_ht"]),
                to_int(match["away_goals_ht"]),
                home_goals,
                away_goals,
            )
            if h_ht is not None and a_ht is not None and actual_ht:
                ht_axis = side_from_margin(h_ht - a_ht, neutral_band=0.08)
                add_stat(bqc_ht_stats, "national_ht_axis", ht_axis == actual_ht[0])

            nat_spf = side_from_margin(margin_signal, neutral_band=0.22)
            act_spf = actual_spf(home_goals, away_goals)
            if nat_spf:
                add_stat(spf_stats, "national_spf_axis", nat_spf == act_spf)
            if pred.get("spf") in {"3", "1", "0"}:
                model_spf_correct = pred.get("spf") == act_spf
                add_stat(model_stats, "model_spf", model_spf_correct)
                if nat_spf in {"3", "1", "0"}:
                    add_overlay(
                        overlay_stats,
                        "spf_replace_when_national_decisive",
                        model_correct=model_spf_correct,
                        overlay_correct=nat_spf == act_spf,
                        changed=nat_spf != pred.get("spf"),
                    )

            handicap = pred.get("rqspf_line")
            if handicap is None:
                handicap = to_float(match["handicap_line"], 0.0) or 0.0
            nat_rq = side_from_margin((margin_signal or 0.0) + handicap, neutral_band=0.22)
            act_rq = normalize_play_result("rqspf", match["rqspf_result"]) or actual_rqspf(home_goals, away_goals, handicap)
            if nat_rq:
                add_stat(rqspf_stats, "national_rqspf_axis", nat_rq == act_rq)
            if pred.get("rqspf") in {"3", "1", "0"}:
                model_rq_correct = pred.get("rqspf") == act_rq
                add_stat(model_stats, "model_rqspf", model_rq_correct)
                if nat_rq in {"3", "1", "0"}:
                    add_overlay(
                        overlay_stats,
                        "rqspf_replace_when_national_decisive",
                        model_correct=model_rq_correct,
                        overlay_correct=nat_rq == act_rq,
                        changed=nat_rq != pred.get("rqspf"),
                    )
                    if nat_rq != pred.get("rqspf"):
                        add_overlay(
                            overlay_stats,
                            "rqspf_replace_only_on_conflict",
                            model_correct=model_rq_correct,
                            overlay_correct=nat_rq == act_rq,
                            changed=True,
                        )

            rows_out.append({
                "match_key": match["lottery_match_id"],
                "match_num": match["match_num"],
                "date": str(match["kickoff"])[:10],
                "teams": f"{match['home_team_cn']} vs {match['away_team_cn']}",
                "score": f"{home_goals}:{away_goals}",
                "line": line,
                "actual_ou": actual_ou,
                "model_ou": model_ou,
                "national_ou": nat_ou,
                "national_total_signal": total_signal,
                "national_margin_signal": margin_signal,
                "model_expected_total": pred.get("expected_total"),
                "home_sample": home_nat.get("sample"),
                "away_sample": away_nat.get("sample"),
                "home_friendly_ratio": home_nat.get("friendly_ratio"),
                "away_friendly_ratio": away_nat.get("friendly_ratio"),
                "home_official_ratio": home_nat.get("official_ratio"),
                "away_official_ratio": away_nat.get("official_ratio"),
            })

    return {
        "db": str(db_path),
        "fact_table": fact_table,
        "date_from": date_from,
        "date_to": date_to,
        "league": league,
        "matches_checked": len(matches),
        "matches_with_national_profile": len(rows_out),
        "settings": {
            "sample_limit": limit,
            "ou_neutral_band": neutral_band,
        },
        "national_ou": finish_stats(stats),
        "national_ou_by_line": finish_stats(by_line),
        "national_ou_by_model_relation": finish_stats(by_relation),
        "national_ou_by_sample": finish_stats(by_sample),
        "national_half_time": finish_stats(bqc_ht_stats),
        "national_spf": finish_stats(spf_stats),
        "national_rqspf": finish_stats(rqspf_stats),
        "current_model": finish_stats(model_stats),
        "what_if_overlays": finish_overlay(overlay_stats),
        "helped_examples": helped[:examples_limit],
        "hurt_examples": hurt[:examples_limit],
        "sample_rows": rows_out[:examples_limit],
        "decision": decision_summary(stats, by_relation, bqc_ht_stats, spf_stats, rqspf_stats),
    }


def match_example(
    match: sqlite3.Row,
    pred: Dict[str, Any],
    actual_ou: str,
    nat_ou: str,
    total_signal: Optional[float],
    margin_signal: Optional[float],
    home_profile: Dict[str, Any],
    away_profile: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "match_num": match["match_num"],
        "date": str(match["kickoff"])[:10],
        "teams": f"{match['home_team_cn']} vs {match['away_team_cn']}",
        "score": f"{match['home_goals_ft']}:{match['away_goals_ft']}",
        "model_ou": pred.get("ou"),
        "actual_ou": actual_ou,
        "national_ou": nat_ou,
        "line": pred.get("ou_line"),
        "national_total_signal": total_signal,
        "national_margin_signal": margin_signal,
        "home_profile": {
            "sample": home_profile.get("sample"),
            "avg_for": home_profile.get("avg_for"),
            "avg_against": home_profile.get("avg_against"),
            "friendly_ratio": home_profile.get("friendly_ratio"),
            "official_ratio": home_profile.get("official_ratio"),
            "kinds": home_profile.get("kinds"),
        },
        "away_profile": {
            "sample": away_profile.get("sample"),
            "avg_for": away_profile.get("avg_for"),
            "avg_against": away_profile.get("avg_against"),
            "friendly_ratio": away_profile.get("friendly_ratio"),
            "official_ratio": away_profile.get("official_ratio"),
            "kinds": away_profile.get("kinds"),
        },
    }


def accuracy(bucket: Dict[str, Dict[str, int]], key: str) -> Optional[float]:
    item = bucket.get(key)
    if not item or not item.get("total"):
        return None
    return item["correct"] / item["total"]


def decision_summary(
    ou_stats: Dict[str, Dict[str, int]],
    relation_stats: Dict[str, Dict[str, int]],
    ht_stats: Dict[str, Dict[str, int]],
    spf_stats: Dict[str, Dict[str, int]],
    rqspf_stats: Dict[str, Dict[str, int]],
) -> Dict[str, Any]:
    ou_acc = accuracy(ou_stats, "national_ou_decisive")
    disagree_acc = accuracy(relation_stats, "disagree")
    ht_acc = accuracy(ht_stats, "national_ht_axis")
    spf_acc = accuracy(spf_stats, "national_spf_axis")
    rq_acc = accuracy(rqspf_stats, "national_rqspf_axis")

    recommendations = []
    if ou_acc is not None:
        if ou_acc >= 0.58 and (disagree_acc is None or disagree_acc >= 0.55):
            recommendations.append("national_ou_can_enter_weight_gate")
        else:
            recommendations.append("national_ou_reference_only")
    if ht_acc is not None:
        recommendations.append("national_half_time_reference_only" if ht_acc < 0.55 else "national_half_time_can_test_weight")
    if spf_acc is not None:
        recommendations.append("national_spf_reference_only" if spf_acc < 0.55 else "national_spf_can_test_weight")
    if rq_acc is not None:
        recommendations.append("national_rqspf_reference_only" if rq_acc < 0.55 else "national_rqspf_can_test_weight")

    return {
        "ou_accuracy": round(ou_acc * 100, 1) if ou_acc is not None else None,
        "ou_disagree_accuracy": round(disagree_acc * 100, 1) if disagree_acc is not None else None,
        "half_time_accuracy": round(ht_acc * 100, 1) if ht_acc is not None else None,
        "spf_accuracy": round(spf_acc * 100, 1) if spf_acc is not None else None,
        "rqspf_accuracy": round(rq_acc * 100, 1) if rq_acc is not None else None,
        "recommendations": recommendations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit national reference calibration")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--fact-table", default="team_match_facts")
    parser.add_argument("--from", dest="date_from", default="2026-06-13")
    parser.add_argument("--to", dest="date_to", default="2026-06-23")
    parser.add_argument("--league", default="世界杯")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--ou-neutral-band", type=float, default=0.18)
    parser.add_argument("--examples-limit", type=int, default=12)
    args = parser.parse_args()

    summary = build_audit(
        db_path=args.db,
        fact_table=args.fact_table,
        date_from=args.date_from,
        date_to=args.date_to,
        league=args.league,
        limit=max(3, args.limit),
        neutral_band=max(0.0, args.ou_neutral_band),
        examples_limit=max(1, args.examples_limit),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
