"""
5/31(周日) 体彩7001-7012 全因素深度分析
数据源: sporttery赔率 + apifootball积分榜/近期战绩/预测 + wttr.in天气 + FIFA排名
"""
import sys, io, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import urllib3
urllib3.disable_warnings()

lines = []
def p(s=''): lines.append(s)

# ===== 1. 体彩赔率 =====
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

sporttery_matches = []
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

        sporttery_matches.append({
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

# ===== 2. apifootball数据 =====
API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
BASE = 'https://apiv3.apifootball.com'
af = requests.Session()
af.trust_env = False
af.verify = False

# 积分榜
standings_data = {}
for lid, name in [(209, 'J1'), (307, 'Allsvenskan'), (352, 'Veikkausliiga')]:
    r2 = af.get(f'{BASE}/?action=get_standings&league_id={lid}&APIkey={API_KEY}', timeout=15)
    d = r2.json()
    if isinstance(d, list) and len(d) > 0:
        s = d[0] if isinstance(d[0], list) else d
        if isinstance(s, list):
            for team in s:
                tn = team.get('team_name', '')
                standings_data[tn] = team

# 近期战绩
recent_data = {}
for lid, name in [(209, 'J1'), (307, 'Allsvenskan'), (352, 'Veikkausliiga')]:
    r2 = af.get(f'{BASE}/?action=get_events&league_id={lid}&from=2026-05-01&to=2026-05-30&APIkey={API_KEY}', timeout=15)
    d = r2.json()
    if isinstance(d, list):
        for match in d:
            home = match.get('match_hometeam_name', '')
            away = match.get('match_awayteam_name', '')
            hs = match.get('match_hometeam_score', '?')
            as_ = match.get('match_awayteam_score', '?')
            date = match.get('match_date', '')
            for team_name in [home, away]:
                if team_name not in recent_data:
                    recent_data[team_name] = []
                recent_data[team_name].append({
                    'date': date, 'home': home, 'away': away,
                    'hs': hs, 'as': as_,
                    'is_home': team_name == home,
                })

# API预测
predictions = {}
for lid in [209, 307, 352]:
    r2 = af.get(f'{BASE}/?action=get_events&league_id={lid}&from=2026-05-31&to=2026-05-31&APIkey={API_KEY}', timeout=15)
    d = r2.json()
    if isinstance(d, list):
        for m in d:
            mid = m.get('match_id', '')
            if mid:
                r3 = af.get(f'{BASE}/?action=get_predictions&match_id={mid}&APIkey={API_KEY}', timeout=15)
                pd = r3.json()
                if isinstance(pd, list) and len(pd) > 0:
                    predictions[m.get('match_hometeam_name', '')] = pd[0]

# 天气
ws = requests.Session()
ws.trust_env = False
ws.headers.update({'User-Agent': 'curl/7.64.1', 'Accept': 'application/json'})

weather_data = {}
for city in ['Okayama', 'Shimizu', 'Vasteras', 'Goteborg', 'Degerfors', 'Oulu']:
    try:
        r4 = ws.get(f'https://wttr.in/{city}?format=j1', timeout=10, proxies={'http': None, 'https': None})
        if r4.status_code == 200:
            wd = r4.json()
            cur = wd.get('current_condition', [{}])[0]
            weather_data[city] = {
                'temp': cur.get('temp_C', '?'),
                'feels': cur.get('FeelsLikeC', '?'),
                'humidity': cur.get('humidity', '?'),
                'wind': cur.get('windspeedKmph', '?'),
                'desc': cur.get('weatherDesc', [{}])[0].get('value', '?'),
                'precip': cur.get('precipMM', '?'),
            }
    except:
        pass

# ===== 3. 模型 =====
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

def get_recent_form(team_name, n=5):
    """获取最近n场战绩"""
    games = recent_data.get(team_name, [])
    finished = [g for g in games if g['hs'] != '?' and g['as'] != '?']
    finished.sort(key=lambda x: x['date'], reverse=True)
    result = []
    for g in finished[:n]:
        try:
            hs, as_ = int(g['hs']), int(g['as'])
        except:
            continue
        if g['is_home']:
            if hs > as_: result.append('W')
            elif hs == as_: result.append('D')
            else: result.append('L')
        else:
            if hs < as_: result.append('W')
            elif hs == as_: result.append('D')
            else: result.append('L')
    return result

def get_team_stats(team_name):
    """获取积分榜数据"""
    s = standings_data.get(team_name, {})
    if not s: return None
    return {
        'pos': s.get('overall_league_position', '?'),
        'played': s.get('overall_league_payed', '?'),
        'w': s.get('overall_league_W', '?'),
        'd': s.get('overall_league_D', '?'),
        'l': s.get('overall_league_L', '?'),
        'gf': s.get('overall_league_GF', '?'),
        'ga': s.get('overall_league_GA', '?'),
        'pts': s.get('overall_league_PTS', '?'),
        'hw': s.get('home_league_W', '?'),
        'hd': s.get('home_league_D', '?'),
        'hl': s.get('home_league_L', '?'),
        'aw': s.get('away_league_W', '?'),
        'ad': s.get('away_league_D', '?'),
        'al': s.get('away_league_L', '?'),
    }

# 城市映射
city_map = {
    '冈山绿雉': 'Okayama', '浦和红钻': 'Okayama',
    '清水鼓动': 'Shimizu', '横滨水手': 'Shimizu',
    '韦斯特罗斯': 'Vasteras', 'IFK哥德堡': 'Goteborg', '哥德堡': 'Goteborg',
    '赫根': 'Goteborg', '哈马比': 'Goteborg',
    '代格福什': 'Degerfors', '布鲁马波卡纳': 'Degerfors',
    'AC奥卢': 'Oulu', '雅罗': 'Oulu',
}

# apifootball队名映射
af_team_map = {
    '冈山绿雉': 'Okayama', '浦和红钻': 'Urawa Reds',
    '清水鼓动': 'Shimizu S-Pulse', '横滨水手': 'Yokohama F. Marinos',
    '韦斯特罗斯': 'Vasteras SK', 'IFK哥德堡': 'Goteborg',
    '赫根': 'Hacken', '哈马比': 'Hammarby',
    '代格福什': 'Degerfors', '布鲁马波卡纳': 'Brommapojkarna',
    'AC奥卢': 'AC Oulu', '雅罗': 'Jaro',
}

# FIFA排名
fifa = {
    '日本': 15, '冰岛': 72, '瑞士': 12, '约旦': 71,
    '捷克': 38, '科索沃': 101, '德国': 16, '芬兰': 58,
    '美国': 13, '塞内加尔': 17, '巴西': 5, '巴拿马': 51,
}

# ===== 4. 输出 =====
p('=' * 90)
p('  5/31(周日) 体彩7001-7012 全因素深度分析')
p('  数据: 体彩赔率 + apifootball积分榜/预测 + wttr.in天气 + FIFA排名')
p('=' * 90)

for m in sporttery_matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    league = m['league']
    home_cn = m['home']
    away_cn = m['away']

    p('')
    p(f'  {"━"*85}')
    p(f'  {m["num_str"]} [{league}] {m["time"]}  {home_cn} vs {away_cn}')
    p(f'  {"━"*85}')

    # === 赔率分析 ===
    pred = predict(oh, od, oa, league)
    if not pred:
        p(f'  ⚠ 赔率未出，无法分析')
        continue

    pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
    p(f'')
    p(f'  【赔率分析】')
    p(f'  SPF: {oh:.2f}/{od:.2f}/{oa:.2f}  margin={pred["margin"]*100:.1f}%')
    p(f'  隐含概率: 主{pred["hp"]*100:.1f}% 平{pred["dp"]*100:.1f}% 客{pred["ap"]*100:.1f}%')
    p(f'  模型预测: {pred_cn} (置信{pred["conf"]*100:.1f}%)')
    evs = [('主胜',pred['ev_h'],oh), ('平局',pred['ev_d'],od), ('客胜',pred['ev_a'],oa)]
    evs.sort(key=lambda x: -x[1])
    p(f'  EV: {evs[0][0]}{evs[0][1]:+.3f}(赔{evs[0][2]:.2f})  {evs[1][0]}{evs[1][1]:+.3f}  {evs[2][0]}{evs[2][1]:+.3f}')

    # 让球
    rq_pred = predict(m['rqh'], m['rqd'], m['rqa'], league)
    if rq_pred:
        rq_cn = {'H':'让胜','D':'让平','A':'让负'}[rq_pred['pred']]
        p(f'  让{m["hc"]}: {m["rqh"]:.2f}/{m["rqd"]:.2f}/{m["rqa"]:.2f} → {rq_cn} (置信{rq_pred["conf"]*100:.1f}%)')

    # === 积分榜/近期战绩 ===
    is_intl = league in ['国际赛']
    if not is_intl:
        home_af = af_team_map.get(home_cn, '')
        away_af = af_team_map.get(away_cn, '')

        home_stats = get_team_stats(home_af)
        away_stats = get_team_stats(away_af)

        p(f'')
        p(f'  【积分榜】')
        if home_stats:
            p(f'  {home_cn}({home_af}): 第{home_stats["pos"]}位 {home_stats["played"]}场 {home_stats["w"]}胜{home_stats["d"]}平{home_stats["l"]}负 进{home_stats["gf"]}失{home_stats["ga"]} 积{home_stats["pts"]}分')
            p(f'    主场: {home_stats["hw"]}胜{home_stats["hd"]}平{home_stats["hl"]}负')
        if away_stats:
            p(f'  {away_cn}({away_af}): 第{away_stats["pos"]}位 {away_stats["played"]}场 {away_stats["w"]}胜{away_stats["d"]}平{away_stats["l"]}负 进{away_stats["gf"]}失{away_stats["ga"]} 积{away_stats["pts"]}分')
            p(f'    客场: {away_stats["aw"]}胜{away_stats["ad"]}平{away_stats["al"]}负')

        # 排名差
        if home_stats and away_stats:
            try:
                diff = int(away_stats['pos']) - int(home_stats['pos'])
                if diff > 0:
                    p(f'  排名差: 主队高{diff}位 (主队排名优势)')
                elif diff < 0:
                    p(f'  排名差: 客队高{-diff}位 (客队排名优势)')
                else:
                    p(f'  排名差: 同排名')
            except:
                pass

        # 近期战绩
        home_form = get_recent_form(home_af)
        away_form = get_recent_form(away_af)
        p(f'')
        p(f'  【近期战绩】')
        p(f'  {home_cn} 近5场: {" ".join(home_form)} ({home_form.count("W")}胜{home_form.count("D")}平{home_form.count("L")}负)')
        p(f'  {away_cn} 近5场: {" ".join(away_form)} ({away_form.count("W")}胜{away_form.count("D")}平{away_form.count("L")}负)')

        # 近期进球趋势
        home_games = recent_data.get(home_af, [])
        away_games = recent_data.get(away_af, [])
        home_finished = [g for g in home_games if g['hs'] != '?' and g['as'] != '?']
        away_finished = [g for g in away_games if g['hs'] != '?' and g['as'] != '?']
        home_finished.sort(key=lambda x: x['date'], reverse=True)
        away_finished.sort(key=lambda x: x['date'], reverse=True)

        home_gf = 0; home_ga = 0
        for g in home_finished[:5]:
            try:
                hs, as_ = int(g['hs']), int(g['as'])
                if g['is_home']:
                    home_gf += hs; home_ga += as_
                else:
                    home_gf += as_; home_ga += hs
            except: pass
        away_gf = 0; away_ga = 0
        for g in away_finished[:5]:
            try:
                hs, as_ = int(g['hs']), int(g['as'])
                if g['is_home']:
                    away_gf += hs; away_ga += as_
                else:
                    away_gf += as_; away_ga += hs
            except: pass

        n_h = min(len(home_finished), 5) or 1
        n_a = min(len(away_finished), 5) or 1
        p(f'  {home_cn} 近5场进失: 进{home_gf}失{home_ga} (场均{home_gf/n_h:.1f}/{home_ga/n_h:.1f})')
        p(f'  {away_cn} 近5场进失: 进{away_gf}失{away_ga} (场均{away_gf/n_a:.1f}/{away_ga/n_a:.1f})')

    else:
        # 国际赛
        home_rank = fifa.get(home_cn, '?')
        away_rank = fifa.get(away_cn, '?')
        p(f'')
        p(f'  【FIFA排名】')
        p(f'  {home_cn}: FIFA #{home_rank}')
        p(f'  {away_cn}: FIFA #{away_rank}')
        if isinstance(home_rank, int) and isinstance(away_rank, int):
            diff = away_rank - home_rank
            if diff > 0:
                p(f'  排名差: {diff}位 ({home_cn}排名优势明显)' if diff > 20 else f'  排名差: {diff}位 ({home_cn}排名略优)')
            elif diff < 0:
                p(f'  排名差: {-diff}位 ({away_cn}排名优势明显)' if -diff > 20 else f'  排名差: {-diff}位 ({away_cn}排名略优)')
            else:
                p(f'  排名差: 同排名')

        # 国际赛特殊因素
        p(f'')
        p(f'  【国际赛特殊因素】')
        if home_cn == '日本' and away_cn == '冰岛':
            p(f'  • 日本主场(埼玉)优势巨大，亚洲顶级球队')
            p(f'  • 冰岛近年实力下滑严重，远离2016-2018巅峰期')
            p(f'  • 日本旅欧军团完整，三笘薫/久保建英/远藤航等核心可用')
            p(f'  • 友谊赛性质，日本可能轮换但替补实力仍远超冰岛')
            p(f'  • 1.15超低赔率反映巨大实力差距，但友谊赛冷门率偏高')
        elif home_cn == '捷克' and away_cn == '科索沃':
            p(f'  • 捷克主场优势，欧洲中上游球队')
            p(f'  • 科索沃FIFA排名101，实力差距明显')
            p(f'  • 捷克近期欧国联表现稳定，主场胜率高')
            p(f'  • 科索沃客场能力弱，面对欧洲中上游鲜有胜绩')
        elif home_cn == '美国' and away_cn == '塞内加尔':
            p(f'  • 美国主场优势(可能在中立场地)')
            p(f'  • 塞内加尔非洲冠军底蕴，马内/库利巴利等核心')
            p(f'  • FIFA排名接近(13 vs 17)，实力伯仲之间')
            p(f'  • 友谊赛双方可能试验阵容，不确定性高')
            p(f'  • 赔率2.43/3.00/2.60反映势均力敌')
        elif home_cn == '瑞士' and away_cn == '约旦':
            p(f'  • 瑞士欧洲强队，FIFA#12')
            p(f'  • 约旦亚洲中游，FIFA#71')
            p(f'  • 实力差距巨大，但赔率未出')
        elif home_cn == '德国' and away_cn == '芬兰':
            p(f'  • 德国FIFA#16，实力碾压芬兰(#58)')
            p(f'  • 赔率未出，预计德国大胜')
        elif home_cn == '巴西' and away_cn == '巴拿马':
            p(f'  • 巴西FIFA#5，世界顶级')
            p(f'  • 巴拿马FIFA#51，中北美中游')
            p(f'  • 赔率未出，预计巴西大胜')

    # === API预测对比 ===
    home_af = af_team_map.get(home_cn, '')
    api_pred = predictions.get(home_af)
    if api_pred:
        p(f'')
        p(f'  【API-Football预测】')
        p(f'  主{api_pred.get("prob_HW","?")}% 平{api_pred.get("prob_D","?")}% 客{api_pred.get("prob_AW","?")}%')
        p(f'  大2.5球: O={api_pred.get("prob_O_3","?")}% U={api_pred.get("prob_U_3","?")}%')
        p(f'  双方进球(BTS): {api_pred.get("prob_bts","?")}%')

        # 与体彩模型对比
        try:
            api_h = float(api_pred.get('prob_HW', 0))
            api_d = float(api_pred.get('prob_D', 0))
            api_a = float(api_pred.get('prob_AW', 0))
            api_pred_dir = max(['H','D','A'], key=lambda x: {'H':api_h,'D':api_d,'A':api_a}[x])
            if api_pred_dir == pred['pred']:
                p(f'  ✓ 与体彩模型一致: {pred_cn}')
            else:
                api_cn = {'H':'主胜','D':'平局','A':'客胜'}[api_pred_dir]
                p(f'  ✗ 与体彩模型不一致: 体彩={pred_cn} API={api_cn} → 需警惕!')
        except:
            pass

    # === 天气 ===
    city_en = city_map.get(home_cn, '')
    w = weather_data.get(city_en)
    if w:
        p(f'')
        p(f'  【天气】({city_en})')
        p(f'  {w["temp"]}°C(体感{w["feels"]}°C) 湿度{w["humidity"]}% 风{w["wind"]}km/h {w["desc"]} 降水{w["precip"]}mm')
        # 天气影响评估
        factors = []
        if w['temp'] and int(w['temp']) > 30: factors.append('高温影响体能')
        if w['humidity'] and int(w['humidity']) > 85: factors.append('高湿闷热')
        if w['wind'] and int(w['wind']) > 25: factors.append('大风影响传中/定位球')
        if w['precip'] and float(w['precip']) > 3: factors.append('降雨影响场地')
        if factors:
            p(f'  影响: {"; ".join(factors)}')
        else:
            p(f'  影响: 天气条件正常，对比赛影响小')

    # === 综合判断 ===
    p(f'')
    p(f'  【综合判断】')

    # 综合所有因素给出最终判断
    final_pred = pred['pred']
    final_conf = pred['conf']
    notes = []

    # 排名/实力因素
    if not is_intl:
        home_af = af_team_map.get(home_cn, '')
        away_af = af_team_map.get(away_cn, '')
        home_stats = get_team_stats(home_af)
        away_stats = get_team_stats(away_af)
        home_form = get_recent_form(home_af)
        away_form = get_recent_form(away_af)

        # 排名vs赔率一致性
        if home_stats and away_stats:
            try:
                h_pos = int(home_stats['pos'])
                a_pos = int(away_stats['pos'])
                if h_pos < a_pos and pred['pred'] == 'A':
                    notes.append(f'排名{h_pos}vs{a_pos}主队更高但赔率倾向客胜 → 可能是客场龙/主场虫')
                elif a_pos < h_pos and pred['pred'] == 'H':
                    notes.append(f'排名{a_pos}vs{h_pos}客队更高但赔率倾向主胜 → 主场优势被高估')
            except: pass

        # 近况vs赔率
        if home_form and away_form:
            h_wr = home_form.count('W') / len(home_form) if home_form else 0
            a_wr = away_form.count('W') / len(away_form) if away_form else 0
            if h_wr > 0.6 and a_wr < 0.4 and pred['pred'] != 'H':
                notes.append(f'主队近况{home_form}火热但模型不看好 → 值得关注')
            if a_wr > 0.6 and h_wr < 0.4 and pred['pred'] != 'A':
                notes.append(f'客队近况{away_form}火热但模型不看好 → 值得关注')

        # 主客场差异
        if home_stats and away_stats:
            try:
                h_home_wr = int(home_stats['hw']) / (int(home_stats['hw'])+int(home_stats['hd'])+int(home_stats['hl'])) if (int(home_stats['hw'])+int(home_stats['hd'])+int(home_stats['hl'])) > 0 else 0
                a_away_wr = int(away_stats['aw']) / (int(away_stats['aw'])+int(away_stats['ad'])+int(away_stats['al'])) if (int(away_stats['aw'])+int(away_stats['ad'])+int(away_stats['al'])) > 0 else 0
                if h_home_wr > 0.6:
                    notes.append(f'主队主场胜率{h_home_wr*100:.0f}% → 主场强势')
                if a_away_wr < 0.3:
                    notes.append(f'客队客场胜率{a_away_wr*100:.0f}% → 客场疲软')
            except: pass

    else:
        # 国际赛
        home_rank = fifa.get(home_cn, 0)
        away_rank = fifa.get(away_cn, 0)
        if isinstance(home_rank, int) and isinstance(away_rank, int):
            if home_rank < away_rank - 30 and pred['pred'] == 'H':
                notes.append(f'FIFA排名#{home_rank}vs#{away_rank}差距大 → 主胜合理')
            elif away_rank < home_rank - 30 and pred['pred'] == 'A':
                notes.append(f'FIFA排名#{away_rank}vs#{home_rank}差距大 → 客胜合理')
            elif abs(home_rank - away_rank) < 15:
                notes.append(f'FIFA排名接近(#{home_rank}vs#{away_rank}) → 势均力敌，平局概率提升')

        # 友谊赛因素
        notes.append('友谊赛/国际赛性质 → 战意不确定，轮换多，冷门率高于正式赛')

    # API预测对比
    if api_pred:
        try:
            api_h = float(api_pred.get('prob_HW', 0))
            api_d = float(api_pred.get('prob_D', 0))
            api_a = float(api_pred.get('prob_AW', 0))
            api_dir = max(['H','D','A'], key=lambda x: {'H':api_h,'D':api_d,'A':api_a}[x])
            if api_dir != pred['pred']:
                api_cn = {'H':'主胜','D':'平局','A':'客胜'}[api_dir]
                notes.append(f'API预测{api_cn}vs体彩{pred_cn} → 分歧! 需谨慎')
        except: pass

    # 天气因素
    if w:
        if w['temp'] and int(w['temp']) > 28:
            notes.append(f'气温{w["temp"]}°C偏高 → 体能消耗大，下半场进球概率升')
        if w['humidity'] and int(w['humidity']) > 85:
            notes.append(f'湿度{w["humidity"]}%极高 → 芬超/北欧特殊条件')

    # 冷门预警
    min_o = min(oh, oa)
    if 0 < min_o < 1.40:
        fav = '主' if oh < oa else '客'
        notes.append(f'⚠ 冷门预警: {fav}方赔率{min_o:.2f}极低 → 博彩公司高度看好但回报差')

    # margin过高
    if pred['margin'] > 0.12:
        notes.append(f'margin={pred["margin"]*100:.1f}%偏高 → 体彩抽水多，EV普遍为负')

    for note in notes:
        p(f'  • {note}')

    # === 推荐比分 ===
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

    p(f'')
    p(f'  【推荐比分】')
    for i, (sc, odds) in enumerate(picks[:3]):
        d_cn = {'H':'主胜','D':'平局','A':'客胜'}[score_dir(sc)]
        p(f'    {i+1}. {sc}  ({d_cn}, 赔率{odds:.1f})')
    p(f'  【大小球】')
    goal_str = '  '.join(f'{g}={v:.1f}' for g, v in top3_goals)
    p(f'    {goal_str}')

# ===== 汇总 =====
p('')
p(f'  {"═"*85}')
p(f'  汇总推荐 (按EV排序)')
p(f'  {"═"*85}')

all_recs = []
for m in sporttery_matches:
    pred = predict(m['oh'], m['od'], m['oa'], m['league'])
    if not pred: continue
    evs = [('主胜',pred['ev_h'],m['oh'],pred['hp']), ('平局',pred['ev_d'],m['od'],pred['dp']), ('客胜',pred['ev_a'],m['oa'],pred['ap'])]
    best = max(evs, key=lambda x: x[1])
    all_recs.append((m, best, pred))

all_recs.sort(key=lambda x: -x[1][1])

p('')
p(f'  {"编号":6s} {"联赛":6s} {"比赛":28s} {"方向":6s} {"EV":8s} {"赔率":6s} {"概率":8s} {"备注"}')
p(f'  {"─"*80}')
for rec in all_recs:
    m = rec[0]
    dir_name, ev, odds, prob = rec[1]
    pred = rec[2]
    marker = '★' if ev > -0.05 else ''
    match_str = m['home'] + ' vs ' + m['away']

    # 备注
    note = ''
    home_af = af_team_map.get(m['home'], '')
    api_pred_data = predictions.get(home_af)
    if api_pred_data:
        try:
            api_h = float(api_pred_data.get('prob_HW', 0))
            api_d = float(api_pred_data.get('prob_D', 0))
            api_a = float(api_pred_data.get('prob_AW', 0))
            api_dir = max(['H','D','A'], key=lambda x: {'H':api_h,'D':api_d,'A':api_a}[x])
            if api_dir != pred['pred']:
                note = 'API分歧'
        except: pass
    if m['league'] == '国际赛':
        note = note + '友谊赛' if note else '友谊赛'

    p(f'  {m["num_str"]:6s} {m["league"]:6s} {match_str:28s} {dir_name:6s} {ev:+.3f}  {odds:.2f}  {prob*100:.1f}%{marker}  {note}')

p('')
p(f'  冷门预警 (低赔率<1.40):')
for m in sporttery_matches:
    min_o = min(m['oh'], m['oa'])
    if 0 < min_o < 1.40:
        fav = '主' if m['oh'] < m['oa'] else '客'
        risk = '高' if min_o < 1.25 else '中' if min_o < 1.35 else '低'
        p(f'    {m["num_str"]} {m["home"]} vs {m["away"]} → {fav}方{min_o:.2f} 风险{risk}')

p('')
p('=' * 90)

report = '\n'.join(lines)
print(report)
