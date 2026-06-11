"""Extract WC 2018 lineups and match statistics from StatsBomb event data.

StatsBomb's open data includes Starting XI events with formation/player info,
and we can aggregate shots/passes/fouls/cards from individual events.
"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')

SB_DIR = 'data/open-data-master/data'
OUT_DIR = 'data/world_cup'

def extract_match_data(match_meta, events):
    """Extract lineup and statistics from StatsBomb events for one match."""
    home_team = match_meta['home_team']['home_team_name']
    away_team = match_meta['away_team']['away_team_name']

    # --- Lineups ---
    lineups = {home_team: [], away_team: []}
    formations = {}

    for e in events:
        if e.get('type', {}).get('name') == 'Starting XI':
            team = e.get('team', {}).get('name', '')
            tactics = e.get('tactics', {})
            formations[team] = tactics.get('formation', '')
            for p in tactics.get('lineup', []):
                lineups[team].append({
                    'name': p.get('player', {}).get('name', ''),
                    'position': p.get('position', {}).get('name', ''),
                    'jersey_number': p.get('player', {}).get('jersey_number', ''),
                })

    # --- Statistics ---
    stats = {
        home_team: {'shots': 0, 'shots_on_target': 0, 'passes': 0, 'pass_accuracy': 0,
                     'fouls': 0, 'corners': 0, 'offsides': 0,
                     'yellow_cards': 0, 'red_cards': 0, 'possession': 0},
        away_team: {'shots': 0, 'shots_on_target': 0, 'passes': 0, 'pass_accuracy': 0,
                     'fouls': 0, 'corners': 0, 'offsides': 0,
                     'yellow_cards': 0, 'red_cards': 0, 'possession': 0},
    }

    # Possession counting
    home_poss_duration = 0
    away_poss_duration = 0

    for e in events:
        team = e.get('team', {}).get('name', '')
        if team not in stats:
            continue
        s = stats[team]
        etype = e.get('type', {}).get('name', '')

        if etype == 'Shot':
            s['shots'] += 1
            outcome = e.get('shot', {}).get('outcome', {}).get('name', '')
            if outcome in ('Goal', 'Saved', 'Saved to Post', 'Post'):
                s['shots_on_target'] += 1

        elif etype == 'Pass':
            s['passes'] += 1
            if e.get('pass', {}).get('outcome') is None:
                s['pass_accuracy'] += 1

        elif etype == 'Foul Committed':
            if e.get('foul_committed', {}).get('card') is None:
                s['fouls'] += 1

        elif etype == 'Bad Behaviour':
            card = e.get('bad_behaviour', {}).get('card', {}).get('name', '')
            if 'Yellow' in card:
                s['yellow_cards'] += 1
            elif 'Red' in card:
                s['red_cards'] += 1

        elif etype == 'Offside':
            s['offsides'] += 1

        # Possession from duration
        if etype == 'Half End':
            pass  # skip
        duration = e.get('duration', 0) or 0
        if duration > 0:
            if team == home_team:
                home_poss_duration += duration
            else:
                away_poss_duration += duration

    # Calculate pass accuracy % and possession %
    for team in [home_team, away_team]:
        s = stats[team]
        if s['passes'] > 0:
            s['pass_accuracy'] = round(s['pass_accuracy'] / s['passes'] * 100, 1)
        else:
            s['pass_accuracy'] = 0

    total_poss = home_poss_duration + away_poss_duration
    if total_poss > 0:
        stats[home_team]['possession'] = round(home_poss_duration / total_poss * 100, 1)
        stats[away_team]['possession'] = round(away_poss_duration / total_poss * 100, 1)

    # Format statistics like apifootball format for compatibility
    stat_list = []
    for stat_name, display_name in [
        ('shots', 'Total Shots'),
        ('shots_on_target', 'Shots on Target'),
        ('passes', 'Total Passes'),
        ('pass_accuracy', 'Pass Accuracy %'),
        ('fouls', 'Fouls'),
        ('corners', 'Corner Kicks'),
        ('offsides', 'Offsides'),
        ('yellow_cards', 'Yellow Cards'),
        ('red_cards', 'Red Cards'),
        ('possession', 'Ball Possession'),
    ]:
        stat_list.append({
            'type': display_name,
            'home': str(stats[home_team].get(stat_name, 0)),
            'away': str(stats[away_team].get(stat_name, 0)),
        })

    return {
        'lineups': lineups,
        'formations': formations,
        'statistics': stat_list,
    }


def main():
    # Load WC 2018 match list
    with open(os.path.join(SB_DIR, 'matches', '43', '3.json'), 'r', encoding='utf-8') as f:
        matches_meta = json.load(f)

    print(f'WC 2018: {len(matches_meta)} matches')

    results = []
    ok = 0
    fail = 0

    for i, m in enumerate(matches_meta):
        mid = m['match_id']
        home = m['home_team']['home_team_name']
        away = m['away_team']['away_team_name']

        event_file = os.path.join(SB_DIR, 'events', f'{mid}.json')
        if not os.path.exists(event_file):
            print(f'  [{i+1}] No events: {home} vs {away}')
            fail += 1
            continue

        with open(event_file, 'r', encoding='utf-8') as f:
            events = json.load(f)

        data = extract_match_data(m, events)

        entry = {
            'match_id': mid,
            'date': m['match_date'][:10],
            'home_team': home,
            'away_team': away,
            'home_score': m['home_score'],
            'away_score': m['away_score'],
            'home_formation': data['formations'].get(home, ''),
            'away_formation': data['formations'].get(away, ''),
            'home_lineup': data['lineups'].get(home, []),
            'away_lineup': data['lineups'].get(away, []),
            'statistics': data['statistics'],
        }
        results.append(entry)
        ok += 1

        if (i + 1) % 16 == 0 or i == 0:
            print(f'  [{i+1}/{len(matches_meta)}] {home} vs {away} '
                  f'form={data["formations"].get(home,"?")}-{data["formations"].get(away,"?")} '
                  f'lineup={len(data["lineups"].get(home,[]))}+{len(data["lineups"].get(away,[]))} '
                  f'stats={len(data["statistics"])}')

    print(f'\nDone: {ok} ok, {fail} fail')

    # Save
    out_file = os.path.join(OUT_DIR, 'wc_2018_statsbomb_stats.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'Saved to {out_file}')

    # Verify
    has_lineup = sum(1 for r in results if len(r.get('home_lineup', [])) == 11 and len(r.get('away_lineup', [])) == 11)
    has_stats = sum(1 for r in results if len(r.get('statistics', [])) >= 5)
    has_formation = sum(1 for r in results if r.get('home_formation') and r.get('away_formation'))
    print(f'  With full lineup (11+11): {has_lineup}/{ok}')
    print(f'  With statistics (5+): {has_stats}/{ok}')
    print(f'  With formations: {has_formation}/{ok}')

if __name__ == '__main__':
    main()
