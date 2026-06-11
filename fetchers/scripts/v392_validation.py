"""
v3.9.2验证: 赛季末均衡比赛draw回调规则
DB发现: 赛季末5轮+均衡(both<3.0)+dt30: actual=36.5%, implied=31.4%, gap=+5.14%
规则: late_season + balanced(odds_h<3.0 & odds_a<3.0) + market_draw>=0.28 → draw += X
"""
import sys, io, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

import sqlite3
from fetchers.analysis.models.enhanced_linear import EnhancedLinearModel

model = EnhancedLinearModel()

conn = sqlite3.connect('data/football_v2.db')
conn.row_factory = sqlite3.Row

# 获取有赔率和结果的比赛
c = conn.cursor()
c.execute("""SELECT m.match_id, m.result,
    mo.b365_home as oh, mo.b365_draw as od, mo.b365_away as oa,
    m.league_id,
    SUBSTR(m.match_code, 1, INSTR(m.match_code, '_')-1) as league_code,
    m.round_num
FROM matches m JOIN match_odds mo ON m.match_id = mo.match_id
WHERE mo.b365_home IS NOT NULL AND mo.b365_draw IS NOT NULL AND mo.b365_away IS NOT NULL
AND m.result IN ('H','D','A') AND mo.b365_home > 1.0 AND mo.b365_draw > 1.0 AND mo.b365_away > 1.0
""")

rows = c.fetchall()
print(f"Total matches: {len(rows)}")

# 构建联赛最大轮次
league_max_round = {}
for r in rows:
    lc, rn = r['league_code'], r['round_num']
    if lc and rn:
        if lc not in league_max_round or rn > league_max_round[lc]:
            league_max_round[lc] = rn

# 预查询联赛信息
league_info = {}
c2 = conn.cursor()
c2.execute("SELECT league_id, name_en, competition_type FROM leagues")
for lr in c2.fetchall():
    league_info[lr['league_id']] = (lr['name_en'] or '', lr['competition_type'] or '')

cup_kw_lower = [kw.lower() for kw in model.CUP_KEYWORDS]
div2_kw_lower = [kw.lower() for kw in model.DIV2_KEYWORDS]

def apply_v391(hp, dp, ap, oh, od, oa, league_name, is_cup, is_div2):
    """v3.9.1全部规则"""
    # cup draw reduce
    if is_cup or any(kw in (league_name or '').lower() for kw in cup_kw_lower):
        dp -= model.CUP_DP_REDUCE
        nd = hp + ap
        if nd > 0: hp += model.CUP_DP_REDUCE*(hp/nd); ap += model.CUP_DP_REDUCE*(ap/nd)
        hp, dp, ap = model._normalize_probs(hp, dp, ap)

    # league draw reduce
    if model.LEAGUE_DP_REDUCE and league_name:
        for lk, rv in model.LEAGUE_DP_REDUCE.items():
            if lk.lower() in league_name.lower():
                dp -= rv; nd = hp + ap
                if nd > 0: hp += rv*(hp/nd); ap += rv*(ap/nd)
                hp, dp, ap = model._normalize_probs(hp, dp, ap)
                break

    # dt30 boost
    md = 1/od if od > 1 else 0
    if md > 0:
        for threshold, dt_boost in sorted(model.DRAW_PROB_THRESHOLDS.items(), reverse=True):
            if md >= threshold:
                ab = model.DIV2_DT30_BOOST if (is_div2 and threshold==0.30) else dt_boost
                if ab > 0:
                    dp += ab; nd = hp+ap
                    if nd > 0: hp -= ab*(hp/nd); ap -= ab*(ap/nd)
                    hp, dp, ap = model._normalize_probs(hp, dp, ap)
                break

    # dt30 reduce
    if md > 0:
        for threshold in sorted(model.DRAW_PROB_THRESHOLDS.keys(), reverse=True):
            if md >= threshold:
                if threshold == 0.30 and model.DT30_BASE_DP_REDUCE > 0:
                    br = model.DIV2_DT30_BASE_DP_REDUCE if is_div2 else model.DT30_BASE_DP_REDUCE
                    if br > 0:
                        dp -= br; nd = hp+ap
                        if nd > 0: hp += br*(hp/nd); ap += br*(ap/nd)
                        hp, dp, ap = model._normalize_probs(hp, dp, ap)
                break

    return hp, dp, ap

# 预计算所有比赛的v3.9.1结果和元数据
precomputed = []
for r in rows:
    result = r['result']
    oh, od, oa = r['oh'], r['od'], r['oa']
    lcode, rnd = r['league_code'], r['round_num']
    lid = r['league_id']

    rh, rd, ra = 1/oh, 1/od, 1/oa
    t = rh + rd + ra
    hp, dp, ap = rh/t, rd/t, ra/t

    ln_info = league_info.get(lid, ('', ''))
    league_name = ln_info[0]
    is_cup = ln_info[1] == 'cup'
    is_div2 = any(kw in (league_name or '').lower() for kw in div2_kw_lower)

    hp, dp, ap = apply_v391(hp, dp, ap, oh, od, oa, league_name, is_cup, is_div2)

    market_draw = 1/od if od > 1 else 0
    is_balanced = oh < 3.0 and oa < 3.0

    # 计算各window的is_late
    late_windows_map = {}
    for w in [3, 4, 5, 6]:
        is_late = False
        if lcode and rnd and lcode in league_max_round:
            if league_max_round[lcode] >= 20 and rnd > (league_max_round[lcode] - w):
                is_late = True
        late_windows_map[w] = is_late

    precomputed.append({
        'result': result,
        'hp': hp, 'dp': dp, 'ap': ap,
        'is_balanced': is_balanced,
        'market_draw': market_draw,
        'late': late_windows_map,
    })

N = len(precomputed)

# 基线
base_correct = sum(1 for m in precomputed if ('H' if m['hp']>=m['dp'] and m['hp']>=m['ap'] else ('D' if m['dp']>=m['ap'] else 'A')) == m['result'])
base_brier = sum(
    ((1 if m['result']=='H' else 0)-m['hp'])**2 +
    ((1 if m['result']=='D' else 0)-m['dp'])**2 +
    ((1 if m['result']=='A' else 0)-m['ap'])**2
    for m in precomputed
)
base_acc = base_correct / N
base_br = base_brier / N

lines = []
def p(s=""): lines.append(s)

p("=" * 80)
p("  v3.9.2验证: 赛季末均衡比赛draw回调规则")
p("=" * 80)
p(f"\n  总比赛: {N}")
p(f"  v3.9.1基线: {base_acc:.2%} ({base_correct}/{N}), Brier={base_br:.4f}")
p("")
p("  DB发现:")
p("  赛季末5轮+均衡(both<3.0)+dt30: actual=36.5%, implied=31.4%, gap=+5.14%")
p("  规则: late_season + balanced(oh<3.0 & oa<3.0) + market_draw>=0.28 → draw += boost")
p("")

# 搜索
p(f"  {'窗口':>4s} {'boost':>6s} {'准确率':>8s} {'Brier':>8s} {'Δ准确':>7s} {'ΔBrier':>7s} {'受影响':>5s}")
p("  " + "-" * 55)

best_delta = 0
best_w, best_b = 0, 0

for window in [3, 4, 5, 6]:
    for boost in [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04]:
        correct = 0
        brier = 0.0
        affected = 0

        for m in precomputed:
            hp, dp, ap = m['hp'], m['dp'], m['ap']

            is_trigger = m['late'][window] and m['is_balanced'] and m['market_draw'] >= 0.28
            if is_trigger:
                dp += boost
                nd = hp + ap
                if nd > 0: hp -= boost*(hp/nd); ap -= boost*(ap/nd)
                hp, dp, ap = model._normalize_probs(hp, dp, ap)
                affected += 1

            pred = 'H' if hp>=dp and hp>=ap else ('D' if dp>=ap else 'A')
            if pred == m['result']: correct += 1
            brier += ((1 if m['result']=='H' else 0)-hp)**2 + ((1 if m['result']=='D' else 0)-dp)**2 + ((1 if m['result']=='A' else 0)-ap)**2

        acc = correct / N
        bri = brier / N
        da = acc - base_acc
        db = bri - base_br
        tag = ''
        if da > best_delta:
            best_delta = da
            best_w, best_b = window, boost
            tag = ' ★BEST'
        elif da > 0:
            tag = ' ★'

        p(f"  {window:>4d} {boost:>6.3f} {acc:>7.2%} {bri:>8.4f} {da:>+6.2%} {db:>+7.4f} {affected:>5d}{tag}")

p(f"\n  最优: window={best_w}, boost={best_b:.3f}, Δ={best_delta:+.2%} (net{int(best_delta*N):+d})")

# 也测试market_draw阈值
p("\n  ─── draw阈值搜索 (window=5) ───")
p(f"  {'阈值':>6s} {'boost':>6s} {'准确率':>8s} {'Δ准确':>7s} {'受影响':>5s}")

for threshold in [0.25, 0.26, 0.28, 0.30]:
    for boost in [0.01, 0.015, 0.02, 0.025]:
        correct = 0
        brier = 0.0
        affected = 0

        for m in precomputed:
            hp, dp, ap = m['hp'], m['dp'], m['ap']
            is_trigger = m['late'][5] and m['is_balanced'] and m['market_draw'] >= threshold
            if is_trigger:
                dp += boost
                nd = hp + ap
                if nd > 0: hp -= boost*(hp/nd); ap -= boost*(ap/nd)
                hp, dp, ap = model._normalize_probs(hp, dp, ap)
                affected += 1

            pred = 'H' if hp>=dp and hp>=ap else ('D' if dp>=ap else 'A')
            if pred == m['result']: correct += 1
            brier += ((1 if m['result']=='H' else 0)-hp)**2 + ((1 if m['result']=='D' else 0)-dp)**2 + ((1 if m['result']=='A' else 0)-ap)**2

        acc = correct / N
        da = acc - base_acc
        db = brier/N - base_br
        p(f"  {threshold:>6.2f} {boost:>6.3f} {acc:>7.2%} {da:>+6.2%} {affected:>5d}")

p(f"\n{'=' * 80}")
p("  验证完成")
p("=" * 80)

with open('d:/football_tools/fetchers/scripts/v392_validation.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('\n'.join(lines))

conn.close()
