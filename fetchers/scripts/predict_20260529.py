"""
v3.9.1手动预测: 2026-05-29 5场比赛
使用用户提供的欧赔数据直接预测
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

from fetchers.analysis.models.enhanced_linear import EnhancedLinearModel

# 用户提供的比赛数据
# 格式: (比赛ID, 联赛, 主队, 客队, 欧赔主, 欧赔平, 欧赔客, 亚盘让球)
matches = [
    {
        'id': '001', 'league': '友谊赛', 'league_standard': 'friendly',
        'home': 'Republic of Ireland', 'away': 'Qatar',
        'odds_h': 1.51, 'odds_d': 3.48, 'odds_a': 5.60,
        'ah': -1, 'ah_h': 2.80, 'ah_d': 3.20, 'ah_a': 2.18,
        'rank_h': 59, 'rank_a': 55, 'weather': '',
    },
    {
        'id': '002', 'league': '葡超', 'league_standard': 'primeira_liga',
        'home': 'Casa Pia', 'away': 'Durens',
        'odds_h': 2.10, 'odds_d': 2.77, 'odds_a': 3.42,
        'ah': -1, 'ah_h': 5.05, 'ah_d': 3.40, 'ah_a': 1.57,
        'rank_h': None, 'rank_a': None, 'weather': '',
    },
    {
        'id': '003', 'league': '解放者杯', 'league_standard': 'copa_libertadores',
        'home': 'Porteno Hill', 'away': 'Sporting Cristal',
        'odds_h': 1.52, 'odds_d': 3.45, 'odds_a': 5.50,
        'ah': -1, 'ah_h': 2.95, 'ah_d': 2.98, 'ah_a': 2.20,
        'rank_h': 2, 'rank_a': 4, 'weather': '晴',
    },
    {
        'id': '004', 'league': '解放者杯', 'league_standard': 'copa_libertadores',
        'home': 'Palmeiras', 'away': 'Junior Barranquilla',
        'odds_h': 1.13, 'odds_d': 5.95, 'odds_a': 13.00,
        'ah': -2, 'ah_h': 2.85, 'ah_d': 3.53, 'ah_a': 2.02,
        'rank_h': 1, 'rank_a': 2, 'weather': '多云',
    },
    {
        'id': '005', 'league': '解放者杯', 'league_standard': 'copa_libertadores',
        'home': 'Boca Juniors', 'away': 'Universidad Catolica',
        'odds_h': 1.27, 'odds_d': 4.50, 'odds_a': 8.35,
        'ah': -1, 'ah_h': 2.09, 'ah_d': 3.13, 'ah_a': 3.02,
        'rank_h': 2, 'rank_a': 4, 'weather': '多云',
    },
]

model = EnhancedLinearModel()

lines = []
def p(s=""): lines.append(s)

p("=" * 70)
p("  2026-05-29 v3.9.1预测")
p("=" * 70)

for m in matches:
    # 从欧赔计算隐含概率
    oh, od, oa = m['odds_h'], m['odds_d'], m['odds_a']
    raw_h = 1/oh; raw_d = 1/od; raw_a = 1/oa
    total = raw_h + raw_d + raw_a
    # 去除margin后的隐含概率
    imp_h = raw_h / total
    imp_d = raw_d / total
    imp_a = raw_a / total

    p(f"\n  {m['id']} {m['league']} {m['home']} vs {m['away']}")
    p(f"    欧赔: {oh:.2f} / {od:.2f} / {oa:.2f}")
    p(f"    隐含概率: H={imp_h:.1%} D={imp_d:.1%} A={imp_a:.1%}")
    p(f"    亚盘: {m['ah']} ({m['ah_h']:.2f}/{m['ah_d']:.2f}/{m['ah_a']:.2f})")

    # v3.9.1核心逻辑
    hp, dp, ap = imp_h, imp_d, imp_a

    # 1. 杯赛减draw (解放者杯是杯赛)
    is_cup = any(kw in m['league_standard'] for kw in model.CUP_KEYWORDS)
    # 解放者杯关键词
    is_copa = 'libertadores' in m['league_standard'].lower()
    is_cup = is_cup or is_copa  # copa_libertadores匹配

    if is_cup:
        p(f"    [杯赛] 减draw {model.CUP_DP_REDUCE}")
        dp -= model.CUP_DP_REDUCE
        nd = hp + ap
        if nd > 0:
            hp += model.CUP_DP_REDUCE * (hp / nd)
            ap += model.CUP_DP_REDUCE * (ap / nd)
        hp, dp, ap = model._normalize_probs(hp, dp, ap)

    # 2. prima_liga减draw
    is_prima = 'primeira_liga' in m['league_standard'].lower()
    if is_prima:
        p(f"    [葡超] 减draw 0.02")
        dp -= 0.02
        nd = hp + ap
        if nd > 0:
            hp += 0.02 * (hp / nd)
            ap += 0.02 * (ap / nd)
        hp, dp, ap = model._normalize_probs(hp, dp, ap)

    # 3. draw_threshold规则
    if imp_d >= 0.30:
        p(f"    [dt30] draw隐含≥30%: boost +0.01 → reduce(0.01+ah0)")
        dp += 0.01
        nd = hp + ap
        if nd > 0: hp -= 0.01*(hp/nd); ap -= 0.01*(ap/nd)
        hp, dp, ap = model._normalize_probs(hp, dp, ap)
        # AH=0? 亚盘让球数
        is_ah0 = abs(m['ah']) < 0.01
        reduce_val = model.DT30_BASE_DP_REDUCE + (model.DT30_AH0_EXTRA_DP_REDUCE if is_ah0 else 0)
        if is_prima:  # 二级联赛(这里prima不是div2但用类似逻辑)
            reduce_val = 0.02 + (0.02 if is_ah0 else 0)
        dp -= reduce_val
        nd = hp + ap
        if nd > 0: hp += reduce_val*(hp/nd); ap += reduce_val*(ap/nd)
        hp, dp, ap = model._normalize_probs(hp, dp, ap)
    elif imp_d >= 0.28:
        p(f"    [dt28] draw隐含≥28%: boost +0.01")
        dp += 0.01; nd = hp + ap
        if nd > 0: hp -= 0.01*(hp/nd); ap -= 0.01*(ap/nd)
        hp, dp, ap = model._normalize_probs(hp, dp, ap)
    elif imp_d >= 0.26:
        p(f"    [dt26] draw隐含≥26%: boost +0.005")
        dp += 0.005; nd = hp + ap
        if nd > 0: hp -= 0.005*(hp/nd); ap -= 0.005*(ap/nd)
        hp, dp, ap = model._normalize_probs(hp, dp, ap)

    # 4. 南美杯赛冷门区
    is_sa = is_copa
    if is_sa and 1.35 <= oh <= 1.50:
        p(f"    [南美冷门区] 赔率{oh:.2f}在1.35-1.50")
        hp -= 0.02; dp += 0.01; ap += 0.01
        hp, dp, ap = model._normalize_probs(hp, dp, ap)

    hp, dp, ap = model._normalize_probs(hp, dp, ap)

    # 预测结果
    pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
    pred_cn = {'home': '主胜', 'draw': '平局', 'away': '客胜'}[pred]

    # 信心等级
    max_prob = max(hp, dp, ap)
    if max_prob >= 0.60:
        confidence = '高'
    elif max_prob >= 0.50:
        confidence = '中'
    elif max_prob >= 0.45:
        confidence = '低'
    else:
        confidence = '极低'

    p(f"    最终概率: H={hp:.1%} D={dp:.1%} A={ap:.1%}")
    p(f"    >>> 预测: {pred_cn} (信心: {confidence})")

    # 亚盘建议
    if m['ah'] < 0:  # 主让球
        ah_val = abs(m['ah'])
        if ah_val >= 2:
            ah_note = '深盘, 主胜2+球难度大'
        elif ah_val >= 1:
            ah_note = '主让1球, 需赢2球以上才能赢盘'
        else:
            ah_note = ''
        p(f"    亚盘参考: 主让{ah_val:.0f}球 {ah_note}")

p(f"\n{'=' * 70}")
p("  预测完成 — 仅供参考, 理性投注")
p("=" * 70)

OUTPUT = 'd:/football_tools/fetchers/scripts/predict_20260529.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('\n'.join(lines))