"""
football-data.org API 数据同步工具
免费层: 10 requests/minute, 12个TIER_ONE赛事
数据: 比赛、积分榜、射手榜、球队阵容
"""

import requests
import time
import csv
import json
import os
from pathlib import Path
from datetime import datetime

API_TOKEN = "944e431594bf477fa85d24fa04d9c2fe"
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_TOKEN}
REQUEST_INTERVAL = 7  # seconds between requests (safe for 10/min)

# TIER_ONE competitions available on free tier
COMPETITIONS = {
    "PL": {"name": "premier_league", "zh": "英超"},
    "PD": {"name": "la_liga", "zh": "西甲"},
    "BL1": {"name": "bundesliga", "zh": "德甲"},
    "SA": {"name": "serie_a", "zh": "意甲"},
    "FL1": {"name": "ligue_1", "zh": "法甲"},
    "DED": {"name": "eredivisie", "zh": "荷甲"},
    "PPL": {"name": "primeira_liga", "zh": "葡超"},
    "BSA": {"name": "brasileirao", "zh": "巴甲"},
    "WC": {"name": "world_cup", "zh": "世界杯"},
    "EC": {"name": "euro_championship", "zh": "欧洲杯"},
    "CL": {"name": "champions_league", "zh": "欧冠"},
    "ELC": {"name": "championship", "zh": "英冠"},
}

BASE_DIR = Path(__file__).parent / "football-data_new"


class FootballDataAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.trust_env = False  # Bypass system proxy
        self.last_request = 0

    def _rate_limit(self):
        elapsed = time.time() - self.last_request
        if elapsed < REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL - elapsed)
        self.last_request = time.time()

    def get(self, endpoint, params=None):
        self._rate_limit()
        url = f"{BASE_URL}/{endpoint}"
        resp = self.session.get(url, params=params)
        if resp.status_code == 429:
            print("  Rate limited, waiting 60s...")
            time.sleep(60)
            return self.get(endpoint, params)
        if resp.status_code != 200:
            print(f"  Error {resp.status_code}: {url}")
            return None
        return resp.json()

    def get_all_pages(self, endpoint, params=None):
        """Get all pages of paginated results."""
        if params is None:
            params = {}
        all_items = []
        page = 1
        while True:
            params["page"] = page
            data = self.get(endpoint, params)
            if not data:
                break
            items_key = None
            for k in data:
                if isinstance(data[k], list):
                    items_key = k
                    break
            if not items_key:
                break
            items = data[items_key]
            all_items.extend(items)
            total_pages = (data.get("count", 0) + 99) // 100
            if page >= total_pages or len(items) < 100:
                break
            page += 1
        return all_items


def sync_matches(api, comp_code, season=None):
    """Sync all matches for a competition."""
    comp = COMPETITIONS[comp_code]
    comp_dir = BASE_DIR / "matches" / "clubs" / "leagues" / comp["name"]
    comp_dir.mkdir(parents=True, exist_ok=True)

    params = {}
    if season:
        params["season"] = season

    matches = api.get_all_pages(f"competitions/{comp_code}/matches", params)
    if not matches:
        print(f"  No matches found for {comp_code}")
        return

    # Group matches by season
    by_season = {}
    for m in matches:
        season_year = m.get("season", {}).get("startDate", "")[:4]
        if not season_year:
            continue
        end_year = m.get("season", {}).get("endDate", "")[:4]
        season_key = f"{season_year}-{end_year}"
        if season_key not in by_season:
            by_season[season_key] = []
        by_season[season_key].append(m)

    for season_key, season_matches in sorted(by_season.items()):
        filepath = comp_dir / f"{comp['name']}_{season_key}.csv"
        _write_matches_csv(season_matches, filepath, comp["zh"])
        print(f"  {filepath.name}: {len(season_matches)} matches")


def _write_matches_csv(matches, filepath, league_zh):
    matches.sort(key=lambda m: (m.get("matchday") or 0, m.get("utcDate") or ""))

    fieldnames = [
        "round", "date", "home_team", "home_team_tla", "away_team",
        "away_team_tla", "ft_home", "ft_away", "ht_home", "ht_away",
        "status", "match_id"
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in matches:
            score = m.get("score") or {}
            ft = score.get("fullTime") or {}
            ht = score.get("halfTime") or {}
            writer.writerow({
                "round": m.get("matchday", ""),
                "date": (m.get("utcDate") or "")[:10],
                "home_team": m["homeTeam"]["shortName"],
                "home_team_tla": m["homeTeam"].get("tla", ""),
                "away_team": m["awayTeam"]["shortName"],
                "away_team_tla": m["awayTeam"].get("tla", ""),
                "ft_home": ft.get("home", ""),
                "ft_away": ft.get("away", ""),
                "ht_home": ht.get("home", ""),
                "ht_away": ht.get("away", ""),
                "status": m.get("status", ""),
                "match_id": m.get("id", ""),
            })


def sync_standings(api, comp_code, season=None):
    """Sync standings for a competition."""
    comp = COMPETITIONS[comp_code]
    comp_dir = BASE_DIR / "standings" / "clubs" / "leagues" / comp["name"]
    comp_dir.mkdir(parents=True, exist_ok=True)

    endpoint = f"competitions/{comp_code}/standings"
    params = {}
    if season:
        params["season"] = season

    data = api.get(endpoint, params)
    if not data or "standings" not in data:
        print(f"  No standings for {comp_code}")
        return

    season_info = data.get("season") or data.get("competition", {}).get("season", {})
    start = (season_info.get("startDate") or "")[:4]
    end = (season_info.get("endDate") or "")[:4]
    if not start:
        start = str(season) if season else str(datetime.now().year)
    if not end:
        end = str(int(start) + 1)
    season_key = f"{start}-{end}"

    for standing in data["standings"]:
        stype = standing["type"]  # TOTAL, HOME, AWAY
        suffix = "" if stype == "TOTAL" else f"_{stype.lower()}"
        filepath = comp_dir / f"{comp['name']}_{season_key}{suffix}.csv"
        _write_standings_csv(standing["table"], filepath, comp["zh"])
        print(f"  {filepath.name}: {len(standing['table'])} teams")


def _write_standings_csv(table, filepath, league_zh):
    fieldnames = [
        "position", "team", "tla", "played", "won", "draw", "lost",
        "goals_for", "goals_against", "goal_difference", "points",
        "team_id"
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in table:
            writer.writerow({
                "position": entry.get("position", ""),
                "team": entry["team"]["shortName"],
                "tla": entry["team"].get("tla", ""),
                "played": entry.get("playedGames", ""),
                "won": entry.get("won", ""),
                "draw": entry.get("draw", ""),
                "lost": entry.get("lost", ""),
                "goals_for": entry.get("goalsFor", ""),
                "goals_against": entry.get("goalsAgainst", ""),
                "goal_difference": entry.get("goalDifference", ""),
                "points": entry.get("points", ""),
                "team_id": entry["team"].get("id", ""),
            })


def sync_scorers(api, comp_code, season=None):
    """Sync top scorers for a competition."""
    comp = COMPETITIONS[comp_code]
    comp_dir = BASE_DIR / "scorers" / "clubs" / "leagues" / comp["name"]
    comp_dir.mkdir(parents=True, exist_ok=True)

    params = {"limit": 100}
    if season:
        params["season"] = season

    scorers = api.get_all_pages(f"competitions/{comp_code}/scorers", params)
    if not scorers:
        print(f"  No scorers for {comp_code}")
        return

    # Get season info from competition endpoint
    comp_data = api.get(f"competitions/{comp_code}")
    if comp_data and "currentSeason" in comp_data:
        s = comp_data["currentSeason"]
        start = (s.get("startDate") or "")[:4]
        end = (s.get("endDate") or "")[:4]
        season_key = f"{start}-{end}" if start else "current"
    else:
        season_key = f"{season}-{int(season)+1}" if season else "current"

    filepath = comp_dir / f"{comp['name']}_{season_key}_scorers.csv"
    _write_scorers_csv(scorers, filepath)
    print(f"  {filepath.name}: {len(scorers)} scorers")


def _write_scorers_csv(scorers, filepath):
    fieldnames = [
        "rank", "player", "player_id", "team", "team_tla",
        "goals", "assists", "penalties", "played_matches"
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, s in enumerate(scorers, 1):
            writer.writerow({
                "rank": i,
                "player": s["player"]["name"],
                "player_id": s["player"]["id"],
                "team": s["team"]["shortName"],
                "team_tla": s["team"].get("tla", ""),
                "goals": s.get("goals", ""),
                "assists": s.get("assists", ""),
                "penalties": s.get("penalties", ""),
                "played_matches": s.get("playedMatches", ""),
            })


def sync_team_squads(api, comp_code, season=None):
    """Sync team squads for a competition."""
    comp = COMPETITIONS[comp_code]
    comp_dir = BASE_DIR / "squads" / "clubs" / "leagues" / comp["name"]
    comp_dir.mkdir(parents=True, exist_ok=True)

    # First get all teams from standings
    params = {}
    if season:
        params["season"] = season
    data = api.get(f"competitions/{comp_code}/standings", params)
    if not data or "standings" not in data:
        print(f"  No teams for {comp_code}")
        return

    season_info = data.get("season") or data.get("competition", {}).get("season", {})
    start = (season_info.get("startDate") or "")[:4]
    end = (season_info.get("endDate") or "")[:4]
    if not start:
        start = str(season) if season else str(datetime.now().year)
    if not end:
        end = str(int(start) + 1)
    season_key = f"{start}-{end}"

    teams = []
    for standing in data["standings"]:
        if standing["type"] == "TOTAL":
            for entry in standing["table"]:
                teams.append(entry["team"])
            break

    all_players = []
    for team in teams:
        squad = api.get(f"teams/{team['id']}")
        if not squad:
            continue
        for player in squad.get("squad") or []:
            all_players.append({
                "team": team["shortName"],
                "team_tla": team.get("tla", ""),
                "team_id": team["id"],
                "player": player["name"],
                "player_id": player["id"],
                "position": player.get("position", ""),
                "nationality": player.get("nationality", ""),
                "date_of_birth": (player.get("dateOfBirth") or "")[:10],
            })

    if all_players:
        filepath = comp_dir / f"{comp['name']}_{season_key}_squad.csv"
        fieldnames = [
            "team", "team_tla", "team_id", "player", "player_id",
            "position", "nationality", "date_of_birth"
        ]
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_players)
        print(f"  {filepath.name}: {len(all_players)} players from {len(teams)} teams")


def sync_competition(api, comp_code, data_types=None, seasons=None):
    """Sync all data for a competition."""
    comp = COMPETITIONS[comp_code]
    print(f"\n{'='*60}")
    print(f"Syncing {comp['zh']} ({comp['name']}) [{comp_code}]")
    print(f"{'='*60}")

    if data_types is None:
        data_types = ["matches", "standings", "scorers", "squads"]

    target_seasons = seasons or [None]  # None = current season

    for season in target_seasons:
        season_str = f" {season}" if season else " (current)"
        print(f"\n--- Season{season_str} ---")

        if "matches" in data_types:
            print("  Matches...")
            sync_matches(api, comp_code, season)

        if "standings" in data_types:
            print("  Standings...")
            sync_standings(api, comp_code, season)

        if "scorers" in data_types:
            print("  Scorers...")
            sync_scorers(api, comp_code, season)

        if "squads" in data_types:
            print("  Squads...")
            sync_team_squads(api, comp_code, season)


def sync_all(data_types=None, competitions=None, seasons=None):
    """Sync data for all (or selected) competitions."""
    api = FootballDataAPI()

    comp_codes = competitions or list(COMPETITIONS.keys())

    for comp_code in comp_codes:
        try:
            sync_competition(api, comp_code, data_types, seasons)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

    print(f"\n{'='*60}")
    print("Done!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="football-data.org API sync")
    parser.add_argument("--type", nargs="+", default=["matches", "standings", "scorers", "squads"],
                        choices=["matches", "standings", "scorers", "squads"],
                        help="Data types to sync")
    parser.add_argument("--comp", nargs="+", default=None,
                        help="Competition codes (e.g. PL PD BL1)")
    parser.add_argument("--season", nargs="+", default=None, type=int,
                        help="Seasons (e.g. 2024)")
    parser.add_argument("--matches-only", action="store_true",
                        help="Sync matches only (quick mode)")
    parser.add_argument("--current", action="store_true",
                        help="Sync current season only")

    args = parser.parse_args()

    if args.matches_only:
        data_types = ["matches"]
    else:
        data_types = args.type

    seasons = args.season if args.season else None

    sync_all(data_types=data_types, competitions=args.comp, seasons=seasons)
