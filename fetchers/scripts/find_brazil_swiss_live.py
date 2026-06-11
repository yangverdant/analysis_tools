"""
查今天实时进行的比赛 + 搜索国际友谊赛
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

# 1. 当前实时比赛
print("=" * 70)
print("  当前实时比赛 (apifootball livescores)")
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
        time_ = ev.get('match_time', '')

        highlight = ''
        for kw in ['Brazil', 'Switzerland', 'Germany', 'Panama', 'Jordan', 'Finland',
                     'Brasil', 'Suisse', 'Deutschland']:
            if kw.lower() in home.lower() or kw.lower() in away.lower():
                highlight = ' ★★★'
                break

        print(f'  [{date} {time_}] [{league}] {home} {hs}:{as_} {away} [{status}]{highlight}')
    print(f'\n  总计: {len(data)}场')
else:
    print(f'  返回: {data}')

# 2. 搜索5/31+6/1的全部国际赛
print()
print("=" * 70)
print("  5/31+6/1 全部国际友谊赛 (get_events)")
print("=" * 70)

for date in ['2026-05-31', '2026-06-01']:
    r = session.get(f'{api_url}/', params={
        'action': 'get_events',
        'from': date,
        'to': date,
        'APIkey': api_key,
    }, timeout=30)
    data = r.json()

    if isinstance(data, list):
        internationals = [ev for ev in data
                         if any(kw in (ev.get('league_name','') + ev.get('match_hometeam_name','') + ev.get('match_awayteam_name',''))
                                for kw in ['International', 'Friendly', 'World', 'Brazil', 'Switzerland', 'Germany',
                                           'Panama', 'Jordan', 'Finland', 'Brasil', 'Deutschland'])]
        if internationals:
            print(f'\n  日期: {date} ({len(internationals)}场)')
            for ev in internationals:
                home = ev.get('match_hometeam_name', '')
                away = ev.get('match_awayteam_name', '')
                hs = ev.get('match_hometeam_score', '')
                as_ = ev.get('match_awayteam_score', '')
                status = ev.get('match_status', '')
                league = ev.get('league_name', '')
                print(f'    [{league}] {home} {hs}:{as_} {away} [{status}]')

# 3. 用ESPN查今天的足球赛果
print()
print("=" * 70)
print("  ESPN 6/1 国际赛赛果")
print("=" * 70)

for league_id in ['fifa.friendly', 'fifa.worldq.uefa', 'fifa.worldq.conmebol']:
    try:
        url = f'https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard'
        r = session.get(url, params={'date': '20260601'}, timeout=15)
        data = r.json()
        events = data.get('events', [])
        if events:
            print(f'\n  [{league_id}] {len(events)}场')
            for ev in events:
                comps = ev.get('competitions', [])
                if not comps: continue
                comp = comps[0]
                home_team = away_team = ''
                home_score = away_score = 0
                for c in comp.get('competitors', []):
                    if c.get('homeAway') == 'home':
                        home_team = c.get('team', {}).get('displayName', '')
                        home_score = int(c.get('score', 0) or 0)
                    else:
                        away_team = c.get('team', {}).get('displayName', '')
                        away_score = int(c.get('score', 0) or 0)
                status = comp.get('status', {}).get('type', {}).get('name', '')
                print(f'    {home_team} {home_score}:{away_score} {away_team} [{status}]')
    except Exception as e:
        print(f'  {league_id}: {e}')

# 4. 也试5/31的ESPN
print()
print("=" * 70)
print("  ESPN 5/31 国际赛赛果")
print("=" * 70)

for league_id in ['fifa.friendly', 'fifa.worldq.uefa', 'fifa.worldq.conmebol']:
    try:
        url = f'https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard'
        r = session.get(url, params={'date': '20260531'}, timeout=15)
        data = r.json()
        events = data.get('events', [])
        if events:
            print(f'\n  [{league_id}] {len(events)}场')
            for ev in events:
                comps = ev.get('competitions', [])
                if not comps: continue
                comp = comps[0]
                home_team = away_team = ''
                home_score = away_score = 0
                for c in comp.get('competitors', []):
                    if c.get('homeAway') == 'home':
                        home_team = c.get('team', {}).get('displayName', '')
                        home_score = int(c.get('score', 0) or 0)
                    else:
                        away_team = c.get('team', {}).get('displayName', '')
                        away_score = int(c.get('score', 0) or 0)
                status = comp.get('status', {}).get('type', {}).get('name', '')
                print(f'    {home_team} {home_score}:{away_score} {away_team} [{status}]')
    except Exception as e:
        print(f'  {league_id}: {e}')
