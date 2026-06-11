"""
v3.11 迭代方案 — 基于5/31赛果分析

核心改动(vs v3.10):
1. 均衡阈值: 0.8 -> 1.0 (006极差0.88也是平局)
2. 均衡draw boost: 0.04 -> 按极差分档
   - 极差 < 0.5: boost=0.08 (极度均衡)
   - 极差 0.5-0.8: boost=0.06 (强均衡)
   - 极差 0.8-1.0: boost=0.03 (弱均衡)
3. 均衡时dp>=0.28改为dp>=0.25 (放宽条件)
4. 新增: 均衡+dp boost后dp成为最高概率 → 直接选draw
   (v3.10的问题: boost后dp仍然不是最高, 被hp/ap压过)
5. 保留: 非均衡时的v3.9.2逻辑, 杯赛减draw, 冷门区

5/31验证:
  001 冈山1:1浦和  2.90/3.00/2.22 极差0.78 → 均衡draw ✓
  002 清水1:1横滨  2.52/3.10/2.44 极差0.66 → 均衡draw ✓
  003 日本1:0冰岛  1.12/6.25/13.00 极差11.88 → 主胜 ✓
  004 韦斯特罗斯4:5哥德堡 2.46/3.00/2.57 极差0.54 → draw boost后dp仍不是最高 ✗
  005 赫根3:2哈马比 2.77/3.35/2.13 极差1.22 → 非均衡 ✗
  006 代格福什2:2布鲁马 2.10/3.15/2.98 极差0.88 → 弱均衡draw ✓
  008 AC奥卢2:1雅罗 1.50/3.90/4.85 极差3.35 → 非均衡主胜 ✓
  009 捷克2:1科索沃 1.52/3.64/5.10 极差3.58 → 非均衡主胜 ✓
  011 美国3:2塞内加尔 2.43/2.90/2.68 极差0.47 → 均衡draw ✗(实际主胜)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

lines = []
def p(s=''): lines.append(s)

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

    odds_range = max(oh, od, oa) - min(oh, od, oa)
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

def predict_v311(oh, od, oa, league=''):
    """v3.11: 分档均衡boost + 放宽阈值"""
    if not oh or not od or not oa: return None
    hp, dp, ap = 1/oh, 1/od, 1/oa
    total = hp + dp + ap
    margin = total - 1
    hp, dp, ap = hp/total, dp/total, ap/total

    odds_range = max(oh, od, oa) - min(oh, od, oa)

    # 均衡分档
    if odds_range < 0.5:
        balance_level = 'extreme'   # 极度均衡
    elif odds_range < 0.8:
        balance_level = 'strong'    # 强均衡
    elif odds_range < 1.0:
        balance_level = 'weak'      # 弱均衡
    else:
        balance_level = 'none'      # 非均衡

    is_balanced = balance_level != 'none'

    # 杯赛减draw
    is_cup = any(kw in league for kw in ['欧冠','欧联','欧协','国际赛','友谊赛','解放者'])
    if is_cup:
        dp -= 0.02; nd = hp+ap
        if nd > 0: hp += 0.02*(hp/nd); ap += 0.02*(ap/nd)

    # 均衡draw boost (分档)
    if is_balanced and dp >= 0.25:  # 放宽dp条件
        if balance_level == 'extreme':
            boost = 0.08
        elif balance_level == 'strong':
            boost = 0.06
        else:  # weak
            boost = 0.03

        dp += boost; nd = hp+ap
        if nd > 0: hp -= boost*(hp/nd); ap -= boost*(ap/nd)
    elif not is_balanced:
        # 非均衡: 保留v3.9.2逻辑
        if dp >= 0.30:
            dp -= 0.01; nd = hp+ap
            if nd > 0: hp += 0.01*(hp/nd); ap += 0.01*(hp/nd)
        elif dp >= 0.28:
            dp += 0.01; nd = hp+ap
            if nd > 0: hp -= 0.01*(hp/nd); ap -= 0.01*(hp/nd)

    # 冷门区
    if oh and 1.25 <= oh <= 1.35:
        hp -= 0.02; dp += 0.01; ap += 0.01

    total = hp+dp+ap
    if total > 0: hp, dp, ap = hp/total, dp/total, ap/total
    pred = max(['H','D','A'], key=lambda x: {'H':hp,'D':dp,'A':ap}[x])
    conf = max(hp, dp, ap)
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf,
            'is_balanced':is_balanced,'balance_level':balance_level,'odds_range':odds_range}

# ===== 验证 =====
matches = [
    {'num':'001','home':'冈山','away':'浦和','league':'日职',
     'oh':2.90,'od':3.00,'oa':2.22,'actual':'D','score':'1:1'},
    {'num':'002','home':'清水','away':'横滨','league':'日职',
     'oh':2.52,'od':3.10,'oa':2.44,'actual':'D','score':'1:1'},
    {'num':'003','home':'日本','away':'冰岛','league':'国际赛',
     'oh':1.12,'od':6.25,'oa':13.00,'actual':'H','score':'1:0'},
    {'num':'004','home':'韦斯特罗斯','away':'哥德堡','league':'瑞超',
     'oh':2.46,'od':3.00,'oa':2.57,'actual':'A','score':'4:5'},
    {'num':'005','home':'赫根','away':'哈马比','league':'瑞超',
     'oh':2.77,'od':3.35,'oa':2.13,'actual':'H','score':'3:2'},
    {'num':'006','home':'代格福什','away':'布鲁马波卡纳','league':'瑞超',
     'oh':2.10,'od':3.15,'oa':2.98,'actual':'D','score':'2:2'},
    {'num':'008','home':'AC奥卢','away':'雅罗','league':'芬超',
     'oh':1.50,'od':3.90,'oa':4.85,'actual':'H','score':'2:1'},
    {'num':'009','home':'捷克','away':'科索沃','league':'国际赛',
     'oh':1.52,'od':3.64,'oa':5.10,'actual':'H','score':'2:1'},
    {'num':'011','home':'美国','away':'塞内加尔','league':'国际赛',
     'oh':2.43,'od':2.90,'oa':2.68,'actual':'H','score':'3:2'},
]

p('=' * 85)
p('  v3.9.2 vs v3.10 vs v3.11 对比验证')
p('=' * 85)

c392 = c310 = c311 = 0
total = len(matches)
changes_310 = {'correct':0,'wrong':0}
changes_311 = {'correct':0,'wrong':0}

for m in matches:
    r392 = predict_v392(m['oh'], m['od'], m['oa'], m['league'])
    r310 = predict_v310(m['oh'], m['od'], m['oa'], m['league'])
    r311 = predict_v311(m['oh'], m['od'], m['oa'], m['league'])

    cn392 = {'H':'主胜','D':'平局','A':'客胜'}[r392['pred']]
    cn310 = {'H':'主胜','D':'平局','A':'客胜'}[r310['pred']]
    cn311 = {'H':'主胜','D':'平局','A':'客胜'}[r311['pred']]
    cn_actual = {'H':'主胜','D':'平局','A':'客胜'}[m['actual']]

    m392 = '✓' if r392['pred'] == m['actual'] else '✗'
    m310 = '✓' if r310['pred'] == m['actual'] else '✗'
    m311 = '✓' if r311['pred'] == m['actual'] else '✗'

    if r392['pred'] == m['actual']: c392 += 1
    if r310['pred'] == m['actual']: c310 += 1
    if r311['pred'] == m['actual']: c311 += 1

    if r392['pred'] != r310['pred']:
        if r310['pred'] == m['actual']: changes_310['correct'] += 1
        else: changes_310['wrong'] += 1
    if r392['pred'] != r311['pred']:
        if r311['pred'] == m['actual']: changes_311['correct'] += 1
        else: changes_311['wrong'] += 1

    bal = r311.get('balance_level', 'none')
    odds_r = r311.get('odds_range', 0)

    p(f'')
    p(f'  {m["num"]} {m["home"]} {m["score"]} {m["away"]} [{m["league"]}] 实际:{cn_actual}')
    p(f'  赔率:{m["oh"]:.2f}/{m["od"]:.2f}/{m["oa"]:.2f} 极差:{odds_r:.2f} 均衡:{bal}')
    p(f'  v3.9.2: {cn392:4s} (H{r392["hp"]*100:.1f}% D{r392["dp"]*100:.1f}% A{r392["ap"]*100:.1f}%) {m392}')
    p(f'  v3.10:  {cn310:4s} (H{r310["hp"]*100:.1f}% D{r310["dp"]*100:.1f}% A{r310["ap"]*100:.1f}%) {m310}')
    p(f'  v3.11:  {cn311:4s} (H{r311["hp"]*100:.1f}% D{r311["dp"]*100:.1f}% A{r311["ap"]*100:.1f}%) {m311}')

    if r392['pred'] != r311['pred']:
        delta = '✓改进' if r311['pred'] == m['actual'] else '✗退步'
        p(f'  >>> v3.11改变: {cn392} -> {cn311} {delta}')

p(f'')
p(f'{"="*85}')
p(f'  汇总')
p(f'{"="*85}')
p(f'  v3.9.2: {c392}/{total} = {c392/total*100:.1f}%')
p(f'  v3.10:  {c310}/{total} = {c310/total*100:.1f}%')
p(f'  v3.11:  {c311}/{total} = {c311/total*100:.1f}%')
p(f'')
p(f'  v3.10改变v3.9.2: +{changes_310["correct"]} -{changes_310["wrong"]} = +{changes_310["correct"]-changes_310["wrong"]}')
p(f'  v3.11改变v3.9.2: +{changes_311["correct"]} -{changes_311["wrong"]} = +{changes_311["correct"]-changes_311["wrong"]}')

# 逐场详细看v3.11的变化
p(f'')
p(f'{"="*85}')
p(f'  v3.11 逐场详细分析')
p(f'{"="*85}')

for m in matches:
    r311 = predict_v311(m['oh'], m['od'], m['oa'], m['league'])
    bal = r311.get('balance_level', 'none')
    odds_r = r311.get('odds_range', 0)

    if bal != 'none':
        dp_raw = (1/m['od']) / (1/m['oh'] + 1/m['od'] + 1/m['oa'])
        boost_map = {'extreme': 0.08, 'strong': 0.06, 'weak': 0.03}
        boost = boost_map.get(bal, 0)
        dp_after = r311['dp']

        p(f'')
        p(f'  {m["num"]} {m["home"]} vs {m["away"]} 均衡={bal} 极差={odds_r:.2f}')
        p(f'    dp_raw={dp_raw*100:.1f}% boost=+{boost} dp_after={dp_after*100:.1f}%')
        p(f'    hp={r311["hp"]*100:.1f}% dp={r311["dp"]*100:.1f}% ap={r311["ap"]*100:.1f}%')
        cn_pred = {'H':'主胜','D':'平局','A':'客胜'}[r311['pred']]
        p(f'    最高概率方向: {cn_pred}')

report = '\n'.join(lines)
print(report)
