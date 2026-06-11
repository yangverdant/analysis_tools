"""临时测试脚本"""
import sys, json, requests, urllib3
sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings()

session = requests.Session()
session.trust_env = False
session.verify = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.sporttery.cn/',
    'Origin': 'https://www.sporttery.cn',
})

for d in ['2026-06-02', '2026-06-03']:
    print(f'\n=== {d} ===')
    resp = session.get('https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry',
        params={'sellStatus': 'off', 'date': d}, timeout=10)
    data = json.loads(resp.text)

    for date_info in data.get('value', {}).get('matchInfoList', []):
        for item in date_info.get('subMatchList', []):
            league = item.get('leagueAbbName', '')
            home = item.get('homeTeamAllName', '')
            away = item.get('awayTeamAllName', '')
            had = item.get('had', {})
            spf = f'{had.get("h","?")}/{had.get("d","?")}/{had.get("a","?")}' if had else '无'
            print(f'{league:6} | {home} vs {away} | SPF={spf}')
