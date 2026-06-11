"""Scrape real WC 2018/2022 odds from betexplorer.com.

Strategy:
1. Use Playwright to visit betexplorer match pages
2. Get match IDs from the results page (knockout stage)
3. For group stage matches, use betexplorer search or direct URL construction
4. Visit each match page and extract closing 1X2 odds from data-odd attributes
"""
import json, re, time, sys, os
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding='utf-8')

ODDS_DIR = 'data/world_cup'

def team_slug(name):
    """Convert team name to betexplorer URL slug."""
    return (name.lower()
            .replace(' ', '-')
            .replace('é', 'e').replace('á', 'a').replace('í', 'i')
            .replace('ó', 'o').replace('ú', 'u').replace('ã', 'a')
            .replace('ç', 'c').replace('ñ', 'n').replace('ü', 'u')
            .replace('ö', 'o').replace('ä', 'a').replace('ø', 'o')
            .replace('æ', 'ae').replace('&', '-and-')
            .replace('sr.', 'sr')
            .replace('st.', 'st'))

def extract_odds_from_match_page(page, match_id=None):
    """Extract 1X2 closing odds from a betexplorer match page."""
    html = page.content()

    # Method 1: data-odd attributes (most reliable for rendered page)
    data_odds = re.findall(r'data-odd="([\d.]+)"', html)

    # Method 2: table-main__odds class
    table_odds = re.findall(r'class="table-main__odds[^"]*"[^>]*>([\d.]+)</td>', html)

    # Use data-odd as primary (they're the closing odds shown in the main odds table)
    if len(data_odds) >= 3:
        return {
            'odds_home': float(data_odds[0]),
            'odds_draw': float(data_odds[1]),
            'odds_away': float(data_odds[2]),
        }
    elif len(table_odds) >= 3:
        return {
            'odds_home': float(table_odds[0]),
            'odds_draw': float(table_odds[1]),
            'odds_away': float(table_odds[2]),
        }
    return None

def scrape_wc_odds(year):
    """Scrape betexplorer for WC odds."""

    # Load existing match data
    with open(f'data/world_cup/wc_{year}_af_matches.json', 'r', encoding='utf-8') as f:
        matches = json.load(f)

    # Load xG data for cross-reference
    with open(f'data/world_cup/wc_{year}_xg.json', 'r', encoding='utf-8') as f:
        xg_data = json.load(f)

    print(f'WC {year}: {len(matches)} matches to process')

    odds_results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({'width': 1280, 'height': 800})

        # Visit betexplorer homepage to get cookies
        page.goto('https://www.betexplorer.com/', wait_until='networkidle', timeout=30000)
        time.sleep(2)

        try:
            btn = page.locator('#onetrust-accept-btn-handler')
            if btn.is_visible(timeout=3000):
                btn.click()
                time.sleep(1)
        except:
            pass

        # Method 1: Get match IDs from results page
        results_url = f'https://www.betexplorer.com/football/world/world-cup-{year}/results/'
        page.goto(results_url, wait_until='networkidle', timeout=60000)
        time.sleep(3)

        # Load more matches
        for attempt in range(20):
            try:
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(0.5)
                load_more = page.locator('button:has-text("Load more")')
                if load_more.count() > 0 and load_more.first.is_visible(timeout=1500):
                    load_more.first.click()
                    time.sleep(2)
                else:
                    break
            except:
                break

        html = page.content()

        # Extract match URLs with IDs
        match_pattern = rf'href="/football/world/world-cup-{year}/([^/]+)/([^"]+)/"'
        match_urls = re.findall(match_pattern, html)

        # Also extract matches with odds directly from the results page
        in_match_pattern = r'<a[^>]*class="in-match"[^>]*><span>([^<]+)</span>\s*-\s*<span>([^<]+)</span></a>'
        results_matches = list(re.finditer(in_match_pattern, html))

        for rm in results_matches:
            home = rm.group(1).strip()
            away = rm.group(2).strip()
            end_pos = rm.end()
            snippet = html[end_pos:end_pos+600]
            odds_vals = re.findall(r'data-odd="([\d.]+)"', snippet)

            if len(odds_vals) >= 3:
                key = f'{home}|{away}'
                odds_results[key] = {
                    'home_team': home,
                    'away_team': away,
                    'odds_home': float(odds_vals[0]),
                    'odds_draw': float(odds_vals[1]),
                    'odds_away': float(odds_vals[2]),
                    'source': 'betexplorer',
                }

        print(f'  From results page: {len(odds_results)} matches')

        # Visit each match detail page for better odds
        for slug, mid in match_urls:
            try:
                match_url = f'https://www.betexplorer.com/football/world/world-cup-{year}/{slug}/{mid}/'
                page.goto(match_url, wait_until='networkidle', timeout=20000)
                time.sleep(2)

                odds = extract_odds_from_match_page(page, mid)
                if odds:
                    # Get team names from slug
                    parts = slug.split('-')
                    # Team names are separated by the last hyphen before the ID
                    # e.g., argentina-france -> argentina, france
                    # But some teams have multi-word names like costa-rica
                    # Let's extract from the page title
                    title = page.title()
                    teams_in_title = re.findall(r'([^–]+)', title)
                    if len(teams_in_title) >= 2:
                        home = teams_in_title[0].strip()
                        away = teams_in_title[1].strip().split(' - ')[0].strip() if ' - ' in teams_in_title[1] else teams_in_title[1].strip()
                    else:
                        # Fallback: use slug
                        home = slug
                        away = ''

                    key = f'{home}|{away}'
                    odds_results[key] = {
                        'home_team': home,
                        'away_team': away,
                        **odds,
                        'source': 'betexplorer',
                    }
                    print(f'    Detail: {slug} → {odds}')
            except:
                continue

        # Method 2: For remaining matches, try search
        matched_teams = set()
        for key in odds_results:
            matched_teams.add(odds_results[key]['home_team'].lower())
            matched_teams.add(odds_results[key]['away_team'].lower())

        remaining = []
        for m in matches:
            home = m['match_hometeam_name']
            away = m['match_awayteam_name']
            home_lower = home.lower()
            away_lower = away.lower()

            found = False
            for key, val in odds_results.items():
                if (val['home_team'].lower() == home_lower and val['away_team'].lower() == away_lower) or \
                   (val['home_team'].lower() == away_lower and val['away_team'].lower() == home_lower):
                    found = True
                    break
            if not found:
                remaining.append(m)

        print(f'  Remaining: {len(remaining)} matches')

        # Try searching for each remaining match
        for m in remaining:
            home = m['match_hometeam_name']
            away = m['match_awayteam_name']

            # Try betexplorer search
            search_url = f'https://www.betexplorer.com/search/?q={home.replace(" ", "+")}+{away.replace(" ", "+")}'
            try:
                page.goto(search_url, wait_until='networkidle', timeout=15000)
                time.sleep(2)

                search_html = page.content()

                # Find match links in search results
                search_match_pattern = r'href="(/football/[^"]+/[^"]+/[^"]+/)"'
                search_urls = re.findall(search_match_pattern, search_html)

                for su in search_urls[:3]:
                    try:
                        full_url = f'https://www.betexplorer.com{su}'
                        page.goto(full_url, wait_until='networkidle', timeout=15000)
                        time.sleep(2)

                        mhtml = page.content()

                        # Check if this is the right match
                        if home.lower() in mhtml.lower() and away.lower() in mhtml.lower():
                            odds = extract_odds_from_match_page(page)
                            if odds:
                                key = f'{home}|{away}'
                                odds_results[key] = {
                                    'home_team': home,
                                    'away_team': away,
                                    **odds,
                                    'source': 'betexplorer',
                                }
                                print(f'    Search: {home} vs {away}: {odds}')
                                break
                    except:
                        continue
            except:
                continue

        browser.close()

    # Build final odds data by matching to our match list
    final_data = []
    for m in matches:
        home = m['match_hometeam_name']
        away = m['match_awayteam_name']
        date = m['match_date']
        home_score = m.get('match_hometeam_score', '')
        away_score = m.get('match_awayteam_score', '')

        entry = {
            'date': date,
            'home_team': home,
            'away_team': away,
            'home_score': home_score,
            'away_score': away_score,
        }

        # Find matching odds
        for key, val in odds_results.items():
            if (val['home_team'].lower() == home.lower() and val['away_team'].lower() == away.lower()) or \
               (val['home_team'].lower() == away.lower() and val['away_team'].lower() == home.lower()):
                entry['odds_home'] = val['odds_home']
                entry['odds_draw'] = val['odds_draw']
                entry['odds_away'] = val['odds_away']
                entry['source'] = val.get('source', 'betexplorer')
                break

        final_data.append(entry)

    return final_data

# Run for both years
for year in [2022, 2018]:
    odds_data = scrape_wc_odds(year)
    has_odds = sum(1 for m in odds_data if 'odds_home' in m)
    print(f'\nWC {year}: {len(odds_data)} matches, {has_odds} with odds')

    for m in odds_data[:5]:
        if 'odds_home' in m:
            print(f'  {m["date"]} {m["home_team"]} vs {m["away_team"]} {m["home_score"]}:{m["away_score"]} odds: {m["odds_home"]}/{m["odds_draw"]}/{m["odds_away"]}')
        else:
            print(f'  {m["date"]} {m["home_team"]} vs {m["away_team"]} (no odds)')

    # Save
    out_file = f'{ODDS_DIR}/wc_{year}_odds.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(odds_data, f, ensure_ascii=False, indent=2)
    print(f'  Saved to {out_file}')
