"""
手动分析比赛 — 用用户提供的赔率数据直接计算

不需要从API采集，直接输入赔率和队名即可
"""
import sys, io, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def implied_prob(odds_h, odds_d, odds_a):
    """从赔率计算隐含概率"""
    margin = 1/odds_h + 1/odds_d + 1/odds_a
    return {
        'home': 1/(odds_h * margin),
        'draw': 1/(odds_d * margin),
        'away': 1/(odds_a * margin),
    }

def ev(model_prob, odds):
    """计算EV = model_prob × fair_odds - 1"""
    margin = 1/odds['h'] + 1/odds['d'] + 1/odds['a']
    fair = {
        'home': odds['h'] * margin,
        'draw': odds['d'] * margin,
        'away': odds['a'] * margin,
    }
    return {
        'home': model_prob['home'] * fair['home'] - 1,
        'draw': model_prob['draw'] * fair['draw'] - 1,
        'away': model_prob['away'] * fair['away'] - 1,
    }

def poisson_score(home_lambda, away_lambda):
    """泊松比分概率矩阵"""
    from math import exp, factorial
    def poisson(lam, k):
        return (lam**k) * exp(-lam) / factorial(k)

    scores = {}
    home_win = draw = away_win = over25 = 0
    for i in range(6):
        for j in range(6):
            p = poisson(home_lambda, i) * poisson(away_lambda, j)
            scores[f"{i}-{j}"] = round(p, 4)
            if i > j: home_win += p
            elif i == j: draw += p
            else: away_win += p
            if i + j > 2.5: over25 += p
    top5 = sorted(scores.items(), key=lambda x: -x[1])[:5]
    return home_win, draw, away_win, over25, top5

def analyze_match(home, away, league, odds_h, odds_d, odds_a,
                  home_motivation=None, away_motivation=None,
                  home_rest=None, away_rest=None,
                  home_score=None, away_score=None):
    """完整分析一场比赛"""

    # 1. 赔率隐含概率
    market = implied_prob(odds_h, odds_d, odds_a)

    # 2. 泊松进球 — 从赔率O/U近似推算total_lambda
    # 简化: 用赔率隐含概率推算两队进球比例
    non_draw = market['home'] + market['away']
    home_ratio = market['home'] / non_draw + 0.05  # 主场加成
    home_ratio = min(0.70, home_ratio)

    # total_lambda = 2.6 (默认)，如果赔率主胜概率高则略高
    total_lambda = 2.6 + (non_draw - 0.74) * 0.5  # 偏主/客时总进球略多
    home_lambda = total_lambda * home_ratio
    away_lambda = total_lambda * (1 - home_ratio)

    pois_h, pois_d, pois_a, over25, top5 = poisson_score(home_lambda, away_lambda)

    # 3. 模型概率 = 赔率70% + 泊松30%
    model_home = market['home'] * 0.7 + pois_h * 0.3
    model_draw = market['draw'] * 0.7 + pois_d * 0.3
    model_away = market['away'] * 0.7 + pois_a * 0.3
    total = model_home + model_draw + model_away
    model_home /= total
    model_draw /= total
    model_away /= total

    # 4. 基本面调整
    adjustments = []
    if home_motivation and away_motivation:
        mot_strength = {
            'title_race': 1.0, 'european': 0.6, 'relegation': 0.8,
            'relegation_battle': 0.9, 'mid_table': 0.0, 'dead_rubber': -0.5,
        }
        hm = mot_strength.get(home_motivation, 0)
        am = mot_strength.get(away_motivation, 0)
        diff = hm - am
        boost = diff * 0.04 * 1.5 if abs(diff) > 0.5 else diff * 0.04
        if abs(boost) > 0.001:
            adjustments.append(f"动机差: {home_motivation} vs {away_motivation} → {diff:+.1f} → 调整{boost:+.2%}")
            model_home += boost
            model_away -= boost * 0.7
            model_draw -= boost * 0.3
            total = model_home + model_draw + model_away
            model_home /= total; model_draw /= total; model_away /= total

    # 5. 疲劳调整
    if home_rest and away_rest:
        if min(home_rest, away_rest) < 4:
            tired = "主队" if home_rest < away_rest else "客队"
            boost = 0.03 if home_rest < away_rest else -0.03
            adjustments.append(f"疲劳: {tired}休息不足({min(home_rest,away_rest)}天)")
            model_home += boost
            model_away -= boost * 0.7
            model_draw -= boost * 0.3
            total = model_home + model_draw + model_away
            model_home /= total; model_draw /= total; model_away /= total

    # 6. EV
    e = ev({'home': model_home, 'draw': model_draw, 'away': model_away},
           {'h': odds_h, 'd': odds_d, 'a': odds_a})

    # 7. 预测方向
    pred = max(['home', 'draw', 'away'], key=lambda x: {'home': model_home, 'draw': model_draw, 'away': model_away}[x])
    pred_cn = {'home': '主胜', 'draw': '平局', 'away': '客胜'}[pred]

    # 大小球
    ou_dir = "大2.5球" if over25 > 0.52 else "小2.5球"

    # 结果
    result_str = ""
    if home_score is not None and away_score is not None:
        actual = 'home' if home_score > away_score else 'draw' if home_score == away_score else 'away'
        actual_cn = {'home': '主胜', 'draw': '平局', 'away': '客胜'}[actual]
        correct = pred == actual
        result_str = f"\n  实际结果: {actual_cn} ({home_score}-{away_score}) 预测{'正确' if correct else '错误'}"

    output = f"""
{'='*60}
  {league}: {home} vs {away}
{'='*60}
  赔率隐含概率: 主{market['home']*100:.1f}% 平{market['draw']*100:.1f}% 客{market['away']*100:.1f}%

  泊松模型:
    期望进球: 主{home_lambda:.2f} 客{away_lambda:.2f} 总{home_lambda+away_lambda:.2f}
    最可能比分: {top5[0][0]}({top5[0][1]*100:.1f}%)
    TOP5: {', '.join(f'{s}({p*100:.1f}%)' for s,p in top5)}

  模型概率(综合):
    主胜 {model_home*100:.1f}%  平局 {model_draw*100:.1f}%  客胜 {model_away*100:.1f}%

  预测方向: {pred_cn}
  大小球: {ou_dir} (大2.5={over25*100:.0f}%)

  EV分析:
    主胜EV={e['home']:+.2%}  平局EV={e['draw']:+.2%}  客胜EV={e['away']:+.2%}
    最优方向: {max(['home','draw','away'], key=lambda x: e[x])} (EV={max(e.values()):+.2%})
"""
    if adjustments:
        output += f"\n  场景信号:\n"
        for a in adjustments:
            output += f"    {a}\n"

    output += result_str
    output += f"\n{'='*60}"
    return output


# === 分析用户提供的比赛 ===

print(analyze_match(
    "St Etienne", "Nice", "法甲/Ligue 1",
    2.80, 3.17, 2.77,
    home_motivation="relegation_battle", away_motivation="mid_table",
    home_score=0, away_score=0  # 0-0平局
))

print(analyze_match(
    "Crystal Palace", "Rayo Vallecano", "欧协联/Conference League",
    2.00, 3.25, 3.90,
    home_motivation="european", away_motivation="mid_table",
))

print(analyze_match(
    "U. de Deportes", "Deportes Tolima", "解放者杯/Copa Libertadores",
    2.13, 3.09, 4.07,
    home_score=0, away_score=0
))

print(analyze_match(
    "Estudiantes L.P.", "Ind. Medellin", "解放者杯/Copa Libertadores",
    1.72, 3.57, 5.44,
    home_score=1, away_score=0
))

print(analyze_match(
    "Nacional", "Coquimbo", "解放者杯/Copa Libertadores",
    2.25, 3.34, 3.36,
    home_score=1, away_score=0
))

print(analyze_match(
    "Flamengo RJ", "Cusco", "解放者杯/Copa Libertadores",
    1.08, 10.88, 24.30,
    home_score=3, away_score=0,
    home_motivation="title_race"
))

print(analyze_match(
    "Ind. del Valle", "Rosario", "解放者杯/Copa Libertadores",
    1.97, 3.30, 3.98,
))

print(analyze_match(
    "Libertad", "Universidad Central", "解放者杯/Copa Libertadores",
    1.38, 5.00, 7.50,
    home_motivation="title_race"
))