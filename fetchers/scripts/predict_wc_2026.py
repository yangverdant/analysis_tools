"""
WC 2026 模型预测脚本

基于:
- 2018/2022历史WC数据统计
- 2026球队阵容+历史战绩实力评分
- 欧赔隐含概率(待赔率开出后填入)
- WC特有规则: 中立场地/小组赛vs淘汰赛/战意不对称
"""
import sys, io, json, os, math
from collections import defaultdict, Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_DIR = 'd:/football_tools/data/world_cup'

def load_json(name):
    path = os.path.join(DATA_DIR, name)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

lines = []
def p(s=""): lines.append(s)

# ===== 1. 构建球队实力评分 =====
p("=" * 80)
p("  WC 2026 模型预测")
p("=" * 80)

# 从2018+2022 AF数据构建历史战绩
combined_stats = defaultdict(lambda: {'W':0, 'D':0, 'L':0, 'GF':0, 'GA':0, 'tournaments':set()})

for year in [2018, 2022]:
    af_data = load_json(f'wc_{year}_af_matches.json')
    if not af_data: continue
    for m in af_data:
        hs = m.get('match_hometeam_score')
        aws = m.get('match_awayteam_score')
        try:
            hs = int(hs) if hs not in (None, '', '-') else None
            aws = int(aws) if aws not in (None, '', '-') else None
        except:
            continue
        if hs is None or aws is None: continue
        ht, at = m.get('match_hometeam_name', ''), m.get('match_awayteam_name', '')
        if not ht or not at: continue

        combined_stats[ht]['tournaments'].add(year)
        combined_stats[at]['tournaments'].add(year)
        if hs > aws:
            combined_stats[ht]['W'] += 1; combined_stats[at]['L'] += 1
        elif hs == aws:
            combined_stats[ht]['D'] += 1; combined_stats[at]['D'] += 1
        else:
            combined_stats[at]['W'] += 1; combined_stats[ht]['L'] += 1
        combined_stats[ht]['GF'] += hs; combined_stats[ht]['GA'] += aws
        combined_stats[at]['GF'] += aws; combined_stats[at]['GA'] += hs

# 评分: Pts/Played, 用Elo式归一化到0-1
team_ratings = {}
for team, s in combined_stats.items():
    played = s['W'] + s['D'] + s['L']
    if played == 0: continue
    pts = s['W'] * 3 + s['D']
    win_pct = s['W'] / played
    # 综合评分: 胜率*0.5 + 积分率*0.3 + 进攻力*0.2
    pts_rate = pts / (played * 3)  # 0-1
    gf_rate = min(s['GF'] / played / 3.0, 1.0)  # 场均进球/3, cap at 1.0
    rating = win_pct * 0.5 + pts_rate * 0.3 + gf_rate * 0.2
    team_ratings[team] = rating

# 归一化到0.3-1.0范围 (避免0分)
if team_ratings:
    min_r = min(team_ratings.values())
    max_r = max(team_ratings.values())
    range_r = max_r - min_r if max_r > min_r else 1.0
    for team in team_ratings:
        team_ratings[team] = 0.3 + 0.7 * (team_ratings[team] - min_r) / range_r

# 无历史数据的队: 默认0.4
DEFAULT_RATING = 0.4

# ===== 2. WC特有参数 =====
# WC draw率: 2018=20.3%, 2022=15.6%, 平均~18% (vs 联赛26%)
# 中立场地: home advantage大幅削弱
# 小组赛draw率: ~19-21%, 淘汰赛draw率: ~12-13% (90分钟内)

WC_DRAW_PRIOR = 0.19       # WC平均draw率
WC_HOME_PRIOR = 0.40       # WC平均home胜率 (vs 联赛43%)
WC_AWAY_PRIOR = 0.41       # WC平均away胜率 (vs 联赛32%)
GROUP_DRAW_BOOST = 0.02    # 小组赛draw比淘汰赛高
KNOCKOUT_DRAW_REDUCE = 0.03 # 淘汰赛draw更低

# ===== 3. 预测函数 =====
def predict_wc_match(home_team, away_team, stage='GROUP', matchday=1,
                     home_odds=None, draw_odds=None, away_odds=None):
    """预测单场WC比赛

    Args:
        home_team/away_team: 队名
        stage: 'GROUP' or 'KNOCKOUT'
        matchday: 小组赛轮次(1-3)
        home/draw/away_odds: 欧赔(可选)

    Returns:
        dict with home/draw/away probs and prediction
    """
    hr = team_ratings.get(home_team, DEFAULT_RATING)
    ar = team_ratings.get(away_team, DEFAULT_RATING)

    # 基础概率: 从实力差推导
    # 实力差 → 预期进球差 → 胜负概率
    diff = hr - ar  # -1 to +1

    # 如果有赔率, 用赔率隐含概率作为基础
    if home_odds and draw_odds and away_odds:
        hp = 1.0 / home_odds
        dp = 1.0 / draw_odds
        ap = 1.0 / away_odds
        total = hp + dp + ap
        hp, dp, ap = hp/total, dp/total, ap/total
    else:
        # 从实力评分推导
        # diff > 0 → home更强
        # 用sigmoid映射
        hp = 1.0 / (1.0 + math.exp(-4.0 * diff))  # sigmoid
        ap = 1.0 - hp

        # draw概率: WC平均~19%, 实力越接近draw越高
        draw_base = WC_DRAW_PRIOR
        closeness = 1.0 - abs(diff)  # 0-1, 越接近越高
        dp = draw_base + 0.10 * closeness  # draw: 19-29%
        dp = min(dp, 0.30)  # cap

        # 归一化
        remaining = 1.0 - dp
        hp = hp * remaining
        ap = ap * remaining

    # WC中立场修正: home advantage削弱
    # 联赛中home~43%, WC中home~40% → 减3pp
    # 将home/away向中间收敛
    ha_gap = hp - ap
    neutral_shrink = 0.85  # 中立场地home advantage收缩到85%
    new_gap = ha_gap * neutral_shrink
    hp = (hp + ap) / 2 + new_gap / 2
    ap = (hp + ap) / 2 - new_gap / 2

    # 小组赛/淘汰赛修正
    if stage == 'GROUP':
        dp += GROUP_DRAW_BOOST
        # 第3轮小组赛: 战意不对称场景
        # (这里无法判断出线形势, 需要实时数据)
    elif stage in ('KNOCKOUT', 'LAST_32', 'LAST_16', 'QUARTER_FINALS', 'SEMI_FINALS', 'FINAL'):
        dp -= KNOCKOUT_DRAW_REDUCE
        # 淘汰赛双方都需赢 → draw回调(但90分钟内draw概率低)
        # 决赛/半决赛: 更保守, draw概率微增
        if stage in ('SEMI_FINALS', 'FINAL'):
            dp += 0.01  # 大赛压力 → 更谨慎

    # 归一化
    total = hp + dp + ap
    if total > 0:
        hp, dp, ap = hp/total, dp/total, ap/total

    # 预测
    pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
    confidence = max(hp, dp, ap)

    return {
        'home_prob': hp, 'draw_prob': dp, 'away_prob': ap,
        'prediction': pred, 'confidence': confidence,
        'home_rating': hr, 'away_rating': ar,
        'rating_diff': hr - ar
    }

# ===== 4. 预测WC 2026小组赛 =====
p(f"\n{'─' * 70}")
p(f"  WC 2026 小组赛预测")
p(f"{'─' * 70}")

fd2026 = load_json('wc_2026_matches.json')
if fd2026:
    # 按分组组织比赛
    group_matches = defaultdict(list)
    for m in fd2026:
        g = m.get('group', '')
        if g and 'GROUP' in g.upper():
            group_matches[g].append(m)

    # 预测每场小组赛
    p(f"\n  分组赛预测(基于历史战绩实力评分, 无赔率):")
    p(f"  {'日期':12s} {'主队':20s} {'客队':20s} {'H%':>5} {'D%':>5} {'A%':>5} {'预测':6s} {'置信':5s}")
    p(f"  {'─'*90}")

    group_predictions = defaultdict(list)
    for g in sorted(group_matches.keys()):
        p(f"\n  {g}:")
        for m in sorted(group_matches[g], key=lambda x: x.get('date', '')):
            ht = m.get('home_team', '')
            at = m.get('away_team', '')
            date = m.get('date', '')

            result = predict_wc_match(ht, at, stage='GROUP')
            pred_str = {'home': '主胜', 'draw': '平局', 'away': '客胜'}[result['prediction']]
            conf_str = f"{result['confidence']*100:.0f}%"

            p(f"  {date:12s} {ht:20s} {at:20s} {result['home_prob']*100:5.1f} {result['draw_prob']*100:5.1f} {result['away_prob']*100:5.1f} {pred_str:6s} {conf_str:5s}")
            group_predictions[g].append({
                'date': date, 'home': ht, 'away': at, **result
            })

    # 小组出线预测
    p(f"\n{'─' * 70}")
    p(f"  小组出线预测(模拟积分)")
    p(f"{'─' * 70}")

    for g in sorted(group_predictions.keys()):
        team_points = defaultdict(float)
        team_gd = defaultdict(float)

        for pred in group_predictions[g]:
            ht, at = pred['home'], pred['away']
            hp, dp, ap = pred['home_prob'], pred['draw_prob'], pred['away_prob']

            # 期望积分
            team_points[ht] += hp * 3 + dp * 1
            team_points[at] += ap * 3 + dp * 1

            # 期望净胜球(简化: 从实力差估算)
            diff = pred['rating_diff']
            team_gd[ht] += diff * 1.5
            team_gd[at] -= diff * 1.5

        # 排序
        p(f"\n  {g}:")
        sorted_teams = sorted(team_points.keys(), key=lambda x: (-team_points[x], -team_gd[x]))
        for i, team in enumerate(sorted_teams):
            pts = team_points[team]
            gd = team_gd[team]
            rating = team_ratings.get(team, DEFAULT_RATING)
            marker = " ★" if i < 2 else "  "  # 前2名出线
            p(f"    {i+1}. {team:20s} 期望{pts:.1f}分 GD{gd:+.1f} 评分{rating:.2f}{marker}")

# ===== 5. WC特有规则总结 =====
p(f"\n{'─' * 70}")
p(f"  WC模型规则总结")
p(f"{'─' * 70}")

p(f"""
  当前模型(enhanced_linear v3.9.2)对WC的适配:

  已有规则:
  1. CUP_DP_REDUCE=0.02 → 杯赛draw概率-2pp
     WC draw率(~18-22%) < 联赛(~26%) → 方向正确
  2. CUP_KEYWORDS包含"world_cup" → WC自动触发杯赛规则
  3. 赔率平局阈值规则 → 当draw隐含概率≥30%时微调

  需新增/调整:
  1. 中立场地home advantage收缩
     - 联赛: home~43%, away~32%, gap=11pp
     - WC:   home~40%, away~41%, gap=-1pp (客胜率>主胜率!)
     - 建议: WC中home_away因子权重×0.3或直接跳过

  2. WC小组赛第3轮战意不对称
     - 已出线队 vs 需赢队 → 动机差巨大
     - 类似联赛赛季末dead_rubber场景
     - 需实时积分榜数据才能判断

  3. 淘汰赛draw回调
     - 90分钟内draw概率极低(~12%)
     - 但加时赛后draw→点球 → 实际"平局"概率更高
     - 模型应区分90分钟vs加时赛结果

  4. WC赔率特点
     - 市场流动性高 → 隐含概率更可靠
     - euro_odds权重可适当提高
     - 赔率尚未开出 → 需等6月赛前1-2周

  5. 球队实力评估
     - 国家队比赛间隔长 → form数据不可靠
     - 建议用: 球员身价总和 + 历届WC战绩 + 近期友谊赛
     - 当前评分基于2018+2022历史, 阵容变化大的队需调整
""")

# ===== 6. 保存预测结果 =====
predictions = {}
if fd2026:
    for m in fd2026:
        ht = m.get('home_team', '')
        at = m.get('away_team', '')
        if not ht or not at: continue
        stage = 'GROUP' if 'GROUP' in (m.get('stage', '') or '').upper() else 'KNOCKOUT'
        result = predict_wc_match(ht, at, stage=stage)
        mk = f"{m.get('date','')}|{ht}|{at}"
        predictions[mk] = result

save_path = os.path.join(DATA_DIR, 'wc_2026_predictions.json')
with open(save_path, 'w', encoding='utf-8') as f:
    json.dump(predictions, f, ensure_ascii=False, indent=2)
p(f"\n  预测结果已保存: {save_path} ({len(predictions)}场)")

p(f"\n{'=' * 80}")
p("  WC 2026预测完成")
p("=" * 80)

report = '\n'.join(lines)
with open(os.path.join(DATA_DIR, 'wc_2026_prediction_report.txt'), 'w', encoding='utf-8') as f:
    f.write(report)
print(report)
