"""Scrape real WC 2018/2022 closing 1X2 odds from flashscore.com.

Flashscore shows closing odds on each match detail page.
We extract them from the rendered page text.
"""
import json, re, time, sys, os
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding='utf-8')

ODDS_DIR = 'data/world_cup'

def scrape_flashscore_wc_odds(year):
    """Scrape flashscore for WC closing odds."""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Step 1: Get all match IDs from results page
        url = f'https://www.flashscore.com/football/world/world-cup-{year}/results/'
        page.goto(url, wait_until='networkidle', timeout=60000)
        time.sleep(5)

        try:
            btn = page.locator('#onetrust-accept-btn-handler')
            if btn.is_visible(timeout=3000):
                btn.click()
                time.sleep(1)
        except:
            pass

        # Load all matches
        for i in range(10):
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(1)

        for i in range(10):
            try:
                show_more = page.locator('a:has-text("Show more")')
                if show_more.count() > 0 and show_more.first.is_visible(timeout=2000):
                    show_more.first.click()
                    time.sleep(2)
                else:
                    break
            except:
                break

        html = page.content()
        match_ids = list(dict.fromkeys(re.findall(r'id="g_1_([^"]+)"', html)))
        print(f'WC {year}: Found {len(match_ids)} match IDs')

        # Step 2: Visit each match page and extract closing 1X2 odds
        odds_data = []

        for i, mid in enumerate(match_ids):
            try:
                match_url = f'https://www.flashscore.com/match/{mid}/'
                page.goto(match_url, wait_until='networkidle', timeout=20000)
                time.sleep(3)

                # Get team names from title
                title = page.title()
                teams_match = re.match(r'(.+?)\s+v\s+(.+?)\s+\d', title)
                home = teams_match.group(1).strip() if teams_match else ''
                away = teams_match.group(2).strip() if teams_match else ''

                # Get body text
                body = page.inner_text('body')

                # Extract 1X2 closing odds
                # Pattern 1: "1X2" followed by 3 decimal numbers
                odds_home = odds_draw = odds_away = None

                # Find 1X2 in the body text
                idx_1x2 = body.find('1X2')
                if idx_1x2 < 0:
                    idx_1x2 = body.find('1x2')

                if idx_1x2 >= 0:
                    # Get text after 1X2 header
                    section = body[idx_1x2:idx_1x2+200]
                    # Find 3 consecutive decimal numbers
                    nums = re.findall(r'\b(\d{1,2}\.\d{1,2})\b', section)
                    if len(nums) >= 3:
                        odds_home = float(nums[0])
                        odds_draw = float(nums[1])
                        odds_away = float(nums[2])

                # Pattern 2: Look for "Closing" or "Average" followed by odds
                if not odds_home:
                    for keyword in ['Closing odds', 'Average odds', 'Opening odds']:
                        idx = body.find(keyword)
                        if idx >= 0:
                            section = body[idx:idx+200]
                            nums = re.findall(r'\b(\d{1,2}\.\d{1,2})\b', section)
                            if len(nums) >= 3:
                                odds_home = float(nums[0])
                                odds_draw = float(nums[1])
                                odds_away = float(nums[2])
                                break

                # Pattern 3: Look for odds in specific CSS class patterns
                if not odds_home:
                    mhtml = page.content()
                    # Find oddsValue or similar
                    odds_from_html = re.findall(r'class="[^"]*odds[^"]*"[^>]*>(\d{1,2}\.\d{1,2})<', mhtml)
                    if len(odds_from_html) >= 3:
                        odds_home = float(odds_from_html[0])
                        odds_draw = float(odds_from_html[1])
                        odds_away = float(odds_from_html[2])

                entry = {
                    'home_team': home,
                    'away_team': away,
                    'match_id': mid,
                }

                if odds_home and odds_draw and odds_away:
                    entry['odds_home'] = odds_home
                    entry['odds_draw'] = odds_draw
                    entry['odds_away'] = odds_away
                    entry['source'] = 'flashscore'
                    print(f'  [{i+1}/{len(match_ids)}] {home} vs {away}: {odds_home}/{odds_draw}/{odds_away}')
                else:
                    entry['source'] = 'no_odds'
                    print(f'  [{i+1}/{len(match_ids)}] {home} vs {away}: no odds')

                odds_data.append(entry)

            except Exception as e:
                odds_data.append({
                    'match_id': mid,
                    'source': f'error: {str(e)[:50]}',
                })
                print(f'  [{i+1}/{len(match_ids)}] Error: {str(e)[:50]}')

        browser.close()

    return odds_data

# Run for both years
for year in [2022, 2018]:
    odds_data = scrape_flashscore_wc_odds(year)
    has_odds = sum(1 for m in odds_data if 'odds_home' in m)
    print(f'\nWC {year}: {len(odds_data)} matches, {has_odds} with odds')

    # Save
    out_file = f'{ODDS_DIR}/wc_{year}_odds_flashscore.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(odds_data, f, ensure_ascii=False, indent=2)
    print(f'  Saved to {out_file}')
