"""
预测模型优化引擎
基于复盘数据自动优化模型参数，形成预测-复盘-优化闭环
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'football_v2.db')


class ModelParameters:
    """模型参数管理"""

    # 当前模型参数
    CURRENT_PARAMS = {
        # 权重参数
        'fifa_rank_weight': 0.30,      # FIFA排名权重
        'elo_weight': 0.25,            # Elo评分权重
        'form_weight': 0.20,           # 近期状态权重
        'h2h_weight': 0.15,            # 历史交锋权重
        'home_advantage_weight': 0.10, # 主场优势权重

        # 特殊场景参数
        'friendly_draw_boost': 0.15,   # 友谊赛平局概率提升
        'low_motivation_draw_boost': 0.10,  # 低动机场次平局提升
        'rank_diff_threshold': 30,     # 排名差距阈值
        'form_diff_threshold': 20,     # 状态差距阈值

        # 进球预测参数
        'base_goals': 2.5,             # 基准进球数
        'form_goals_impact': 0.3,      # 状态对进球影响
        'friendly_goals_reduction': 0.3,  # 友谊赛进球减少

        # 风险控制
        'min_confidence': 0.35,        # 最低置信度
        'max_draw_prob': 0.40,         # 最大平局概率
        'upset_threshold': 0.25,       # 爆冷阈值
    }

    # 参数调整约束
    PARAM_CONSTRAINTS = {
        'fifa_rank_weight': {'min': 0.10, 'max': 0.50, 'step': 0.05},
        'elo_weight': {'min': 0.10, 'max': 0.40, 'step': 0.05},
        'form_weight': {'min': 0.10, 'max': 0.35, 'step': 0.05},
        'h2h_weight': {'min': 0.05, 'max': 0.25, 'step': 0.05},
        'home_advantage_weight': {'min': 0.05, 'max': 0.20, 'step': 0.02},
        'friendly_draw_boost': {'min': 0.05, 'max': 0.30, 'step': 0.03},
        'low_motivation_draw_boost': {'min': 0.05, 'max': 0.25, 'step': 0.03},
        'rank_diff_threshold': {'min': 15, 'max': 50, 'step': 5},
        'form_diff_threshold': {'min': 10, 'max': 35, 'step': 5},
        'base_goals': {'min': 2.0, 'max': 3.0, 'step': 0.1},
        'form_goals_impact': {'min': 0.1, 'max': 0.5, 'step': 0.05},
        'friendly_goals_reduction': {'min': 0.1, 'max': 0.5, 'step': 0.05},
        'min_confidence': {'min': 0.25, 'max': 0.45, 'step': 0.05},
        'max_draw_prob': {'min': 0.30, 'max': 0.50, 'step': 0.05},
        'upset_threshold': {'min': 0.15, 'max': 0.35, 'step': 0.05},
    }

    @classmethod
    def get_params(cls):
        return cls.CURRENT_PARAMS.copy()

    @classmethod
    def update_param(cls, param_name: str, new_value: float, reason: str = ''):
        """更新参数并记录"""
        if param_name not in cls.CURRENT_PARAMS:
            raise ValueError(f"未知参数: {param_name}")

        constraint = cls.PARAM_CONSTRAINTS.get(param_name, {})
        new_value = max(constraint.get('min', 0), min(constraint.get('max', 1), new_value))

        old_value = cls.CURRENT_PARAMS[param_name]
        cls.CURRENT_PARAMS[param_name] = new_value

        # 记录变更
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO model_params_history
            (model_version, param_name, old_value, new_value, change_reason, changed_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('v1.0', param_name, old_value, new_value, reason, datetime.now().isoformat()))
        conn.commit()
        conn.close()

        logger.info(f"参数更新: {param_name} {old_value:.3f} -> {new_value:.3f} ({reason})")


class ModelOptimizer:
    """模型优化器 - 基于复盘数据自动调参"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.params = ModelParameters()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def analyze_errors(self, days: int = 30) -> Dict:
        """
        分析预测误差，找出系统性问题

        Returns:
            误差分析结果和优化建议
        """
        conn = self._get_conn()
        c = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        analysis = {
            'period': f'{days}天',
            'total_predictions': 0,
            'errors': {},
            'patterns': [],
            'suggestions': []
        }

        # 1. 总体误差统计
        c.execute('''
            SELECT
                COUNT(*) as total,
                SUM(result_correct) as hits,
                AVG(brier_score) as avg_brier,
                AVG(ABS(goal_error)) as avg_goal_error
            FROM prediction_review r
            JOIN prediction_records p ON r.prediction_id = p.id
            WHERE p.match_date >= ?
        ''', (since,))

        row = c.fetchone()
        analysis['total_predictions'] = row['total']
        analysis['overall_accuracy'] = row['hits'] / row['total'] * 100 if row['total'] > 0 else 0
        analysis['avg_brier'] = row['avg_brier']
        analysis['avg_goal_error'] = row['avg_goal_error']

        # 2. 按误差类型分析
        # 2.1 平局漏判分析
        c.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN p.pred_result != 'draw' AND r.actual_result = 'draw' THEN 1 ELSE 0 END) as missed_draws,
                SUM(CASE WHEN p.pred_result = 'draw' AND r.actual_result != 'draw' THEN 1 ELSE 0 END) as false_draws
            FROM prediction_review r
            JOIN prediction_records p ON r.prediction_id = p.id
            WHERE p.match_date >= ?
        ''', (since,))

        row = c.fetchone()
        missed_draw_rate = row['missed_draws'] / row['total'] if row['total'] > 0 else 0
        false_draw_rate = row['false_draws'] / row['total'] if row['total'] > 0 else 0

        analysis['errors']['draw'] = {
            'missed_rate': missed_draw_rate,
            'false_rate': false_draw_rate,
            'net_error': missed_draw_rate - false_draw_rate
        }

        if missed_draw_rate > 0.25:
            analysis['suggestions'].append({
                'param': 'friendly_draw_boost',
                'direction': 'increase',
                'magnitude': min(0.05, missed_draw_rate - 0.20),
                'reason': f"平局漏判率{missed_draw_rate*100:.1f}%过高"
            })

        # 2.2 主胜预测偏差
        c.execute('''
            SELECT
                AVG(r.prob_error_home) as avg_home_error,
                AVG(CASE WHEN p.fifa_rank_diff < -30 THEN r.prob_error_home ELSE NULL END) as strong_home_error,
                AVG(CASE WHEN p.is_friendly = 1 THEN r.prob_error_home ELSE NULL END) as friendly_home_error
            FROM prediction_review r
            JOIN prediction_records p ON r.prediction_id = p.id
            WHERE p.match_date >= ?
        ''', (since,))

        row = c.fetchone()
        analysis['errors']['home_prob'] = {
            'avg_error': row['avg_home_error'],
            'strong_home_error': row['strong_home_error'],
            'friendly_home_error': row['friendly_home_error']
        }

        if row['strong_home_error'] and abs(row['strong_home_error']) > 0.10:
            direction = 'decrease' if row['strong_home_error'] > 0 else 'increase'
            analysis['suggestions'].append({
                'param': 'fifa_rank_weight',
                'direction': direction,
                'magnitude': 0.05,
                'reason': f"强队主胜概率误差{row['strong_home_error']*100:.1f}%"
            })

        # 3. 按场景分析
        # 3.1 友谊赛准确率
        c.execute('''
            SELECT
                COUNT(*) as total,
                SUM(result_correct) as hits,
                AVG(brier_score) as avg_brier
            FROM prediction_review r
            JOIN prediction_records p ON r.prediction_id = p.id
            WHERE p.is_friendly = 1 AND p.match_date >= ?
        ''', (since,))

        row = c.fetchone()
        if row['total'] >= 5:
            friendly_acc = row['hits'] / row['total'] * 100
            analysis['patterns'].append({
                'type': 'friendly',
                'total': row['total'],
                'accuracy': friendly_acc,
                'avg_brier': row['avg_brier']
            })

            if friendly_acc < 45:
                analysis['suggestions'].append({
                    'param': 'friendly_draw_boost',
                    'direction': 'increase',
                    'magnitude': 0.05,
                    'reason': f"友谊赛准确率仅{friendly_acc:.1f}%"
                })

        # 3.2 排名差距场景
        c.execute('''
            SELECT
                CASE
                    WHEN fifa_rank_diff < -50 THEN 'home_strong'
                    WHEN fifa_rank_diff > 50 THEN 'away_strong'
                    WHEN ABS(fifa_rank_diff) <= 15 THEN 'even'
                    ELSE 'moderate'
                END as category,
                COUNT(*) as total,
                SUM(result_correct) as hits,
                AVG(brier_score) as avg_brier
            FROM prediction_review r
            JOIN prediction_records p ON r.prediction_id = p.id
            WHERE p.match_date >= ?
            GROUP BY category
        ''', (since,))

        for row in c.fetchall():
            analysis['patterns'].append({
                'type': f"rank_{row['category']}",
                'total': row['total'],
                'accuracy': row['hits'] / row['total'] * 100 if row['total'] > 0 else 0,
                'avg_brier': row['avg_brier']
            })

        # 3.3 状态差距场景
        c.execute('''
            SELECT
                CASE
                    WHEN form_diff > 30 THEN 'home_hot'
                    WHEN form_diff < -30 THEN 'away_hot'
                    WHEN ABS(form_diff) <= 10 THEN 'similar_form'
                    ELSE 'moderate_form'
                END as category,
                COUNT(*) as total,
                SUM(result_correct) as hits,
                AVG(goal_error) as avg_goal_error
            FROM prediction_review r
            JOIN prediction_records p ON r.prediction_id = p.id
            WHERE p.match_date >= ?
            GROUP BY category
        ''', (since,))

        for row in c.fetchall():
            analysis['patterns'].append({
                'type': f"form_{row['category']}",
                'total': row['total'],
                'accuracy': row['hits'] / row['total'] * 100 if row['total'] > 0 else 0,
                'goal_error': row['avg_goal_error']
            })

        conn.close()
        return analysis

    def auto_optimize(self, min_samples: int = 10, auto_apply: bool = False) -> List[Dict]:
        """
        自动优化模型参数

        Args:
            min_samples: 最小样本数
            auto_apply: 是否自动应用优化

        Returns:
            优化建议列表
        """
        analysis = self.analyze_errors(days=30)

        if analysis['total_predictions'] < min_samples:
            logger.warning(f"样本数不足({analysis['total_predictions']}<{min_samples})，跳过优化")
            return []

        optimizations = []

        # 1. 平局概率优化
        draw_error = analysis['errors'].get('draw', {})
        if draw_error.get('missed_rate', 0) > 0.25:
            current = ModelParameters.CURRENT_PARAMS['friendly_draw_boost']
            new_value = min(0.30, current + 0.03)
            optimizations.append({
                'param': 'friendly_draw_boost',
                'current': current,
                'suggested': new_value,
                'reason': f"平局漏判率{draw_error['missed_rate']*100:.1f}%",
                'priority': 'high'
            })

        # 2. 排名权重优化
        home_error = analysis['errors'].get('home_prob', {})
        if home_error.get('strong_home_error') and abs(home_error['strong_home_error']) > 0.12:
            current = ModelParameters.CURRENT_PARAMS['fifa_rank_weight']
            if home_error['strong_home_error'] > 0:
                # 高估了主胜，降低权重
                new_value = max(0.10, current - 0.05)
            else:
                # 低估了主胜，提高权重
                new_value = min(0.50, current + 0.05)
            optimizations.append({
                'param': 'fifa_rank_weight',
                'current': current,
                'suggested': new_value,
                'reason': f"强队主胜误差{home_error['strong_home_error']*100:.1f}%",
                'priority': 'medium'
            })

        # 3. 进球预测优化
        if analysis.get('avg_goal_error', 0) > 0.8:
            current = ModelParameters.CURRENT_PARAMS['form_goals_impact']
            new_value = min(0.50, current + 0.05)
            optimizations.append({
                'param': 'form_goals_impact',
                'current': current,
                'suggested': new_value,
                'reason': f"平均进球误差{analysis['avg_goal_error']:.1f}球",
                'priority': 'low'
            })

        # 4. 场景特定优化
        for pattern in analysis.get('patterns', []):
            if pattern['total'] < 5:
                continue

            if pattern['type'] == 'friendly' and pattern['accuracy'] < 45:
                current = ModelParameters.CURRENT_PARAMS['friendly_draw_boost']
                new_value = min(0.30, current + 0.03)
                optimizations.append({
                    'param': 'friendly_draw_boost',
                    'current': current,
                    'suggested': new_value,
                    'reason': f"友谊赛准确率{pattern['accuracy']:.1f}%",
                    'priority': 'high'
                })

            if 'rank_even' in pattern['type'] and pattern['accuracy'] < 40:
                current = ModelParameters.CURRENT_PARAMS['max_draw_prob']
                new_value = min(0.50, current + 0.05)
                optimizations.append({
                    'param': 'max_draw_prob',
                    'current': current,
                    'suggested': new_value,
                    'reason': f"排名接近场次准确率{pattern['accuracy']:.1f}%",
                    'priority': 'medium'
                })

        # 去重
        seen = set()
        unique_optimizations = []
        for opt in optimizations:
            key = opt['param']
            if key not in seen:
                seen.add(key)
                unique_optimizations.append(opt)

        # 自动应用
        if auto_apply:
            for opt in unique_optimizations:
                if opt['priority'] == 'high':
                    ModelParameters.update_param(
                        opt['param'],
                        opt['suggested'],
                        opt['reason']
                    )

        return unique_optimizations

    def backtest_params(self, params: Dict, days: int = 30) -> Dict:
        """
        回测参数效果

        Args:
            params: 要测试的参数
            days: 回测天数

        Returns:
            回测结果
        """
        # 这里应该用历史数据重新预测，计算准确率
        # 简化版本：对比当前参数和新参数在已有预测上的表现

        conn = self._get_conn()
        c = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # 获取历史预测和结果
        c.execute('''
            SELECT
                p.*,
                r.actual_result,
                r.actual_home_score,
                r.actual_away_score,
                r.brier_score
            FROM prediction_records p
            JOIN prediction_review r ON p.match_id = r.match_id
            WHERE p.match_date >= ?
        ''', (since,))

        records = [dict(row) for row in c.fetchall()]
        conn.close()

        if not records:
            return {'error': '无历史数据'}

        # 计算理论改进
        improvement = {
            'total': len(records),
            'current_brier': np.mean([r['brier_score'] for r in records if r['brier_score']]),
            'simulated_improvement': 0
        }

        # 模拟新参数效果
        # 这里需要重新计算每场预测，简化处理
        simulated_correct = 0
        for r in records:
            # 模拟：如果平局概率提升，检查是否原本漏判了平局
            if r['actual_result'] == 'draw' and r['pred_result'] != 'draw':
                if params.get('friendly_draw_boost', 0) > ModelParameters.CURRENT_PARAMS['friendly_draw_boost']:
                    if r['is_friendly']:
                        simulated_correct += 1
            elif r['result_correct']:
                simulated_correct += 1

        improvement['simulated_accuracy'] = simulated_correct / len(records) * 100
        improvement['current_accuracy'] = sum(r['result_correct'] for r in records) / len(records) * 100

        return improvement


class PredictionModel:
    """预测模型 - 使用可优化参数"""

    def __init__(self):
        self.params = ModelParameters.get_params()

    def predict(self, match_data: Dict) -> Dict:
        """
        预测比赛结果

        Args:
            match_data: 比赛数据

        Returns:
            预测结果
        """
        # 获取参数
        fifa_weight = self.params['fifa_rank_weight']
        elo_weight = self.params['elo_weight']
        form_weight = self.params['form_weight']
        h2h_weight = self.params['h2h_weight']
        home_weight = self.params['home_advantage_weight']

        # 计算各因素得分
        scores = {'home': 0, 'draw': 0, 'away': 0}

        # 1. FIFA排名
        fifa_diff = match_data.get('fifa_rank_diff', 0)
        if fifa_diff:
            # 排名差越大，高排名队越有优势
            fifa_score = -fifa_diff / 100  # 负值表示主队排名高
            scores['home'] += fifa_score * fifa_weight
            scores['away'] -= fifa_score * fifa_weight

        # 2. Elo评分
        elo_diff = match_data.get('elo_diff', 0)
        if elo_diff:
            elo_score = elo_diff / 400
            scores['home'] += elo_score * elo_weight

        # 3. 近期状态
        form_diff = match_data.get('form_diff', 0)
        if form_diff:
            form_score = form_diff / 100
            scores['home'] += form_score * form_weight

        # 4. H2H
        h2h_total = match_data.get('h2h_total', 0)
        if h2h_total > 0:
            h2h_home_rate = match_data.get('h2h_home_wins', 0) / h2h_total
            h2h_away_rate = match_data.get('h2h_away_wins', 0) / h2h_total
            scores['home'] += (h2h_home_rate - 0.33) * h2h_weight
            scores['away'] += (h2h_away_rate - 0.33) * h2h_weight

        # 5. 主场优势
        if match_data.get('home_advantage', 1):
            scores['home'] += home_weight

        # 转换为概率
        total_score = abs(scores['home']) + abs(scores['draw']) + abs(scores['away']) + 0.01

        # 基础概率
        base_home = 0.40
        base_draw = 0.28
        base_away = 0.32

        # 根据得分调整
        home_prob = base_home + scores['home'] / total_score * 0.3
        away_prob = base_away + scores['away'] / total_score * 0.3
        draw_prob = base_draw + scores['draw'] / total_score * 0.1

        # 特殊场景调整
        if match_data.get('is_friendly'):
            draw_prob += self.params['friendly_draw_boost']
            # 调整后重新归一化

        if match_data.get('motivation_away') == 'low':
            draw_prob += self.params['low_motivation_draw_boost']

        # 归一化
        total = home_prob + draw_prob + away_prob
        home_prob /= total
        draw_prob /= total
        away_prob /= total

        # 限制平局概率
        draw_prob = min(self.params['max_draw_prob'], draw_prob)
        home_prob = max(0.10, min(0.80, home_prob))
        away_prob = max(0.10, min(0.80, away_prob))

        # 重新归一化
        total = home_prob + draw_prob + away_prob
        home_prob /= total
        draw_prob /= total
        away_prob /= total

        # 确定预测结果
        if home_prob > away_prob and home_prob > draw_prob:
            result = 'home'
        elif away_prob > home_prob and away_prob > draw_prob:
            result = 'away'
        else:
            result = 'draw'

        # 预测进球
        base_goals = self.params['base_goals']
        form_impact = self.params['form_goals_impact']

        form_avg = (match_data.get('form_home_rating', 50) + match_data.get('form_away_rating', 50)) / 2
        goal_adjust = (form_avg - 50) / 100 * form_impact

        if match_data.get('is_friendly'):
            goal_adjust -= self.params['friendly_goals_reduction']

        total_goals = max(0.5, base_goals + goal_adjust)

        return {
            'home_prob': round(home_prob * 100, 1),
            'draw_prob': round(draw_prob * 100, 1),
            'away_prob': round(away_prob * 100, 1),
            'result': result,
            'total_goals': round(total_goals, 1),
            'confidence': round(max(home_prob, draw_prob, away_prob) * 100, 1)
        }

    def reload_params(self):
        """重新加载参数"""
        self.params = ModelParameters.get_params()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='模型优化引擎')
    parser.add_argument('--analyze', action='store_true', help='分析误差')
    parser.add_argument('--optimize', action='store_true', help='自动优化')
    parser.add_argument('--backtest', action='store_true', help='回测参数')
    parser.add_argument('--params', action='store_true', help='查看当前参数')
    parser.add_argument('--apply', action='store_true', help='自动应用优化')

    args = parser.parse_args()

    optimizer = ModelOptimizer()

    if args.analyze:
        analysis = optimizer.analyze_errors(days=30)
        print(json.dumps(analysis, ensure_ascii=False, indent=2))

    if args.optimize:
        suggestions = optimizer.auto_optimize(auto_apply=args.apply)
        print("\n优化建议:")
        for s in suggestions:
            print(f"  {s['param']}: {s['current']:.3f} -> {s['suggested']:.3f}")
            print(f"    原因: {s['reason']}")
            print(f"    优先级: {s['priority']}")

    if args.backtest:
        new_params = ModelParameters.CURRENT_PARAMS.copy()
        new_params['friendly_draw_boost'] = 0.20
        result = optimizer.backtest_params(new_params)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.params:
        print("\n当前模型参数:")
        for k, v in ModelParameters.CURRENT_PARAMS.items():
            print(f"  {k}: {v}")

    if not any([args.analyze, args.optimize, args.backtest, args.params]):
        print("模型优化引擎")
        print("用法:")
        print("  python model_optimizer.py --analyze        # 分析误差")
        print("  python model_optimizer.py --optimize       # 优化建议")
        print("  python model_optimizer.py --optimize --apply  # 自动应用")
        print("  python model_optimizer.py --backtest       # 回测参数")
        print("  python model_optimizer.py --params         # 查看参数")