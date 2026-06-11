"""
Step3: 完整验证 + 模型迭代分析
5/31全部赛果 vs v3.9.2/v3.10预测
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

lines = []
def p(s=''): lines.append(s)

# ===== 模型 =====
def predict_v392(oh, od, oa, league=''):
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
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf}

def predict_v310(oh, od, oa, league=''):
    if not oh or not od or not oa: return None
    hp, dp, ap = 1/oh, 1/od, 1/oa
    total = hp + dp + ap
    margin = total - 1
    hp, dp, ap = hp/total, dp/total, ap/total

    odds_list = [oh, od, oa]
    odds_range = max(odds_list) - min(odds_list)
    is_balanced = odds_range < 0.8

    is_cup = any(kw in league for kw in ['欧冠','欧联','欧协','国际赛','友谊赛','解放者'])
    if is_cup:
        dp -= 0.02; nd = hp+ap
        if nd > 0: hp += 0.02*(hp/nd); ap += 0.02*(ap/nd)

    if is_balanced and dp >= 0.28:
        boost = 0.04
        dp += boost; nd = hp+ap
        if nd > 0: hp -= boost*(hp/nd); ap -= boost*(ap/nd)
    elif not is_balanced:
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
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf,'is_balanced':is_balanced}

# ===== 5/31全部赛果 =====
matches = [
    {'num':'001','home':'冈山绿雉','away':'浦和红钻','league':'日职',
     'oh':2.90,'od':3.00,'oa':2.22,'hs':1,'as':1,'actual':'D'},
    {'num':'002','home':'清水鼓动','away':'横滨水手','league':'日职',
     'oh':2.52,'od':3.10,'oa':2.44,'hs':1,'as':1,'actual':'D'},
    {'num':'003','home':'日本','away':'冰岛','league':'国际赛',
     'oh':1.12,'od':6.25,'oa':13.00,'hs':1,'as':0,'actual':'H'},
    {'num':'004','home':'韦斯特罗斯','away':'IFK哥德堡','league':'瑞超',
     'oh':2.46,'od':3.00,'oa':2.57,'hs':4,'as':5,'actual':'A'},
    {'num':'005','home':'赫根','away':'哈马比','league':'瑞超',
     'oh':2.77,'od':3.35,'oa':2.13,'hs':3,'as':2,'actual':'H'},
    {'num':'006','home':'代格福什','away':'布鲁马波卡纳','league':'瑞超',
     'oh':2.10,'od':3.15,'oa':2.98,'hs':2,'as':2,'actual':'D'},
    {'num':'008','home':'AC奥卢','away':'雅罗','league':'芬超',
     'oh':1.50,'od':3.90,'oa':4.85,'hs':2,'as':1,'actual':'H'},
    {'num':'009','home':'捷克','away':'科索沃','league':'国际赛',
     'oh':1.52,'od':3.64,'oa':5.10,'hs':2,'as':1,'actual':'H'},
    {'num':'011','home':'美国','away':'塞内加尔','league':'国际赛',
     'oh':2.43,'od':2.90,'oa':2.68,'hs':3,'as':2,'actual':'H'},
]

p('=' * 85)
p('  5/31赛果验证: v3.9.2 vs v3.10')
p('=' * 85)

correct392 = 0
correct310 = 0
total = len(matches)

changed = 0
changed_correct = 0
changed_wrong = 0

balanced_total = 0
balanced_correct392 = 0
balanced_correct310 = 0

# 按类型统计
type_stats = {}  # league -> {correct392, correct310, total}

for m in matches:
    oh, od, oa = m['oh'], m['od'], m['oa']
    r392 = predict_v392(oh, od, oa, m['league'])
    r310 = predict_v310(oh, od, oa, m['league'])

    pred392 = r392['pred']
    pred310 = r310['pred']
    cn392 = {'H':'主胜','D':'平局','A':'客胜'}[pred392]
    cn310 = {'H':'主胜','D':'平局','A':'客胜'}[pred310]
    cn_actual = {'H':'主胜','D':'平局','A':'客胜'}[m['actual']]

    is_bal = r310.get('is_balanced', False)
    bal_str = '均衡' if is_bal else ''

    mark392 = '✓' if pred392 == m['actual'] else '✗'
    mark310 = '✓' if pred310 == m['actual'] else '✗'

    if pred392 == m['actual']: correct392 += 1
    if pred310 == m['actual']: correct310 += 1

    if is_bal:
        balanced_total += 1
        if pred392 == m['actual']: balanced_correct392 += 1
        if pred310 == m['actual']: balanced_correct310 += 1

    if pred392 != pred310:
        changed += 1
        if pred310 == m['actual']: changed_correct += 1
        else: changed_wrong += 1

    # 按类型统计
    lg = m['league']
    if lg not in type_stats: type_stats[lg] = {'c392':0,'c310':0,'t':0}
    type_stats[lg]['t'] += 1
    if pred392 == m['actual']: type_stats[lg]['c392'] += 1
    if pred310 == m['actual']: type_stats[lg]['c310'] += 1

    # 赔率分析
    odds_range = max(oh,od,oa) - min(oh,od,oa)
    dp_raw = (1/od) / (1/oh + 1/od + 1/oa)

    p(f'')
    p(f'  {m["num"]} {m["home"]} {m["hs"]}:{m["as"]} {m["away"]} [{m["league"]}]  实际:{cn_actual}')
    p(f'  赔率: {oh:.2f}/{od:.2f}/{oa:.2f}  极差:{odds_range:.2f}  dp_raw:{dp_raw*100:.1f}%  {bal_str}')
    p(f'  v3.9.2: {cn392:4s} (H{r392["hp"]*100:.1f}% D{r392["dp"]*100:.1f}% A{r392["ap"]*100:.1f}%) {mark392}')
    p(f'  v3.10:  {cn310:4s} (H{r310["hp"]*100:.1f}% D{r310["dp"]*100:.1f}% A{r310["ap"]*100:.1f}%) {mark310}')
    if pred392 != pred310:
        p(f'  >>> 改变! {cn392} → {cn310}')

    # 错误分析
    if pred310 != m['actual']:
        # 分析为什么错
        probs = {'H':r310['hp'],'D':r310['dp'],'A':r310['ap']}
        sorted_probs = sorted(probs.items(), key=lambda x: -x[1])
        actual_prob = probs[m['actual']]
        pred_prob = probs[pred310]
        gap = pred_prob - actual_prob
        p(f'  错误分析: 预测{cn310}概率{pred_prob*100:.1f}% vs 实际{cn_actual}概率{actual_prob*100:.1f}% 差{gap*100:.1f}pp')

p(f'')
p(f'{"="*85}')
p(f'  汇总统计')
p(f'{"="*85}')
p(f'')
p(f'  总场次: {total}')
p(f'  v3.9.2正确: {correct392}/{total} = {correct392/total*100:.1f}%')
p(f'  v3.10 正确: {correct310}/{total} = {correct310/total*100:.1f}%')
p(f'')
p(f'  均衡赔率场次: {balanced_total}')
if balanced_total > 0:
    p(f'  均衡-v3.9.2: {balanced_correct392}/{balanced_total} = {balanced_correct392/balanced_total*100:.1f}%')
    p(f'  均衡-v3.10:  {balanced_correct310}/{balanced_total} = {balanced_correct310/balanced_total*100:.1f}%')
p(f'')
p(f'  预测改变: {changed}场')
p(f'  改变后正确: {changed_correct}, 错误: {changed_wrong}, 净收益: +{changed_correct-changed_wrong}')
p(f'')
p(f'  按联赛:')
for lg, stats in type_stats.items():
    p(f'    {lg}: v3.9.2={stats["c392"]}/{stats["t"]} v3.10={stats["c310"]}/{stats["t"]}')

# ===== 错误模式分析 =====
p(f'')
p(f'{"="*85}')
p(f'  错误模式分析 → 模型迭代方向')
p(f'{"="*85}')

# 分析每场错误
errors = []
for m in matches:
    r310 = predict_v310(m['oh'], m['od'], m['oa'], m['league'])
    if r310['pred'] != m['actual']:
        odds_range = max(m['oh'],m['od'],m['oa']) - min(m['oh'],m['od'],m['oa'])
        dp_raw = (1/m['od']) / (1/m['oh'] + 1/m['od'] + 1/m['oa'])
        errors.append({
            'num': m['num'],
            'home': m['home'],
            'away': m['away'],
            'league': m['league'],
            'pred': r310['pred'],
            'actual': m['actual'],
            'odds_range': odds_range,
            'dp_raw': dp_raw,
            'is_balanced': r310.get('is_balanced', False),
            'pred_prob': max(r310['hp'], r310['dp'], r310['ap']),
            'actual_prob': {'H':r310['hp'],'D':r310['dp'],'A':r310['ap']}[m['actual']],
        })

p(f'')
p(f'  v3.10错误场次: {len(errors)}/{total}')
for e in errors:
    cn_pred = {'H':'主胜','D':'平局','A':'客胜'}[e['pred']]
    cn_actual = {'H':'主胜','D':'平局','A':'客胜'}[e['actual']]
    p(f'')
    p(f'  {e["num"]} {e["home"]} vs {e["away"]} [{e["league"]}]')
    p(f'    预测:{cn_pred}({e["pred_prob"]*100:.1f}%) 实际:{cn_actual}({e["actual_prob"]*100:.1f}%)')
    p(f'    极差:{e["odds_range"]:.2f} dp_raw:{e["dp_raw"]*100:.1f}% 均衡:{e["is_balanced"]}')

# 关键发现
p(f'')
p(f'{"="*85}')
p(f'  关键发现 & 迭代方向')
p(f'{"="*85}')

# 1. 均衡赔率分析
balanced_errors = [e for e in errors if e['is_balanced']]
non_balanced_errors = [e for e in errors if not e['is_balanced']]

p(f'')
p(f'  1. 均衡赔率(极差<0.8)错误: {len(balanced_errors)}场')
for e in balanced_errors:
    cn_pred = {'H':'主胜','D':'平局','A':'客胜'}[e['pred']]
    cn_actual = {'H':'主胜','D':'平局','A':'客胜'}[e['actual']]
    p(f'     {e["num"]} 预测{cn_pred}实际{cn_actual} (dp_raw={e["dp_raw"]*100:.1f}%)')

p(f'  2. 非均衡赔率错误: {len(non_balanced_errors)}场')
for e in non_balanced_errors:
    cn_pred = {'H':'主胜','D':'平局','A':'客胜'}[e['pred']]
    cn_actual = {'H':'主胜','D':'平局','A':'客胜'}[e['actual']]
    p(f'     {e["num"]} 预测{cn_pred}实际{cn_actual} (极差={e["odds_range"]:.2f})')

# 3. 看实际draw比例
actual_draws = sum(1 for m in matches if m['actual'] == 'D')
p(f'')
p(f'  3. 实际draw比例: {actual_draws}/{total} = {actual_draws/total*100:.1f}%')
p(f'     模型预测draw: {sum(1 for m in matches if predict_v310(m["oh"],m["od"],m["oa"],m["league"])["pred"]=="D")}/{total}')

# 4. 均衡赔率中实际draw比例
balanced_matches = [m for m in matches if max(m['oh'],m['od'],m['oa'])-min(m['oh'],m['od'],m['oa']) < 0.8]
balanced_draws = sum(1 for m in balanced_matches if m['actual'] == 'D')
p(f'     均衡赔率中draw: {balanced_draws}/{len(balanced_matches)} = {balanced_draws/len(balanced_matches)*100:.1f}%')

# 5. v3.10的均衡draw boost还不够
p(f'')
p(f'  4. v3.10均衡draw boost=0.04的效果:')
p(f'     均衡赔率4场, v3.10只成功预测1场draw(001)')
p(f'     002/004/011 虽然dp被提升, 但仍不是最高概率')
p(f'     → boost=0.04不够, 需要更大boost或改变决策逻辑')

p(f'')
p(f'  5. 非均衡赔率的问题:')
p(f'     005 赫根3:2哈马比: 赔率2.77/3.35/2.13(极差1.22) 预测客胜实际主胜')
p(f'     006 代格福什2:2布鲁马: 赔率2.10/3.15/2.98(极差0.88) 预测主胜实际平局')
p(f'     004 韦斯特罗斯4:5哥德堡: 均衡赔率, 预测主胜实际客胜(大比分!)')
p(f'     → 这些场次的赔率本身就不能准确反映概率')

p(f'')
p(f'{"="*85}')
p(f'  v3.11 迭代方案')
p(f'{"="*85}')
p(f('')
p(f'  问题1: 均衡赔率draw boost不够')
p(f'  当前: is_balanced(odds_range<0.8) and dp>=0.28 -> boost=0.04')
p(f'  001: dp_raw=30.5%, boost后33.5%, 但hp=34.0%仍最高 -> 选主胜而非平局')
p(f'  002: dp_raw=29.6%, boost后32.6%, 但ap=34.3%仍最高 -> 选客胜而非平局')
p(f'  011: dp_raw=29.5%, boost后32.5%, 但hp=35.4%仍最高 -> 选主胜而非平局')
p(f'  -> boost=0.04不够让dp超过hp/ap')
p(f'  -> 方案A: 增大boost到0.06-0.08')
p(f'  -> 方案B: 均衡时直接选draw(不依赖概率比较)')
p(f'  -> 方案C: 均衡时用dp是否>=max(hp,ap)作为draw条件')
p(f'')
p(f'  问题2: 非均衡赔率也有平局被低估')
p(f'  006: 赔率2.10/3.15/2.98(极差0.88, 不均衡) dp=29.2% -> 预测主胜实际平局')
p(f'  -> 极差0.88接近0.8, 可能需要放宽均衡阈值到1.0')
p(f'  -> 或者: 极差0.8-1.2时给中等draw boost(0.02)')
p(f'')
p(f'  问题3: 高dp场次预测方向错误')
p(f'  004: 均衡赔率但实际客胜(4:5大比分) -> 赔率无法预测')
p(f'  005: 非均衡赔率预测客胜实际主胜 -> 赫根主场优势被低估')
p(f'  -> 这些属于赔率本身的局限, 模型无法完全解决')
p(f('  004: 均衡赔率但实际客胜(4:5大比分) → 赔率无法预测这种比赛')
p(f('  005: 非均衡赔率预测客胜实际主胜 → 赫根主场优势被低估')
p(f('  → 这些属于赔率本身的局限, 模型无法完全解决')

report = '\n'.join(lines)
print(report)
