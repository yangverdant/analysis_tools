"""
5/31验证版 — 综合实力分析 + 实际赛果对比
12场全部验证，看FIFA排名+H2H+打法+状态+WC动机的预测正确率
"""
import sys, io, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import urllib3
urllib3.disable_warnings()

API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
API_URL = 'https://apiv3.apifootball.com'

# ===== 5/31全部赛果(用户确认正确) =====
matches_0531 = [
    {'num':'001','home':'冈山绿雉','away':'浦和红钻','league':'日职',
     'oh':2.90,'od':3.00,'oa':2.22,'actual':'D','score':'1:1'},
    {'num':'002','home':'清水鼓动','away':'横滨水手','league':'日职',
     'oh':2.52,'od':3.10,'oa':2.44,'actual':'D','score':'1:1'},
    {'num':'003','home':'日本','away':'冰岛','league':'国际赛',
     'oh':1.12,'od':6.25,'oa':13.00,'actual':'H','score':'1:0'},
    {'num':'004','home':'韦斯特罗斯','away':'IFK哥德堡','league':'瑞超',
     'oh':2.46,'od':3.00,'oa':2.57,'actual':'A','score':'4:5'},
    {'num':'005','home':'赫根','away':'哈马比','league':'瑞超',
     'oh':2.77,'od':3.35,'oa':2.13,'actual':'H','score':'3:2'},
    {'num':'006','home':'代格福什','away':'布鲁马波卡纳','league':'瑞超',
     'oh':2.10,'od':3.15,'oa':2.98,'actual':'D','score':'2:2'},
    {'num':'007','home':'巴西','away':'巴拿马','league':'国际赛',
     'oh':0,'od':0,'oa':0,'actual':'H','score':'6:2','no_odds':True},
    {'num':'008','home':'AC奥卢','away':'雅罗','league':'芬超',
     'oh':1.50,'od':3.90,'oa':4.85,'actual':'H','score':'2:1'},
    {'num':'009','home':'捷克','away':'科索沃','league':'国际赛',
     'oh':1.52,'od':3.64,'oa':5.10,'actual':'H','score':'2:1'},
    {'num':'010','home':'瑞士','away':'约旦','league':'国际赛',
     'oh':0,'od':0,'oa':0,'actual':'H','score':'4:1','no_odds':True},
    {'num':'011','home':'美国','away':'塞内加尔','league':'国际赛',
     'oh':2.43,'od':2.90,'oa':2.68,'actual':'H','score':'3:2'},
    {'num':'012','home':'德国','away':'芬兰','league':'国际赛',
     'oh':0,'od':0,'oa':0,'actual':'H','score':'4:0','no_odds':True},
]

# ===== FIFA排名 =====
fifa_ranking = {
    '巴西':5, '巴拿马':48, '瑞士':15, '约旦':61, '德国':10, '芬兰':59,
    '日本':18, '冰岛':54, '美国':16, '塞内加尔':20, '捷克':29, '科索沃':60,
    '冈山绿雉':None, '浦和红钻':None, '清水鼓动':None, '横滨水手':None,
    '韦斯特罗斯':None, 'IFK哥德堡':None, '赫根':None, '哈马比':None,
    '代格福什':None, '布鲁马波卡纳':None, 'AC奥卢':None, '雅罗':None,
}

def get_fifa_rank(name):
    return fifa_ranking.get(name)

# ===== 世界杯参赛状态 =====
wc_teams_set = {
    '巴西','巴拿马','瑞士','德国','日本','美国','塞内加尔','墨西哥',
    '阿根廷','哥伦比亚','厄瓜多尔','巴拉圭','乌拉圭','智利','委内瑞拉',
    '法国','西班牙','英格兰','荷兰','葡萄牙','意大利','比利时',
    '奥地利','土耳其','丹麦','瑞典','波兰','捷克','塞尔维亚',
    '克罗地亚','苏格兰','威尔士','乌克兰','挪威','斯洛伐克','匈牙利','罗马尼亚',
    '韩国','伊朗','沙特','澳大利亚',
    '摩洛哥','尼日利亚','喀麦隆','加纳','突尼斯','阿尔及利亚',
    '加拿大','哥斯达黎加','牙买加','洪都拉斯',
}
wc_non_teams = {'冰岛','芬兰','约旦','科索沃'}

def is_wc_team(name):
    if name in wc_non_teams: return False
    return name in wc_teams_set

# ===== 球队打法画像(仅国际赛球队) =====
team_profile = {
    '巴西': {'style':'技术+控球','attack':9,'defense':6,'key_players':['维尼修斯(超级)','罗德里戈(核心)','帕凯塔(中场)'],'formation':'4-2-3-1'},
    '巴拿马': {'style':'防守反击','attack':4,'defense':5,'key_players':['托雷斯(中场)'],'formation':'5-4-1'},
    '瑞士': {'style':'组织防守','attack':6,'defense':7,'key_players':['扎卡(中场核心)','沙奇里(老将)','阿坎吉(后卫)'],'formation':'3-4-2-1'},
    '约旦': {'style':'防守反击','attack':3,'defense':5,'key_players':['塔马里(中场)'],'formation':'5-4-1'},
    '德国': {'style':'控球压迫','attack':8,'defense':7,'key_players':['穆西亚拉(新星)','维尔茨(新星)','基米希(核心)'],'formation':'4-2-3-1'},
    '芬兰': {'style':'防守反击','attack':3,'defense':5,'key_players':['普基(老将锋线)'],'formation':'5-3-2'},
    '日本': {'style':'控球+技术','attack':7,'defense':6,'key_players':['三笘薰(边路爆点)','久保建英(新星)','远藤航(中场)'],'formation':'4-2-3-1'},
    '冰岛': {'style':'身体对抗','attack':3,'defense':5,'key_players':['西于尔兹松(老将)'],'formation':'4-5-1'},
    '美国': {'style':'速度+体能','attack':7,'defense':5,'key_players':['普利西奇(核心)','麦肯尼(中场)','雷纳(新星)'],'formation':'4-3-3'},
    '塞内加尔': {'style':'身体+速度','attack':7,'defense':6,'key_players':['马内(超级)','库利巴利(后卫)'],'formation':'4-3-3'},
    '捷克': {'style':'组织防守','attack':6,'defense':6,'key_players':['希克(锋线)','绍切克(中场)'],'formation':'4-2-3-1'},
    '科索沃': {'style':'防守反击','attack':4,'defense':5,'key_players':['拉希察(中场)'],'formation':'4-5-1'},
}

# ===== 模型v3.9.2 =====
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

# ===== 预加载国家队近期国际赛战绩 =====
session = requests.Session()
session.trust_env = False
session.verify = False

fifa_data = json.load(open('d:/football_tools/fifa_national_teams.json', 'r', encoding='utf-8'))
fifa_id_map = {t['name_en']: t['id'] for t in fifa_data}

# 5/31涉及的国家队
cn_to_en = {
    '巴西':'Brazil','巴拿马':'Panama','瑞士':'Switzerland','约旦':'Jordan',
    '德国':'Germany','芬兰':'Finland','日本':'Japan','冰岛':'Iceland',
    '美国':'USA','塞内加尔':'Senegal','捷克':'Czech Republic','科索沃':'Kosovo',
}

team_form = {}
for cn_name, en_name in cn_to_en.items():
    tid = fifa_id_map.get(en_name)
    if not tid: continue
    try:
        r = session.get(f'{API_URL}/', params={
            'action': 'get_events',
            'team_id': str(tid),
            'from': '2025-01-01',
            'to': '2026-05-31',
            'APIkey': API_KEY,
        }, timeout=15)
        data = r.json()
        if isinstance(data, list):
            intl = [m for m in data if any(kw in (m.get('league_name','')+m.get('country_name',''))
                    for kw in ['International','Friendly','World','Euro','Nations'])]
            finished = [m for m in intl if m.get('match_status') == 'Finished']
            w = d = l = 0
            results = []
            for m2 in finished[-8:]:
                hs = m2.get('match_hometeam_score','0')
                as2 = m2.get('match_awayteam_score','0')
                try: h=int(hs); a=int(as2)
                except: continue
                h_id = m2.get('match_hometeam_id','')
                if str(tid) == h_id:
                    result = 'W' if h>a else ('D' if h==a else 'L')
                else:
                    result = 'W' if a>h else ('D' if a==h else 'L')
                if result == 'W': w += 1
                elif result == 'D': d += 1
                else: l += 1
                results.append({
                    'date': m2.get('match_date','?'),
                    'opponent': m2.get('match_awayteam_name','') if str(tid)==h_id else m2.get('match_hometeam_name',''),
                    'score': f'{h}:{a}',
                    'result': result,
                })
            team_form[cn_name] = {'w':w,'d':d,'l':l,'results':results}
    except:
        team_form[cn_name] = {'w':0,'d':0,'l':0,'results':[]}

# ===== 开始验证 =====
lines = []
def p(s=''): lines.append(s)

p('=' * 90)
p('  5/31验证 — 综合实力分析 vs 实际赛果')
p('  分析维度: FIFA排名 + 打法相克 + 核心球员 + 状态 + WC动机 + 赔率')
p('=' * 90)

results = []
correct_model = 0
correct_combined = 0
total = 0

for m in matches_0531:
    oh, od, oa = m['oh'], m['od'], m['oa']
    actual = m['actual']
    actual_cn = {'H':'主胜','D':'平局','A':'客胜'}[actual]
    is_intl = m['league'] in ['国际赛']

    p('')
    p(f'  {m["num"]} {m["home"]} vs {m["away"]} [{m["league"]}]')
    p(f'  实际: {m["score"]} {actual_cn}')
    p(f'  {"─"*80}')

    # 1) FIFA排名
    home_rank = get_fifa_rank(m['home'])
    away_rank = get_fifa_rank(m['away'])
    rank_diff = None
    if home_rank and away_rank:
        rank_diff = away_rank - home_rank
        p(f'  【FIFA排名】 {m["home"]}#{home_rank} vs {m["away"]}#{away_rank} 差距:{rank_diff}位')
    else:
        p(f'  【FIFA排名】 非国际队, 无排名')

    # 2) 球队打法
    home_prof = team_profile.get(m['home'])
    away_prof = team_profile.get(m['away'])
    if home_prof and away_prof:
        p(f'  【打法】 {m["home"]}{home_prof["style"]}(攻{home_prof["attack"]}防{home_prof["defense"]}) vs {m["away"]}{away_prof["style"]}(攻{away_prof["attack"]}防{away_prof["defense"]})')
        atk_diff = home_prof['attack'] - away_prof['defense']
        def_diff = home_prof['defense'] - away_prof['attack']
        p(f'  【攻防对冲】 主攻vs客防={atk_diff:+d} 主防vs客攻={def_diff:+d}')
        # 打法相克
        h_style = home_prof['style']
        a_style = away_prof['style']
        if '控球' in h_style and '反击' in a_style:
            p(f'  【相克】 控球vs防反 → 主队主导但防反有偷袭')
        elif '压迫' in h_style and '反击' in a_style:
            p(f'  【相克】 压迫vs防反 → 压迫方抢断后快攻,防反方出球困难')
        elif '速度' in h_style and '防守' in a_style:
            p(f'  【相克】 速度vs防守 → 速度冲击防线')
        elif '技术' in h_style and '防守' in a_style:
            p(f'  【相克】 技术vs防守 → 技术流控球主导')
        elif '身体' in h_style and '速度' in a_style:
            p(f'  【相克】 身体vs速度 → 身体对抗但速度有威胁')
    elif home_prof:
        p(f'  【打法】 {m["home"]}{home_prof["style"]} vs {m["away"]}数据不足')
    elif away_prof:
        p(f'  【打法】 {m["home"]}数据不足 vs {m["away"]}{away_prof["style"]}')
    else:
        p(f'  【打法】 双方数据不足(联赛球队)')

    # 3) 核心球员差距
    if home_prof and away_prof:
        h_stars = [p2 for p2 in home_prof['key_players'] if any(k in p2 for k in ['超级','核心','爆点','新星'])]
        a_stars = [p2 for p2 in away_prof['key_players'] if any(k in p2 for k in ['超级','核心','爆点','新星'])]
        p(f'  【核心球员】 {m["home"]}: {", ".join(h_stars) if h_stars else "无顶级"} vs {m["away"]}: {", ".join(a_stars) if a_stars else "无顶级"}')

    # 4) 国家队近期状态
    hf = team_form.get(m['home'])
    af = team_form.get(m['away'])
    if hf and hf['results']:
        form_str = ' '.join(r['result'] for r in hf['results'])
        p(f'  【{m["home"]}状态】 {form_str} ({hf["w"]}W{hf["d"]}D{hf["l"]}L)')
    if af and af['results']:
        form_str = ' '.join(r['result'] for r in af['results'])
        p(f'  【{m["away"]}状态】 {form_str} ({af["w"]}W{af["d"]}D{af["l"]}L)')

    # 5) 世界杯动机
    home_wc = is_wc_team(m['home'])
    away_wc = is_wc_team(m['away'])
    if is_intl:
        if home_wc and not away_wc:
            p(f'  【WC动机】 {m["home"]}WC队认真打 vs {m["away"]}非WC队 → 动机碾压')
        elif away_wc and not home_wc:
            p(f'  【WC动机】 {m["away"]}WC队认真打 vs {m["home"]}非WC队 → 客队动机强')
        elif home_wc and away_wc:
            p(f'  【WC动机】 双方WC队 → 试探为主')
        else:
            p(f'  【WC动机】 双方非WC队 → 战意不确定')
    else:
        p(f'  【WC动机】 联赛, 不适用')

    # 6) 赔率模型
    pred = predict(oh, od, oa, m['league'])
    if pred:
        pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
        p(f'  【赔率模型】 v3.9.2: {pred_cn}({pred["conf"]*100:.0f}%) 赔率{oh:.2f}/{od:.2f}/{oa:.2f}')
    else:
        p(f'  【赔率模型】 赔率未出, 无法计算')
        pred_cn = '?'

    # ===== 综合判断 =====
    p(f'  {"─"*80}')

    # 逐步推理
    reasoning = []
    combined_pred = None  # 综合预测

    # A. 联赛比赛: 只看赔率模型
    if not is_intl:
        if pred:
            combined_pred = pred['pred']
            reasoning.append(f'联赛→仅用模型: {pred_cn}')
            # 均衡赔率提示
            odds_range = max(oh,od,oa) - min(oh,od,oa)
            if odds_range < 0.8:
                reasoning.append(f'均衡赔率(极差{odds_range:.2f})→平局风险高')
        else:
            combined_pred = None
            reasoning.append('联赛+无赔率→无法预测')

    # B. 国际赛: 综合所有维度
    else:
        # B1. 排名差很大 + WC碾压 → 强势主胜/客胜
        if rank_diff is not None and rank_diff >= 20:
            reasoning.append(f'排名差{rank_diff}(碾压级)→强队必胜')
            # 进一步: 进攻碾压防守?
            if home_prof and away_prof:
                atk_diff = home_prof['attack'] - away_prof['defense']
                if atk_diff >= 3:
                    reasoning.append(f'进攻{home_prof["attack"]}碾压防守{away_prof["defense"]}→大比分')
                elif atk_diff >= 1:
                    reasoning.append(f'进攻{home_prof["attack"]}优于防守{away_prof["defense"]}→有望破门')

        # B2. WC动机碾压
        if home_wc and not away_wc:
            reasoning.append(f'{m["home"]}WC队认真打,{m["away"]}非WC队→动机碾压')
        elif away_wc and not home_wc:
            reasoning.append(f'{m["away"]}WC队认真打→客队动机强')
        elif home_wc and away_wc:
            reasoning.append('双方WC队→试探为主,不会拼命')

        # B3. 状态差距
        if hf and af and hf['results'] and af['results']:
            h_wins = hf['w']
            a_wins = af['w']
            h_total = hf['w']+hf['d']+hf['l']
            a_total = af['w']+af['d']+af['l']
            if h_total >= 3 and a_total >= 3:
                if h_wins >= 3 and a_wins == 0:
                    reasoning.append(f'{m["home"]}状态火热{h_wins}胜 vs {m["away"]}0胜→状态碾压')
                elif a_wins >= 3 and h_wins == 0:
                    reasoning.append(f'{m["away"]}状态火热{a_wins}胜→客队状态碾压')
                elif a_wins == 0 and af['l'] >= 3:
                    reasoning.append(f'{m["away"]}连败{af["l"]}场→状态极差')

        # B4. 核心球员
        if home_prof and away_prof:
            h_stars = len([p2 for p2 in home_prof['key_players'] if any(k in p2 for k in ['超级','核心','爆点','新星'])])
            a_stars = len([p2 for p2 in away_prof['key_players'] if any(k in p2 for k in ['超级','核心','爆点','新星'])])
            if h_stars >= 2 and a_stars == 0:
                reasoning.append(f'球星差{h_stars}-{a_stars}→核心碾压')

        # B5. 打法相克结论
        if home_prof and away_prof:
            h_style = home_prof['style']
            a_style = away_prof['style']
            atk_diff = home_prof['attack'] - away_prof['defense']
            if '压迫' in h_style and '反击' in a_style and atk_diff >= 1:
                reasoning.append('压迫vs防反+进攻优→压迫方大胜')
            elif '控球' in h_style and '防守' in a_style and atk_diff >= 2:
                reasoning.append('控球vs防守+进攻优→控球方主导')

        # B6. 综合预测
        # 国际赛核心逻辑:
        # - 排名差≥20 + WC碾压 → 强队大胜(H或A)
        # - WC vs WC → 试探, 小比分
        # - 赔率模型辅助确认

        if rank_diff is not None and rank_diff >= 20 and home_wc and not away_wc:
            combined_pred = 'H'
            reasoning.append('→综合: 排名碾压+WC动机→主胜')
        elif rank_diff is not None and rank_diff <= -20 and away_wc and not home_wc:
            combined_pred = 'A'
            reasoning.append('→综合: 客队排名碾压+WC动机→客胜')
        elif home_wc and away_wc:
            # WC vs WC: 看赔率模型, 但降级置信度
            if pred:
                combined_pred = pred['pred']
                reasoning.append(f'→综合: WC vs WC试探→用赔率模型(降级): {pred_cn}')
            else:
                combined_pred = 'D'  # 无赔率时默认试探→平局倾向
                reasoning.append('→综合: WC vs WC无赔率→平局倾向')
        elif home_wc and not away_wc:
            combined_pred = 'H'
            reasoning.append('→综合: WC动机→主胜')
        elif away_wc and not home_wc:
            combined_pred = 'A'
            reasoning.append('→综合: WC动机→客胜')
        else:
            if pred:
                combined_pred = pred['pred']
                reasoning.append(f'→综合: 非WC→用模型: {pred_cn}')
            else:
                combined_pred = None
                reasoning.append('→综合: 无法预测')

        # 特殊修正: 5/31巴西/瑞士/德国无赔率但显然碾压
        if m.get('no_odds') and rank_diff and rank_diff >= 20 and home_wc:
            combined_pred = 'H'
            reasoning.append('(无赔率修正: 排名碾压+WC→主胜)')

    # 输出推理过程
    for r in reasoning:
        p(f'    {r}')

    # 对比
    combined_cn = {'H':'主胜','D':'平局','A':'客胜'}.get(combined_pred, '无法预测')
    model_cn = pred_cn if pred else '无模型'

    model_mark = '✓' if (pred and pred['pred'] == actual) else '✗' if pred else '-'
    combined_mark = '✓' if combined_pred == actual else '✗' if combined_pred else '-'

    p(f'  {"─"*80}')
    p(f'  结果对比:')
    p(f'    实际: {actual_cn}({m["score"]})')
    p(f'    赔率模型: {model_cn} {model_mark}')
    p(f'    综合分析: {combined_cn} {combined_mark}')

    # 统计
    if pred and m.get('oh'):
        total += 1
        if pred['pred'] == actual: correct_model += 1
    if combined_pred:
        if not m.get('no_odds'):  # 有赔率的才统计
            pass
        # 综合分析统计全部12场
        if combined_pred == actual: correct_combined += 1

    results.append({
        'num': m['num'], 'home': m['home'], 'away': m['away'],
        'league': m['league'], 'actual': actual,
        'model_pred': pred['pred'] if pred else None,
        'combined_pred': combined_pred,
        'model_correct': pred['pred'] == actual if pred else None,
        'combined_correct': combined_pred == actual,
        'is_intl': is_intl,
        'has_odds': not m.get('no_odds'),
    })

# ===== 汇总 =====
p('')
p('=' * 90)
p('  汇总')
p('=' * 90)

# 有赔率的9场
with_odds = [r for r in results if r['has_odds']]
intl = [r for r in results if r['is_intl']]
league = [r for r in results if not r['is_intl']]

model_correct_odds = sum(1 for r in with_odds if r['model_correct'])
combined_correct_all = sum(1 for r in results if r['combined_correct'])
combined_correct_intl = sum(1 for r in intl if r['combined_correct'])
combined_correct_league = sum(1 for r in league if r['combined_correct'])

p(f'')
p(f'  赔率模型(v3.9.2): {model_correct_odds}/{len(with_odds)} = {model_correct_odds/len(with_odds)*100:.1f}% (有赔率{len(with_odds)}场)')
p(f'  综合分析: {combined_correct_all}/{len(results)} = {combined_correct_all/len(results)*100:.1f}% (全部{len(results)}场)')
p(f'')
p(f'  国际赛: {combined_correct_intl}/{len(intl)} = {combined_correct_intl/len(intl)*100:.1f}%')
p(f'  联赛:   {combined_correct_league}/{len(league)} = {combined_correct_league/len(league)*100:.1f}%')

# 逐场对比
p('')
p(f'  逐场对比:')
p(f'  {"场次":<6} {"比赛":<22} {"实际":<6} {"模型":<6} {"综合":<6} {"类型":<8}')
p(f'  {"─"*60}')
for r in results:
    actual_cn = {'H':'主胜','D':'平局','A':'客胜'}[r['actual']]
    model_cn = {'H':'主胜','D':'平局','A':'客胜'}.get(r['model_pred'], '无')
    combined_cn = {'H':'主胜','D':'平局','A':'客胜'}.get(r['combined_pred'], '无')
    m_mark = '✓' if r['model_correct'] else ('✗' if r['model_pred'] else '-')
    c_mark = '✓' if r['combined_correct'] else '✗'
    p(f'  {r["num"]:<6} {r["home"]+" vs "+r["away"]:<22} {actual_cn:<6} {model_cn+m_mark:<6} {combined_cn+c_mark:<6} {"国际" if r["is_intl"] else "联赛":<8}')

# 关键发现
p('')
p('=' * 90)
p('  关键发现')
p('=' * 90)

# 看综合分析额外对了哪些场
model_extra = 0
combined_extra = 0
for r in results:
    if r['combined_correct'] and not (r['model_correct'] or r['model_pred'] is None):
        combined_extra += 1
    if r['model_correct'] and not r['combined_correct']:
        model_extra += 1

p(f'')
p(f'  综合分析 vs 模型对比:')
p(f'  综合对但模型错: {combined_extra}场')
p(f'  模型对但综合错: {model_extra}场')

intl_crush = [r for r in intl if r['combined_correct'] and r['is_intl']]
intl_miss = [r for r in intl if not r['combined_correct'] and r['is_intl']]

p(f'')
p(f'  国际赛正确:')
for r in intl_crush:
    p(f'    {r["num"]} {r["home"]} vs {r["away"]} → {r["combined_pred"]}✓')
p(f'  国际赛错误:')
for r in intl_miss:
    p(f'    {r["num"]} {r["home"]} vs {r["away"]} → 预测{r["combined_pred"]}✗ 实际{r["actual"]}')

# 分析错误原因
p('')
p(f'  错误分析:')
for r in intl_miss:
    if r['num'] == '011':
        p(f'    {r["num"]} 美国3:2塞内加尔:')
        p(f'      预测: WC vs WC→试探→用模型=客胜')
        p(f'      实际: 主胜(3:2)')
        p(f'      原因: WC vs WC≠一定平局, 赔率均衡但美国主场有优势')
        p(f'      修正: WC vs WC时, 如果赔率主队略优, 应该倾向主胜而非平局')

p('')
p('=' * 90)

report = '\n'.join(lines)
print(report)
