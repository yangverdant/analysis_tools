"""
采集 2024-2025 和 2025-2026 赛季数据

Step 1: football_data_org — 五大联赛 matches + standings
Step 2: apifootball — 7联赛 standings + odds + predictions
"""

import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from fetchers.football_data_org.get_matches import get_league_matches, get_standings as fdo_standings
from fetchers.apifootball.get_data import get_fixtures, get_standings, get_match_odds, get_predictions
from fetchers.adapter.adapter import adapt
from fetchers.storage.crud import UnifiedStorage


FDO_LEAGUES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
}

API_LEAGUE_IDS = {
    39: "Premier League", 140: "La Liga", 135: "Serie A",
    78: "Bundesliga", 61: "Ligue 1",
    253: "Eliteserien", 307: "Allsvenskan",
}

SEASONS = ["2024", "2025"]


def collect_fdo():
    """football_data_org: 五大联赛 matches + standings"""
    storage = UnifiedStorage()
    print("=== football_data.org ===")

    for code, name in FDO_LEAGUES.items():
        for season in SEASONS:
            print(f"\n  {name} {season}:")

            try:
                raw = get_league_matches(league=code, season=season)
                if raw:
                    records = adapt("football_data_org", "get_matches", raw)
                    count = storage.upsert_match_data(records)
                    print(f"    matches: {len(raw)} → {count} stored")
                else:
                    print(f"    matches: empty")
            except Exception as e:
                print(f"    matches ERR: {str(e)[:80]}")
            time.sleep(6.5)

            try:
                raw = fdo_standings(league=code, season=season)
                if raw:
                    records = adapt("football_data_org", "get_standings", raw)
                    count = storage.upsert_match_data(records)
                    print(f"    standings: {len(raw)} → {count} stored")
                else:
                    print(f"    standings: empty")
            except Exception as e:
                print(f"    standings ERR: {str(e)[:80]}")
            time.sleep(6.5)

    _summary(storage)


def collect_api_fixtures():
    """apifootball: 按日期范围采集赛程（补充Eliteserien/Allsvenskan）"""
    storage = UnifiedStorage()
    print("\n=== apifootball: fixtures ===")

    from datetime import datetime, timedelta
    start = datetime(2024, 3, 1)
    end = datetime(2026, 5, 31)

    current = start
    total = 0
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        try:
            raw = get_fixtures(from_date=date_str, to_date=date_str)
            if raw:
                records = adapt("apifootball", "get_fixtures", raw)
                count = storage.upsert_match_data(records)
                if count > 0:
                    total += count
                    print(f"    {date_str}: {count} stored")
        except Exception as e:
            print(f"    {date_str} ERR: {str(e)[:60]}")

        current += timedelta(days=3)
        time.sleep(6.5)

    print(f"  Total fixtures: {total}")
    _summary(storage)


def collect_api_standings():
    """apifootball: standings"""
    storage = UnifiedStorage()
    print("\n=== apifootball: standings ===")

    for lid, name in API_LEAGUE_IDS.items():
        for season in SEASONS:
            print(f"  {name} ({lid}) {season}...")
            try:
                raw = get_standings(league=str(lid), season=season)
                if raw:
                    records = adapt("apifootball", "get_standings", raw)
                    count = storage.upsert_match_data(records)
                    print(f"    {len(raw)} → {count} stored")
                else:
                    print(f"    empty")
            except Exception as e:
                print(f"    ERR: {str(e)[:80]}")
            time.sleep(6.5)


def collect_api_odds():
    """apifootball: odds by date range"""
    storage = UnifiedStorage()
    print("\n=== apifootball: odds ===")

    from datetime import datetime, timedelta
    start = datetime(2024, 8, 1)
    end = datetime(2026, 5, 31)

    current = start
    total = 0
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        try:
            raw = get_match_odds(from_date=date_str, to_date=date_str)
            if raw:
                records = adapt("apifootball", "get_match_odds", raw)
                count = storage.upsert_match_data(records)
                if count > 0:
                    total += count
                    print(f"    {date_str}: {count} odds stored")
        except Exception as e:
            print(f"    {date_str} ERR: {str(e)[:60]}")

        current += timedelta(days=7)
        time.sleep(6.5)

    print(f"  Total odds: {total}")


def collect_api_predictions():
    """apifootball: predictions (per match_id)"""
    import sqlite3, json
    storage = UnifiedStorage()
    print("\n=== apifootball: predictions ===")

    conn = sqlite3.connect("d:/football_tools/data/unified_football.db")

    # Find matches without predictions
    need_pred = conn.execute("""
        SELECT md.match_key, json_extract(md.data_json, '$.match_id')
        FROM match_data md
        WHERE md.data_type='match' AND md.source='apifootball'
        AND md.match_key NOT IN (
            SELECT match_key FROM match_data WHERE data_type='prediction'
        )
        ORDER BY md.match_key DESC
        LIMIT 200
    """).fetchall()

    print(f"  Need predictions: {len(need_pred)} matches")

    ok = err = 0
    for mk, mid in need_pred:
        if not mid:
            continue
        try:
            raw = get_predictions(match_id=str(mid))
            if raw:
                records = adapt("apifootball", "get_predictions", [raw] if isinstance(raw, dict) else raw)
                count = storage.upsert_match_data(records)
                ok += 1
            else:
                err += 1
        except:
            err += 1
        time.sleep(6.5)

    conn.close()
    print(f"  Predictions: {ok} ok, {err} err")


def _summary(storage):
    conn = storage._conn()
    m = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    md = conn.execute("SELECT COUNT(*) FROM match_data").fetchone()[0]
    st = conn.execute("SELECT COUNT(*) FROM standings").fetchone()[0]
    fin = conn.execute("SELECT COUNT(*) FROM matches WHERE status='finished'").fetchone()[0]
    print(f"\n  Summary: {m} matches ({fin} finished), {md} match_data, {st} standings")

    breakdown = conn.execute("SELECT source, data_type, COUNT(*) FROM match_data GROUP BY source, data_type").fetchall()
    for b in breakdown:
        print(f"    {b[0]}/{b[1]}: {b[2]}")
    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("step", nargs="?", default="all",
                        choices=["fdo", "api_fixtures", "api_standings", "api_odds", "api_pred", "all"])
    args = parser.parse_args()

    if args.step == "fdo":
        collect_fdo()
    elif args.step == "api_fixtures":
        collect_api_fixtures()
    elif args.step == "api_standings":
        collect_api_standings()
    elif args.step == "api_odds":
        collect_api_odds()
    elif args.step == "api_pred":
        collect_api_predictions()
    elif args.step == "all":
        collect_fdo()
        collect_api_standings()
        collect_api_odds()
