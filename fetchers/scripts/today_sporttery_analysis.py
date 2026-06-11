"""
今日体彩比赛分析
- 从体彩官网获取比赛+赔率
- 用模型预测
- 输出推荐
"""
import sys, io, json, os, math, requests
from datetime import date
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

lines = []
def p(s=""): lines.append(s)

# ===== 1. 从体彩获取数据 =====
def fetch_sporttery(match_date=None):
    if match_date is None:
        match_date = date.today().strftime('%Y-%m-%d')

    session = requests.Session()
    session.trust_env = False
    session.verify = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://www.sporttery.cn/',
        'Origin': 'https://www.sporttery.cn',
    })

    url = 'https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry'
    r = session.get(url, params={'sellStatus': 'on', 'date': match_date}, timeout=30)
    data = r.json()
    if not data.get('success'):
        print("API返回失败")
        return []

    matches = []
    for dg in data.get('value', {}).get('matchInfoList', []):
        bdate = dg.get('businessDate', '')
        for m in dg.get('subMatchList', []):
            # 提取赔率
            had = m.get('had', {})  # 胜平负
            hhad = m.get('hhad', {})  # 让球胜平负
            hafu = m.get('hafu', {})  # 半全场
            crs = m.get('crs', {})  # 比分
            ttg = m.get('ttg', {})  # 进球数

            match = {
                'match_num': m.get('matchNum', ''),
                'match_num_str': m.get('matchNumStr', ''),
                'home_team': m.get('homeTeamAllName', '') or m.get('homeTeamAbbName', ''),
                'away_team': m.get('awayTeamAllName', '') or m.get('awayTeamAbbName', ''),
                'home_team_en': m.get('homeTeamAbbEnName', ''),
                'away_team_en': m.get('awayTeamAbbEnName', ''),
                'league': m.get('leagueAbbName', ''),
                'league_full': m.get('leagueAllName', ''),
                'match_date': bdate,
                'match_time': m.get('matchTime', ''),
                'match_status': m.get('matchStatus', ''),
                # SPF赔率
                'spf_h': float(had.get('h', 0) or 0),
                'spf_d': float(had.get('d', 0) or 0),
                'spf_a': float(had.get('a', 0) or 0),
                # RQSPF赔率
                'rqspf_h': float(hhad.get('h', 0) or 0),
                'rqspf_d': float(hhad.get('d', 0) or 0),
                'rqspf_a': float(hhad.get('a', 0) or 0),
                'handicap': hhad.get('goalLine', ''),
                # 排名
                'home_rank': m.get('homeRank', [''])[0] if m.get('homeRank') else '',
                'away_rank': m.get('awayRank', [''])[0] if m.get('awayRank') else '',
                # 比分赔率(热门几个)
                'crs_10': float(crs.get('s01s00', 0) or 0),
                'crs_00': float(crs.get('s00s00', 0) or 0),
                'crs_01': float(crs.get('s00s01', 0) or 0),
                'crs_11': float(crs.get('s01s01', 0) or 0),
                'crs_21': float(crs.get('s02s01', 0) or 0),
                'crs_12': float(crs.get('s01s02', 0) or 0),
                'crs_20': float(crs.get('s02s00', 0) or 0),
                'crs_02': float(crs.get('s00s02', 0) or 0),
            }
            matches.append(match)

    return matches

# ===== 2. 模型预测 =====
def predict_from_odds(oh, od, oa, league='', is_cup=False):
    """从体彩赔率推导概率+模型调整"""
    if not oh or not od or not oa:
        return None

    # 隐含概率
    hp = 1.0 / oh
    dp = 1.0 / od
    ap = 1.0 / oa
    total = hp + dp + ap
    margin = total - 1.0  # 抽水
    hp, dp, ap = hp/total, dp/total, ap/total

    # 模型调整
    # 1. 杯赛draw-2pp
    if is_cup:
        dp -= 0.02
        nd = hp + ap
        if nd > 0: hp += 0.02*(hp/nd); ap += 0.02*(ap/nd)

    # 2. draw_threshold规则
    if dp >= 0.30:
        # dt30: 减draw (v3.8数据驱动)
        dp -= 0.01
        nd = hp + ap
        if nd > 0: hp += 0.01*(hp/nd); ap += 0.01*(ap/nd)
    elif dp >= 0.28:
        dp += 0.01
        nd = hp + ap
        if nd > 0: hp -= 0.01*(hp/nd); ap -= 0.01*(ap/nd)

    # 3. 赔率冷门区(1.25-1.35, 5-6月)
    if oh and 1.25 <= oh <= 1.35:
        import datetime
        month = datetime.date.today().month
        if month in [5, 6]:
            hp -= 0.02; dp += 0.01; ap += 0.01

    # 归一化
    total = hp + dp + ap
    if total > 0: hp, dp, ap = hp/total, dp/total, ap/total

    pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
    confidence = max(hp, dp, ap)

    # EV (期望值)
    ev_h = hp * oh - 1
    ev_d = dp * od - 1
    ev_a = ap * oa - 1

    return {
        'home_prob': hp, 'draw_prob': dp, 'away_prob': ap,
        'prediction': pred, 'confidence': confidence,
        'margin': margin,
        'ev_h': ev_h, 'ev_d': ev_d, 'ev_a': ev_a,
    }

# ===== 3. 主分析 =====
TODAY = date.today().strftime('%Y-%m-%d')
p("=" * 90)
p(f"  今日体彩比赛分析 ({TODAY})")
p("=" * 90)

matches = fetch_sporttery(TODAY)
p(f"\n  共 {len(matches)} 场开售比赛")

# 按联赛分组
by_league = defaultdict(list)
for m in matches:
    by_league[m['league']].append(m)

# 杯赛关键词
CUP_KW = ['欧冠', '欧联', '欧协', '解放者', '世界杯', '国际赛', '友谊赛']

# 分析每场比赛
p(f"\n{'─' * 90}")
p(f"  比赛列表 + 赔率 + 模型预测")
p(f"{'─' * 90}")

results = []
for league in sorted(by_league.keys()):
    league_matches = by_league[league]
    p(f"\n  【{league}】({len(league_matches)}场)")
    p(f"  {'编号':6s} {'时间':8s} {'主队':16s} {'客队':16s} {'SPF赔率':16s} {'隐含概率':18s} {'预测':6s} {'EV':10s}")
    p(f"  {'─'*85}")

    for m in league_matches:
        oh, od, oa = m['spf_h'], m['spf_d'], m['spf_a']
        is_cup = any(kw in league for kw in CUP_KW)

        pred = predict_from_odds(oh, od, oa, league=league, is_cup=is_cup)

        if pred:
            hp, dp, ap = pred['home_prob'], pred['draw_prob'], pred['away_prob']
            pred_cn = {'home': '主胜', 'draw': '平局', 'away': '客胜'}[pred['prediction']]
            prob_str = f"H{hp*100:4.1f}% D{dp*100:4.1f}% A{ap*100:4.1f}%"
            odds_str = f"{oh:.2f}/{od:.2f}/{oa:.2f}"

            # EV
            best_ev = max(pred['ev_h'], pred['ev_d'], pred['ev_a'])
            ev_str = f"最佳{best_ev:+.3f}"
            if best_ev > 0.05:
                ev_str += " ★"
            elif best_ev > 0:
                ev_str += " ↑"

            p(f"  {m['match_num_str']:6s} {m['match_time'][:5]:8s} {m['home_team']:16s} {m['away_team']:16s} {odds_str:16s} {prob_str:18s} {pred_cn:6s} {ev_str:10s}")

            # 让球赔率
            rqh, rqd, rqa = m['rqspf_h'], m['rqspf_d'], m['rqspf_a']
            hc = m.get('handicap', '')
            if rqh and rqd and rqa and hc:
                rq_pred = predict_from_odds(rqh, rqd, rqa, league=league, is_cup=is_cup)
                if rq_pred:
                    rq_cn = {'home': '让胜', 'draw': '让平', 'away': '让负'}[rq_pred['prediction']]
                    rq_prob = f"H{rq_pred['home_prob']*100:4.1f}% D{rq_pred['draw_prob']*100:4.1f}% A{rq_pred['away_prob']*100:4.1f}%"
                    p(f"         让{hc} → RQ {rqh:.2f}/{rqd:.2f}/{rqa:.2f} {rq_prob} → {rq_cn}")

            results.append({**m, 'pred': pred})
        else:
            p(f"  {m['match_num_str']:6s} {m['match_time'][:5]:8s} {m['home_team']:16s} {m['away_team']:16s} (赔率未开)")

# ===== 4. 重点推荐 =====
p(f"\n{'─' * 90}")
p(f"  重点推荐 (EV>0 或 高置信度)")
p(f"{'─' * 90}")

# 按EV排序
recommendations = []
for r in results:
    pred = r.get('pred')
    if not pred: continue
    best_ev = max(pred['ev_h'], pred['ev_d'], pred['ev_a'])
    if best_ev > -0.05:  # 接近正EV
        # 找最佳方向
        evs = {'主胜': pred['ev_h'], '平局': pred['ev_d'], '客胜': pred['ev_a']}
        best_dir = max(evs, key=evs.get)
        recommendations.append((r, best_dir, evs[best_dir], pred['confidence']))

recommendations.sort(key=lambda x: -x[2])  # 按EV降序

if recommendations:
    p(f"\n  {'编号':6s} {'联赛':6s} {'比赛':36s} {'方向':6s} {'EV':8s} {'置信':6s} {'赔率':8s}")
    p(f"  {'─'*80}")
    for r, direction, ev, conf in recommendations[:10]:
        match_str = f"{r['home_team']} vs {r['away_team']}"
        oh, od, oa = r['spf_h'], r['spf_d'], r['spf_a']
        if direction == '主胜': odds = oh
        elif direction == '平局': odds = od
        else: odds = oa
        p(f"  {r['match_num_str']:6s} {r['league']:6s} {match_str:36s} {direction:6s} {ev:+.3f}  {conf*100:.1f}%  {odds:.2f}")
else:
    p(f"\n  无正EV推荐")

# ===== 5. 冷门预警 =====
p(f"\n{'─' * 90}")
p(f"  冷门预警 (低赔率方<1.40)")
p(f"{'─' * 90}")

upsets = []
for r in results:
    pred = r.get('pred')
    if not pred: continue
    oh = r['spf_h']
    oa = r['spf_a']
    # 低赔率方
    min_odds = min(oh, oa)
    if min_odds < 1.40 and min_odds > 0:
        favored = '主' if oh < oa else '客'
        implied = 1.0 / min_odds
        upsets.append((r, favored, min_odds, implied))

if upsets:
    p(f"\n  {'编号':6s} {'联赛':6s} {'比赛':36s} {'热门方':6s} {'赔率':6s} {'隐含概率':8s} {'风险':6s}")
    p(f"  {'─'*75}")
    for r, favored, odds, implied in upsets:
        match_str = f"{r['home_team']} vs {r['away_team']}"
        risk = "高" if odds < 1.25 else "中" if odds < 1.35 else "低"
        p(f"  {r['match_num_str']:6s} {r['league']:6s} {match_str:36s} {favored:6s} {odds:.2f}  {implied*100:.1f}%    {risk}")
else:
    p(f"\n  无冷门预警")

# ===== 6. 比分赔率参考 =====
p(f"\n{'─' * 90}")
p(f"  比分赔率热门 (最低比分赔率)")
p(f"{'─' * 90}")

for r in results:
    crs_odds = {
        '1:0': r.get('crs_10', 0), '0:0': r.get('crs_00', 0), '0:1': r.get('crs_01', 0),
        '1:1': r.get('crs_11', 0), '2:1': r.get('crs_21', 0), '1:2': r.get('crs_12', 0),
        '2:0': r.get('crs_20', 0), '0:2': r.get('crs_02', 0),
    }
    valid = {k: v for k, v in crs_odds.items() if v > 0}
    if not valid: continue
    top3 = sorted(valid.items(), key=lambda x: x[1])[:3]
    top_str = ' '.join(f"{k}={v:.1f}" for k, v in top3)
    p(f"  {r['match_num_str']:6s} {r['home_team']:12s} vs {r['away_team']:12s} → {top_str}")

p(f"\n{'=' * 90}")
p(f"  分析完成")
p("=" * 90)

report = '\n'.join(lines)
print(report)
