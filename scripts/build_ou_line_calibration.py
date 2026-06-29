"""Build O/U line calibration from finished match reviews.

The table produced here is descriptive, not a betting rule engine. Analysis code
may read it to say "historically similar line groups behaved like this"; if no
sample exists, it should say nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "football_v2.db"


def _parse_line(value: Any) -> Optional[float]:
    if value is None:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(value))
    if not match:
        return None
    try:
        return round(float(match.group(1)), 2)
    except ValueError:
        return None


def _load_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def _is_edge_total(total_goals: int, line: float) -> bool:
    whole = int(line)
    frac = round(line - whole, 2)
    if abs(frac) < 0.01:
        return total_goals == whole
    if abs(frac - 0.25) < 0.01:
        return total_goals == whole
    if abs(frac - 0.5) < 0.01:
        return total_goals in {whole, whole + 1}
    if abs(frac - 0.75) < 0.01:
        return total_goals == whole + 1
    return abs(total_goals - line) <= 0.5


def _edge_definition(line: float) -> str:
    whole = int(line)
    frac = round(line - whole, 2)
    if abs(frac) < 0.01:
        return f"total_goals == {whole}"
    if abs(frac - 0.25) < 0.01:
        return f"quarter boundary: total_goals == {whole}"
    if abs(frac - 0.5) < 0.01:
        return f"half-goal boundary: total_goals in ({whole}, {whole + 1})"
    if abs(frac - 0.75) < 0.01:
        return f"quarter boundary: total_goals == {whole + 1}"
    return "abs(total_goals - line) <= 0.5"


def _iter_review_rows(conn: sqlite3.Connection) -> Iterable[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            pr.match_key,
            pr.predicted_result,
            pr.actual_result,
            pr.is_correct,
            pr.review_json,
            pr.created_at,
            lm.league_name_cn,
            lr.home_goals_ft,
            lr.away_goals_ft
        FROM post_match_reviews pr
        LEFT JOIN lottery_matches lm ON lm.lottery_match_id = pr.match_key
        LEFT JOIN lottery_results lr ON lr.lottery_match_id = pr.match_key
        WHERE pr.play_type = 'ou'
          AND pr.created_at = (
              SELECT MAX(pr2.created_at)
              FROM post_match_reviews pr2
              WHERE pr2.match_key = pr.match_key
                AND pr2.play_type = pr.play_type
          )
        """
    )
    yield from cursor.fetchall()


def _row_to_sample(row: sqlite3.Row) -> Optional[Dict[str, Any]]:
    payload = _load_json(row["review_json"])
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else payload

    line = (
        _parse_line(validation.get("predicted_result"))
        or _parse_line(row["predicted_result"])
        or _parse_line(validation.get("actual_result"))
        or _parse_line(row["actual_result"])
    )
    if line is None:
        return None

    home_goals = validation.get("home_goals")
    away_goals = validation.get("away_goals")
    if home_goals is None:
        home_goals = row["home_goals_ft"]
    if away_goals is None:
        away_goals = row["away_goals_ft"]

    try:
        total_goals = int(home_goals) + int(away_goals)
    except (TypeError, ValueError):
        return None

    return {
        "match_key": row["match_key"],
        "line": line,
        "total_goals": total_goals,
        "league_name_cn": row["league_name_cn"] or "_unknown",
        "scenario_type": validation.get("scenario_type") or "_unknown",
        "is_correct": 1 if row["is_correct"] else 0,
    }


def _profile_key(line: float, league_name_cn: str) -> str:
    return f"line:{line:g}|league:{league_name_cn or '_global'}"


def _build_profiles(samples: Iterable[Dict[str, Any]]) -> Dict[Tuple[float, str], Dict[str, Any]]:
    groups: Dict[Tuple[float, str], list[Dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        line = sample["line"]
        groups[(line, "_global")].append(sample)
        if sample.get("league_name_cn") and sample["league_name_cn"] != "_unknown":
            groups[(line, sample["league_name_cn"])].append(sample)

    profiles: Dict[Tuple[float, str], Dict[str, Any]] = {}
    for (line, league_name_cn), rows in groups.items():
        totals = [int(row["total_goals"]) for row in rows]
        sample_size = len(rows)
        if sample_size <= 0:
            continue

        over_count = sum(1 for total in totals if total > line)
        under_count = sum(1 for total in totals if total < line)
        push_count = sum(1 for total in totals if abs(total - line) < 0.001)
        edge_count = sum(1 for total in totals if _is_edge_total(total, line))
        hit_count = sum(int(row.get("is_correct") or 0) for row in rows)

        profiles[(line, league_name_cn)] = {
            "profile_key": _profile_key(line, league_name_cn),
            "line": line,
            "league_name_cn": league_name_cn,
            "scenario_type": "_all",
            "sample_size": sample_size,
            "over_rate": over_count / sample_size,
            "under_rate": under_count / sample_size,
            "push_rate": push_count / sample_size,
            "edge_rate": edge_count / sample_size,
            "avg_total_goals": sum(totals) / sample_size,
            "median_total_goals": median(totals),
            "prediction_hit_rate": hit_count / sample_size,
            "edge_definition": _edge_definition(line),
            "source": "post_match_reviews",
        }
    return profiles


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ou_line_calibration (
            profile_key TEXT PRIMARY KEY,
            line REAL NOT NULL,
            league_name_cn TEXT,
            scenario_type TEXT DEFAULT '_all',
            sample_size INTEGER NOT NULL,
            over_rate REAL,
            under_rate REAL,
            push_rate REAL,
            edge_rate REAL,
            avg_total_goals REAL,
            median_total_goals REAL,
            prediction_hit_rate REAL,
            edge_definition TEXT,
            source TEXT DEFAULT 'post_match_reviews',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ou_line_calibration_line ON ou_line_calibration(line)"
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ou_line_calibration_league_line
        ON ou_line_calibration(league_name_cn, line)
        """
    )
    conn.commit()


def build_ou_line_calibration(db_path: Path, min_samples_to_print: int = 1) -> Dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _ensure_table(conn)

    samples = []
    skipped = 0
    for row in _iter_review_rows(conn):
        sample = _row_to_sample(row)
        if sample:
            samples.append(sample)
        else:
            skipped += 1

    profiles = _build_profiles(samples)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with conn:
        conn.execute("DELETE FROM ou_line_calibration")
        conn.executemany(
            """
            INSERT OR REPLACE INTO ou_line_calibration (
                profile_key, line, league_name_cn, scenario_type, sample_size,
                over_rate, under_rate, push_rate, edge_rate, avg_total_goals,
                median_total_goals, prediction_hit_rate, edge_definition,
                source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    profile["profile_key"],
                    profile["line"],
                    profile["league_name_cn"],
                    profile["scenario_type"],
                    profile["sample_size"],
                    profile["over_rate"],
                    profile["under_rate"],
                    profile["push_rate"],
                    profile["edge_rate"],
                    profile["avg_total_goals"],
                    profile["median_total_goals"],
                    profile["prediction_hit_rate"],
                    profile["edge_definition"],
                    profile["source"],
                    now,
                )
                for profile in profiles.values()
            ],
        )

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT line, league_name_cn, sample_size, over_rate, under_rate, push_rate, edge_rate
        FROM ou_line_calibration
        WHERE sample_size >= ?
        ORDER BY CASE WHEN league_name_cn = '_global' THEN 0 ELSE 1 END,
                 sample_size DESC, line
        LIMIT 20
        """,
        (min_samples_to_print,),
    )
    preview = cursor.fetchall()
    conn.close()

    print(f"Built ou_line_calibration: samples={len(samples)}, profiles={len(profiles)}, skipped={skipped}")
    for row in preview:
        print(
            f"  line={row['line']:g} league={row['league_name_cn']} "
            f"n={row['sample_size']} over={row['over_rate']:.1%} "
            f"under={row['under_rate']:.1%} push={row['push_rate']:.1%} "
            f"edge={row['edge_rate']:.1%}"
        )
    return {"samples": len(samples), "profiles": len(profiles), "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to football_v2.db")
    parser.add_argument("--min-samples-to-print", type=int, default=1)
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    build_ou_line_calibration(db_path, args.min_samples_to_print)


if __name__ == "__main__":
    main()
