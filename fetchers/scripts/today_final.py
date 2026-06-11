"""
体彩推荐 — 完整推理版 v2
核心认知(5/31+6/1验证):
  足球是团队游戏 — 排名差距=体系差距, 不因球星缺阵改变
  友谊赛球星大面积轮换(6/1验证: Haaland/Ødegaard/Çalhanoğlu都没上)
  球星只影响比分大小(赢几个), 不影响胜负方向(谁赢)
  排名碾压+WC动机 → 10/10全对(5/31:6/6, 6/1:4/4)

推理流程:
  1. FIFA排名差距 → 体系差距(决定胜负方向)
  2. 历史交锋H2H → 过往战绩
  3. 打法相克 → 比分形式
  4. 团队深度 → 板凳vs首发(友谊赛关键)
  5. 核心球员 → 只影响转化率(赢2球还是3球)
  6. 位置冲突/团队氛围 → 球星多≠更强
  7. 国家队近期状态 → 士气信心
  8. 世界杯动机 → 全队认真度(放大体系差距)
  9. 赔率模型 → 市场定价
  10. 综合推理 → 逐步推出结论
"""
import sys, io, requests, json
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import urllib3
urllib3.disable_warnings()

API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
API_URL = 'https://apiv3.apifootball.com'

# ===== 拉取体彩数据 =====
sp_session = requests.Session()
sp_session.trust_env = False
sp_session.verify = False
sp_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.sporttery.cn/',
})

r = sp_session.get('https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry',
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

# ===== 数据层 =====

# 1. FIFA排名(覆盖所有常见国际赛球队)
fifa_ranking = {
    # WC2026全部48队 + 其他国家队 (数据源: football_v2.db fifa_rankings 2026-05-20)
    # 南美
    '阿根廷':4, '巴西':28, '哥伦比亚':17, '厄瓜多尔':20, '巴拉圭':53,
    '乌拉圭':29, '智利':104, '委内瑞拉':63,
    # 欧洲
    '德国':13, '法国':2, '西班牙':1, '英格兰':7, '荷兰':15, '葡萄牙':11,
    '意大利':30, '比利时':24, '瑞士':21, '奥地利':22, '土耳其':9,
    '丹麦':42, '瑞典':44, '波兰':80, '捷克':54, '塞尔维亚':66,
    '克罗地亚':23, '苏格兰':115, '威尔士':72, '乌克兰':49, '挪威':25,
    '斯洛伐克':71, '匈牙利':87, '罗马尼亚':79, '保加利亚':246,
    '黑山':263, '北马其顿':92, '格鲁吉亚':197, '冰岛':203, '芬兰':234,
    '科索沃':35, '阿尔巴尼亚':99, '波黑':193, '斯洛文尼亚':46,
    '爱尔兰':95, '以色列':111, '希腊':59,
    # 亚洲
    '日本':8, '韩国':27, '伊朗':14, '沙特':67, '澳大利亚':33,
    '乌兹别克斯坦':16, '中国':236, '伊拉克':41, '约旦':36, '卡塔尔':201,
    # 非洲
    '摩洛哥':5, '塞内加尔':3, '尼日利亚':6, '喀麦隆':40,
    '加纳':199, '突尼斯':32, '阿尔及利亚':10, '埃及':18,
    '科特迪瓦':19, '刚果(金)':12, '佛得角':47, '南非':56,
    # 中北美
    '美国':85, '加拿大':38, '墨西哥':31, '哥斯达黎加':64,
    '巴拿马':26, '牙买加':45, '洪都拉斯':65, '海地':60, '库拉索':93,
    # 大洋洲
    '新西兰':196,
}

def get_fifa_rank(name):
    return fifa_ranking.get(name)

# 2. 世界杯参赛状态
wc_teams_set = {
    # WC2026全部48个参赛队
    '土耳其','奥地利','加拿大','挪威','瑞典','哥伦比亚','哥斯达黎加',
    '巴西','巴拿马','瑞士','德国','日本','美国','塞内加尔','墨西哥',
    '阿根廷','厄瓜多尔','巴拉圭','乌拉圭','智利','委内瑞拉',
    '法国','西班牙','英格兰','荷兰','葡萄牙','意大利','比利时',
    '丹麦','波兰','捷克','塞尔维亚','克罗地亚','苏格兰','威尔士',
    '乌克兰','斯洛伐克','匈牙利','罗马尼亚',
    '韩国','伊朗','沙特','澳大利亚','伊拉克','约旦','乌兹别克斯坦','卡塔尔',
    '摩洛哥','尼日利亚','喀麦隆','加纳','突尼斯','阿尔及利亚',
    '埃及','科特迪瓦','刚果(金)','佛得角','南非',
    '牙买加','洪都拉斯','海地','库拉索',
    '波黑','新西兰',
}
wc_non_teams = {'保加利亚','黑山','北马其顿','冰岛','芬兰','科索沃','中国','格鲁吉亚'}

def is_wc_team(name):
    if name in wc_non_teams: return False
    return name in wc_teams_set

# 3. 球队体系画像
# depth: 板凳深度(1-10) — 替补在五大联赛的级别, 友谊赛关键指标
# position_conflict: 核心球员位置是否重叠(如两个10号位)
# team_vibe: 团队氛围('稳定'/'新老交替'/'矛盾')
team_profile = {
    # ===== 南美 =====
    '阿根廷': {'style':'控球+压迫','attack':9,'defense':7,'depth':8,
               'key_players':['梅西(超级)','迪马利亚(老将)','劳塔罗(锋线)'],
               'formation':'4-3-3','position_conflict':False,'team_vibe':'稳定'},
    '巴西': {'style':'技术+控球','attack':9,'defense':6,'depth':8,
             'key_players':['维尼修斯(超级)','罗德里戈(核心)','帕凯塔(中场)'],
             'formation':'4-2-3-1','position_conflict':False,'team_vibe':'新老交替'},
    '哥伦比亚': {'style':'技术流+边路','attack':8,'defense':6,'depth':6,
               'key_players':['J罗(组织核心)','路易斯·迪亚斯(边路爆点)','夸德拉多(边路)'],
               'formation':'4-2-3-1','position_conflict':True,
               'position_conflict_note':'J罗和Carrascal同属10号位, 功能重叠',
               'team_vibe':'新老交替'},
    '乌拉圭': {'style':'身体+技术','attack':7,'defense':7,'depth':6,
               'key_players':['努涅斯(锋线)','巴尔韦德(中场核心)','阿劳霍(后卫)'],
               'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '厄瓜多尔': {'style':'身体+速度','attack':6,'defense':6,'depth':4,
               'key_players':['瓦伦西亚(锋线)','凯塞多(中场)'],
               'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '巴拉圭': {'style':'防守反击','attack':5,'defense':6,'depth':4,
               'key_players':['阿尔米隆(边路)','罗梅罗(中场)'],
               'formation':'4-4-2','position_conflict':False,'team_vibe':'稳定'},
    '智利': {'style':'技术+压迫','attack':6,'defense':5,'depth':4,
             'key_players':['巴尔加斯(锋线)','比达尔(老将)'],
             'formation':'4-3-3','position_conflict':False,'team_vibe':'新老交替'},
    '委内瑞拉': {'style':'防守反击','attack':5,'defense':6,'depth':3,
               'key_players':['龙东(锋线)'],
               'formation':'5-4-1','position_conflict':False,'team_vibe':'稳定'},
    # ===== 欧洲 =====
    '德国': {'style':'控球压迫','attack':8,'defense':7,'depth':8,
             'key_players':['穆西亚拉(新星)','维尔茨(新星)','基米希(核心)'],
             'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '法国': {'style':'速度+技术','attack':9,'defense':7,'depth':9,
             'key_players':['姆巴佩(超级)','格列兹曼(核心)','楚阿梅尼(中场)'],
             'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '西班牙': {'style':'控球+传球','attack':8,'defense':7,'depth':8,
               'key_players':['佩德里(核心)','亚马尔(新星)','罗德里(中场)'],
               'formation':'4-3-3','position_conflict':False,'team_vibe':'稳定'},
    '英格兰': {'style':'速度+技术','attack':8,'defense':7,'depth':9,
               'key_players':['凯恩(超级)','贝林厄姆(核心)','福登(新星)'],
               'formation':'4-2-3-1','position_conflict':True,
               'position_conflict_note':'贝林厄姆和福登都偏10号位, 位置需协调',
               'team_vibe':'稳定'},
    '荷兰': {'style':'控球+边路','attack':8,'defense':7,'depth':7,
             'key_players':['范戴克(后卫核心)','德容(中场)','加克波(锋线)'],
             'formation':'3-4-2-1','position_conflict':False,'team_vibe':'稳定'},
    '葡萄牙': {'style':'技术+边路','attack':8,'defense':7,'depth':7,
               'key_players':['B费(中场核心)','莱奥(边路爆点)','鲁本·迪亚斯(后卫)'],
               'formation':'4-3-3','position_conflict':False,'team_vibe':'新老交替'},
    '意大利': {'style':'组织防守','attack':7,'defense':8,'depth':7,
               'key_players':['巴雷拉(中场)','基耶萨(边路)','多纳鲁马(门将)'],
               'formation':'3-5-2','position_conflict':False,'team_vibe':'新老交替'},
    '比利时': {'style':'技术+速度','attack':7,'defense':6,'depth':6,
               'key_players':['德布劳内(超级)','卢卡库(锋线)','多库(边路)'],
               'formation':'4-2-3-1','position_conflict':False,
               'team_vibe':'新老交替',
               'depth_note':'德布劳内等老将友谊赛可能轮换, 但替补如特罗萨德(阿森纳)仍为五大联赛主力'},
    '瑞士': {'style':'组织防守','attack':6,'defense':7,'depth':6,
             'key_players':['扎卡(中场核心)','沙奇里(老将)','阿坎吉(后卫)'],
             'formation':'3-4-2-1','position_conflict':False,'team_vibe':'稳定'},
    '奥地利': {'style':'高位压迫','attack':7,'defense':7,'depth':6,
               'key_players':['萨比策(中场核心)','阿瑙托维奇(锋线)','莱默尔(中场)'],
               'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '土耳其': {'style':'控球+边路','attack':7,'defense':5,'depth':7,
               'key_players':['恰尔汗奥卢(中场核心)','居勒尔(皇马新星)','伊尔马兹(锋线)'],
               'formation':'4-2-3-1','position_conflict':True,
               'position_conflict_note':'恰尔汗奥卢和Kökçü同属10号位, 都上可能挤占空间',
               'team_vibe':'稳定'},
    '丹麦': {'style':'控球+组织','attack':6,'defense':7,'depth':6,
             'key_players':['埃里克森(核心)','霍伊伦德(锋线)','克里斯滕森(后卫)'],
             'formation':'3-4-2-1','position_conflict':False,'team_vibe':'稳定'},
    '瑞典': {'style':'身体对抗','attack':5,'defense':6,'depth':4,
             'key_players':['伊萨克(锋线)','福斯贝里(中场)'],
             'formation':'4-4-2','position_conflict':False,'team_vibe':'稳定'},
    '波兰': {'style':'直接进攻','attack':6,'defense':5,'depth':5,
             'key_players':['莱万(超级射手)','齐林斯基(中场)'],
             'formation':'4-2-3-1','position_conflict':False,'team_vibe':'新老交替'},
    '捷克': {'style':'组织防守','attack':6,'defense':6,'depth':5,
             'key_players':['希克(锋线)','绍切克(中场)'],
             'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '塞尔维亚': {'style':'技术+身体','attack':7,'defense':5,'depth':5,
               'key_players':['米特罗维奇(锋线)','弗拉霍维奇(锋线)','塔迪奇(核心)'],
               'formation':'3-4-2-1','position_conflict':True,
               'position_conflict_note':'米特罗维奇和弗拉霍维奇同属9号位, 无法共存',
               'team_vibe':'稳定'},
    '克罗地亚': {'style':'控球+组织','attack':6,'defense':7,'depth':5,
               'key_players':['莫德里奇(大师)','科瓦契奇(中场)','格瓦尔迪奥尔(后卫)'],
               'formation':'4-3-3','position_conflict':False,
               'team_vibe':'新老交替',
               'depth_note':'莫德里奇(39岁)友谊赛大概率不上, 但克拉马里奇/帕萨利奇替补仍有经验'},
    '苏格兰': {'style':'身体+压迫','attack':5,'defense':6,'depth':4,
               'key_players':['罗伯逊(边路)','麦克托米奈(中场)'],
               'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '威尔士': {'style':'速度+反击','attack':5,'defense':6,'depth':4,
               'key_players':['贝尔(退役)','拉姆塞(老将)','丹尼尔·詹姆斯(边路)'],
               'formation':'4-3-3','position_conflict':False,
               'team_vibe':'新老交替',
               'depth_note':'后贝尔时代缺少超级球星, 但布伦南·约翰逊(热刺)领衔新一代'},
    '乌克兰': {'style':'技术+反击','attack':6,'defense':6,'depth':5,
               'key_players':['津琴科(中场)','穆德里克(边路)','多夫比克(锋线)'],
               'formation':'4-3-3','position_conflict':False,'team_vibe':'稳定'},
    '挪威': {'style':'直接进攻','attack':8,'defense':5,'depth':6,
             'key_players':['哈兰德(超级射手)','厄德高(中场大师)','瑟洛特(锋线)'],
             'formation':'4-3-3','position_conflict':False,
             'depth_note':'Sørloth(比利亚雷亚尔),Bobb(曼城),Nusa(热刺)替补仍为五大联赛主力',
             'team_vibe':'稳定'},
    '斯洛伐克': {'style':'防守反击','attack':5,'defense':6,'depth':4,
               'key_players':['什克里尼亚尔(后卫)','洛博特卡(中场)'],
               'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '匈牙利': {'style':'组织防守','attack':6,'defense':6,'depth':4,
               'key_players':['索博斯洛伊(核心)','奥尔班(后卫)'],
               'formation':'3-4-2-1','position_conflict':False,'team_vibe':'稳定'},
    '罗马尼亚': {'style':'防守反击','attack':5,'defense':6,'depth':4,
               'key_players':['斯坦丘(中场核心)','德拉古辛(后卫)'],
               'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '格鲁吉亚': {'style':'技术+反击','attack':6,'defense':5,'depth':3,
               'key_players':['克瓦拉茨赫利亚(边路爆点)','米考塔泽(锋线)'],
               'formation':'4-3-3','position_conflict':False,'team_vibe':'稳定'},
    '保加利亚': {'style':'防守反击','attack':3,'defense':5,'depth':2,
               'key_players':['基里洛夫(中场)'],
               'formation':'4-5-1','position_conflict':False,'team_vibe':'稳定'},
    '黑山': {'style':'防守反击','attack':4,'defense':5,'depth':2,
             'key_players':['约韦蒂奇(老将锋线)','萨维奇(后卫)'],
             'formation':'4-5-1','position_conflict':False,'team_vibe':'稳定'},
    '北马其顿': {'style':'防守反击','attack':4,'defense':6,'depth':3,
               'key_players':['埃尔马斯(中场)'],
               'formation':'5-4-1','position_conflict':False,'team_vibe':'稳定'},
    '冰岛': {'style':'身体对抗','attack':3,'defense':5,'depth':2,
             'key_players':['西于尔兹松(老将)'],
             'formation':'4-5-1','position_conflict':False,'team_vibe':'稳定'},
    '芬兰': {'style':'防守反击','attack':3,'defense':5,'depth':2,
             'key_players':['普基(老将锋线)'],
             'formation':'5-3-2','position_conflict':False,'team_vibe':'稳定'},
    '科索沃': {'style':'防守反击','attack':4,'defense':5,'depth':3,
               'key_players':['拉希察(中场)'],
               'formation':'4-5-1','position_conflict':False,'team_vibe':'稳定'},
    '波黑': {'style':'防守反击','attack':4,'defense':5,'depth':3,
             'key_players':['皮亚尼奇(老将中场)','哲科(老将锋线)'],
             'formation':'4-2-3-1','position_conflict':False,'team_vibe':'新老交替'},
    '阿尔巴尼亚': {'style':'防守反击','attack':4,'defense':6,'depth':3,
               'key_players':['布罗亚(锋线)'],
               'formation':'4-5-1','position_conflict':False,'team_vibe':'稳定'},
    '斯洛文尼亚': {'style':'防守反击','attack':5,'defense':7,'depth':4,
               'key_players':['奥布拉克(门神)','伊利契奇(老将)'],
               'formation':'4-4-2','position_conflict':False,'team_vibe':'稳定'},
    '爱尔兰': {'style':'身体+压迫','attack':4,'defense':6,'depth':3,
               'key_players':['弗格森(锋线新星)'],
               'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '希腊': {'style':'组织防守','attack':5,'defense':7,'depth':4,
             'key_players':['巴卡塞塔斯(中场)'],
             'formation':'3-4-2-1','position_conflict':False,'team_vibe':'稳定'},
    # ===== 亚洲 =====
    '日本': {'style':'控球+技术','attack':7,'defense':6,'depth':7,
             'key_players':['三笘薰(边路爆点)','久保建英(新星)','远藤航(中场)'],
             'formation':'4-2-3-1','position_conflict':False,
             'depth_note':'替补阵容几乎全五大联赛, 友谊赛轮换影响极小',
             'team_vibe':'稳定'},
    '韩国': {'style':'技术+速度','attack':7,'defense':5,'depth':5,
             'key_players':['孙兴慜(超级)','李刚仁(新星)','黄喜灿(锋线)'],
             'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '伊朗': {'style':'身体+反击','attack':6,'defense':6,'depth':4,
             'key_players':['阿兹蒙(锋线)','塔雷米(锋线)'],
             'formation':'4-2-3-1','position_conflict':True,
             'position_conflict_note':'阿兹蒙和塔雷米都需前场核心地位',
             'team_vibe':'稳定'},
    '沙特': {'style':'控球+技术','attack':5,'defense':6,'depth':4,
             'key_players':['达瓦萨里(中场)'],
             'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '澳大利亚': {'style':'身体+速度','attack':6,'defense':5,'depth':4,
               'key_players':['赫鲁斯蒂奇(中场)'],
               'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '乌兹别克斯坦': {'style':'防守反击','attack':4,'defense':5,'depth':2,
               'key_players':['肖穆罗多夫(锋线)','马沙里波夫(中场)'],
               'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    # ===== 非洲 =====
    '摩洛哥': {'style':'组织防守','attack':6,'defense':8,'depth':6,
               'key_players':['阿什拉夫(边路)','齐耶赫(核心)','布努(门将)'],
               'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '塞内加尔': {'style':'身体+速度','attack':7,'defense':6,'depth':5,
               'key_players':['马内(超级)','库利巴利(后卫)'],
               'formation':'4-3-3','position_conflict':False,'team_vibe':'稳定'},
    '尼日利亚': {'style':'速度+技术','attack':7,'defense':5,'depth':5,
               'key_players':['奥斯梅恩(超级射手)','丘库埃泽(边路)'],
               'formation':'4-3-3','position_conflict':False,'team_vibe':'稳定'},
    '喀麦隆': {'style':'身体+反击','attack':6,'defense':6,'depth':4,
               'key_players':['阿布巴卡尔(锋线)','安古伊萨(中场)'],
               'formation':'4-3-3','position_conflict':False,'team_vibe':'稳定'},
    '加纳': {'style':'速度+技术','attack':6,'defense':5,'depth':5,
             'key_players':['托马斯(中场核心)','库杜斯(新星)'],
             'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '突尼斯': {'style':'防守反击','attack':5,'defense':7,'depth':5,
               'key_players':['斯希里(中场)','哈兹里(锋线)'],
               'formation':'4-3-3','position_conflict':False,'team_vibe':'稳定'},
    '阿尔及利亚': {'style':'技术+反击','attack':6,'defense':5,'depth':4,
               'key_players':['马赫雷斯(核心)','本纳赛尔(中场)'],
               'formation':'4-2-3-1','position_conflict':False,
               'team_vibe':'新老交替'},
    # ===== 中北美 =====
    '美国': {'style':'速度+体能','attack':7,'defense':5,'depth':6,
             'key_players':['普利西奇(核心)','麦肯尼(中场)','雷纳(新星)'],
             'formation':'4-3-3','position_conflict':False,
             'depth_note':'美职联+五大联赛混搭, 替补深度足',
             'team_vibe':'稳定'},
    '加拿大': {'style':'速度+边路','attack':6,'defense':5,'depth':5,
               'key_players':['阿方索·戴维斯(边路爆点)','乔纳森·大卫(锋线)'],
               'formation':'4-4-2','position_conflict':False,'team_vibe':'新老交替'},
    '墨西哥': {'style':'控球+技术','attack':6,'defense':5,'depth':5,
               'key_players':['希门尼斯(锋线)','洛萨诺(边路)'],
               'formation':'4-2-3-1','position_conflict':False,'team_vibe':'新老交替'},
    '哥斯达黎加': {'style':'防守反击','attack':4,'defense':6,'depth':3,
               'key_players':['纳瓦斯(门神)','鲁伊斯(中场)'],
               'formation':'5-4-1','position_conflict':False,'team_vibe':'稳定'},
    '巴拿马': {'style':'防守反击','attack':4,'defense':5,'depth':3,
               'key_players':['托雷斯(中场)'],
               'formation':'5-4-1','position_conflict':False,'team_vibe':'稳定'},
    '牙买加': {'style':'速度+身体','attack':5,'defense':5,'depth':3,
               'key_players':['贝利(边路)'],
               'formation':'4-3-3','position_conflict':False,'team_vibe':'稳定'},
    '洪都拉斯': {'style':'防守反击','attack':4,'defense':5,'depth':2,
               'key_players':['埃斯佩兰(中场)'],
               'formation':'4-5-1','position_conflict':False,'team_vibe':'稳定'},
    # ===== WC2026新增队 =====
    '伊拉克': {'style':'防守反击','attack':5,'defense':6,'depth':3,
              'key_players':['阿里(锋线)'],
              'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '约旦': {'style':'防守反击','attack':4,'defense':6,'depth':2,
             'key_players':['塔马里(中场)'],
             'formation':'4-5-1','position_conflict':False,'team_vibe':'稳定'},
    '卡塔尔': {'style':'控球+技术','attack':4,'defense':5,'depth':3,
              'key_players':['阿里(锋线)','海多斯(中场)'],
              'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '埃及': {'style':'防守反击','attack':6,'defense':7,'depth':4,
             'key_players':['萨拉赫(超级)','埃尔内尼(中场)'],
             'formation':'4-2-3-1','position_conflict':False,'team_vibe':'稳定'},
    '科特迪瓦': {'style':'技术+速度','attack':7,'defense':5,'depth':5,
                'key_players':['佩佩(边路爆点)','凯西(中场)'],
                'formation':'4-3-3','position_conflict':False,'team_vibe':'稳定'},
    '刚果(金)': {'style':'速度+身体','attack':5,'defense':4,'depth':3,
                'key_players':['巴坎布(锋线)'],
                'formation':'4-3-3','position_conflict':False,'team_vibe':'稳定'},
    '佛得角': {'style':'技术+反击','attack':4,'defense':5,'depth':2,
              'key_players':['门德斯(中场)'],
              'formation':'4-4-2','position_conflict':False,'team_vibe':'稳定'},
    '南非': {'style':'身体+反击','attack':4,'defense':5,'depth':2,
             'key_players':['福斯特(锋线)'],
             'formation':'4-4-2','position_conflict':False,'team_vibe':'稳定'},
    '海地': {'style':'防守反击','attack':4,'defense':5,'depth':2,
             'key_players':['邓肯(中场)'],
             'formation':'5-4-1','position_conflict':False,'team_vibe':'稳定'},
    '库拉索': {'style':'防守反击','attack':3,'defense':5,'depth':2,
              'key_players':['马丁纳(中场)'],
              'formation':'5-4-1','position_conflict':False,'team_vibe':'稳定'},
    '新西兰': {'style':'身体对抗','attack':3,'defense':5,'depth':2,
              'key_players':['伍德(锋线)'],
              'formation':'4-5-1','position_conflict':False,'team_vibe':'稳定'},
}

# 4. 模型
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

# ===== 预加载: H2H + 国家队近期战绩 =====
api_session = requests.Session()
api_session.trust_env = False
api_session.verify = False

fifa_data = json.load(open('d:/football_tools/fifa_national_teams.json', 'r', encoding='utf-8'))
fifa_id_map = {t['name_en']: t['id'] for t in fifa_data}

cn_to_en = {
    # 南美
    '阿根廷':'Argentina','巴西':'Brazil','哥伦比亚':'Colombia','厄瓜多尔':'Ecuador',
    '巴拉圭':'Paraguay','乌拉圭':'Uruguay','智利':'Chile','委内瑞拉':'Venezuela',
    # 欧洲
    '德国':'Germany','法国':'France','西班牙':'Spain','英格兰':'England',
    '荷兰':'Netherlands','葡萄牙':'Portugal','意大利':'Italy','比利时':'Belgium',
    '瑞士':'Switzerland','奥地利':'Austria','土耳其':'Turkey',
    '丹麦':'Denmark','瑞典':'Sweden','波兰':'Poland','捷克':'Czech Republic',
    '塞尔维亚':'Serbia','克罗地亚':'Croatia','苏格兰':'Scotland','威尔士':'Wales',
    '乌克兰':'Ukraine','挪威':'Norway','斯洛伐克':'Slovakia','匈牙利':'Hungary',
    '罗马尼亚':'Romania','保加利亚':'Bulgaria','黑山':'Montenegro',
    '北马其顿':'North Macedonia','格鲁吉亚':'Georgia','冰岛':'Iceland',
    '芬兰':'Finland','科索沃':'Kosovo','波黑':'Bosnia and Herzegovina',
    '阿尔巴尼亚':'Albania','斯洛文尼亚':'Slovenia','爱尔兰':'Ireland',
    '以色列':'Israel','希腊':'Greece',
    # 亚洲
    '日本':'Japan','韩国':'South Korea','伊朗':'Iran','沙特':'Saudi Arabia',
    '澳大利亚':'Australia','乌兹别克斯坦':'Uzbekistan','中国':'China',
    '伊拉克':'Iraq','约旦':'Jordan','卡塔尔':'Qatar',
    # 非洲
    '摩洛哥':'Morocco','塞内加尔':'Senegal','尼日利亚':'Nigeria','喀麦隆':'Cameroon',
    '加纳':'Ghana','突尼斯':'Tunisia','阿尔及利亚':'Algeria',
    '埃及':'Egypt','科特迪瓦':'Ivory Coast','刚果(金)':'DR Congo',
    '佛得角':'Cape Verde','南非':'South Africa',
    # 中北美
    '美国':'USA','加拿大':'Canada','墨西哥':'Mexico','哥斯达黎加':'Costa Rica',
    '巴拿马':'Panama','牙买加':'Jamaica','洪都拉斯':'Honduras',
    '海地':'Haiti','库拉索':'Curacao',
    # 大洋洲
    '新西兰':'New Zealand',
}

team_form = {}
for cn_name, en_name in cn_to_en.items():
    tid = fifa_id_map.get(en_name)
    if not tid: continue
    try:
        r2 = api_session.get(f'{API_URL}/', params={
            'action': 'get_events',
            'team_id': str(tid),
            'from': '2025-01-01',
            'to': '2026-06-01',
            'APIkey': API_KEY,
        }, timeout=15)
        d2 = r2.json()
        if isinstance(d2, list):
            intl = [m2 for m2 in d2 if any(kw in (m2.get('league_name','')+m2.get('country_name',''))
                    for kw in ['International','Friendly','World','Euro','Nations'])]
            finished = [m2 for m2 in intl if m2.get('match_status') == 'Finished']
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
            team_form[cn_name] = {'w':w,'d':d,'l':l,'results':results}
    except:
        team_form[cn_name] = {'w':0,'d':0,'l':0,'results':[]}

# H2H
h2h_data = {}
for m_temp in matches:
    home_cn = m_temp['home']
    away_cn = m_temp['away']
    home_en = cn_to_en.get(home_cn)
    away_en = cn_to_en.get(away_cn)
    home_id = fifa_id_map.get(home_en) if home_en else None
    away_id = fifa_id_map.get(away_en) if away_en else None
    if not home_id or not away_id: continue
    key = f'{home_cn}_vs_{away_cn}'
    try:
        r2 = api_session.get(f'{API_URL}/', params={
            'action': 'get_H2H',
            'firstTeamId': str(home_id),
            'secondTeamId': str(away_id),
            'APIkey': API_KEY,
        }, timeout=15)
        h2h_raw = r2.json()
        vs_list = h2h_raw.get('firstTeam_VS_secondTeam', []) if isinstance(h2h_raw, dict) else []
        finished = [m2 for m2 in vs_list if m2.get('match_status') == 'Finished']
        home_wins = draws = away_wins = 0
        home_goals = away_goals = 0
        recent = []
        for m2 in finished:
            hs = m2.get('match_hometeam_score','0')
            as2 = m2.get('match_awayteam_score','0')
            try: h=int(hs); a=int(as2)
            except: continue
            h_id = m2.get('match_hometeam_id','')
            is_home_pov = (str(home_id) == h_id)
            if is_home_pov:
                if h>a: home_wins+=1
                elif h==a: draws+=1
                else: away_wins+=1
                home_goals+=h; away_goals+=a
            else:
                if h>a: away_wins+=1
                elif h==a: draws+=1
                else: home_wins+=1
                home_goals+=a; away_goals+=h
            recent.append({'date':m2.get('match_date','?'),'home':m2.get('match_hometeam_name',''),'away':m2.get('match_awayteam_name',''),'score':f'{h}:{a}','league':m2.get('league_name','')})
        total = home_wins+draws+away_wins
        h2h_data[key] = {
            'total':total,'home_wins':home_wins,'draws':draws,'away_wins':away_wins,
            'avg_home_goals':home_goals/total if total else 0,'avg_away_goals':away_goals/total if total else 0,
            'recent':recent[-5:],
        }
    except:
        pass

# ===== 输出 =====
lines = []
def p(s=''): lines.append(s)

from datetime import datetime
today_str = datetime.now().strftime('%m/%d')

p('=' * 90)
p(f'  {today_str} 体彩推荐 — 完整推理版 v2.2')
p('  核心认知: 足球是团队游戏 — 排名差距=体系差距, 不因球星缺阵改变')
p('  WC碾压非WC: 5/31+6/1=10/10全对 | WC vs WC: 偏斜<20%→平局')
p('  联赛均衡赔率→平局(5/31: 3/3) | 国际赛主场优势60%+')
p('  推理流程: 排名→交锋→打法→深度→球星→氛围→状态→动机→主场→赔率→结论')
p('=' * 90)

all_results = []

for m in matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    hc = m.get('hc', '')
    has_spf = oh and od and oa
    has_rq = m['rqh'] and m['rqd'] and m['rqa']
    has_rq_only = (not has_spf) and has_rq

    pred = predict(oh, od, oa, m['league']) if has_spf else None
    rq_pred = predict(m['rqh'], m['rqd'], m['rqa'], m['league']) if has_rq else None

    home_wc = is_wc_team(m['home'])
    away_wc = is_wc_team(m['away'])
    home_rank = get_fifa_rank(m['home'])
    away_rank = get_fifa_rank(m['away'])
    rank_diff = (away_rank - home_rank) if (home_rank and away_rank) else None
    home_prof = team_profile.get(m['home'])
    away_prof = team_profile.get(m['away'])
    is_intl = m['league'] in ['国际赛']
    hf = team_form.get(m['home'])
    af = team_form.get(m['away'])
    h2h_key = f'{m["home"]}_vs_{m["away"]}'
    h2h = h2h_data.get(h2h_key)

    # 让球
    rq_dir = rq_pred['pred'] if rq_pred else None
    rq_cn = {'H':'让胜','D':'让平','A':'让负'}[rq_dir] if rq_dir else ''
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

    # 比分选择 — 基于赔率模型(初步), 后面Step10后会根据combined_pred调整
    scores = m.get('scores', [])
    home_scores = [(s, o) for s, o in scores if score_dir(s) == 'H']
    draw_scores = [(s, o) for s, o in scores if score_dir(s) == 'D']
    away_scores = [(s, o) for s, o in scores if score_dir(s) == 'A']

    # 先用赔率模型做初步选择, 后面会覆盖
    initial_pred_dir = pred['pred'] if pred else None
    picks = []
    if pred:
        if pred['pred'] == 'H' and home_scores: picks.append(home_scores[0])
        elif pred['pred'] == 'D' and draw_scores: picks.append(draw_scores[0])
        elif pred['pred'] == 'A' and away_scores: picks.append(away_scores[0])
        probs = [('H', pred['hp'], home_scores), ('D', pred['dp'], draw_scores), ('A', pred['ap'], away_scores)]
        probs_sorted = sorted(probs, key=lambda x: -x[1])
        for d2, prob, sc_list in probs_sorted:
            if d2 != pred['pred'] and sc_list:
                picks.append(sc_list[0])
                break
        if pred['pred'] == 'H' and len(home_scores) > 1: picks.append(home_scores[1])
        elif pred['pred'] == 'D' and len(draw_scores) > 1: picks.append(draw_scores[1])
        elif pred['pred'] == 'A' and len(away_scores) > 1: picks.append(away_scores[1])
    elif has_rq_only:
        if home_scores: picks.append(home_scores[0])
        if len(home_scores) > 1: picks.append(home_scores[1])
        elif draw_scores: picks.append(draw_scores[0])

    p('')
    p(f'  ═══════════════════════════════════════════════════════════════════════════════')
    p(f'  {m["num_str"]} {m["home"]}{"★" if home_wc else ""} vs {m["away"]}{"★" if away_wc else ""} [{m["league"]}] {m["time"]}')
    p(f'  ═══════════════════════════════════════════════════════════════════════════════')

    # ===== 逐步推理 =====
    reasoning = []

    # Step 1: FIFA排名
    p(f'  Step1 [FIFA排名]')
    if rank_diff is not None:
        p(f'    {m["home"]}#{home_rank} vs {m["away"]}#{away_rank} → 差距{rank_diff}位')
        if rank_diff >= 30:
            p(f'    → 主队排名碾压级(差距≥30), 体系悬殊')
            reasoning.append('排名碾压')
        elif rank_diff >= 15:
            p(f'    → 主队排名明显优(差距≥15), 体系有差距')
            reasoning.append('排名明显优')
        elif rank_diff >= 5:
            p(f'    → 主队排名略优(差距5-15), 有一定优势')
            reasoning.append('排名略优')
        elif rank_diff > -5:
            p(f'    → 排名接近, 实力相当')
        elif rank_diff > -15:
            p(f'    → 客队排名略优(差距5-15)')
            reasoning.append('排名客优')
        elif rank_diff > -30:
            p(f'    → 客队排名明显优(差距≥15), 体系有差距')
            reasoning.append('排名客优明显')
        else:
            p(f'    → 客队排名碾压级(差距≥30), 体系悬殊')
            reasoning.append('排名客队碾压')
    else:
        p(f'    非国际排名球队')

    # Step 2: H2H
    p(f'  Step2 [历史交锋]')
    if h2h and h2h['total'] > 0:
        win_rate = h2h['home_wins'] / h2h['total'] * 100
        p(f'    {h2h["total"]}场 → {m["home"]}胜{h2h["home_wins"]} 平{h2h["draws"]} {m["away"]}胜{h2h["away_wins"]} 场均{h2h["avg_home_goals"]:.1f}:{h2h["avg_away_goals"]:.1f}')
        if win_rate >= 70:
            p(f'    → {m["home"]}历史碾压({win_rate:.0f}%胜率)')
            reasoning.append('H2H碾压')
        elif win_rate >= 55:
            p(f'    → {m["home"]}历史占优({win_rate:.0f}%胜率)')
            reasoning.append('H2H占优')
        elif win_rate < 30:
            p(f'    → {m["away"]}历史碾压({100-win_rate:.0f}%胜率)')
        else:
            p(f'    → 历史势均力敌')
        for r2 in h2h['recent'][-3:]:
            p(f'      {r2["date"]} {r2["home"]} {r2["score"]} {r2["away"]}')
    else:
        p(f'    无交锋记录')

    # Step 3: 打法相克
    p(f'  Step3 [打法相克]')
    if home_prof and away_prof:
        p(f'    {m["home"]}{home_prof["style"]}(攻{home_prof["attack"]}防{home_prof["defense"]}) vs {m["away"]}{away_prof["style"]}(攻{away_prof["attack"]}防{away_prof["defense"]})')
        atk_diff = home_prof['attack'] - away_prof['defense']
        def_diff = home_prof['defense'] - away_prof['attack']
        p(f'    攻防对冲: 主攻vs客防={atk_diff:+d} 主防vs客攻={def_diff:+d}')

        # 打法结论
        clash = ''
        h_style = home_prof['style']
        a_style = away_prof['style']
        if '压迫' in h_style and '反击' in a_style:
            clash = '高位压迫vs防反 → 压迫方抢断快攻, 防反方出球困难 → 压迫方优势'
        elif '控球' in h_style and '反击' in a_style:
            clash = '控球vs防反 → 控球方主导但防反有偷袭'
        elif '速度' in h_style and '防守' in a_style:
            clash = '速度vs防守 → 速度冲击防线, 防守方压力大'
        elif '技术' in h_style and '防守' in a_style:
            clash = '技术vs防守 → 技术流控球主导, 防守方纪律性是关键'
        elif '直接' in h_style and '身体' in a_style:
            clash = '直接进攻vs身体对抗 → 对攻战, 看谁火力猛'
        elif '控球' in h_style and '身体' in a_style:
            clash = '控球vs身体 → 技术vs力量, 看谁能掌控节奏'
        elif '速度' in h_style and '反击' in a_style:
            clash = '速度vs防反 → 双方都靠反击, 进球可能不多'
        else:
            clash = '打法接近, 无明显相克'
        p(f'    {clash}')

        if atk_diff >= 3:
            p(f'    → 进攻碾压防守(atk_diff={atk_diff}), 大比分可能')
            reasoning.append('攻防碾压')
        elif atk_diff >= 1:
            p(f'    → 进攻略优于防守')
    else:
        p(f'    数据不足')

    # Step 4: 团队深度(友谊赛关键!)
    p(f'  Step4 [团队深度]')
    if home_prof and away_prof:
        h_depth = home_prof.get('depth', 5)
        a_depth = away_prof.get('depth', 5)
        depth_diff = h_depth - a_depth
        p(f'    {m["home"]}板凳深度:{h_depth} vs {m["away"]}板凳深度:{a_depth} (差{depth_diff:+d})')
        if depth_diff >= 3:
            p(f'    → 深度碾压! {m["home"]}替补仍是五大联赛级别, 友谊赛轮换影响小')
            reasoning.append('深度碾压')
        elif depth_diff >= 1:
            p(f'    → 深度略优, 轮换后仍有竞争力')
        if home_prof.get('depth_note'):
            p(f'    注: {home_prof["depth_note"]}')
        if away_prof.get('depth_note'):
            p(f'    注: {away_prof["depth_note"]}')
    else:
        p(f'    数据不足')

    # Step 5: 核心球员(只影响转化率, 不决定胜负方向)
    p(f'  Step5 [核心球员] ← 只影响赢几个球, 不影响谁赢')
    if home_prof and away_prof:
        h_stars = [p2 for p2 in home_prof['key_players'] if any(k in p2 for k in ['超级','核心','爆点','新星','大师'])]
        a_stars = [p2 for p2 in away_prof['key_players'] if any(k in p2 for k in ['超级','核心','爆点','新星','大师'])]
        p(f'    {m["home"]}: {", ".join(h_stars) if h_stars else "无顶级球星"}')
        p(f'    {m["away"]}: {", ".join(a_stars) if a_stars else "无顶级球星"}')
        if len(h_stars) >= 2 and len(a_stars) == 0:
            p(f'    → 球星数量占优, 但友谊赛可能轮换(6/1验证: Haaland/Ødegaard/Çalhanoğlu都没上)')
            reasoning.append('球星数量优')
        elif len(h_stars) >= 1 and len(a_stars) == 0:
            p(f'    → 有核心球员, 但友谊赛不一定首发')
    else:
        p(f'    数据不足')

    # Step 6: 位置冲突/团队氛围
    p(f'  Step6 [位置冲突/团队氛围]')
    if home_prof:
        vibe = home_prof.get('team_vibe', '稳定')
        if vibe == '新老交替':
            p(f'    {m["home"]}氛围: {vibe} → 核心可能轮换, 新人上位')
            reasoning.append('主队新老交替')
        elif vibe == '矛盾':
            p(f'    {m["home"]}氛围: {vibe} → 队内不和, 影响执行力!')
            reasoning.append('主队矛盾')
        else:
            p(f'    {m["home"]}氛围: {vibe}')
        if home_prof.get('position_conflict'):
            p(f'    ⚠ {m["home"]}位置冲突: {home_prof.get("position_conflict_note","")}')
            p(f'    → 球星不上反而可能更流畅(6/1: 土耳其没上Çalhanoğlu=4:0大胜)')
            reasoning.append('主队位置冲突')
    if away_prof:
        vibe = away_prof.get('team_vibe', '稳定')
        if vibe != '稳定':
            p(f'    {m["away"]}氛围: {vibe}')
        if away_prof.get('position_conflict'):
            p(f'    ⚠ {m["away"]}位置冲突: {away_prof.get("position_conflict_note","")}')
            reasoning.append('客队位置冲突')
    if not home_prof and not away_prof:
        p(f'    数据不足')

    # Step 7: 近期状态
    p(f'  Step7 [近期状态]')
    if hf and hf['results']:
        form_str = ' '.join(r2['result'] for r2 in hf['results'])
        p(f'    {m["home"]}: {form_str} ({hf["w"]}W{hf["d"]}D{hf["l"]}L)')
        if hf['w'] >= 3:
            p(f'    → {m["home"]}状态火热!')
            reasoning.append('主队状态火热')
        elif hf['l'] >= 3 and hf['w'] == 0:
            p(f'    → {m["home"]}连败{hf["l"]}场, 状态极差!')
    if af and af['results']:
        form_str = ' '.join(r2['result'] for r2 in af['results'])
        p(f'    {m["away"]}: {form_str} ({af["w"]}W{af["d"]}D{af["l"]}L)')
        if af['w'] >= 3:
            p(f'    → {m["away"]}状态火热!')
            reasoning.append('客队状态火热')
        elif af['l'] >= 3 and af['w'] == 0:
            p(f'    → {m["away"]}连败{af["l"]}场, 状态极差!')
            reasoning.append('客队状态极差')
    if hf and af and hf['results'] and af['results']:
        h_pts = hf['w']*3+hf['d']
        a_pts = af['w']*3+af['d']
        h_total = hf['w']+hf['d']+hf['l']
        a_total = af['w']+af['d']+af['l']
        if h_total >= 3 and a_total >= 3:
            h_rate = h_pts/(h_total*3)*100
            a_rate = a_pts/(a_total*3)*100
            p(f'    状态对比: {m["home"]}{h_rate:.0f}% vs {m["away"]}{a_rate:.0f}%')

    # Step 8: 世界杯动机
    p(f'  Step8 [世界杯动机]')
    if home_wc and not away_wc:
        p(f'    {m["home"]}是WC队(6/12开幕) → 全队认真磨合, 不只是球星认真')
        p(f'    {m["away"]}非WC队 → 无大赛压力, 战意存疑')
        p(f'    → 动机严重不对称! 体系差距被动机放大')
        reasoning.append('WC动机碾压')
    elif away_wc and not home_wc:
        p(f'    {m["away"]}是WC队 → 全队认真磨合')
        p(f'    {m["home"]}非WC队 → 战意存疑')
        reasoning.append('客队WC动机')
    elif home_wc and away_wc:
        p(f'    双方WC队 → 都在磨合, 但不会拼命(怕受伤)')
        p(f'    → 试探为主, 不会大比分拼命')
    else:
        p(f'    双方非WC队 → 战意不确定')
        reasoning.append('双方无WC动机')

    # Step 8.5: 主场优势 + 赔率均衡信号
    p(f'  Step8.5 [主场优势 + 赔率均衡]')
    # 主场优势(国际赛尤其明显)
    if is_intl:
        p(f'    国际赛主场优势: 验证数据显示主胜率约60%(5/31+6/1+6/2)')
        reasoning.append('国际赛主场优势')

    # 赔率均衡信号(联赛关键!)
    if pred:
        odds_range = max(oh,od,oa) - min(oh,od,oa)
        hp_ap_diff = abs(pred['hp'] - pred['ap'])
        if odds_range < 0.8:
            p(f'    ⚠ 均衡赔率(极差{odds_range:.2f}<0.8) → 平局风险极高!')
            p(f'    5/31验证: 3场均衡联赛全平(冈山1:1浦和/清水1:1横滨/代格福什2:2布鲁马)')
            reasoning.append('均衡赔率→平局风险')
        elif odds_range < 1.0:
            p(f'    近均衡赔率(极差{odds_range:.2f}) → 平局风险较高')
            reasoning.append('近均衡赔率→平局风险')
        p(f'    赔率偏斜: 主客概率差{hp_ap_diff*100:.1f}%')

    # Step 9: 赔率模型
    p(f'  Step9 [赔率模型]')
    if pred:
        pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
        p(f'    v3.9.2: {pred_cn}({pred["conf"]*100:.0f}%) 赔率{oh:.2f}/{od:.2f}/{oa:.2f}')
        p(f'    概率: 主{pred["hp"]*100:.1f}% 平{pred["dp"]*100:.1f}% 客{pred["ap"]*100:.1f}%')
    elif has_rq_only:
        p(f'    SPF赔率未出, 只有让球')
    else:
        p(f'    赔率未出')

    if hc and rq_cn:
        rq_conf = rq_pred['conf'] if rq_pred else 0
        p(f'    让球: 让{hc} {rq_cn}({rq_conf*100:.0f}%) 赔率{m["rqh"]:.2f}/{m["rqd"]:.2f}/{m["rqa"]:.2f}')
        if rq_meaning:
            p(f'    含义: {rq_meaning}')
        # 亚盘偏斜信号 — 让球赔率比SPF更能反映市场真实判断
        # 关键: SPF均衡时(偏斜<5%), 亚盘只要有方向就比SPF更可信
        if rq_pred and pred:
            rq_hp_ap_diff = abs(rq_pred['hp'] - rq_pred['ap'])
            spf_hp_ap_diff = abs(pred['hp'] - pred['ap'])
            if rq_pred['pred'] != 'D' and spf_hp_ap_diff < 0.05:
                # SPF均衡但亚盘有方向 → 亚盘信号更强
                rq_dir_cn = {'H':'主胜','A':'客胜'}[rq_pred['pred']]
                p(f'    ⚠ 亚盘信号: SPF均衡(偏斜{spf_hp_ap_diff*100:.1f}%)但让球偏{rq_dir_cn}(偏斜{rq_hp_ap_diff*100:.1f}%) → 市场真实倾向{rq_dir_cn}')
                p(f'    6/2验证: 克罗地亚vs比利时 SPF偏斜0%但亚盘偏客胜 → 实际0:2客胜!')
                reasoning.append(f'亚盘偏{rq_dir_cn}')
            elif rq_hp_ap_diff > spf_hp_ap_diff + 0.05:
                rq_dir_cn = {'H':'主胜','A':'客胜'}[rq_pred['pred']] if rq_pred['pred'] != 'D' else '平局'
                p(f'    ⚠ 亚盘信号: 让球偏斜{rq_hp_ap_diff*100:.1f}% > SPF偏斜{spf_hp_ap_diff*100:.1f}% → 市场真实倾向{rq_dir_cn}')
                reasoning.append(f'亚盘偏{rq_dir_cn}')

    # ===== Step 10: 综合推理 =====
    p(f'  {"─"*80}')
    p(f'  Step10 [综合推理]')
    p(f'    信号汇总: {" | ".join(reasoning) if reasoning else "无强信号"}')

    # 核心认知:
    # 足球是团队游戏 — 排名差距=体系差距, 不因球星缺阵改变
    # 体系碾压(排名差≥20) + WC动机 → 最强信号(5/31+6/1验证10/10全对)
    # 球星只影响比分大小, 不影响胜负方向
    # 位置冲突: 球星不上反而可能更流畅
    # 板凳深度: 强队替补仍是五大联赛级别, 友谊赛轮换影响小

    combined_pred = None
    combined_rq = None  # 让球方向覆盖
    override_note = ''

    if rank_diff is not None and rank_diff >= 30 and home_wc and not away_wc:
        combined_pred = 'H'
        p(f'    推理: 排名差{rank_diff}(体系碾压) + {m["home"]}WC碾压{m["away"]}非WC → 主队大胜')
        p(f'    体系差距不因球星缺阵改变(6/1: 土耳其没上Çalhanoğlu=4:0, 挪威没上Haaland=3:1)')
        combined_rq = 'H'
        override_note = '体系碾压+WC动机→让胜'
    elif rank_diff is not None and rank_diff >= 15 and home_wc and not away_wc:
        combined_pred = 'H'
        p(f'    推理: 排名差{rank_diff}(体系明显优) + {m["home"]}WC碾压{m["away"]}非WC → 主队胜')
        combined_rq = 'H'
        override_note = '体系优+WC动机→让胜'
    elif rank_diff is not None and rank_diff <= -30 and away_wc and not home_wc:
        combined_pred = 'A'
        p(f'    推理: 排名差{rank_diff}(客队体系碾压) + {m["away"]}WC碾压{m["home"]}非WC → 客队大胜')
        p(f'    体系差距不因球星缺阵改变')
        combined_rq = 'A'
        override_note = '客队体系碾压+WC动机→客胜'
        # 修正: 6/2验证 格鲁吉亚1:1罗马尼亚 — 排名差-30但主队有球星爆点
        if home_prof and home_prof.get('attack',0) >= 6 and home_rank and home_rank >= 50:
            p(f'    ⚠ 修正: {m["home"]}虽排名低但有球星爆点(攻{home_prof["attack"]}), 逼平风险高!')
            p(f'    6/2验证: 格鲁吉亚(#68)有克瓦拉茨赫利亚→1:1逼平罗马尼亚(#38)')
            combined_pred = 'D'
            combined_rq = None
            override_note = ''
            reasoning.append('主队有爆点逼平风险')
    elif rank_diff is not None and rank_diff <= -15 and away_wc and not home_wc:
        combined_pred = 'A'
        p(f'    推理: 排名差{rank_diff}(客队体系明显优) + {m["away"]}WC碾压{m["home"]}非WC → 客队胜')
        combined_rq = 'A'
        override_note = '客队体系优+WC动机→客胜'
    elif rank_diff is not None and rank_diff >= 20 and home_wc and away_wc:
        combined_pred = 'H'
        p(f'    推理: 排名差{rank_diff}(体系明显优) + 双方WC队 → 主队胜但试探为主')
        p(f'    → 不是碾压局, 小比分胜(5/31: 美国3:2塞内加尔)')
    elif rank_diff is not None and rank_diff <= -20 and away_wc and home_wc:
        combined_pred = 'A'
        p(f'    推理: 排名差{rank_diff}(客队体系明显优) + 双方WC队 → 客队胜但试探为主')
    elif home_wc and away_wc:
        # WC vs WC: 友谊赛试探局, 默认倾向平局
        # 6/2验证: 威尔士1:1加纳(赔率偏斜18.6%选主胜→错), 格鲁吉亚1:1罗马尼亚→对
        # 5/31: 美国3:2塞内加尔(排名差-4赔率均衡→平局?实际主胜)
        # 统计: 5场WC vs WC友谊赛=3平2分胜负, 平局率60%
        # 规则: 赔率偏斜<20% → 默认平局; ≥20% → 可跟赔率但降级
        if pred:
            hp_ap_diff = abs(pred['hp'] - pred['ap'])
            if hp_ap_diff >= 0.20:
                # 赔率极偏斜(≥20%), 可以跟, 但仍降级
                combined_pred = pred['pred']
                pred_cn_wc = {'H':'主胜','D':'平局','A':'客胜'}[combined_pred]
                p(f'    推理: WC vs WC + 赔率极偏斜{hp_ap_diff*100:.1f}%(≥20%) → 跟赔率={pred_cn_wc} (降级)')
            else:
                combined_pred = 'D'
                p(f'    推理: WC vs WC + 赔率偏斜{hp_ap_diff*100:.1f}%(<20%) → 试探局默认平局')
                p(f'    6/2验证: 威尔士1:1加纳(偏斜18.6%选主胜→错!) → WC vs WC赔率不可靠')
        else:
            combined_pred = 'D'
            p(f'    推理: WC vs WC + 无赔率 → 试探局默认平局')
    elif home_wc and not away_wc:
        combined_pred = 'H'
        p(f'    推理: {m["home"]}WC队 vs {m["away"]}非WC队 → WC动机→主胜')
        combined_rq = 'H'
    elif away_wc and not home_wc:
        combined_pred = 'A'
        p(f'    推理: {m["away"]}WC队 vs {m["home"]}非WC队 → 客队WC动机→客胜')
        combined_rq = 'A'
    else:
        if pred:
            combined_pred = pred['pred']
            pred_cn_model = {'H':'主胜','D':'平局','A':'客胜'}[combined_pred]
            p(f'    推理: 双方非WC → 用赔率模型={pred_cn_model}')
        else:
            p(f'    推理: 无法预测')

    # 位置冲突修正: 球星不上可能反而更流畅
    if '主队位置冲突' in reasoning and combined_pred == 'H':
        p(f'    修正: 位置冲突 → 球星不上反而可能更流畅, 不降低信心')

    # 板凳深度加分
    if '深度碾压' in reasoning and combined_pred == 'H':
        p(f'    加分: 板凳深度碾压 → 友谊赛轮换影响小, 让球更安全')

    # 客队状态极差
    if '客队状态极差' in reasoning and combined_pred in ('H', None):
        if not combined_pred: combined_pred = 'H'
        p(f'    加分: {m["away"]}连败 → 主队更可能大胜')

    # 攻防碾压 → 大比分倾向
    if '攻防碾压' in reasoning and combined_pred == 'H':
        p(f'    加分: 进攻碾压防守 → 大比分倾向')

    # 联赛均衡赔率 → 强制平局(5/31验证: 均衡联赛平局率高)
    if combined_pred and combined_pred != 'D':
        if not is_intl:
            if '均衡赔率→平局风险' in reasoning:
                p(f'    修正: 联赛均衡赔率(极差<0.8) → 覆盖为平局(5/31验证3/3全平)')
                combined_pred = 'D'
            elif '近均衡赔率→平局风险' in reasoning and pred and pred['dp'] >= 0.27:
                dp_pct = pred['dp']*100
                p(f'    修正: 联赛近均衡赔率+平局概率{dp_pct:.0f}%≥27% → 覆盖为平局')
                combined_pred = 'D'

    # 亚盘偏斜信号 — SPF均衡但亚盘偏一侧时，用亚盘方向(6/2验证: 克罗地亚vs比利时)
    if combined_pred == 'D' and '亚盘偏' in str(reasoning):
        rq_dir = [r for r in reasoning if r.startswith('亚盘偏')]
        if rq_dir:
            rq_cn_name = rq_dir[0].replace('亚盘偏','')
            rq_direction = {'主胜':'H','客胜':'A','平局':'D'}.get(rq_cn_name, 'D')
            if rq_direction != 'D':
                p(f'    修正: SPF均衡→平局, 但亚盘偏{rq_cn_name} → 修正为{rq_cn_name}')
                p(f'    6/2验证: 克罗地亚vs比利时 SPF均衡→平局, 但亚盘偏客胜 → 实际0:2客胜!')
                combined_pred = rq_direction

    # 根据综合预测调整比分选择
    if combined_pred and combined_pred != initial_pred_dir:
        picks = []
        if combined_pred == 'H' and home_scores: picks.append(home_scores[0])
        elif combined_pred == 'D' and draw_scores: picks.append(draw_scores[0])
        elif combined_pred == 'A' and away_scores: picks.append(away_scores[0])
        if combined_pred == 'H':
            if draw_scores: picks.append(draw_scores[0])
            elif len(home_scores) > 1: picks.append(home_scores[1])
        elif combined_pred == 'A':
            if draw_scores: picks.append(draw_scores[0])
            elif len(away_scores) > 1: picks.append(away_scores[1])
        elif combined_pred == 'D':
            if home_scores: picks.append(home_scores[0])
            elif away_scores: picks.append(away_scores[0])

    # ===== 最终推荐 =====
    p(f'  {"═"*80}')
    p(f'  ★ 推荐 ★')

    advice = []

    # SPF方向
    if combined_pred:
        pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[combined_pred]
        if has_spf:
            spf_odds = {'H':oh,'D':od,'A':oa}[combined_pred]
            advice.append(f'SPF{pred_cn}({spf_odds:.2f})')

    # 让球方向(综合推理覆盖模型)
    if hc:
        if combined_rq == 'H' and rq_dir != 'H':
            advice.append(f'让{hc}让胜({m["rqh"]:.2f}) ← {override_note}(模型原判{rq_cn})')
        elif combined_rq == 'H' and rq_dir == 'H':
            advice.append(f'让{hc}让胜({m["rqh"]:.2f}) ← 模型+推理同向')
        elif combined_pred == 'H' and home_wc and not away_wc:
            if rq_dir != 'H':
                advice.append(f'让{hc}考虑让胜({m["rqh"]:.2f}) ← WC碾压(谨慎)')
            else:
                advice.append(f'让{hc}让胜({m["rqh"]:.2f})')
        elif rq_cn:
            advice.append(f'让{hc}{rq_cn}')

    # 比分
    if picks:
        score_str = ' / '.join(f'{s}({o:.1f})' for s, o in picks[:3])
        advice.append(f'比分{score_str}')

    p(f'    {" / ".join(advice)}')

    # 评分(核心: 体系差距+WC动机为主, 球星/深度为辅)
    score_val = 0
    # 体系差距(决定胜负方向) — 双向: 主优或客优都算
    abs_rank_diff = abs(rank_diff) if rank_diff else 0
    if abs_rank_diff >= 30: score_val += 5
    elif abs_rank_diff >= 15: score_val += 3
    elif abs_rank_diff >= 5: score_val += 1
    # H2H
    if 'H2H碾压' in reasoning: score_val += 3
    elif 'H2H占优' in reasoning: score_val += 2
    # 攻防
    if '攻防碾压' in reasoning: score_val += 2
    elif home_prof and away_prof and home_prof['attack'] - away_prof['defense'] >= 1: score_val += 1
    # WC动机(放大体系差距)
    if 'WC动机碾压' in reasoning: score_val += 3
    elif '客队WC动机' in reasoning: score_val += 2  # 客队WC动机, 但6/2验证格鲁吉亚1:1罗马尼亚(逼平), 降级
    # WC vs WC试探局 → 大幅降分(6/2验证: WC vs WC平局高发)
    if combined_pred == 'D' and home_wc and away_wc: score_val -= 3
    # 国际赛主场优势
    if '国际赛主场优势' in reasoning and combined_pred == 'H': score_val += 1
    # 联赛均衡赔率→平局(稳健但低赔率)
    if '均衡赔率→平局风险' in reasoning and combined_pred == 'D': score_val += 1
    # 板凳深度(友谊赛关键)
    if '深度碾压' in reasoning: score_val += 2
    elif home_prof and away_prof and abs(home_prof.get('depth',5) - away_prof.get('depth',5)) >= 2: score_val += 1
    # 球星(友谊赛降权: 只+1, 因为可能不上)
    if '球星数量优' in reasoning: score_val += 1
    # 状态
    if '主队状态火热' in reasoning: score_val += 1
    if '客队状态极差' in reasoning: score_val += 1
    # 负面信号
    if '双方无WC动机' in reasoning: score_val -= 2
    if '主队位置冲突' in reasoning: score_val -= 0  # 位置冲突不一定负面, 不扣分
    if '主队矛盾' in reasoning: score_val -= 2

    if score_val >= 10: tier = 'A'
    elif score_val >= 6: tier = 'B'
    elif score_val >= 3: tier = 'C'
    else: tier = 'D'

    tier_cn = {'A':'A档(重点推荐)','B':'B档(小注)','C':'C档(观望)','D':'D档(避让)'}
    p(f'    档位: {tier_cn[tier]} (评分{score_val})')

    all_results.append({
        'm': m, 'pred': pred, 'rq_pred': rq_pred, 'picks': picks,
        'tier': tier, 'score_val': score_val, 'reasoning': reasoning,
        'combined_pred': combined_pred, 'combined_rq': combined_rq,
        'home_wc': home_wc, 'away_wc': away_wc,
        'home_rank': home_rank, 'away_rank': away_rank,
        'h2h': h2h, 'hf': hf, 'af': af,
    })

# ===== 最终汇总 =====
p('')
p(f'{"="*90}')
p(f'  最终推荐汇总')
p(f'  5/31验证: 排名碾压+WC动机→大胜 正确率6/6=100%')
p(f'{"="*90}')

for tier_name, tier_label in [('A','A档(重点推荐)'), ('B','B档(小注)'), ('C','C档(观望)'), ('D','D档(避让)')]:
    tier_matches = [r for r in all_results if r['tier'] == tier_name]
    if not tier_matches: continue
    p('')
    p(f'  【{tier_label}】')
    for r in tier_matches:
        m = r['m']
        pred_cn = {'H':'主胜','D':'平局','A':'客胜'}.get(r['combined_pred'], '?')
        rank_info = f'#{r["home_rank"]}vs#{r["away_rank"]}' if r['home_rank'] else ''
        h2h_info = ''
        if r['h2h'] and r['h2h']['total'] > 0:
            h2h_info = f' H2H:{r["h2h"]["home_wins"]}W{r["h2h"]["draws"]}D{r["h2h"]["away_wins"]}L'

        p(f'')
        p(f'  {m["num_str"]} {m["home"]}{"★" if r["home_wc"] else ""} vs {m["away"]}{"★" if r["away_wc"] else ""} [{rank_info}]{h2h_info}')
        p(f'  SPF: {pred_cn}')
        if m.get('hc'):
            if r.get('combined_rq') == 'H':
                p(f'  让球: 让{m["hc"]}让胜({m["rqh"]:.2f}) ← 推理覆盖')
            elif r.get('rq_pred'):
                rq_d = r['rq_pred']['pred']
                rq_c = {'H':'让胜','D':'让平','A':'让负'}[rq_d]
                p(f'  让球: 让{m["hc"]}{rq_c}')
        score_str = ' / '.join(f'{s}({o:.1f})' for s, o in r['picks'][:3])
        p(f'  比分: {score_str}')
        p(f'  信号: {" | ".join(r["reasoning"])}')

# 串关
p('')
p(f'  {"─"*80}')
p(f'  串关建议:')
p(f'')

# A档让球串
a_crush = [r for r in all_results if r['tier'] == 'A' and r.get('combined_rq') == 'H' and r['m'].get('hc')]
if len(a_crush) >= 2:
    p(f'  A档碾压让胜2串1:')
    for i in range(min(len(a_crush)-1, 2)):
        r1 = a_crush[i]
        r2 = a_crush[i+1]
        m1, m2 = r1['m'], r2['m']
        o1, o2 = m1['rqh'], m2['rqh']
        combo = o1 * o2
        p(f'    {m1["num_str"]}让{m1["hc"]}让胜({o1:.2f}) x {m2["num_str"]}让{m2["hc"]}让胜({o2:.2f}) = {combo:.2f}')

# A+B档比分串
p(f'')
p(f'  比分2串1(高风险):')
score_picks = [r for r in all_results if r['tier'] in ('A','B') and len(r['picks']) >= 1]
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
try:
    print(report)
except Exception:
    pass
# Always write to file as backup
with open('d:/football_tools/today_report.txt', 'w', encoding='utf-8') as f:
    f.write(report)
