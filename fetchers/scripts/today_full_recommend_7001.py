"""
5/31 剩余比赛 全场推荐: 3个比分 + 让球方向
使用v3.10模型(均衡赔率draw boost)
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

# ===== v3.10 模型 =====
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
    ev_h, ev_d, ev_a = hp*oh-1, dp*od-1, ap*oa-1
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf,'margin':margin,
            'ev_h':ev_h,'ev_d':ev_d,'ev_a':ev_a,'is_balanced':is_balanced}

def score_dir(sc):
    h, a = sc.split(':')
    if int(h) > int(a): return 'H'
    elif int(h) == int(a): return 'D'
    else: return 'A'

lines = []
def p(s=''): lines.append(s)

p('=' * 85)
p('  5/31(周日) 剩余比赛 全场推荐  v3.10模型')
p('  3个推荐比分 + 让球方向')
p('  7001冈山1:1浦和  7002清水1:1横滨  已结束(均为平局)')
p('=' * 85)

for m in matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    if not oh or not od or not oa:
        p('')
        p(f'  {m["num_str"]} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]}')
        p(f'  赔率未出 -> 跳过')
        p(f'  {"─"*75}')
        continue

    pred = predict_v310(oh, od, oa, m['league'])
    rq_pred = predict_v310(m['rqh'], m['rqd'], m['rqa'], m['league'])

    pred_dir = pred['pred']
    pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred_dir]
    bal_str = '均衡' if pred['is_balanced'] else ''

    # 让球方向
    rq_dir = rq_pred['pred'] if rq_pred else None
    rq_cn = {'H':'让胜','D':'让平','A':'让负'}[rq_dir] if rq_dir else ''
    hc = m['hc']

    # 让球含义解释
    if hc and rq_dir:
        try:
            hc_val = float(hc)
            if hc_val < 0:  # 主让
                abs_hc = abs(hc_val)
                if abs_hc == 1:
                    rq_meaning = {
                        'H': f'主赢{int(abs_hc)+1}球以上',
                        'D': f'主赢恰好{int(abs_hc)}球',
                        'A': f'平局/客赢/主赢不到{int(abs_hc)+1}球'
                    }[rq_dir]
                elif abs_hc == 2:
                    rq_meaning = {
                        'H': f'主赢{int(abs_hc)+1}球以上',
                        'D': f'主赢恰好{int(abs_hc)}球',
                        'A': f'主赢不到{int(abs_hc)}球/平/客赢'
                    }[rq_dir]
                else:
                    rq_meaning = rq_cn
            elif hc_val > 0:  # 客让
                abs_hc = abs(hc_val)
                if abs_hc == 1:
                    rq_meaning = {
                        'H': f'主赢/平/客赢不到2球',
                        'D': f'客赢恰好{int(abs_hc)}球',
                        'A': f'客赢{int(abs_hc)+1}球以上'
                    }[rq_dir]
                else:
                    rq_meaning = rq_cn
            else:
                rq_meaning = rq_cn
        except:
            rq_meaning = rq_cn
    else:
        rq_meaning = ''

    # 比分选择
    home_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'H']
    draw_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'D']
    away_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'A']

    picks = []
    # 1. 预测方向最低赔率比分
    if pred_dir == 'H' and home_scores: picks.append(home_scores[0])
    elif pred_dir == 'D' and draw_scores: picks.append(draw_scores[0])
    elif pred_dir == 'A' and away_scores: picks.append(away_scores[0])

    # 2. 第二方向最低赔率比分
    probs = [('H', pred['hp'], home_scores), ('D', pred['dp'], draw_scores), ('A', pred['ap'], away_scores)]
    probs_sorted = sorted(probs, key=lambda x: -x[1])
    for d, prob, sc_list in probs_sorted:
        if d != pred_dir and sc_list:
            picks.append(sc_list[0])
            break

    # 3. 预测方向第二比分 或 第三方向
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

    # EV分析
    evs = [('主胜',pred['ev_h'],oh), ('平局',pred['ev_d'],od), ('客胜',pred['ev_a'],oa)]
    evs.sort(key=lambda x: -x[1])
    best_ev = evs[0]

    # 让球EV
    rq_evs = []
    if rq_pred:
        rq_evs = [('让胜',rq_pred['ev_h'],m['rqh']), ('让平',rq_pred['ev_d'],m['rqd']), ('让负',rq_pred['ev_a'],m['rqa'])]
        rq_evs.sort(key=lambda x: -x[1])

    p('')
    p(f'  {m["num_str"]} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]}')
    p(f'  {"─"*75}')
    p(f'  SPF赔率: {oh:.2f}/{od:.2f}/{oa:.2f}  预测: {pred_cn}({pred["conf"]*100:.1f}%) {bal_str}')
    p(f'  隐含概率: 主{pred["hp"]*100:.1f}% 平{pred["dp"]*100:.1f}% 客{pred["ap"]*100:.1f}%')
    p(f'  最佳EV: {best_ev[0]} {best_ev[1]:+.3f}(赔{best_ev[2]:.2f})')
    p(f'  {"─"*75}')

    # 3个推荐比分
    p(f'  ★ 推荐比分:')
    for i, (sc, odds) in enumerate(picks[:3]):
        d_cn = {'H':'主胜','D':'平局','A':'客胜'}[score_dir(sc)]
        marker = ' ◄' if score_dir(sc) == pred_dir else ''
        p(f'    {i+1}. {sc}  ({d_cn}, 赔率{odds:.1f}){marker}')

    # 让球推荐
    p(f'  {"─"*75}')
    p(f'  ★ 让球推荐:')
    if hc and rq_cn:
        p(f'    让{hc} → {rq_cn} (赔率 {m["rqh"]:.2f}/{m["rqd"]:.2f}/{m["rqa"]:.2f})')
        p(f'    含义: {rq_meaning}')
        if rq_evs:
            p(f'    让球EV: {rq_evs[0][0]} {rq_evs[0][1]:+.3f}(赔{rq_evs[0][2]:.2f})')
    else:
        p(f'    让球赔率未出')

    # 大小球
    p(f'  {"─"*75}')
    p(f'  大小球: {" / ".join(f"{g}({v:.1f})" for g, v in top3_goals)}')

    # 综合建议
    p(f'  {"─"*75}')
    p(f'  ★ 综合建议:')
    # SPF方向
    if pred['conf'] >= 0.50:
        p(f'    SPF: {pred_cn}({pred["conf"]*100:.0f}%) 置信较高')
    elif pred['conf'] >= 0.35:
        p(f'    SPF: {pred_cn}({pred["conf"]*100:.0f}%) 置信一般，胶着')
    else:
        p(f'    SPF: {pred_cn}({pred["conf"]*100:.0f}%) 置信很低，慎选')

    # 让球方向建议
    if hc and rq_dir:
        rq_conf = rq_pred['conf'] if rq_pred else 0
        if rq_conf >= 0.50:
            p(f'    让球: {rq_cn}({rq_conf*100:.0f}%) 置信较高')
        elif rq_conf >= 0.35:
            p(f'    让球: {rq_cn}({rq_conf*100:.0f}%) 置信一般')
        else:
            p(f'    让球: {rq_cn}({rq_conf*100:.0f}%) 置信低，可考虑跳过')

    # 特殊提示
    if pred['is_balanced']:
        p(f'    ⚠ 均衡赔率(极差<0.8)，平局概率被提升')
    if m['league'] == '国际赛':
        p(f'    ⚠ 友谊赛/国际赛，战意不确定')
    if oh < 1.30 or oa < 1.30:
        fav = '主' if oh < oa else '客'
        p(f'    ⚠ {fav}方低赔率({min(oh,oa):.2f})，SPF价值低，建议走让球')

# ===== 汇总表 =====
p('')
p(f'{"="*85}')
p(f'  汇总推荐表')
p(f'{"="*85}')
p('')
p(f'  {"编号":8s} {"比赛":28s} {"SPF":8s} {"置信":6s} {"让球":12s} {"比分1":8s} {"比分2":8s} {"比分3":8s}')
p(f'  {"─"*85}')

for m in matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    if not oh or not od or not oa: continue

    pred = predict_v310(oh, od, oa, m['league'])
    rq_pred = predict_v310(m['rqh'], m['rqd'], m['rqa'], m['league'])

    pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
    conf_str = f'{pred["conf"]*100:.0f}%'

    rq_str = ''
    if rq_pred and m['hc']:
        rq_cn = {'H':'让胜','D':'让平','A':'让负'}[rq_pred['pred']]
        rq_str = f'让{m["hc"]}{rq_cn}'

    home_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'H']
    draw_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'D']
    away_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'A']

    picks = []
    if pred['pred'] == 'H' and home_scores: picks.append(home_scores[0])
    elif pred['pred'] == 'D' and draw_scores: picks.append(draw_scores[0])
    elif pred['pred'] == 'A' and away_scores: picks.append(away_scores[0])

    probs = [('H', pred['hp'], home_scores), ('D', pred['dp'], draw_scores), ('A', pred['ap'], away_scores)]
    probs_sorted = sorted(probs, key=lambda x: -x[1])
    for d, prob, sc_list in probs_sorted:
        if d != pred['pred'] and sc_list:
            picks.append(sc_list[0])
            break

    if pred['pred'] == 'H' and len(home_scores) > 1: picks.append(home_scores[1])
    elif pred['pred'] == 'D' and len(draw_scores) > 1: picks.append(draw_scores[1])
    elif pred['pred'] == 'A' and len(away_scores) > 1: picks.append(away_scores[1])
    else:
        for d, prob, sc_list in probs_sorted:
            already = [score_dir(s) for s, _ in picks]
            if d not in already and sc_list:
                picks.append(sc_list[0])
                break

    s1 = picks[0][0] if len(picks) > 0 else '-'
    s2 = picks[1][0] if len(picks) > 1 else '-'
    s3 = picks[2][0] if len(picks) > 2 else '-'

    match_str = f'{m["home"]}vs{m["away"]}'
    p(f'  {m["num_str"]:8s} {match_str:28s} {pred_cn:8s} {conf_str:6s} {rq_str:12s} {s1:8s} {s2:8s} {s3:8s}')

# ===== 最终推荐 =====
p('')
p(f'{"="*85}')
p(f'  最终推荐 (v3.10模型)')
p(f'{"="*85}')

# 逐场给出最终结论
finals = []
for m in matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    if not oh or not od or not oa: continue

    pred = predict_v310(oh, od, oa, m['league'])
    rq_pred = predict_v310(m['rqh'], m['rqd'], m['rqa'], m['league'])

    home_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'H']
    draw_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'D']
    away_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'A']

    picks = []
    if pred['pred'] == 'H' and home_scores: picks.append(home_scores[0])
    elif pred['pred'] == 'D' and draw_scores: picks.append(draw_scores[0])
    elif pred['pred'] == 'A' and away_scores: picks.append(away_scores[0])

    probs = [('H', pred['hp'], home_scores), ('D', pred['dp'], draw_scores), ('A', pred['ap'], away_scores)]
    probs_sorted = sorted(probs, key=lambda x: -x[1])
    for d, prob, sc_list in probs_sorted:
        if d != pred['pred'] and sc_list:
            picks.append(sc_list[0])
            break
    if pred['pred'] == 'H' and len(home_scores) > 1: picks.append(home_scores[1])
    elif pred['pred'] == 'D' and len(draw_scores) > 1: picks.append(draw_scores[1])
    elif pred['pred'] == 'A' and len(away_scores) > 1: picks.append(away_scores[1])
    else:
        for d, prob, sc_list in probs_sorted:
            already = [score_dir(s) for s, _ in picks]
            if d not in already and sc_list:
                picks.append(sc_list[0])
                break

    rq_dir = rq_pred['pred'] if rq_pred else None
    rq_cn = {'H':'让胜','D':'让平','A':'让负'}[rq_dir] if rq_dir else ''

    # 评分
    score_val = 0
    reasons = []

    # 置信度
    if pred['conf'] >= 0.55:
        score_val += 3; reasons.append('高置信')
    elif pred['conf'] >= 0.40:
        score_val += 1; reasons.append('中置信')
    else:
        score_val -= 1; reasons.append('低置信/胶着')

    # EV
    best_ev = max(pred['ev_h'], pred['ev_d'], pred['ev_a'])
    if best_ev > -0.05:
        score_val += 2; reasons.append('EV接近正')
    elif best_ev > -0.10:
        score_val += 0
    else:
        score_val -= 1

    # SPF+让球同向
    if rq_dir and pred['pred'] == rq_dir:
        score_val += 1; reasons.append('SPF+让球同向')
    elif rq_dir:
        score_val -= 1; reasons.append('SPF与让球矛盾')

    # 联赛因素
    if m['league'] == '国际赛':
        score_val -= 2; reasons.append('友谊赛不确定')
    if m['league'] == '芬超':
        score_val += 1; reasons.append('联赛数据清晰')

    # 特殊判断
    if m['home'] == 'AC奥卢' and m['away'] == '雅罗':
        score_val += 3; reasons.append('主100%胜vs客0%胜')
    if m['home'] == '日本' and m['away'] == '冰岛':
        score_val += 2; reasons.append('实力碾压')
    if m['home'] == '代格福什' and m['away'] == '布鲁马波卡纳':
        score_val -= 3; reasons.append('排名/赔率矛盾')
    if m['home'] == '美国' and m['away'] == '塞内加尔':
        score_val -= 1; reasons.append('势均力敌')

    if score_val >= 4: tier = 'A'
    elif score_val >= 1: tier = 'B'
    else: tier = 'C'

    finals.append({
        'm': m, 'pred': pred, 'rq_pred': rq_pred, 'picks': picks,
        'tier': tier, 'score_val': score_val, 'reasons': reasons,
        'rq_cn': rq_cn, 'rq_dir': rq_dir,
    })

# 按档位输出
for tier_name, tier_label in [('A','A档(重点)'), ('B','B档(小注)'), ('C','C档(避让)')]:
    tier_matches = [f for f in finals if f['tier'] == tier_name]
    if not tier_matches: continue

    p('')
    p(f'  【{tier_label}】')
    for f in tier_matches:
        m = f['m']
        pred = f['pred']
        picks = f['picks']
        rq_cn = f['rq_cn']
        rq_pred = f['rq_pred']

        pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]

        p(f'')
        p(f'  {m["num_str"]} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]}')
        p(f'  SPF: {pred_cn}({pred["conf"]*100:.0f}%) 赔率{m["oh"]:.2f}/{m["od"]:.2f}/{m["oa"]:.2f}')

        if m['hc'] and rq_cn:
            p(f'  让球: 让{m["hc"]} {rq_cn}({rq_pred["conf"]*100:.0f}%) 赔率{m["rqh"]:.2f}/{m["rqd"]:.2f}/{m["rqa"]:.2f}')

        p(f'  比分: {" / ".join(f"{s}({o:.1f})" for s, o in picks[:3])}')
        p(f'  评分: {f["score_val"]} {" ".join(f["reasons"])}')

# 串关建议
p('')
p(f'  {"─"*75}')
p(f'  串关建议:')
p(f'')

a_tier = [f for f in finals if f['tier'] == 'A']
b_tier = [f for f in finals if f['tier'] == 'B']

# 2串1
if len(a_tier) >= 2:
    for i in range(min(3, len(a_tier))):
        for j in range(i+1, min(4, len(a_tier))):
            f1, f2 = a_tier[i], a_tier[j]
            m1, m2 = f1['m'], f2['m']
            p1_cn = {'H':'主胜','D':'平局','A':'客胜'}[f1['pred']['pred']]
            p2_cn = {'H':'主胜','D':'平局','A':'客胜'}[f2['pred']['pred']]
            o1 = f1['pred']['conf']  # use conf as proxy
            o2 = f2['pred']['conf']
            # 实际赔率
            dir_odds1 = {'H':m1['oh'],'D':m1['od'],'A':m1['oa']}[f1['pred']['pred']]
            dir_odds2 = {'H':m2['oh'],'D':m2['od'],'A':m2['oa']}[f2['pred']['pred']]
            combo = dir_odds1 * dir_odds2
            p(f'    {m1["num_str"]}{p1_cn}({dir_odds1:.2f}) x {m2["num_str"]}{p2_cn}({dir_odds2:.2f}) = {combo:.2f}')

# 让球串
rq_picks = [f for f in finals if f['rq_dir'] and f['tier'] in ('A','B') and f['rq_pred']['conf'] >= 0.40]
if len(rq_picks) >= 2:
    p(f'')
    p(f'  让球2串1:')
    for i in range(min(2, len(rq_picks))):
        for j in range(i+1, min(3, len(rq_picks))):
            f1, f2 = rq_picks[i], rq_picks[j]
            m1, m2 = f1['m'], f2['m']
            rq1_odds = {'H':m1['rqh'],'D':m1['rqd'],'A':m1['rqa']}[f1['rq_dir']]
            rq2_odds = {'H':m2['rqh'],'D':m2['rqd'],'A':m2['rqa']}[f2['rq_dir']]
            combo = rq1_odds * rq2_odds
            p(f'    {m1["num_str"]}让{m1["hc"]}{f1["rq_cn"]}({rq1_odds:.2f}) x {m2["num_str"]}让{m2["hc"]}{f2["rq_cn"]}({rq2_odds:.2f}) = {combo:.2f}')

# 比分串
p(f'')
p(f'  比分2串1(高风险高回报):')
score_picks = [f for f in finals if f['tier'] in ('A','B') and len(f['picks']) >= 2]
if len(score_picks) >= 2:
    for i in range(min(2, len(score_picks))):
        for j in range(i+1, min(3, len(score_picks))):
            f1, f2 = score_picks[i], score_picks[j]
            s1, o1 = f1['picks'][0]
            s2, o2 = f2['picks'][0]
            combo = o1 * o2
            p(f'    {f1["m"]["num_str"]}比分{s1}({o1:.1f}) x {f2["m"]["num_str"]}比分{s2}({o2:.1f}) = {combo:.1f}')

p('')
p('=' * 85)

report = '\n'.join(lines)
print(report)
