"""
5/31(周日) 体彩比分+大小球推荐 7001-7012
"""
import sys, io, requests
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
    params={'sellStatus': 'on', 'date': '2026-05-31'}, timeout=30)
data = r.json()

score_map = {
    's01s00':'1:0','s00s00':'0:0','s00s01':'0:1','s01s01':'1:1',
    's02s01':'2:1','s01s02':'1:2','s02s00':'2:0','s00s02':'0:2',
    's03s01':'3:1','s01s03':'1:3','s03s00':'3:0','s00s03':'0:3',
    's02s02':'2:2','s03s02':'3:2','s02s03':'2:3',
    's04s00':'4:0','s00s04':'0:4','s04s01':'4:1','s01s04':'1:4',
}
goal_map = {'s0':'0球','s1':'1球','s2':'2球','s3':'3球','s4':'4球','s5':'5球','s6':'6球','s7':'7+'}

matches = []
for dg in data.get('value', {}).get('matchInfoList', []):
    for m in dg.get('subMatchList', []):
        raw_num = m.get('matchNum', '')
        num = str(raw_num) if raw_num else ''
        if not num.startswith('7'): continue

        had = m.get('had', {})
        hhad = m.get('hhad', {})
        crs = m.get('crs', {})
        ttg = m.get('ttg', {})

        oh = float(had.get('h', 0) or 0)
        od = float(had.get('d', 0) or 0)
        oa = float(had.get('a', 0) or 0)

        valid_scores = [(score_map.get(k, k), float(v or 0)) for k, v in crs.items()
                        if k in score_map and float(v or 0) > 0]
        valid_goals = [(goal_map.get(k, k), float(v or 0)) for k, v in ttg.items()
                       if k in goal_map and float(v or 0) > 0]

        matches.append({
            'num': num,
            'num_str': m.get('matchNumStr', ''),
            'time': m.get('matchTime', '')[:5],
            'league': m.get('leagueAbbName', ''),
            'home': m.get('homeTeamAllName', '') or m.get('homeTeamAbbName', ''),
            'away': m.get('awayTeamAllName', '') or m.get('awayTeamAbbName', ''),
            'oh': oh, 'od': od, 'oa': oa,
            'hc': hhad.get('goalLine', ''),
            'rqh': float(hhad.get('h', 0) or 0),
            'rqd': float(hhad.get('d', 0) or 0),
            'rqa': float(hhad.get('a', 0) or 0),
            'scores': sorted(valid_scores, key=lambda x: x[1]),
            'goals': sorted(valid_goals, key=lambda x: x[1]),
        })

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
        if nd > 0: hp -= 0.01*(hp/nd); ap -= 0.01*(hp/nd)
    if oh and 1.25 <= oh <= 1.35:
        hp -= 0.02; dp += 0.01; ap += 0.01
    total = hp+dp+ap
    if total > 0: hp, dp, ap = hp/total, dp/total, ap/total
    pred = max(['H','D','A'], key=lambda x: {'H':hp,'D':dp,'A':ap}[x])
    conf = max(hp, dp, ap)
    ev_h, ev_d, ev_a = hp*oh-1, dp*od-1, ap*oa-1
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf,'margin':margin,
            'ev_h':ev_h,'ev_d':ev_d,'ev_a':ev_a}

def score_dir(sc):
    h, a = sc.split(':')
    if int(h) > int(a): return 'H'
    elif int(h) == int(a): return 'D'
    else: return 'A'

p('=' * 85)
p('  5/31(周日) 体彩比分+大小球推荐  7001-7012')
p('=' * 85)

for m in matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    pred = predict(oh, od, oa, m['league'])
    if not pred:
        p('')
        p(f'  {m["num_str"]} [{m["league"]}] {m["time"]} {m["home"]} vs {m["away"]}')
        p(f'  赔率未出')
        p(f'  {"─"*75}')
        continue

    pred_dir = pred['pred']
    pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred_dir]

    home_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'H']
    draw_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'D']
    away_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'A']

    picks = []
    if pred_dir == 'H' and home_scores: picks.append(home_scores[0])
    elif pred_dir == 'D' and draw_scores: picks.append(draw_scores[0])
    elif pred_dir == 'A' and away_scores: picks.append(away_scores[0])

    probs = [('H', pred['hp'], home_scores), ('D', pred['dp'], draw_scores), ('A', pred['ap'], away_scores)]
    probs_sorted = sorted(probs, key=lambda x: -x[1])
    for d, prob, sc_list in probs_sorted:
        if d != pred_dir and sc_list:
            picks.append(sc_list[0])
            break

    if pred_dir == 'H' and len(home_scores) > 1: picks.append(home_scores[1])
    elif pred_dir == 'D' and len(draw_scores) > 1: picks.append(draw_scores[1])
    elif pred_dir == 'A' and len(away_scores) > 1: picks.append(away_scores[1])
    else:
        for d, prob, sc_list in probs_sorted:
            already = [score_dir(s) for s, _ in picks]
            if d not in already and sc_list:
                picks.append(sc_list[0])
                break

    top3_goals = m['goals'][:3]

    rq_pred = predict(m['rqh'], m['rqd'], m['rqa'], m['league'])
    rq_cn = ''
    if rq_pred:
        rq_cn = {'H':'让胜','D':'让平','A':'让负'}[rq_pred['pred']] + f' ({rq_pred["conf"]*100:.1f}%)'

    p('')
    p(f'  {m["num_str"]} [{m["league"]}] {m["time"]} {m["home"]} vs {m["away"]}')
    p(f'  赔率: {oh:.2f}/{od:.2f}/{oa:.2f}  让{m["hc"]}  预测: {pred_cn}({pred["conf"]*100:.1f}%)')
    if rq_cn:
        p(f'  让球: {m["rqh"]:.2f}/{m["rqd"]:.2f}/{m["rqa"]:.2f} -> {rq_cn}')
    p(f'  隐含: 主{pred["hp"]*100:.1f}% 平{pred["dp"]*100:.1f}% 客{pred["ap"]*100:.1f}%  margin={pred["margin"]*100:.1f}%')
    evs = [('主胜',pred['ev_h'],oh), ('平局',pred['ev_d'],od), ('客胜',pred['ev_a'],oa)]
    evs.sort(key=lambda x: -x[1])
    p(f'  EV:  {evs[0][0]}{evs[0][1]:+.3f}(赔{evs[0][2]:.2f})  {evs[1][0]}{evs[1][1]:+.3f}  {evs[2][0]}{evs[2][1]:+.3f}')
    p(f'  {"─"*75}')
    p(f'  推荐比分:')
    for i, (sc, odds) in enumerate(picks[:3]):
        d_cn = {'H':'主胜','D':'平局','A':'客胜'}[score_dir(sc)]
        p(f'    {i+1}. {sc}  ({d_cn}, 赔率{odds:.1f})')
    p(f'  大小球:')
    goal_str = '  '.join(f'{g}={v:.1f}' for g, v in top3_goals)
    p(f'    {goal_str}')
    p(f'  {"─"*75}')

# 汇总
p('')
p(f'  {"═"*75}')
p(f'  汇总推荐 (按EV排序)')
p(f'  {"═"*75}')

all_recs = []
for m in matches:
    pred = predict(m['oh'], m['od'], m['oa'], m['league'])
    if not pred: continue
    evs = [('主胜',pred['ev_h'],m['oh'],pred['hp']), ('平局',pred['ev_d'],m['od'],pred['dp']), ('客胜',pred['ev_a'],m['oa'],pred['ap'])]
    best = max(evs, key=lambda x: x[1])
    all_recs.append((m, best, pred))

all_recs.sort(key=lambda x: -x[1][1])

p('')
p(f'  {"编号":6s} {"联赛":6s} {"比赛":30s} {"方向":6s} {"EV":8s} {"赔率":6s} {"概率":8s}')
p(f'  {"─"*70}')
for rec in all_recs:
    m = rec[0]
    dir_name, ev, odds, prob = rec[1]
    marker = ' ★' if ev > -0.05 else ''
    match_str = m['home'] + ' vs ' + m['away']
    p(f'  {m["num_str"]:6s} {m["league"]:6s} {match_str:30s} {dir_name:6s} {ev:+.3f}  {odds:.2f}  {prob*100:.1f}%{marker}')

p('')
p(f'  冷门预警 (低赔率<1.40):')
for m in matches:
    min_o = min(m['oh'], m['oa'])
    if 0 < min_o < 1.40:
        fav = '主' if m['oh'] < m['oa'] else '客'
        risk = '高' if min_o < 1.25 else '中' if min_o < 1.35 else '低'
        p(f'    {m["num_str"]} {m["home"]} vs {m["away"]} -> {fav}方{min_o:.2f} 风险{risk}')

p('')
p('=' * 85)

report = '\n'.join(lines)
print(report)
