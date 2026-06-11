"""
今日(6/1)体彩推荐 — 基于v3.9.2 + 均衡draw辅助判断
5/31验证教训: 强行boost draw反而退步, 保守策略更好

模型策略:
1. 基础预测用v3.9.2(最稳)
2. 均衡赔率(< 0.8)作为辅助信号, 不强制改预测
3. 均衡赔率时标注"平局可能", 让用户自行判断
4. 低赔率SPF无价值 → 推荐让球
5. 今日6场全是国际友谊赛, 战意不确定
"""
import sys, io, requests, json
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

r = session.get('https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry',
    params={'sellStatus': 'on'}, timeout=30)
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

# ===== v3.9.2模型(验证最稳) =====
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
    ev_h, ev_d, ev_a = hp*oh-1, dp*od-1, ap*oa-1
    odds_range = max(oh,od,oa) - min(oh,od,oa)
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf,'margin':margin,
            'ev_h':ev_h,'ev_d':ev_d,'ev_a':ev_a,'odds_range':odds_range}

def score_dir(sc):
    h, a = sc.split(':')
    if int(h) > int(a): return 'H'
    elif int(h) == int(a): return 'D'
    else: return 'A'

lines = []
def p(s=''): lines.append(s)

p('=' * 85)
p('  6/1(周一) 体彩推荐  v3.9.2 + 均衡辅助')
p('  昨日验证: v3.9.2=4/9(44.4%), v3.11=3/9(33.3%)')
p('  教训: 强行boost draw反而退步, 均衡只做辅助信号')
p('  今日全国际友谊赛, 战意不确定')
p('=' * 85)

results = []
for m in matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    if not oh or not od or not oa:
        p('')
        p(f'  {m["num_str"]} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]}')
        p(f'  赔率未出')
        p(f'  {"─"*75}')
        continue

    pred = predict(oh, od, oa, m['league'])
    rq_pred = predict(m['rqh'], m['rqd'], m['rqa'], m['league'])

    pred_dir = pred['pred']
    pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred_dir]
    odds_range = pred['odds_range']
    is_balanced = odds_range < 0.8

    # 让球
    rq_dir = rq_pred['pred'] if rq_pred else None
    rq_cn = {'H':'让胜','D':'让平','A':'让负'}[rq_dir] if rq_dir else ''
    hc = m.get('hc','')

    # 让球含义
    rq_meaning = ''
    if hc and rq_dir:
        try:
            hc_val = float(hc)
            if hc_val < 0:
                abs_hc = int(abs(hc_val))
                if abs_hc == 1:
                    rq_meaning = {'H':'主赢2球+','D':'主赢恰好1球','A':'平/客赢/主赢不到2球'}[rq_dir]
                elif abs_hc == 2:
                    rq_meaning = {'H':'主赢3球+','D':'主赢恰好2球','A':'主赢0-1球/平/客赢'}[rq_dir]
            elif hc_val > 0:
                abs_hc = int(abs(hc_val))
                if abs_hc == 1:
                    rq_meaning = {'H':'主赢/平/客赢不到2球','D':'客赢恰好1球','A':'客赢2球+'}[rq_dir]
        except:
            rq_meaning = rq_cn

    # 比分选择
    scores = m.get('scores', [])
    home_scores = [(s, o) for s, o in scores if score_dir(s) == 'H']
    draw_scores = [(s, o) for s, o in scores if score_dir(s) == 'D']
    away_scores = [(s, o) for s, o in scores if score_dir(s) == 'A']

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

    top3_goals = m.get('goals', [])[:3]

    # EV
    evs = [('主胜',pred['ev_h'],oh), ('平局',pred['ev_d'],od), ('客胜',pred['ev_a'],oa)]
    evs.sort(key=lambda x: -x[1])
    best_ev = evs[0]

    rq_evs = []
    if rq_pred:
        rq_evs = [('让胜',rq_pred['ev_h'],m['rqh']), ('让平',rq_pred['ev_d'],m['rqd']), ('让负',rq_pred['ev_a'],m['rqa'])]
        rq_evs.sort(key=lambda x: -x[1])

    # 辅助信号
    signals = []
    if is_balanced:
        # 检查dp boost后是否能成为最高
        dp_boosted = pred['dp'] + 0.06  # 用strong boost模拟
        if dp_boosted > pred['hp'] and dp_boosted > pred['ap']:
            signals.append('均衡+draw可成为最高概率→平局有价')
        else:
            signals.append(f'均衡(极差{odds_range:.2f})但draw非最高→平局辅助')

    if oh < 1.30 or oa < 1.30:
        fav = '主' if oh < oa else '客'
        signals.append(f'{fav}方低赔率({min(oh,oa):.2f})SPF无价值→走让球')

    if m['league'] == '国际赛':
        signals.append('友谊赛战意不确定')

    # 评分
    score_val = 0
    reasons = []

    if pred['conf'] >= 0.55:
        score_val += 3; reasons.append('高置信')
    elif pred['conf'] >= 0.40:
        score_val += 1; reasons.append('中置信')
    else:
        score_val -= 1; reasons.append('低置信/胶着')

    best_ev_val = max(pred['ev_h'], pred['ev_d'], pred['ev_a'])
    if best_ev_val > -0.05:
        score_val += 2; reasons.append('EV接近正')
    elif best_ev_val > -0.10:
        score_val += 0
    else:
        score_val -= 1

    if rq_dir and pred_dir == rq_dir:
        score_val += 1; reasons.append('SPF+让球同向')
    elif rq_dir:
        score_val -= 1; reasons.append('SPF与让球矛盾')

    if m['league'] == '国际赛':
        score_val -= 2; reasons.append('友谊赛不确定')

    # 特殊判断
    if m['home'] == '土耳其' and m['away'] == '北马其顿':
        score_val += 2; reasons.append('FIFA差大')
    if m['home'] == '挪威' and m['away'] == '瑞典':
        score_val += 0; reasons.append('北欧德比')

    if score_val >= 4: tier = 'A'
    elif score_val >= 1: tier = 'B'
    else: tier = 'C'

    # 输出
    p('')
    p(f'  {m["num_str"]} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]}')
    p(f'  {"═"*75}')
    p(f'  SPF: {pred_cn}({pred["conf"]*100:.1f}%)  赔率 {oh:.2f}/{od:.2f}/{oa:.2f}  极差:{odds_range:.2f}')
    p(f'  概率: 主{pred["hp"]*100:.1f}% 平{pred["dp"]*100:.1f}% 客{pred["ap"]*100:.1f}%')
    p(f'  EV: {evs[0][0]}{evs[0][1]:+.3f}  {evs[1][0]}{evs[1][1]:+.3f}  {evs[2][0]}{evs[2][1]:+.3f}')
    p(f'  {"─"*75}')

    # 让球
    if hc and rq_cn:
        rq_conf = rq_pred['conf'] if rq_pred else 0
        p(f'  让球: 让{hc} {rq_cn}({rq_conf*100:.0f}%) 赔率{m["rqh"]:.2f}/{m["rqd"]:.2f}/{m["rqa"]:.2f}')
        p(f'  含义: {rq_meaning}')
        if rq_evs:
            p(f'  让球EV: {rq_evs[0][0]}{rq_evs[0][1]:+.3f}(赔{rq_evs[0][2]:.2f})')

    # 比分
    p(f'  {"─"*75}')
    p(f'  推荐比分:')
    for i, (sc, odds) in enumerate(picks[:3]):
        d_cn = {'H':'主胜','D':'平局','A':'客胜'}[score_dir(sc)]
        marker = ' ◄首选' if i == 0 else ''
        p(f'    {i+1}. {sc}  ({d_cn}, 赔率{odds:.1f}){marker}')

    if top3_goals:
        p(f'  大小球: {" / ".join(f"{g}({v:.1f})" for g, v in top3_goals)}')

    # 信号
    if signals:
        p(f'  {"─"*75}')
        for s in signals:
            p(f'  ! {s}')

    # 建议
    p(f'  {"─"*75}')
    advice = []
    if pred['conf'] >= 0.50 and min(oh,od,oa) >= 1.40:
        dir_odds = {'H':oh,'D':od,'A':oa}[pred_dir]
        advice.append(f'SPF{pred_cn}({dir_odds:.2f})')
    if hc and rq_cn and rq_pred and rq_pred['conf'] >= 0.40:
        rq_odds = {'H':m['rqh'],'D':m['rqd'],'A':m['rqa']}[rq_dir]
        if rq_odds >= 1.50:
            advice.append(f'让{hc}{rq_cn}({rq_odds:.2f})')
    if is_balanced and pred['dp'] >= 0.25:
        advice.append(f'平局({od:.2f})有价值')
    if picks:
        advice.append(f'比分{picks[0][0]}({picks[0][1]:.1f})')
    if not advice:
        advice.append('本场不推荐')
    p(f'  >> {" / ".join(advice)}')

    results.append({
        'm': m, 'pred': pred, 'rq_pred': rq_pred, 'picks': picks,
        'tier': tier, 'score_val': score_val, 'reasons': reasons,
        'rq_cn': rq_cn, 'rq_dir': rq_dir, 'is_balanced': is_balanced,
    })

# ===== 汇总 =====
p('')
p(f'{"="*85}')
p(f'  汇总推荐表')
p(f'{"="*85}')
p('')
p(f'  {"编号":8s} {"比赛":24s} {"SPF":6s} {"让球":14s} {"比分1":6s} {"比分2":6s} {"比分3":6s}')
p(f'  {"─"*75}')

for r in results:
    m = r['m']
    pred = r['pred']
    picks = r['picks']
    pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
    rq_str = f'让{m["hc"]}{r["rq_cn"]}' if m.get('hc') and r['rq_cn'] else '-'

    s1 = picks[0][0] if len(picks) > 0 else '-'
    s2 = picks[1][0] if len(picks) > 1 else '-'
    s3 = picks[2][0] if len(picks) > 2 else '-'

    match_str = f'{m["home"]}vs{m["away"]}'
    if len(match_str) > 24: match_str = match_str[:24]
    p(f'  {m["num_str"]:8s} {match_str:24s} {pred_cn:6s} {rq_str:14s} {s1:6s} {s2:6s} {s3:6s}')

# ===== 最终推荐 =====
p('')
p(f'{"="*85}')
p(f'  最终推荐 (v3.9.2 + 均衡辅助)')
p(f'{"="*85}')

for tier_name, tier_label in [('A','A档(重点)'), ('B','B档(小注)'), ('C','C档(避让)')]:
    tier_matches = [r for r in results if r.get('tier') == tier_name]
    if not tier_matches: continue

    p('')
    p(f'  【{tier_label}】')
    for r in tier_matches:
        m = r['m']
        pred = r['pred']
        picks = r['picks']
        rq_pred = r.get('rq_pred')

        pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]

        p(f'')
        p(f'  {m["num_str"]} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]}')
        p(f'  SPF: {pred_cn}({pred["conf"]*100:.0f}%) 赔率{m["oh"]:.2f}/{m["od"]:.2f}/{m["oa"]:.2f}')

        if m.get('hc') and r['rq_cn']:
            rq_conf = rq_pred['conf'] if rq_pred else 0
            p(f'  让球: 让{m["hc"]} {r["rq_cn"]}({rq_conf*100:.0f}%) 赔率{m["rqh"]:.2f}/{m["rqd"]:.2f}/{m["rqa"]:.2f}')

        score_str = ' / '.join(f'{s}({o:.1f})' for s, o in picks[:3])
        p(f'  比分: {score_str}')
        p(f'  评分: {r["score_val"]} {" ".join(r["reasons"])}')

# 串关建议
p('')
p(f'  {"─"*75}')
p(f'  串关建议:')
p(f'')

combo_options = []
for r in results:
    if r.get('tier') not in ('A','B'): continue
    m = r['m']
    pred = r['pred']

    if pred['conf'] >= 0.50:
        dir_odds = {'H':m['oh'],'D':m['od'],'A':m['oa']}[pred['pred']]
        pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
        if dir_odds >= 1.40:
            combo_options.append(('SPF', m['num_str'], pred_cn, dir_odds, r['tier']))

    if m.get('hc') and r['rq_cn'] and r.get('rq_pred') and r['rq_pred']['conf'] >= 0.40:
        rq_odds = {'H':m['rqh'],'D':m['rqd'],'A':m['rqa']}[r['rq_dir']]
        if rq_odds >= 1.50:
            combo_options.append(('RQ', m['num_str'], f'让{m["hc"]}{r["rq_cn"]}', rq_odds, r['tier']))

if len(combo_options) >= 2:
    p(f'  2串1:')
    shown = 0
    for i in range(len(combo_options)):
        for j in range(i+1, len(combo_options)):
            if shown >= 5: break
            o1, o2 = combo_options[i], combo_options[j]
            if o1[1] == o2[1]: continue
            if o1[3] < 1.50 or o2[3] < 1.50: continue
            combo = o1[3] * o2[3]
            if combo >= 2.5:
                p(f'    {o1[1]}{o1[2]}({o1[3]:.2f}) x {o2[1]}{o2[2]}({o2[3]:.2f}) = {combo:.2f}')
                shown += 1
        if shown >= 5: break

# 昨日验证
p('')
p(f'{"="*85}')
p(f'  昨日(5/31)赛果验证')
p(f'{"="*85}')
p(f'')
p(f'  001 冈山 1:1 浦和 [日职]  赔率2.90/3.00/2.22  预测客胜 ✗ 实际平局')
p(f'  002 清水 1:1 横滨 [日职]  赔率2.52/3.10/2.44  预测客胜 ✗ 实际平局')
p(f'  003 日本 1:0 冰岛 [国际赛] 赔率1.12/6.25/13.00 预测主胜 ✓ 实际主胜')
p(f'  004 韦斯特罗斯 4:5 哥德堡 [瑞超] 赔率2.46/3.00/2.57 预测主胜 ✗ 实际客胜')
p(f'  005 赫根 3:2 哈马比 [瑞超] 赔率2.77/3.35/2.13 预测客胜 ✗ 实际主胜')
p(f'  006 代格福什 2:2 布鲁马波卡纳 [瑞超] 赔率2.10/3.15/2.98 预测主胜 ✗ 实际平局')
p(f'  008 AC奥卢 2:1 雅罗 [芬超] 赔率1.50/3.90/4.85 预测主胜 ✓ 实际主胜')
p(f'  009 捷克 2:1 科索沃 [国际赛] 赔率1.52/3.64/5.10 预测主胜 ✓ 实际主胜')
p(f'  011 美国 3:2 塞内加尔 [国际赛] 赔率2.43/2.90/2.68 预测主胜 ✓ 实际主胜')
p(f'')
p(f'  v3.9.2: 4/9 = 44.4%  |  v3.11: 3/9 = 33.3%')
p(f'  4场均衡赔率: 实际3平1非平 → 均衡=平局概率高但不绝对')
p(f'  3场非均衡错误: 赔率本身的局限, 模型无法弥补')
p(f'')
p('=' * 85)

report = '\n'.join(lines)
print(report)
