"""
v3.9.1完整预测: 更合理的泊松参数推导
修正: 用欧赔隐含概率直接分配进球, 不用draw反推
"""
import sys, io, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

from fetchers.analysis.models.enhanced_linear import EnhancedLinearModel

model = EnhancedLinearModel()

def implied_probs(oh, od, oa):
    """欧赔→隐含概率(去margin)"""
    rh, rd, ra = 1/oh, 1/od, 1/oa
    t = rh + rd + ra
    return rh/t, rd/t, ra/t

def odds_to_poisson_params(oh, od, oa, ah_handicap):
    """
    用欧赔+亚盘推导合理的泊松参数
    方法:
    1. 总进球期望 = 历史同联赛平均(用赔率区间估算)
    2. 实力差距 = 亚盘让球数
    3. λ_h = (μ + diff)/2, λ_a = (μ - diff)/2
    """
    ph, pd, pa = implied_probs(oh, od, oa)

    # 总进球期望估算: 用赔率区间的历史数据
    # 低赔率主胜(1.10-1.30): 平均3.0球, 杯赛2.5球
    # 中赔率(1.40-1.70): 平均2.7球, 杯赛2.3球
    # 高赔率(1.80+): 平均2.5球, 杯赛2.2球
    # 超高赔率(2.0+): 平均2.4球
    if oh <= 1.30:
        mu = 2.9  # 强队碾压, 进球多
    elif oh <= 1.55:
        mu = 2.6
    elif oh <= 1.80:
        mu = 2.5
    elif oh <= 2.10:
        mu = 2.4
    else:
        mu = 2.3

    # draw概率修正总进球: draw率越高→总进球越少
    # 因为0-0和1-1概率高 → 进球少
    draw_factor = 1 - pd * 1.5  # pd=30% → factor=0.55 → mu*0.55+mu*0.45*2.5
    # 更简单: pd高 → mu减小
    if pd >= 0.30:
        mu *= 0.85  # 高draw → 进球少
    elif pd >= 0.25:
        mu *= 0.92

    # 亚盘让球修正实力差距
    if ah_handicap < 0:
        diff = abs(ah_handicap)
    elif ah_handicap > 0:
        diff = -abs(ah_handicap)
    else:
        diff = 0

    lam_h = max(0.5, (mu + diff) / 2)
    lam_a = max(0.3, (mu - diff) / 2)

    # 确保主场优势: λ_h应略高于λ_a(即使赔率相近)
    if lam_h < lam_a * 1.1 and oh < oa:
        lam_h *= 1.15
        lam_a *= 0.87
        mu = lam_h + lam_a

    return ph, pd, pa, lam_h, lam_a, mu

def poisson_p(lh, la, hg, ag):
    ph = math.exp(-lh) * lh**hg / math.factorial(hg)
    pa = math.exp(-la) * la**ag / math.factorial(ag)
    return ph * pa

def top_scores(lh, la, n=8):
    scores = []
    for h in range(5):
        for a in range(5):
            scores.append((h, a, poisson_p(lh, la, h, a)))
    scores.sort(key=lambda x: -x[2])
    return scores[:n]

def ou_probs(lh, la):
    mu = lh + la
    p = [math.exp(-mu) * mu**g / math.factorial(g) for g in range(8)]
    u25 = p[0] + p[1] + p[2]  # 0,1,2球 = 小2.5
    o25 = 1 - u25
    u35 = u25 + p[3]  # +3球 = 小3.5
    o35 = 1 - u35
    return o25, u25, o35, u35

def ah_probs(lh, la, handicap):
    """亚盘概率(让handicap球)"""
    p_win = 0; p_draw = 0; p_lose = 0
    for h in range(7):
        for a in range(7):
            p = poisson_p(lh, la, h, a)
            diff = h - a + handicap  # handicap为主让球数(负数=主让)
            if handicap < 0:  # 主让球
                if h - a >= abs(handicap) + 1: p_win += p  # 赢盘
                elif h - a == abs(handicap): p_draw += p  # 走水
                else: p_lose += p  # 输盘
    return p_win, p_draw, p_lose

# 5场比赛
matches = [
    {'id':'001','league':'友谊赛','league_std':'friendly',
     'home':'爱尔兰','away':'卡塔尔',
     'oh':1.51,'od':3.48,'oa':5.60,'ah':-1},
    {'id':'002','league':'葡超','league_std':'primeira_liga',
     'home':'卡萨皮亚','away':'杜连斯',
     'oh':2.10,'od':2.77,'oa':3.42,'ah':-1},
    {'id':'003','league':'解放者杯','league_std':'copa_libertadores',
     'home':'波特诺山丘','away':'水晶体育',
     'oh':1.52,'od':3.45,'oa':5.50,'ah':-1},
    {'id':'004','league':'解放者杯','league_std':'copa_libertadores',
     'home':'帕尔梅拉斯','away':'巴兰基亚青年',
     'oh':1.13,'od':5.95,'oa':13.00,'ah':-2},
    {'id':'005','league':'解放者杯','league_std':'copa_libertadores',
     'home':'博卡青年','away':'天主大学',
     'oh':1.27,'od':4.50,'oa':8.35,'ah':-1},
]

lines = []
def p(s=""): lines.append(s)

p("=" * 80)
p("  2026-05-29 v3.9.1 完整预测")
p("=" * 80)

for m in matches:
    oh,od,oa,ah_hc = m['oh'],m['od'],m['oa'],m['ah']

    # 欧赔隐含概率
    ph, pd, pa = implied_probs(oh, od, oa)

    # v3.9.1调整
    hp, dp, ap = ph, pd, pa
    flags = []

    is_cup = any(kw in m['league_std'] for kw in model.CUP_KEYWORDS) or 'libertadores' in m['league_std']
    is_prima = 'primeira_liga' in m['league_std']

    if is_cup:
        dp -= model.CUP_DP_REDUCE; nd=hp+ap
        if nd>0: hp+=model.CUP_DP_REDUCE*(hp/nd); ap+=model.CUP_DP_REDUCE*(ap/nd)
        hp,dp,ap=model._normalize_probs(hp,dp,ap); flags.append('杯赛减draw')
    if is_prima:
        dp-=0.02; nd=hp+ap
        if nd>0: hp+=0.02*(hp/nd); ap+=0.02*(ap/nd)
        hp,dp,ap=model._normalize_probs(hp,dp,ap); flags.append('葡超减draw')
    if pd>=0.30:
        if is_prima:
            boost=0.00; base=0.02; ah0_e=0.02
        else:
            boost=0.01; base=0.01; ah0_e=0.02
        if boost>0:
            dp+=boost; nd=hp+ap
            if nd>0: hp-=boost*(hp/nd); ap-=boost*(ap/nd)
            hp,dp,ap=model._normalize_probs(hp,dp,ap)
        is_ah0 = abs(ah_hc)<0.01
        rv = base + (ah0_e if is_ah0 else 0)
        if rv>0:
            dp-=rv; nd=hp+ap
            if nd>0: hp+=rv*(hp/nd); ap+=rv*(ap/nd)
            hp,dp,ap=model._normalize_probs(hp,dp,ap); flags.append('dt30减draw')
    if is_cup and 1.35<=oh<=1.50:
        hp-=0.02; dp+=0.01; ap+=0.01
        hp,dp,ap=model._normalize_probs(hp,dp,ap); flags.append('南美冷门区')
    hp,dp,ap=model._normalize_probs(hp,dp,ap)

    # 泊松参数
    _, _, _, lh, la, mu = odds_to_poisson_params(oh, od, oa, ah_hc)

    # 最可能比分
    scores = top_scores(lh, la)
    # 大小球
    o25,u25,o35,u35 = ou_probs(lh, la)
    # 亚盘
    aw,ad,al = ah_probs(lh, la, ah_hc)

    # 预测
    pred_map = {'主胜':hp,'平局':dp,'客胜':ap}
    pred = max(pred_map, key=pred_map.get)
    max_p = max(hp,dp,ap)
    conf = '★★★' if max_p>=0.65 else ('★★☆' if max_p>=0.55 else ('★☆☆' if max_p>=0.45 else '☆☆☆'))

    # 总进球分布
    p_goals = [math.exp(-mu)*mu**g/math.factorial(g) for g in range(7)]

    p(f"\n{'─'*70}")
    p(f"  {m['id']}  {m['league']}  {m['home']} vs {m['away']}")
    p(f"{'─'*70}")
    p(f"  欧赔: {oh}/{od}/{oa}  亚盘: 主让{abs(ah_hc)}球")
    if flags: p(f"  规则: {' | '.join(flags)}")

    p(f"\n  ◆ 胜平负")
    p(f"    主胜 {hp:.1%}  平局 {dp:.1%}  客胜 {ap:.1%}")
    p(f"    预测: {pred} {conf}")

    p(f"\n  ◆ 最可能比分")
    for h,a,prob in scores:
        tag = '主胜' if h>a else ('平' if h==a else '客胜')
        p(f"    {h}-{a}  {prob:.1%}  [{tag}]")

    p(f"\n  ◆ 总进球分布")
    for g,pg in enumerate(p_goals[:5]):
        p(f"    {g}球: {pg:.1%}")

    p(f"\n  ◆ 大小球 (预期{mu:.1f}球)")
    p(f"    大2.5: {o25:.1%}  小2.5: {u25:.1%}")
    p(f"    大3.5: {o35:.1%}  小3.5: {u35:.1%}")
    ou = '大2.5' if o25>0.58 else ('小2.5' if u25>0.55 else '中性(2-3球)')
    p(f"    倾向: {ou}")

    p(f"\n  ◆ 亚盘 主让{abs(ah_hc)}球")
    p(f"    赢盘: {aw:.1%}  走水: {ad:.1%}  输盘: {al:.1%}")
    if aw < 0.38 and ah_hc == -1:
        p(f"    ⚠ 主让1球赢盘概率低, 小胜1球走水风险高")
    elif ah_hc == -2 and aw < 0.30:
        p(f"    ⚠ 深盘-2球, 主赢3球以上概率很低")
    elif ad > 0.22:
        p(f"    → 走水概率偏高, 主队可能刚好赢{abs(ah_hc)}球")

    # 综合建议
    p(f"\n  ◆ 综合参考")
    score_top = f"{scores[0][0]}-{scores[0][1]}"
    p(f"    最可能比分: {score_top}")
    p(f"    胜平负: {pred}")
    p(f"    大小球: {ou}")
    if aw > 0.40:
        p(f"    亚盘: 主让{abs(ah_hc)}球有一定价值")
    elif ad > 0.20:
        p(f"    亚盘: 走水概率高, 不建议重仓")
    else:
        p(f"    亚盘: 赢盘概率偏低, 谨慎")

p(f"\n{'='*80}")
p("  预测完成 — 仅供参考")
p("="*80)

with open('d:/football_tools/fetchers/scripts/predict_20260529_v2.txt','w',encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('\n'.join(lines))