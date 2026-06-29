#!/usr/bin/env python3
"""Build team ID mappings for apifootball and api-sports in source_entity_mappings.

Uses apifootball_teams table + team_aliases for fuzzy matching against teams.name_en.
"""

import hashlib
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "football_v2.db"


def _mapping_id(entity_type: str, canonical_id: str, source_name: str) -> str:
    raw = f"{entity_type}|{canonical_id}|{source_name}"
    return "map_" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def _norm(name: str) -> str:
    import re
    return re.sub(r'[^a-z0-9]', '', str(name or '').lower())


def build_apifootball_mappings(conn: sqlite3.Connection) -> Tuple[int, int, List[str]]:
    """Map apifootball_teams to teams table via name matching."""
    cursor = conn.cursor()

    # Load all teams with their normalized names
    cursor.execute("SELECT team_id, name_en, name_cn, tla FROM teams")
    teams_by_norm: Dict[str, dict] = {}
    teams_by_tla: Dict[str, dict] = {}
    for row in cursor.fetchall():
        team_id, name_en, name_cn, tla = row
        norm_en = _norm(name_en) if name_en else ""
        if norm_en:
            teams_by_norm[norm_en] = {"team_id": team_id, "name_en": name_en}
        if tla:
            teams_by_tla[tla.upper()] = {"team_id": team_id, "name_en": name_en}

    # Load team_aliases
    cursor.execute("SELECT team_id, alias_name FROM team_aliases")
    aliases_by_norm: Dict[str, int] = {}
    for row in cursor.fetchall():
        team_id, alias_name = row
        norm = _norm(alias_name)
        if norm:
            aliases_by_norm[norm] = team_id

    # Load apifootball_teams
    cursor.execute("SELECT apifootball_id, team_name, team_name_cn, is_national FROM apifootball_teams")
    apifootball_teams = cursor.fetchall()

    inserted = 0
    skipped = 0
    unmatched: List[str] = []

    now = datetime.now().isoformat()

    for af_id, af_name, af_name_cn, is_national in apifootball_teams:
        # Try to find matching team_id
        canonical_id = None
        confidence = 0.9

        # 1. Exact name match (normalized)
        norm_name = _norm(af_name)
        if norm_name in teams_by_norm:
            canonical_id = str(teams_by_norm[norm_name]["team_id"])
            confidence = 0.95

        # 2. Alias match
        if not canonical_id and norm_name in aliases_by_norm:
            canonical_id = str(aliases_by_norm[norm_name])
            confidence = 0.85

        # 3. Try common name variations
        if not canonical_id:
            # "Korea Republic" -> "South Korea", "Ivory Coast" -> "Cote d'Ivoire"
            name_variants = {
                "korearepublic": "southkorea",
                "ivorycoast": "cotedivoire",
                "czechrepublic": "czechia",
                "bosniaherzegovina": "bosnia",
                "congodr": "drcongo",
                "capeverde": "capeverdeislands",
                "usa": "unitedstates",
            }
            variant = name_variants.get(norm_name, "")
            if variant and variant in teams_by_norm:
                canonical_id = str(teams_by_norm[variant]["team_id"])
                confidence = 0.80
            elif variant and variant in aliases_by_norm:
                canonical_id = str(aliases_by_norm[variant])
                confidence = 0.75

        # 4. Partial match (af_name contained in team name or vice versa)
        if not canonical_id and len(norm_name) > 5:
            for norm_key, team_info in teams_by_norm.items():
                if norm_name in norm_key or norm_key in norm_name:
                    # Only accept if the shorter one is at least 60% of the longer
                    min_len = min(len(norm_name), len(norm_key))
                    max_len = max(len(norm_name), len(norm_key))
                    if min_len / max_len >= 0.6:
                        canonical_id = str(team_info["team_id"])
                        confidence = 0.70
                        break

        if not canonical_id:
            skipped += 1
            unmatched.append(f"apifootball_id={af_id} name={af_name}")
            continue

        # Insert mapping
        mapping_id = _mapping_id("team", canonical_id, "apifootball")
        cursor.execute("""
            INSERT OR REPLACE INTO source_entity_mappings
            (mapping_id, entity_type, canonical_id, source_name, source_entity_id, source_entity_name, confidence, status, updated_at)
            VALUES (?, 'team', ?, 'apifootball', ?, ?, ?, 'active', ?)
        """, (mapping_id, canonical_id, str(af_id), af_name, confidence, now))
        inserted += 1

    return inserted, skipped, unmatched


def build_api_sports_mappings(conn: sqlite3.Connection) -> Tuple[int, int]:
    """For api-sports, use the same team IDs as apifootball (same API family)."""
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # Copy apifootball mappings to api-sports with same canonical_id
    cursor.execute("""
        SELECT canonical_id, source_entity_id, source_entity_name, confidence
        FROM source_entity_mappings
        WHERE entity_type = 'team' AND source_name = 'apifootball'
    """)
    rows = cursor.fetchall()

    inserted = 0
    for canonical_id, af_id, name, confidence in rows:
        mapping_id = _mapping_id("team", canonical_id, "api_sports")
        cursor.execute("""
            INSERT OR REPLACE INTO source_entity_mappings
            (mapping_id, entity_type, canonical_id, source_name, source_entity_id, source_entity_name, confidence, status, updated_at)
            VALUES (?, 'team', ?, 'api_sports', ?, ?, ?, 'active', ?)
        """, (mapping_id, canonical_id, af_id, name, confidence * 0.95, now))
        inserted += 1

    return inserted, 0


def run():
    db_path = str(DB_PATH)
    if not DB_PATH.exists():
        logger.error(f"Database not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)

    logger.info("Building apifootball team mappings...")
    af_inserted, af_skipped, af_unmatched = build_apifootball_mappings(conn)
    logger.info(f"  apifootball: {af_inserted} inserted, {af_skipped} unmatched")

    if af_unmatched[:10]:
        logger.info("  Unmatched samples:")
        for u in af_unmatched[:10]:
            logger.info(f"    {u}")

    logger.info("Building api-sports team mappings...")
    as_inserted, as_skipped = build_api_sports_mappings(conn)
    logger.info(f"  api-sports: {as_inserted} inserted")

    conn.commit()
    conn.close()

    result = {
        "success": True,
        "apifootball_inserted": af_inserted,
        "apifootball_unmatched": af_skipped,
        "api_sports_inserted": as_inserted,
        "unmatched_samples": af_unmatched[:20],
    }
    print(__import__('json').dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
