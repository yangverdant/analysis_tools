"""
从多个源获取5/31全部赛果
"""
import sys, io, requests, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import urllib3
urllib3.disable_warnings()

session = requests.Session()
session.trust_env = False
session.verify = False

# 1. ESPN - 搜索各联赛5/31赛果
print("=" * 70)
print("  ESPN 5/31赛果")
print("=" * 70)

leagues_espn = {
    'jpn.1': '日职',
    'swe.1': '瑞超',
    'fin.1': '芬超',
    'fifa.friendly': '国际赛',
}

espn_results = {}
for league_id, league_cn in leagues_espn.items():
    try:
        url = f'https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard'
        r = session.get(url, params={'date': '20260531'}, timeout=15)
        data = r.json()
        for ev in data.get('events', []):
            comps = ev.get('competitions', [])
            if not comps: continue
            comp = comps[0]
            status_type = comp.get('status', {}).get('type', {}).get('name', '')
            if status_type != 'Status.Full': continue  # 只看完赛的

            home_team = ''
            away_team = ''
            home_score = 0
            away_score = 0

            for competitor in comp.get('competitors', []):
                if competitor.get('homeAway') == 'home':
                    home_team = competitor.get('team', {}).get('displayName', '')
                    home_score = int(competitor.get('score', 0) or 0)
                else:
                    away_team = competitor.get('team', {}).get('displayName', '')
                    away_score = int(competitor.get('score', 0) or 0)

            result = 'H' if home_score > away_score else ('D' if home_score == away_score else 'A')
            print(f'  [{league_cn}] {home_team} {home_score}:{away_score} {away_team} -> {result}')
            espn_results[home_team] = {'hs': home_score, 'as': away_score, 'result': result, 'league': league_cn}
    except Exception as e:
        print(f'  {league_cn}: 获取失败 {e}')

# 2. apifootball - 获取更多联赛
print()
print("=" * 70)
print("  apifootball 5/31赛果")
print("=" * 70)

api_key = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"
api_url = 'https://apiv3.apifootball.com'

# 瑞超=307, 芬超=352, 日职=209
api_results = {}
for league_id, league_cn in [(307,'瑞超'), (352,'芬超'), (209,'日职')]:
    try:
        r = session.get(f'{api_url}/', params={
            'action': 'get_events',
            'from': '2026-05-31',
            'to': '2026-05-31',
            'APIkey': api_key,
            'league_id': league_id,
        }, timeout=30)
        data = r.json()
        if isinstance(data, list):
            for ev in data:
                home = ev.get('match_hometeam_name', '')
                away = ev.get('match_awayteam_name', '')
                hs = ev.get('match_hometeam_score', '')
                as_ = ev.get('match_awayteam_score', '')
                status = ev.get('match_status', '')

                # 显示所有比赛状态
                if hs and as_:
                    try:
                        hs_i, as_i = int(hs), int(as_)
                        result = 'H' if hs_i > as_i else ('D' if hs_i == as_i else 'A')
                        print(f'  [{league_cn}] {home} {hs}:{as_} {away} [{status}] -> {result}')
                        if status == 'Finished':
                            api_results[home] = {'hs': hs_i, 'as': as_i, 'result': result, 'league': league_cn}
                    except:
                        print(f'  [{league_cn}] {home} vs {away} [{status}] 比分解析失败')
                else:
                    print(f'  [{league_cn}] {home} vs {away} [{status}]')
    except Exception as e:
        print(f'  {league_cn}: 获取失败 {e}')

# 3. 尝试获取国际赛友谊赛
print()
print("  国际友谊赛赛果:")
# 搜索近期已完赛的国际赛
try:
    r = session.get(f'{api_url}/', params={
        'action': 'get_events',
        'from': '2026-05-31',
        'to': '2026-05-31',
        'APIkey': api_key,
        'league_id': 10,  # 国际赛可能没有统一ID
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
            if hs and as_ and status == 'Finished':
                hs_i, as_i = int(hs), int(as_)
                result = 'H' if hs_i > as_i else ('D' if hs_i == as_i else 'A')
                print(f'  [{league}] {home} {hs}:{as_} {away} -> {result}')
                api_results[home] = {'hs': hs_i, 'as': as_i, 'result': result, 'league': league}
    elif isinstance(data, dict):
        print(f'  API返回: {data.get("message", "unknown error")}')
except Exception as e:
    print(f'  获取失败: {e}')

# 合并所有结果
all_results = {**espn_results, **api_results}

print()
print("=" * 70)
print(f"  共获取到 {len(all_results)} 场5/31赛果")
print("=" * 70)

# 保存
with open('d:/football_tools/data/results_0531.json', 'w', encoding='utf-8') as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)
