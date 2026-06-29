"""Build durable per-team match facts for tempo and defensive-risk signals.

The table is intentionally event-level, not aggregate-level. Analysis can
query rows before a match date, so this does not leak post-match information
into pre-match predictions.
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS team_match_facts (
    fact_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_match_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    opponent_team_id TEXT,
    team_name TEXT,
    opponent_name TEXT,
    league_name_cn TEXT,
    match_date TEXT NOT NULL,
    is_home INTEGER NOT NULL DEFAULT 0,
    goals_for INTEGER,
    goals_against INTEGER,
    goals_ht_for INTEGER,
    goals_ht_against INTEGER,
    total_goals INTEGER,
    ht_total_goals INTEGER,
    result_code TEXT,
    shots_for INTEGER,
    shots_against INTEGER,
    shots_on_target_for INTEGER,
    shots_on_target_against INTEGER,
    xg_for REAL,
    xg_against REAL,
    possession_for REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_team_match_facts_team_date ON team_match_facts(team_id, match_date);",
    "CREATE INDEX IF NOT EXISTS idx_team_match_facts_source ON team_match_facts(source_name, source_match_id);",
    "CREATE INDEX IF NOT EXISTS idx_team_match_facts_league_date ON team_match_facts(league_name_cn, match_date);",
]


UPSERT_SQL = """
INSERT INTO team_match_facts (
    fact_id, source_name, source_match_id, team_id, opponent_team_id,
    team_name, opponent_name, league_name_cn, match_date, is_home,
    goals_for, goals_against, goals_ht_for, goals_ht_against,
    total_goals, ht_total_goals, result_code,
    shots_for, shots_against, shots_on_target_for, shots_on_target_against,
    xg_for, xg_against, possession_for, updated_at
) VALUES (
    :fact_id, :source_name, :source_match_id, :team_id, :opponent_team_id,
    :team_name, :opponent_name, :league_name_cn, :match_date, :is_home,
    :goals_for, :goals_against, :goals_ht_for, :goals_ht_against,
    :total_goals, :ht_total_goals, :result_code,
    :shots_for, :shots_against, :shots_on_target_for, :shots_on_target_against,
    :xg_for, :xg_against, :possession_for, CURRENT_TIMESTAMP
)
ON CONFLICT(fact_id) DO UPDATE SET
    opponent_team_id=excluded.opponent_team_id,
    team_name=excluded.team_name,
    opponent_name=excluded.opponent_name,
    league_name_cn=excluded.league_name_cn,
    match_date=excluded.match_date,
    is_home=excluded.is_home,
    goals_for=excluded.goals_for,
    goals_against=excluded.goals_against,
    goals_ht_for=excluded.goals_ht_for,
    goals_ht_against=excluded.goals_ht_against,
    total_goals=excluded.total_goals,
    ht_total_goals=excluded.ht_total_goals,
    result_code=excluded.result_code,
    shots_for=excluded.shots_for,
    shots_against=excluded.shots_against,
    shots_on_target_for=excluded.shots_on_target_for,
    shots_on_target_against=excluded.shots_on_target_against,
    xg_for=excluded.xg_for,
    xg_against=excluded.xg_against,
    possession_for=excluded.possession_for,
    updated_at=CURRENT_TIMESTAMP;
"""


def compact_id(*parts: Any) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    return "tmf_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def result_code(gf: Optional[int], ga: Optional[int]) -> Optional[str]:
    if gf is None or ga is None:
        return None
    if gf > ga:
        return "W"
    if gf == ga:
        return "D"
    return "L"


def add_fact(
    facts: List[Dict[str, Any]],
    *,
    source_name: str,
    source_match_id: Any,
    team_id: Any,
    opponent_team_id: Any,
    team_name: Any,
    opponent_name: Any,
    league_name_cn: Any,
    match_date: Any,
    is_home: bool,
    goals_for: Any,
    goals_against: Any,
    goals_ht_for: Any,
    goals_ht_against: Any,
    shots_for: Any = None,
    shots_against: Any = None,
    shots_on_target_for: Any = None,
    shots_on_target_against: Any = None,
    xg_for: Any = None,
    xg_against: Any = None,
    possession_for: Any = None,
) -> None:
    gf = to_int(goals_for)
    ga = to_int(goals_against)
    ht_for = to_int(goals_ht_for)
    ht_against = to_int(goals_ht_against)
    if team_id in (None, "") or source_match_id in (None, "") or not match_date:
        return
    if gf is None or ga is None:
        return
    facts.append({
        "fact_id": compact_id(source_name, source_match_id, team_id),
        "source_name": source_name,
        "source_match_id": str(source_match_id),
        "team_id": str(team_id),
        "opponent_team_id": None if opponent_team_id is None else str(opponent_team_id),
        "team_name": None if team_name is None else str(team_name),
        "opponent_name": None if opponent_name is None else str(opponent_name),
        "league_name_cn": None if league_name_cn is None else str(league_name_cn),
        "match_date": str(match_date)[:10],
        "is_home": 1 if is_home else 0,
        "goals_for": gf,
        "goals_against": ga,
        "goals_ht_for": ht_for,
        "goals_ht_against": ht_against,
        "total_goals": gf + ga,
        "ht_total_goals": (ht_for + ht_against) if ht_for is not None and ht_against is not None else None,
        "result_code": result_code(gf, ga),
        "shots_for": to_int(shots_for),
        "shots_against": to_int(shots_against),
        "shots_on_target_for": to_int(shots_on_target_for),
        "shots_on_target_against": to_int(shots_on_target_against),
        "xg_for": to_float(xg_for),
        "xg_against": to_float(xg_against),
        "possession_for": to_float(possession_for),
    })


def fetch_match_facts(conn: sqlite3.Connection, date_from: str, date_to: str, league: str) -> List[Dict[str, Any]]:
    if not table_exists(conn, "matches"):
        return []
    match_cols = columns(conn, "matches")
    has_leagues = table_exists(conn, "leagues")
    where = [
        "m.home_goals IS NOT NULL",
        "m.away_goals IS NOT NULL",
        "m.match_date BETWEEN ? AND ?",
    ]
    params: List[Any] = [date_from, date_to]
    if league and has_leagues:
        where.append("COALESCE(l.name_cn, '') = ?")
        params.append(league)

    select_shots = all(col in match_cols for col in ("home_shots", "away_shots"))
    select_sot = all(col in match_cols for col in ("home_shots_target", "away_shots_target"))
    select_xg = all(col in match_cols for col in ("home_xg", "away_xg"))
    select_possession = all(col in match_cols for col in ("home_possession", "away_possession"))
    league_select = "l.name_cn AS league_name_cn" if has_leagues else "NULL AS league_name_cn"
    league_join = "LEFT JOIN leagues l ON l.league_id = m.league_id" if has_leagues else ""

    rows = conn.execute(f"""
        SELECT m.match_id, m.match_date, m.home_team_id, m.away_team_id,
               ht.name_cn AS home_name, at.name_cn AS away_name,
               {league_select},
               m.home_goals, m.away_goals, m.home_goals_ht, m.away_goals_ht,
               {'m.home_shots' if select_shots else 'NULL'} AS home_shots,
               {'m.away_shots' if select_shots else 'NULL'} AS away_shots,
               {'m.home_shots_target' if select_sot else 'NULL'} AS home_sot,
               {'m.away_shots_target' if select_sot else 'NULL'} AS away_sot,
               {'m.home_xg' if select_xg else 'NULL'} AS home_xg,
               {'m.away_xg' if select_xg else 'NULL'} AS away_xg,
               {'m.home_possession' if select_possession else 'NULL'} AS home_possession,
               {'m.away_possession' if select_possession else 'NULL'} AS away_possession
        FROM matches m
        LEFT JOIN teams ht ON ht.team_id = m.home_team_id
        LEFT JOIN teams at ON at.team_id = m.away_team_id
        {league_join}
        WHERE {' AND '.join(where)}
    """, params).fetchall()

    facts: List[Dict[str, Any]] = []
    for row in rows:
        add_fact(
            facts,
            source_name="matches",
            source_match_id=row["match_id"],
            team_id=row["home_team_id"],
            opponent_team_id=row["away_team_id"],
            team_name=row["home_name"],
            opponent_name=row["away_name"],
            league_name_cn=row["league_name_cn"],
            match_date=row["match_date"],
            is_home=True,
            goals_for=row["home_goals"],
            goals_against=row["away_goals"],
            goals_ht_for=row["home_goals_ht"],
            goals_ht_against=row["away_goals_ht"],
            shots_for=row["home_shots"],
            shots_against=row["away_shots"],
            shots_on_target_for=row["home_sot"],
            shots_on_target_against=row["away_sot"],
            xg_for=row["home_xg"],
            xg_against=row["away_xg"],
            possession_for=row["home_possession"],
        )
        add_fact(
            facts,
            source_name="matches",
            source_match_id=row["match_id"],
            team_id=row["away_team_id"],
            opponent_team_id=row["home_team_id"],
            team_name=row["away_name"],
            opponent_name=row["home_name"],
            league_name_cn=row["league_name_cn"],
            match_date=row["match_date"],
            is_home=False,
            goals_for=row["away_goals"],
            goals_against=row["home_goals"],
            goals_ht_for=row["away_goals_ht"],
            goals_ht_against=row["home_goals_ht"],
            shots_for=row["away_shots"],
            shots_against=row["home_shots"],
            shots_on_target_for=row["away_sot"],
            shots_on_target_against=row["home_sot"],
            xg_for=row["away_xg"],
            xg_against=row["home_xg"],
            possession_for=row["away_possession"],
        )
    return facts


def fetch_lottery_facts(conn: sqlite3.Connection, date_from: str, date_to: str, league: str) -> List[Dict[str, Any]]:
    if not table_exists(conn, "lottery_matches") or not table_exists(conn, "lottery_results"):
        return []
    where = [
        "lr.home_goals_ft IS NOT NULL",
        "lr.away_goals_ft IS NOT NULL",
        "substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) BETWEEN ? AND ?",
    ]
    params: List[Any] = [date_from, date_to]
    if league:
        where.append("COALESCE(lm.league_name_cn, '') = ?")
        params.append(league)
    rows = conn.execute(f"""
        SELECT lm.lottery_match_id, COALESCE(lm.beijing_time, lm.match_date) AS d,
               lm.home_team_id, lm.away_team_id, lm.home_team_cn, lm.away_team_cn,
               lm.league_name_cn,
               lr.home_goals_ft, lr.away_goals_ft, lr.home_goals_ht, lr.away_goals_ht
        FROM lottery_matches lm
        JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
        WHERE {' AND '.join(where)}
    """, params).fetchall()

    facts: List[Dict[str, Any]] = []
    for row in rows:
        add_fact(
            facts,
            source_name="lottery_results",
            source_match_id=row["lottery_match_id"],
            team_id=row["home_team_id"],
            opponent_team_id=row["away_team_id"],
            team_name=row["home_team_cn"],
            opponent_name=row["away_team_cn"],
            league_name_cn=row["league_name_cn"],
            match_date=row["d"],
            is_home=True,
            goals_for=row["home_goals_ft"],
            goals_against=row["away_goals_ft"],
            goals_ht_for=row["home_goals_ht"],
            goals_ht_against=row["away_goals_ht"],
        )
        add_fact(
            facts,
            source_name="lottery_results",
            source_match_id=row["lottery_match_id"],
            team_id=row["away_team_id"],
            opponent_team_id=row["home_team_id"],
            team_name=row["away_team_cn"],
            opponent_name=row["home_team_cn"],
            league_name_cn=row["league_name_cn"],
            match_date=row["d"],
            is_home=False,
            goals_for=row["away_goals_ft"],
            goals_against=row["home_goals_ft"],
            goals_ht_for=row["away_goals_ht"],
            goals_ht_against=row["home_goals_ht"],
        )
    return facts


def build(db_path: Path, date_from: str, date_to: str, league: str, apply: bool) -> Dict[str, Any]:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    try:
        match_facts = fetch_match_facts(conn, date_from, date_to, league)
        lottery_facts = fetch_lottery_facts(conn, date_from, date_to, league)
        facts = {item["fact_id"]: item for item in [*match_facts, *lottery_facts]}
        summary = {
            "db": str(db_path),
            "mode": "apply" if apply else "dry_run",
            "date_from": date_from,
            "date_to": date_to,
            "league": league,
            "matches_facts": len(match_facts),
            "lottery_facts": len(lottery_facts),
            "unique_facts": len(facts),
        }
        if not apply:
            return summary
        conn.execute(CREATE_SQL)
        for statement in INDEX_SQL:
            conn.execute(statement)
        before_changes = conn.total_changes
        conn.executemany(UPSERT_SQL, list(facts.values()))
        conn.commit()
        summary["upserted"] = conn.total_changes - before_changes
        summary["total_rows"] = conn.execute("SELECT COUNT(*) FROM team_match_facts").fetchone()[0]
        return summary
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-team match facts from settled match tables.")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--from", dest="date_from", default="1900-01-01")
    parser.add_argument("--to", dest="date_to", default="2100-12-31")
    parser.add_argument("--league", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(build(Path(args.db), args.date_from, args.date_to, args.league, args.apply))


if __name__ == "__main__":
    main()
