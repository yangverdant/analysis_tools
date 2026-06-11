"""
检查澳超季后赛数据 - 尝试不同日期范围
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

print("Checking A-League data availability...")
print("=" * 60)

# 检查不同日期范围
date_ranges = [
    ("2025-05-01", "2025-05-31"),
    ("2025-06-01", "2025-06-30"),
    ("2025-07-01", "2025-07-31"),
    ("2025-10-01", "2026-05-31"),
    ("2026-01-01", "2026-05-31"),
]

for from_date, to_date in date_ranges:
    fixtures = fetch_api("get_events", {
        "league_id": 49,
        "from": from_date,
        "to": to_date
    })

    if fixtures and isinstance(fixtures, list):
        print(f"\n{from_date} to {to_date}: {len(fixtures)} matches")
        if len(fixtures) > 0:
            # 显示最后几场
            for f in fixtures[-3:]:
                print(f"  {f.get('match_date')}: {f.get('match_hometeam_name')} vs {f.get('match_awayteam_name')}")
    else:
        print(f"\n{from_date} to {to_date}: No data")

print("\n" + "=" * 60)
print("Note: A-League season runs October to May")
print("2025-26 season should have finals in May 2026")
print("API may not have future playoff data yet")