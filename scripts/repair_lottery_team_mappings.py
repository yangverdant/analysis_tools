"""Repair lottery match team mappings using canonical team history.

This script turns runtime fallbacks into durable mappings:
- choose a canonical team_id from the team name and recent half-time history
- write source_entity_mappings for the sporttery/lottery name
- optionally update lottery_matches.home_team_id / away_team_id

It is intentionally conservative: youth/women/reserve labels are ignored, and a
mapping is updated only when the candidate clearly matches the lottery team
name and has better historical coverage than the current id.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "football_v2.db"

ALIAS_GROUPS = [
    ("韩国", "韩国共和国", "大韩民国", "Korea Republic", "South Korea"),
    ("捷克", "捷克共和国", "Czechia", "Czech Republic"),
    ("刚果(金)", "刚果（金）", "刚果民主共和国", "刚果民主", "DR Congo", "Congo DR", "Congo Democratic Republic"),
    ("科特迪瓦", "象牙海岸", "Ivory Coast", "Cote d'Ivoire", "Côte d'Ivoire"),
    ("库拉索", "Curacao", "Curaçao"),
    ("波黑", "波斯尼亚和黑塞哥维那", "Bosnia-H.", "Bosnia and Herzegovina"),
    ("美国", "USA", "United States", "United States of America"),
]


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    return conn


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def stable_id(*parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def is_senior_team_label(label: Any) -> bool:
    text = str(label or "").strip().lower()
    if not text:
        return True
    padded = f" {text} "
    markers = (" u16", " u17", " u18", " u19", " u20", " u21", " u23", " women", " w ")
    if any(marker in padded for marker in markers):
        return False
    if text.endswith(" w") or text.startswith("team "):
        return False
    return True


def nonempty(value: Any) -> str:
    return str(value or "").strip()


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def normalize_label(value: Any) -> str:
    text = unicodedata.normalize("NFKD", nonempty(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = text.replace("（", "(").replace("）", ")")
    return re.sub(r"[\s\-_./'’`·,，、:：()（）]+", "", text)


def alias_norms_for_hint(hint: str) -> set[str]:
    hint_norm = normalize_label(hint)
    aliases = {hint_norm} if hint_norm else set()
    for group in ALIAS_GROUPS:
        group_norms = {normalize_label(item) for item in group}
        if hint_norm in group_norms:
            aliases.update(group_norms)
    return aliases


def alias_values_for_hint(hint: str) -> List[str]:
    hint_norm = normalize_label(hint)
    values = [nonempty(hint)] if nonempty(hint) else []
    for group in ALIAS_GROUPS:
        group_norms = {normalize_label(item) for item in group}
        if hint_norm in group_norms:
            values.extend(group)
    seen = set()
    result = []
    for value in values:
        key = normalize_label(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def label_matches_hint(label: Any, hint: str) -> bool:
    label_text = nonempty(label)
    hint_text = nonempty(hint)
    if not label_text or not hint_text:
        return False
    label_norm = normalize_label(label_text)
    hint_norm = normalize_label(hint_text)
    if len(label_norm) < 2 and len(hint_norm) < 2:
        return False
    if label_norm in alias_norms_for_hint(hint_text):
        return True
    if has_cjk(label_text) or has_cjk(hint_text):
        # Chinese substrings are dangerous: 突尼斯 must not match 尼斯.
        return (
            len(label_norm) >= 3
            and len(hint_norm) >= 3
            and (label_norm.startswith(hint_norm) or hint_norm.startswith(label_norm))
        )
    return (
        len(label_norm) >= 5
        and len(hint_norm) >= 5
        and (label_norm.startswith(hint_norm) or hint_norm.startswith(label_norm))
    )


def sample_count(conn: sqlite3.Connection, team_ids: Sequence[Any], before_date: str = "") -> int:
    ids = [item for item in team_ids if item not in (None, "")]
    if not ids:
        return 0
    placeholders = ",".join(["?"] * len(ids))
    params: List[Any] = list(ids) + list(ids)
    date_filter = ""
    if before_date:
        date_filter = "AND date(match_date) < date(?)"
        params.append(str(before_date)[:10])
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM matches
        WHERE (home_team_id IN ({placeholders}) OR away_team_id IN ({placeholders}))
          AND home_goals IS NOT NULL AND away_goals IS NOT NULL
          AND home_goals_ht IS NOT NULL AND away_goals_ht IS NOT NULL
          {date_filter}
        """,
        params,
    ).fetchone()
    return int(row["c"] if row else 0)


def team_row(conn: sqlite3.Connection, team_id: Any) -> Optional[sqlite3.Row]:
    if team_id in (None, ""):
        return None
    return conn.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,)).fetchone()


def team_labels(row: sqlite3.Row, columns: set[str]) -> List[str]:
    labels = []
    for column in (
        "name_cn",
        "sporttery_name_cn",
        "oddsfe_name_cn",
        "apifootball_name_cn",
        "name_en",
        "sporttery_name_en",
        "oddsfe_name_en",
        "apifootball_name_en",
    ):
        if column in columns and row[column]:
            labels.append(str(row[column]))
    return labels


def alias_ids(conn: sqlite3.Connection, base_row: sqlite3.Row, columns: set[str], name_hint: str = "") -> List[Any]:
    clauses = ["team_id = ?"]
    params: List[Any] = [base_row["team_id"]]
    for column in ("oddsfe_team_id", "sm_team_id", "sporttery_team_id"):
        if column in columns and base_row[column] not in (None, ""):
            clauses.append(f"{column} = ?")
            params.append(base_row[column])
    for column in ("name_en", "name_cn"):
        if column in columns and base_row[column] not in (None, "") and label_matches_hint(base_row[column], name_hint):
            clauses.append(f"{column} = ?")
            params.append(base_row[column])
    select_columns = ["team_id"]
    for column in ("name_en", "name_cn", "sporttery_name_cn", "sporttery_name_en", "oddsfe_name_cn", "oddsfe_name_en"):
        if column in columns:
            select_columns.append(column)
    rows = conn.execute(
        f"SELECT {', '.join(select_columns)} FROM teams WHERE {' OR '.join(clauses)}",
        params,
    ).fetchall()
    result = []
    for row in rows:
        labels = [row[col] for col in row.keys() if col != "team_id"]
        hint_ok = not name_hint or any(label_matches_hint(label, name_hint) for label in labels if label)
        if row["team_id"] == base_row["team_id"]:
            hint_ok = True
        if hint_ok and all(is_senior_team_label(label) for label in labels if label):
            result.append(row["team_id"])
    return result or [base_row["team_id"]]


def candidate_rows(conn: sqlite3.Connection, name_hint: str, current_id: Any, columns: set[str]) -> List[sqlite3.Row]:
    clauses = []
    params: List[Any] = []
    if current_id not in (None, ""):
        clauses.append("team_id = ?")
        params.append(current_id)

    hint = nonempty(name_hint)
    if hint:
        hint_bits = []
        hint_values = alias_values_for_hint(hint)
        for value in hint_values:
            for column in ("name_cn", "sporttery_name_cn", "oddsfe_name_cn", "apifootball_name_cn", "name_en", "sporttery_name_en", "oddsfe_name_en", "apifootball_name_en"):
                if column in columns:
                    hint_bits.append(f"{column} = ?")
                    params.append(value)
        for column in ("name_cn", "sporttery_name_cn", "oddsfe_name_cn", "apifootball_name_cn"):
            if column in columns:
                hint_bits.append(f"({column} IS NOT NULL AND length({column}) >= 2 AND {column} LIKE ? || '%')")
                params.append(hint)
                hint_bits.append(f"({column} IS NOT NULL AND length({column}) >= 2 AND ? LIKE {column} || '%')")
                params.append(hint)
        if "name_cn_aliases" in columns:
            hint_bits.append("name_cn_aliases LIKE ?")
            params.append(f"%{hint}%")
        if hint_bits:
            clauses.append("(" + " OR ".join(hint_bits) + ")")

    if not clauses:
        return []
    return conn.execute(f"SELECT * FROM teams WHERE {' OR '.join(clauses)}", params).fetchall()


def choose_canonical(
    conn: sqlite3.Connection,
    name_hint: str,
    current_id: Any,
    before_date: str,
    preferred_team_type: str = "",
) -> Optional[Dict[str, Any]]:
    columns = table_columns(conn, "teams")
    rows = candidate_rows(conn, name_hint, current_id, columns)
    if not rows:
        return None

    candidates = []
    for row in rows:
        labels = team_labels(row, columns)
        if not all(is_senior_team_label(label) for label in labels if label):
            continue
        matched_by_name = any(label_matches_hint(label, name_hint) for label in labels)
        if not matched_by_name and row["team_id"] != current_id:
            continue
        team_type = nonempty(row["team_type"]) if "team_type" in columns else ""
        if preferred_team_type and row["team_id"] != current_id and team_type and team_type != preferred_team_type:
            continue
        aliases = alias_ids(conn, row, columns, name_hint)
        samples = sample_count(conn, aliases, before_date)
        current_penalty = 0 if row["team_id"] == current_id else 1
        type_bonus = 1 if (not preferred_team_type or team_type == preferred_team_type) else 0
        candidates.append({
            "team_id": row["team_id"],
            "labels": labels,
            "aliases": aliases,
            "sample_count": samples,
            "matched_by_name": matched_by_name,
            "current": row["team_id"] == current_id,
            "team_type": team_type,
            "sort_key": (1 if matched_by_name else 0, type_bonus, samples, current_penalty * -1),
        })

    if not candidates:
        return None

    candidates.sort(key=lambda item: item["sort_key"], reverse=True)
    best = candidates[0]
    current = next((item for item in candidates if item["current"]), None)
    current_samples = int(current["sample_count"]) if current else 0

    should_update = best["team_id"] != current_id and best["matched_by_name"] and (
        current is None
        or not current["matched_by_name"]
        or best["sample_count"] >= max(8, current_samples + 5)
    )
    return {
        **best,
        "current_sample_count": current_samples,
        "should_update": should_update,
        "candidate_count": len(candidates),
    }


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
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_source_entity_mapping_unique
        ON source_entity_mappings(entity_type, source_name, source_entity_id)
        """
    )


def upsert_mapping(
    conn: sqlite3.Connection,
    source_name: str,
    source_entity_id: str,
    source_entity_name: str,
    canonical_id: Any,
    confidence: float,
) -> None:
    mapping_id = "map_" + stable_id("team", source_name, source_entity_id)
    conn.execute(
        """
        INSERT INTO source_entity_mappings (
            mapping_id, entity_type, canonical_id, source_name, source_entity_id,
            source_entity_name, confidence, status, updated_at
        )
        VALUES (?, 'team', ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
        ON CONFLICT(entity_type, source_name, source_entity_id) DO UPDATE SET
            canonical_id = excluded.canonical_id,
            source_entity_name = excluded.source_entity_name,
            confidence = excluded.confidence,
            status = 'active',
            updated_at = CURRENT_TIMESTAMP
        """,
        (mapping_id, str(canonical_id), source_name, str(source_entity_id), source_entity_name, confidence),
    )


def iter_lottery_rows(conn: sqlite3.Connection, date_from: str, date_to: str, league: str) -> Iterable[sqlite3.Row]:
    params: List[Any] = []
    where = ["1=1"]
    if date_from:
        where.append("date(match_date) >= date(?)")
        params.append(date_from)
    if date_to:
        where.append("date(match_date) <= date(?)")
        params.append(date_to)
    if league:
        where.append("league_name_cn = ?")
        params.append(league)
    return conn.execute(
        f"""
        SELECT lottery_match_id, match_date, home_team_cn, away_team_cn,
               home_team_id, away_team_id
        FROM lottery_matches
        WHERE {' AND '.join(where)}
        ORDER BY match_date, match_time, lottery_match_id
        """,
        params,
    ).fetchall()


def repair(db_path: Path, date_from: str, date_to: str, league: str, apply: bool) -> Dict[str, Any]:
    conn = connect(db_path)
    ensure_mapping_table(conn)
    rows = list(iter_lottery_rows(conn, date_from, date_to, league))
    changes = []
    mappings = 0
    preferred_team_type = "national" if league == "世界杯" else ""

    for row in rows:
        for side in ("home", "away"):
            name = row[f"{side}_team_cn"]
            current_id = row[f"{side}_team_id"]
            chosen = choose_canonical(conn, name, current_id, row["match_date"], preferred_team_type)
            if not chosen:
                continue
            confidence = 0.95 if chosen["sample_count"] >= 8 else 0.75
            source_entity_id = nonempty(name) or str(current_id)
            if apply:
                upsert_mapping(conn, "sporttery_name", source_entity_id, name, chosen["team_id"], confidence)
                upsert_mapping(
                    conn,
                    "lottery_match_team_ref",
                    f"{row['lottery_match_id']}:{side}",
                    f"{name}|old_id={current_id}",
                    chosen["team_id"],
                    confidence,
                )
                mappings += 2
            if chosen["should_update"]:
                change = {
                    "lottery_match_id": row["lottery_match_id"],
                    "side": side,
                    "name": name,
                    "old_team_id": current_id,
                    "new_team_id": chosen["team_id"],
                    "new_alias_ids": chosen["aliases"],
                    "old_sample_count": chosen["current_sample_count"],
                    "new_sample_count": chosen["sample_count"],
                    "candidate_count": chosen["candidate_count"],
                }
                changes.append(change)
                if apply:
                    column = f"{side}_team_id"
                    conn.execute(
                        f"UPDATE lottery_matches SET {column} = ?, updated_at = CURRENT_TIMESTAMP WHERE lottery_match_id = ?",
                        (chosen["team_id"], row["lottery_match_id"]),
                    )

    if apply:
        conn.commit()
    else:
        conn.rollback()
    conn.close()

    print(json.dumps({
        "db": str(db_path),
        "mode": "apply" if apply else "dry_run",
        "matches_scanned": len(rows),
        "changes": len(changes),
        "mappings_upserted": mappings if apply else 0,
        "change_preview": changes[:80],
    }, ensure_ascii=False, indent=2))
    return {"matches_scanned": len(rows), "changes": len(changes), "mappings": mappings}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--date-from", default="2026-06-11")
    parser.add_argument("--date-to", default="2026-07-19")
    parser.add_argument("--league", default="世界杯")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    repair(db_path, args.date_from, args.date_to, args.league, args.apply)


if __name__ == "__main__":
    main()
