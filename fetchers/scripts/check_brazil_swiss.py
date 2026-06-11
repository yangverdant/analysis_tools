"""
检查今日体彩所有比赛 - 找巴西和瑞士
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

# 尝试不同日期
for date_str, label in [('2026-06-01', '6/1'), ('2026-06-02', '6/2'), ('', '默认')]:
    params = {'sellStatus': 'on'}
    if date_str:
        params['date'] = date_str

    r = session.get('https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry',
        params=params, timeout=30)
    data = r.json()

    print(f'\n{"="*70}')
    print(f'  日期={label} 的全部比赛')
    print(f'{"="*70}')

    for dg in data.get('value', {}).get('matchInfoList', []):
        for m in dg.get('subMatchList', []):
            num = str(m.get('matchNum', ''))
            num_str = m.get('matchNumStr', '')
            league = m.get('leagueAbbName', '')
            home = m.get('homeTeamAllName', '') or m.get('homeTeamAbbName', '')
            away = m.get('awayTeamAllName', '') or m.get('awayTeamAbbName', '')
            time = m.get('matchTime', '')[:5]

            had = m.get('had', {})
            oh = float(had.get('h', 0) or 0)
            od = float(had.get('d', 0) or 0)
            oa = float(had.get('a', 0) or 0)

            hhad = m.get('hhad', {})
            hc = hhad.get('goalLine', '')
            rqh = float(hhad.get('h', 0) or 0)
            rqd = float(hhad.get('d', 0) or 0)
            rqa = float(hhad.get('a', 0) or 0)

            odds_str = f'{oh:.2f}/{od:.2f}/{oa:.2f}' if oh else '未出'
            rq_str = f' 让{hc} {rqh:.2f}/{rqd:.2f}/{rqa:.2f}' if rqh else ''

            # 高亮巴西/瑞士
            highlight = ''
            if any(kw in home+away for kw in ['巴西','瑞士','Brazil','Switzerland','巴拉圭','Paraguay']):
                highlight = ' ★★★'

            print(f'{num_str:8s} [{league:6s}] {time} {home} vs {away}  SPF:{odds_str}{rq_str}{highlight}')
