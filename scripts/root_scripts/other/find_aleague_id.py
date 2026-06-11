"""
查找正确的澳超API ID
"""

import json
import ssl
import urllib.request

API_KEY = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"
BASE_URL = "https://apiv3.apifootball.com"

def fetch_api(action: str, params: dict) -> dict:
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        url = f"{BASE_URL}?action={action}&{param_str}&APIkey={API_KEY}"

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"API error: {e}")
        return None

# 获取所有联赛
print("Finding A-League API ID...")
leagues = fetch_api("get_leagues", {})

if leagues:
    for league in leagues:
        name = league.get('league_name', '').lower()
        # 查找澳大利亚联赛
        if 'a-league' in name or 'australia' in name or 'aleague' in name.replace('-', '').replace(' ', ''):
            print(f"ID: {league.get('league_id')}, Name: {league.get('league_name')}, Country: {league.get('country_name')}")