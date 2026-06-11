"""Build final WC odds files by matching flashscore odds to StatsBomb xG matches.

Flashscore odds data has messy team names (includes score info) and includes
qualifier matches. This script cleans team names, matches to the 64 main
tournament matches from StatsBomb, and outputs clean odds files.
"""
import json, re, sys
sys.stdout.reconfigure(encoding='utf-8')

# Name variations between StatsBomb and Flashscore
NAME_MAP = {
    'usa': 'united states',
    'korea republic': 'south korea',
    'korea': 'south korea',
    "côte d'ivoire": 'ivory coast',
    'dr congo': 'd.r. congo',
    'congo dr': 'd.r. congo',
    'bosnia-herzegovina': 'bosnia and herzegovina',
    'bosnia & herzegovina': 'bosnia and herzegovina',
    'north macedonia': 'north macedonia',
    'macedonia': 'north macedonia',
    'china pr': 'china',
    "korea dpr": "korea republic",
    'ivory coast': "côte d'ivoire",
}

def clean_team_name(name):
    """Remove score prefix from flashscore team names."""
    if ' | ' in name:
        name = name.split(' | ')[-1]
    return name.strip()

def normalize_name(name):
    """Normalize team name for matching."""
    n = name.lower().strip()
    return NAME_MAP.get(n, n)

def build_wc_odds(year):
    # Load odds data
    odds_file = f'data/world_cup/wc_{year}_odds.json'
    with open(odds_file, 'r', encoding='utf-8') as f:
        odds_data = json.load(f)

    # Load xG data (has exactly 64 main tournament matches)
    xg_file = f'data/world_cup/wc_{year}_xg.json'
    with open(xg_file, 'r', encoding='utf-8') as f:
        xg_data = json.load(f)

    # Build match lookup from xG
    xg_matches = {}
    for k, v in xg_data.items():
        home = normalize_name(v['home_team'])
        away = normalize_name(v['away_team'])
        key = f'{home}|{away}'
        xg_matches[key] = v

    print(f'\nWC {year}: {len(odds_data)} odds entries, {len(xg_matches)} xG matches')

    # Build odds lookup
    odds_lookup = {}
    for m in odds_data:
        if 'odds_home' not in m:
            continue
        raw_home = clean_team_name(m.get('home_team', ''))
        raw_away = clean_team_name(m.get('away_team', ''))
        home = normalize_name(raw_home)
        away = normalize_name(raw_away)
        key = f'{home}|{away}'
        odds_lookup[key] = {
            'odds_home': m['odds_home'],
            'odds_draw': m['odds_draw'],
            'odds_away': m['odds_away'],
            'source': 'flashscore',
        }

    # Match and build final data
    final = []
    matched = 0
    unmatched = []

    for k, v in sorted(xg_matches.items()):
        home = v['home_team']
        away = v['away_team']
        nhome = normalize_name(home)
        naway = normalize_name(away)
        key = f'{nhome}|{naway}'

        entry = {
            'date': v['date'][:10],
            'home_team': home,
            'away_team': away,
            'home_score': v['home_score'],
            'away_score': v['away_score'],
            'home_xg': v['home_xg'],
            'away_xg': v['away_xg'],
        }

        if key in odds_lookup:
            entry['odds_home'] = odds_lookup[key]['odds_home']
            entry['odds_draw'] = odds_lookup[key]['odds_draw']
            entry['odds_away'] = odds_lookup[key]['odds_away']
            entry['odds_source'] = 'flashscore'
            matched += 1
        else:
            unmatched.append(f'{home} vs {away} (key={key})')

        final.append(entry)

    print(f'  Matched: {matched}/{len(xg_matches)}')
    if unmatched:
        print(f'  Unmatched: {len(unmatched)}')
        for u in unmatched:
            print(f'    {u}')

    # Show sample
    print(f'  Sample:')
    for m in final[:5]:
        if 'odds_home' in m:
            print(f'    {m["date"]} {m["home_team"]} vs {m["away_team"]} {m["home_score"]}:{m["away_score"]} xG {m["home_xg"]}:{m["away_xg"]} odds {m["odds_home"]}/{m["odds_draw"]}/{m["odds_away"]}')
        else:
            print(f'    {m["date"]} {m["home_team"]} vs {m["away_team"]} {m["home_score"]}:{m["away_score"]} xG {m["home_xg"]}:{m["away_xg"]} (no odds)')

    # Save
    out_file = f'data/world_cup/wc_{year}_odds_final.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f'  Saved to {out_file}')

    return final, matched

for year in [2022, 2018]:
    final, matched = build_wc_odds(year)
