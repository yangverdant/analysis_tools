"""Scrape real historical odds from oddsportal.com for WC 2018 & 2022 using Playwright."""
import json, re, time, sys, os
sys.stdout.reconfigure(encoding='utf-8')

ODDS_DIR = 'data/world_cup'
os.makedirs(ODDS_DIR, exist_ok=True)

def scrape_oddsportal_wc(year):
    """Scrape oddsportal for WC odds using Playwright."""
    url = f'https://www.oddsportal.com/football/world/world-cup-{year}/results/'

    print(f'Scraping oddsportal for WC {year}: {url}')

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Set a realistic viewport
        page.set_viewport_size({'width': 1280, 'height': 800})

        print(f'  Navigating to {url}...')
        page.goto(url, wait_until='networkidle', timeout=60000)
        time.sleep(3)  # Extra wait for JS rendering

        # Try to accept cookies if popup exists
        try:
            accept_btn = page.locator('#onetrust-accept-btn-handler')
            if accept_btn.is_visible(timeout=3000):
                accept_btn.click()
                time.sleep(2)
        except:
            pass

        # Get the rendered HTML
        html = page.content()
        print(f'  Page size: {len(html)} chars')

        # Extract match data from the rendered page
        # oddsportal puts match rows in table with class 'table-main'
        matches = []

        # Find all match rows
        rows = page.locator('tr[data-eventid]').all()
        print(f'  Match rows found: {len(rows)}')

        if not rows:
            # Try alternative selectors
            rows = page.locator('table.table-main tbody tr').all()
            print(f'  Alternative rows: {len(rows)}')

        for row in rows:
            try:
                # Get match link and teams
                link_el = row.locator('a[href*="/match/"]').first
                if not link_el.is_visible(timeout=2000):
                    continue

                match_url = link_el.get_attribute('href') or ''
                match_text = link_el.inner_text() or ''

                # Parse team names from match text
                # Format like "Qatar - Ecuador" or "Qatar vs Ecuador"
                teams = re.split(r'\s*[-–vs]\s*', match_text.strip())
                if len(teams) < 2:
                    continue

                home_team = teams[0].strip()
                away_team = teams[1].strip()

                # Get score
                score_el = row.locator('td[class*="score"]').first
                score_text = score_el.inner_text() if score_el.is_visible(timeout=1000) else ''

                # Get 1X2 odds from data-odd attributes or text
                odds_cells = row.locator('td[data-odd]').all()
                odds_values = []
                for cell in odds_cells:
                    odd_val = cell.get_attribute('data-odd') or cell.inner_text()
                    odds_values.append(odd_val.strip())

                # If no data-odd, try text-based extraction
                if len(odds_values) < 3:
                    # Look for odds in td cells with specific classes
                    all_tds = row.locator('td').all()
                    for td in all_tds:
                        text = td.inner_text().strip()
                        if re.match(r'^\d+\.\d{1,2}$', text):
                            odds_values.append(text)

                match_data = {
                    'home_team': home_team,
                    'away_team': away_team,
                    'score': score_text,
                    'match_url': match_url,
                    'odds': odds_values[:3] if len(odds_values) >= 3 else odds_values,
                }
                matches.append(match_data)

            except Exception as e:
                continue

        # Also try getting match URLs for detailed odds (per-match page)
        print(f'  Extracted {len(matches)} matches with basic data')

        # Now visit each match page for full odds
        detailed_matches = []
        for i, m in enumerate(matches[:5]):  # Start with 5 matches to test
            match_url = m['match_url']
            if not match_url:
                continue

            full_url = f'https://www.oddsportal.com{match_url}' if match_url.startswith('/') else match_url

            print(f'  Visiting match {i+1}: {m["home_team"]} vs {m["away_team"]}')
            try:
                page.goto(full_url, wait_until='networkidle', timeout=30000)
                time.sleep(2)

                # Get 1X2 odds from the match detail page
                # oddsportal shows odds in a table with bookmakers
                detail_html = page.content()

                # Find odds table
                odds_table = page.locator('table.table-main').first
                if odds_table.is_visible(timeout=3000):
                    bookmaker_rows = odds_table.locator('tbody tr').all()
                    for bk_row in bookmaker_rows[:3]:  # Get first few bookmakers
                        bk_name = bk_row.locator('td:first-child a').inner_text() if bk_row.locator('td:first-child a').is_visible(timeout=500) else ''
                        bk_odds = bk_row.locator('td[data-odd]').all()
                        bk_odds_vals = [td.get_attribute('data-odd') or td.inner_text() for td in bk_odds[:3]]
                        print(f'    {bk_name}: {bk_odds_vals}')
            except Exception as e:
                print(f'    Error visiting match: {e}')

        browser.close()

    return matches

for year in [2022, 2018]:
    matches = scrape_oddsportal_wc(year)
    print(f'\nWC {year} total matches scraped: {len(matches)}')
    for m in matches[:5]:
        print(f'  {m["home_team"]} vs {m["away_team"]} score={m["score"]} odds={m["odds"]}')

    # Save
    out_file = f'{ODDS_DIR}/wc_{year}_odds_oddsportal.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    print(f'  Saved to {out_file}')