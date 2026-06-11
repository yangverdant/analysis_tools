"""
权重优化器 - 根据验证结果优化模型权重

功能:
1. 分析各特征提取器的准确率
2. 计算权重调整幅度
3. 生成新权重配置
4. 写入权重调整历史
5. 支持多种优化策略
"""

from typing import Dict, List, Optional, Tuple
import sqlite3
import json
import logging
from datetime import datetime, date, timedelta
import math

logger = logging.getLogger(__name__)


class WeightOptimizer:
    """
    权重优化器

    闭环学习的关键环节:
    验证结果 → 分析表现 → 调整权重 → 改进预测

    优化策略:
    1. 表现好的提取器增加权重
    2. 表现差的提取器减少权重
    3. 考虑样本量避免过拟合
    4. 设置权重上下限
    """

    # 默认权重配置
    DEFAULT_WEIGHTS = {
        'spf': {
            'poisson': 0.30,
            'elo': 0.25,
            'h2h': 0.20,
            'form': 0.15,
            'home_advantage': 0.10
        },
        'bf': {
            'poisson': 0.40,
            'league_pattern': 0.30,
            'h2h': 0.30
        },
        'bqc': {
            'ht_distribution': 0.35,
            'transition': 0.35,
            'form': 0.30
        },
        'rqspf': {
            'adjusted_spf': 0.50,
            'handicap_analysis': 0.50
        }
    }

    # 权重范围限制
    WEIGHT_MIN = 0.05
    WEIGHT_MAX = 0.50

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.current_weights = self._load_current_weights()

    def optimize_weights(
        self,
        days: int = 30,
        min_samples: int = 10
    ) -> Dict:
        """
        根据历史验证结果优化权重

        Args:
            days: 统计天数
            min_samples: 最小样本量

        Returns:
            优化结果
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 1. 获取各玩法的验证结果
            validation_stats = self._get_validation_stats(cursor, days)

            # 2. 获取各提取器的表现数据
            extractor_performance = self._get_extractor_performance(cursor, days)

            # 3. 计算权重调整
            weight_adjustments = self._calculate_weight_adjustments(
                extractor_performance, min_samples
            )

            # 4. 生成新权重
            new_weights = self._apply_adjustments(weight_adjustments)

            # 5. 保存权重调整历史
            self._save_weight_history(cursor, weight_adjustments, new_weights)

            conn.commit()

            return {
                'success': True,
                'validation_stats': validation_stats,
                'extractor_performance': extractor_performance,
                'weight_adjustments': weight_adjustments,
                'new_weights': new_weights,
                'previous_weights': self.current_weights,
                'optimized_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Weight optimization failed: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def _load_current_weights(self) -> Dict:
        """加载当前权重配置"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT play_type, weights FROM weight_adjustment_history
                ORDER BY created_at DESC LIMIT 1
            """)

            row = cursor.fetchone()
            if row:
                return json.loads(row[1])

        except:
            pass
        finally:
            conn.close()

        return self.DEFAULT_WEIGHTS.copy()

    def _get_validation_stats(self, cursor, days: int) -> Dict:
        """获取验证统计"""
        cursor.execute("""
            SELECT
                play_type,
                COUNT(*) as total,
                SUM(is_correct) as correct,
                AVG(brier_score) as avg_brier
            FROM lottery_validation
            WHERE validated_at >= date('now', ?)
            GROUP BY play_type
        """, (f'-{days} days',))

        stats = {}
        for row in cursor.fetchall():
            accuracy = row[1] / row[2] if row[2] > 0 else 0
            stats[row[0]] = {
                'total': row[1],
                'correct': row[2],
                'accuracy': round(accuracy, 4),
                'avg_brier': round(row[3], 4) if row[3] else None
            }

        return stats

    def _get_extractor_performance(self, cursor, days: int) -> Dict:
        """
        获取各提取器的表现

        由于我们无法直接追踪每个提取器的贡献，
        这里使用间接方法:
        1. 分析预测的置信度与准确率关系
        2. 分析不同时期的准确率变化
        """
        performance = {}

        # 获取按置信度分组的准确率
        cursor.execute("""
            SELECT
                p.confidence_level,
                COUNT(*) as total,
                SUM(v.is_correct) as correct
            FROM lottery_predictions p
            JOIN lottery_validation v ON p.prediction_id = v.prediction_id
            WHERE v.validated_at >= date('now', ?)
            GROUP BY p.confidence_level
        """, (f'-{days} days',))

        for row in cursor.fetchall():
            performance[row[0]] = {
                'total': row[1],
                'correct': row[2],
                'accuracy': row[2] / row[1] if row[1] > 0 else 0
            }

        return performance

    def _calculate_weight_adjustments(
        self,
        performance: Dict,
        min_samples: int
    ) -> Dict:
        """
        计算权重调整幅度

        策略:
        1. 根据准确率调整权重
        2. 考虑样本量进行平滑
        3. 设置调整幅度上下限
        """
        adjustments = {}

        for play_type, weights in self.current_weights.items():
            adjustments[play_type] = {}

            for extractor, current_weight in weights.items():
                # 获取该提取器的表现
                perf = performance.get(extractor, {})

                if perf.get('total', 0) < min_samples:
                    # 样本不足，不调整
                    adjustments[play_type][extractor] = {
                        'current': current_weight,
                        'adjustment': 0,
                        'reason': 'insufficient_samples'
                    }
                    continue

                # 计算调整因子
                accuracy = perf.get('accuracy', 0.33)

                # 调整因子: 准确率高于期望则增加权重
                # 期望准确率: SPF约33%, BF约10%, BQC约11%
                expected_accuracy = self._get_expected_accuracy(play_type)

                if accuracy > expected_accuracy:
                    # 表现好，增加权重
                    adjustment_factor = min(0.1, (accuracy - expected_accuracy) * 0.5)
                else:
                    # 表现差，减少权重
                    adjustment_factor = max(-0.1, (accuracy - expected_accuracy) * 0.5)

                new_weight = current_weight + adjustment_factor

                # 限制范围
                new_weight = max(self.WEIGHT_MIN, min(self.WEIGHT_MAX, new_weight))

                adjustments[play_type][extractor] = {
                    'current': current_weight,
                    'adjustment': round(new_weight - current_weight, 4),
                    'new_weight': round(new_weight, 4),
                    'accuracy': accuracy,
                    'reason': 'performance_based'
                }

        return adjustments

    def _get_expected_accuracy(self, play_type: str) -> float:
        """获取期望准确率"""
        expected = {
            'spf': 0.33,   # 3个选项，随机33%
            'bf': 0.10,    # 27个选项，随机约3.7%，但模型应该更好
            'bqc': 0.11,   # 9个选项，随机11%
            'rqspf': 0.33
        }
        return expected.get(play_type, 0.33)

    def _apply_adjustments(self, adjustments: Dict) -> Dict:
        """应用权重调整"""
        new_weights = {}

        for play_type, extractors in adjustments.items():
            # 提取新权重
            raw_weights = {
                ext: data.get('new_weight', data['current'])
                for ext, data in extractors.items()
            }

            # 归一化 (使权重和为1)
            total = sum(raw_weights.values())
            if total > 0:
                normalized = {k: round(v / total, 4) for k, v in raw_weights.items()}
            else:
                normalized = raw_weights

            new_weights[play_type] = normalized

        self.current_weights = new_weights
        return new_weights

    def _save_weight_history(
        self,
        cursor,
        adjustments: Dict,
        new_weights: Dict
    ):
        """保存权重调整历史"""
        cursor.execute("""
            INSERT INTO weight_adjustment_history
            (play_type, previous_weights, new_weights, adjustments, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            'all',
            json.dumps(self.current_weights),
            json.dumps(new_weights),
            json.dumps(adjustments),
            'automated_optimization',
            datetime.now().isoformat()
        ))

    def get_weight_history(self, limit: int = 10) -> List[Dict]:
        """获取权重调整历史"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM weight_adjustment_history
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_current_weights(self) -> Dict:
        """获取当前权重"""
        return self.current_weights

    def set_weights(self, weights: Dict, reason: str = 'manual') -> Dict:
        """
        手动设置权重

        Args:
            weights: 新权重配置
            reason: 设置原因

        Returns:
            设置结果
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            previous = self.current_weights.copy()
            self.current_weights = weights

            # 保存历史
            cursor.execute("""
                INSERT INTO weight_adjustment_history
                (play_type, previous_weights, new_weights, adjustments, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                'all',
                json.dumps(previous),
                json.dumps(weights),
                json.dumps({'manual': weights}),
                reason,
                datetime.now().isoformat()
            ))

            conn.commit()

            return {
                'success': True,
                'previous': previous,
                'new': weights
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def reset_to_default(self) -> Dict:
        """重置为默认权重"""
        return self.set_weights(self.DEFAULT_WEIGHTS.copy(), 'reset_to_default')
