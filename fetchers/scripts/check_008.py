"""检查008的home/away字段"""
import sys, io, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import urllib3
urllib3.disable_warnings()

session = requests.Session()
session.trust_env = False
session.verify = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.sporttery.cn/',
})

r = session.get('https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry',
    params={'sellStatus': 'on'}, timeout=30)
data = r.json()

for dg in data.get('value', {}).get('matchInfoList', []):
    for m in dg.get('subMatchList', []):
        num = str(m.get('matchNum', ''))
        if num == '7008':
            print(f"home: '{m.get('homeTeamAllName', '')}' / '{m.get('homeTeamAbbName', '')}'")
            print(f"away: '{m.get('awayTeamAllName', '')}' / '{m.get('awayTeamAbbName', '')}'")
            print(f"league: '{m.get('leagueAbbName', '')}'")
