"""
v3.9.1完整预测: 比分/大小球/胜平负 + 亚盘分析
基于用户提供的欧赔+亚盘数据，用泊松模型推导比分和大小球
"""
import sys, io, math, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

from fetchers.analysis.models.enhanced_linear import EnhancedLinearModel

model = EnhancedLinearModel()

# 根据欧赔推导泊松参数(lambda_home, lambda_away)
# 方法: 欧赔→胜平负概率 → 用draw概率反推总进球期望 → 分配主客进球
def odds_to_poisson(oh, od, oa, ah_handicap=None, ah_h=None, ah_d=None, ah_a=None):
    """从欧赔推导泊松参数"""
    raw_h = 1/oh; raw_d = 1/od; raw_a = 1/oa
    total = raw_h + raw_d + raw_a
    ph = raw_h/total; pd = raw_d/total; pa = raw_a/total

    # draw概率反推总进球: pd ≈ exp(-μ) * I0(2√(ρ)) ≈ exp(-μ) where ρ=λ_h*λ_a/μ
    # 简化: 用经验公式 pd = 1/(1 + 0.3*μ^1.5) → μ = ((1/pd - 1)/0.3)^(2/3)
    if pd > 0 and pd < 1:
        mu = ((1/pd - 1)/0.3) ** (2/3)
    else:
        mu = 2.5

    # 主客分配: 主队进球比例 = ph/(ph+pa), 客队 = pa/(ph+pa)
    p_non_draw = ph + pa
    if p_non_draw > 0:
        ratio_h = ph / p_non_draw
        ratio_a = pa / p_non_draw
    else:
        ratio_h = 0.6; ratio_a = 0.4

    # 用亚盘信息修正
    if ah_handicap is not None and ah_h is not None and ah_a is not None:
        # 亚盘让球数反映实力差距
        # 让1球 → 主队多进1球, 让2球 → 多2球
        if ah_handicap < 0:  # 主让
            expected_diff = abs(ah_handicap)
            # λ_h - λ_a ≈ expected_diff
            # λ_h + λ_a = mu
            lam_h = (mu + expected_diff) / 2
            lam_a = (mu - expected_diff) / 2
            if lam_a < 0.3: lam_a = 0.3
            if lam_h < 0.5: lam_h = 0.5
            return ph, pd, pa, lam_h, lam_a, mu

    lam_h = mu * ratio_h * 1.15  # 主场加成15%
    lam_a = mu * ratio_a * 0.85

    return ph, pd, pa, lam_h, lam_a, mu

def poisson_prob(lam_h, lam_a, h_goals, a_goals):
    """计算特定比分的泊松概率"""
    p_h = math.exp(-lam_h) * (lam_h ** h_goals) / math.factorial(h_goals)
    p_a = math.exp(-lam_a) * (lam_a ** a_goals) / math.factorial(a_goals)
    return p_h * p_a

def top_scores(lam_h, lam_a, n=8):
    """返回最可能的n个比分"""
    scores = []
    for h in range(6):
        for a in range(6):
            if h + a > 7: continue
            p = poisson_prob(lam_h, lam_a, h, a)
            scores.append((h, a, p))
    scores.sort(key=lambda x: -x[2])
    total_p = sum(s[2] for s in scores[:n])
    return scores[:n]

def over_under_probs(lam_h, lam_a):
    """计算大小球概率"""
    # 总进球 = Poisson(lam_h + lam_a)
    mu = lam_h + lam_a
    p_under = 0; p_over = 0
    for g in range(10):
        p_g = math.exp(-mu) * (mu ** g) / math.factorial(g)
        if g < 2: p_under += p_g
        elif g == 2:
            p_under += p_g * 0.5  # 2球算半
            p_over += p_g * 0.5
        else: p_over += p_g
    # 2.5球
    p_u25 = sum(math.exp(-mu) * (mu ** g) / math.factorial(g) for g in range(3))
    p_o25 = 1 - p_u25
    # 3.5球
    p_u35 = sum(math.exp(-mu) * (mu ** g) / math.factorial(g) for g in range(4))
    p_o35 = 1 - p_u35
    return p_o25, p_u25, p_o35, p_u35, mu

# 5场比赛数据
matches = [
    {
        'id': '001', 'league': '友谊赛', 'league_standard': 'friendly',
        'home': '爱尔兰', 'home_en': 'Republic of Ireland',
        'away': '卡塔尔', 'away_en': 'Qatar',
        'odds_h': 1.51, 'odds_d': 3.48, 'odds_a': 5.60,
        'ah': -1, 'ah_h': 2.80, 'ah_d': 3.20, 'ah_a': 2.18,
    },
    {
        'id': '002', 'league': '葡超', 'league_standard': 'primeira_liga',
        'home': '卡萨皮亚', 'home_en': 'Casa Pia',
        'away': '杜连斯', 'away_en': 'Durens',
        'odds_h': 2.10, 'odds_d': 2.77, 'odds_a': 3.42,
        'ah': -1, 'ah_h': 5.05, 'ah_d': 3.40, 'ah_a': 1.57,
    },
    {
        'id': '003', 'league': '解放者杯', 'league_standard': 'copa_libertadores',
        'home': '波特诺山丘', 'home_en': 'Cerro Porteno',
        'away': '水晶体育', 'away_en': 'Sporting Cristal',
        'odds_h': 1.52, 'odds_d': 3.45, 'odds_a': 5.50,
        'ah': -1, 'ah_h': 2.95, 'ah_d': 2.98, 'ah_a': 2.20,
    },
    {
        'id': '004', 'league': '解放者杯', 'league_standard': 'copa_libertadores',
        'home': '帕尔梅拉斯', 'home_en': 'Palmeiras',
        'away': '巴兰基亚青年', 'away_en': 'Junior Barranquilla',
        'odds_h': 1.13, 'odds_d': 5.95, 'odds_a': 13.00,
        'ah': -2, 'ah_h': 2.85, 'ah_d': 3.53, 'ah_a': 2.02,
    },
    {
        'id': '005', 'league': '解放者杯', 'league_standard': 'copa_libertadores',
        'home': '博卡青年', 'home_en': 'Boca Juniors',
        'away': '天主大学', 'away_en': 'Universidad Catolica',
        'odds_h': 1.27, 'odds_d': 4.50, 'odds_a': 8.35,
        'ah': -1, 'ah_h': 2.09, 'ah_d': 3.13, 'ah_a': 3.02,
    },
]

lines = []
def p(s=""): lines.append(s)

p("=" * 80)
p("  2026-05-29 v3.9.1 完整预测 (比分/大小球/胜平负/亚盘)")
p("=" * 80)

for m in matches:
    oh, od, oa = m['odds_h'], m['odds_d'], m['odds_a']
    ah_hc = m['ah']

    # 计算隐含概率
    ph_raw, pd_raw, pa_raw, lam_h, lam_a, mu = odds_to_poisson(
        oh, od, oa, ah_hc, m['ah_h'], m['ah_a'])

    # v3.9.1规则调整
    hp, dp, ap = ph_raw, pd_raw, pa_raw

    is_cup = any(kw in m['league_standard'] for kw in model.CUP_KEYWORDS) or 'libertadores' in m['league_standard'].lower()
    is_prima = 'primeira_liga' in m['league_standard'].lower()

    flags = []
    if is_cup:
        dp -= model.CUP_DP_REDUCE
        nd = hp + ap
        if nd > 0: hp += model.CUP_DP_REDUCE*(hp/nd); ap += model.CUP_DP_REDUCE*(ap/nd)
        hp, dp, ap = model._normalize_probs(hp, dp, ap)
        flags.append('cup_draw_reduce')
    if is_prima:
        dp -= 0.02; nd = hp + ap
        if nd > 0: hp += 0.02*(hp/nd); ap += 0.02*(ap/nd)
        hp, dp, ap = model._normalize_probs(hp, dp, ap)
        flags.append('prima_draw_reduce')
    if pd_raw >= 0.30:
        if is_prima:
            boost = 0.00; base = 0.02; ah0_e = 0.02
        else:
            boost = 0.01; base = 0.01; ah0_e = 0.02
        if boost > 0:
            dp += boost; nd = hp+ap
            if nd > 0: hp -= boost*(hp/nd); ap -= boost*(ap/nd)
            hp, dp, ap = model._normalize_probs(hp, dp, ap)
        is_ah0 = abs(ah_hc) < 0.01
        rv = base + (ah0_e if is_ah0 else 0)
        if rv > 0:
            dp -= rv; nd = hp+ap
            if nd > 0: hp += rv*(hp/nd); ap += rv*(ap/nd)
            hp, dp, ap = model._normalize_probs(hp, dp, ap)
        flags.append(f'dt30_reduce')
    # 南美杯赛冷门区
    if is_cup and 1.35 <= oh <= 1.50:
        hp -= 0.02; dp += 0.01; ap += 0.01
        hp, dp, ap = model._normalize_probs(hp, dp, ap)
        flags.append('sa_upset_zone')

    hp, dp, ap = model._normalize_probs(hp, dp, ap)

    # 预测结果
    pred = max(['主胜', '平局', '客胜'], key=lambda x: {'主胜': hp, '平局': dp, '客胜': ap}[x])
    max_prob = max(hp, dp, ap)

    # 用调整后概率重新推导泊松参数(更准确)
    # draw概率变了,需要更新lam
    pd_new = dp
    if pd_new > 0 and pd_new < 1:
        mu_new = ((1/pd_new - 1)/0.3) ** (2/3)
    else:
        mu_new = mu
    # 保持实力差距比例
    if ph_raw + pa_raw > 0:
        h_ratio = hp / (hp + ap) if (hp + ap) > 0 else 0.6
    else:
        h_ratio = 0.6
    # 亚盘修正实力差距
    if ah_hc < 0:
        expected_diff = abs(ah_hc)
        lam_h_new = (mu_new + expected_diff) / 2
        lam_a_new = (mu_new - expected_diff) / 2
        if lam_a_new < 0.25: lam_a_new = 0.25
        if lam_h_new < 0.5: lam_h_new = 0.5
    else:
        lam_h_new = mu_new * h_ratio * 1.15
        lam_a_new = mu_new * (1-h_ratio) * 0.85

    # 最可能比分
    scores = top_scores(lam_h_new, lam_a_new, 8)

    # 大小球概率
    p_o25, p_u25, p_o35, p_u35, mu_final = over_under_probs(lam_h_new, lam_a_new)

    # 信心等级
    if max_prob >= 0.65: conf = '★★★'
    elif max_prob >= 0.55: conf = '★★☆'
    elif max_prob >= 0.45: conf = '★☆☆'
    else: conf = '☆☆☆'

    # 亚盘建议
    if ah_hc == -1:
        ah_prob_h = sum(poisson_prob(lam_h_new, lam_a_new, h, a) for h in range(6) for a in range(6) if h-a >= 2)
        ah_prob_d = sum(poisson_prob(lam_h_new, lam_a_new, h, a) for h in range(6) for a in range(6) if h-a == 1)
        ah_prob_a = sum(poisson_prob(lam_h_new, lam_a_new, h, a) for h in range(6) for a in range(6) if h-a <= 0)
    elif ah_hc == -2:
        ah_prob_h = sum(poisson_prob(lam_h_new, lam_a_new, h, a) for h in range(7) for a in range(7) if h-a >= 3)
        ah_prob_d = sum(poisson_prob(lam_h_new, lam_a_new, h, a) for h in range(7) for a in range(7) if h-a == 2)
        ah_prob_a = sum(poisson_prob(lam_h_new, lam_a_new, h, a) for h in range(7) for a in range(7) if h-a <= 1)
    else:
        ah_prob_h = hp; ah_prob_d = dp; ah_prob_a = ap

    p(f"\n{'─' * 70}")
    p(f"  {m['id']}  {m['league']}  {m['home']} vs {m['away']}")
    p(f"{'─' * 70}")
    p(f"  欧赔: {oh:.2f} / {od:.2f} / {oa:.2f}")
    p(f"  亚盘: 主让{abs(ah_hc):.0f}球 ({m['ah_h']:.2f}/{m['ah_d']:.2f}/{m['ah_a']:.2f})")

    p(f"\n  【胜平负】")
    p(f"    主胜 {hp:.1%}  平局 {dp:.1%}  客胜 {ap:.1%}")
    if flags:
        p(f"    触发规则: {', '.join(flags)}")
    p(f"    ▶ 预测: {pred} {conf}")

    p(f"\n  【最可能比分 TOP8】")
    for h, a, prob in scores:
        result_tag = '主胜' if h > a else ('平局' if h == a else '客胜')
        p(f"    {h}-{a}  {prob:.1%}  ({result_tag})")

    p(f"\n  【大小球】")
    p(f"    预期总进球: {mu_final:.1f}")
    p(f"    大2.5球: {p_o25:.1%}  小2.5球: {p_u25:.1%}")
    p(f"    大3.5球: {p_o35:.1%}  小3.5球: {p_u35:.1%}")
    ou_pred = '大2.5球' if p_o25 > 0.55 else ('小2.5球' if p_u25 > 0.55 else '中性')
    p(f"    ▶ 倾向: {ou_pred}")

    p(f"\n  【亚盘分析】主让{abs(ah_hc):.0f}球")
    if ah_hc == -1:
        p(f"    赢盘(主赢2+): {ah_prob_h:.1%}")
        p(f"    走水(主赢1球): {ah_prob_d:.1%}")
        p(f"    输盘(平/客胜): {ah_prob_a:.1%}")
        if ah_prob_h < 0.40:
            p(f"    ▶ 主让1球赢盘概率低, 注意走水或输盘风险")
        elif ah_prob_d > 0.25:
            p(f"    ▶ 走水概率较高, 主队小胜1球可能性大")
        else:
            p(f"    ▶ 主让1球有一定价值")
    elif ah_hc == -2:
        p(f"    赢盘(主赢3+): {ah_prob_h:.1%}")
        p(f"    走水(主赢2球): {ah_prob_d:.1%}")
        p(f"    输盘(主赢0-1球): {ah_prob_a:.1%}")
        if ah_prob_h < 0.35:
            p(f"    ▶ 深盘风险大, 主赢3+球概率低")
        else:
            p(f"    ▶ 深盘有翻盘可能, 但风险较高")

p(f"\n{'=' * 80}")
p("  预测完成 — 仅供参考, 理性分析")
p("=" * 80)

OUTPUT = 'd:/football_tools/fetchers/scripts/predict_20260529_full.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('\n'.join(lines))