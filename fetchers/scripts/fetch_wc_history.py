"""Fetch 2018 and 2022 World Cup complete data from football-data.org API."""
import requests, json, time, sys, os
sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
session.trust_env = False

with open('api_config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

fd_token = config['apis']['football_data_org']['api_token']
headers = {'X-Auth-Token': fd_token}
BASE = 'https://api.football-data.org/v4'

def fetch_matches(season):
    """Fetch all WC matches for a season."""
    r = session.get(f'{BASE}/competitions/WC/matches?season={season}', headers=headers, timeout=15)
    if r.status_code != 200:
        print(f'  ERROR: {r.status_code}')
        return []
    data = r.json()
    matches = data.get('matches', [])
    print(f'  Got {len(matches)} matches for WC {season}')
    return matches

def fetch_teams(season):
    """Fetch all WC teams for a season."""
    r = session.get(f'{BASE}/competitions/WC/teams?season={season}', headers=headers, timeout=15)
    if r.status_code != 200:
        print(f'  ERROR: {r.status_code}')
        return []
    data = r.json()
    teams = data.get('teams', [])
    print(f'  Got {len(teams)} teams for WC {season}')
    return teams

def fetch_squad(team_id):
    """Fetch squad for a team."""
    r = session.get(f'{BASE}/teams/{team_id}', headers=headers, timeout=15)
    if r.status_code != 200:
        print(f'  Squad ERROR: {r.status_code} for team {team_id}')
        return []
    data = r.json()
    return data.get('squad', [])

def parse_match(m):
    """Parse a match into standardized format."""
    home = m.get('homeTeam', {})
    away = m.get('awayTeam', {})
    score = m.get('score', {})

    result = {
        'id': m.get('id'),
        'date': m.get('utcDate', '')[:10],
        'matchday': m.get('matchday'),
        'stage': m.get('stage'),
        'group': m.get('group'),
        'status': m.get('status'),
        'home_team': home.get('name', ''),
        'home_tla': home.get('tla', ''),
        'home_id': home.get('id'),
        'away_team': away.get('name', ''),
        'away_tla': away.get('tla', ''),
        'away_id': away.get('id'),
        'home_goals': score.get('fullTime', {}).get('home'),
        'away_goals': score.get('fullTime', {}).get('away'),
        'home_ht_goals': score.get('halfTime', {}).get('home'),
        'away_ht_goals': score.get('halfTime', {}).get('away'),
        'home_et_goals': score.get('extraTime', {}).get('home'),
        'away_et_goals': score.get('extraTime', {}).get('away'),
        'home_pen_goals': score.get('penalties', {}).get('home'),
        'away_pen_goals': score.get('penalties', {}).get('away'),
        'winner': score.get('winner'),
        'duration': score.get('duration'),
        'venue': m.get('venue', ''),
        'referee': m.get('referees', [{}])[0].get('name', '') if m.get('referees') else '',
    }
    return result

def parse_squad_player(p):
    """Parse a squad player."""
    return {
        'name': p.get('name', ''),
        'position': p.get('position', ''),
        'nationality': p.get('nationality', ''),
        'dateOfBirth': p.get('dateOfBirth', ''),
        'countryOfBirth': p.get('countryOfBirth', ''),
        'id': p.get('id'),
    }

# === Main ===
os.makedirs('data/world_cup', exist_ok=True)

for season in [2018, 2022]:
    print(f'\n=== WC {season} ===')

    # 1. Matches
    matches = fetch_matches(season)
    parsed_matches = [parse_match(m) for m in matches]

    # Stats
    group_matches = [m for m in parsed_matches if 'GROUP' in (m.get('stage') or '')]
    knockout_matches = [m for m in parsed_matches if 'GROUP' not in (m.get('stage') or '')]
    print(f'  Group: {len(group_matches)}, Knockout: {len(knockout_matches)}')

    with open(f'data/world_cup/wc_{season}_matches.json', 'w', encoding='utf-8') as f:
        json.dump(parsed_matches, f, ensure_ascii=False, indent=2)
    print(f'  Saved matches to wc_{season}_matches.json')

    # 2. Teams + Squads
    teams = fetch_teams(season)
    team_data = {}

    for i, team in enumerate(teams):
        tid = team['id']
        name = team['name']
        tla = team.get('tla', '')

        # Fetch squad (rate limit: 7s)
        squad = fetch_squad(tid)
        players = [parse_squad_player(p) for p in squad]

        team_data[tla] = {
            'name': name,
            'tla': tla,
            'team_id': tid,
            'crest': team.get('crest', ''),
            'squad_size': len(players),
            'players': players,
        }
        print(f'    [{i+1}/{len(teams)}] {name} ({tla}): {len(players)} players')

        if i < len(teams) - 1:
            time.sleep(7)

    with open(f'data/world_cup/wc_{season}_squads.json', 'w', encoding='utf-8') as f:
        json.dump(team_data, f, ensure_ascii=False, indent=2)
    print(f'  Saved squads to wc_{season}_squads.json')

    # Summary
    total_players = sum(t['squad_size'] for t in team_data.values())
    print(f'  Total: {len(team_data)} teams, {total_players} players')

print('\nDone!')
