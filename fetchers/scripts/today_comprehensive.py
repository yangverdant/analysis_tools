"""
6/1体彩推荐 - 综合实力分析版
不只是"是不是世界杯队"，而是看:
1. FIFA排名 → 量化实力差距
2. 历史交锋H2H → 过往战绩和比分
3. 球队打法 → 控球型vs反击型, 进攻火力vs防守硬度
4. 核心球员 → 有没有超级巨星(哈兰德/居勒尔/阿瑙托维奇等)
5. 世界杯动机 → WC队磨合战意 vs 非WC队走过场
6. 赔率+让球 → 市场定价+价值方向
"""
import sys, io, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import urllib3
urllib3.disable_warnings()

API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
API_URL = 'https://apiv3.apifootball.com'

# 球队apifootball ID映射
team_api_ids = {
    '保加利亚': 170, '黑山': 617, '挪威': 661, '瑞典': 885,
    '土耳其': 922, '北马其顿': 657, '奥地利': 85, '突尼斯': 921,
    '加拿大': 188, '乌兹别克斯坦': 943, '哥伦比亚': 227, '哥斯达黎加': 239,
}

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

# ===== 1. FIFA排名 (2025年12月数据) =====
fifa_ranking = {
    '阿根廷':1, '法国':2, '西班牙':3, '英格兰':4, '巴西':5,
    '葡萄牙':6, '荷兰':7, '比利时':8, '意大利':9, '德国':10,
    '乌拉圭':11, '哥伦比亚':12, '克罗地亚':13, '摩洛哥':14, '瑞士':15,
    '美国':16, '墨西哥':17, '日本':18, '丹麦':19, '塞内加尔':20,
    '奥地利':21, '韩国':22, '土耳其':23, '瑞典':24, '波兰':25,
    '乌克兰':26, '智利':27, '威尔士':28, '捷克':29, '委内瑞拉':30,
    '苏格兰':31, '厄瓜多尔':32, '爱尔兰':33, '突尼斯':34, '罗马尼亚':35,
    '挪威':36, '斯洛伐克':37, '巴拉圭':38, '塞尔维亚':39, '加纳':40,
    '尼日利亚':41, '喀麦隆':42, '加拿大':43, '匈牙利':44, '阿尔及利亚':45,
    '伊朗':46, '沙特':47, '巴拿马':48, '哥斯达黎加':49, '澳大利亚':50,
    '秘鲁':51, '牙买加':52, '洪都拉斯':53, '冰岛':54, '黑山':55,
    '北马其顿':56, '保加利亚':57, '乌兹别克斯坦':58, '芬兰':59,
    '科索沃':60, '约旦':61, '巴拿马':62,
    # 英文名映射
    'Argentina':1, 'France':2, 'Spain':3, 'England':4, 'Brazil':5,
    'Portugal':6, 'Netherlands':7, 'Belgium':8, 'Italy':9, 'Germany':10,
    'Uruguay':11, 'Colombia':12, 'Croatia':13, 'Morocco':14, 'Switzerland':15,
    'USA':16, 'Mexico':17, 'Japan':18, 'Denmark':19, 'Senegal':20,
    'Austria':21, 'South Korea':22, 'Turkey':23, 'Sweden':24, 'Poland':25,
    'Ukraine':26, 'Chile':27, 'Wales':28, 'Czech Republic':29, 'Venezuela':30,
    'Scotland':31, 'Ecuador':32, 'Tunisia':34, 'Romania':35,
    'Norway':36, 'Slovakia':37, 'Paraguay':38, 'Serbia':39, 'Ghana':40,
    'Nigeria':41, 'Cameroon':42, 'Canada':43, 'Hungary':44, 'Algeria':45,
    'Iran':46, 'Saudi Arabia':47, 'Panama':48, 'Costa Rica':49, 'Australia':50,
    'Jamaica':52, 'Honduras':53, 'Iceland':54, 'Montenegro':55,
    'North Macedonia':56, 'Bulgaria':57, 'Uzbekistan':58, 'Finland':59,
    'Czechia':29, 'Brasil':5,
}

# 体彩中文→FIFA排名(手动映射)
cn_to_fifa = {
    '保加利亚': 57, '黑山': 55, '挪威': 36, '瑞典': 24,
    '土耳其': 23, '北马其顿': 56, '奥地利': 21, '突尼斯': 34,
    '加拿大': 43, '乌兹别克斯坦': 58, '哥伦比亚': 12, '哥斯达黎加': 49,
}

def get_fifa_rank(name):
    if name in cn_to_fifa: return cn_to_fifa[name]
    if name in fifa_ranking: return fifa_ranking[name]
    return None

# ===== 2. 球队打法画像 =====
team_profile = {
    '土耳其': {
        'style': '控球+边路', 'strength': '中场控制力强,恰尔汗奥卢组织核心',
        'weakness': '防守不稳,容易丢球', 'attack': 7, 'defense': 5,
        'key_players': ['恰尔汗奥卢(中场核心)', '居勒尔(皇马新星)', '伊尔马兹(锋线)'],
        'formation': '4-2-3-1', 'wc_team': True,
    },
    '北马其顿': {
        'style': '防守反击', 'strength': '防守纪律性好',
        'weakness': '进攻火力不足,缺乏顶级球员', 'attack': 4, 'defense': 6,
        'key_players': ['埃尔马斯(中场)', '巴尔科利夫斯基(老将)'],
        'formation': '5-4-1', 'wc_team': False,
    },
    '奥地利': {
        'style': '高位压迫', 'strength': '朗尼克体系,整体性强,压迫凶',
        'weakness': '缺少顶级射手', 'attack': 7, 'defense': 7,
        'key_players': ['萨比策(中场)', '阿瑙托维奇(锋线)', '莱默尔(中场)'],
        'formation': '4-2-3-1', 'wc_team': True,
    },
    '突尼斯': {
        'style': '防守反击', 'strength': '非洲防守强队,纪律性好',
        'weakness': '进攻创造力不足', 'attack': 5, 'defense': 7,
        'key_players': ['斯希里(中场)', '哈兹里(锋线)'],
        'formation': '4-3-3', 'wc_team': True,
    },
    '加拿大': {
        'style': '速度+边路', 'strength': '阿方索·戴维斯速度恐怖,主场优势',
        'weakness': '整体技术粗糙,中场控制力弱', 'attack': 6, 'defense': 5,
        'key_players': ['阿方索·戴维斯(边路爆点)', '乔纳森·大卫(锋线)'],
        'formation': '4-4-2', 'wc_team': True,
    },
    '乌兹别克斯坦': {
        'style': '防守反击', 'strength': '亚洲新锐,有一定组织能力',
        'weakness': '对抗弱,面对欧美球队身体吃亏', 'attack': 4, 'defense': 5,
        'key_players': ['肖穆罗多夫(锋线)', '马沙里波夫(中场)'],
        'formation': '4-2-3-1', 'wc_team': False,
    },
    '保加利亚': {
        'style': '防守反击', 'strength': '无',
        'weakness': '实力严重下滑,无顶级球员', 'attack': 3, 'defense': 5,
        'key_players': ['基里洛夫(中场)'],
        'formation': '4-5-1', 'wc_team': False,
    },
    '黑山': {
        'style': '防守反击', 'strength': '约韦蒂奇经验丰富',
        'weakness': '阵容单薄,整体实力弱', 'attack': 4, 'defense': 5,
        'key_players': ['约韦蒂奇(老将锋线)', '萨维奇(后卫)'],
        'formation': '4-5-1', 'wc_team': False,
    },
    '挪威': {
        'style': '直接进攻', 'strength': '哈兰德+厄德高双核,进攻火力顶级',
        'weakness': '防守端一般,整体配合不够默契', 'attack': 8, 'defense': 5,
        'key_players': ['哈兰德(超级射手)', '厄德高(中场大师)', '瑟洛特(锋线)'],
        'formation': '4-3-3', 'wc_team': True,
    },
    '瑞典': {
        'style': '身体对抗', 'strength': '身体强壮,定位球好',
        'weakness': '技术偏粗糙,缺少创造力', 'attack': 5, 'defense': 6,
        'key_players': ['伊萨克(锋线)', '福斯贝里(中场)'],
        'formation': '4-4-2', 'wc_team': True,
    },
    '哥伦比亚': {
        'style': '技术流+边路', 'strength': 'J罗组织+路易斯·迪亚斯速度,进攻华丽',
        'weakness': '防守有时松散', 'attack': 8, 'defense': 6,
        'key_players': ['J罗(组织核心)', '路易斯·迪亚斯(边路)', '夸德拉多(边路)'],
        'formation': '4-2-3-1', 'wc_team': True,
    },
    '哥斯达黎加': {
        'style': '防守反击', 'strength': '纳瓦斯门神,防守纪律好',
        'weakness': '阵容老化,进攻乏力', 'attack': 4, 'defense': 6,
        'key_players': ['纳瓦斯(门神)', '鲁伊斯(中场)'],
        'formation': '5-4-1', 'wc_team': True,
    },
}

# ===== 3. 世界杯参赛状态 =====
wc_teams = {
    '加拿大', '墨西哥', '美国', 'USA', 'Canada', 'Mexico',
    '阿根廷', '巴西', '哥伦比亚', '厄瓜多尔', '巴拉圭', '乌拉圭', '智利', '委内瑞拉',
    'Argentina', 'Brazil', 'Colombia', 'Ecuador', 'Paraguay', 'Uruguay', 'Chile', 'Venezuela',
    'Brasil',
    '德国', '法国', '西班牙', '英格兰', '荷兰', '葡萄牙', '意大利', '比利时',
    '瑞士', '奥地利', '土耳其', '丹麦', '瑞典', '波兰', '捷克', '塞尔维亚',
    '克罗地亚', '苏格兰', '威尔士', '乌克兰', '挪威', '斯洛伐克', '匈牙利', '罗马尼亚',
    'Germany', 'France', 'Spain', 'England', 'Netherlands', 'Portugal', 'Italy', 'Belgium',
    'Switzerland', 'Austria', 'Turkey', 'Denmark', 'Sweden', 'Poland', 'Czech Republic',
    'Serbia', 'Croatia', 'Scotland', 'Wales', 'Ukraine', 'Norway', 'Slovakia', 'Hungary',
    'Romania', 'Czechia',
    '日本', '韩国', '伊朗', '沙特', '澳大利亚',
    'Japan', 'South Korea', 'Iran', 'Saudi Arabia', 'Australia',
    '塞内加尔', '摩洛哥', '尼日利亚', '喀麦隆', '加纳', '突尼斯', '阿尔及利亚',
    'Senegal', 'Morocco', 'Nigeria', 'Cameroon', 'Ghana', 'Tunisia', 'Algeria',
    '哥斯达黎加', '巴拿马', '牙买加', '洪都拉斯',
    'Costa Rica', 'Panama', 'Jamaica', 'Honduras',
}

def is_wc_team(name):
    if name in team_profile: return team_profile[name]['wc_team']
    return name in wc_teams

# ===== 4. 模型预测 =====
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

# ===== 预加载H2H数据 + 国家队近期战绩 =====
h2h_data = {}  # key: "home_vs_away"
team_form = {}  # key: team_cn, value: {w, d, l, matches:[]}
api_session = requests.Session()
api_session.trust_env = False
api_session.verify = False

# 球队apifootball ID → 查询国家队近期战绩
fifa_data = json.load(open('d:/football_tools/fifa_national_teams.json', 'r', encoding='utf-8'))
fifa_id_map = {t['name_en']: t['id'] for t in fifa_data}

for m_temp in matches:
    home_cn = m_temp['home']
    away_cn = m_temp['away']
    home_id = team_api_ids.get(home_cn)
    away_id = team_api_ids.get(away_id, '') if False else team_api_ids.get(away_cn)

    # 查国家队近期国际赛战绩
    for team_cn, tid in [(home_cn, home_id), (away_cn, away_id)]:
        if not tid or team_cn in team_form:
            continue
        try:
            r = api_session.get(f'{API_URL}/', params={
                'action': 'get_events',
                'team_id': str(tid),
                'from': '2025-01-01',
                'to': '2026-06-01',
                'APIkey': API_KEY,
            }, timeout=15)
            data = r.json()
            if isinstance(data, list):
                intl = [m for m in data if any(kw in (m.get('league_name','')+m.get('country_name',''))
                        for kw in ['International', 'Friendly', 'World', 'Euro', 'Nations'])]
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
                        'home': m2.get('match_hometeam_name',''),
                        'away': m2.get('match_awayteam_name',''),
                        'score': f'{h}:{a}',
                        'league': m2.get('league_name',''),
                        'result': result,
                    })
                team_form[team_cn] = {'w': w, 'd': d, 'l': l, 'results': results}
        except:
            team_form[team_cn] = {'w': 0, 'd': 0, 'l': 0, 'results': []}

    # H2H交锋记录
    if not home_id or not away_id:
        continue
    key = f'{home_cn}_vs_{away_cn}'
    try:
        r = api_session.get(f'{API_URL}/', params={
            'action': 'get_H2H',
            'firstTeamId': str(home_id),
            'secondTeamId': str(away_id),
            'APIkey': API_KEY,
        }, timeout=15)
        h2h_raw = r.json()

        # apifootball H2H返回dict: {firstTeam_VS_secondTeam:[], firstTeam_lastResults:[], secondTeam_lastResults:[]}
        vs_list = h2h_raw.get('firstTeam_VS_secondTeam', []) if isinstance(h2h_raw, dict) else (h2h_raw if isinstance(h2h_raw, list) else [])
        first_last = h2h_raw.get('firstTeam_lastResults', []) if isinstance(h2h_raw, dict) else []
        second_last = h2h_raw.get('secondTeam_lastResults', []) if isinstance(h2h_raw, dict) else []

        finished = [m for m in vs_list if m.get('match_status') == 'Finished']
        home_wins = draws = away_wins = 0
        home_goals = away_goals = 0
        recent = []
        for m2 in finished:
            hs = m2.get('match_hometeam_score', '0')
            as2 = m2.get('match_awayteam_score', '0')
            try:
                h = int(hs); a = int(as2)
            except:
                continue
            h_id = m2.get('match_hometeam_id', '')
            is_home_pov = (str(home_id) == h_id)
            if is_home_pov:
                if h > a: home_wins += 1
                elif h == a: draws += 1
                else: away_wins += 1
                home_goals += h; away_goals += a
            else:
                if h > a: away_wins += 1
                elif h == a: draws += 1
                else: home_wins += 1
                home_goals += a; away_goals += h
            recent.append({
                'date': m2.get('match_date', '?'),
                'home': m2.get('match_hometeam_name', ''),
                'away': m2.get('match_awayteam_name', ''),
                'score': f'{h}:{a}',
                'league': m2.get('league_name', ''),
            })
        total = home_wins + draws + away_wins
        avg_home_goals = home_goals / total if total > 0 else 0
        avg_away_goals = away_goals / total if total > 0 else 0

        # 两队各自最近战绩
        first_results = []  # [(W/D/L, score)]
        for m2 in first_last[:5]:
            hs = m2.get('match_hometeam_score', '0')
            as2 = m2.get('match_awayteam_score', '0')
            try: h = int(hs); a = int(as2)
            except: continue
            h_id = m2.get('match_hometeam_id', '')
            is_home = (str(home_id) == h_id)
            if is_home:
                result = 'W' if h > a else ('D' if h == a else 'L')
                gf, ga = h, a
            else:
                result = 'W' if a > h else ('D' if a == h else 'L')
                gf, ga = a, h
            first_results.append((result, f'{gf}:{ga}', m2.get('match_hometeam_name',''), m2.get('match_awayteam_name','')))

        second_results = []
        for m2 in second_last[:5]:
            hs = m2.get('match_hometeam_score', '0')
            as2 = m2.get('match_awayteam_score', '0')
            try: h = int(hs); a = int(as2)
            except: continue
            h_id = m2.get('match_hometeam_id', '')
            is_home = (str(away_id) == h_id)
            if is_home:
                result = 'W' if h > a else ('D' if h == a else 'L')
                gf, ga = h, a
            else:
                result = 'W' if a > h else ('D' if a == h else 'L')
                gf, ga = a, h
            second_results.append((result, f'{gf}:{ga}', m2.get('match_hometeam_name',''), m2.get('match_awayteam_name','')))

        h2h_data[key] = {
            'total': total, 'home_wins': home_wins, 'draws': draws, 'away_wins': away_wins,
            'avg_home_goals': avg_home_goals, 'avg_away_goals': avg_away_goals,
            'recent': recent[-5:],
            'first_form': first_results,  # 主队近况
            'second_form': second_results,  # 客队近况
        }
    except:
        pass

p('=' * 90)
p('  6/1 体彩推荐 — 综合实力分析版')
p('  分析维度: FIFA排名 + 球队打法 + 核心球员 + 世界杯动机 + 赔率')
p('  5/31验证: WC强队碾压非WC队 4/4全中, 但关键是实力差距而非WC标签')
p('=' * 90)

results = []
for m in matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    # 特殊处理: 只有让球没有SPF的比赛(如哥伦比亚vs哥斯达黎加)
    has_rq_only = (not oh or not od or not oa) and m['rqh'] and m['rqd'] and m['rqa']
    if not oh or not od or not oa:
        if has_rq_only:
            # 用让球赔率做基础分析
            rqh, rqd, rqa = m['rqh'], m['rqd'], m['rqa']
            rq_pred = predict(rqh, rqd, rqa, m['league'])
            pred = None
        else:
            p('')
            p(f'  {m["num_str"]} {m["home"]} vs {m["away"]} [{m["league"]}] {m["time"]}')
            p(f'  赔率未出')
            continue

    pred = predict(oh, od, oa, m['league'])
    rq_pred = predict(m['rqh'], m['rqd'], m['rqa'], m['league'])

    home_wc = is_wc_team(m['home'])
    away_wc = is_wc_team(m['away'])

    # FIFA排名
    home_rank = get_fifa_rank(m['home'])
    away_rank = get_fifa_rank(m['away'])
    rank_diff = None
    if home_rank and away_rank:
        rank_diff = away_rank - home_rank  # 正=主队排名更高(数字更小)

    # 球队画像
    home_prof = team_profile.get(m['home'])
    away_prof = team_profile.get(m['away'])

    if not pred and not rq_pred:
        continue  # 跳过完全没有赔率的比赛

    if pred is None and has_rq_only:
        # 只有让球赔率的比赛, 用让球赔率构造一个基础预测
        # 让-2的强队: 假设主胜概率极高(约80%)
        pred = {'hp': 0.80, 'dp': 0.10, 'ap': 0.10, 'pred': 'H', 'conf': 0.80,
                'margin': 0, 'ev_h': 0, 'ev_d': 0, 'ev_a': 0}

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

    # ===== 综合实力分析 =====
    p('')
    p(f'  {m["num_str"]} {m["home"]}{"★" if home_wc else ""} vs {m["away"]}{"★" if away_wc else ""} [{m["league"]}] {m["time"]}')
    p(f'  {"═"*80}')

    # 1) FIFA排名
    p(f'  【FIFA排名】')
    if home_rank and away_rank:
        p(f'    {m["home"]}: #{home_rank}  vs  {m["away"]}: #{away_rank}  差距: {abs(rank_diff)}位')
        if rank_diff >= 20:
            p(f'    → 主队实力远强于客队(排名差≥20)')
        elif rank_diff >= 10:
            p(f'    → 主队实力明显强于客队(排名差≥10)')
        elif rank_diff >= 5:
            p(f'    → 主队实力略强于客队')
        elif rank_diff > -5:
            p(f'    → 双方实力接近')
        elif rank_diff > -10:
            p(f'    → 客队实力略强于主队')
        else:
            p(f'    → 客队实力明显强于主队')
    else:
        p(f'    {m["home"]}: {"#"+str(home_rank) if home_rank else "未知"}  vs  {m["away"]}: {"#"+str(away_rank) if away_rank else "未知"}')

    # 2) 球队打法
    p(f'  【球队打法】')
    if home_prof:
        p(f'    {m["home"]}: {home_prof["style"]} | 阵型{home_prof["formation"]} | 进攻{home_prof["attack"]}/10 防守{home_prof["defense"]}/10')
        p(f'    核心球员: {", ".join(home_prof["key_players"])}')
        p(f'    优势: {home_prof["strength"]} | 弱点: {home_prof["weakness"]}')
    else:
        p(f'    {m["home"]}: 数据不足')
    if away_prof:
        p(f'    {m["away"]}: {away_prof["style"]} | 阵型{away_prof["formation"]} | 进攻{away_prof["attack"]}/10 防守{away_prof["defense"]}/10')
        p(f'    核心球员: {", ".join(away_prof["key_players"])}')
        p(f'    优势: {away_prof["strength"]} | 弱点: {away_prof["weakness"]}')
    else:
        p(f'    {m["away"]}: 数据不足')

    # 3) 历史交锋 + 近况
    h2h_key = f'{m["home"]}_vs_{m["away"]}'
    h2h = h2h_data.get(h2h_key)
    p(f'  【历史交锋 + 近况】')
    if h2h:
        if h2h['total'] > 0:
            p(f'    交锋: {h2h["total"]}场 → {m["home"]}胜{h2h["home_wins"]} 平{h2h["draws"]} {m["away"]}胜{h2h["away_wins"]}')
            p(f'    场均: {m["home"]}{h2h["avg_home_goals"]:.1f}球 vs {m["away"]}{h2h["avg_away_goals"]:.1f}球')
            win_rate = h2h["home_wins"] / h2h["total"] * 100
            if win_rate >= 70:
                p(f'    → {m["home"]}历史碾压({win_rate:.0f}%胜率)')
            elif win_rate >= 55:
                p(f'    → {m["home"]}历史占优({win_rate:.0f}%胜率)')
            elif win_rate >= 45:
                p(f'    → 历史势均力敌')
            elif win_rate >= 30:
                p(f'    → {m["away"]}历史占优({100-win_rate:.0f}%胜率)')
            else:
                p(f'    → {m["away"]}历史碾压({100-win_rate:.0f}%胜率)')
            if h2h['recent']:
                p(f'    交锋记录:')
                for r2 in h2h['recent']:
                    p(f'      {r2["date"]} {r2["home"]} {r2["score"]} {r2["away"]} [{r2["league"]}]')
        else:
            p(f'    无历史交锋记录')

        # 两队国家队近况(真正的国际赛战绩)
        hf = team_form.get(m["home"])
        af = team_form.get(m["away"])
        if hf and hf['results']:
            form_str = ' '.join(r['result'] for r in hf['results'])
            total = hf['w'] + hf['d'] + hf['l']
            p(f'    {m["home"]}国家队近况: {form_str} ({hf["w"]}W{hf["d"]}D{hf["l"]}L / {total}场)')
            for r2 in hf['results'][:3]:
                p(f'      {r2["date"]} {r2["home"]} {r2["score"]} {r2["away"]} [{r2["league"]}]')
        if af and af['results']:
            form_str = ' '.join(r['result'] for r in af['results'])
            total = af['w'] + af['d'] + af['l']
            p(f'    {m["away"]}国家队近况: {form_str} ({af["w"]}W{af["d"]}D{af["l"]}L / {total}场)')
            for r2 in af['results'][:3]:
                p(f'      {r2["date"]} {r2["home"]} {r2["score"]} {r2["away"]} [{r2["league"]}]')
    else:
        p(f'    无数据')

    # 4) 打法相克
    if home_prof and away_prof:
        p(f'  【打法相克】')
        h_style = home_prof['style']
        a_style = away_prof['style']

        # 控球型 vs 防反型
        if '控球' in h_style and '反击' in a_style:
            p(f'    {m["home"]}控球 vs {m["away"]}防反 → 控球方主导但防反有偷袭机会')
            p(f'    关键: {m["home"]}能否尽早破门, 否则防反偷一个就麻烦')
        elif '反击' in h_style and '控球' in a_style:
            p(f'    {m["home"]}防反 vs {m["away"]}控球 → 主队靠反击, 客队控球主导')
            p(f'    关键: {m["home"]}主场+反击, 如果客队压上留空档就有机会')
        elif '压迫' in h_style and '反击' in a_style:
            p(f'    {m["home"]}高位压迫 vs {m["away"]}防反 → 压迫方抢断后快速进攻, 防反方出球困难')
            p(f'    → 压迫方优势明显, 防反方很难组织有效反击')
        elif '速度' in h_style and '防守' in a_style:
            p(f'    {m["home"]}速度型 vs {m["away"]}防守型 → 速度冲击防线, 防守方压力大')
        elif '直接' in h_style and '身体' in a_style:
            p(f'    {m["home"]}直接进攻 vs {m["away"]}身体对抗 → 对攻战, 看谁火力更猛')
        elif '技术' in h_style and '防守' in a_style:
            p(f'    {m["home"]}技术流 vs {m["away"]}防守型 → 技术流控球主导, 防守方靠纪律')

        # 进攻vs防守对比
        atk_diff = home_prof['attack'] - away_prof['defense']
        def_diff = home_prof['defense'] - away_prof['attack']
        p(f'    进攻对冲: {m["home"]}进攻{home_prof["attack"]} vs {m["away"]}防守{away_prof["defense"]} = {"主优" if atk_diff>0 else "客优" if atk_diff<0 else "均势"}({atk_diff:+d})')
        p(f'    防守对冲: {m["home"]}防守{home_prof["defense"]} vs {m["away"]}进攻{away_prof["attack"]} = {"主优" if def_diff>0 else "客优" if def_diff<0 else "均势"}({def_diff:+d})')

    # 5) 世界杯动机
    p(f'  【世界杯动机】')
    if home_wc and not away_wc:
        p(f'    {m["home"]}是WC队(6/12开幕) → 认真磨合, 要赢要大胜')
        p(f'    {m["away"]}非WC队 → 无大赛压力, 战意存疑')
        p(f'    → 动机不对称: 主队认真打, 客队可能走过场')
    elif away_wc and not home_wc:
        p(f'    {m["away"]}是WC队 → 认真磨合')
        p(f'    {m["home"]}非WC队 → 战意存疑')
        p(f'    → 动机不对称: 客队认真打')
    elif home_wc and away_wc:
        p(f'    双方都是WC队 → 都在磨合, 但不会拼命(怕受伤)')
        p(f'    → 试探为主, 比分不会太夸张')
    else:
        p(f'    双方非WC队 → 战意不确定, 可能走过场')

    # 6) 赔率分析
    p(f'  【赔率分析】')
    if has_rq_only:
        p(f'    SPF赔率未出, 只有让球赔率')
    else:
        p(f'    SPF: {pred_cn}({pred["conf"]*100:.0f}%)  赔率 {oh:.2f}/{od:.2f}/{oa:.2f}')
        p(f'    概率: 主{pred["hp"]*100:.1f}% 平{pred["dp"]*100:.1f}% 客{pred["ap"]*100:.1f}%')
    if hc and rq_cn:
        rq_conf = rq_pred['conf'] if rq_pred else 0
        p(f'    让球: 让{hc} {rq_cn}({rq_conf*100:.0f}%) 赔率{m["rqh"]:.2f}/{m["rqd"]:.2f}/{m["rqa"]:.2f}')
        p(f'    含义: {rq_meaning}')

    # ===== 综合评分 =====
    score_val = 0
    reasons = []

    # FIFA排名差距 (最重要)
    if rank_diff is not None:
        if rank_diff >= 20:
            score_val += 5; reasons.append(f'排名差{rank_diff}(碾压级)')
        elif rank_diff >= 10:
            score_val += 3; reasons.append(f'排名差{rank_diff}(明显优)')
        elif rank_diff >= 5:
            score_val += 1; reasons.append(f'排名差{rank_diff}(略优)')
        elif rank_diff > -5:
            score_val += 0; reasons.append('排名接近')
        elif rank_diff > -10:
            score_val -= 1; reasons.append(f'排名差{rank_diff}(客优)')
        else:
            score_val -= 3; reasons.append(f'排名差{rank_diff}(客碾压)')

    # 历史交锋优势
    if h2h and h2h['total'] >= 3:
        win_rate = h2h['home_wins'] / h2h['total']
        if win_rate >= 0.70:
            score_val += 3; reasons.append(f'H2H碾压({win_rate*100:.0f}%胜)')
        elif win_rate >= 0.55:
            score_val += 2; reasons.append(f'H2H占优({win_rate*100:.0f}%胜)')
        elif win_rate >= 0.45:
            score_val += 0; reasons.append('H2H均势')
        elif win_rate >= 0.30:
            score_val -= 2; reasons.append(f'H2H劣势({win_rate*100:.0f}%胜)')
        else:
            score_val -= 3; reasons.append(f'H2H被碾压({win_rate*100:.0f}%胜)')
        # 场均进球趋势
        if h2h['avg_home_goals'] >= 2.0:
            score_val += 1; reasons.append(f'H2H场均{h2h["avg_home_goals"]:.1f}球')
    elif h2h and h2h['total'] > 0:
        # 样本太少, 仅做参考
        if h2h['home_wins'] > h2h['away_wins']:
            score_val += 1; reasons.append('H2H略优(样本少)')
        elif h2h['away_wins'] > h2h['home_wins']:
            score_val -= 1; reasons.append('H2H略劣(样本少)')

    # 进攻vs防守对冲
    if home_prof and away_prof:
        atk_diff = home_prof['attack'] - away_prof['defense']
        if atk_diff >= 3:
            score_val += 2; reasons.append('进攻碾压防守')
        elif atk_diff >= 1:
            score_val += 1; reasons.append('进攻略优防守')

    # 世界杯动机
    if home_wc and not away_wc:
        score_val += 2; reasons.append('WC动机碾压')
    elif away_wc and not home_wc:
        score_val += 1; reasons.append('客队WC动机')
    elif home_wc and away_wc:
        score_val -= 1; reasons.append('WC vs WC试探')

    # 国家队近期状态差
    hf = team_form.get(m["home"])
    af = team_form.get(m["away"])
    if hf and af:
        h_pts = hf['w'] * 3 + hf['d']  # 简易积分
        a_pts = af['w'] * 3 + af['d']
        h_total = hf['w'] + hf['d'] + hf['l']
        a_total = af['w'] + af['d'] + af['l']
        if h_total >= 3 and a_total >= 3:
            h_rate = h_pts / (h_total * 3) * 100
            a_rate = a_pts / (a_total * 3) * 100
            form_diff = h_rate - a_rate
            if form_diff >= 30:
                score_val += 2; reasons.append(f'状态差{form_diff:.0f}pp(主优)')
            elif form_diff >= 15:
                score_val += 1; reasons.append(f'状态差{form_diff:.0f}pp(主略优)')
            elif form_diff <= -30:
                score_val -= 2; reasons.append(f'状态差{form_diff:.0f}pp(客优)')
            elif form_diff <= -15:
                score_val -= 1; reasons.append(f'状态差{form_diff:.0f}pp(客略优)')
        # 特殊: 客队连败
        if af['l'] >= 4 and af['w'] == 0:
            score_val += 2; reasons.append(f'{m["away"]}连败{af["l"]}场!')
        if hf['l'] >= 4 and hf['w'] == 0:
            score_val -= 2; reasons.append(f'{m["home"]}连败{hf["l"]}场!')

    # 核心球员差距
    if home_prof and away_prof:
        h_star = len([p for p in home_prof['key_players'] if '超级' in p or '核心' in p or '大师' in p or '爆点' in p or '新星' in p])
        a_star = len([p for p in away_prof['key_players'] if '超级' in p or '核心' in p or '大师' in p or '爆点' in p or '新星' in p])
        star_diff = h_star - a_star
        if star_diff >= 2:
            score_val += 2; reasons.append(f'球星差{star_diff}(核心级)')
        elif star_diff >= 1:
            score_val += 1; reasons.append(f'球星差{star_diff}')

    # 模型置信度
    if pred['conf'] >= 0.55:
        score_val += 1; reasons.append('高置信')
    elif pred['conf'] < 0.40:
        score_val -= 1; reasons.append('低置信')

    # SPF低赔率无价值
    if oh < 1.30:
        score_val -= 1; reasons.append('SPF低赔走让球')

    if score_val >= 8: tier = 'A'
    elif score_val >= 5: tier = 'B'
    elif score_val >= 2: tier = 'C'
    else: tier = 'D'

    # ===== 推荐 =====
    p(f'  {"─"*80}')
    advice = []
    wc_rq_override = False

    # 让球方向判断: 综合排名差+打法+动机
    rq_should_H = False  # 是否应该推让胜
    if hc:
        try:
            hc_val = float(hc)
            if hc_val < 0:  # 主让球
                # 条件: 主队排名远高于客队 + (进攻碾压防守 或 WC动机)
                if rank_diff and rank_diff >= 15 and home_prof and away_prof:
                    if home_prof['attack'] - away_prof['defense'] >= 1:
                        rq_should_H = True
                # 或者: WC碾压非WC + 排名差>=10
                if home_wc and not away_wc and rank_diff and rank_diff >= 10:
                    rq_should_H = True
        except:
            pass

    if rq_should_H and rq_dir != 'H':
        wc_rq_override = True
        override_odds = m['rqh']
        advice.append(f'让{hc}让胜({override_odds:.2f}) ← 综合实力覆盖模型!')
        advice.append(f'理由: 排名差{rank_diff}+进攻{home_prof["attack"]}vs防守{away_prof["defense"]}+WC动机')
    elif rq_should_H and rq_dir == 'H':
        advice.append(f'让{hc}让胜({m["rqh"]:.2f}) ← 模型+实力同向')
    elif home_wc and not away_wc and hc:
        # WC碾压但排名差不够大, 仍倾向让胜
        try:
            hc_val = float(hc)
            if hc_val < 0 and rq_dir != 'H':
                wc_rq_override = True
                advice.append(f'让{hc}让胜({m["rqh"]:.2f}) ← WC碾压覆盖(谨慎)')
            elif hc_val < 0 and rq_dir == 'H':
                advice.append(f'让{hc}让胜({m["rqh"]:.2f}) ← WC碾压+模型同向')
        except:
            advice.append(f'SPF主胜({oh:.2f})')
    elif pred['pred'] == 'H':
        advice.append(f'SPF主胜({oh:.2f})')
    elif pred['pred'] == 'A':
        advice.append(f'SPF客胜({oa:.2f})')
    else:
        advice.append(f'SPF平局({od:.2f})')

    if picks:
        advice.append(f'比分{picks[0][0]}({picks[0][1]:.1f})')

    p(f'  >> {" / ".join(advice)}')
    p(f'  档位: {tier} (评分{score_val} {" ".join(reasons)})')
    if wc_rq_override:
        p(f'  ⚠ 综合实力覆盖模型让球方向! 模型判{rq_cn} → 实力分析改推让胜')

    results.append({
        'm': m, 'pred': pred, 'rq_pred': rq_pred, 'picks': picks,
        'tier': tier, 'score_val': score_val, 'reasons': reasons,
        'rq_cn': rq_cn, 'rq_dir': rq_dir, 'hc': hc,
        'home_wc': home_wc, 'away_wc': away_wc,
        'home_rank': home_rank, 'away_rank': away_rank, 'rank_diff': rank_diff,
        'wc_rq_override': wc_rq_override, 'rq_should_H': rq_should_H,
        'home_prof': home_prof, 'away_prof': away_prof,
        'h2h': h2h,
    })

# ===== 最终推荐 =====
p('')
p(f'{"="*90}')
p(f'  最终推荐 — 综合实力分析')
p(f'  核心逻辑: FIFA排名差距 + 历史交锋 + 打法相克 + 核心球员 + 世界杯动机')
p(f'  5/31验证: 排名差≥20的WC队 vs 非WC队 = 4/4大比分碾压')
p(f'{"="*90}')

for tier_name, tier_label in [('A','A档(重点)'), ('B','B档(小注)'), ('C','C档(观望)'), ('D','D档(避让)')]:
    tier_matches = [r for r in results if r.get('tier') == tier_name]
    if not tier_matches: continue

    p('')
    p(f'  【{tier_label}】')
    for r in tier_matches:
        m = r['m']
        pred = r['pred']

        rank_info = ''
        if r['home_rank'] and r['away_rank']:
            rank_info = f' [#{r["home_rank"]} vs #{r["away_rank"]}]'

        p(f'')
        p(f'  {m["num_str"]} {m["home"]}{"★" if r["home_wc"] else ""} vs {m["away"]}{"★" if r["away_wc"] else ""}{rank_info}')
        p(f'  SPF: {pred_cn}({pred["conf"]*100:.0f}%) 赔率{m["oh"]:.2f}/{m["od"]:.2f}/{m["oa"]:.2f}')

        if r['hc']:
            if r.get('wc_rq_override'):
                p(f'  让球: 让{r["hc"]} 让胜({m["rqh"]:.2f}) ← 实力覆盖! (模型原判{r["rq_cn"]})')
            elif r['rq_cn']:
                rq_conf = r['rq_pred']['conf'] if r['rq_pred'] else 0
                p(f'  让球: 让{r["hc"]} {r["rq_cn"]}({rq_conf*100:.0f}%)')

        # 打法摘要
        if r['home_prof'] and r['away_prof']:
            p(f'  打法: {r["home_prof"]["style"]}(攻{r["home_prof"]["attack"]}防{r["home_prof"]["defense"]}) vs {r["away_prof"]["style"]}(攻{r["away_prof"]["attack"]}防{r["away_prof"]["defense"]})')

        # H2H摘要
        h2h = r.get('h2h')
        if h2h and h2h['total'] > 0:
            p(f'  交锋: {h2h["total"]}场 {m["home"]}胜{h2h["home_wins"]} 平{h2h["draws"]} {m["away"]}胜{h2h["away_wins"]} (场均{h2h["avg_home_goals"]:.1f}:{h2h["avg_away_goals"]:.1f})')

        score_str = ' / '.join(f'{s}({o:.1f})' for s, o in r['picks'][:3])
        p(f'  比分: {score_str}')
        p(f'  评分: {r["score_val"]} {" ".join(r["reasons"])}')

# 串关
p('')
p(f'  {"─"*80}')
p(f'  串关建议:')
p(f'')

# 实力碾压场次的让球
crush_matches = [r for r in results if r.get('rq_should_H') or (r.get('wc_rq_override') and r['hc'])]
if len(crush_matches) >= 2:
    p(f'  实力碾压让球2串1:')
    for i in range(min(2, len(crush_matches))):
        for j in range(i+1, min(3, len(crush_matches))):
            r1, r2 = crush_matches[i], crush_matches[j]
            m1, m2 = r1['m'], r2['m']
            o1, o2 = m1['rqh'], m2['rqh']
            combo = o1 * o2
            override_note = ' (覆盖模型)' if r1.get('wc_rq_override') or r2.get('wc_rq_override') else ''
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
p('=' * 90)

report = '\n'.join(lines)
print(report)
