"""FIFA World Ranking fetcher.

Provides FIFA ranking data for international match analysis.
Ranking data is stored locally and can be refreshed from FIFA's website.

Available functions:
- get_rankings() → current FIFA rankings (top 100+)
- get_team_ranking(team_name) → single team rank + points
- get_ranking_diff(home, away) → ranking difference for prediction
- get_confederation(team_name) → team's confederation
"""
import json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

from .config import DATA_DIR, CONFEDERATION_STRENGTH

RANKING_FILE = os.path.join(DATA_DIR, 'fifa_ranking_current.json')
HISTORICAL_FILE = os.path.join(DATA_DIR, 'fifa_ranking_historical.json')


def _load_rankings():
    """Load current ranking data from local JSON."""
    if not os.path.exists(RANKING_FILE):
        return {}
    with open(RANKING_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save_rankings(data):
    """Save ranking data to local JSON."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(RANKING_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize_team(name):
    """Normalize team name for matching."""
    n = name.lower().strip()
    aliases = {
        'usa': 'united states',
        'usmnt': 'united states',
        'south korea': 'korea republic',
        'korea': 'korea republic',
        "côte d'ivoire": 'ivory coast',
        'dr congo': 'congo dr',
        'bosnia-herzegovina': 'bosnia and herzegovina',
        'china pr': 'china',
        'north macedonia': 'macedonia',
    }
    return aliases.get(n, n)


# ---------------------------------------------------------------------------
# get_rankings — full ranking table
# ---------------------------------------------------------------------------
def get_rankings(top_n=None):
    """Get current FIFA World Rankings.

    Returns list of dicts with fields:
        rank, team, points, confederation, source
    """
    data = _load_rankings()
    if not data:
        print('[fifa_ranking] No ranking data loaded. Run refresh first.')
        return []

    results = []
    for team, info in data.items():
        results.append({
            'rank': info.get('rank', 0),
            'team': team,
            'points': info.get('points', 0),
            'confederation': info.get('confederation', ''),
            'source': 'fifa_ranking',
        })

    results.sort(key=lambda x: x['rank'])

    if top_n:
        results = results[:top_n]

    print(f'[fifa_ranking] get_rankings(): {len(results)} teams')
    return results


# ---------------------------------------------------------------------------
# get_team_ranking — single team
# ---------------------------------------------------------------------------
def get_team_ranking(team_name):
    """Get FIFA ranking for a single team.

    Returns dict with: rank, team, points, confederation, source
    """
    data = _load_rankings()
    key = _normalize_team(team_name)

    # Try exact match first
    if team_name in data:
        info = data[team_name]
    elif key in data:
        info = data[key]
    else:
        # Fuzzy: check if any key contains the name
        for k, v in data.items():
            if key in _normalize_team(k) or _normalize_team(k) in key:
                info = v
                break
        else:
            return {
                'rank': 999,
                'team': team_name,
                'points': 0,
                'confederation': '',
                'source': 'fifa_ranking',
                'note': 'not_found',
            }

    return {
        'rank': info.get('rank', 0),
        'team': team_name,
        'points': info.get('points', 0),
        'confederation': info.get('confederation', ''),
        'source': 'fifa_ranking',
    }


# ---------------------------------------------------------------------------
# get_ranking_diff — for prediction features
# ---------------------------------------------------------------------------
def get_ranking_diff(home_team, away_team):
    """Get ranking difference between two teams.

    Returns dict with:
        home_rank, away_rank, rank_diff (home - away, negative = home stronger),
        home_points, away_points, points_diff,
        home_confederation, away_confederation,
        confederation_strength_diff,
        source
    """
    home = get_team_ranking(home_team)
    away = get_team_ranking(away_team)

    home_conf = home.get('confederation', '')
    away_conf = away.get('confederation', '')

    home_str = CONFEDERATION_STRENGTH.get(home_conf, 0.5)
    away_str = CONFEDERATION_STRENGTH.get(away_conf, 0.5)

    return {
        'home_rank': home['rank'],
        'away_rank': away['rank'],
        'rank_diff': home['rank'] - away['rank'],  # negative = home ranked higher
        'home_points': home['points'],
        'away_points': away['points'],
        'points_diff': home['points'] - away['points'],
        'home_confederation': home_conf,
        'away_confederation': away_conf,
        'confederation_strength_diff': round(home_str - away_str, 2),
        'source': 'fifa_ranking',
    }


# ---------------------------------------------------------------------------
# get_confederation — single team confederation
# ---------------------------------------------------------------------------
def get_confederation(team_name):
    """Get confederation for a team."""
    info = get_team_ranking(team_name)
    return {
        'team': team_name,
        'confederation': info.get('confederation', ''),
        'confederation_strength': CONFEDERATION_STRENGTH.get(info.get('confederation', ''), 0.5),
        'source': 'fifa_ranking',
    }


# ---------------------------------------------------------------------------
# refresh_rankings — scrape from FIFA website (optional, needs Playwright)
# ---------------------------------------------------------------------------
def refresh_rankings():
    """Refresh FIFA ranking data from FIFA's website using Playwright.

    Requires: playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('[fifa_ranking] Playwright not installed. Cannot refresh.')
        return False

    import time

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('https://www.fifa.com/fifa-world-ranking/men',
                  wait_until='networkidle', timeout=60000)
        time.sleep(5)

        # Try to accept cookies
        try:
            btn = page.locator('#onetrust-accept-btn-handler')
            if btn.is_visible(timeout=3000):
                btn.click()
                time.sleep(1)
        except:
            pass

        # Extract ranking data from page
        html = page.content()
        body = page.inner_text('body')

        rankings = {}
        # Parse ranking rows from the rendered text
        # FIFA shows format like: "1 Argentina 1865.52 ..."
        pattern = r'(\d{1,3})\s+([A-Z][a-zA-Z\s&.\'-]+?)\s+(\d{3,5}\.?\d*)'
        matches = re.findall(pattern, body)

        for rank_str, team, points_str in matches:
            try:
                rank = int(rank_str)
                points = float(points_str)
                if rank <= 300 and points > 0:
                    # Get confederation from page if available
                    conf = ''
                    rankings[team.strip()] = {
                        'rank': rank,
                        'points': points,
                        'confederation': conf,
                    }
            except:
                continue

        browser.close()

    if rankings:
        _save_rankings(rankings)
        print(f'[fifa_ranking] Refreshed: {len(rankings)} teams')
        return True
    else:
        print('[fifa_ranking] No ranking data found on page')
        return False
