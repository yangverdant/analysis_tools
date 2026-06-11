"""
明日体彩比分推荐 (6006-6014) 2026-05-30
含比分 + 大小球
"""
import sys, io, json, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import urllib3
urllib3.disable_warnings()

lines = []
def p(s=''): lines.append(s)

session = requests.Session()
session.trust_env = False
session.verify = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.sporttery.cn/',
})

r = session.get('https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry',
    params={'sellStatus': 'on', 'date': '2026-05-30'}, timeout=30)
data = r.json()

score_map = {
    's01s00':'1:0','s00s00':'0:0','s00s01':'0:1','s01s01':'1:1',
    's02s01':'2:1','s01s02':'1:2','s02s00':'2:0','s00s02':'0:2',
    's03s01':'3:1','s01s03':'1:3','s03s00':'3:0','s00s03':'0:3',
    's02s02':'2:2','s03s02':'3:2','s02s03':'2:3',
    's04s00':'4:0','s00s04':'0:4','s04s01':'4:1','s01s04':'1:4',
}
goal_map = {'s0':'0球','s1':'1球','s2':'2球','s3':'3球','s4':'4球','s5':'5球','s6':'6球','s7':'7+'}

def predict(oh, od, oa, league=''):
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
        if nd > 0: hp += 0.01*(hp/nd); ap += 0.01*(ap/nd)
    elif dp >= 0.28:
        dp += 0.01; nd = hp+ap
        if nd > 0: hp -= 0.01*(hp/nd); ap -= 0.01*(ap/nd)
    if oh and 1.25 <= oh <= 1.35:
        hp -= 0.02; dp += 0.01; ap += 0.01
    total = hp+dp+ap
    if total > 0: hp, dp, ap = hp/total, dp/total, ap/total
    pred = max(['H','D','A'], key=lambda x: {'H':hp,'D':dp,'A':ap}[x])
    conf = max(hp, dp, ap)
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf}

def score_dir(sc):
    h, a = sc.split(':')
    if int(h) > int(a): return 'H'
    elif int(h) == int(a): return 'D'
    else: return 'A'

p('=' * 85)
p('  明日体彩比分+大小球推荐 (2026-05-30)  6006-6014')
p('=' * 85)

for dg in data.get('value', {}).get('matchInfoList', []):
    for m in dg.get('subMatchList', []):
        raw_num = m.get('matchNum', '')
        num = str(raw_num) if raw_num else ''
        if not num.startswith('6'): continue
        if not (6006 <= int(num) <= 6014): continue

        had = m.get('had', {})
        hhad = m.get('hhad', {})
        crs = m.get('crs', {})
        ttg = m.get('ttg', {})
        oh = float(had.get('h', 0) or 0)
        od = float(had.get('d', 0) or 0)
        oa = float(had.get('a', 0) or 0)
        hc = hhad.get('goalLine', '')
        league = m.get('leagueAbbName', '')
        home = m.get('homeTeamAllName', '') or m.get('homeTeamAbbName', '')
        away = m.get('awayTeamAllName', '') or m.get('awayTeamAbbName', '')
        num_str = m.get('matchNumStr', '')

        pred = predict(oh, od, oa, league)
        if not pred: continue

        pred_dir = pred['pred']
        pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred_dir]

        # 比分赔率
        valid_scores = [(score_map.get(k, k), float(v or 0)) for k, v in crs.items()
                        if k in score_map and float(v or 0) > 0]
        sorted_scores = sorted(valid_scores, key=lambda x: x[1])

        home_scores = [(s, o) for s, o in sorted_scores if score_dir(s) == 'H']
        draw_scores = [(s, o) for s, o in sorted_scores if score_dir(s) == 'D']
        away_scores = [(s, o) for s, o in sorted_scores if score_dir(s) == 'A']

        # 选3个比分
        picks = []
        # 1. 预测方向最低赔率比分
        if pred_dir == 'H' and home_scores:
            picks.append(home_scores[0])
        elif pred_dir == 'D' and draw_scores:
            picks.append(draw_scores[0])
        elif pred_dir == 'A' and away_scores:
            picks.append(away_scores[0])

        # 2. 第二方向
        probs = [('H', pred['hp'], home_scores), ('D', pred['dp'], draw_scores), ('A', pred['ap'], away_scores)]
        probs_sorted = sorted(probs, key=lambda x: -x[1])
        for d, prob, sc_list in probs_sorted:
            if d != pred_dir and sc_list:
                picks.append(sc_list[0])
                break

        # 3. 预测方向第二比分 或 第三方向
        if pred_dir == 'H' and len(home_scores) > 1:
            picks.append(home_scores[1])
        elif pred_dir == 'D' and len(draw_scores) > 1:
            picks.append(draw_scores[1])
        elif pred_dir == 'A' and len(away_scores) > 1:
            picks.append(away_scores[1])
        else:
            for d, prob, sc_list in probs_sorted:
                already = [score_dir(s) for s, _ in picks]
                if d not in already and sc_list:
                    picks.append(sc_list[0])
                    break

        # 大小球
        valid_goals = [(goal_map.get(k, k), float(v or 0)) for k, v in ttg.items()
                       if k in goal_map and float(v or 0) > 0]
        sorted_goals = sorted(valid_goals, key=lambda x: x[1])
        top3_goals = sorted_goals[:3]

        p('')
        p(f'  {num_str} [{league}] {home} vs {away}')
        p(f'  赔率: {oh:.2f}/{od:.2f}/{oa:.2f}  让{hc}  预测: {pred_cn}({pred["conf"]*100:.1f}%)')
        p(f'  ────────────────────────────────────────')
        p(f'  推荐比分:')
        for i, (sc, odds) in enumerate(picks[:3]):
            d_cn = {'H':'主胜','D':'平局','A':'客胜'}[score_dir(sc)]
            p(f'    {i+1}. {sc}  ({d_cn}, 赔率{odds:.1f})')
        p(f'  大小球:')
        goal_str = '  '.join(f'{g}={v:.1f}' for g, v in top3_goals)
        p(f'    {goal_str}')
        p(f'  {"─"*75}')

p('')
p('=' * 85)

report = '\n'.join(lines)
print(report)
