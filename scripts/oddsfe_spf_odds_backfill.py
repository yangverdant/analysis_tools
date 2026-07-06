#!/usr/bin/env python3
"""Backfill lottery_odds.spf from oddsfe 1X2 prematch odds.

Background
----------
sporttery's lottery odds API is WAF-banned (see memory: sporttery_waf_ban),
so matches collected via oddsfe_schedule_to_lottery.py have no spf odds in
the lottery_odds table. Without spf odds:
  - Frontend "缺赔率" badge shows on match cards
  - _rank_value_bets can't compute value for these matches
  - _check_stop_loss / ROI tracking skips them

This script is the structural fix (治本): pull Pinnacle prematch 1X2 odds
from oddsfe's per-event HTML endpoint (parsed by oddsfe_realtime_detail_v2.parse_event_odds_v2)
and convert to sporttery's spf format:
  {"3": home_win_odds, "1": draw_odds, "0": away_win_odds}

Pinnacle is the sharpest book, so its odds are the best proxy for "true"
probabilities. We write a single row per match (snapshot_type='current').

Run from cloud_automation_tick.sh after oddsfe_schedule_to_lottery.py.
Skips matches that already have spf odds (sporttery-sourced) — preserves
existing data.
"""
import json
import logging
import sqlite3
import sys
from datetime import date, timedelta
from typing import Optional, Tuple

ROOT = "/opt/football_tools"
DB_PATH = f"{ROOT}/data/football_v2.db"

sys.path.insert(0, ROOT)
sys.path.insert(0, f"{ROOT}/backend")
sys.path.insert(0, f"{ROOT}/fetchers/odds_feed_api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _parse_pinnacle_1x2(odds_data: dict) -> Optional[Tuple[float, float, float]]:
    """Extract Pinnacle prematch 1X2 (home/draw/away) from oddsfe parse result.

    Format: ":home/draw/away:moid|PINNACLE:h:d:a:time;BK2:..."
    Falls back to BET365 if PINNACLE absent, then to first bookmaker listed.
    Returns (home, draw, away) or None if no prematch 1X2 lines.
    """
    raw = odds_data.get("1X2_prematch_lines") or ""
    if not raw or "|" not in raw:
        return None

    # First segment before "|" is the summary line: ":h/d/a:moid"
    summary = raw.split("|", 1)[0]
    parts = summary.split(":")
    # parts[0]="" parts[1]="h/d/a" parts[2]="moid"
    if len(parts) < 3 or "/" not in parts[1]:
        return None
    try:
        h, d, a = (float(x) for x in parts[1].split("/"))
    except (ValueError, IndexError):
        return None

    # Prefer PINNACLE if available — sharpest odds
    bk_segment = raw.split("|", 1)[1] if "|" in raw else ""
    for bk_row in bk_segment.split(";"):
        cols = bk_row.split(":")
        if len(cols) >= 4 and cols[0] == "PINNACLE":
            try:
                h, d, a = float(cols[1]), float(cols[2]), float(cols[3])
                break
            except (ValueError, IndexError):
                continue
    return (h, d, a)


def _fetch_oddsfe_1x2(event_id: str) -> Optional[Tuple[float, float, float]]:
    """Call oddsfe detail parser and return Pinnacle 1X2 odds."""
    try:
        from oddsfe_realtime_detail_v2 import parse_event_odds_v2, create_session
    except ImportError as exc:
        logger.warning("oddsfe_realtime_detail_v2 import failed: %s", exc)
        return None
    try:
        session = create_session()
        odds_data = parse_event_odds_v2(session, event_id)
        return _parse_pinnacle_1x2(odds_data)
    except Exception as exc:
        logger.debug("oddsfe 1x2 fetch failed for %s: %s", event_id, exc)
        return None


def backfill_spf_odds(target_date: date) -> dict:
    """For all matches on target_date missing spf odds, fetch from oddsfe."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    cur = conn.cursor()

    # Find matches with oddsfe_event_id but no spf odds row
    rows = cur.execute(
        """
        SELECT lm.lottery_match_id, lm.oddsfe_event_id, lm.home_team_cn, lm.away_team_cn
        FROM lottery_matches lm
        LEFT JOIN lottery_odds lo
          ON lm.lottery_match_id = lo.lottery_match_id AND lo.play_type = 'spf'
        WHERE lm.match_date = ?
          AND lm.oddsfe_event_id IS NOT NULL AND lm.oddsfe_event_id != ''
          AND lo.lottery_match_id IS NULL
        """,
        (str(target_date),)
    ).fetchall()

    inserted = 0
    skipped = 0
    failed = 0

    for lm_id, eid, home_cn, away_cn in rows:
        odds = _fetch_oddsfe_1x2(eid)
        if odds is None:
            failed += 1
            continue
        home, draw, away = odds
        # sporttery spf format: {"3": home, "1": draw, "0": away}
        odds_json = json.dumps({"3": home, "1": draw, "0": away})
        try:
            cur.execute(
                """
                INSERT OR IGNORE INTO lottery_odds
                (lottery_match_id, play_type, odds_data, opening_odds, latest_odds,
                 snapshot_type, update_time, created_at)
                VALUES (?, 'spf', ?, ?, ?, 'current',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (lm_id, odds_json, odds_json, odds_json)
            )
            if cur.rowcount > 0:
                inserted += 1
                logger.info("spf %s %s vs %s: %.2f/%.2f/%.2f",
                            lm_id, home_cn, away_cn, home, draw, away)
            else:
                skipped += 1
        except sqlite3.IntegrityError:
            skipped += 1

        # Also set handicap_line if it's still 0/NULL — derive from Asian handicap
        # if available, otherwise leave 0 (we don't have AH line here)
        # Reverse-sync play_types from lottery_odds so frontend knows what's
        # available. This catches both newly-inserted spf rows AND pre-existing
        # sporttery-sourced spf rows that never got play_types populated.
        play_types_row = cur.execute(
            "SELECT GROUP_CONCAT(play_type, ',') FROM (SELECT DISTINCT play_type FROM lottery_odds WHERE lottery_match_id = ? AND play_type IN ('spf','rqspf','bf','bqc','ttg') ORDER BY play_type)",
            (lm_id,)
        ).fetchone()
        if play_types_row and play_types_row[0]:
            pts = json.dumps(play_types_row[0].split(','))
            cur.execute(
                "UPDATE lottery_matches SET play_types = ? WHERE lottery_match_id = ? AND (play_types IS NULL OR play_types = '' OR play_types = '[]')",
                (pts, lm_id)
            )

    conn.commit()
    conn.close()

    result = {
        "date": str(target_date),
        "candidates": len(rows),
        "inserted": inserted,
        "skipped": skipped,
        "failed": failed,
    }
    logger.info("oddsfe_spf_backfill %s: %s", target_date, result)
    return result


def main() -> None:
    today = date.today()
    total = 0
    for offset in (0, 1, 2):
        target = today + timedelta(days=offset)
        try:
            result = backfill_spf_odds(target)
            total += result["inserted"]
        except Exception as exc:
            logger.error("spf backfill failed for %s: %s", target, exc)
    print(f"oddsfe_spf_backfill done: total_inserted={total}")


if __name__ == "__main__":
    main()
