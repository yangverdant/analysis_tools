"""
世界杯综合分析脚本
- 2018/2022历史统计
- 2026赛程分析
- 球队阵容实力评估
- WC vs 联赛差异分析（draw rate, goals等）
- 模型预测准备
"""
import sys, io, json, os, math
from collections import defaultdict, Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_DIR = 'd:/football_tools/data/world_cup'

lines = []
def p(s=""): lines.append(s)

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_json_safe(name):
    path = os.path.join(DATA_DIR, name)
    if os.path.exists(path):
        return load_json(path)
    return None

# ===== 统计函数 =====
def calc_match_stats(matches, label):
    """计算比赛基本统计"""
    finished = [m for m in matches if m.get('status') == 'FINISHED' or m.get('home_score_ft') is not None]

    if not finished:
        p(f"\n  {label}: 无已完赛数据")
        return None

    total_goals = sum((m['home_score_ft'] or 0) + (m['away_score_ft'] or 0) for m in finished)
    avg_goals = total_goals / len(finished) if finished else 0

    results = Counter(m['result'] for m in finished if m.get('result'))
    total_r = sum(results.values())

    stats = {
        'total': len(finished),
        'goals': total_goals,
        'avg_goals': avg_goals,
        'results': dict(results),
        'home_win_pct': results.get('H', 0) / total_r * 100 if total_r else 0,
        'draw_pct': results.get('D', 0) / total_r * 100 if total_r else 0,
        'away_win_pct': results.get('A', 0) / total_r * 100 if total_r else 0,
    }
    return stats

def calc_team_stats(matches):
    """计算球队战绩"""
    team_stats = defaultdict(lambda: {'W':0, 'D':0, 'L':0, 'GF':0, 'GA':0, 'Pts':0, 'matches':[]})
    for m in matches:
        if not m.get('result'): continue
        ht, at = m.get('home_team', ''), m.get('away_team', '')
        if not ht or not at: continue

        hs, aws = m['home_score_ft'] or 0, m['away_score_ft'] or 0

        if m['result'] == 'H':
            team_stats[ht]['W'] += 1; team_stats[ht]['Pts'] += 3
            team_stats[at]['L'] += 1
        elif m['result'] == 'D':
            team_stats[ht]['D'] += 1; team_stats[ht]['Pts'] += 1
            team_stats[at]['D'] += 1; team_stats[at]['Pts'] += 1
        elif m['result'] == 'A':
            team_stats[at]['W'] += 1; team_stats[at]['Pts'] += 3
            team_stats[ht]['L'] += 1

        team_stats[ht]['GF'] += hs; team_stats[ht]['GA'] += aws
        team_stats[at]['GF'] += aws; team_stats[at]['GA'] += hs
        team_stats[ht]['matches'].append(m)
        team_stats[at]['matches'].append(m)

    return dict(team_stats)

# ===== 1. AF 2018/2022 比赛处理 =====

p("=" * 80)
p("  世界杯综合分析报告")
p("=" * 80)

for year in [2018, 2022]:
    af_data = load_json_safe(f'wc_{year}_af_matches.json')
    if not af_data:
        p(f"\n  WC {year}: 无AF数据")
        continue

    # 转换AF格式为统一格式
    matches = []
    for m in af_data:
        hs = m.get('match_hometeam_score')
        aws = m.get('match_awayteam_score')
        try:
            hs = int(hs) if hs not in (None, '', '-') else None
            aws = int(aws) if aws not in (None, '', '-') else None
        except:
            hs = None; aws = None

        result = None
        if hs is not None and aws is not None:
            if hs > aws: result = 'H'
            elif hs == aws: result = 'D'
            else: result = 'A'

        # 判断stage
        stage_name = m.get('stage_name', '')
        stage = 'GROUP' if 'GROUP' in stage_name.upper() or 'GROUP' in (m.get('league_name','')).upper() or m.get('match_day','') in ['1','2','3'] else 'KNOCKOUT'
        # AF用match_day: 1-3是小组赛
        md = m.get('match_day', '')
        if md in ['1', '2', '3']:
            stage = 'GROUP'
        elif md in ['4', '5', '6', '7']:
            stage = 'KNOCKOUT'

        matches.append({
            'home_team': m.get('match_hometeam_name', ''),
            'away_team': m.get('match_awayteam_name', ''),
            'home_score_ft': hs,
            'away_score_ft': aws,
            'result': result,
            'status': 'FINISHED' if result else 'SCHEDULED',
            'stage': stage,
            'stage_name': stage_name,
            'date': m.get('match_date', ''),
            'group': m.get('league_name', ''),
            'match_day': md,
            'source': 'apifootball',
            'raw': m
        })

    p(f"\n{'─' * 70}")
    p(f"  WC {year} 统计 (apifootball)")
    p(f"{'─' * 70}")

    stats = calc_match_stats(matches, f'WC {year}')
    if stats:
        p(f"\n  比赛场次: {stats['total']}")
        p(f"  总进球: {stats['goals']}  场均: {stats['avg_goals']:.2f}")
        p(f"  主胜: {stats['home_win_pct']:.1f}%  平局: {stats['draw_pct']:.1f}%  客胜: {stats['away_win_pct']:.1f}%")

    # 小组赛 vs 淘汰赛
    group_m = [m for m in matches if m['stage'] == 'GROUP' and m['result']]
    knockout_m = [m for m in matches if m['stage'] == 'KNOCKOUT' and m['result']]

    if group_m:
        gs = calc_match_stats(group_m, '小组赛')
        p(f"\n  小组赛: {gs['total']}场 场均{gs['avg_goals']:.2f}球")
        p(f"    主胜{gs['home_win_pct']:.1f}% 平{gs['draw_pct']:.1f}% 客胜{gs['away_win_pct']:.1f}%")

    if knockout_m:
        ks = calc_match_stats(knockout_m, '淘汰赛')
        p(f"\n  淘汰赛: {ks['total']}场 场均{ks['avg_goals']:.2f}球")
        p(f"    主胜{ks['home_win_pct']:.1f}% 平{ks['draw_pct']:.1f}% 客胜{ks['away_win_pct']:.1f}%")

    # 球队战绩
    team_stats = calc_team_stats(matches)
    p(f"\n  球队排名(按积分):")
    sorted_teams = sorted(team_stats.items(), key=lambda x: (-x[1]['Pts'], -(x[1]['GF']-x[1]['GA'])))
    for i, (team, s) in enumerate(sorted_teams[:16]):
        played = s['W'] + s['D'] + s['L']
        gd = s['GF'] - s['GA']
        p(f"    {i+1:>2}. {team:25s} P{played} W{s['W']} D{s['D']} L{s['L']} GF{s['GF']} GA{s['GA']} GD{gd:+d} Pts={s['Pts']}")

    # 进球分布
    if matches:
        goal_counts = Counter((m['home_score_ft'] or 0) + (m['away_score_ft'] or 0) for m in matches if m['result'])
        p(f"\n  进球分布:")
        for goals in sorted(goal_counts.keys()):
            pct = goal_counts[goals] / len([m for m in matches if m['result']]) * 100
            bar = '█' * int(pct)
            p(f"    {goals}球: {goal_counts[goals]:>3}场 ({pct:5.1f}%) {bar}")

# ===== 2. WC vs 联赛对比 =====
p(f"\n{'─' * 70}")
p(f"  WC vs 联赛差异分析")
p(f"{'─' * 70}")

# 从已有验证数据: 五大联赛 H=39.8% D=26.2% A=34.0% (v3.9.1 baseline)
# WC: 2018 H=37.5% D=23.4% A=39.1%, 2022 H=40.6% D=21.9% A=37.5%
p(f"\n  联赛(b365)参照: H≈39.8% D≈26.2% A≈34.0% 场均≈2.6")
p(f"  WC 2018:        H=37.5% D=23.4% A=39.1% 场均=2.64")
p(f"  WC 2022:        H=40.6% D=21.9% A=37.5% 场均=2.69")
p(f"\n  关键差异:")
p(f"  1. WC draw率(~22-23%) < 联赛(~26%) → 中立场地draw概率应降低")
p(f"  2. WC客胜率(~37-39%) > 联赛(~34%) → 中立场地削弱主场优势")
p(f"  3. 场均进球接近(~2.6-2.7) → 攻防平衡类似")

# ===== 3. 2026赛程分析 =====
p(f"\n{'─' * 70}")
p(f"  WC 2026 赛程分析")
p(f"{'─' * 70}")

# FD.org 2026 data
fd2026 = load_json_safe('wc_2026_matches.json')
af2026 = load_json_safe('wc_2026_af_matches.json')

if fd2026:
    scheduled = [m for m in fd2026 if m['status'] in ('SCHEDULED', 'TIMED')]
    p(f"\n  FD.org 2026: {len(fd2026)}场 (未开始{len(scheduled)})")

    # 按阶段
    stages = Counter(m.get('stage', 'Unknown') for m in fd2026)
    p(f"\n  阶段分布:")
    for stage, cnt in sorted(stages.items(), key=lambda x: -x[1]):
        p(f"    {stage}: {cnt}场")

    # 按分组
    groups = defaultdict(set)
    for m in fd2026:
        g = m.get('group', '')
        if g and 'GROUP' in g.upper():
            if m['home_team']: groups[g].add(m['home_team'])
            if m['away_team']: groups[g].add(m['away_team'])

    p(f"\n  分组({len(groups)}个):")
    for g in sorted(groups.keys()):
        teams_str = ', '.join(sorted(groups[g]))
        p(f"    {g}: {teams_str}")

    # 时间范围
    dates = [m['date'] for m in fd2026 if m.get('date')]
    if dates:
        p(f"\n  时间: {min(dates)} ~ {max(dates)}")

if af2026:
    p(f"\n  AF 2026: {len(af2026)}场")

# ===== 4. 球队阵容分析 =====
p(f"\n{'─' * 70}")
p(f"  WC 2026 球队阵容分析")
p(f"{'─' * 70}")

teams_2026 = load_json_safe('wc_2026_teams.json')
if teams_2026:
    p(f"\n  总球队: {len(teams_2026)}")

    # 阵容人数
    squad_sizes = [(t['short_name'], t['squad_size']) for t in teams_2026 if t.get('squad_size')]
    if squad_sizes:
        sizes = [s[1] for s in squad_sizes]
        p(f"  阵容人数: 平均{sum(sizes)/len(sizes):.1f} 最多{max(sizes)} 最少{min(sizes)}")

    # 位置分布
    all_positions = Counter()
    for t in teams_2026:
        for pl in t.get('squad', []):
            pos = pl.get('position', 'Unknown')
            if pos: all_positions[pos] += 1

    p(f"\n  位置分布(全部):")
    for pos, cnt in sorted(all_positions.items(), key=lambda x: -x[1]):
        p(f"    {pos}: {cnt}")

    # 各队阵容概要
    p(f"\n  各队阵容:")
    for t in sorted(teams_2026, key=lambda x: -x.get('squad_size', 0)):
        squad = t.get('squad', [])
        positions = Counter(pl.get('position', '?') for pl in squad)
        pos_str = ' '.join(f"{(k or '?')[:3]}{v}" for k, v in sorted(positions.items(), key=lambda x: x[0] or '') if k)
        p(f"    {t['short_name']:20s} {t['squad_size']:>2}人 [{pos_str}]")

    # 识别球星(从AF 2022 lineup中的知名球员)
    p(f"\n  注意: 当前阵容为基础名单，世界杯开赛前会有最终23/26人名单更新")

# ===== 5. AF 2022 球员表现分析 =====
p(f"\n{'─' * 70}")
p(f"  WC 2022 球员表现统计 (来自AF比赛数据)")
p(f"{'─' * 70}")

af2022 = load_json_safe('wc_2022_af_matches.json')
if af2022:
    # 从goalscorer提取射手榜
    goal_scorers = defaultdict(lambda: {'goals': 0, 'assists': 0, 'team': ''})
    for m in af2022:
        gs = m.get('goalscorer', [])
        if not gs: continue
        for g in gs:
            if isinstance(g, dict):
                scorer = g.get('player_name', '')
                team = g.get('team_name', '')
                if scorer and g.get('time', {}).get('from', ''):
                    goal_scorers[scorer]['goals'] += 1
                    goal_scorers[scorer]['team'] = team
                # Assist
                assist = g.get('assist_name', '')
                if assist:
                    goal_scorers[assist]['assists'] += 1
                    if not goal_scorers[assist]['team']:
                        goal_scorers[assist]['team'] = team

    # 射手榜
    p(f"\n  射手榜:")
    for i, (name, s) in enumerate(sorted(goal_scorers.items(), key=lambda x: (-x[1]['goals'], -x[1]['assists']))[:20]):
        p(f"    {i+1:>2}. {name:25s} ({s['team']:15s}) {s['goals']}球 {s['assists']}助")

    # 从statistics提取球队比赛统计
    team_match_stats = defaultdict(list)
    for m in af2022:
        stats = m.get('statistics', [])
        if not stats: continue
        for s in stats:
            if isinstance(s, dict):
                team = s.get('team_name', '')
                if team:
                    team_match_stats[team].append(s)

    if team_match_stats:
        p(f"\n  球队平均比赛统计:")
        p(f"  {'球队':20s} {'场次':>4} {'射门':>6} {'射正':>6} {'控球%':>6} {'传球':>6} {'犯规':>6} {'角球':>6}")
        for team in sorted(team_match_stats.keys()):
            ms = team_match_stats[team]
            n = len(ms)
            avg_shots = sum(int(s.get('total_shots', 0) or 0) for s in ms) / n
            avg_sot = sum(int(s.get('shots_on_target', 0) or 0) for s in ms) / n
            avg_poss = sum(float(s.get('ball_possession', '0').replace('%','') or 0) for s in ms) / n
            avg_pass = sum(int(s.get('total_passes', 0) or 0) for s in ms) / n
            avg_fouls = sum(int(s.get('fouls', 0) or 0) for s in ms) / n
            avg_corners = sum(int(s.get('corner_kicks', 0) or 0) for s in ms) / n
            p(f"  {team:20s} {n:>4} {avg_shots:>6.1f} {avg_sot:>6.1f} {avg_poss:>5.1f}% {avg_pass:>6.0f} {avg_fouls:>6.1f} {avg_corners:>6.1f}")

# ===== 6. 跨届战绩分析 =====
p(f"\n{'─' * 70}")
p(f"  2018+2022跨届战绩(世界杯常客)")
p(f"{'─' * 70}")

combined_team_stats = defaultdict(lambda: {'W':0, 'D':0, 'L':0, 'GF':0, 'GA':0, 'tournaments':set()})

for year in [2018, 2022]:
    af_data = load_json_safe(f'wc_{year}_af_matches.json')
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

        combined_team_stats[ht]['tournaments'].add(year)
        combined_team_stats[at]['tournaments'].add(year)

        if hs > aws:
            combined_team_stats[ht]['W'] += 1; combined_team_stats[at]['L'] += 1
        elif hs == aws:
            combined_team_stats[ht]['D'] += 1; combined_team_stats[at]['D'] += 1
        else:
            combined_team_stats[at]['W'] += 1; combined_team_stats[ht]['L'] += 1

        combined_team_stats[ht]['GF'] += hs; combined_team_stats[ht]['GA'] += aws
        combined_team_stats[at]['GF'] += aws; combined_team_stats[at]['GA'] += hs

both_tournaments = {k: v for k, v in combined_team_stats.items() if len(v['tournaments']) == 2}
p(f"\n  两届均参加的球队: {len(both_tournaments)}")

p(f"\n  {'球队':25s} {'P':>3} {'W':>3} {'D':>3} {'L':>3} {'GF':>3} {'GA':>3} {'GD':>4} {'Pts':>4} {'胜率':>6}")
for team, s in sorted(both_tournaments.items(), key=lambda x: -(x[1]['W']*3 + x[1]['D'])):
    played = s['W'] + s['D'] + s['L']
    gd = s['GF'] - s['GA']
    pts = s['W'] * 3 + s['D']
    win_rate = s['W'] / played * 100 if played > 0 else 0
    p(f"  {team:25s} {played:>3} {s['W']:>3} {s['D']:>3} {s['L']:>3} {s['GF']:>3} {s['GA']:>3} {gd:>+4} {pts:>4} {win_rate:>5.1f}%")

# ===== 7. 世界杯模型预测要点 =====
p(f"\n{'─' * 70}")
p(f"  世界杯模型预测要点")
p(f"{'─' * 70}")

p(f"""
  1. 中立场地效应
     - WC draw率(22-23%)显著低于联赛(26%)
     - 无主场优势 → H/A概率应向中间收敛
     - 模型需要: 减弱home advantage权重，draw概率降低

  2. 小组赛 vs 淘汰赛
     - 小组赛: draw率较高(~25%)，可接受平局
     - 淘汰赛: draw率较低(~15%)，但加时赛增加
     - 第3轮小组赛: 战意不对称时需特殊处理

  3. 战意/动机
     - 第3轮小组赛: 出线/出局队之间动机差异巨大
     - 淘汰赛: 双方都需赢 → draw回调可能更合理
     - 决赛/半决赛: 心理压力增大 → 大概率低比分

  4. 实力评估
     - 国家队比赛间隔长 → 近期状态难评估
     - 依赖: 球员身价/俱乐部表现 + 历届WC战绩
     - 弱队面对强队: WC中的"奇迹"概率高于联赛

  5. 赔率特点
     - WC赔率市场流动性高 → 隐含概率更可靠
     - b365等对WC有专门市场
     - 中立场地 → 赔率本身已反映无主场优势
""")

# ===== 8. 2026分组实力评估 =====
p(f"{'─' * 70}")
p(f"  WC 2026 分组实力评估")
p(f"{'─' * 70}")

if teams_2026:
    # 用历史战绩+阵容评估分组实力
    group_teams = defaultdict(list)
    for t in teams_2026:
        name = t['short_name']
        # 从历史战绩取实力评分
        hist = combined_team_stats.get(name, None) or combined_team_stats.get(t['name'], None)
        if hist:
            played = hist['W'] + hist['D'] + hist['L']
            pts = hist['W'] * 3 + hist['D']
            rating = pts / played if played > 0 else 1.0
        else:
            rating = 0  # 无历史数据

        # 用squad size作为辅助
        squad_bonus = min(t.get('squad_size', 0) / 26.0, 1.0)  # 26人满编=1.0

        t['history_rating'] = rating
        t['squad_bonus'] = squad_bonus
        t['overall_rating'] = (rating * 0.7 + squad_bonus * 0.3) if rating > 0 else squad_bonus * 0.5

    # 重建分组(从FD 2026 matches)
    if fd2026:
        group_teams_fd = defaultdict(set)
        for m in fd2026:
            g = m.get('group', '')
            if g and 'GROUP' in g.upper():
                if m['home_team']: group_teams_fd[g].add(m['home_team'])
                if m['away_team']: group_teams_fd[g].add(m['away_team'])

        # 建立team name -> rating映射
        name_to_rating = {}
        for t in teams_2026:
            name_to_rating[t['short_name']] = t['overall_rating']
            name_to_rating[t['name']] = t['overall_rating']

        p(f"\n  分组实力排名(基于2018+2022战绩+阵容):")
        group_rankings = {}
        for g in sorted(group_teams_fd.keys()):
            teams_in_group = sorted(group_teams_fd[g])
            p(f"\n  {g}:")
            group_ratings = []
            for team_name in teams_in_group:
                r = name_to_rating.get(team_name, 0)
                hist = combined_team_stats.get(team_name, None)
                if hist:
                    played = hist['W'] + hist['D'] + hist['L']
                    record = f"W{hist['W']}D{hist['D']}L{hist['L']}"
                else:
                    played = 0
                    record = "no_hist"
                p(f"    {team_name:25s} 评分:{r:.2f} ({record})")
                group_ratings.append((team_name, r))
            group_rankings[g] = sorted(group_ratings, key=lambda x: -x[1])

        # 识别死亡之组
        p(f"\n  分组竞争度(最高评分-最低评分, 差距越小越激烈):")
        for g, ratings in sorted(group_rankings.items(), key=lambda x: (x[1][0][1] - x[1][-1][1]) if len(x[1]) >= 2 else 999):
            if len(ratings) < 2: continue
            spread = ratings[0][1] - ratings[-1][1]
            avg = sum(r for _, r in ratings) / len(ratings)
            p(f"    {g}: spread={spread:.2f} avg={avg:.2f} {'★死亡之组★' if spread < 0.5 and avg > 1.5 else ''}")

p(f"\n{'=' * 80}")
p("  分析完成")
p("=" * 80)

report = '\n'.join(lines)
with open(os.path.join(DATA_DIR, 'analysis_report.txt'), 'w', encoding='utf-8') as f:
    f.write(report)
print(report)
