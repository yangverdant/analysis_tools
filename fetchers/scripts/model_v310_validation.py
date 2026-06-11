"""
模型v3.10 — 修正均衡赔率下平局被低估的问题

核心改动:
1. 赔率3-way均衡度检测: max_odds - min_odds < 0.8 → 均衡信号
2. 均衡时dp boost: 如果dp隐含概率>=0.28且赔率均衡 → dp +0.03
3. 取消dp>=0.30时减draw的逻辑(这个规则只在赔率不均衡时合理)
4. 低赔率冷门区: oh或oa在1.25-1.35时, 保留原逻辑

v3.9.2的问题:
- 冈山(2.90) vs 浦和(2.22) 平(3.00): dp=0.30 → 触发减0.01 → dp=0.29 → 选客胜
- 清水(2.52) vs 横滨(2.44) 平(3.10): dp=0.296 → 不触发 → 选客胜(ap=0.33最高)
- 两场实际都是1:1平局

根本原因: 均衡赔率下, 平局是最可能的结果, 但模型只看哪个概率最高就选哪个
"""
import sys, io, json, sqlite3, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

lines = []
def p(s=''): lines.append(s)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                        'data', 'football_v2.db')

# ===== 模型函数 =====

def predict_v392(oh, od, oa, league=''):
    """v3.9.2 原版"""
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
    """v3.10 修正版"""
    if not oh or not od or not oa: return None
    hp, dp, ap = 1/oh, 1/od, 1/oa
    total = hp + dp + ap
    margin = total - 1
    hp, dp, ap = hp/total, dp/total, ap/total

    # 1. 均衡度检测
    odds_list = [oh, od, oa]
    odds_range = max(odds_list) - min(odds_list)
    is_balanced = odds_range < 0.8  # 赔率极差<0.8 = 均衡

    # 2. 杯赛/国际赛: 减draw (保留)
    is_cup = any(kw in league for kw in ['欧冠','欧联','欧协','国际赛','友谊赛','解放者'])
    if is_cup:
        dp -= 0.02; nd = hp+ap
        if nd > 0: hp += 0.02*(hp/nd); ap += 0.02*(ap/nd)

    # 3. 核心改动: 均衡赔率 → 提升draw
    if is_balanced and dp >= 0.28:
        # 均衡时平局是最可能结果，给draw boost
        boost = 0.04  # 均衡信号强，给0.04
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

    # 4. 冷门区: oh在1.25-1.35 (保留)
    if oh and 1.25 <= oh <= 1.35:
        hp -= 0.02; dp += 0.01; ap += 0.01

    # 归一化
    total = hp+dp+ap
    if total > 0: hp, dp, ap = hp/total, dp/total, ap/total
    pred = max(['H','D','A'], key=lambda x: {'H':hp,'D':dp,'A':ap}[x])
    conf = max(hp, dp, ap)
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf,'is_balanced':is_balanced}

# ===== 验证 =====

# 今天已验证的2场
test_cases = [
    {'oh': 2.90, 'od': 3.00, 'oa': 2.22, 'league': '日职',
     'home': '冈山绿雉', 'away': '浦和红钻', 'actual': 'D', 'actual_cn': '1:1平局'},
    {'oh': 2.52, 'od': 3.10, 'oa': 2.44, 'league': '日职',
     'home': '清水鼓动', 'away': '横滨水手', 'actual': 'D', 'actual_cn': '1:1平局'},
    # 后面的比赛(待验证)
    {'oh': 2.46, 'od': 3.00, 'oa': 2.57, 'league': '瑞超',
     'home': '韦斯特罗斯', 'away': '哥德堡'},
    {'oh': 2.77, 'od': 3.35, 'oa': 2.13, 'league': '瑞超',
     'home': '赫根', 'away': '哈马比'},
    {'oh': 2.10, 'od': 3.15, 'oa': 2.98, 'league': '瑞超',
     'home': '代格福什', 'away': '布鲁马波卡纳'},
    {'oh': 1.12, 'od': 6.25, 'oa': 13.00, 'league': '国际赛',
     'home': '日本', 'away': '冰岛'},
    {'oh': 1.50, 'od': 3.80, 'oa': 4.60, 'league': '芬超',
     'home': 'AC奥卢', 'away': '雅罗'},
    {'oh': 1.52, 'od': 3.64, 'oa': 5.10, 'league': '国际赛',
     'home': '捷克', 'away': '科索沃'},
    {'oh': 2.43, 'od': 2.90, 'oa': 2.68, 'league': '国际赛',
     'home': '美国', 'away': '塞内加尔'},
]

p('=' * 85)
p('  模型v3.9.2 vs v3.10 对比 — 均衡赔率下平局修正')
p('=' * 85)

correct_v392 = 0
correct_v310 = 0
total = 0

for tc in test_cases:
    r392 = predict_v392(tc['oh'], tc['od'], tc['oa'], tc['league'])
    r310 = predict_v310(tc['oh'], tc['od'], tc['oa'], tc['league'])

    pred392 = r392['pred']
    pred310 = r310['pred']
    cn392 = {'H':'主胜','D':'平局','A':'客胜'}[pred392]
    cn310 = {'H':'主胜','D':'平局','A':'客胜'}[pred310]

    has_result = 'actual' in tc
    mark392 = ''
    mark310 = ''
    if has_result:
        total += 1
        if pred392 == tc['actual']: correct_v392 += 1; mark392 = '✓'
        else: mark392 = '✗'
        if pred310 == tc['actual']: correct_v310 += 1; mark310 = '✓'
        else: mark310 = '✗'

    actual_str = f'实际:{tc["actual_cn"]}' if has_result else '待验证'
    balanced = r310.get('is_balanced', False)
    bal_str = '均衡' if balanced else '不均衡'

    p(f'')
    p(f'  {tc["home"]} vs {tc["away"]} [{tc["league"]}]  赔率:{tc["oh"]:.2f}/{tc["od"]:.2f}/{tc["oa"]:.2f}  {bal_str}')
    p(f'  v3.9.2: {cn392:4s} (H{r392["hp"]*100:.1f}% D{r392["dp"]*100:.1f}% A{r392["ap"]*100:.1f}%) {mark392}')
    p(f'  v3.10:  {cn310:4s} (H{r310["hp"]*100:.1f}% D{r310["dp"]*100:.1f}% A{r310["ap"]*100:.1f}%) {mark310}')
    p(f'  {actual_str}')
    if pred392 != pred310:
        p(f'  >>> 改变! v3.9.2={cn392} → v3.10={cn310}')

p(f'')
p(f'  已验证场次: {total}')
p(f'  v3.9.2正确: {correct_v392}/{total} = {correct_v392/total*100:.1f}%' if total > 0 else '  无验证数据')
p(f'  v3.10 正确: {correct_v310}/{total} = {correct_v310/total*100:.1f}%' if total > 0 else '  无验证数据')

# ===== 用DB历史数据验证 =====
p(f'')
p(f'{"="*85}')
p(f'  DB历史数据验证')
p(f'{"="*85}')

if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 查有赔率和赛果的比赛
    cur.execute("""
        SELECT m.match_date, m.home_team, m.away_team,
               o.home_win, o.draw, o.away_win,
               r.home_score, r.away_score
        FROM matches m
        JOIN odds o ON m.match_id = o.match_id
        JOIN results r ON m.match_id = r.match_id
        WHERE o.home_win > 1.01 AND o.draw > 1.01 AND o.away_win > 1.01
        AND r.home_score IS NOT NULL AND r.away_score IS NOT NULL
        AND o.source = 'sporttery'
        ORDER BY m.match_date DESC
        LIMIT 2000
    """)
    rows = cur.fetchall()

    if rows:
        correct392 = 0
        correct310 = 0
        changed = 0
        changed_correct = 0
        changed_wrong = 0
        balanced_total = 0
        balanced_correct392 = 0
        balanced_correct310 = 0

        for row in rows:
            date, home, away, oh, od, oa, hs, aws = row
            try:
                hs_i, as_i = int(hs), int(aws)
                if hs_i > as_i: actual = 'H'
                elif hs_i == as_i: actual = 'D'
                else: actual = 'A'
            except:
                continue

            r392 = predict_v392(oh, od, oa)
            r310 = predict_v310(oh, od, oa)
            if not r392 or not r310: continue

            is_bal = r310.get('is_balanced', False)
            if is_bal:
                balanced_total += 1
                if r392['pred'] == actual: balanced_correct392 += 1
                if r310['pred'] == actual: balanced_correct310 += 1

            if r392['pred'] == actual: correct392 += 1
            if r310['pred'] == actual: correct310 += 1

            if r392['pred'] != r310['pred']:
                changed += 1
                if r310['pred'] == actual: changed_correct += 1
                else: changed_wrong += 1

        total_db = len(rows)
        p(f'')
        p(f'  总场次: {total_db}')
        p(f'  v3.9.2总正确: {correct392}/{total_db} = {correct392/total_db*100:.2f}%')
        p(f'  v3.10 总正确: {correct310}/{total_db} = {correct310/total_db*100:.2f}%')
        p(f'')
        p(f'  均衡赔率场次: {balanced_total}')
        p(f'  均衡-v3.9.2: {balanced_correct392}/{balanced_total} = {balanced_correct392/balanced_total*100:.2f}%' if balanced_total > 0 else '  均衡-无数据')
        p(f'  均衡-v3.10:  {balanced_correct310}/{balanced_total} = {balanced_correct310/balanced_total*100:.2f}%' if balanced_total > 0 else '  均衡-无数据')
        p(f'')
        p(f'  预测改变的场次: {changed}')
        p(f'  改变后正确: {changed_correct}/{changed} = {changed_correct/changed*100:.2f}%' if changed > 0 else '  改变-无数据')
        p(f'  改变后错误: {changed_wrong}/{changed} = {changed_wrong/changed*100:.2f}%' if changed > 0 else '  改变-无数据')
        p(f'  净收益: +{changed_correct} -{changed_wrong} = +{changed_correct-changed_wrong}')
    else:
        p(f'  DB中无赔率+赛果数据')

    conn.close()
else:
    p(f'  DB文件不存在: {DB_PATH}')

p(f'')
p('=' * 85)

report = '\n'.join(lines)
print(report)
