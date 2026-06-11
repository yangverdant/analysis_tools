"""
从澳客m.okooo.com提取竞彩足球数据
- 昨日赛果(400x系列)
- 今日赔率(500x系列)
- 明日赔率(600x/700x系列)
"""
import sys, io, re, json, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import urllib3
urllib3.disable_warnings()

lines = []
def p(s=''): lines.append(s)

# ===== 1. 从m.okooo.com获取数据 =====
session = requests.Session()
session.trust_env = False
session.verify = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
})

r = session.get('https://m.okooo.com/jczq/', timeout=20)
html = r.text

# 提取oddsData (赔率)
odds_match = re.search(r'var oddsData\s*=\s*(\{.*?\});', html, re.DOTALL)
if not odds_match:
    print("oddsData not found!")
    sys.exit(1)
odds_data = json.loads(odds_match.group(1))

# 提取比赛基本信息(队名+比分+联赛)
match_starts = [(m.start(), m.group(1)) for m in re.finditer(r'id="match_(\d+)"', html)]

matches = []
for i, (pos, match_num) in enumerate(match_starts):
    end_pos = match_starts[i+1][0] if i + 1 < len(match_starts) else pos + 3000
    block = html[pos:end_pos]

    home = re.search(r'ctrl_homename[^>]*>([^<]+)', block)
    away = re.search(r'ctrl_awayname[^>]*>([^<]+)', block)
    score = re.search(r'class="zVS"[^>]*>\s*([^<]+)', block)
    league = re.search(r'leaguename="([^"]+)"', block)
    if not league:
        league = re.search(r'league[^>]*>([^<]+)', block)
    matchid = re.search(r'matchid="(\d+)"', block)

    home_name = home.group(1).strip() if home else ''
    away_name = away.group(1).strip() if away else ''
    score_str = score.group(1).strip() if score else ''
    league_name = league.group(1) if league else ''
    mid = matchid.group(1) if matchid else ''

    # 从oddsData提取赔率
    odds = odds_data.get(match_num, {})
    odds_list = odds.get('OddsList', {})
    boundary = odds.get('Boundary', {})

    # SportteryWDL: 胜平负(含让球)  13=主胜, 11=平, 10=客胜
    spf = odds_list.get('SportteryWDL', {})
    # SportteryNWDL: 非让球胜平负  16=胜, 15=平, 14=负
    nwdl = odds_list.get('SportteryNWDL', {})
    # 让球数
    handicap_str = boundary.get('SportteryWDL', '0')

    match_info = {
        'num': match_num,
        'match_id': mid,
        'league': league_name,
        'home': home_name,
        'away': away_name,
        'score': score_str,
        'handicap': handicap_str,
        # SPF赔率(让球)
        'spf_h': float(spf.get('13', 0) or 0),
        'spf_d': float(spf.get('11', 0) or 0),
        'spf_a': float(spf.get('10', 0) or 0),
        # 非让球赔率
        'nw_h': float(nwdl.get('16', 0) or 0),
        'nw_d': float(nwdl.get('15', 0) or 0),
        'nw_a': float(nwdl.get('14', 0) or 0),
    }
    matches.append(match_info)

# ===== 2. 模型预测函数 =====
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
        if nd > 0: hp += 0.01*(hp/nd); ap += 0.01*(ap/nd)
    elif dp >= 0.28:
        dp += 0.01; nd = hp+ap
        if nd > 0: hp -= 0.01*(hp/nd); ap -= 0.01*(ap/nd)
    if oh and 1.25 <= oh <= 1.35:
        hp -= 0.02; dp += 0.01; ap += 0.01
    total = hp+dp+ap
    if total > 0: hp, dp, ap = hp/total, dp/total, ap/total
    pred = max(['H','D','A'], key=lambda x: {'H':hp,'D':dp,'A':ap}[x])
    conf = max(hp, dp, ap)
    ev_h, ev_d, ev_a = hp*oh-1, dp*od-1, ap*oa-1
    return {'hp':hp,'dp':dp,'ap':ap,'pred':pred,'conf':conf,'margin':margin,
            'ev_h':ev_h,'ev_d':ev_d,'ev_a':ev_a}

# ===== 3. 输出分析 =====
p('=' * 85)
p('  澳客竞彩足球数据 (m.okooo.com)')
p('  含昨日赛果(400x) + 今日赔率(500x) + 明日(600x/700x)')
p('=' * 85)

# 按编号分组
yesterday = [m for m in matches if m['num'].startswith('4')]
today = [m for m in matches if m['num'].startswith('5')]
tomorrow = [m for m in matches if m['num'].startswith('6') or m['num'].startswith('7')]

# ===== 昨日赛果 =====
p(f'\n{"─"*85}')
p(f'  昨日赛果 (5/28) — 编号4001-{max(m["num"] for m in yesterday) if yesterday else "?"}')
p(f'{"─"*85}')

correct = 0
total_pred = 0
results_detail = []

for m in yesterday:
    score = m['score']
    if not score or '-' not in score:
        p(f'  #{m["num"]} [{m["league"]}] {m["home"]} vs {m["away"]} — 比分未获取')
        continue

    hs, aws = score.split('-')
    try:
        hs, aws = int(hs), int(aws)
    except:
        p(f'  #{m["num"]} [{m["league"]}] {m["home"]} vs {m["away"]} — 比分格式异常: {score}')
        continue

    if hs > aws:
        actual = 'H'
        actual_cn = '主胜'
    elif hs == aws:
        actual = 'D'
        actual_cn = '平局'
    else:
        actual = 'A'
        actual_cn = '客胜'

    # 用非让球赔率做预测
    pred = predict(m['nw_h'], m['nw_d'], m['nw_a'], m['league'])

    p(f'  #{m["num"]} [{m["league"]}] {m["home"]} {hs}:{aws} {m["away"]}')
    p(f'    赛果: {actual_cn}')

    if pred:
        pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
        is_correct = pred['pred'] == actual
        mark = '✓' if is_correct else '✗'
        total_pred += 1
        if is_correct:
            correct += 1

        p(f'    模型: {pred_cn} (置信{pred["conf"]*100:.1f}%) {mark}')
        p(f'    赔率: {m["nw_h"]:.2f}/{m["nw_d"]:.2f}/{m["nw_a"]:.2f} (margin={pred["margin"]*100:.1f}%)')
        p(f'    隐含: 主{pred["hp"]*100:.1f}% 平{pred["dp"]*100:.1f}% 客{pred["ap"]*100:.1f}%')

        # 让球结果
        hc = m['handicap']
        try:
            hc_int = int(hc)
        except:
            hc_int = 0
        rq_result = (hs + hc_int) - aws  # 让球后的净胜
        if rq_result > 0:
            rq_cn = '让胜'
        elif rq_result == 0:
            rq_cn = '让平'
        else:
            rq_cn = '让负'
        p(f'    让球: 让{hc} → {rq_cn} (让后{hs+hc_int}:{aws})')

        # EV
        evs = [('主胜',pred['ev_h'],m['nw_h']), ('平局',pred['ev_d'],m['nw_d']), ('客胜',pred['ev_a'],m['nw_a'])]
        evs.sort(key=lambda x: -x[1])
        p(f'    EV:  {evs[0][0]}{evs[0][1]:+.3f}(赔{evs[0][2]:.2f})  {evs[1][0]}{evs[1][1]:+.3f}  {evs[2][0]}{evs[2][1]:+.3f}')

        results_detail.append({
            'num': m['num'], 'league': m['league'],
            'home': m['home'], 'away': m['away'],
            'score': f'{hs}:{aws}', 'actual': actual_cn,
            'pred': pred_cn, 'correct': is_correct,
            'conf': pred['conf'], 'margin': pred['margin'],
        })

    p(f'    {"─"*70}')

# 汇总
if total_pred > 0:
    p(f'\n  昨日模型验证: {correct}/{total_pred} = {correct/total_pred*100:.1f}%')

    # 按赛果统计
    from collections import Counter
    actual_dist = Counter(r['actual'] for r in results_detail)
    pred_dist = Counter(r['pred'] for r in results_detail)
    p(f'  实际分布: {dict(actual_dist)}')
    p(f'  预测分布: {dict(pred_dist)}')

    # 错误分析
    wrong = [r for r in results_detail if not r['correct']]
    if wrong:
        p(f'\n  预测错误:')
        for r in wrong:
            p(f'    #{r["num"]} {r["home"]} vs {r["away"]} {r["score"]} → 预测{r["pred"]} 实际{r["actual"]}')

# ===== 今日赔率 =====
p(f'\n{"─"*85}')
p(f'  今日赔率 (5/29) — 编号5001-5009')
p(f'{"─"*85}')

for m in today:
    p(f'  #{m["num"]} [{m["league"]}] {m["home"]} vs {m["away"]}')
    pred = predict(m['nw_h'], m['nw_d'], m['nw_a'], m['league'])
    if pred:
        pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
        p(f'    赔率: {m["nw_h"]:.2f}/{m["nw_d"]:.2f}/{m["nw_a"]:.2f} (margin={pred["margin"]*100:.1f}%)')
        p(f'    隐含: 主{pred["hp"]*100:.1f}% 平{pred["dp"]*100:.1f}% 客{pred["ap"]*100:.1f}%')
        p(f'    模型: {pred_cn} (置信{pred["conf"]*100:.1f}%)')
        evs = [('主胜',pred['ev_h'],m['nw_h']), ('平局',pred['ev_d'],m['nw_d']), ('客胜',pred['ev_a'],m['nw_a'])]
        evs.sort(key=lambda x: -x[1])
        p(f'    EV:  {evs[0][0]}{evs[0][1]:+.3f}(赔{evs[0][2]:.2f})  {evs[1][0]}{evs[1][1]:+.3f}  {evs[2][0]}{evs[2][1]:+.3f}')

    # 让球
    hc = m['handicap']
    rq_pred = predict(m['spf_h'], m['spf_d'], m['spf_a'], m['league'])
    if rq_pred:
        rq_cn = {'H':'让胜','D':'让平','A':'让负'}[rq_pred['pred']]
        p(f'    让{hc}: {m["spf_h"]:.2f}/{m["spf_d"]:.2f}/{m["spf_a"]:.2f} → {rq_cn} (置信{rq_pred["conf"]*100:.1f}%)')

    p(f'    {"─"*70}')

# ===== 明日赔率 =====
if tomorrow:
    p(f'\n{"─"*85}')
    p(f'  明日赔率 — 编号{tomorrow[0]["num"]}-{tomorrow[-1]["num"]}')
    p(f'{"─"*85}')

    for m in tomorrow:
        p(f'  #{m["num"]} [{m["league"]}] {m["home"]} vs {m["away"]}')
        pred = predict(m['nw_h'], m['nw_d'], m['nw_a'], m['league'])
        if pred:
            pred_cn = {'H':'主胜','D':'平局','A':'客胜'}[pred['pred']]
            p(f'    {m["nw_h"]:.2f}/{m["nw_d"]:.2f}/{m["nw_a"]:.2f} → {pred_cn} (置信{pred["conf"]*100:.1f}%)')
        p(f'    {"─"*70}')

p(f'\n{"="*85}')
p('  分析完成')
p('=' * 85)

report = '\n'.join(lines)
print(report)
