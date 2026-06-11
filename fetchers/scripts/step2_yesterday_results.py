"""
Step2: 获取昨日(5/31)赛果 + 用v3.9.2和v3.10分别预测，对比准确率
"""
import sys, io, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import urllib3
urllib3.disable_warnings()

# ===== 模型 =====
def predict_v392(oh, od, oa, league=''):
    if not oh or not od or not oa: return None
    hp, dp, ap = 1/oh, 1/od, 1/oa
    total = hp + dp + ap
    margin = total - 1
    hp, dp, ap = hp/total, dp/total, ap/total
    is_cup = any(kw in league for kw in ['欧冠','欧联','欧协','国际赛','友谊赛','解放者'])
    if is_cup:
        dp -= 0.02; nd = hp+ap
        if nd > 0: hp += 0.02*(hp/nd); ap += 0.02*(ap/nd)
    if dp >= 0.30:
        dp -= 0.01; nd = hp+ap
        if nd > 0: hp += 0.01*(hp/nd); ap += 0.01*(hp/nd)
    elif dp >= 0.28:
        dp += 0.01; nd = hp+ap
        if nd > 0: hp -= 0.01*(hp/nd); ap -= 0.01*(hp/nd)
    if oh and 1.25 <= oh <= 1.35:
        hp -= 0.02; dp += 0.01; ap += 0.01
    total = hp+dp+ap
    if total > 0: hp, dp, ap = hp/total, dp/total, ap/total
    pred = max(['H','D','A'], key=lambda x: {'H':hp,'D':dp,'A':ap}[x])
    conf = max(hp, dp, ap)
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf}

def predict_v310(oh, od, oa, league=''):
    if not oh or not od or not oa: return None
    hp, dp, ap = 1/oh, 1/od, 1/oa
    total = hp + dp + ap
    margin = total - 1
    hp, dp, ap = hp/total, dp/total, ap/total

    odds_list = [oh, od, oa]
    odds_range = max(odds_list) - min(odds_list)
    is_balanced = odds_range < 0.8

    is_cup = any(kw in league for kw in ['欧冠','欧联','欧协','国际赛','友谊赛','解放者'])
    if is_cup:
        dp -= 0.02; nd = hp+ap
        if nd > 0: hp += 0.02*(hp/nd); ap += 0.02*(ap/nd)

    if is_balanced and dp >= 0.28:
        boost = 0.04
        dp += boost; nd = hp+ap
        if nd > 0: hp -= boost*(hp/nd); ap -= boost*(ap/nd)
    elif not is_balanced:
        if dp >= 0.30:
            dp -= 0.01; nd = hp+ap
            if nd > 0: hp += 0.01*(hp/nd); ap += 0.01*(hp/nd)
        elif dp >= 0.28:
            dp += 0.01; nd = hp+ap
            if nd > 0: hp -= 0.01*(hp/nd); ap -= 0.01*(hp/nd)

    if oh and 1.25 <= oh <= 1.35:
        hp -= 0.02; dp += 0.01; ap += 0.01

    total = hp+dp+ap
    if total > 0: hp, dp, ap = hp/total, dp/total, ap/total
    pred = max(['H','D','A'], key=lambda x: {'H':hp,'D':dp,'A':ap}[x])
    conf = max(hp, dp, ap)
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf,'is_balanced':is_balanced}

# ===== 昨日赛果 (5/31) =====
# 已知赛果 + 赔率
yesterday_matches = [
    {'num':'7001','home':'冈山绿雉','away':'浦和红钻','league':'日职',
     'oh':2.90,'od':3.00,'oa':2.22,'hs':1,'as':1,'actual':'D'},
    {'num':'7002','home':'清水鼓动','away':'横滨水手','league':'日职',
     'oh':2.52,'od':3.10,'oa':2.44,'hs':1,'as':1,'actual':'D'},
    {'num':'7003','home':'日本','away':'冰岛','league':'国际赛',
     'oh':1.12,'od':6.25,'oa':13.00,'hs':None,'as':None,'actual':None},
    {'num':'7004','home':'韦斯特罗斯','away':'IFK哥德堡','league':'瑞超',
     'oh':2.46,'od':3.00,'oa':2.57,'hs':None,'as':None,'actual':None},
    {'num':'7005','home':'赫根','away':'哈马比','league':'瑞超',
     'oh':2.77,'od':3.35,'oa':2.13,'hs':None,'as':None,'actual':None},
    {'num':'7006','home':'代格福什','away':'布鲁马波卡纳','league':'瑞超',
     'oh':2.10,'od':3.15,'oa':2.98,'hs':None,'as':None,'actual':None},
    {'num':'7008','home':'AC奥卢','away':'雅罗','league':'芬超',
     'oh':1.50,'od':3.90,'oa':4.85,'hs':None,'as':None,'actual':None},
    {'num':'7009','home':'捷克','away':'科索沃','league':'国际赛',
     'oh':1.52,'od':3.64,'oa':5.10,'hs':None,'as':None,'actual':None},
    {'num':'7011','home':'美国','away':'塞内加尔','league':'国际赛',
     'oh':2.43,'od':2.90,'oa':2.68,'hs':None,'as':None,'actual':None},
]

# 尝试从ESPN获取赛果
session = requests.Session()
session.trust_env = False
session.verify = False

print("=" * 85)
print("  5/31赛果获取 (ESPN API)")
print("=" * 85)

# 用ESPN获取5/31的比赛结果
try:
    espn_url = 'https://site.api.espn.com/apis/site/v2/sports/soccer/scoreboard'
    r = session.get(espn_url, params={'date': '20260531'}, timeout=30)
    espn_data = r.json()

    espn_results = {}
    for ev in espn_data.get('events', []):
        name = ev.get('name', '')
        competitions = ev.get('competitions', [])
        if not competitions: continue
        comp = competitions[0]
        status = comp.get('status', {}).get('type', {}).get('name', '')

        scores = {}
        for team in comp.get('competitors', []):
            tname = team.get('team', {}).get('displayName', '')
            score = team.get('score', '0')
            home_away = team.get('homeAway', '')
            scores[home_away] = {'name': tname, 'score': int(score) if score else 0}

        if 'home' in scores and 'away' in scores:
            hs = scores['home']['score']
            as_ = scores['away']['score']
            result = 'H' if hs > as_ else ('D' if hs == as_ else 'A')
            print(f'  {scores["home"]["name"]} {hs}:{as_} {scores["away"]["name"]} [{status}] -> {result}')
            espn_results[scores['home']['name']] = result
except Exception as e:
    print(f'  ESPN获取失败: {e}')
    espn_results = {}

# 尝试用apifootball获取赛果
print()
print("=" * 85)
print("  5/31赛果获取 (apifootball)")
print("=" * 85)

api_key = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"
try:
    # 获取今天的赛果(5/31)
    api_url = f'https://apiv3.apifootball.com'
    r = session.get(f'{api_url}/', params={
        'action': 'get_events',
        'from': '2026-05-31',
        'to': '2026-05-31',
        'APIkey': api_key,
        'league_id': 307,  # 瑞超
    }, timeout=30)
    api_data = r.json()

    api_results = {}
    if isinstance(api_data, list):
        for ev in api_data:
            home = ev.get('match_hometeam_name', '')
            away = ev.get('match_awayteam_name', '')
            hs = ev.get('match_hometeam_score', '')
            as_ = ev.get('match_awayteam_score', '')
            status = ev.get('match_status', '')
            league = ev.get('league_name', '')

            if hs and as_ and status == 'Finished':
                hs_i, as_i = int(hs), int(as_)
                result = 'H' if hs_i > as_i else ('D' if hs_i == as_i else 'A')
                print(f'  {home} {hs}:{as_} {away} [{league}] -> {result}')
                api_results[home] = result
    else:
        print(f'  API返回非列表: {type(api_data)}')
except Exception as e:
    print(f'  apifootball获取失败: {e}')
    api_results = {}

# 再获取芬超和日职的赛果
for league_id, league_name in [(352, '芬超'), (209, '日职'), (10, '国际赛')]:
    try:
        r = session.get(f'{api_url}/', params={
            'action': 'get_events',
            'from': '2026-05-31',
            'to': '2026-05-31',
            'APIkey': api_key,
            'league_id': league_id,
        }, timeout=30)
        api_data = r.json()
        if isinstance(api_data, list):
            for ev in api_data:
                home = ev.get('match_hometeam_name', '')
                away = ev.get('match_awayteam_name', '')
                hs = ev.get('match_hometeam_score', '')
                as_ = ev.get('match_awayteam_score', '')
                status = ev.get('match_status', '')
                if hs and as_ and status == 'Finished':
                    hs_i, as_i = int(hs), int(as_)
                    result = 'H' if hs_i > as_i else ('D' if hs_i == as_i else 'A')
                    print(f'  {home} {hs}:{as_} {away} [{league_name}] -> {result}')
                    api_results[home] = result
    except Exception as e:
        print(f'  {league_name}获取失败: {e}')

print()
print("=" * 85)
print("  v3.9.2 vs v3.10 预测对比 (5/31)")
print("=" * 85)

# 合并赛果
all_results = {**espn_results, **api_results}

# 已知赛果(手动)
known_results = {
    '冈山绿雉': 'D',  # 1:1
    '清水鼓动': 'D',  # 1:1
}

# 更新昨日赛果
for m in yesterday_matches:
    if m['actual'] is None:
        # 尝试从API结果中匹配
        for key, result in all_results.items():
            if m['home'] in key or key in m['home']:
                m['actual'] = result
                break
        if m['actual'] is None and m['home'] in known_results:
            m['actual'] = known_results[m['home']]

# 对比
correct392 = 0
correct310 = 0
total_verified = 0
changed = 0
changed_correct = 0
changed_wrong = 0

balanced_correct392 = 0
balanced_correct310 = 0
balanced_total = 0

lines_detail = []

for m in yesterday_matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    r392 = predict_v392(oh, od, oa, m['league'])
    r310 = predict_v310(oh, od, oa, m['league'])

    if not r392 or not r310: continue

    pred392 = r392['pred']
    pred310 = r310['pred']
    cn392 = {'H':'主胜','D':'平局','A':'客胜'}[pred392]
    cn310 = {'H':'主胜','D':'平局','A':'客胜'}[pred310]

    is_bal = r310.get('is_balanced', False)
    bal_str = '均衡' if is_bal else ''

    actual_str = '待验证'
    mark392 = ''
    mark310 = ''

    if m['actual']:
        total_verified += 1
        actual_str = f'实际:{m["actual"]}({"主胜" if m["actual"]=="H" else "平局" if m["actual"]=="D" else "客胜"})'
        if pred392 == m['actual']: correct392 += 1; mark392 = '✓'
        else: mark392 = '✗'
        if pred310 == m['actual']: correct310 += 1; mark310 = '✓'
        else: mark310 = '✗'

        if is_bal:
            balanced_total += 1
            if pred392 == m['actual']: balanced_correct392 += 1
            if pred310 == m['actual']: balanced_correct310 += 1

    if pred392 != pred310:
        changed += 1
        if m['actual']:
            if pred310 == m['actual']: changed_correct += 1
            else: changed_wrong += 1

    detail = f'{m["num"]} {m["home"]} vs {m["away"]} [{m["league"]}] 赔率:{oh:.2f}/{od:.2f}/{oa:.2f} {bal_str}'
    detail += f'\n  v3.9.2: {cn392} (H{r392["hp"]*100:.1f}% D{r392["dp"]*100:.1f}% A{r392["ap"]*100:.1f}%) {mark392}'
    detail += f'\n  v3.10:  {cn310} (H{r310["hp"]*100:.1f}% D{r310["dp"]*100:.1f}% A{r310["ap"]*100:.1f}%) {mark310}'
    detail += f'\n  {actual_str}'
    if pred392 != pred310:
        detail += f'\n  >>> 改变! {cn392} → {cn310}'
    lines_detail.append(detail)

for d in lines_detail:
    print()
    print(f'  {d}')

print()
print(f'  已验证场次: {total_verified}')
if total_verified > 0:
    print(f'  v3.9.2正确: {correct392}/{total_verified} = {correct392/total_verified*100:.1f}%')
    print(f'  v3.10 正确: {correct310}/{total_verified} = {correct310/total_verified*100:.1f}%')
if balanced_total > 0:
    print(f'  均衡赔率:')
    print(f'    v3.9.2: {balanced_correct392}/{balanced_total} = {balanced_correct392/balanced_total*100:.1f}%')
    print(f'    v3.10:  {balanced_correct310}/{balanced_total} = {balanced_correct310/balanced_total*100:.1f}%')
print(f'  预测改变: {changed}场')
if total_verified > 0:
    print(f'  改变后正确: {changed_correct}, 错误: {changed_wrong}, 净收益: +{changed_correct-changed_wrong}')

# 保存结果
results_data = {
    'yesterday_matches': yesterday_matches,
    'api_results': {k: v for k, v in all_results.items()},
    'total_verified': total_verified,
    'correct392': correct392,
    'correct310': correct310,
}
with open('d:/football_tools/data/validation_0531.json', 'w', encoding='utf-8') as f:
    json.dump(results_data, f, ensure_ascii=False, indent=2)

print()
print('=' * 85)
