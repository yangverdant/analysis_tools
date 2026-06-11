"""World Cup historical data fetcher.

Reads pre-collected data from StatsBomb open data and Flashscore scraped odds.
Returns data in the same dict-of-fields format as other fetchers.

Available functions:
- get_matches(year) → match results + scores + xG
- get_odds(year) → 1X2 closing odds from Flashscore
- get_lineups(year) → Starting XI + formations from StatsBomb
- get_statistics(year) → Aggregated match stats from StatsBomb events
- get_full_data(year) → All data merged by match_key
"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')

from .config import DATA_DIR, SB_DATA_DIR, STATSBOMB_COMPETITION_ID, STATSBOMB_SEASON_IDS


def _load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def _sb_events_path(match_id):
    return os.path.join(SB_DATA_DIR, 'events', f'{match_id}.json')


def _sb_matches_path(season_id):
    return os.path.join(SB_DATA_DIR, 'matches', str(STATSBOMB_COMPETITION_ID), f'{season_id}.json')


# ---------------------------------------------------------------------------
# get_matches — scores + xG from StatsBomb
# ---------------------------------------------------------------------------
def get_matches(year):
    """Get WC match results with scores and xG.

    Returns list of dicts with fields:
        match_key, date, home_team, away_team, home_score, away_score,
        home_xg, away_xg, home_shots, away_shots, league, source
    """
    xg_file = os.path.join(DATA_DIR, f'wc_{year}_xg.json')
    if not os.path.exists(xg_file):
        print(f'[world_cup] No xG data for WC {year}')
        return []

    xg_data = _load_json(xg_file)
    results = []

    for key, v in xg_data.items():
        results.append({
            'match_key': f'{v["date"][:10]}|{v["home_team"]}|{v["away_team"]}',
            'date': v['date'][:10],
            'home_team': v['home_team'],
            'away_team': v['away_team'],
            'home_score': str(v['home_score']),
            'away_score': str(v['away_score']),
            'home_xg': v['home_xg'],
            'away_xg': v['away_xg'],
            'home_shots': v.get('home_shots', 0),
            'away_shots': v.get('away_shots', 0),
            'league': 'World Cup',
            'source': 'statsbomb',
        })

    print(f'[world_cup] get_matches({year}): {len(results)} matches')
    return results


# ---------------------------------------------------------------------------
# get_odds — 1X2 closing odds from Flashscore
# ---------------------------------------------------------------------------
def get_odds(year):
    """Get WC 1X2 closing odds from Flashscore.

    Returns list of dicts with fields:
        match_key, date, home_team, away_team, odds_home, odds_draw, odds_away,
        odds_source, source
    """
    odds_file = os.path.join(DATA_DIR, f'wc_{year}_odds.json')
    if not os.path.exists(odds_file):
        print(f'[world_cup] No odds data for WC {year}')
        return []

    data = _load_json(odds_file)
    results = []

    for m in data:
        entry = {
            'match_key': f'{m["date"]}|{m["home_team"]}|{m["away_team"]}',
            'date': m['date'],
            'home_team': m['home_team'],
            'away_team': m['away_team'],
            'source': 'flashscore',
        }
        if 'odds_home' in m:
            entry['odds_home'] = m['odds_home']
            entry['odds_draw'] = m['odds_draw']
            entry['odds_away'] = m['odds_away']
            entry['odds_source'] = 'flashscore'
        results.append(entry)

    print(f'[world_cup] get_odds({year}): {len(results)} matches, '
          f'{sum(1 for r in results if "odds_home" in r)} with odds')
    return results


# ---------------------------------------------------------------------------
# get_lineups — Starting XI + formations from StatsBomb
# ---------------------------------------------------------------------------
def get_lineups(year):
    """Get WC starting lineups and formations from StatsBomb events.

    Returns list of dicts with fields:
        match_key, date, home_team, away_team, home_formation, away_formation,
        home_lineup, away_lineup, source
    """
    season_id = STATSBOMB_SEASON_IDS.get(year)
    if not season_id:
        print(f'[world_cup] No StatsBomb season ID for WC {year}')
        return []

    matches_path = _sb_matches_path(season_id)
    if not os.path.exists(matches_path):
        print(f'[world_cup] StatsBomb matches file not found: {matches_path}')
        return []

    matches_meta = _load_json(matches_path)
    results = []

    for m in matches_meta:
        mid = m['match_id']
        home = m['home_team']['home_team_name']
        away = m['away_team']['away_team_name']

        events_path = _sb_events_path(mid)
        if not os.path.exists(events_path):
            continue

        events = _load_json(events_path)

        lineups = {home: [], away: []}
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

        results.append({
            'match_key': f'{m["match_date"][:10]}|{home}|{away}',
            'date': m['match_date'][:10],
            'home_team': home,
            'away_team': away,
            'home_formation': formations.get(home, ''),
            'away_formation': formations.get(away, ''),
            'home_lineup': lineups.get(home, []),
            'away_lineup': lineups.get(away, []),
            'source': 'statsbomb',
        })

    print(f'[world_cup] get_lineups({year}): {len(results)} matches')
    return results


# ---------------------------------------------------------------------------
# get_statistics — aggregated match stats from StatsBomb events
# ---------------------------------------------------------------------------
def get_statistics(year):
    """Get WC match statistics aggregated from StatsBomb events.

    Returns list of dicts with fields:
        match_key, date, home_team, away_team, statistics, source
    """
    season_id = STATSBOMB_SEASON_IDS.get(year)
    if not season_id:
        return []

    matches_path = _sb_matches_path(season_id)
    if not os.path.exists(matches_path):
        return []

    matches_meta = _load_json(matches_path)
    results = []

    for m in matches_meta:
        mid = m['match_id']
        home = m['home_team']['home_team_name']
        away = m['away_team']['away_team_name']

        events_path = _sb_events_path(mid)
        if not os.path.exists(events_path):
            continue

        events = _load_json(events_path)
        stats = _aggregate_stats(events, home, away)

        results.append({
            'match_key': f'{m["match_date"][:10]}|{home}|{away}',
            'date': m['match_date'][:10],
            'home_team': home,
            'away_team': away,
            'statistics': stats,
            'source': 'statsbomb',
        })

    print(f'[world_cup] get_statistics({year}): {len(results)} matches')
    return results


def _aggregate_stats(events, home_team, away_team):
    """Aggregate match statistics from StatsBomb events."""
    counters = {
        home_team: {'shots': 0, 'shots_on_target': 0, 'passes': 0, 'passes_completed': 0,
                     'fouls': 0, 'offsides': 0, 'yellow_cards': 0, 'red_cards': 0},
        away_team: {'shots': 0, 'shots_on_target': 0, 'passes': 0, 'passes_completed': 0,
                     'fouls': 0, 'offsides': 0, 'yellow_cards': 0, 'red_cards': 0},
    }

    home_dur = 0.0
    away_dur = 0.0

    for e in events:
        team = e.get('team', {}).get('name', '')
        if team not in counters:
            continue
        c = counters[team]
        etype = e.get('type', {}).get('name', '')

        if etype == 'Shot':
            c['shots'] += 1
            outcome = e.get('shot', {}).get('outcome', {}).get('name', '')
            if outcome in ('Goal', 'Saved', 'Saved to Post', 'Post'):
                c['shots_on_target'] += 1
        elif etype == 'Pass':
            c['passes'] += 1
            if e.get('pass', {}).get('outcome') is None:
                c['passes_completed'] += 1
        elif etype == 'Foul Committed':
            if not e.get('foul_committed', {}).get('card'):
                c['fouls'] += 1
        elif etype == 'Bad Behaviour':
            card = e.get('bad_behaviour', {}).get('card', {}).get('name', '')
            if 'Yellow' in card:
                c['yellow_cards'] += 1
            elif 'Red' in card:
                c['red_cards'] += 1
        elif etype == 'Offside':
            c['offsides'] += 1

        dur = e.get('duration', 0) or 0
        if dur > 0:
            if team == home_team:
                home_dur += dur
            else:
                away_dur += dur

    # Build stat list (same format as apifootball)
    stat_items = [
        ('Total Shots', 'shots'),
        ('Shots on Target', 'shots_on_target'),
        ('Total Passes', 'passes'),
        ('Pass Accuracy %', 'passes_completed', 'passes'),
        ('Fouls', 'fouls'),
        ('Offsides', 'offsides'),
        ('Yellow Cards', 'yellow_cards'),
        ('Red Cards', 'red_cards'),
    ]

    stats = []
    for item in stat_items:
        label = item[0]
        key = item[1]
        h_val = counters[home_team][key]
        a_val = counters[away_team][key]

        if len(item) == 3:
            # Percentage stat
            denom_h = counters[home_team][item[2]]
            denom_a = counters[away_team][item[2]]
            h_str = f'{h_val}/{denom_h} ({round(h_val/denom_h*100,1)}%)' if denom_h else '0'
            a_str = f'{a_val}/{denom_a} ({round(a_val/denom_a*100,1)}%)' if denom_a else '0'
        else:
            h_str = str(h_val)
            a_str = str(a_val)

        stats.append({'type': label, 'home': h_str, 'away': a_str})

    # Possession
    total_dur = home_dur + away_dur
    if total_dur > 0:
        stats.append({
            'type': 'Ball Possession',
            'home': f'{round(home_dur/total_dur*100,1)}%',
            'away': f'{round(away_dur/total_dur*100,1)}%',
        })

    return stats


# ---------------------------------------------------------------------------
# get_full_data — all data merged by match_key
# ---------------------------------------------------------------------------
def get_full_data(year):
    """Get all WC data for a year, merged by match_key.

    Returns list of dicts with all fields from matches + odds + lineups + statistics.
    """
    matches = {m['match_key']: m for m in get_matches(year)}
    odds = {m['match_key']: m for m in get_odds(year)}
    lineups = {m['match_key']: m for m in get_lineups(year)}
    statistics = {m['match_key']: m for m in get_statistics(year)}

    all_keys = sorted(set(matches.keys()) | set(odds.keys()) | set(lineups.keys()) | set(statistics.keys()))

    results = []
    for key in all_keys:
        entry = {'match_key': key}

        # Base match info
        if key in matches:
            entry.update(matches[key])

        # Merge odds (don't overwrite existing fields)
        if key in odds:
            for k, v in odds[key].items():
                if k not in entry or k.startswith('odds_'):
                    entry[k] = v

        # Merge lineups
        if key in lineups:
            for k, v in lineups[key].items():
                if k not in entry:
                    entry[k] = v

        # Merge statistics
        if key in statistics:
            for k, v in statistics[key].items():
                if k not in entry:
                    entry[k] = v

        entry['source'] = 'statsbomb+flashscore'
        results.append(entry)

    has_odds = sum(1 for r in results if 'odds_home' in r)
    has_lineup = sum(1 for r in results if 'home_lineup' in r and len(r.get('home_lineup', [])) == 11)
    print(f'[world_cup] get_full_data({year}): {len(results)} matches, '
          f'{has_odds} with odds, {has_lineup} with lineups')
    return results
