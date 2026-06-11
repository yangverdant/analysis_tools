"""
5/31完整赛果验证 - 用正确赛果(用户确认)
巴西6:2巴拿马 瑞士4:1约旦 德国4:0芬兰
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

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
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf,
            'ev_h':ev_h,'ev_d':ev_d,'ev_a':ev_a}

lines = []
def p(s=''): lines.append(s)

# 5/31全部赛果(用户确认正确比分)
matches = [
    {'num':'001','home':'冈山绿雉','away':'浦和红钻','league':'日职',
     'oh':2.90,'od':3.00,'oa':2.22,'score':'1:1','actual':'D'},
    {'num':'002','home':'清水鼓动','away':'横滨水手','league':'日职',
     'oh':2.52,'od':3.10,'oa':2.44,'score':'1:1','actual':'D'},
    {'num':'003','home':'日本','away':'冰岛','league':'国际赛',
     'oh':1.12,'od':6.25,'oa':13.00,'score':'1:0','actual':'H'},
    {'num':'004','home':'韦斯特罗斯','away':'IFK哥德堡','league':'瑞超',
     'oh':2.46,'od':3.00,'oa':2.57,'score':'4:5','actual':'A'},
    {'num':'005','home':'赫根','away':'哈马比','league':'瑞超',
     'oh':2.77,'od':3.35,'oa':2.13,'score':'3:2','actual':'H'},
    {'num':'006','home':'代格福什','away':'布鲁马波卡纳','league':'瑞超',
     'oh':2.10,'od':3.15,'oa':2.98,'score':'2:2','actual':'D'},
    {'num':'007','home':'巴西','away':'巴拿马','league':'国际赛',
     'oh':0,'od':0,'oa':0,'score':'6:2','actual':'H','no_odds':True},
    {'num':'008','home':'AC奥卢','away':'雅罗','league':'芬超',
     'oh':1.50,'od':3.90,'oa':4.85,'score':'2:1','actual':'H'},
    {'num':'009','home':'捷克','away':'科索沃','league':'国际赛',
     'oh':1.52,'od':3.64,'oa':5.10,'score':'2:1','actual':'H'},
    {'num':'010','home':'瑞士','away':'约旦','league':'国际赛',
     'oh':0,'od':0,'oa':0,'score':'4:1','actual':'H','no_odds':True},
    {'num':'011','home':'美国','away':'塞内加尔','league':'国际赛',
     'oh':2.43,'od':2.90,'oa':2.68,'score':'3:2','actual':'H'},
    {'num':'012','home':'德国','away':'芬兰','league':'国际赛',
     'oh':0,'od':0,'oa':0,'score':'4:0','actual':'H','no_odds':True},
]

p('=' * 85)
p('  5/31完整赛果 (12场, 用户确认)')
p('=' * 85)

correct = 0
total = 0
draw_count = 0
home_count = 0
away_count = 0
balanced_draw = 0
balanced_total = 0

for m in matches:
    cn = {'H':'主胜','D':'平局','A':'客胜'}
    cn_actual = cn[m['actual']]

    # 统计
    if m['actual'] == 'H': home_count += 1
    elif m['actual'] == 'D': draw_count += 1
    else: away_count += 1

    if m.get('no_odds'):
        p(f'  {m["num"]} {m["home"]:10s} {m["score"]:4s} {m["away"]:10s} [{m["league"]}] 实际:{cn_actual} (赔率未出)')
        continue

    oh, od, oa = m['oh'], m['od'], m['oa']
    r = predict(oh, od, oa, m['league'])
    cn_pred = cn[r['pred']]
    mark = '✓' if r['pred'] == m['actual'] else '✗'
    total += 1
    if r['pred'] == m['actual']: correct += 1

    odds_range = max(oh,od,oa) - min(oh,od,oa)
    is_bal = odds_range < 0.8
    if is_bal:
        balanced_total += 1
        if m['actual'] == 'D': balanced_draw += 1

    ev_best = max(r['ev_h'], r['ev_d'], r['ev_a'])
    ev_name = [('主胜',r['ev_h']),('平局',r['ev_d']),('客胜',r['ev_a'])]
    ev_name.sort(key=lambda x: -x[1])

    p(f'  {m["num"]} {m["home"]:10s} {m["score"]:4s} {m["away"]:10s} [{m["league"]}] 极差:{odds_range:.2f}')
    p(f'       赔率:{oh:.2f}/{od:.2f}/{oa:.2f} 预测:{cn_pred}({r["conf"]*100:.0f}%) {mark} 实际:{cn_actual}')
    if r['pred'] != m['actual']:
        p(f'       错误! EV最优:{ev_name[0][0]}{ev_name[0][1]:+.3f}')
    if is_bal:
        p(f'       均衡赔率 → 实际{cn_actual}')

p(f'')
p(f'{"="*85}')
p(f'  汇总')
p(f'{"="*85}')
p(f'  v3.9.2正确: {correct}/{total} = {correct/total*100:.1f}%')
p(f'  主胜:{home_count} 平局:{draw_count} 客胜:{away_count} (12场)')
p(f'  均衡赔率(<0.8)中平局: {balanced_draw}/{balanced_total} = {balanced_draw/balanced_total*100:.0f}%' if balanced_total > 0 else '')
p(f'')
p(f'  错误模式:')
p(f'  - 001/002 均衡赔率选客胜,实际平局 → 均衡draw信号被忽略')
p(f'  - 004 均衡赔率选主胜,实际客胜(4:5) → 赔率无法预测大比分')
p(f'  - 005 非均衡选客胜,实际主胜(3:2) → 主场优势被低估')
p(f'  - 006 近均衡(0.88)选主胜,实际平局(2:2) → 阈值太窄')
p(f'')
p(f'  正确模式:')
p(f'  - 003/008/009 低赔率主胜 → 强队碾压,最稳方向')
p(f'  - 011 均衡赔率但实际主胜(3:2) → 均衡≠一定平局')
p(f'  - 007/010/012 国际赛强队全胜 → 友谊赛强队靠谱')

report = '\n'.join(lines)
print(report)
