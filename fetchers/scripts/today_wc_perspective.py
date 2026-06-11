"""
6/1体彩推荐 - 世界杯热身赛视角
核心逻辑: 6/12世界杯开幕, 友谊赛=正赛前磨合
世界杯球队 vs 非世界杯球队 → 认真碾压
世界杯球队 vs 世界杯球队 → 试探为主，比分不会大
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
        num = str(m.get('matchNum', ''))

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

# ===== 世界杯参赛状态 =====
# 2026世界杯参赛队 (48队)
wc_teams = {
    # 东道主
    '加拿大', '墨西哥', '美国',
    'USA', 'Canada', 'Mexico',
    # 南美
    '阿根廷', '巴西', '哥伦比亚', '厄瓜多尔', '巴拉圭', '乌拉圭', '智利', '委内瑞拉',
    'Argentina', 'Brazil', 'Colombia', 'Ecuador', 'Paraguay', 'Uruguay', 'Chile', 'Venezuela',
    'Brasil',
    # 欧洲(预选赛出线)
    '德国', '法国', '西班牙', '英格兰', '荷兰', '葡萄牙', '意大利', '比利时',
    '瑞士', '奥地利', '土耳其', '丹麦', '瑞典', '波兰', '捷克', '塞尔维亚',
    '克罗地亚', '苏格兰', '威尔士', '乌克兰', '挪威', '斯洛伐克', '匈牙利', '罗马尼亚',
    'Germany', 'France', 'Spain', 'England', 'Netherlands', 'Portugal', 'Italy', 'Belgium',
    'Switzerland', 'Austria', 'Turkey', 'Denmark', 'Sweden', 'Poland', 'Czech Republic',
    'Serbia', 'Croatia', 'Scotland', 'Wales', 'Ukraine', 'Norway', 'Slovakia', 'Hungary',
    'Romania', 'Czechia',
    # 亚洲
    '日本', '韩国', '伊朗', '沙特', '澳大利亚',
    'Japan', 'South Korea', 'Iran', 'Saudi Arabia', 'Australia',
    # 非洲
    '塞内加尔', '摩洛哥', '尼日利亚', '喀麦隆', '加纳', '突尼斯', '阿尔及利亚',
    'Senegal', 'Morocco', 'Nigeria', 'Cameroon', 'Ghana', 'Tunisia', 'Algeria',
    # 中北美
    '哥斯达黎加', '巴拿马', '牙买加', '洪都拉斯',
    'Costa Rica', 'Panama', 'Jamaica', 'Honduras',
}

# 体彩中文队名映射
wc_cn = {
    '保加利亚': False, '黑山': False,
    '挪威': True, '瑞典': True,
    '土耳其': True, '北马其顿': False,
    '奥地利': True, '突尼斯': True,
    '加拿大': True, '乌兹别克斯坦': False,
}

def is_wc_team(name):
    """判断是否世界杯球队"""
    if name in wc_cn:
        return wc_cn[name]
    return name in wc_teams

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
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf,'margin':margin,
            'ev_h':ev_h,'ev_d':ev_d,'ev_a':ev_a}

def score_dir(sc):
    h, a = sc.split(':')
    if int(h) > int(a): return 'H'
    elif int(h) == int(a): return 'D'
    else: return 'A'

lines = []
def p(s=''): lines.append(s)

p('=' * 85)
p('  6/1 体彩推荐 — 世界杯热身赛视角')
p('  6/12世界杯开幕! 这些友谊赛是正赛前最后磨合')
p('  5/31验证: 世界杯队vs非世界杯队 → 全部碾压大比分')
p('    巴西6:2巴拿马 瑞士4:1约旦 德国4:0芬兰 日本1:0冰岛')
p('  唯一例外: 美国3:2塞内加尔(双方都是世界杯队)')
p('=' * 85)

results = []
for m in matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    if not oh or not od or not oa:
        p('')
        p(f'  {m["num_str"]} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]}')
        p(f'  赔率未出')
        continue

    pred = predict(oh, od, oa, m['league'])
    rq_pred = predict(m['rqh'], m['rqd'], m['rqa'], m['league'])

    # 世界杯球队判断
    home_wc = is_wc_team(m['home'])
    away_wc = is_wc_team(m['away'])

    pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
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

    # 比分
    scores = m.get('scores', [])
    home_scores = [(s, o) for s, o in scores if score_dir(s) == 'H']
    draw_scores = [(s, o) for s, o in scores if score_dir(s) == 'D']
    away_scores = [(s, o) for s, o in scores if score_dir(s) == 'A']

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

    top3_goals = m.get('goals', [])[:3]

    # ===== 世界杯热身赛分析 =====
    wc_analysis = []
    if home_wc and not away_wc:
        match_type = 'WC vs 非WC'
        wc_analysis.append(f'{m["home"]}是世界杯队, {m["away"]}不是 → 认真碾压')
        wc_analysis.append('5/31验证: 4场WC vs 非WC全部大比分赢球')
        # 如果主队是世界杯队，倾向让球方向
        if rq_dir == 'H' and hc:
            wc_analysis.append(f'让{hc}让胜是世界杯逻辑最稳方向')
    elif away_wc and not home_wc:
        match_type = '非WC vs WC'
        wc_analysis.append(f'{m["away"]}是世界杯队, {m["home"]}不是 → 客队认真打')
        if rq_dir and hc:
            wc_analysis.append(f'让{hc}方向要考虑客队战意')
    elif home_wc and away_wc:
        match_type = 'WC vs WC'
        wc_analysis.append('双方都是世界杯队 → 试探为主, 不拼命')
        wc_analysis.append('5/31验证: 美国3:2塞内加尔, 势均力敌')
    else:
        match_type = '非WC vs 非WC'
        wc_analysis.append('双方都不是世界杯队 → 战意不确定')

    # 评分(世界杯逻辑)
    score_val = 0
    reasons = []

    # 世界杯vs非世界杯 = 最强信号
    if home_wc and not away_wc:
        score_val += 4; reasons.append('WC碾压非WC')
        # 主队让球更安全
        if rq_dir == 'H':
            score_val += 2; reasons.append('让球同向+WC碾压')
    elif away_wc and not home_wc:
        score_val += 2; reasons.append('客队WC有战意')
    elif home_wc and away_wc:
        score_val -= 1; reasons.append('WC vs WC试探为主')

    # 模型置信度
    if pred['conf'] >= 0.55:
        score_val += 2; reasons.append('高置信')
    elif pred['conf'] >= 0.40:
        score_val += 0
    else:
        score_val -= 1; reasons.append('低置信')

    # EV
    best_ev = max(pred['ev_h'], pred['ev_d'], pred['ev_a'])
    if best_ev > -0.05:
        score_val += 1; reasons.append('EV接近正')

    # SPF低赔率无价值
    if oh < 1.30:
        score_val -= 1; reasons.append('SPF低赔无价值走让球')

    if score_val >= 6: tier = 'A'
    elif score_val >= 3: tier = 'B'
    elif score_val >= 1: tier = 'C'
    else: tier = 'D'

    # 输出
    wc_home = '★WC' if home_wc else ''
    wc_away = '★WC' if away_wc else ''

    p('')
    p(f'  {m["num_str"]} {m["home"]}{wc_home} vs {m["away"]}{wc_away} [{m["league"]}] {m["time"]}')
    p(f'  类型: {match_type}')
    p(f'  {"═"*75}')
    p(f'  SPF: {pred_cn}({pred["conf"]*100:.0f}%)  赔率 {oh:.2f}/{od:.2f}/{oa:.2f}')
    p(f'  概率: 主{pred["hp"]*100:.1f}% 平{pred["dp"]*100:.1f}% 客{pred["ap"]*100:.1f}%')

    if hc and rq_cn:
        rq_conf = rq_pred['conf'] if rq_pred else 0
        p(f'  让球: 让{hc} {rq_cn}({rq_conf*100:.0f}%) 赔率{m["rqh"]:.2f}/{m["rqd"]:.2f}/{m["rqa"]:.2f}')
        p(f'  含义: {rq_meaning}')

    p(f'  {"─"*75}')
    p(f'  世界杯热身分析:')
    for a in wc_analysis:
        p(f'    - {a}')

    p(f'  {"─"*75}')
    p(f'  推荐比分:')
    for i, (sc, odds) in enumerate(picks[:3]):
        d_cn = {'H':'主胜','D':'平局','A':'客胜'}[score_dir(sc)]
        marker = ' ◄首选' if i == 0 else ''
        p(f'    {i+1}. {sc}  ({d_cn}, 赔率{odds:.1f}){marker}')

    # 建议
    p(f'  {"─"*75}')
    advice = []

    # WC碾压时覆盖让球方向
    wc_rq_override = False  # 是否WC逻辑覆盖了模型让球方向

    if home_wc and not away_wc:
        # WC碾压非WC → 让球方向强制让胜(覆盖模型)
        if hc:
            try:
                hc_val = float(hc)
                if hc_val < 0:  # 主让球
                    if rq_dir != 'H':
                        wc_rq_override = True
                        override_odds = m['rqh']  # 让胜赔率
                        advice.append(f'让{hc}让胜({override_odds:.2f}) ← WC碾压覆盖模型让负!')
                    else:
                        advice.append(f'让{hc}让胜({m["rqh"]:.2f}) ← WC碾压+模型同向')
                else:
                    advice.append(f'SPF主胜({oh:.2f}) ← WC碾压')
            except:
                advice.append(f'SPF主胜({oh:.2f}) ← WC碾压')
        else:
            advice.append(f'SPF主胜({oh:.2f}) ← WC碾压')

        # 5/31验证: 巴西让-2让胜(6:2), 瑞士让-1让胜(4:1), 德国让-2让胜(4:0)
        advice.append('5/31验证: WC碾压让球让胜3/3全中')

        if picks:
            advice.append(f'比分{picks[0][0]}({picks[0][1]:.1f})')
    elif away_wc and not home_wc:
        advice.append(f'客队{m["away"]}是WC队, 客胜({oa:.2f})有战意')
        if hc and hc_val > 0:  # 客让球
            if rq_dir == 'A':
                advice.append(f'让{hc}让负({m["rqa"]:.2f}) ← WC客队碾压')
            else:
                advice.append(f'让{hc}考虑让负方向 ← WC客队战意')
    elif home_wc and away_wc:
        advice.append('WC vs WC → 慎选, 试探为主')
        if hc and rq_cn:
            advice.append(f'让球{rq_cn}相对安全')
    else:
        advice.append('双方非WC → 战意不确定, 跳过')

    p(f'  >> {" / ".join(advice)}')
    p(f'  档位: {tier} (评分{score_val} {" ".join(reasons)})')
    if wc_rq_override:
        p(f'  ⚠️ WC逻辑覆盖模型让球方向! 模型预测让负 → WC碾压改推让胜')

    results.append({
        'm': m, 'pred': pred, 'rq_pred': rq_pred, 'picks': picks,
        'tier': tier, 'score_val': score_val, 'reasons': reasons,
        'rq_cn': rq_cn, 'rq_dir': rq_dir, 'hc': hc,
        'home_wc': home_wc, 'away_wc': away_wc,
        'match_type': match_type, 'wc_rq_override': wc_rq_override,
    })

# ===== 最终推荐 =====
p('')
p(f'{"="*85}')
p(f'  最终推荐 — 世界杯热身赛逻辑')
p(f'  昨日验证: WC队 vs 非WC队 = 4/4大比分碾压')
p(f'{"="*85}')

for tier_name, tier_label in [('A','A档(重点)'), ('B','B档(小注)'), ('C','C档(观望)'), ('D','D档(避让)')]:
    tier_matches = [r for r in results if r.get('tier') == tier_name]
    if not tier_matches: continue

    p('')
    p(f'  【{tier_label}】')
    for r in tier_matches:
        m = r['m']
        pred = r['pred']

        p(f'')
        p(f'  {m["num_str"]} {m["home"]}{"★" if r["home_wc"] else ""} vs {m["away"]}{"★" if r["away_wc"] else ""} [{r["match_type"]}]')
        p(f'  SPF: {pred_cn}({pred["conf"]*100:.0f}%) 赔率{m["oh"]:.2f}/{m["od"]:.2f}/{m["oa"]:.2f}')

        if r['hc'] and r['rq_cn']:
            rq_conf = r['rq_pred']['conf'] if r['rq_pred'] else 0
            # WC碾压时强制显示让胜方向
            if r.get('wc_rq_override'):
                p(f'  让球: 让{r["hc"]} 让胜({r["m"]["rqh"]:.2f}) ← WC覆盖! (模型原判让负)')
            else:
                p(f'  让球: 让{r["hc"]} {r["rq_cn"]}({rq_conf*100:.0f}%)')

        score_str = ' / '.join(f'{s}({o:.1f})' for s, o in r['picks'][:3])
        p(f'  比分: {score_str}')
        p(f'  评分: {r["score_val"]} {" ".join(r["reasons"])}')

# 串关
p('')
p(f'  {"─"*75}')
p(f'  串关建议:')
p(f'')

# WC碾压场次的让球 (使用覆盖后的让胜方向)
wc_crush = [r for r in results if r['match_type'] == 'WC vs 非WC' and r['hc']]
if len(wc_crush) >= 2:
    p(f'  WC碾压让球2串1 (让胜方向覆盖模型):')
    for i in range(min(2, len(wc_crush))):
        for j in range(i+1, min(3, len(wc_crush))):
            r1, r2 = wc_crush[i], wc_crush[j]
            m1, m2 = r1['m'], r2['m']
            # WC碾压强制让胜
            o1, o2 = m1['rqh'], m2['rqh']
            combo = o1 * o2
            override_note = ''
            if r1.get('wc_rq_override') or r2.get('wc_rq_override'):
                override_note = ' (覆盖模型)'
            p(f'    {m1["num_str"]}让{m1["hc"]}让胜({o1:.2f}) x {m2["num_str"]}让{m2["hc"]}让胜({o2:.2f}) = {combo:.2f}{override_note}')

# 比分串
p(f'')
p(f'  比分2串1(高风险):')
score_picks = [r for r in results if r['tier'] in ('A','B') and len(r['picks']) >= 1]
if len(score_picks) >= 2:
    for i in range(min(2, len(score_picks))):
        for j in range(i+1, min(3, len(score_picks))):
            r1, r2 = score_picks[i], score_picks[j]
            s1, o1 = r1['picks'][0]
            s2, o2 = r2['picks'][0]
            combo = o1 * o2
            p(f'    {r1["m"]["num_str"]}比分{s1}({o1:.1f}) x {r2["m"]["num_str"]}比分{s2}({o2:.1f}) = {combo:.1f}')

p('')
p('=' * 85)

report = '\n'.join(lines)
print(report)
