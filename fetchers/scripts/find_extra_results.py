"""
获取5/31未验证的比赛赛果: 瑞士vs约旦、德国vs芬兰、巴西vs巴拿马
"""
import sys, io, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import urllib3
urllib3.disable_warnings()

api_key = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"
api_url = 'https://apiv3.apifootball.com'

session = requests.Session()
session.trust_env = False
session.verify = False

print("=" * 70)
print("  5/31全部友谊赛赛果 (apifootball)")
print("=" * 70)

# 用get_events搜索5/31全部比赛, 找友谊赛
r = session.get(f'{api_url}/', params={
    'action': 'get_events',
    'from': '2026-05-31',
    'to': '2026-05-31',
    'APIkey': api_key,
}, timeout=30)
data = r.json()

if isinstance(data, list):
    # 找所有友谊赛
    friendlies = []
    keywords = ['Switzerland', 'Jordan', 'Germany', 'Finland', 'Brazil', 'Panama',
                 'Swiss', 'Suisse', 'Schweiz', 'Brasil', 'Deutschland', 'Alemanha']

    for ev in data:
        home = ev.get('match_hometeam_name', '')
        away = ev.get('match_awayteam_name', '')
        hs = ev.get('match_hometeam_score', '')
        as_ = ev.get('match_awayteam_score', '')
        status = ev.get('match_status', '')
        league = ev.get('league_name', '')

        # 搜索包含关键词的比赛
        is_target = False
        for kw in keywords:
            if kw.lower() in home.lower() or kw.lower() in away.lower():
                is_target = True
                break

        # 也找所有Friendly International
        if 'Friendly' in league or 'International' in league:
            is_target = True

        if is_target:
            result_str = f'{hs}:{as_}' if hs and as_ else '未完赛'
            print(f'  [{league}] {home} {result_str} {away} [{status}]')
            friendlies.append(ev)

    print(f'\n  找到 {len(friendlies)} 场友谊赛/国际赛')

    # 特别搜索目标比赛
    print()
    print("=" * 70)
    print("  特别搜索: 瑞士vs约旦 / 德国vs芬兰 / 巴西vs巴拿马")
    print("=" * 70)

    for ev in data:
        home = ev.get('match_hometeam_name', '')
        away = ev.get('match_awayteam_name', '')
        hs = ev.get('match_hometeam_score', '')
        as_ = ev.get('match_awayteam_score', '')
        status = ev.get('match_status', '')
        league = ev.get('league_name', '')

        combined = home + ' ' + away
        targets = [
            ('Swiss' in combined or 'Switzerland' in combined or 'Jordan' in combined,
             '瑞士vs约旦'),
            ('Germany' in combined or 'Finland' in combined or 'Deutschland' in combined,
             '德国vs芬兰'),
            ('Brazil' in combined or 'Panama' in combined or 'Brasil' in combined,
             '巴西vs巴拿马'),
        ]

        for cond, label in targets:
            if cond:
                print(f'  {label}: [{league}] {home} {hs}:{as_} {away} [{status}]')
elif isinstance(data, dict):
    print(f'  API错误: {data}')

# 也搜索6/1的友谊赛(有些可能是5/31/6/1的)
print()
print("=" * 70)
print("  6/1友谊赛赛果")
print("=" * 70)

r = session.get(f'{api_url}/', params={
    'action': 'get_events',
    'from': '2026-06-01',
    'to': '2026-06-01',
    'APIkey': api_key,
}, timeout=30)
data2 = r.json()

if isinstance(data2, list):
    for ev in data2:
        home = ev.get('match_hometeam_name', '')
        away = ev.get('match_awayteam_name', '')
        hs = ev.get('match_hometeam_score', '')
        as_ = ev.get('match_awayteam_score', '')
        status = ev.get('match_status', '')
        league = ev.get('league_name', '')

        combined = home + ' ' + away
        targets = [
            ('Swiss' in combined or 'Switzerland' in combined or 'Jordan' in combined,
             '瑞士vs约旦'),
            ('Germany' in combined or 'Finland' in combined or 'Deutschland' in combined,
             '德国vs芬兰'),
            ('Brazil' in combined or 'Panama' in combined or 'Brasil' in combined,
             '巴西vs巴拿马'),
            ('Friendly' in league or 'International' in league,
             f'[{league}] {home} vs {away}'),
        ]

        for cond, label in targets:
            if cond:
                result_str = f'{hs}:{as_}' if hs and as_ else '比分未出'
                print(f'  {label}: {result_str} [{status}]')