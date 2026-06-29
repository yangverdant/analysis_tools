"""Backfill APIFootball team ids from the local apifootball_teams cache.

Default mode is dry-run. Use --apply to update teams.apifootball_team_id and
source_entity_mappings. The matcher intentionally uses only exact normalized
names and a small alias list, so unmatched teams remain explicit gaps.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "football_v2.db"


ALIASES = {
    "bosnia": "Bosnia and Herzegovina",
    "bosnia herzegovina": "Bosnia and Herzegovina",
    "bosnia & herzegovina": "Bosnia and Herzegovina",
    "cote divoire": "Cote d'Ivoire",
    "cote d ivoire": "Cote d'Ivoire",
    "cote d'ivoire": "Cote d'Ivoire",
    "ivory coast": "Cote d'Ivoire",
    "czechia": "Czech Republic",
    "dr congo": "DR Congo",
    "d r congo": "DR Congo",
    "congo dr": "DR Congo",
    "democratic republic of congo": "DR Congo",
    "ir iran": "Iran",
    "iran": "Iran",
    "south korea": "South Korea",
    "korea republic": "South Korea",
    "usa": "United States",
    "united states": "United States",
    "curacao": "Curacao",
    "curaçao": "Curacao",
}


@dataclass
class Candidate:
    team_id: int
    name_cn: Optional[str]
    name_en: Optional[str]
    oddsfe_name_en: Optional[str]
    sporttery_name_en: Optional[str]
    apifootball_team_id: Optional[str]
    team_type: Optional[str]
    country: Optional[str]


@dataclass
class ApiTeam:
    api_id: str
    name: str
    is_national: bool


def norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def alias_target(value: Any) -> Optional[str]:
    n = norm(value)
    if not n:
        return None
    return ALIASES.get(n) or str(value).strip()


def compact_id(*parts: Any) -> str:
    raw = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def load_api_teams(conn: sqlite3.Connection) -> Dict[str, ApiTeam]:
    rows = conn.execute(
        """
        SELECT apifootball_id, team_name, COALESCE(is_national, 0) AS is_national
        FROM apifootball_teams
        WHERE apifootball_id IS NOT NULL
          AND team_name IS NOT NULL
          AND TRIM(team_name) <> ''
        """
    ).fetchall()
    result: Dict[str, ApiTeam] = {}
    for row in rows:
        api = ApiTeam(str(row["apifootball_id"]), row["team_name"], bool(row["is_national"]))
        keys = {norm(api.name)}
        target = alias_target(api.name)
        if target:
            keys.add(norm(target))
        for key in keys:
            if key and key not in result:
                result[key] = api
    return result


def load_candidates(
    conn: sqlite3.Connection,
    date_from: Optional[str],
    date_to: Optional[str],
    league: Optional[str],
    all_missing: bool,
) -> List[Candidate]:
    if all_missing:
        where = ["(apifootball_team_id IS NULL OR apifootball_team_id = '')"]
        params: List[Any] = []
        query = f"""
            SELECT team_id, name_cn, name_en, oddsfe_name_en, sporttery_name_en,
                   apifootball_team_id, team_type, country
            FROM teams
            WHERE {' AND '.join(where)}
            ORDER BY team_id
        """
        rows = conn.execute(query, params).fetchall()
    else:
        where = ["1=1"]
        params = []
        if date_from:
            where.append("lm.match_date >= ?")
            params.append(date_from)
        if date_to:
            where.append("lm.match_date <= ?")
            params.append(date_to)
        if league:
            where.append("lm.league_name_cn = ?")
            params.append(league)
        query = f"""
            SELECT DISTINCT t.team_id, t.name_cn, t.name_en, t.oddsfe_name_en,
                   t.sporttery_name_en, t.apifootball_team_id, t.team_type, t.country
            FROM lottery_matches lm
            JOIN teams t ON t.team_id IN (lm.home_team_id, lm.away_team_id)
            WHERE {' AND '.join(where)}
            ORDER BY t.team_id
        """
        rows = conn.execute(query, params).fetchall()
    return [Candidate(**dict(row)) for row in rows]


def match_candidate(candidate: Candidate, api_index: Dict[str, ApiTeam]) -> Tuple[Optional[ApiTeam], str, float]:
    names = [
        ("name_en", candidate.name_en, 0.98),
        ("oddsfe_name_en", candidate.oddsfe_name_en, 0.96),
        ("sporttery_name_en", candidate.sporttery_name_en, 0.94),
    ]
    for field, value, confidence in names:
        if not value:
            continue
        direct = api_index.get(norm(value))
        if direct:
            return direct, f"{field}:exact", confidence
        target = alias_target(value)
        if target and target != value:
            alias = api_index.get(norm(target))
            if alias:
                return alias, f"{field}:alias:{target}", min(confidence, 0.94)
    return None, "unmatched", 0.0


def ensure_mapping_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_entity_mappings (
            mapping_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            canonical_id TEXT,
            source_name TEXT NOT NULL,
            source_entity_id TEXT,
            source_entity_name TEXT,
            confidence REAL DEFAULT 0.5,
            status TEXT NOT NULL DEFAULT 'active',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_source_entity_mapping_unique "
        "ON source_entity_mappings(entity_type, source_name, source_entity_id)"
    )


def apply_match(conn: sqlite3.Connection, candidate: Candidate, api: ApiTeam, method: str, confidence: float) -> None:
    conn.execute(
        """
        UPDATE teams
        SET apifootball_team_id = ?,
            apifootball_name_en = ?,
            team_type = CASE WHEN ? = 1 THEN 'national' ELSE team_type END,
            country = CASE WHEN ? = 1 THEN ? ELSE country END,
            updated_at = CURRENT_TIMESTAMP
        WHERE team_id = ?
        """,
        (api.api_id, api.name, int(api.is_national), int(api.is_national), api.name, candidate.team_id),
    )
    mapping_id = compact_id("map", "team", "apifootball", api.api_id)
    conn.execute(
        """
        INSERT INTO source_entity_mappings (
            mapping_id, entity_type, canonical_id, source_name, source_entity_id,
            source_entity_name, confidence, status, updated_at
        )
        VALUES (?, 'team', ?, 'apifootball', ?, ?, ?, 'active', CURRENT_TIMESTAMP)
        ON CONFLICT(entity_type, source_name, source_entity_id) DO UPDATE SET
            canonical_id = excluded.canonical_id,
            source_entity_name = excluded.source_entity_name,
            confidence = excluded.confidence,
            status = excluded.status,
            updated_at = CURRENT_TIMESTAMP
        """,
        (mapping_id, str(candidate.team_id), api.api_id, api.name, confidence),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO team_aliases (team_id, alias_name, source)
        VALUES (?, ?, ?)
        """,
        (candidate.team_id, api.name, f"apifootball_cache:{method}"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill APIFootball team mappings from local cache")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--date-from", default=None)
    parser.add_argument("--date-to", default=None)
    parser.add_argument("--league", default=None)
    parser.add_argument("--all-missing", action="store_true", help="Scan all teams missing apifootball_team_id")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db, timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    try:
        if not table_exists(conn, "apifootball_teams"):
            raise SystemExit("apifootball_teams table is missing")
        api_index = load_api_teams(conn)
        candidates = load_candidates(conn, args.date_from, args.date_to, args.league, args.all_missing)
        matches = []
        conflicts = []
        unmatched = []
        for candidate in candidates:
            api, method, confidence = match_candidate(candidate, api_index)
            if not api:
                unmatched.append(candidate)
                continue
            existing = str(candidate.apifootball_team_id or "").strip()
            if existing and existing != api.api_id:
                conflicts.append((candidate, api, existing, method))
                continue
            matches.append((candidate, api, method, confidence))

        print(f"candidates={len(candidates)} matched={len(matches)} unmatched={len(unmatched)} conflicts={len(conflicts)}")
        for candidate, api, method, confidence in matches:
            action = "APPLY" if args.apply else "DRY"
            print(f"[{action}] {candidate.team_id} {candidate.name_cn or candidate.name_en} -> {api.name} ({api.api_id}) {method} confidence={confidence:.2f}")
        for candidate, api, existing, method in conflicts:
            print(f"[CONFLICT] {candidate.team_id} {candidate.name_cn or candidate.name_en}: existing={existing}, candidate={api.api_id}/{api.name}, {method}")
        for candidate in unmatched[:40]:
            print(f"[UNMATCHED] {candidate.team_id} {candidate.name_cn or candidate.name_en} / {candidate.name_en}")
        if args.apply and matches:
            ensure_mapping_table(conn)
            for candidate, api, method, confidence in matches:
                apply_match(conn, candidate, api, method, confidence)
            conn.commit()
            print(f"applied={len(matches)}")
        elif not args.apply:
            print("dry-run only; pass --apply to write")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
