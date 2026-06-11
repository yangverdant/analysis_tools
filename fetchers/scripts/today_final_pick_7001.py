"""
5/31 体彩7003-7012 直接推荐 - 结论导向
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
        if not (7003 <= int(num) <= 7012): continue

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

p('=' * 70)
p('  5/31(周日) 体彩推荐  直接给结论')
p('  7001冈山1:1浦和  7002清水1:1横滨  已结束')
p('=' * 70)

# 逐场
for m in matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    pred = predict(oh, od, oa, m['league'])
    if not pred:
        p(f'')
        p(f'{m["num_str"]} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]}')
        p(f'  赔率未出 -> 跳过')
        continue

    rq_pred = predict(m['rqh'], m['rqd'], m['rqa'], m['league'])

    # 比分
    home_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'H']
    draw_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'D']
    away_scores = [(s, o) for s, o in m['scores'] if score_dir(s) == 'A']

    picks = []
    pred_dir = pred['pred']
    if pred_dir == 'H' and home_scores: picks.append(home_scores[0])
    elif pred_dir == 'D' and draw_scores: picks.append(draw_scores[0])
    elif pred_dir == 'A' and away_scores: picks.append(away_scores[0])

    probs_list = [('H', pred['hp'], home_scores), ('D', pred['dp'], draw_scores), ('A', pred['ap'], away_scores)]
    probs_sorted = sorted(probs_list, key=lambda x: -x[1])
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

    pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred_dir]
    rq_cn = ''
    if rq_pred:
        rq_cn = {'H':'让胜','D':'让平','A':'让负'}[rq_pred['pred']]

    # 综合评分
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

    if rq_pred and pred_dir == rq_pred['pred']:
        score_val += 1; reasons.append('SPF+让球同向')
    elif rq_pred:
        score_val -= 1; reasons.append('SPF与让球矛盾')

    if m['league'] == '国际赛':
        score_val -= 2; reasons.append('友谊赛不确定性高')
    if m['league'] == '芬超':
        score_val += 1; reasons.append('联赛数据清晰')

    # 特殊判断
    if m['home'] == 'AC奥卢' and m['away'] == '雅罗':
        score_val += 3; reasons.append('主场100%胜率vs客场0%胜率')
    if m['home'] == '日本' and m['away'] == '冰岛':
        score_val += 2; reasons.append('实力碾压')
    if m['home'] == '代格福什' and m['away'] == '布鲁马波卡纳':
        score_val -= 3; reasons.append('排名/近况/赔率三方矛盾')
    if m['home'] == '美国' and m['away'] == '塞内加尔':
        score_val -= 1; reasons.append('势均力敌难判断')

    if score_val >= 4:
        tier = 'A'
    elif score_val >= 1:
        tier = 'B'
    else:
        tier = 'C'

    p(f'')
    p(f'--- {m["num_str"]} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]} ---')
    p(f'')
    p(f'  SPF: {pred_cn} (置信{pred["conf"]*100:.0f}%)  赔率 {oh:.2f}/{od:.2f}/{oa:.2f}')
    if rq_cn:
        p(f'  让球: 让{m["hc"]} {rq_cn} ({rq_pred["conf"]*100:.0f}%)  赔率 {m["rqh"]:.2f}/{m["rqd"]:.2f}/{m["rqa"]:.2f}')
    p(f'  比分: {" / ".join(f"{s}({o:.1f})" for s, o in picks[:3])}')
    p(f'  大小球: {" / ".join(f"{g}({v:.1f})" for g, v in top3_goals)}')
    p(f'  档位: {tier}档 (评分{score_val}) {" ".join(reasons)}')

# ===== 最终推荐 =====
p(f'')
p(f'{"="*70}')
p(f'  最终推荐单')
p(f'{"="*70}')

# 手动综合所有因素给最终结论
p(f'')
p(f'  A档(重点投):')
p(f'')
p(f'  1. 周日008 AC奥卢 vs 雅罗 [芬超] 21:00')
p(f'     -> 主胜(1.50) / 让-1让负(2.20)')
p(f'     -> 比分: 2:0(6.8) / 2:1(6.5) / 1:0(6.8)')
p(f'     理由: 主场3战全胜 vs 客场5战0胜，积分榜差7位')
p(f'            近5场主3胜1负 vs 客1胜1平3负')
p(f'            API预测主86%，数据面最清晰的一场')
p(f'     风险: 芬超联赛小，样本少；奥卢湿度89%')
p(f'')
p(f'  2. 周日003 日本 vs 冰岛 [国际赛] 18:25')
p(f'     -> 主胜(1.13) / 让-2让胜(2.20)')
p(f'     -> 比分: 2:0(6.0) / 3:0(6.5) / 3:1(10.0)')
p(f'     理由: FIFA#15 vs #72，日本主场埼玉')
p(f'            旅欧军团完整，实力差3个档次')
p(f'            SPF主胜1.13是今天最低赔率')
p(f'     风险: 友谊赛轮换+战意不确定，1.13回报极差')
p(f'     建议: 不要买SPF主胜(1.13无价值)，买让-2让胜(2.20)')
p(f'')
p(f'  3. 周日009 捷克 vs 科索沃 [国际赛] 22:00')
p(f'     -> 主胜(1.52) / 让-1让负(2.15)')
p(f'     -> 比分: 1:0(6.0) / 2:1(6.5) / 2:0(7.5)')
p(f'     理由: FIFA#38 vs #101，差距63位')
p(f'            捷克主场稳定，科索沃客场能力弱')
p(f'     风险: 友谊赛，捷克可能轮换')
p(f'     建议: 主胜1.52可接受，让-1偏保守选让负')
p(f'')

p(f'  B档(小注):')
p(f'')
p(f'  4. 周日005 赫根 vs 哈马比 [瑞超] 20:00')
p(f'     -> 客胜(2.13) / 让+1让胜(1.54)')
p(f'     -> 比分: 1:2(7.3) / 2:1(8.2) / 0:1(11.0)')
p(f'     理由: 哈马比联赛第3，10场22球攻击力强')
p(f'            赫根9场0负但5场平局，攻坚能力不足')
p(f'            让+1(1.54)几乎稳赢，赫根0负+平局多')
p(f'     风险: 赫根主场不败，哈马比客场1胜1平2负')
p(f'     建议: 不买胜负，买让+1让胜(1.54)最安全')
p(f'')
p(f'  5. 周日004 韦斯特罗斯 vs IFK哥德堡 [瑞超] 20:00')
p(f'     -> 平局(3.00) / 让-1让负(1.42)')
p(f'     -> 比分: 1:1(5.5) / 0:0(8.0) / 1:0(8.0)')
p(f'     理由: 主队主场0胜3平1负(平局王！)')
p(f'            客队客场1胜2平2负(也是平局多)')
p(f'            平局赔率3.00是SPF里最低的')
p(f'     风险: 两队都差，谁赢都可能的烂局')
p(f'     建议: 平局3.00有价值，或让-1让负(1.42)保底')
p(f'')

p(f'  C档(避让):')
p(f'')
p(f'  6. 周日006 代格福什 vs 布鲁马波卡纳 [瑞超] 20:00')
p(f'     -> 不推荐任何方向')
p(f'     理由: 赔率开主让-1但排名13vs7客队高6位')
p(f'            主队近5场0胜2平2负，客队3胜0平1负')
p(f'            客队客场3胜1平2负(50%)非常强')
p(f'            赔率和基本面严重矛盾，庄家可能在诱导主胜')
p(f'     如果非要买: 客胜(2.98)是价值方向')
p(f'')
p(f'  7. 周日011 美国 vs 塞内加尔 [国际赛] 03:30')
p(f'     -> 不推荐')
p(f'     理由: FIFA#13 vs #17差距4位，势均力敌')
p(f'            友谊赛双方试验阵容，无法判断')
p(f'            赔率2.43/2.90/2.68三方均衡，无方向')
p(f'')
p(f'  8. 周日007/010/012 赔率未出 -> 跳过')
p(f'')

p(f'  --- 串关建议 ---')
p(f'')
p(f'  2串1:')
p(f'    周日008主胜(1.50) x 周日009主胜(1.52) = 2.28')
p(f'    周日003让-2让胜(2.20) x 周日008主胜(1.50) = 3.30')
p(f'')
p(f'  3串1:')
p(f'    周日008主胜(1.50) x 周日009主胜(1.52) x 周日005让+1让胜(1.54) = 3.51')
p(f'')
p(f'  比分2串1(高风险高回报):')
p(f'    周日008比分2:0(6.8) x 周日003比分2:0(6.0) = 40.8')
p(f'    周日008比分2:1(6.5) x 周日009比分1:0(6.0) = 39.0')
p(f'')

p(f'  --- 今日验证 ---')
p(f'  7001 冈山1:1浦和: 模型预测客胜 -> 实际平局')
p(f'  7002 清水1:1横滨: 模型预测客胜 -> 实际平局')
p(f'  教训: 赔率3-way均衡(差值<0.5)的比赛，平局概率被低估')
p(f'        这种比赛应该优先考虑平局，而不是强行选胜负')
p(f'')
p(f'=' * 70)

report = '\n'.join(lines)
print(report)
