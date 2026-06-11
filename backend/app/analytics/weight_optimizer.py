"""
权重优化器 — 闭环学习核心

根据历史预测的维度贡献分析，自动调整各子分析器的权重：
1. 对齐实际赛果的维度 → 增大权重
2. 偏离实际赛果的维度 → 减小权重
3. 生成新权重版本，保留历史版本可回滚
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional


class WeightOptimizer:
    """权重自动优化器"""

    DIMENSIONS = ['elo', 'poisson', 'h2h', 'form', 'home_away', 'motivation', 'news_factors']
    WEIGHT_KEYS = [f'{d}_weight' for d in DIMENSIONS]

    # 优化约束
    MIN_WEIGHT = 0.03    # 单维度最低权重
    MAX_WEIGHT = 0.50    # 单维度最高权重
    MIN_SAMPLES = 10     # 最少样本数才能优化
    LEARNING_RATE = 0.05 # 学习率（控制调整幅度）

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── 1. 计算维度准确率 ────────────────────────────────────

    def compute_dimension_accuracy(self, model_version: str = None, min_samples: int = None) -> Dict:
        """
        统计每个维度的方向准确率

        返回每个维度在历史预测中方向与实际赛果对齐的比例
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            min_s = min_samples or self.MIN_SAMPLES

            version_filter = ''
            params = []
            if model_version:
                version_filter = 'AND pl.model_version = ?'
                params.append(model_version)

            # 获取所有已验证预测的维度贡献
            cursor.execute(f'''
                SELECT pl.model_version, pr.dimension_contribution, pr.result_correct
                FROM prediction_results pr
                JOIN prediction_logs pl ON pr.log_id = pl.log_id
                WHERE pr.dimension_contribution IS NOT NULL
                {version_filter}
            ''', params)

            dimension_stats = {d: {'aligned': 0, 'total': 0} for d in self.DIMENSIONS}
            total_predictions = 0

            for row in cursor.fetchall():
                contrib = json.loads(row['dimension_contribution']) if row['dimension_contribution'] else {}
                total_predictions += 1

                for dim in self.DIMENSIONS:
                    if dim in contrib and contrib[dim].get('direction'):
                        dimension_stats[dim]['total'] += 1
                        if contrib[dim].get('aligned'):
                            dimension_stats[dim]['aligned'] += 1

            # 计算准确率
            result = {
                'total_predictions': total_predictions,
                'dimensions': {}
            }

            for dim in self.DIMENSIONS:
                total = dimension_stats[dim]['total']
                aligned = dimension_stats[dim]['aligned']
                result['dimensions'][dim] = {
                    'total': total,
                    'aligned': aligned,
                    'accuracy': round(aligned / total * 100, 2) if total > 0 else None,
                    'sufficient_data': total >= min_s
                }

            return result
        finally:
            conn.close()

    # ── 2. 执行权重优化 ──────────────────────────────────────

    def optimize_weights(self, force: bool = False) -> Dict:
        """
        基于维度准确率优化权重

        核心逻辑：
        - 准确率 > 50% 的维度 → 按比例增大权重
        - 准确率 < 50% 的维度 → 按比例减小权重
        - 准确率 = 50% 的维度 → 不变
        - 归一化保证权重和为1
        """
        conn = self.get_connection()
        try:
            # 获取当前权重
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM model_weights WHERE is_active = 1 LIMIT 1')
            current = cursor.fetchone()
            if not current:
                return {'success': False, 'reason': '无激活权重'}

            current_weights = {k: current[k] for k in self.WEIGHT_KEYS}

            # 计算维度准确率
            dim_accuracy = self.compute_dimension_accuracy()

            if dim_accuracy['total_predictions'] < self.MIN_SAMPLES and not force:
                return {
                    'success': False,
                    'reason': f'样本不足（{dim_accuracy["total_predictions"]}/{self.MIN_SAMPLES}），使用 --force 强制优化'
                }

            # 计算调整
            new_weights = {}
            adjustments = {}

            for dim in self.DIMENSIONS:
                key = f'{dim}_weight'
                current_val = current_weights[key]
                dim_info = dim_accuracy['dimensions'][dim]

                if dim_info['sufficient_data'] and dim_info['accuracy'] is not None:
                    # 准确率偏离50%的幅度决定调整方向和大小
                    accuracy = dim_info['accuracy'] / 100  # 转为0-1
                    deviation = accuracy - 0.5  # 正值=方向对，负值=方向错
                    adjustment = deviation * self.LEARNING_RATE

                    new_val = current_val + adjustment
                    new_val = max(self.MIN_WEIGHT, min(self.MAX_WEIGHT, new_val))

                    adjustments[dim] = {
                        'old': round(current_val, 4),
                        'new': round(new_val, 4),
                        'accuracy': dim_info['accuracy'],
                        'adjustment': round(adjustment, 4),
                        'direction': 'up' if adjustment > 0 else ('down' if adjustment < 0 else 'none')
                    }
                else:
                    # 数据不足，保持不变
                    new_val = current_val
                    adjustments[dim] = {
                        'old': round(current_val, 4),
                        'new': round(current_val, 4),
                        'accuracy': dim_info['accuracy'],
                        'adjustment': 0,
                        'direction': 'no_data'
                    }

                new_weights[key] = new_val

            # 归一化
            total = sum(new_weights.values())
            for key in new_weights:
                new_weights[key] = round(new_weights[key] / total, 4)

            # 生成新版本号
            last_version = current['version']
            new_version = self._next_version(last_version)

            # 计算当前准确率
            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    AVG(brier_score) as avg_brier,
                    SUM(result_correct) * 1.0 / COUNT(*) as accuracy
                FROM prediction_results pr
                JOIN prediction_logs pl ON pr.log_id = pl.log_id
                WHERE pl.model_version = ?
            ''', (last_version,))
            stats = cursor.fetchone()

            # 停用旧版本
            cursor.execute('UPDATE model_weights SET is_active = 0 WHERE version = ?', (last_version,))

            # 插入新版本
            cursor.execute('''
                INSERT INTO model_weights (
                    version, elo_weight, poisson_weight, h2h_weight, form_weight,
                    home_away_weight, motivation_weight, news_factors_weight,
                    sample_size, brier_score_avg, accuracy_rate, is_active
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,1)
            ''', (
                new_version,
                new_weights['elo_weight'], new_weights['poisson_weight'],
                new_weights['h2h_weight'], new_weights['form_weight'],
                new_weights['home_away_weight'], new_weights['motivation_weight'],
                new_weights['news_factors_weight'],
                stats['total'] or 0,
                round(stats['avg_brier'] or 0, 4),
                round((stats['accuracy'] or 0) * 100, 2)
            ))

            conn.commit()

            return {
                'success': True,
                'old_version': last_version,
                'new_version': new_version,
                'adjustments': adjustments,
                'new_weights': {k: new_weights[k] for k in self.WEIGHT_KEYS},
                'sample_size': stats['total'] or 0,
                'current_accuracy': round((stats['accuracy'] or 0) * 100, 2),
                'current_brier': round(stats['avg_brier'] or 0, 4)
            }
        finally:
            conn.close()

    # ── 3. 回滚权重版本 ──────────────────────────────────────

    def rollback_weights(self, target_version: str) -> Dict:
        """回滚到指定权重版本"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM model_weights WHERE version = ?', (target_version,))
            target = cursor.fetchone()
            if not target:
                return {'success': False, 'reason': f'版本 {target_version} 不存在'}

            # 停用当前
            cursor.execute('UPDATE model_weights SET is_active = 0 WHERE is_active = 1')
            # 激活目标
            cursor.execute('UPDATE model_weights SET is_active = 1 WHERE version = ?', (target_version,))

            conn.commit()

            return {
                'success': True,
                'activated_version': target_version,
                'weights': {k: target[k] for k in self.WEIGHT_KEYS}
            }
        finally:
            conn.close()

    # ── 4. 辅助函数 ──────────────────────────────────────────

    @staticmethod
    def _next_version(current: str) -> str:
        """生成下一个版本号 v1 → v2, v10 → v11"""
        try:
            num = int(current.replace('v', ''))
            return f'v{num + 1}'
        except ValueError:
            return f'{current}_opt1'

    def get_optimization_history(self) -> List[Dict]:
        """获取权重优化历史"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT version, elo_weight, poisson_weight, h2h_weight, form_weight,
                       home_away_weight, motivation_weight, news_factors_weight,
                       sample_size, brier_score_avg, accuracy_rate, is_active, created_at
                FROM model_weights
                ORDER BY created_at ASC
            ''')
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
