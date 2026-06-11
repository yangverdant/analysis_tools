"""
结果验证服务 - 预测结果验证

功能:
1. 获取开奖结果
2. 对比预测与实际
3. 计算准确率指标
4. 写入验证记录
5. 计算Brier分数
"""

from typing import Dict, List, Optional
import sqlite3
import json
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)


class ValidationService:
    """
    结果验证服务

    闭环学习的关键环节:
    预测 → 验证 → 优化 → 改进预测
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def validate_match(self, lottery_match_id: str) -> Dict:
        """
        验证单场比赛预测

        流程:
        1. 获取开奖结果
        2. 获取预测记录
        3. 对比预测与实际
        4. 计算准确率指标
        5. 写入 validation 表

        Args:
            lottery_match_id: 体彩比赛ID

        Returns:
            验证结果字典
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 1. 获取比赛信息
            cursor.execute("""
                SELECT lm.*, lr.home_goals_ft, lr.away_goals_ft,
                       lr.spf_result, lr.bf_result, lr.bqc_result
                FROM lottery_matches lm
                LEFT JOIN lottery_results lr ON lm.lottery_match_id = lr.lottery_match_id
                WHERE lm.lottery_match_id = ?
            """, (lottery_match_id,))

            match = cursor.fetchone()
            if not match:
                return {'success': False, 'error': 'Match not found'}

            # 检查是否有开奖结果
            if match['home_goals_ft'] is None:
                return {'success': False, 'error': 'No result available yet'}

            # 2. 获取预测记录
            cursor.execute("""
                SELECT * FROM lottery_predictions
                WHERE lottery_match_id = ?
            """, (lottery_match_id,))

            predictions = [dict(row) for row in cursor.fetchall()]

            if not predictions:
                return {'success': False, 'error': 'No predictions found'}

            # 3. 验证每个预测
            validation_results = []

            for pred in predictions:
                validation = self._validate_single_prediction(
                    pred, dict(match)
                )
                validation_results.append(validation)

                # 4. 写入验证记录
                self._save_validation_result(cursor, validation)

            conn.commit()

            # 5. 计算整体准确率
            accuracy_summary = self._calculate_accuracy_summary(validation_results)

            return {
                'success': True,
                'lottery_match_id': lottery_match_id,
                'match_result': {
                    'home_goals': match['home_goals_ft'],
                    'away_goals': match['away_goals_ft'],
                    'spf_result': match['spf_result'],
                    'bf_result': match['bf_result'],
                    'bqc_result': match['bqc_result']
                },
                'validations': validation_results,
                'accuracy_summary': accuracy_summary
            }

        except Exception as e:
            logger.error(f"Validation failed for {lottery_match_id}: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def _validate_single_prediction(
        self,
        prediction: Dict,
        match_result: Dict
    ) -> Dict:
        """
        验证单个预测

        Args:
            prediction: 预测记录
            match_result: 比赛结果

        Returns:
            验证结果字典
        """
        play_type = prediction['play_type']
        predictions_data = json.loads(prediction['predictions']) if prediction['predictions'] else {}

        # 根据玩法类型验证
        if play_type == 'spf':
            return self._validate_spf(prediction, match_result, predictions_data)
        elif play_type == 'bf':
            return self._validate_bf(prediction, match_result, predictions_data)
        elif play_type == 'bqc':
            return self._validate_bqc(prediction, match_result, predictions_data)
        elif play_type == 'rqspf':
            return self._validate_rqspf(prediction, match_result, predictions_data)
        else:
            return {
                'prediction_id': prediction['prediction_id'],
                'play_type': play_type,
                'error': f'Unknown play type: {play_type}'
            }

    def _validate_spf(
        self,
        prediction: Dict,
        match_result: Dict,
        predictions_data: Dict
    ) -> Dict:
        """验证胜平负预测"""
        # 实际结果
        actual_result = match_result.get('spf_result')
        if not actual_result:
            # 计算胜平负结果
            home_goals = match_result['home_goals_ft']
            away_goals = match_result['away_goals_ft']
            if home_goals > away_goals:
                actual_result = '3'
            elif home_goals == away_goals:
                actual_result = '1'
            else:
                actual_result = '0'

        # 预测结果
        predicted_result = predictions_data.get('result')

        # 预测概率
        prob_map = {
            '3': predictions_data.get('home_win', 0),
            '1': predictions_data.get('draw', 0),
            '0': predictions_data.get('away_win', 0)
        }
        predicted_prob = prob_map.get(actual_result, 0)

        # 计算正确性
        is_correct = 1 if predicted_result == actual_result else 0

        # 计算Brier分数
        brier_score = self.calculate_brier_score(predicted_prob, is_correct == 1)

        return {
            'prediction_id': prediction['prediction_id'],
            'play_type': 'spf',
            'predicted_result': predicted_result,
            'actual_result': actual_result,
            'predicted_prob': predicted_prob,
            'is_correct': is_correct,
            'brier_score': brier_score
        }

    def _validate_bf(
        self,
        prediction: Dict,
        match_result: Dict,
        predictions_data: Dict
    ) -> Dict:
        """验证比分预测"""
        # 实际比分
        home_goals = match_result['home_goals_ft']
        away_goals = match_result['away_goals_ft']
        actual_score = f"{home_goals}{away_goals}"

        # 预测比分
        predicted_score = predictions_data.get('result')

        # 比分概率
        predicted_prob = predictions_data.get('scores', {}).get(actual_score, 0)

        # 计算正确性
        is_correct = 1 if predicted_score == actual_score else 0

        # Brier分数
        brier_score = self.calculate_brier_score(predicted_prob, is_correct == 1)

        return {
            'prediction_id': prediction['prediction_id'],
            'play_type': 'bf',
            'predicted_result': predicted_score,
            'actual_result': actual_score,
            'predicted_prob': predicted_prob,
            'is_correct': is_correct,
            'brier_score': brier_score
        }

    def _validate_bqc(
        self,
        prediction: Dict,
        match_result: Dict,
        predictions_data: Dict
    ) -> Dict:
        """验证半全场预测"""
        actual_result = match_result.get('bqc_result')

        # 如果没有半全场结果，尝试从数据中计算
        if not actual_result:
            # 需要半场数据
            home_goals_ht = match_result.get('home_goals_ht', 0)
            away_goals_ht = match_result.get('away_goals_ht', 0)
            home_goals_ft = match_result['home_goals_ft']
            away_goals_ft = match_result['away_goals_ft']

            # 半场结果
            if home_goals_ht > away_goals_ht:
                ht_result = '3'
            elif home_goals_ht == away_goals_ht:
                ht_result = '1'
            else:
                ht_result = '0'

            # 全场结果
            if home_goals_ft > away_goals_ft:
                ft_result = '3'
            elif home_goals_ft == away_goals_ft:
                ft_result = '1'
            else:
                ft_result = '0'

            actual_result = ht_result + ft_result

        predicted_result = predictions_data.get('result')
        predicted_prob = predictions_data.get('probabilities', {}).get(actual_result, 0)

        is_correct = 1 if predicted_result == actual_result else 0
        brier_score = self.calculate_brier_score(predicted_prob, is_correct == 1)

        return {
            'prediction_id': prediction['prediction_id'],
            'play_type': 'bqc',
            'predicted_result': predicted_result,
            'actual_result': actual_result,
            'predicted_prob': predicted_prob,
            'is_correct': is_correct,
            'brier_score': brier_score
        }

    def _validate_rqspf(
        self,
        prediction: Dict,
        match_result: Dict,
        predictions_data: Dict
    ) -> Dict:
        """验证让球胜平负预测"""
        handicap_line = prediction.get('handicap_line', 0)
        home_goals = match_result['home_goals_ft']
        away_goals = match_result['away_goals_ft']

        # 计算让球后结果
        adjusted_home = home_goals - handicap_line

        if adjusted_home > away_goals:
            actual_result = '3'
        elif adjusted_home == away_goals:
            actual_result = '1'
        else:
            actual_result = '0'

        predicted_result = predictions_data.get('result')
        prob_map = {
            '3': predictions_data.get('home_win', 0),
            '1': predictions_data.get('draw', 0),
            '0': predictions_data.get('away_win', 0)
        }
        predicted_prob = prob_map.get(actual_result, 0)

        is_correct = 1 if predicted_result == actual_result else 0
        brier_score = self.calculate_brier_score(predicted_prob, is_correct == 1)

        return {
            'prediction_id': prediction['prediction_id'],
            'play_type': 'rqspf',
            'handicap_line': handicap_line,
            'predicted_result': predicted_result,
            'actual_result': actual_result,
            'predicted_prob': predicted_prob,
            'is_correct': is_correct,
            'brier_score': brier_score
        }

    def calculate_brier_score(
        self,
        predicted_prob: float,
        actual_outcome: bool
    ) -> float:
        """
        计算Brier分数

        Brier分数 = (预测概率 - 实际结果)^2

        越小越好:
        - 0 = 完美预测 (预测概率=1且实际发生)
        - 1 = 最差预测 (预测概率=1但实际未发生)
        """
        actual = 1.0 if actual_outcome else 0.0
        return round((predicted_prob - actual) ** 2, 4)

    def _save_validation_result(self, cursor, validation: Dict):
        """保存验证结果"""
        cursor.execute("""
            INSERT INTO lottery_validation
            (prediction_id, lottery_match_id, play_type, predicted_result,
             actual_result, is_correct, predicted_prob, brier_score, validated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            validation['prediction_id'],
            validation.get('lottery_match_id'),
            validation['play_type'],
            validation['predicted_result'],
            validation['actual_result'],
            validation['is_correct'],
            validation['predicted_prob'],
            validation['brier_score'],
            datetime.now().isoformat()
        ))

    def _calculate_accuracy_summary(self, validations: List[Dict]) -> Dict:
        """计算准确率统计"""
        total = len(validations)
        correct = sum(1 for v in validations if v.get('is_correct'))
        avg_brier = sum(v.get('brier_score', 0) for v in validations) / total if total > 0 else 0

        return {
            'total_predictions': total,
            'correct_predictions': correct,
            'accuracy': round(correct / total * 100, 2) if total > 0 else 0,
            'avg_brier_score': round(avg_brier, 4)
        }

    def validate_date_range(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        批量验证日期范围内的比赛

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            批量验证结果
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 获取日期范围内的已完场比赛
            cursor.execute("""
                SELECT lottery_match_id FROM lottery_matches
                WHERE match_date >= ? AND match_date <= ?
                AND lottery_match_id IN (
                    SELECT lottery_match_id FROM lottery_results
                )
            """, (str(start_date), str(end_date)))

            match_ids = [row[0] for row in cursor.fetchall()]

        finally:
            conn.close()

        # 逐个验证
        results = []
        for match_id in match_ids:
            result = self.validate_match(match_id)
            results.append(result)

        return {
            'date_range': f"{start_date} to {end_date}",
            'total_matches': len(match_ids),
            'results': results
        }

    def get_accuracy_stats(
        self,
        days: int = 30,
        play_type: str = None
    ) -> Dict:
        """
        获取准确率统计

        Args:
            days: 统计天数
            play_type: 玩法筛选

        Returns:
            准确率统计
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            query = """
                SELECT
                    play_type,
                    COUNT(*) as total,
                    SUM(is_correct) as correct,
                    AVG(brier_score) as avg_brier
                FROM lottery_validation
                WHERE validated_at >= date('now', ?)
            """
            params = [f'-{days} days']

            if play_type:
                query += " AND play_type = ?"
                params.append(play_type)

            query += " GROUP BY play_type"

            cursor.execute(query, params)

            stats = []
            for row in cursor.fetchall():
                accuracy = row['correct'] / row['total'] if row['total'] > 0 else 0
                stats.append({
                    'play_type': row['play_type'],
                    'total': row['total'],
                    'correct': row['correct'],
                    'accuracy': round(accuracy * 100, 2),
                    'avg_brier_score': round(row['avg_brier'], 4) if row['avg_brier'] else None
                })

            return {
                'days': days,
                'stats': stats
            }

        finally:
            conn.close()
