#!/usr/bin/env python3
"""Refresh player_status table using ESPN injuries and football-data.org squad data.

This script:
1. Fetches injury data from ESPN API for active leagues
2. Fetches squad data from football-data.org for major leagues
3. Updates player_status table with fresh injury/squad data
"""
import sys
import os
import sqlite3
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetchers.espn.get_lineups import get_league_injuries, LEAGUE_CODES
from fetchers.football_data_org.get_matches import get_team_detail


def refresh_espn_injuries(conn, leagues=None):
    """Fetch ESPN injury data and update player_status table."""
    if leagues is None:
        # Active leagues with likely injury data
        leagues = ["eng.1", "esp.1", "ger.1", "ita.1", "fra.1",
                   "uefa.champions", "uefa.europa", "usa.1", "bra.1"]

    total_injuries = 0
    updated_teams = set()

    for lg_code in leagues:
        try:
            data = get_league_injuries(lg_code)
            injuries = data.get("injuries", [])
            if not injuries:
                continue

            for inj in injuries:
                team_name = inj.get("team_name", "")
                player_name = inj.get("athlete_name", "")
                injury_type = inj.get("injury_type", "")
                status = inj.get("status", "")

                if not player_name or not team_name:
                    continue

                # Map ESPN status to our status
                status_map = {
                    "Out": "injured",
                    "Doubtful": "doubtful",
                    "Questionable": "doubtful",
                    "Probable": "available",
                    "Day To Day": "doubtful",
                }
                mapped_status = status_map.get(status, "injured" if "out" in status.lower() else "doubtful")

                # Find team_id from teams table
                team_id = _find_team_id(conn, team_name)
                if not team_id:
                    continue

                # Upsert player_status
                try:
                    conn.execute("""
                        INSERT INTO player_status (player_name, team_id, status, status_detail,
                                                   injury_type, source, updated_at)
                        VALUES (?, ?, ?, ?, ?, 'espn_api', ?)
                        ON CONFLICT(player_name, team_id) DO UPDATE SET
                            status = excluded.status,
                            status_detail = excluded.status_detail,
                            injury_type = excluded.injury_type,
                            source = excluded.source,
                            updated_at = excluded.updated_at
                    """, (player_name, team_id, mapped_status, status, injury_type,
                          datetime.now().isoformat()))
                    total_injuries += 1
                    updated_teams.add(team_id)
                except Exception:
                    pass

        except Exception as exc:
            print(f"  Error fetching {lg_code}: {exc}")
            continue

    conn.commit()
    return total_injuries, len(updated_teams)


def refresh_fdo_squads(conn, team_ids=None):
    """Fetch football-data.org squad data and update players table."""
    if team_ids is None:
        # Major league team IDs from football-data.org
        team_ids = [
            (57, "Arsenal"), (58, "Aston Villa"), (61, "Chelsea"),
            (64, "Liverpool"), (65, "Man City"), (66, "Man United"),
            (76, "Tottenham"), (73, "West Ham"),
            (86, "Real Madrid"), (81, "Barcelona"), (83, "Atletico Madrid"),
            (91, "Bayern"), (98, "Dortmund"),
            (99, "Inter"), (100, "Juventus"), (102, "AC Milan"),
            (524, "PSG"), (529, "Marseille"),
        ]

    total_players = 0
    updated_teams = 0

    for fd_id, name in team_ids:
        try:
            detail = get_team_detail(str(fd_id))
            squad = detail.get("squad", [])
            if not squad:
                print(f"  {name}: no squad data")
                time.sleep(8)
                continue

            # Find internal team_id
            team_id = _find_team_id(conn, name)
            if not team_id:
                continue

            # Update player_status: mark squad members as available
            for p in squad:
                player_name = p.get("name", "")
                position = p.get("position", "")
                if not player_name:
                    continue

                try:
                    conn.execute("""
                        INSERT INTO player_status (player_name, team_id, status, source, updated_at)
                        VALUES (?, ?, 'available', 'fdo_squad', ?)
                        ON CONFLICT(player_name, team_id) DO UPDATE SET
                            status = CASE
                                WHEN player_status.status IN ('injured', 'suspended') THEN player_status.status
                                ELSE 'available'
                            END,
                            updated_at = ?
                    """, (player_name, team_id, datetime.now().isoformat(),
                          datetime.now().isoformat()))
                    total_players += 1
                except Exception:
                    pass

            updated_teams += 1
            print(f"  {name}: {len(squad)} players")

        except Exception as exc:
            print(f"  Error fetching {name}: {exc}")
            continue

        time.sleep(8)  # Rate limit: 10 req/min on free tier

    conn.commit()
    return total_players, updated_teams


def _find_team_id(conn, team_name: str) -> int:
    """Find internal team_id from team name."""
    try:
        # Try exact match on name_en
        row = conn.execute(
            "SELECT team_id FROM teams WHERE name_en = ? LIMIT 1",
            (team_name,),
        ).fetchone()
        if row:
            return row[0]

        # Try partial match
        row = conn.execute(
            "SELECT team_id FROM teams WHERE name_en LIKE ? OR name_cn LIKE ? LIMIT 1",
            (f"%{team_name}%", f"%{team_name}%"),
        ).fetchone()
        if row:
            return row[0]
    except Exception:
        pass
    return None


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/football_v2.db"
    conn = sqlite3.connect(db_path)

    print("=== Refreshing player_status from ESPN injuries ===")
    injuries, injury_teams = refresh_espn_injuries(conn)
    print(f"  Updated: {injuries} injuries across {injury_teams} teams")

    print("\n=== Refreshing player_status from football-data.org squads ===")
    players, squad_teams = refresh_fdo_squads(conn)
    print(f"  Updated: {players} players across {squad_teams} teams")

    # Summary
    total = conn.execute("SELECT COUNT(*) FROM player_status").fetchone()[0]
    recent = conn.execute(
        "SELECT COUNT(*) FROM player_status WHERE updated_at > datetime('now', '-1 day')"
    ).fetchone()[0]
    print(f"\n=== Summary ===")
    print(f"  Total rows: {total}")
    print(f"  Updated in last 24h: {recent}")

    conn.close()
