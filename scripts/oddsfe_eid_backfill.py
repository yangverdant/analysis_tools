#!/usr/bin/env python3
"""Backfill missing oddsfe_event_id for existing lottery_matches by team-name matching.

Used to repair sporttery-sourced rows that never had an oddsfe_event_id, so that
_supplement_results_from_oddsfe can backfill FT/HT/BQC for them.

Matching strategy (3 layers, in order):
1. Direct EN match via teams table (name_cn -> name_en)
2. Reverse: call _cn_team_name on oddsfe team_home_name, compare to lottery_matches.home_team_cn
3. Normalized fuzzy match (lowercase, strip suffixes, first 2 CJK chars)

Run manually or from cloud_automation_tick.sh after oddsfe_schedule_to_lottery.py.
"""
import logging
import re
import sqlite3
import sys
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

ROOT = "/opt/football_tools"
DB_PATH = f"{ROOT}/data/football_v2.db"

sys.path.insert(0, ROOT)
sys.path.insert(0, f"{ROOT}/backend")
sys.path.insert(0, f"{ROOT}/scripts")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"\s+(fc|sk|hd|afc|cf|sc)\b", " ", s)
    s = re.sub(r"\b(fc|sk|hd|afc|cf|sc)\s+", " ", s)
    s = s.replace("football club", "").replace("football", "")
    s = s.replace("hyundai", "").replace("sangmu", "").replace("citizen", "")
    s = s.replace("united", "").replace("fc", "").replace("sk", "").replace("hd", "")
    s = re.sub(r"[^a-z一-鿿]", "", s)
    return s


def _first_cjk(name: str, n: int = 2) -> str:
    """First n CJK characters of a name."""
    out = []
    for ch in (name or ""):
        if "一" <= ch <= "鿿":
            out.append(ch)
            if len(out) >= n:
                break
    return "".join(out)


def _build_team_index(events: List[Dict]) -> Dict[str, List[Tuple[Dict, str]]]:
    """Build normalized-team-name -> [(event, side)] index."""
    idx: Dict[str, List[Tuple[Dict, str]]] = {}
    for ev in events:
        eh = (ev.get("team_home_name") or "").strip()
        ea = (ev.get("team_away_name") or "").strip()
        if not eh or not ea:
            continue
        for name, side in ((eh, "home"), (ea, "away")):
            for key in (_normalize(name), _first_cjk(name, 2)):
                if key:
                    idx.setdefault(key, []).append((ev, side))
            # Also try first token of EN name
            tokens = re.split(r"[\s\-]+", name)
            if tokens and tokens[0]:
                first = _normalize(tokens[0])
                if first and first != _normalize(name):
                    idx.setdefault(first, []).append((ev, side))
    return idx


def _learn_en_to_cn_map(conn: sqlite3.Connection, schedule_by_date: Dict[str, List[Dict]]) -> Dict[str, str]:
    """Learn EN->CN team name mapping from existing lottery_matches rows that have oddsfe_event_id.

    For each (lm.home_team_cn, lm.away_team_cn, lm.oddsfe_event_id), look up the event
    in the schedule and pair the oddsfe EN name with the lottery CN name.
    """
    en_to_cn: Dict[str, str] = {}
    for ds, events in schedule_by_date.items():
        rows = conn.execute(
            "SELECT home_team_cn, away_team_cn, oddsfe_event_id FROM lottery_matches "
            "WHERE match_date=? AND oddsfe_event_id IS NOT NULL",
            (ds,)
        ).fetchall()
        if not rows:
            continue
        eid_to_ev = {str(e.get("event_id")): e for e in events}
        for home_cn, away_cn, eid in rows:
            e = eid_to_ev.get(str(eid))
            if not e:
                continue
            eh = e.get("team_home_name","")
            ea = e.get("team_away_name","")
            if home_cn and eh and home_cn != eh:
                en_to_cn.setdefault(eh, home_cn)
            if away_cn and ea and away_cn != ea:
                en_to_cn.setdefault(ea, away_cn)
    return en_to_cn


def backfill_one_date(target_date_str: str, conn: sqlite3.Connection,
                       schedule_by_date: Dict[str, List[Dict]],
                       en_to_cn_learned: Dict[str, str]) -> Tuple[int, int]:
    """Backfill oddsfe_event_id for matches on target_date. Returns (updated, not_found)."""
    rows = conn.execute(
        """SELECT lottery_match_id, home_team_cn, away_team_cn, league_name_cn
           FROM lottery_matches
           WHERE oddsfe_event_id IS NULL
             AND match_date = ?
             AND home_team_cn IS NOT NULL AND away_team_cn IS NOT NULL""",
        (target_date_str,)
    ).fetchall()
    if not rows:
        return 0, 0

    events = schedule_by_date.get(target_date_str, [])
    if not events:
        return 0, len(rows)

    # Build CN-name -> oddsfe event reverse index, using:
    # 1. teams table (via _cn_team_name)
    # 2. learned EN->CN map from historical lottery_matches with oddsfe_event_id
    from oddsfe_schedule_to_lottery import _cn_team_name, _resolve_league_cn
    reverse_idx: Dict[str, List[Tuple[Dict, str]]] = {}
    for ev in events:
        eh = (ev.get("team_home_name") or "").strip()
        ea = (ev.get("team_away_name") or "").strip()
        if not eh or not ea:
            continue
        eh_cn = _cn_team_name(conn, eh)
        ea_cn = _cn_team_name(conn, ea)
        # Override with learned mapping if teams table gave a NULL/EN result
        if eh in en_to_cn_learned:
            eh_cn = en_to_cn_learned[eh]
        if ea in en_to_cn_learned:
            ea_cn = en_to_cn_learned[ea]
        for cn_name, side in ((eh_cn, "home"), (ea_cn, "away")):
            if cn_name:
                reverse_idx.setdefault(cn_name, []).append((ev, side))

    # Also build normalized EN index
    norm_idx = _build_team_index(events)

    updated = 0
    not_found = 0
    for lm_id, home_cn, away_cn, league_cn in rows:
        found_ev: Optional[Dict] = None

        home_cn_first2 = _first_cjk(home_cn, 2)
        away_cn_first2 = _first_cjk(away_cn, 2)

        # Layer 1: match by CN name (full or first-2-CJK) against reverse_idx
        # Trust home-side uniqueness within a single day's schedule.
        # If home matches exactly one event, accept it (away match is a sanity check,
        # not a hard requirement — team name CN/EN discrepancies are common).
        home_candidates: List[Tuple[Dict, str]] = []
        for home_key in (home_cn, home_cn_first2):
            if not home_key:
                continue
            for ev, side in reverse_idx.get(home_key, []):
                if ev not in [c[0] for c in home_candidates]:
                    home_candidates.append((ev, side))

        # Filter home_candidates by away-side sanity check (soft match)
        if home_candidates:
            filtered_candidates = []
            for ev, side in home_candidates:
                other_team_en = ev.get("team_away_name","") if side == "home" else ev.get("team_home_name","")
                other_cn = _cn_team_name(conn, other_team_en)
                if other_team_en in en_to_cn_learned:
                    other_cn = en_to_cn_learned[other_team_en]
                other_first2 = _first_cjk(other_cn, 2)
                # Soft match: CN equal, first-2-CJK equal, or away first-2-CJK matches
                # the event's other-side first-2-CJK
                if (other_cn == away_cn or other_cn == away_cn_first2 or
                    (away_cn_first2 and other_first2 == away_cn_first2)):
                    filtered_candidates.append((ev, side))
            # If strict filter found matches, use them; else fall back to all home candidates
            # (when away team CN is missing/EN in teams table, soft match fails — trust home alone
            # if there's only one candidate)
            if filtered_candidates:
                home_candidates = filtered_candidates
            elif len(home_candidates) > 1:
                home_candidates = []  # ambiguous, don't guess

        if home_candidates:
            found_ev = home_candidates[0][0]

        # Layer 2: normalized fuzzy match
        if found_ev is None:
            home_cands = {_normalize(home_cn), _first_cjk(home_cn, 2),
                          _normalize(_first_cjk(home_cn, 2))}
            away_cands = {_normalize(away_cn), _first_cjk(away_cn, 2),
                          _normalize(_first_cjk(away_cn, 2))}
            for hc in home_cands:
                if not hc or hc not in norm_idx:
                    continue
                for ev, side in norm_idx[hc]:
                    other = (ev.get("team_away_name","") if side == "home"
                             else ev.get("team_home_name",""))
                    other_norm = _normalize(other)
                    other_first = _first_cjk(other, 2)
                    for ac in away_cands:
                        if (ac and (ac == other_norm or ac in other_norm or
                                    other_norm in ac or
                                    ac == other_first or ac in other_first or
                                    other_first in ac)):
                            found_ev = ev
                            break
                    if found_ev:
                        break
                if found_ev:
                    break

        if found_ev:
            eid = str(found_ev.get("event_id") or "")
            if not eid:
                not_found += 1
                continue
            t = found_ev.get("tournament_name","")
            c = found_ev.get("category_name","")
            resolved = _resolve_league_cn(t, c)
            league_to_set = resolved if resolved and (not league_cn or
                             league_cn not in __import__("oddsfe_schedule_to_lottery").LEAGUE_WHITELIST) else league_cn
            # Also sync beijing_time/match_date/match_time from oddsfe event_start_at.
            # sporttery-era rows often carry wrong times (sporttery used CN local
            # times that drifted from oddsfe's UTC start). Without this, the row
            # keeps the stale time even after we pair it with the authoritative eid,
            # which surfaces as "duplicate" matches with wrong kickoff times.
            from oddsfe_schedule_to_lottery import _to_beijing_time
            start_at = found_ev.get("event_start_at") or ""
            bj = _to_beijing_time(start_at)
            if bj:
                new_date = bj[:10]
                new_time = bj[11:19]
                conn.execute(
                    "UPDATE lottery_matches SET oddsfe_event_id=?, league_name_cn=?, "
                    "beijing_time=COALESCE(?, beijing_time), "
                    "match_date=COALESCE(?, match_date), "
                    "match_time=COALESCE(?, match_time), "
                    "updated_at=CURRENT_TIMESTAMP WHERE lottery_match_id=?",
                    (eid, league_to_set, bj, new_date, new_time, lm_id)
                )
            else:
                conn.execute(
                    "UPDATE lottery_matches SET oddsfe_event_id=?, league_name_cn=?, "
                    "updated_at=CURRENT_TIMESTAMP WHERE lottery_match_id=?",
                    (eid, league_to_set, lm_id)
                )
            updated += 1
        else:
            not_found += 1

    return updated, not_found


def main() -> None:
    from backend.app.lottery.services.sync_service import _oddsfe_fetch_schedule

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")

    today = date.today()
    # Fetch wider window for learning (30 days) than for backfill (7 days),
    # because historical lottery_matches rows gained oddsfe_event_id only recently.
    schedule_by_date: Dict[str, List[Dict]] = {}
    for offset in range(-30, 2):
        d = today + timedelta(days=offset)
        ds = d.strftime("%Y-%m-%d")
        try:
            schedule_by_date[ds] = _oddsfe_fetch_schedule(ds)
        except Exception as exc:
            logger.warning("fetch %s failed: %s", ds, exc)

    total_updated = 0
    total_not_found = 0

    # Learn EN->CN team-name mapping from historical rows that already have eid
    en_to_cn_learned = _learn_en_to_cn_map(conn, schedule_by_date)
    logger.info("learned %d EN->CN team name mappings", len(en_to_cn_learned))

    for offset in range(-7, 2):
        d = today + timedelta(days=offset)
        ds = d.strftime("%Y-%m-%d")
        if ds not in schedule_by_date:
            continue
        updated, not_found = backfill_one_date(ds, conn, schedule_by_date, en_to_cn_learned)
        if updated or not_found:
            logger.info("backfill %s: updated=%d, not_found=%d", ds, updated, not_found)
            total_updated += updated
            total_not_found += not_found

    conn.commit()
    conn.close()
    if total_updated:
        print(f"oddsfe_eid_backfill done: total_updated={total_updated}, not_found={total_not_found}")


if __name__ == "__main__":
    main()
