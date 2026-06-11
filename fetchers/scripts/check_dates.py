"""
尝试不同date参数获取体彩比赛
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
dates = ['2026-05-31', '2026-06-01', '']

for date in dates:
    params = {'sellStatus': 'on'}
    if date:
        params['date'] = date

    r = session.get('https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry',
        params=params, timeout=30)
    data = r.json()

    nums = []
    for dg in data.get('value', {}).get('matchInfoList', []):
        for m in dg.get('subMatchList', []):
            num = str(m.get('matchNum', ''))
            num_str = m.get('matchNumStr', '')
            nums.append(num_str)

    print(f"date={date or '无'}: {len(nums)}场 - {nums}")
