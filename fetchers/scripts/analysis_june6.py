"""6月6日体彩分析脚本"""
import sys, math
sys.stdout.reconfigure(encoding='utf-8')
from fetchers.pre_match.collector import PreMatchCollector
c = PreMatchCollector()

def otp(h,d,a):
    ih,id_,ia=1/h,1/d,1/a; t=ih+id_+ia; return {'home':ih/t,'draw':id_/t,'away':ia/t}

def predict_score(home_prob, draw_prob, away_prob, is_altitude=False, home_motivated=False,
                  home_team=None, away_team=None, home_odds=None, away_odds=None):
    """预测比分 - 考虑强弱差距"""
    # 基础xG
    base_hxg = 1.0
    base_axg = 0.8

    # 根据概率调整
    hxg = base_hxg + (home_prob - 0.33) * 1.5
    axg = base_axg + (away_prob - 0.33) * 1.0

    # 强弱差距修正: 赔率差距大 → 强队xG提升
    if home_odds and away_odds:
        try:
            ho = float(home_odds)
            ao = float(away_odds)
            if ho < 1.30 and ho < ao * 0.5:
                # 主队碾压: 主队xG大幅提升
                hxg += 0.5 + (1.30 - ho) * 2.0  # 1.20→+0.70, 1.15→+0.80
            elif ao < 1.30 and ao < ho * 0.5:
                # 客队碾压
                axg += 0.5 + (1.30 - ao) * 2.0
            elif ho < 1.60 and ho < ao * 0.7:
                # 主队明显优势
                hxg += 0.3
            elif ao < 1.60 and ao < ho * 0.7:
                # 客队明显优势
                axg += 0.3
            elif ho < 2.00 and ho < ao * 0.8:
                # 主队小幅优势
                hxg += 0.15
            elif ao < 2.00 and ao < ho * 0.8:
                # 客队小幅优势
                axg += 0.15
        except:
            pass

    # 高原效应
    if is_altitude:
        hxg += 0.2
        axg -= 0.2

    # 动机加成
    if home_motivated:
        hxg += 0.3

    # 确保xG合理范围
    hxg = max(0.5, min(2.8, hxg))
    axg = max(0.3, min(2.2, axg))
    scores = []
    for h in range(0,5):
        for a in range(0,5):
            p = (hxg**h * math.exp(-hxg) / math.factorial(h)) * (axg**a * math.exp(-axg) / math.factorial(a))
            scores.append((f'{h}-{a}', p))
    scores.sort(key=lambda x:-x[1])
    return scores[0][0], scores[:3], hxg, axg

sep = '='*100

# === 国际赛 ===
print(sep)
print('6月6日体彩国际赛分析 (比分预测)')
print(sep)

matches = [
    (6207,'Belgium','Tunisia',1.21,4.95,9.90,-1,None,''),
    (6208,'Portugal','Chile',1.15,5.65,12.00,-2,None,''),
    (6209,'Romania','Wales',2.60,2.80,2.58,0,None,''),
    (6210,'United States','Germany',4.80,3.80,1.52,1,None,'home_motivated'),
    (6211,'Australia','Switzerland',5.90,3.70,1.45,1,None,''),
    (6212,'Panama','Bosnia and Herzegovina',3.25,2.98,2.06,1,None,''),
    (6214,'Bolivia','Scotland',6.75,4.25,1.34,1,'La Paz','altitude'),
    (6215,'Brazil','Egypt',1.20,5.00,10.50,-1,None,''),
    (6216,'Venezuela','Turkey',5.75,3.76,1.45,1,None,''),
]

for num,ho,aw,oh,od,oa,hc,vn,flag in matches:
    b = otp(oh,od,oa)
    r = c.collect(ho,aw,'2026-06-06','Friendly',venue_city=vn,odds={'home':oh,'draw':od,'away':oa})
    av = r.friendly_adjustment
    ap = {'home':b['home']+av.get('home_win_adj',0),'draw':b['draw']+av.get('draw_adj',0),'away':b['away']+av.get('away_win_adj',0)}
    for k in ap: ap[k]=max(.01,min(.97,ap[k]))
    t=sum(ap.values()); ap={k:ap[k]/t for k in ap}

    is_alt = flag == 'altitude'
    is_hm = flag == 'home_motivated'

    if is_alt:
        ap['home'] += 0.15; ap['away'] -= 0.10; ap['draw'] -= 0.05
        t=sum(ap.values()); ap={k:ap[k]/t for k in ap}

    score, top3, hxg, axg = predict_score(ap['home'], ap['draw'], ap['away'], is_alt, is_hm,
                                           home_team=ho, away_team=aw, home_odds=oh, away_odds=oa)
    top3_str = ', '.join([f'{s}({p*100:.0f}%)' for s,p in top3])

    # SPF建议
    if ap['draw'] > max(ap['home'],ap['away']):
        spf_tip = '平局'
    elif ap['home'] > ap['away']:
        spf_tip = '主胜'
    else:
        spf_tip = '客胜'

    # RQSPF建议
    if hc < 0:
        if ap['home'] > 0.50 and hxg > axg + 0.8:
            rqspf_tip = '让球主胜'
        else:
            rqspf_tip = '让球下盘'
    elif hc > 0:
        if is_alt or is_hm:
            rqspf_tip = '受让主胜'
        elif ap['home'] + ap['draw'] > 0.55:
            rqspf_tip = '受让主胜'
        else:
            rqspf_tip = '让球客胜'
    else:
        rqspf_tip = '-'

    print(f'\n{num} {ho} vs {aw}')
    print(f'  赔率: SPF {oh}/{od}/{oa} | 让球{hc:+.0f}')
    print(f'  修正概率: 主{ap["home"]:.0%} 平{ap["draw"]:.0%} 客{ap["away"]:.0%}')
    print(f'  预测xG: {hxg:.1f}-{axg:.1f}')
    print(f'  预测比分: {score} (TOP3: {top3_str})')
    print(f'  SPF: {spf_tip} | RQSPF: {rqspf_tip}')
    if r.key_insights:
        for ins in r.key_insights[:2]:
            print(f'  >> {ins[:70]}')
    if is_alt:
        print(f'  >> 高原La Paz 3640m! 苏格兰极不适应,主胜概率大幅上调')
    if is_hm:
        print(f'  >> 美国WC东道主必须认真打,德国陪练不拼命')

# === 日职 ===
print(f'\n{sep}')
print('6月6日日职分析')
print(sep)

jl = [
    (6205,'柏太阳神','京都不死鸟',1.63,3.65,4.15,-1),
    (6206,'川崎前锋','广岛三箭',3.17,3.24,1.98,1),
]
for num,ho_cn,aw_cn,oh,od,oa,hc in jl:
    b = otp(oh,od,oa)
    score, top3, hxg, axg = predict_score(b['home'], b['draw'], b['away'],
                                           home_team=ho_cn, away_team=aw_cn, home_odds=oh, away_odds=oa)
    top3_str = ', '.join([f'{s}({p*100:.0f}%)' for s,p in top3])
    spf_tip = '主胜' if b['home']>b['away'] else ('客胜' if b['away']>b['home'] else '平局')
    if hc < 0:
        rqspf_tip = '让球主胜' if b['home']>0.50 and hxg>axg+0.8 else '让球下盘'
    else:
        rqspf_tip = '受让主胜' if b['home']+b['draw']>0.55 else '让球客胜'

    print(f'\n{num} {ho_cn} vs {aw_cn}')
    print(f'  赔率: SPF {oh}/{od}/{oa} | 让球{hc:+.0f}')
    print(f'  概率: 主{b["home"]:.0%} 平{b["draw"]:.0%} 客{b["away"]:.0%}')
    print(f'  预测xG: {hxg:.1f}-{axg:.1f}')
    print(f'  预测比分: {score} (TOP3: {top3_str})')
    print(f'  SPF: {spf_tip} | RQSPF: {rqspf_tip}')
