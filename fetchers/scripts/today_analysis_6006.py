"""
明日体彩分析 (6006-6014) 2026-05-30
"""
import sys, io, json, math, requests
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

matches = []
for dg in data.get('value', {}).get('matchInfoList', []):
    for m in dg.get('subMatchList', []):
        raw_num = m.get('matchNum', '')
        num = str(raw_num) if raw_num else ''
        if not num.startswith('6'): continue

        had = m.get('had', {})
        hhad = m.get('hhad', {})
        crs = m.get('crs', {})
        ttg = m.get('ttg', {})

        matches.append({
            'num': num, 'num_str': m.get('matchNumStr', ''),
            'time': m.get('matchTime', '')[:5],
            'league': m.get('leagueAbbName', ''),
            'home': m.get('homeTeamAllName', '') or m.get('homeTeamAbbName', ''),
            'away': m.get('awayTeamAllName', '') or m.get('awayTeamAbbName', ''),
            'home_rank': (m.get('homeRank') or [''])[0],
            'away_rank': (m.get('awayRank') or [''])[0],
            'oh': float(had.get('h', 0) or 0),
            'od': float(had.get('d', 0) or 0),
            'oa': float(had.get('a', 0) or 0),
            'rqh': float(hhad.get('h', 0) or 0),
            'rqd': float(hhad.get('d', 0) or 0),
            'rqa': float(hhad.get('a', 0) or 0),
            'hc': hhad.get('goalLine', ''),
            'crs': {k: float(v or 0) for k, v in crs.items() if k.startswith('s') and v},
            'ttg': {k: float(v or 0) for k, v in ttg.items() if k.startswith('s') and v},
        })

matches = [m for m in matches if 6006 <= int(m['num']) <= 6014]

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
    ev_h, ev_d, ev_a = hp*oh-1, dp*od-1, ap*oa-1
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf,'margin':margin,
            'ev_h':ev_h,'ev_d':ev_d,'ev_a':ev_a}

score_map = {
    's01s00':'1:0','s00s00':'0:0','s00s01':'0:1','s01s01':'1:1',
    's02s01':'2:1','s01s02':'1:2','s02s00':'2:0','s00s02':'0:2',
    's03s01':'3:1','s01s03':'1:3','s03s00':'3:0','s00s03':'0:3',
    's02s02':'2:2','s03s02':'3:2','s02s03':'2:3',
    's04s00':'4:0','s00s04':'0:4','s04s01':'4:1','s01s04':'1:4',
}
goal_map = {'s0':'0球','s1':'1球','s2':'2球','s3':'3球','s4':'4球','s5':'5球','s6':'6球','s7':'7+'}

p('=' * 85)
p('  明日体彩分析 (2026-05-30)  6006-6014')
p('=' * 85)

for m in matches:
    p('')
    p(f'  {m["num_str"]} {m["league"]}  {m["time"]}')
    p(f'  {m["home"]} vs {m["away"]}')
    if m['home_rank'] or m['away_rank']:
        p(f'  排名: {m["home_rank"]} vs {m["away_rank"]}')

    pred = predict(m['oh'], m['od'], m['oa'], m['league'])
    if pred:
        cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
        p(f'  胜平负: {m["oh"]:.2f} / {m["od"]:.2f} / {m["oa"]:.2f}  (margin={pred["margin"]*100:.1f}%)')
        p(f'  隐含:  主{pred["hp"]*100:.1f}%  平{pred["dp"]*100:.1f}%  客{pred["ap"]*100:.1f}%')
        p(f'  模型预测: {cn} (置信{pred["conf"]*100:.1f}%)')
        evs = [('主胜',pred['ev_h'],m['oh']), ('平局',pred['ev_d'],m['od']), ('客胜',pred['ev_a'],m['oa'])]
        evs.sort(key=lambda x: -x[1])
        p(f'  EV:  {evs[0][0]}{evs[0][1]:+.3f}(赔{evs[0][2]:.2f})  {evs[1][0]}{evs[1][1]:+.3f}  {evs[2][0]}{evs[2][1]:+.3f}')

    rq_pred = predict(m['rqh'], m['rqd'], m['rqa'], m['league'])
    if rq_pred:
        rq_cn = {'H':'让胜','D':'让平','A':'让负'}[rq_pred['pred']]
        p(f'  让{m["hc"]}: {m["rqh"]:.2f} / {m["rqd"]:.2f} / {m["rqa"]:.2f}  -> {rq_cn} (置信{rq_pred["conf"]*100:.1f}%)')

    valid_scores = [(score_map.get(k, k), v) for k, v in m['crs'].items() if v > 0 and k in score_map]
    if valid_scores:
        top5 = sorted(valid_scores, key=lambda x: x[1])[:5]
        p(f'  比分: {"  ".join(f"{s}={v:.1f}" for s,v in top5)}')

    valid_goals = [(goal_map.get(k, k), v) for k, v in m['ttg'].items() if v > 0 and k in goal_map]
    if valid_goals:
        top3 = sorted(valid_goals, key=lambda x: x[1])[:3]
        p(f'  进球: {"  ".join(f"{g}={v:.1f}" for g,v in top3)}')

    p(f'  {"─"*75}')

# 汇总推荐
p('')
p('  ═══════════════════════════════════════════════════════════════════')
p('  汇总推荐')
p('  ═══════════════════════════════════════════════════════════════════')

all_recs = []
for m in matches:
    pred = predict(m['oh'], m['od'], m['oa'], m['league'])
    if not pred: continue
    evs = [('主胜',pred['ev_h'],m['oh'],pred['hp']), ('平局',pred['ev_d'],m['od'],pred['dp']), ('客胜',pred['ev_a'],m['oa'],pred['ap'])]
    best = max(evs, key=lambda x: x[1])
    all_recs.append((m, best, pred))

all_recs.sort(key=lambda x: -x[1][1])

p('')
p(f'  按EV排序:')
p(f'  {"编号":6s} {"联赛":6s} {"比赛":28s} {"方向":6s} {"EV":8s} {"赔率":6s} {"概率":8s}')
p(f'  {"─"*70}')
for rec in all_recs:
    m = rec[0]
    dir_name, ev, odds, prob = rec[1]
    marker = ' ★' if ev > -0.05 else ''
    match_str = m['home'] + ' vs ' + m['away']
    p(f'  {m["num_str"]:6s} {m["league"]:6s} {match_str:28s} {dir_name:6s} {ev:+.3f}  {odds:.2f}  {prob*100:.1f}%{marker}')

p('')
p('  冷门预警 (低赔率<1.40):')
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