"""
检查体彩API返回的所有比赛编号
"""
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

print("=" * 60)
print("  体彩API返回的所有比赛编号")
print("=" * 60)

all_nums = []
for dg in data.get('value', {}).get('matchInfoList', []):
    for m in dg.get('subMatchList', []):
        raw_num = m.get('matchNum', '')
        num = str(raw_num) if raw_num else ''
        num_str = m.get('matchNumStr', '')
        league = m.get('leagueAbbName', '')
        home = m.get('homeTeamAllName', '') or m.get('homeTeamAbbName', '')
        away = m.get('awayTeamAllName', '') or m.get('awayTeamAbbName', '')
        time = m.get('matchTime', '')[:5]

        had = m.get('had', {})
        oh = float(had.get('h', 0) or 0)
        od = float(had.get('d', 0) or 0)
        oa = float(had.get('a', 0) or 0)

        odds_str = f'{oh:.2f}/{od:.2f}/{oa:.2f}' if oh else '未出'

        all_nums.append(num)
        print(f'{num_str:8s} [{league:6s}] {time} {home} vs {away}  赔率:{odds_str}')

print()
print(f"总计: {len(all_nums)} 场")
print(f"编号: {sorted(set(all_nums))}")
