"""
直接获取apifootball 5/31全部赛果 - 用get_livescores看实时状态
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

# 方法1: get_livescores看当前状态
print("=" * 70)
print("  apifootball get_livescores (当前)")
print("=" * 70)

r = session.get(f'{api_url}/', params={
    'action': 'get_livescores',
    'APIkey': api_key,
}, timeout=30)
data = r.json()

if isinstance(data, list):
    for ev in data:
        home = ev.get('match_hometeam_name', '')
        away = ev.get('match_awayteam_name', '')
        hs = ev.get('match_hometeam_score', '')
        as_ = ev.get('match_awayteam_score', '')
        status = ev.get('match_status', '')
        league = ev.get('league_name', '')
        date = ev.get('match_date', '')

        print(f'  [{date}] [{league}] {home} {hs}:{as_} {away} [{status}]')
else:
    print(f'  返回: {data}')

# 方法2: get_events for specific leagues on 5/31
print()
print("=" * 70)
print("  apifootball get_events (5/31) - 逐联赛")
print("=" * 70)

target_leagues = [
    (209, '日职J1'),
    (307, '瑞超'),
    (352, '芬超'),
    # 国际赛没有统一league_id, 搜索常见的
    (678, '国际友谊赛A'),
    (679, '国际友谊赛B'),
    (680, '国际友谊赛C'),
    (10, 'World Cup'),
    (764, 'International'),
]

for league_id, league_cn in target_leagues:
    try:
        r = session.get(f'{api_url}/', params={
            'action': 'get_events',
            'from': '2026-05-31',
            'to': '2026-05-31',
            'APIkey': api_key,
            'league_id': league_id,
        }, timeout=15)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            print(f'\n  [{league_cn}] id={league_id}: {len(data)}场')
            for ev in data:
                home = ev.get('match_hometeam_name', '')
                away = ev.get('match_awayteam_name', '')
                hs = ev.get('match_hometeam_score', '')
                as_ = ev.get('match_awayteam_score', '')
                status = ev.get('match_status', '')
                print(f'    {home} {hs}:{as_} {away} [{status}]')
        elif isinstance(data, dict):
            msg = data.get('message', str(data))
            if 'no data' not in msg.lower() and 'error' not in msg.lower():
                print(f'  [{league_cn}] id={league_id}: {msg[:80]}')
    except Exception as e:
        print(f'  [{league_cn}] id={league_id}: {e}')

# 方法3: 搜索所有联赛5/31的比赛
print()
print("=" * 70)
print("  apifootball get_events (5/31) - 全联赛搜索")
print("=" * 70)

try:
    r = session.get(f'{api_url}/', params={
        'action': 'get_events',
        'from': '2026-05-31',
        'to': '2026-05-31',
        'APIkey': api_key,
    }, timeout=30)
    data = r.json()
    if isinstance(data, list):
        # 找关键比赛
        keywords = ['Japan', 'Iceland', 'Hacken', 'Hammarby', 'Vasteras', 'Goteborg',
                     'Degerfors', 'Bromma', 'Oulu', 'Jaro', 'Czech', 'Kosovo',
                     'USA', 'Senegal', 'Okayama', 'Urawa', 'Shimizu', 'Yokohama']
        found = 0
        for ev in data:
            home = ev.get('match_hometeam_name', '')
            away = ev.get('match_awayteam_name', '')
            for kw in keywords:
                if kw.lower() in home.lower() or kw.lower() in away.lower():
                    hs = ev.get('match_hometeam_score', '')
                    as_ = ev.get('match_awayteam_score', '')
                    status = ev.get('match_status', '')
                    league = ev.get('league_name', '')
                    print(f'  [{league}] {home} {hs}:{as_} {away} [{status}]')
                    found += 1
                    break
        print(f'\n  找到{found}场相关比赛')
    elif isinstance(data, dict):
        print(f'  返回: {str(data)[:200]}')
except Exception as e:
    print(f'  获取失败: {e}')
