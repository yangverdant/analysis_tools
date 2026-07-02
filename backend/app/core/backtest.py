"""一键回测 — 验证模型虚拟投注收益

从lottery_validation+lottery_odds计算:
1. 按模型推荐SPF投注, 每场虚拟100元
2. 累计盈亏、胜率、ROI
3. 按场景(赛事类型)分组统计
"""
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    total_matches: int = 0
    total_stake: float = 0
    total_return: float = 0
    total_profit: float = 0
    roi: float = 0
    win_count: int = 0
    win_rate: float = 0
    brier_avg: float = 0
    by_scene: Dict = field(default_factory=dict)
    by_date: List[Dict] = field(default_factory=list)
    daily_profit: List[Dict] = field(default_factory=list)


def run_backtest(db_path: str, days: int = 30, stake_per_match: float = 100) -> BacktestResult:
    """执行回测 — 按模型推荐SPF虚拟投注"""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff = str(date.today() - timedelta(days=days))

    # 获取验证记录(有结果的)
    cursor.execute("""
        SELECT
            lv.lottery_match_id,
            lv.predicted_result,
            lv.actual_result,
            lv.is_correct,
            lv.predicted_prob,
            lv.brier_score,
            lv.attribution,
            lv.scenario_type,
            lm.home_team_cn,
            lm.away_team_cn,
            lm.league_name_cn,
            lm.match_date
        FROM lottery_validation lv
        JOIN lottery_matches lm ON lv.lottery_match_id = lm.lottery_match_id
        WHERE lv.validated_at >= ? AND lv.play_type = 'spf'
        ORDER BY lm.match_date
    """, (cutoff,))

    rows = [dict(r) for r in cursor.fetchall()]

    if not rows:
        conn.close()
        return BacktestResult()

    result = BacktestResult()
    scene_stats = {}
    cumulative_profit = 0

    for row in rows:
        match_id = row['lottery_match_id']
        predicted = row['predicted_result']
        actual = row['actual_result']
        is_correct = row['is_correct']
        match_date = row['match_date']

        # 获取投注时的赔率
        odds = _get_bet_odds(cursor, match_id, predicted)
        if not odds or odds <= 1:
            continue  # 无赔率,跳过

        # 计算盈亏
        stake = stake_per_match
        if is_correct:
            payout = stake * odds
            profit = payout - stake
            result.win_count += 1
        else:
            payout = 0
            profit = -stake

        result.total_matches += 1
        result.total_stake += stake
        result.total_return += payout
        result.total_profit += profit
        if row['brier_score']:
            result.brier_avg += row['brier_score']

        cumulative_profit += profit

        # 按场景统计
        scene = row.get('scenario_type') or 'unknown'
        if scene not in scene_stats:
            scene_stats[scene] = {'matches': 0, 'stake': 0, 'profit': 0, 'wins': 0}
        scene_stats[scene]['matches'] += 1
        scene_stats[scene]['stake'] += stake
        scene_stats[scene]['profit'] += profit
        if is_correct:
            scene_stats[scene]['wins'] += 1

        # 每日统计
        result.daily_profit.append({
            'date': match_date,
            'match': f"{row['home_team_cn']}vs{row['away_team_cn']}",
            'league': row['league_name_cn'],
            'predicted': predicted,
            'actual': actual,
            'odds': round(odds, 2),
            'correct': bool(is_correct),
            'profit': round(profit, 1),
            'cumulative': round(cumulative_profit, 1),
            'scene': scene,
            'attribution': row.get('attribution'),
        })

    # 汇总
    if result.total_matches > 0:
        result.win_rate = round(result.win_count / result.total_matches, 4)
        result.roi = round(result.total_profit / result.total_stake, 4) if result.total_stake > 0 else 0
        result.brier_avg = round(result.brier_avg / result.total_matches, 4)

    # 场景汇总
    for scene, stats in scene_stats.items():
        if stats['matches'] > 0:
            stats['win_rate'] = round(stats['wins'] / stats['matches'], 4)
            stats['roi'] = round(stats['profit'] / stats['stake'], 4) if stats['stake'] > 0 else 0
    result.by_scene = scene_stats

    # 按日期汇总
    date_groups = {}
    for dp in result.daily_profit:
        d = dp['date']
        if d not in date_groups:
            date_groups[d] = {'date': d, 'matches': 0, 'profit': 0, 'wins': 0}
        date_groups[d]['matches'] += 1
        date_groups[d]['profit'] += dp['profit']
        if dp['correct']:
            date_groups[d]['wins'] += 1
    result.by_date = sorted(date_groups.values(), key=lambda x: x['date'])

    conn.close()
    return result


def _get_bet_odds(cursor, match_id: str, predicted: str) -> float:
    """获取投注赔率 — lottery_odds优先, report赔率基线备选, 模型概率兜底"""
    # 1. 从lottery_odds获取体彩赔率
    try:
        cursor.execute("""
            SELECT odds_data FROM lottery_odds
            WHERE lottery_match_id = ? AND play_type IN ('spf', 'rqspf')
            ORDER BY play_type, created_at DESC LIMIT 1
        """, (match_id,))
        row = cursor.fetchone()
        if row:
            odds_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            odds_value = float(odds_data.get(predicted, 0))
            if odds_value > 1:
                return odds_value
    except Exception:
        pass

    # 2. 从prediction report的赔率基线反推赔率
    try:
        cursor.execute("""
            SELECT report_data FROM lottery_analysis_reports
            WHERE lottery_match_id = ? AND report_type = 'prediction'
              AND (is_stale = 0 OR is_stale IS NULL)
            ORDER BY created_at DESC, rowid DESC
            LIMIT 1
        """, (match_id,))
        row = cursor.fetchone()
        if row:
            report = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            odds_baseline = report.get('odds_baseline')
            if odds_baseline:
                key_map = {'3': 'home_win', '1': 'draw', '0': 'away_win'}
                prob_key = key_map.get(predicted, predicted)
                prob = float(odds_baseline.get(prob_key, 0))
                if prob > 0.01:
                    return round(1.0 / prob * 1.08, 2)  # 8% margin

            # 3. 从模型概率推导(最低赔率估算)
            probs = report.get('final_prediction', {}).get('probabilities', {})
            key_map = {'3': 'home_win', '1': 'draw', '0': 'away_win'}
            prob_key = key_map.get(predicted, predicted)
            prob = float(probs.get(prob_key, 0))
            if prob > 0.05:
                return round(1.0 / prob * 1.12, 2)  # 12% margin(更保守)
    except Exception:
        pass

    return 0


def backtest_to_dict(result: BacktestResult) -> dict:
    """转换为API返回格式"""
    return {
        'summary': {
            'total_matches': result.total_matches,
            'total_stake': round(result.total_stake, 1),
            'total_return': round(result.total_return, 1),
            'total_profit': round(result.total_profit, 1),
            'roi': f"{result.roi:.1%}",
            'win_count': result.win_count,
            'win_rate': f"{result.win_rate:.1%}",
            'brier_avg': result.brier_avg,
        },
        'by_scene': {
            k: {kk: (f"{vv:.1%}" if kk in ('win_rate', 'roi') else round(vv, 1) if isinstance(vv, float) else vv)
                for kk, vv in v.items()}
            for k, v in result.by_scene.items()
        },
        'by_date': result.by_date,
        'daily_detail': result.daily_profit[-20:],  # 最近20场详情
    }
