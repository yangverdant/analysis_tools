"""
比赛预测报告生成器 v1

输出完整预测链:
1. 赔率隐含概率 → 基础方向
2. 泊松进球模型 → 最可能比分 → 大小球
3. 基本面增量 → 动机/疲劳/伤病 → 概率调整
4. 场景检测 → CLV+动机同向 → 信息差
5. 最终概率 + 投注建议
"""

import sys, io, json, sqlite3, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

from fetchers.storage.crud import UnifiedStorage
from fetchers.analysis import run_all_factors, run_model

DB_PATH = 'd:/football_tools/data/unified_football.db'


def generate_report(match_key: str, storage=None):
    if storage is None:
        storage = UnifiedStorage()

    # 提取因素
    factors = run_all_factors(match_key, storage, force=True)

    # 运行两个模型
    el_result = run_model('enhanced_linear', match_key, storage, force=True)
    ch_result = run_model('chain', match_key, storage, force=True)

    # 比赛信息
    match = storage.get_match(match_key)

    # 因素摘要
    factor_summary = []
    for fname, f in sorted(factors.items(), key=lambda x: -abs(x[1].get('diff', 0))):
        if f.get('confidence', 0) <= 0:
            continue
        diff = f.get('diff', 0)
        direction = "→主" if diff > 0.02 else "→客" if diff < -0.02 else "≈平"
        factor_summary.append({
            'name': fname,
            'direction': direction,
            'diff': round(diff, 3),
            'confidence': f.get('confidence', 0),
        })

    # 场景检测
    scenarios = []
    clv_f = factors.get('odds_movement')
    mot_f = factors.get('motivation')
    rest_f = factors.get('rest_days')

    if clv_f and mot_f and clv_f.get('confidence', 0) > 0 and mot_f.get('confidence', 0) > 0:
        clv_diff = clv_f.get('diff', 0)
        mot_diff = mot_f.get('diff', 0)
        if abs(clv_diff) > 0.03 and abs(mot_diff) > 0.3 and clv_diff * mot_diff > 0:
            scenarios.append("CLV+动机同向 ★")  # 信息差

    if rest_f and rest_f.get('confidence', 0) > 0:
        home_rest = rest_f.get('home_value', 7)
        away_rest = rest_f.get('away_value', 7)
        if home_rest < 4 or away_rest < 4:
            tired = "主队" if home_rest < away_rest else "客队"
            scenarios.append(f"疲劳差异: {tired}休息不足({min(home_rest, away_rest)}天)")

    # 输出
    hp_el = el_result.get('home_win_prob', 0)
    dp_el = el_result.get('draw_prob', 0)
    ap_el = el_result.get('away_win_prob', 0)

    hp_ch = ch_result.get('home_win_prob', 0)
    dp_ch = ch_result.get('draw_prob', 0)
    ap_ch = ch_result.get('away_win_prob', 0)

    # 综合概率 (EL 60% + Chain 40%)
    hp = hp_el * 0.6 + hp_ch * 0.4
    dp = dp_el * 0.6 + dp_ch * 0.4
    ap = ap_el * 0.6 + ap_ch * 0.4
    total = hp + dp + ap
    hp /= total; dp /= total; ap /= total

    # 预测方向
    pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
    pred_label = {'home': '主胜', 'draw': '平局', 'away': '客胜'}[pred]

    # EV
    ev = el_result.get('ev', {})
    best_ev_dir = max(['home', 'draw', 'away'], key=lambda x: ev.get(x, -1))
    best_ev_val = ev.get(best_ev_dir, 0)
    ev_label = {'home': '主胜', 'draw': '平局', 'away': '客胜'}[best_ev_dir]

    # 大小球
    o25 = el_result.get('over_2_5_prob', 0.5)

    # 泊松
    most_likely = ch_result.get('most_likely_score', '')
    top5 = ch_result.get('top5_scores', [])
    home_lambda = ch_result.get('home_lambda', 0)
    away_lambda = ch_result.get('away_lambda', 0)

    report = {
        'match_key': match_key,
        'prediction': pred_label,
        'probabilities': {
            'home': round(hp, 3),
            'draw': round(dp, 3),
            'away': round(ap, 3),
        },
        'model_comparison': {
            'enhanced_linear': {'home': round(hp_el, 3), 'draw': round(dp_el, 3), 'away': round(ap_el, 3)},
            'chain': {'home': round(hp_ch, 3), 'draw': round(dp_ch, 3), 'away': round(ap_ch, 3)},
        },
        'over_under': {
            'over_2_5': round(o25, 3),
            'under_2_5': round(1 - o25, 3),
            'direction': '大2.5球' if o25 > 0.52 else '小2.5球',
        },
        'poisson': {
            'home_lambda': round(home_lambda, 2),
            'away_lambda': round(away_lambda, 2),
            'total_expected': round(home_lambda + away_lambda, 2),
            'most_likely_score': most_likely,
            'top5_scores': top5,
        },
        'ev': {
            'best_direction': ev_label,
            'best_ev': round(best_ev_val, 4),
            'all_ev': {k: round(v, 4) for k, v in ev.items()},
        },
        'scenarios': scenarios,
        'key_factors': factor_summary[:5],
        'confidence': el_result.get('confidence', 0),
    }

    return report


def print_report(report):
    print(f"\n{'='*60}")
    print(f"  比赛: {report['match_key']}")
    print(f"{'='*60}")
    print(f"  预测方向: {report['prediction']}")
    print(f"  概率: 主{report['probabilities']['home']*100:.1f}% "
          f"平{report['probabilities']['draw']*100:.1f}% "
          f"客{report['probabilities']['away']*100:.1f}%")
    print(f"")
    print(f"  大小球: {report['over_under']['direction']} "
          f"(大2.5={report['over_under']['over_2_5']*100:.0f}%)")
    print(f"")
    print(f"  泊松模型:")
    print(f"    期望进球: 主{report['poisson']['home_lambda']} 客{report['poisson']['away_lambda']} "
          f"总{report['poisson']['total_expected']}")
    print(f"    最可能比分: {report['poisson']['most_likely_score']}")
    if report['poisson']['top5_scores']:
        print(f"    TOP5比分: {', '.join(f'{s[0]}({s[1]*100:.1f}%)' for s in report['poisson']['top5_scores'])}")
    print(f"")
    print(f"  EV分析:")
    print(f"    最优方向: {report['ev']['best_direction']} (EV={report['ev']['best_ev']:+.2%})")
    for d, v in report['ev']['all_ev'].items():
        label = {'home': '主胜', 'draw': '平局', 'away': '客胜'}[d]
        print(f"    {label}: {v:+.2%}")
    print(f"")
    if report['scenarios']:
        print(f"  场景信号:")
        for s in report['scenarios']:
            print(f"    ★ {s}")
    print(f"")
    print(f"  关键因素:")
    for f in report['key_factors']:
        print(f"    {f['name']:20s} {f['direction']} (diff={f['diff']:+.3f} conf={f['confidence']:.2f})")
    print(f"")
    print(f"  模型对比:")
    el = report['model_comparison']['enhanced_linear']
    ch = report['model_comparison']['chain']
    print(f"    EL:  主{el['home']*100:.1f}% 平{el['draw']*100:.1f}% 客{el['away']*100:.1f}%")
    print(f"    Chain: 主{ch['home']*100:.1f}% 平{ch['draw']*100:.1f}% 客{ch['away']*100:.1f}%")
    print(f"{'='*60}")


if __name__ == "__main__":
    storage = UnifiedStorage()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 取几场最近的比赛
    matches = conn.execute(
        "SELECT match_key FROM matches "
        "WHERE status='finished' AND home_score IS NOT NULL AND away_score IS NOT NULL "
        "ORDER BY date DESC LIMIT 3"
    ).fetchall()
    conn.close()

    for m in matches:
        report = generate_report(m['match_key'], storage)
        print_report(report)