"""
从 football-data.co.uk 批量采集五大联赛赔率+统计数据
免费公开CSV，包含B365/Pinnacle/Betfair等赔率、亚盘、大小球、收盘赔率
"""

import sys
import io
import csv
import sqlite3
import json
import time
import os
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'

from fetchers.common.team_names import normalize_team_name
from fetchers.common.match_key import make_match_key
from fetchers.storage.crud import UnifiedStorage

DB_PATH = "d:/football_tools/data/unified_football.db"

# football-data.co.uk CSV league codes
# Season format: 2425 = 2024-2025 season, 2324 = 2023-2024 etc.
LEAGUES = {
    "E0":  {"name": "Premier League",    "seasons": ["2324", "2425", "2526"]},
    "D1":  {"name": "Bundesliga",        "seasons": ["2324", "2425", "2526"]},
    "I1":  {"name": "Serie A",           "seasons": ["2324", "2425", "2526"]},
    "SP1": {"name": "LaLiga",            "seasons": ["2324", "2425", "2526"]},
    "F1":  {"name": "Ligue 1",           "seasons": ["2324", "2425", "2526"]},
    "E1":  {"name": "Championship",      "seasons": ["2324", "2425"]},
    "SP2": {"name": "LaLiga2",           "seasons": ["2324", "2425"]},
    "D2":  {"name": "Bundesliga 2",      "seasons": ["2324", "2425"]},
    "I2":  {"name": "Serie B",           "seasons": ["2324", "2425"]},
    "F2":  {"name": "Ligue 2",           "seasons": ["2324", "2425"]},
    "N1":  {"name": "Eredivisie",        "seasons": ["2324", "2425"]},
}

# Team name mapping: football-data.co.uk name → standard name
TEAM_MAP = {
    "Man United": "Manchester United",
    "Man City": "Manchester City",
    "Tottenham": "Tottenham",
    "West Ham": "West Ham",
    "West Brom": "West Bromwich Albion",
    "Wolves": "Wolverhampton",
    "Nottm Forest": "Nottingham Forest",
    "Sheffield Utd": "Sheffield United",
    "Leicester": "Leicester City",
    "Newcastle": "Newcastle",
    "Brighton": "Brighton",
    "Bournemouth": "Bournemouth",
    "Arsenal": "Arsenal",
    "Chelsea": "Chelsea",
    "Liverpool": "Liverpool",
    "Everton": "Everton",
    "Crystal Palace": "Crystal Palace",
    "Aston Villa": "Aston Villa",
    "Fulham": "Fulham",
    "Ipswich": "Ipswich Town",
    "Leeds": "Leeds United",
    "Burnley": "Burnley",
    "Luton": "Luton Town",
    "Brentford": "Brentford",
    "Southampton": "Southampton",
    "Sunderland": "Sunderland",
    "Bayern Munich": "Bayern Munich",
    "Borussia Dortmund": "Borussia Dortmund",
    "B Leverkusen": "Bayer Leverkusen",
    "Stuttgart": "Stuttgart",
    "Wolfsburg": "Wolfsburg",
    "Freiburg": "Freiburg",
    "Hoffenheim": "Hoffenheim",
    "Frankfurt": "Eintracht Frankfurt",
    "M'gladbach": "Monchengladbach",
    "Mainz": "Mainz 05",
    "Augsburg": "Augsburg",
    "Union Berlin": "Union Berlin",
    "Bochum": "Bochum",
    "Darmstadt": "Darmstadt 98",
    "Heidenheim": "Heidenheim",
    "St Pauli": "St Pauli",
    "Holstein Kiel": "Holstein Kiel",
    "Inter": "Inter",
    "Milan": "Milan",
    "Roma": "Roma",
    "Lazio": "Lazio",
    "Napoli": "Napoli",
    "Juventus": "Juventus",
    "Atalanta": "Atalanta",
    "Fiorentina": "Fiorentina",
    "Bologna": "Bologna",
    "Torino": "Torino",
    "Monza": "Monza",
    "Udinese": "Udinese",
    "Sassuolo": "Sassuolo",
    "Empoli": "Empoli",
    "Cagliari": "Cagliari",
    "Genoa": "Genoa",
    "Verona": "Verona",
    "Lecce": "Lecce",
    "Frosinone": "Frosinone",
    "Salernitana": "Salernitana",
    "Parma": "Parma",
    "Como": "Como",
    "Cremonese": "Cremonese",
    "Venezia": "Venezia",
    "Barcelona": "Barcelona",
    "Real Madrid": "Real Madrid",
    "Atletico Madrid": "Atletico Madrid",
    "Ath Bilbao": "Athletic Bilbao",
    "Sevilla": "Sevilla",
    "Betis": "Real Betis",
    "Villarreal": "Villarreal",
    "Sociedad": "Real Sociedad",
    "Celta": "Celta Vigo",
    "Valencia": "Valencia",
    "Mallorca": "Mallorca",
    "Getafe": "Getafe",
    "Osasuna": "Osasuna",
    "Alaves": "Alaves",
    "Las Palmas": "Las Palmas",
    "Cadiz": "Cadiz",
    "Granada": "Granada",
    "Espanyol": "Espanyol",
    "Leganes": "Leganes",
    "Almeria": "Almeria",
    "Girona": "Girona",
    "Huesca": "Huesca",
    "Elche": "Elche",
    "Valladolid": "Valladolid",
    "Eibar": "Eibar",
    "Andorra": "Andorra",
    "PSG": "Paris Saint-Germain",
    "Marseille": "Marseille",
    "Lyon": "Lyon",
    "Lille": "Lille",
    "Monaco": "Monaco",
    "Rennes": "Rennes",
    "Lens": "Lens",
    "Nantes": "Nantes",
    "Strasbourg": "Strasbourg",
    "Toulouse": "Toulouse",
    "Montpellier": "Montpellier",
    "Nice": "Nice",
    "Reims": "Reims",
    "Brest": "Brest",
    "Le Havre": "Le Havre",
    "Metz": "Metz",
    "Clermont": "Clermont Foot",
    "Lorient": "Lorient",
    "Ajaccio": "Ajaccio",
    "Troyes": "Troyes",
    "Auxerre": "Auxerre",
    "Angers": "Angers",
    "Saint-Etienne": "Saint-Etienne",
    "Dunkerque": "Dunkerque",
}


def _normalize_team(name: str) -> str:
    """先映射再normalize"""
    mapped = TEAM_MAP.get(name)
    if mapped:
        return normalize_team_name(mapped)
    return normalize_team_name(name)


def _parse_date(date_str: str) -> str:
    """Convert DD/MM/YYYY to YYYY-MM-DD"""
    if not date_str or '/' not in date_str:
        return ''
    parts = date_str.split('/')
    if len(parts) == 3:
        return '%s-%s-%s' % (parts[2], parts[1], parts[0])
    return date_str


def download_csv(league_code: str, season: str) -> list:
    """Download CSV from football-data.co.uk"""
    url = 'https://www.football-data.co.uk/mmz4281/%s/%s.csv' % (season, league_code)
    try:
        resp = requests.get(url, timeout=30, proxies={'http': None, 'https': None})
        if resp.status_code != 200:
            print('  HTTP %d for %s/%s' % (resp.status_code, season, league_code))
            return []
        text = resp.text.strip()
        if not text:
            return []
        reader = csv.DictReader(text.splitlines())
        rows = list(reader)
        print('  %s/%s: %d rows' % (season, league_code, len(rows)))
        return rows
    except Exception as e:
        print('  Error %s/%s: %s' % (season, league_code, str(e)[:60]))
        return []


def process_csv_rows(rows: list, league_name: str) -> int:
    """Process CSV rows and store odds in DB"""
    storage = UnifiedStorage()
    conn = storage._conn()
    ok = skip = err = 0

    for row in rows:
        try:
            home_raw = row.get('HomeTeam', '')
            away_raw = row.get('AwayTeam', '')
            date_raw = row.get('Date', '')
            if not home_raw or not away_raw or not date_raw:
                skip += 1
                continue

            date = _parse_date(date_raw)
            home_std = _normalize_team(home_raw)
            away_std = _normalize_team(away_raw)
            if not date or not home_std or not away_std:
                skip += 1
                continue

            mk = make_match_key(date, home_std, away_std)
            if not mk or '|' not in mk:
                skip += 1
                continue

            # Check for odds
            avg_h = row.get('AvgH')
            avg_d = row.get('AvgD')
            avg_a = row.get('AvgA')
            b365_h = row.get('B365H')
            b365_d = row.get('B365D')
            b365_a = row.get('B365A')
            ps_h = row.get('PSH')
            ps_d = row.get('PSD')
            ps_a = row.get('PSA')

            # If no odds at all, skip
            if not avg_h and not b365_h and not ps_h:
                skip += 1
                continue

            # Build odds JSON
            odds_json = {
                "league": league_name,
                "date": date,
                "home_team": home_std,
                "away_team": away_std,
                "home_team_original": home_raw,
                "away_team_original": away_raw,
            }

            # Average odds (best indicator)
            if avg_h and avg_d and avg_a:
                odds_json["avg_home_win"] = float(avg_h)
                odds_json["avg_draw"] = float(avg_d)
                odds_json["avg_away_win"] = float(avg_a)
                odds_json["home_win"] = float(avg_h)
                odds_json["draw"] = float(avg_d)
                odds_json["away_win"] = float(avg_a)
                odds_json["bookmaker"] = "Average (football-data.co.uk)"

            # B365 odds
            if b365_h and b365_d and b365_a:
                odds_json["b365_home_win"] = float(b365_h)
                odds_json["b365_draw"] = float(b365_d)
                odds_json["b365_away_win"] = float(b365_a)
                if not odds_json.get("home_win"):
                    odds_json["home_win"] = float(b365_h)
                    odds_json["draw"] = float(b365_d)
                    odds_json["away_win"] = float(b365_a)
                    odds_json["bookmaker"] = "Bet365"

            # Pinnacle odds
            if ps_h and ps_d and ps_a:
                odds_json["pinnacle_home_win"] = float(ps_h)
                odds_json["pinnacle_draw"] = float(ps_d)
                odds_json["pinnacle_away_win"] = float(ps_a)

            # Closing odds
            avg_ch = row.get('AvgCH')
            avg_cd = row.get('AvgCD')
            avg_ca = row.get('AvgCA')
            if avg_ch and avg_cd and avg_ca:
                odds_json["closing_avg_home_win"] = float(avg_ch)
                odds_json["closing_avg_draw"] = float(avg_cd)
                odds_json["closing_avg_away_win"] = float(avg_ca)

            # Score
            fthg = row.get('FTHG')
            ftag = row.get('FTAG')
            if fthg and ftag:
                odds_json["home_score"] = int(fthg)
                odds_json["away_score"] = int(ftag)

            # Over/Under 2.5
            avg_over = row.get('Avg>2.5')
            avg_under = row.get('Avg<2.5')
            if avg_over and avg_under:
                odds_json["avg_over_2_5"] = float(avg_over)
                odds_json["avg_under_2_5"] = float(avg_under)

            b365_over = row.get('B365>2.5')
            b365_under = row.get('B365<2.5')
            if b365_over and b365_under:
                odds_json["b365_over_2_5"] = float(b365_over)
                odds_json["b365_under_2_5"] = float(b365_under)

            # Asian Handicap
            ah_handicap = row.get('AHh')
            avg_ahh = row.get('AvgAHH')
            avg_aha = row.get('AvgAHA')
            if ah_handicap and avg_ahh and avg_aha:
                odds_json["ah_handicap"] = float(ah_handicap)
                odds_json["avg_ah_home"] = float(avg_ahh)
                odds_json["avg_ah_away"] = float(avg_aha)

            # Ensure match exists
            status = "finished" if (fthg and ftag) else "scheduled"
            conn.execute("""
                INSERT OR IGNORE INTO matches (match_key, date, home_team, away_team, league, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (mk, date, home_std, away_std, league_name, status))

            # Store odds (REPLACE to dedup)
            conn.execute("""
                INSERT OR REPLACE INTO match_data (match_key, source, data_type, data_json)
                VALUES (?, ?, ?, ?)
            """, (mk, "football-data-co-uk", "odds", json.dumps(odds_json, ensure_ascii=False)))

            ok += 1
        except Exception as e:
            err += 1
            if err <= 5:
                print('  ERR: %s' % str(e)[:60])

    conn.commit()
    conn.close()
    print('  完成: ok=%d err=%d skip=%d' % (ok, err, skip))
    return ok


def collect_all_odds():
    """采集所有联赛所有赛季赔率"""
    total_ok = 0
    for code, info in LEAGUES.items():
        print('\n=== %s (%s) ===' % (info["name"], code))
        for season in info["seasons"]:
            rows = download_csv(code, season)
            if rows:
                ok = process_csv_rows(rows, info["name"])
                total_ok += ok
            time.sleep(0.5)

    # Summary
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM match_data WHERE source='football-data-co-uk' AND data_type='odds'").fetchone()[0]
    by_lg = conn.execute("""
        SELECT json_extract(data_json, '$.league'), COUNT(*)
        FROM match_data WHERE source='football-data-co-uk' AND data_type='odds'
        GROUP BY json_extract(data_json, '$.league')
    """).fetchall()
    print('\n=== 汇总 ===')
    print('总赔率记录: %d' % total)
    for r in by_lg:
        print('  %s: %d' % (r[0], r[1]))

    # Combined odds coverage
    total_odds = conn.execute("""
        SELECT COUNT(DISTINCT match_key) FROM match_data
        WHERE data_type='odds' AND (source='odds_feed' OR source='football-data-co-uk')
    """).fetchone()[0]
    finished = conn.execute("SELECT COUNT(*) FROM matches WHERE status='finished'").fetchone()[0]
    print('有赔率的finished比赛: %d / %d = %.1f%%' % (total_odds, finished, 100.0*total_odds/finished))

    conn.close()


if __name__ == "__main__":
    collect_all_odds()