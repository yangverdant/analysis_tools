"""Repair lottery match team ids to canonical team ids.

This complements source_entity_mappings with a practical DB-level repair for
lottery_matches.home_team_id / away_team_id. It is conservative:
- only scans selected lottery matches;
- candidates must match the lottery team name through Chinese source labels;
- national-team rows and stronger historical samples are preferred;
- dry-run is the default, and --apply creates a backup outside the project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "football_v2.db"
DEFAULT_BACKUP_DIR = Path(os.environ.get("FOOTBALL_BACKUP_DIR", REPO_ROOT.parent / "football_backups"))
DEFAULT_LEAGUE = "\u4e16\u754c\u676f"

CN_LABEL_COLUMNS = (
    "name_cn",
    "sporttery_name_cn",
    "oddsfe_name_cn",
    "apifootball_name_cn",
)
DISPLAY_COLUMNS = (
    "team_id",
    "name_cn",
    "name_en",
    "team_type",
    "country",
    "sporttery_name_cn",
    "oddsfe_name_cn",
    "oddsfe_name_en",
    "oddsfe_team_id",
)
EN_LABEL_COLUMNS = ("name_en", "sporttery_name_en", "oddsfe_name_en", "apifootball_name_en")


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def text(value: Any) -> str:
    return str(value or "").strip()


def norm_en(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", text(value))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()
    raw = raw.replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", raw)


def en_variants(value: Any) -> set[str]:
    base = norm_en(value)
    if not base:
        return set()
    variants = {base}
    variants.add(base.replace("and", ""))
    if "congo" in base and "dr" in base:
        variants.update({"drcongo", "congodr", "democraticrepublicofthecongo"})
    return {item for item in variants if item}


def stable_id(*parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def sample_count(conn: sqlite3.Connection, team_id: Any, before_date: str = "") -> int:
    if team_id in (None, ""):
        return 0
    params: List[Any] = [team_id, team_id]
    date_filter = ""
    if before_date:
        date_filter = "AND date(match_date) < date(?)"
        params.append(str(before_date)[:10])
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM matches
        WHERE (home_team_id = ? OR away_team_id = ?)
          AND home_goals IS NOT NULL AND away_goals IS NOT NULL
          AND home_goals_ht IS NOT NULL AND away_goals_ht IS NOT NULL
          {date_filter}
        """,
        params,
    ).fetchone()
    return int(row["c"] if row else 0)


def label_score(row: sqlite3.Row, team_name: str, team_cols: set[str]) -> int:
    target = text(team_name)
    if not target:
        return 0
    score = 0
    for col in CN_LABEL_COLUMNS:
        if col not in team_cols:
            continue
        value = text(row[col])
        if not value:
            continue
        if value == target:
            score = max(score, 5 if col in {"name_cn", "sporttery_name_cn"} else 4)
        elif len(target) >= 3 and (value.startswith(target) or target.startswith(value)):
            score = max(score, 3)
    # English labels: normalize+compare so accented/variant spellings still hit.
    target_en = norm_en(target)
    if target_en:
        for col in EN_LABEL_COLUMNS:
            if col not in team_cols:
                continue
            value = text(row[col])
            if not value:
                continue
            if norm_en(value) == target_en:
                score = max(score, 4)
    return score


def is_senior_label(value: Any) -> bool:
    label = f" {text(value).lower()} "
    bad = (" u16", " u17", " u18", " u19", " u20", " u21", " u23", " women", " w ")
    return not any(item in label for item in bad)


# League name → expected country for team disambiguation. When multiple
# teams share the same name_cn (e.g. "兰格斯" for both Rangers Scotland
# and Rangers Chile), the league context tells us which country's team
# is correct. Keyed by substring match.
LEAGUE_COUNTRY_HINTS: dict[str, str] = {
    "智利": "Chile",
    "巴甲": "Brazil",
    "巴乙": "Brazil",
    "巴西": "Brazil",
    "阿甲": "Argentina",
    "阿乙": "Argentina",
    "阿根廷": "Argentina",
    "英超": "England",
    "英冠": "England",
    "英甲": "England",
    "英乙": "England",
    "苏超": "Scotland",
    "苏冠": "Scotland",
    "苏甲": "Scotland",
    "西甲": "Spain",
    "西乙": "Spain",
    "德甲": "Germany",
    "德乙": "Germany",
    "意甲": "Italy",
    "意乙": "Italy",
    "法甲": "France",
    "法乙": "France",
    "葡超": "Portugal",
    "葡甲": "Portugal",
    "荷甲": "Netherlands",
    "荷乙": "Netherlands",
    "比甲": "Belgium",
    "比乙": "Belgium",
    "墨超": "Mexico",
    "墨甲": "Mexico",
    "日职": "Japan",
    "日乙": "Japan",
    "韩职": "South Korea",
    "K联赛": "South Korea",
    "美职": "United States",
    "MLS": "United States",
    "中超": "China",
    "中甲": "China",
    "澳超": "Australia",
    "俄超": "Russia",
    "土超": "Turkey",
    "瑞典超": "Sweden",
    "瑞典甲": "Sweden",
    "挪超": "Norway",
    "挪甲": "Norway",
    "丹超": "Denmark",
    "芬超": "Finland",
    "冰岛超": "Iceland",
    "爱超": "Ireland",
    "瑞士超": "Switzerland",
    "奥甲": "Austria",
    "捷甲": "Czech Republic",
    "波兰超": "Poland",
    "匈甲": "Hungary",
    "罗甲": "Romania",
    "乌超": "Ukraine",
    "希腊超": "Greece",
    "以超": "Israel",
    "世界杯": "",  # national teams, no club country hint
    "国际赛": "",  # national teams
    "欧国联": "",
    "亚洲杯": "",
    "非洲杯": "",
    "美洲杯": "",
    "欧冠": "",  # multi-country
    "欧联": "",
    "欧协联": "",
}


def league_country_hint(league_name: str) -> str:
    """Extract expected country from league name for team disambiguation."""
    if not league_name:
        return ""
    for key, country in LEAGUE_COUNTRY_HINTS.items():
        if key in league_name:
            return country
    return ""


def current_english_variants(conn: sqlite3.Connection, current_id: Any, team_cols: set[str]) -> set[str]:
    if current_id in (None, ""):
        return set()
    row = conn.execute("SELECT * FROM teams WHERE team_id = ?", (current_id,)).fetchone()
    if not row:
        return set()
    variants: set[str] = set()
    for col in EN_LABEL_COLUMNS:
        if col in team_cols and row[col]:
            variants.update(en_variants(row[col]))
    return variants


def candidate_rows(conn: sqlite3.Connection, team_name: str, current_id: Any, team_cols: set[str]) -> List[sqlite3.Row]:
    where: List[str] = []
    params: List[Any] = []
    if current_id not in (None, ""):
        where.append("team_id = ?")
        params.append(current_id)
    name = text(team_name)
    if name:
        bits: List[str] = []
        for col in CN_LABEL_COLUMNS:
            if col not in team_cols:
                continue
            bits.append(f"{col} = ?")
            params.append(name)
            bits.append(f"({col} IS NOT NULL AND length({col}) >= 2 AND ? LIKE {col} || '%')")
            params.append(name)
            bits.append(f"({col} IS NOT NULL AND length({col}) >= 2 AND {col} LIKE ? || '%')")
            params.append(name)
        # English-label exact match (handles oddsfe-supplied English names
        # like "Ponte Preta" where the team has no name_cn).
        for col in EN_LABEL_COLUMNS:
            if col not in team_cols:
                continue
            bits.append(f"{col} = ?")
            params.append(name)
        if bits:
            where.append("(" + " OR ".join(bits) + ")")
    if not where:
        return []
    rows = list(conn.execute(f"SELECT * FROM teams WHERE {' OR '.join(where)}", params).fetchall())
    english_anchor = current_english_variants(conn, current_id, team_cols)
    if english_anchor:
        seen = {str(row["team_id"]) for row in rows}
        for row in conn.execute("SELECT * FROM teams").fetchall():
            if str(row["team_id"]) in seen:
                continue
            variants: set[str] = set()
            for col in EN_LABEL_COLUMNS:
                if col in team_cols and row[col]:
                    variants.update(en_variants(row[col]))
            if variants & english_anchor:
                rows.append(row)
                seen.add(str(row["team_id"]))
    return rows


def display_row(row: sqlite3.Row, team_cols: set[str]) -> Dict[str, Any]:
    return {col: row[col] for col in DISPLAY_COLUMNS if col in team_cols}


def choose_canonical(
    conn: sqlite3.Connection,
    team_name: str,
    current_id: Any,
    match_date: str,
    team_cols: set[str],
    league_name: str = "",
) -> Optional[Dict[str, Any]]:
    rows = candidate_rows(conn, team_name, current_id, team_cols)
    if not rows:
        return None
    english_anchor = current_english_variants(conn, current_id, team_cols)
    expected_country = league_country_hint(league_name)

    candidates = []
    for row in rows:
        labels = [row[col] for col in ("name_cn", "sporttery_name_cn", "name_en", "oddsfe_name_en") if col in team_cols and row[col]]
        if not all(is_senior_label(label) for label in labels):
            continue
        score = label_score(row, team_name, team_cols)
        current = str(row["team_id"]) == str(current_id)
        if english_anchor and not current:
            row_variants: set[str] = set()
            for col in EN_LABEL_COLUMNS:
                if col in team_cols and row[col]:
                    row_variants.update(en_variants(row[col]))
            if row_variants & english_anchor:
                score = max(score, 5)
        if score <= 0 and not current:
            continue
        team_type = text(row["team_type"]) if "team_type" in team_cols else ""
        national_bonus = 1 if team_type == "national" else 0
        samples = sample_count(conn, row["team_id"], match_date)
        sporttery_bonus = 1 if "sporttery_name_cn" in team_cols and text(row["sporttery_name_cn"]) == text(team_name) else 0
        # Country bonus: when league context implies a specific country, boost
        # candidates from that country and penalize candidates with a different
        # explicit country. "International"/empty country is neutral — many teams
        # have incorrect or missing country data, so only penalize clear mismatches.
        team_country = text(row["country"]) if "country" in team_cols else ""
        if expected_country and team_country == expected_country:
            country_bonus = 2
        elif expected_country and team_country and team_country not in ("International", "") and team_country != expected_country:
            country_bonus = -2  # Penalize clear country mismatch
        else:
            country_bonus = 0
        candidates.append(
            {
                "team_id": row["team_id"],
                "sample_count": samples,
                "label_score": score,
                "team_type": team_type,
                "sporttery_bonus": sporttery_bonus,
                "country_bonus": country_bonus,
                "current": current,
                "row": display_row(row, team_cols),
                "sort_key": (score, country_bonus, samples, national_bonus, sporttery_bonus, 1 if current else 0),
            }
        )

    if not candidates:
        return None
    candidates.sort(key=lambda item: item["sort_key"], reverse=True)
    best = candidates[0]
    current = next((item for item in candidates if item["current"]), None)
    current_samples = int(current["sample_count"]) if current else 0
    current_score = int(current["label_score"]) if current else 0

    # sample_advantage only applies when current team_id doesn't have an exact
    # label match. If current_id was set by unambiguous_label_match (exact label
    # match with no competing exact match), a higher-sample candidate with the
    # same label score shouldn't override it — those samples may come from
    # historical mis-assignments (e.g. Avaí #1248 has 106 matches but is the
    # wrong team because it was consistently mis-linked in the past).
    current_exact_match = current is not None and current_score >= 4
    sample_advantage = (
        not current_exact_match
        and int(best["sample_count"]) >= max(8, current_samples + 5)
    )
    label_rescue = (
        current_samples == 0
        and int(best["label_score"]) > current_score
        and int(best["sample_count"]) >= 8
    )
    # Mismatch override: when current team_id has zero label match (name is
    # completely different) but a candidate has an exact match, the current
    # assignment is almost certainly wrong regardless of sample count. E.g.
    # team 746 "流浪者" (Rangers, Scotland) was assigned to "兰格斯" (Rangers,
    # Chile) — different characters, zero label overlap. The 745 samples under
    # 746 are from historical mis-assignments, not evidence of correctness.
    mismatch_override = (
        current is not None
        and current_score == 0
        and int(best["label_score"]) >= 4
    )
    # Context mismatch override: when both best and current have exact label
    # matches (same name, different teams), but the current team's country
    # explicitly conflicts with the league's expected country while the best
    # team's country doesn't, override. E.g. "兰格斯" in 智利杯: current=746
    # (Scotland) vs best=136740 (International/neutral) — Scotland is clearly
    # wrong for a Chilean cup match.
    current_country = text(current["row"]["country"]) if current and "country" in current.get("row", {}) else ""
    best_country = text(best["row"]["country"]) if "country" in best.get("row", {}) else ""
    context_mismatch = (
        expected_country
        and current is not None
        and current_exact_match
        and int(best["label_score"]) >= 4
        and current_country not in ("", "International")
        and current_country != expected_country
        and (best_country == expected_country or best_country in ("", "International"))
    )
    # Unambiguous-label rescue: when current team_id is empty and the best
    # candidate has an exact label match (score >= 4) with no other candidate
    # also at score >= 4, accept it even with zero historical samples. Weak
    # prefix matches (score <= 3) don't count as ambiguity — "智利" (score=3)
    # shouldn't block "智利大学" (score=5) from being selected.
    exact_match_count = sum(1 for c in candidates if int(c["label_score"]) >= 4)
    unambiguous_label_match = (
        current_id in (None, "")
        and exact_match_count == 1
        and int(best["label_score"]) >= 4
    )
    should_update = (
        str(best["team_id"]) != str(current_id)
        and (sample_advantage or label_rescue or unambiguous_label_match or mismatch_override or context_mismatch)
    )
    return {
        **best,
        "current_sample_count": current_samples,
        "current_label_score": current_score,
        "candidate_count": len(candidates),
        "should_update": should_update,
        "candidates": [
            {
                "team_id": item["team_id"],
                "sample_count": item["sample_count"],
                "label_score": item["label_score"],
                "team_type": item["team_type"],
                "current": item["current"],
                "row": item["row"],
            }
            for item in candidates[:5]
        ],
    }


def ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lottery_team_id_repairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            lottery_match_id TEXT NOT NULL,
            side TEXT NOT NULL,
            team_name TEXT,
            old_team_id TEXT,
            new_team_id TEXT,
            source_json TEXT,
            applied INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
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


def upsert_mapping(conn: sqlite3.Connection, source_name: str, source_entity_id: str, team_name: str, canonical_id: Any) -> None:
    mapping_id = "map_" + stable_id("team", source_name, source_entity_id)
    conn.execute(
        """
        INSERT INTO source_entity_mappings (
            mapping_id, entity_type, canonical_id, source_name, source_entity_id,
            source_entity_name, confidence, status, updated_at
        )
        VALUES (?, 'team', ?, ?, ?, ?, 0.9, 'active', CURRENT_TIMESTAMP)
        ON CONFLICT(entity_type, source_name, source_entity_id) DO UPDATE SET
            canonical_id=excluded.canonical_id,
            source_entity_name=excluded.source_entity_name,
            confidence=excluded.confidence,
            status='active',
            updated_at=CURRENT_TIMESTAMP
        """,
        (mapping_id, str(canonical_id), source_name, source_entity_id, team_name),
    )


def backup_db(db_path: Path, backup_root: Path) -> Path:
    backup_dir = backup_root / "team_id_repairs"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_before_team_id_repair_{stamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def fetch_matches(conn: sqlite3.Connection, args: argparse.Namespace) -> List[sqlite3.Row]:
    ids = [item.strip() for item in str(args.ids or "").split(",") if item.strip()]
    where = ["1=1"]
    params: List[Any] = []
    if ids:
        where.append("lottery_match_id IN ({})".format(",".join(["?"] * len(ids))))
        params.extend(ids)
    if args.date_from:
        where.append("date(match_date) >= date(?)")
        params.append(args.date_from)
    if args.date_to:
        where.append("date(match_date) <= date(?)")
        params.append(args.date_to)
    if args.league and not args.all_leagues:
        where.append("league_name_cn = ?")
        params.append(args.league)
    return conn.execute(
        f"""
        SELECT lottery_match_id, match_num, match_date, home_team_cn, away_team_cn,
               home_team_id, away_team_id, league_name_cn
        FROM lottery_matches
        WHERE {' AND '.join(where)}
        ORDER BY date(match_date), beijing_time, lottery_match_id
        """,
        params,
    ).fetchall()


def plan_repairs(conn: sqlite3.Connection, rows: Sequence[sqlite3.Row]) -> List[Dict[str, Any]]:
    team_cols = columns(conn, "teams")
    changes: List[Dict[str, Any]] = []
    for row in rows:
        for side in ("home", "away"):
            name = row[f"{side}_team_cn"]
            old_id = row[f"{side}_team_id"]
            chosen = choose_canonical(conn, name, old_id, row["match_date"], team_cols, row["league_name_cn"])
            if not chosen or not chosen["should_update"]:
                continue
            changes.append(
                {
                    "lottery_match_id": row["lottery_match_id"],
                    "match_num": row["match_num"],
                    "teams": f"{row['home_team_cn']} vs {row['away_team_cn']}",
                    "side": side,
                    "team_name": name,
                    "old_team_id": old_id,
                    "new_team_id": chosen["team_id"],
                    "old_sample_count": chosen["current_sample_count"],
                    "new_sample_count": chosen["sample_count"],
                    "old_label_score": chosen["current_label_score"],
                    "new_label_score": chosen["label_score"],
                    "candidate_count": chosen["candidate_count"],
                    "candidates": chosen["candidates"],
                }
            )
    return changes


def apply_repairs(conn: sqlite3.Connection, changes: Sequence[Dict[str, Any]], run_id: str) -> None:
    ensure_tables(conn)
    for change in changes:
        side = change["side"]
        column = f"{side}_team_id"
        conn.execute(
            f"UPDATE lottery_matches SET {column}=?, updated_at=CURRENT_TIMESTAMP WHERE lottery_match_id=?",
            (change["new_team_id"], change["lottery_match_id"]),
        )
        upsert_mapping(conn, "sporttery_name", text(change["team_name"]), text(change["team_name"]), change["new_team_id"])
        upsert_mapping(
            conn,
            "lottery_match_team_ref",
            f"{change['lottery_match_id']}:{side}",
            text(change["team_name"]),
            change["new_team_id"],
        )
        conn.execute(
            """
            INSERT INTO lottery_team_id_repairs (
                run_id, lottery_match_id, side, team_name, old_team_id, new_team_id,
                source_json, applied
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                run_id,
                change["lottery_match_id"],
                side,
                change["team_name"],
                str(change["old_team_id"]),
                str(change["new_team_id"]),
                json.dumps({k: v for k, v in change.items() if k not in {"candidates"}}, ensure_ascii=False),
            ),
        )


def repair(args: argparse.Namespace) -> Dict[str, Any]:
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    conn = connect(db_path)
    try:
        if not table_exists(conn, "lottery_matches") or not table_exists(conn, "teams"):
            raise SystemExit("Required tables lottery_matches/teams are missing.")
        rows = fetch_matches(conn, args)
        changes = plan_repairs(conn, rows)
        backup_path = None
        if args.apply and changes and not args.no_backup:
            backup_path = backup_db(db_path, Path(args.backup_dir))
        run_id = f"team_ids_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        if args.apply and changes:
            apply_repairs(conn, changes, run_id)
            conn.commit()
        else:
            conn.rollback()
        return {
            "db": str(db_path),
            "mode": "apply" if args.apply else "dry_run",
            "date_from": args.date_from,
            "date_to": args.date_to,
            "league": None if args.all_leagues else args.league,
            "matches_scanned": len(rows),
            "changes": len(changes),
            "backup": str(backup_path) if backup_path else None,
            "preview": changes[: args.preview_limit],
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--ids", default="")
    parser.add_argument("--date-from", default="2026-06-13")
    parser.add_argument("--date-to", default="2026-06-23")
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--all-leagues", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--preview-limit", type=int, default=80)
    args = parser.parse_args()
    print(json.dumps(repair(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
