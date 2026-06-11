"""
5/31 全场完整推荐 7003-7012
包含已停售比赛(用之前获取的赔率) + 在售比赛(实时赔率)
3个推荐比分 + 让球方向 + 综合分析
v3.10模型(均衡赔率draw boost)
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

# 获取实时赔率
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

# 实时赔率
live_matches = {}
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

        live_matches[num] = {
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
        }

# 全部10场比赛(含已停售的赔率数据)
all_matches = [
    # 已结束
    {'num': '7001', 'num_str': '周日001', 'time': '18:00', 'league': '日职',
     'home': '冈山绿雉', 'away': '浦和红钻',
     'oh': 2.90, 'od': 3.00, 'oa': 2.22,
     'hc': '+1', 'rqh': 1.42, 'rqd': 3.95, 'rqa': 5.35,
     'scores': [], 'goals': [], 'finished': '1:1平局'},
    {'num': '7002', 'num_str': '周日002', 'time': '18:00', 'league': '日职',
     'home': '清水鼓动', 'away': '横滨水手',
     'oh': 2.52, 'od': 3.10, 'oa': 2.44,
     'hc': '+1', 'rqh': 1.38, 'rqd': 4.00, 'rqa': 5.80,
     'scores': [], 'goals': [], 'finished': '1:1平局'},
    # 已停售(开赛前)
    {'num': '7003', 'num_str': '周日003', 'time': '18:25', 'league': '国际赛',
     'home': '日本', 'away': '冰岛',
     'oh': 1.12, 'od': 6.25, 'oa': 13.00,
     'hc': '-2', 'rqh': 2.20, 'rqd': 3.80, 'rqa': 2.47,
     'scores': [('2:0',6.0),('3:0',6.5),('3:1',10.0),('4:0',15.0),('1:0',11.0),('2:1',8.0)],
     'goals': [('3球',3.2),('2球',3.5),('4球',4.8)]},
    {'num': '7004', 'num_str': '周日004', 'time': '20:00', 'league': '瑞超',
     'home': '韦斯特罗斯', 'away': 'IFK哥德堡',
     'oh': 2.46, 'od': 3.00, 'oa': 2.57,
     'hc': '-1', 'rqh': 5.50, 'rqd': 4.10, 'rqa': 1.42,
     'scores': [('1:1',5.5),('0:0',8.0),('1:0',8.0),('0:1',9.0),('2:1',11.0),('2:0',17.0)],
     'goals': [('2球',3.3),('1球',3.8),('3球',4.0)]},
    {'num': '7005', 'num_str': '周日005', 'time': '20:00', 'league': '瑞超',
     'home': '赫根', 'away': '哈马比',
     'oh': 2.77, 'od': 3.35, 'oa': 2.13,
     'hc': '+1', 'rqh': 1.54, 'rqd': 4.00, 'rqa': 4.35,
     'scores': [('1:2',7.3),('2:1',8.2),('0:1',11.0),('1:1',5.8),('0:0',11.0),('2:0',13.0)],
     'goals': [('2球',3.4),('3球',3.5),('1球',4.0)]},
    {'num': '7006', 'num_str': '周日006', 'time': '20:00', 'league': '瑞超',
     'home': '代格福什', 'away': '布鲁马波卡纳',
     'oh': 2.10, 'od': 3.15, 'oa': 2.98,
     'hc': '-1', 'rqh': 4.75, 'rqd': 3.65, 'rqa': 1.55,
     'scores': [('1:0',5.8),('1:1',5.8),('2:1',8.0),('0:1',8.5),('2:0',8.5),('0:0',10.0)],
     'goals': [('2球',3.2),('1球',3.8),('3球',4.2)]},
    {'num': '7008', 'num_str': '周日008', 'time': '21:00', 'league': '芬超',
     'home': 'AC奥卢', 'away': '雅罗',
     'oh': 1.50, 'od': 3.90, 'oa': 4.85,
     'hc': '-1', 'rqh': 2.74, 'rqd': 3.25, 'rqa': 2.19,
     'scores': [('2:1',6.5),('1:1',7.8),('1:0',6.8),('2:0',8.5),('0:0',12.0),('0:1',15.0)],
     'goals': [('3球',3.5),('2球',3.6),('4球',5.0)]},
]

# 用实时数据覆盖007-012
for num in ['7007','7008','7009','7010','7011','7012']:
    if num in live_matches:
        m = live_matches[num]
        m['finished'] = None
        all_matches.append(m)

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
p('  5/31(周日) 全场完整推荐  v3.10模型')
p('  3个推荐比分 + 让球方向 + 综合分析')
p('=' * 85)

# 分析每场比赛
results = []
for m in all_matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    num = m['num']
    num_str = m['num_str']

    # 已结束的比赛
    if m.get('finished'):
        pred = predict_v310(oh, od, oa, m.get('league',''))
        actual = m['finished']
        pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']] if pred else '?'
        p('')
        p(f'  {num_str} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]}')
        p(f'  已结束: {actual}  模型预测: {pred_cn}')
        if pred and pred['is_balanced']:
            p(f'  均衡赔率(极差{max(oh,od,oa)-min(oh,od,oa):.2f}<0.8) → v3.10正确提升draw')
        continue

    if not oh or not od or not oa:
        p('')
        p(f'  {num_str} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]}')
        p(f'  赔率未出 → 无法分析，跳过')
        p(f'  {"─"*75}')
        continue

    pred = predict_v310(oh, od, oa, m.get('league',''))
    rq_pred = predict_v310(m.get('rqh',0), m.get('rqd',0), m.get('rqa',0), m.get('league',''))

    pred_dir = pred['pred']
    pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred_dir]
    bal_str = '均衡' if pred['is_balanced'] else ''

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

    # 均衡赔率+平局EV正 → 重新选比分(平局优先)
    if pred['is_balanced'] and pred['ev_d'] > -0.01 and draw_scores:
        picks = [draw_scores[0]]
        for d, prob, sc_list in probs_sorted:
            if d != 'D' and sc_list:
                picks.append(sc_list[0])
                break
        if len(draw_scores) > 1:
            picks.append(draw_scores[1])
        else:
            for d, prob, sc_list in probs_sorted:
                already = [score_dir(s) for s, _ in picks]
                if d not in already and sc_list:
                    picks.append(sc_list[0])
                    break

    # EV
    evs = [('主胜',pred['ev_h'],oh), ('平局',pred['ev_d'],od), ('客胜',pred['ev_a'],oa)]
    evs.sort(key=lambda x: -x[1])
    best_ev = evs[0]

    rq_evs = []
    if rq_pred:
        rq_evs = [('让胜',rq_pred['ev_h'],m['rqh']), ('让平',rq_pred['ev_d'],m['rqd']), ('让负',rq_pred['ev_a'],m['rqa'])]
        rq_evs.sort(key=lambda x: -x[1])

    # 输出
    p('')
    p(f'  {num_str} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]}')
    p(f'  {"═"*75}')
    p(f'  SPF: {pred_cn}({pred["conf"]*100:.1f}%)  赔率 {oh:.2f}/{od:.2f}/{oa:.2f}  {bal_str}')
    p(f'  概率: 主{pred["hp"]*100:.1f}% 平{pred["dp"]*100:.1f}% 客{pred["ap"]*100:.1f}%')
    p(f'  EV:  {evs[0][0]}{evs[0][1]:+.3f}  {evs[1][0]}{evs[1][1]:+.3f}  {evs[2][0]}{evs[2][1]:+.3f}')
    p(f'  {"─"*75}')

    # SPF方向
    if pred['is_balanced'] and pred['ev_d'] > -0.01:
        # 均衡+平局EV正 → 推荐平局
        spf_display = f'平局(推荐) 模型原始{pred_cn}({pred["conf"]*100:.0f}%)'
        spf_note = '均衡+平局EV正→推荐平局 ✓'
    elif pred['conf'] >= 0.50:
        spf_display = f'{pred_cn}({pred["conf"]*100:.0f}%)'
        spf_note = '置信较高 ✓'
    elif pred['conf'] >= 0.35:
        spf_display = f'{pred_cn}({pred["conf"]*100:.0f}%)'
        spf_note = '置信一般，胶着'
    else:
        spf_display = f'{pred_cn}({pred["conf"]*100:.0f}%)'
        spf_note = '置信很低，慎选'
    p(f'  SPF方向: {spf_display} {spf_note}')

    # 让球方向
    if hc and rq_cn:
        rq_conf = rq_pred['conf'] if rq_pred else 0
        if rq_conf >= 0.50:
            rq_note = '置信较高 ✓'
        elif rq_conf >= 0.35:
            rq_note = '置信一般'
        else:
            rq_note = '置信低'
        p(f'  让球方向: 让{hc} {rq_cn}({rq_conf*100:.0f}%) {rq_note}')
        p(f'    含义: {rq_meaning}')
        p(f'    让球赔率: {m["rqh"]:.2f}/{m["rqd"]:.2f}/{m["rqa"]:.2f}')
        if rq_evs:
            p(f'    让球EV: {rq_evs[0][0]}{rq_evs[0][1]:+.3f}(赔{rq_evs[0][2]:.2f})')
    else:
        p(f'  让球: 赔率未出')

    # 推荐比分
    p(f'  {"─"*75}')
    p(f'  推荐比分:')
    for i, (sc, odds) in enumerate(picks[:3]):
        d_cn = {'H':'主胜','D':'平局','A':'客胜'}[score_dir(sc)]
        marker = ' ◄首选' if i == 0 else ''
        p(f'    {i+1}. {sc}  ({d_cn}, 赔率{odds:.1f}){marker}')

    # 大小球
    if top3_goals:
        p(f'  大小球: {" / ".join(f"{g}({v:.1f})" for g, v in top3_goals)}')

    # 特殊提示
    notes = []
    if pred['is_balanced']:
        notes.append('均衡赔率→v3.10提升draw')
    if m.get('league') == '国际赛':
        notes.append('友谊赛/国际赛战意不确定')
    if oh < 1.30 or oa < 1.30:
        fav = '主' if oh < oa else '客'
        notes.append(f'{fav}方低赔率({min(oh,oa):.2f})，SPF无价值，走让球')
    if oh >= 1.25 and oh <= 1.35:
        notes.append('冷门区1.25-1.35')
    # 均衡赔率+平局EV正 → 强制推荐平局
    if pred['is_balanced'] and pred['ev_d'] > -0.01:
        # 重新选比分：平局优先
        if draw_scores:
            picks = [draw_scores[0]]  # 首选平局比分
            # 第二选：最高概率方向
            for d, prob, sc_list in probs_sorted:
                if d != 'D' and sc_list:
                    picks.append(sc_list[0])
                    break
            # 第三选：平局第二比分 或 第三方向
            if len(draw_scores) > 1:
                picks.append(draw_scores[1])
            else:
                for d, prob, sc_list in probs_sorted:
                    already = [score_dir(s) for s, _ in picks]
                    if d not in already and sc_list:
                        picks.append(sc_list[0])
                        break
            # 覆盖SPF推荐为平局
            pred_cn_override = '平局'
            notes.append('均衡+平局EV正→推荐平局')
        else:
            pred_cn_override = None
    else:
        pred_cn_override = None
    if m['home'] == '日本' and m['away'] == '冰岛':
        notes.append('FIFA#15 vs #72，实力差3档')
        notes.append('让-2让胜(2.20)比SPF主胜(1.12)有价值')
    if m['home'] == 'AC奥卢' and m['away'] == '雅罗':
        notes.append('主场3战全胜 vs 客场5战0胜')
    if m['home'] == '代格福什' and m['away'] == '布鲁马波卡纳':
        notes.append('排名13vs7，赔率开主让-1矛盾')
    if m['home'] == '美国' and m['away'] == '塞内加尔':
        notes.append('FIFA#13 vs #17，势均力敌')

    if notes:
        p(f'  {"─"*75}')
        for n in notes:
            p(f'  ! {n}')

    # 存储
    results.append({
        'm': m, 'pred': pred, 'rq_pred': rq_pred, 'picks': picks,
        'rq_cn': rq_cn, 'rq_dir': rq_dir, 'hc': hc,
        'notes': notes,
    })

# ===== 汇总表 =====
p('')
p(f'{"="*85}')
p(f'  汇总推荐表')
p(f'{"="*85}')
p('')
p(f'  {"编号":8s} {"比赛":24s} {"SPF":8s} {"置信":6s} {"让球":14s} {"比分1":8s} {"比分2":8s} {"比分3":8s}')
p(f'  {"─"*85}')

for r in results:
    m = r['m']
    pred = r['pred']
    picks = r['picks']

    pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
    conf_str = f'{pred["conf"]*100:.0f}%'
    rq_str = f'让{r["hc"]}{r["rq_cn"]}' if r['hc'] and r['rq_cn'] else '-'

    s1 = picks[0][0] if len(picks) > 0 else '-'
    s2 = picks[1][0] if len(picks) > 1 else '-'
    s3 = picks[2][0] if len(picks) > 2 else '-'

    match_str = f'{m["home"]}vs{m["away"]}'
    if len(match_str) > 24: match_str = match_str[:24]
    p(f'  {m["num_str"]:8s} {match_str:24s} {pred_cn:8s} {conf_str:6s} {rq_str:14s} {s1:8s} {s2:8s} {s3:8s}')

# ===== 最终推荐 =====
p('')
p(f'{"="*85}')
p(f'  最终推荐 (v3.10模型)')
p(f'{"="*85}')

# 评分
for r in results:
    m = r['m']
    pred = r['pred']
    score_val = 0
    reasons = []

    if pred['conf'] >= 0.55:
        score_val += 3; reasons.append('高置信')
    elif pred['conf'] >= 0.40:
        score_val += 1; reasons.append('中置信')
    else:
        score_val -= 1; reasons.append('低置信/胶着')

    best_ev = max(pred['ev_h'], pred['ev_d'], pred['ev_a'])
    if best_ev > -0.05:
        score_val += 2; reasons.append('EV接近正')
    elif best_ev > -0.10:
        score_val += 0
    else:
        score_val -= 1

    rq_dir = r['rq_dir']
    if rq_dir and pred['pred'] == rq_dir:
        score_val += 1; reasons.append('SPF+让球同向')
    elif rq_dir:
        score_val -= 1; reasons.append('SPF与让球矛盾')

    if m.get('league') == '国际赛':
        score_val -= 2; reasons.append('友谊赛不确定')
    if m.get('league') == '芬超':
        score_val += 1; reasons.append('联赛数据清晰')
    if m.get('league') == '瑞超':
        score_val += 1; reasons.append('联赛数据清晰')

    # 特殊
    if m['home'] == '日本' and m['away'] == '冰岛':
        score_val += 2; reasons.append('实力碾压')
    if m['home'] == 'AC奥卢' and m['away'] == '雅罗':
        score_val += 3; reasons.append('主100%胜vs客0%胜')
    if m['home'] == '捷克' and m['away'] == '科索沃':
        score_val += 1; reasons.append('FIFA差63位')
    if m['home'] == '代格福什' and m['away'] == '布鲁马波卡纳':
        score_val -= 3; reasons.append('排名/赔率矛盾')
    if m['home'] == '美国' and m['away'] == '塞内加尔':
        score_val -= 1; reasons.append('势均力敌')
    if m['home'] == '韦斯特罗斯' and m['away'] == 'IFK哥德堡':
        score_val += 1; reasons.append('双方平局多')
        # 均衡赔率+平局EV正 → 额外加1
        if pred['is_balanced'] and pred['ev_d'] > -0.01:
            score_val += 1; reasons.append('平局EV正')
    if m['home'] == '赫根' and m['away'] == '哈马比':
        score_val += 0; reasons.append('赫根主场不败')

    # 低赔率SPF无价值
    if m['oh'] < 1.30 or m['oa'] < 1.30:
        score_val -= 1; reasons.append('SPF低赔无价值')

    if score_val >= 4: tier = 'A'
    elif score_val >= 1: tier = 'B'
    else: tier = 'C'

    r['tier'] = tier
    r['score_val'] = score_val
    r['reasons'] = reasons

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

        if r['hc'] and r['rq_cn']:
            rq_conf = rq_pred['conf'] if rq_pred else 0
            p(f'  让球: 让{r["hc"]} {r["rq_cn"]}({rq_conf*100:.0f}%) 赔率{m["rqh"]:.2f}/{m["rqd"]:.2f}/{m["rqa"]:.2f}')

        score_str = ' / '.join(f'{s}({o:.1f})' for s, o in picks[:3])
        p(f'  比分: {score_str}')
        p(f'  评分: {r["score_val"]} {" ".join(r["reasons"])}')

        # 给出具体操作建议
        advice = []
        # SPF
        if pred['conf'] >= 0.50 and min(m['oh'],m['od'],m['oa']) >= 1.40:
            dir_odds = {'H':m['oh'],'D':m['od'],'A':m['oa']}[pred['pred']]
            advice.append(f'SPF{pred_cn}({dir_odds:.2f})')
        # 让球
        if r['hc'] and r['rq_cn'] and rq_pred and rq_pred['conf'] >= 0.40:
            rq_odds = {'H':m['rqh'],'D':m['rqd'],'A':m['rqa']}[r['rq_dir']]
            if rq_odds >= 1.50:
                advice.append(f'让{r["hc"]}{r["rq_cn"]}({rq_odds:.2f})')
        # 比分
        if picks:
            advice.append(f'比分{picks[0][0]}({picks[0][1]:.1f})')

        if not advice:
            advice.append('本场不推荐，跳过')
        p(f'  >> 建议: {" / ".join(advice)}')

# 串关建议
p('')
p(f'  {"─"*75}')
p(f'  串关建议:')
p(f'')

# 收集A/B档可串选项
combo_options = []
for r in results:
    if r.get('tier') not in ('A','B'): continue
    m = r['m']
    pred = r['pred']
    rq_pred = r.get('rq_pred')

    # SPF选项
    if pred['conf'] >= 0.50:
        dir_odds = {'H':m['oh'],'D':m['od'],'A':m['oa']}[pred['pred']]
        pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
        if dir_odds >= 1.40:
            combo_options.append(('SPF', m['num_str'], pred_cn, dir_odds, r['tier']))

    # 让球选项
    if r['hc'] and r['rq_cn'] and rq_pred and rq_pred['conf'] >= 0.40:
        rq_odds = {'H':m['rqh'],'D':m['rqd'],'A':m['rqa']}[r['rq_dir']]
        if rq_odds >= 1.50:
            combo_options.append(('RQ', m['num_str'], f'让{r["hc"]}{r["rq_cn"]}', rq_odds, r['tier']))

# 2串1 (排除同场串、排除低水<1.50)
if len(combo_options) >= 2:
    p(f'  2串1:')
    shown = 0
    for i in range(len(combo_options)):
        for j in range(i+1, len(combo_options)):
            if shown >= 5: break
            o1, o2 = combo_options[i], combo_options[j]
            # 排除同场串
            if o1[1] == o2[1]: continue
            # 排除低水
            if o1[3] < 1.50 or o2[3] < 1.50: continue
            combo = o1[3] * o2[3]
            if combo >= 2.5:  # 只显示有价值的
                p(f'    {o1[1]}{o1[2]}({o1[3]:.2f}) x {o2[1]}{o2[2]}({o2[3]:.2f}) = {combo:.2f}')
                shown += 1
        if shown >= 5: break

# 3串1 (排除同场串、排除低水)
if len(combo_options) >= 3:
    p(f'')
    p(f'  3串1:')
    shown = 0
    for i in range(len(combo_options)):
        for j in range(i+1, len(combo_options)):
            for k in range(j+1, len(combo_options)):
                if shown >= 3: break
                o1, o2, o3 = combo_options[i], combo_options[j], combo_options[k]
                # 排除同场串
                if o1[1] == o2[1] or o1[1] == o3[1] or o2[1] == o3[1]: continue
                # 排除低水
                if o1[3] < 1.50 or o2[3] < 1.50 or o3[3] < 1.50: continue
                combo = o1[3] * o2[3] * o3[3]
                if combo >= 4.0:
                    p(f'    {o1[1]}{o1[2]}({o1[3]:.2f}) x {o2[1]}{o2[2]}({o2[3]:.2f}) x {o3[1]}{o3[2]}({o3[3]:.2f}) = {combo:.2f}')
                    shown += 1
            if shown >= 3: break
        if shown >= 3: break

# 比分串
p(f'')
p(f'  比分2串1(高风险高回报):')
score_combo = [r for r in results if r.get('tier') in ('A','B') and len(r['picks']) >= 1]
if len(score_combo) >= 2:
    shown = 0
    for i in range(min(3, len(score_combo))):
        for j in range(i+1, min(4, len(score_combo))):
            if shown >= 3: break
            f1, f2 = score_combo[i], score_combo[j]
            s1, o1 = f1['picks'][0]
            s2, o2 = f2['picks'][0]
            combo = o1 * o2
            p(f'    {f1["m"]["num_str"]}比分{s1}({o1:.1f}) x {f2["m"]["num_str"]}比分{s2}({o2:.1f}) = {combo:.1f}')
            shown += 1

p('')
p('=' * 85)

report = '\n'.join(lines)
print(report)
