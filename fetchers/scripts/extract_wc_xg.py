"""Extract xG from StatsBomb event data for WC 2018 & 2022."""
import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

SB_DIR = 'data/open-data-master/data'

def extract_xg_for_match(match_id):
    """Extract shot xG from StatsBomb events for a match."""
    event_file = os.path.join(SB_DIR, 'events', f'{match_id}.json')
    if not os.path.exists(event_file):
        return None

    with open(event_file, 'r', encoding='utf-8') as f:
        events = json.load(f)

    home_xg = 0.0
    away_xg = 0.0
    home_shots = 0
    away_shots = 0

    for e in events:
        if e.get('type', {}).get('name') == 'Shot':
            shot_stats = e.get('shot', {})
            xg = shot_stats.get('statsbomb_xg', 0.0) or 0.0
            team_id = e.get('team', {}).get('id')
            # Determine if home or away
            pos_team = e.get('possession_team', {}).get('id')
            if pos_team:
                # We need to know which team is home/away from match metadata
                # For now just accumulate by team_id
                if team_id == pos_team:
                    home_xg += xg
                    home_shots += 1
                else:
                    away_xg += xg
                    away_shots += 1

    return {
        'match_id': match_id,
        'home_xg': home_xg,
        'away_xg': away_xg,
        'home_shots': home_shots,
        'away_shots': away_shots,
    }

# Load match metadata to get home/away team IDs
for year, season_id in [('2018', '3'), ('2022', '106')]:
    print(f'=== WC {year} ===')

    with open(os.path.join(SB_DIR, 'matches', '43', f'{season_id}.json'), 'r', encoding='utf-8') as f:
        matches = json.load(f)

    print(f'Matches: {len(matches)}')

    xg_data = {}
    processed = 0
    for m in matches:
        match_id = m['match_id']
        home_team = m['home_team']['home_team_name']
        away_team = m['away_team']['away_team_name']
        home_id = m['home_team']['home_team_id']
        away_id = m['away_team']['away_team_id']
        home_score = m['home_score']
        away_score = m['away_score']
        match_date = m['match_date']

        # Load events and extract xG
        event_file = os.path.join(SB_DIR, 'events', f'{match_id}.json')
        if not os.path.exists(event_file):
            print(f'  No events for match {match_id}: {home_team} vs {away_team}')
            continue

        with open(event_file, 'r', encoding='utf-8') as f:
            events = json.load(f)

        home_xg = 0.0
        away_xg = 0.0
        home_shots = 0
        away_shots = 0
        home_goals_from_xg = 0  # goals from shots
        away_goals_from_xg = 0

        for e in events:
            if e.get('type', {}).get('name') == 'Shot':
                shot = e.get('shot', {})
                xg = shot.get('statsbomb_xg', 0.0) or 0.0
                team_name = e.get('team', {}).get('name', '')
                is_goal = shot.get('outcome', {}).get('name') == 'Goal'

                if team_name == home_team:
                    home_xg += xg
                    home_shots += 1
                    if is_goal:
                        home_goals_from_xg += 1
                elif team_name == away_team:
                    away_xg += xg
                    away_shots += 1
                    if is_goal:
                        away_goals_from_xg += 1

        key = f'{match_date}|{home_team}|{away_team}'
        xg_data[key] = {
            'match_id': match_id,
            'date': match_date,
            'home_team': home_team,
            'away_team': away_team,
            'home_score': home_score,
            'away_score': away_score,
            'home_xg': round(home_xg, 2),
            'away_xg': round(away_xg, 2),
            'home_shots': home_shots,
            'away_shots': away_shots,
        }
        processed += 1

    print(f'  Processed: {processed} matches with xG')

    # Save
    out_file = f'data/world_cup/wc_{year}_xg.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(xg_data, f, ensure_ascii=False, indent=2)
    print(f'  Saved to {out_file}')

    # Sample
    for key in sorted(list(xg_data.keys())[:5]):
        d = xg_data[key]
        print(f'    {d["date"]} {d["home_team"]} {d["home_score"]}:{d["away_score"]} {d["away_team"]} xG {d["home_xg"]}:{d["away_xg"]}')