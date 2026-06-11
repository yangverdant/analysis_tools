"""
从 football_v2.db 迁移 2024-2025 和 2025-2026 赛季数据到 unified_football.db
"""

import sqlite3
import json
import sys
import io
from fetchers.common.team_names import normalize_team_name
from fetchers.common.league_names import normalize_league_name
from fetchers.common.match_key import make_match_key

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OLD_DB = "d:/football_tools/data/football_v2.db"
NEW_DB = "d:/football_tools/data/unified_football.db"

TARGET_LEAGUES = {3: "Allsvenskan", 7: "Bundesliga", 13: "Eliteserien",
                  21: "La Liga", 24: "Ligue 1", 27: "Premier League", 35: "Serie A"}


def migrate():
    old = sqlite3.connect(OLD_DB)
    new = sqlite3.connect(NEW_DB)

    # Get target season IDs
    seasons = old.execute("SELECT season_id, season_name, league_id FROM seasons").fetchall()
    target_sids = set()
    for sid, sn, lid in seasons:
        if lid not in TARGET_LEAGUES or not sn:
            continue
        if any(y in sn for y in ["2024", "2025", "2026"]):
            yr = int(sn[:4])
            if yr >= 2024:
                target_sids.add(sid)

    sid_ph = ','.join(str(x) for x in target_sids)
    lid_ph = ','.join(str(x) for x in TARGET_LEAGUES)
    print(f"Season IDs ({len(target_sids)}): {sorted(target_sids)}")

    # Caches
    teams = dict(old.execute("SELECT team_id, name_en FROM teams").fetchall())
    league_names = dict(old.execute("SELECT league_id, name_en FROM leagues").fetchall())
    season_names = dict(old.execute("SELECT season_id, season_name FROM seasons").fetchall())

    # ---- 1. Migrate matches + odds (from matches table) + xG ----
    rows = old.execute(f"""
        SELECT * FROM matches
        WHERE season_id IN ({sid_ph}) AND league_id IN ({lid_ph})
    """).fetchall()
    cols = [d[0] for d in old.description]

    match_count = 0
    data_count = 0
    odds_count = 0
    xg_count = 0
    match_id_to_mk = {}  # for odds table migration

    for r in rows:
        d = dict(zip(cols, r))
        htid = d.get("home_team_id")
        atid = d.get("away_team_id")
        ht_name = teams.get(htid, "")
        at_name = teams.get(atid, "")
        ht_std = normalize_team_name(ht_name)
        at_std = normalize_team_name(at_name)
        lg_std = normalize_league_name(league_names.get(d.get("league_id"), ""))
        date = d.get("match_date", "") or ""
        mk = make_match_key(date, ht_std, at_std)

        if not mk or "|" not in mk:
            continue

        # Match record
        status = d.get("status", "")
        try:
            new.execute("""
                INSERT OR IGNORE INTO matches (match_key, date, home_team, away_team, league, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (mk, date, ht_std, at_std, lg_std,
                  "finished" if status == "finished" else "scheduled"))
            match_count += 1
        except:
            continue

        match_id_to_mk[d.get("match_id")] = mk

        # Match data
        match_json = {
            "home_team": ht_std, "home_team_original": ht_name,
            "away_team": at_std, "away_team_original": at_name,
            "home_score": str(d.get("home_goals", "")) if d.get("home_goals") is not None else None,
            "away_score": str(d.get("away_goals", "")) if d.get("away_goals") is not None else None,
            "date": date, "time": d.get("match_time", "") or "",
            "league": lg_std, "league_original": league_names.get(d.get("league_id"), ""),
            "round": d.get("round_num"), "venue": d.get("venue"), "status": status,
            "season": season_names.get(d.get("season_id"), ""),
        }
        try:
            new.execute("""
                INSERT OR IGNORE INTO match_data (match_key, source, data_type, data_json)
                VALUES (?, ?, ?, ?)
            """, (mk, "football_v2", "match", json.dumps(match_json, ensure_ascii=False)))
            data_count += 1
        except:
            pass

        # Odds from matches table (b365/avg/ps columns)
        best_h = d.get("odds_b365_home") or d.get("avg_home") or d.get("ps_home")
        best_d = d.get("odds_b365_draw") or d.get("avg_draw") or d.get("ps_draw")
        best_a = d.get("odds_b365_away") or d.get("avg_away") or d.get("ps_away")
        if best_h and best_d and best_a:
            odds_json = {
                "home_win": best_h, "draw": best_d, "away_win": best_a,
                "home_win_closing": d.get("odds_b365_c_home") or d.get("avg_c_home"),
                "draw_closing": d.get("odds_b365_c_draw") or d.get("avg_c_draw"),
                "away_win_closing": d.get("odds_b365_c_away") or d.get("avg_c_away"),
                "over_2_5": d.get("b365_over_2_5"), "under_2_5": d.get("b365_under_2_5"),
                "handicap": d.get("asian_handicap"),
                "ah_home": d.get("b365_ah_home"), "ah_away": d.get("b365_ah_away"),
                "bookmaker": "bet365",
            }
            try:
                new.execute("""
                    INSERT OR IGNORE INTO match_data (match_key, source, data_type, data_json)
                    VALUES (?, ?, ?, ?)
                """, (mk, "football_v2_odds", "odds", json.dumps(odds_json, ensure_ascii=False)))
                odds_count += 1
            except:
                pass

        # xG
        hxg = d.get("home_xg") or d.get("h_xg")
        axg = d.get("away_xg") or d.get("a_xg")
        if hxg or axg:
            xg_json = {"home_xg": hxg, "away_xg": axg}
            try:
                new.execute("""
                    INSERT OR IGNORE INTO match_data (match_key, source, data_type, data_json)
                    VALUES (?, ?, ?, ?)
                """, (mk, "football_v2", "prediction", json.dumps(xg_json, ensure_ascii=False)))
                xg_count += 1
            except:
                pass

    print(f"Matches: {match_count}, match_data: {data_count}, odds: {odds_count}, xG: {xg_count}")

    # ---- 2. Migrate standings ----
    stand_rows = old.execute(f"""
        SELECT * FROM standings
        WHERE league_id IN ({lid_ph}) AND season_id IN ({sid_ph})
    """).fetchall()
    if stand_rows:
        scols = [d[0] for d in old.description]
    else:
        scols = []

    standing_count = 0
    for r in stand_rows:
        d = dict(zip(scols, r))
        team_name = teams.get(d.get("team_id"), "")
        team_std = normalize_team_name(team_name)
        lg_std = normalize_league_name(league_names.get(d.get("league_id"), ""))
        sn = season_names.get(d.get("season_id"), "")

        st_json = {
            "position": d.get("position"), "team": team_std, "team_original": team_name,
            "played": d.get("played"), "won": d.get("won"), "drawn": d.get("drawn"),
            "lost": d.get("lost"), "goals_for": d.get("goals_for"),
            "goals_against": d.get("goals_against"), "goal_diff": d.get("goal_diff"),
            "points": d.get("points"),
            "home_played": d.get("home_played"), "home_won": d.get("home_won"),
            "home_drawn": d.get("home_drawn"), "home_lost": d.get("home_lost"),
            "home_goals_for": d.get("home_goals_for"), "home_goals_against": d.get("home_goals_against"),
            "away_played": d.get("away_played"), "away_won": d.get("away_won"),
            "away_drawn": d.get("away_drawn"), "away_lost": d.get("away_lost"),
            "away_goals_for": d.get("away_goals_for"), "away_goals_against": d.get("away_goals_against"),
            "league": lg_std, "season": sn,
        }
        try:
            new.execute("""
                INSERT OR IGNORE INTO standings (league, team, source, data_json)
                VALUES (?, ?, ?, ?)
            """, (lg_std, team_std, "football_v2", json.dumps(st_json, ensure_ascii=False)))
            standing_count += 1
        except:
            pass

    print(f"Standings: {standing_count}")

    # ---- 3. Migrate injuries ----
    try:
        inj_rows = old.execute(f"""
            SELECT * FROM player_status
            WHERE league_id IN ({lid_ph})
        """).fetchall()
        if inj_rows:
            pcols = [d[0] for d in old.description]
        else:
            pcols = []
    except:
        inj_rows = []
        pcols = []

    injury_count = 0
    for r in inj_rows:
        d = dict(zip(pcols, r))
        team_name = teams.get(d.get("team_id"), "")
        team_std = normalize_team_name(str(team_name))
        player_name = d.get("player_name") or d.get("player") or ""
        if not team_std or not player_name:
            continue

        inj_json = {
            "player_name": player_name, "team": team_std,
            "team_original": str(team_name),
            "reason": d.get("reason", ""), "type": d.get("type", ""),
            "status": d.get("status", ""),
        }
        try:
            new.execute("""
                INSERT OR IGNORE INTO injuries (team_standard, player_name, source, data_json)
                VALUES (?, ?, ?, ?)
            """, (team_std, player_name, "football_v2", json.dumps(inj_json, ensure_ascii=False)))
            injury_count += 1
        except:
            pass

    print(f"Injuries: {injury_count}")

    # ---- 4. Comprehensive odds from match_odds table ----
    try:
        odds_rows = old.execute(f"""
            SELECT o.* FROM match_odds o
            JOIN matches m ON o.match_id = m.match_id
            WHERE m.season_id IN ({sid_ph}) AND m.league_id IN ({lid_ph})
        """).fetchall()
        if odds_rows:
            ocols = [d[0] for d in old.description]
        else:
            ocols = []
    except:
        odds_rows = []
        ocols = []

    extra_odds = 0
    for r in odds_rows:
        d = dict(zip(ocols, r))
        mk = match_id_to_mk.get(d.get("match_id"))
        if not mk:
            continue

        odds_json = {}
        for bk in ["b365", "avg", "ps", "bw", "iw", "mb", "vc", "wh"]:
            for tp in ["home", "draw", "away"]:
                key = f"{bk}_{tp}"
                val = d.get(key)
                if val:
                    odds_json[key] = val
            for tp in ["c_home", "c_draw", "c_away"]:
                key = f"{bk}_{tp}"
                val = d.get(key)
                if val:
                    odds_json[key] = val

        # Asian handicap
        if d.get("asian_handicap"):
            odds_json["handicap"] = d["asian_handicap"]
        for bk in ["b365", "avg"]:
            for side in ["ah_home", "ah_away"]:
                key = f"{bk}_{side}"
                val = d.get(key)
                if val:
                    odds_json[key] = val

        # Over/under
        for bk in ["b365", "avg"]:
            for tp in ["over_2_5", "under_2_5", "over_2_5_c", "under_2_5_c"]:
                key = f"{bk}_{tp}"
                val = d.get(key)
                if val:
                    odds_json[key] = val

        if odds_json:
            try:
                new.execute("DELETE FROM match_data WHERE match_key=? AND source='football_v2_odds' AND data_type='odds'", (mk,))
                new.execute("""
                    INSERT INTO match_data (match_key, source, data_type, data_json)
                    VALUES (?, ?, ?, ?)
                """, (mk, "football_v2_odds", "odds", json.dumps(odds_json, ensure_ascii=False)))
                extra_odds += 1
            except:
                pass

    print(f"Comprehensive odds from match_odds table: {extra_odds}")

    new.commit()

    # ---- Verify ----
    m_cnt = new.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    md_cnt = new.execute("SELECT COUNT(*) FROM match_data").fetchone()[0]
    st_cnt = new.execute("SELECT COUNT(*) FROM standings").fetchone()[0]
    inj_cnt = new.execute("SELECT COUNT(*) FROM injuries").fetchone()[0]

    print(f"\n=== Final ===")
    print(f"  matches: {m_cnt}")
    print(f"  match_data: {md_cnt}")
    print(f"  standings: {st_cnt}")
    print(f"  injuries: {inj_cnt}")

    breakdown = new.execute("SELECT source, data_type, COUNT(*) FROM match_data GROUP BY source, data_type").fetchall()
    print(f"\n  match_data breakdown:")
    for b in breakdown:
        print(f"    {b[0]}/{b[1]}: {b[2]}")

    finished = new.execute("SELECT COUNT(*) FROM matches WHERE status='finished'").fetchone()[0]
    with_odds = new.execute("SELECT COUNT(DISTINCT match_key) FROM match_data WHERE data_type='odds'").fetchone()[0]
    with_xg = new.execute("SELECT COUNT(DISTINCT match_key) FROM match_data WHERE data_type='prediction'").fetchone()[0]
    print(f"\n  Finished: {finished}")
    print(f"  With odds: {with_odds}")
    print(f"  With xG/pred: {with_xg}")

    # By league
    by_lg = new.execute("SELECT league, COUNT(*) FROM matches GROUP BY league ORDER BY COUNT(*) DESC").fetchall()
    print(f"\n  By league:")
    for bl in by_lg:
        print(f"    {bl[0]}: {bl[1]}")

    new.close()
    old.close()
    print("\nDone!")


if __name__ == "__main__":
    migrate()