"""
比赛预测复盘系统
自动跟踪预测结果，量化评估模型准确性，持续优化参数
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'football_v2.db')


class PredictionTracker:
    """预测追踪器 - 记录每次预测，等待结果后复盘"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """初始化预测追踪表"""
        conn = self._get_conn()
        c = conn.cursor()

        # 预测记录表
        c.execute('''
            CREATE TABLE IF NOT EXISTS prediction_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                match_date DATE NOT NULL,
                match_time TEXT,
                league TEXT,
                match_type TEXT DEFAULT 'friendly',

                -- 预测数据
                pred_home_prob REAL,
                pred_draw_prob REAL,
                pred_away_prob REAL,
                pred_total_goals REAL,
                pred_score_home INTEGER,
                pred_score_away INTEGER,
                pred_result TEXT,
                pred_over_under TEXT,

                -- 模型输入参数
                fifa_home_rank INTEGER,
                fifa_away_rank INTEGER,
                fifa_rank_diff INTEGER,
                elo_home REAL,
                elo_away REAL,
                elo_diff REAL,
                form_home_rating REAL,
                form_away_rating REAL,
                form_diff REAL,
                h2h_home_wins INTEGER,
                h2h_draws INTEGER,
                h2h_away_wins INTEGER,
                h2h_total INTEGER,

                -- 特殊因素标记
                is_friendly INTEGER DEFAULT 0,
                home_advantage INTEGER DEFAULT 1,
                motivation_home TEXT,
                motivation_away TEXT,
                injury_impact_home REAL,
                injury_impact_away REAL,
                news_sentiment_home REAL,
                news_sentiment_away REAL,

                -- 模型版本
                model_version TEXT DEFAULT 'v1.0',
                model_params TEXT,

                -- 预测时间
                predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(match_id, predicted_at)
            )
        ''')

        # 实际结果表
        c.execute('''
            CREATE TABLE IF NOT EXISTS match_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                match_date DATE NOT NULL,

                -- 实际结果
                actual_home_score INTEGER,
                actual_away_score INTEGER,
                actual_result TEXT,
                actual_total_goals INTEGER,
                actual_over_under TEXT,

                -- 比赛详情
                home_score_ht INTEGER,
                away_score_ht INTEGER,
                possession_home REAL,
                shots_home INTEGER,
                shots_away INTEGER,
                shots_on_target_home INTEGER,
                shots_on_target_away INTEGER,
                corners_home INTEGER,
                corners_away INTEGER,

                -- 结果获取时间
                result_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(match_id)
            )
        ''')

        # 复盘评估表
        c.execute('''
            CREATE TABLE IF NOT EXISTS prediction_review (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id INTEGER NOT NULL,
                match_id TEXT NOT NULL,

                -- 评估结果
                result_correct INTEGER,
                score_correct INTEGER,
                over_under_correct INTEGER,
                brier_score REAL,
                log_loss REAL,

                -- 误差分析
                prob_error_home REAL,
                prob_error_draw REAL,
                prob_error_away REAL,
                goal_error REAL,
                rank_prediction TEXT,

                -- 因素复盘
                key_factors_correct TEXT,
                missed_factors TEXT,
                unexpected_events TEXT,

                -- 优化建议
                param_adjustment_suggested TEXT,
                rule_adjustment_suggested TEXT,

                reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (prediction_id) REFERENCES prediction_records(id)
            )
        ''')

        # 模型参数优化历史
        c.execute('''
            CREATE TABLE IF NOT EXISTS model_params_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_version TEXT NOT NULL,
                param_name TEXT NOT NULL,
                old_value REAL,
                new_value REAL,
                change_reason TEXT,
                accuracy_before REAL,
                accuracy_after REAL,
                sample_size INTEGER,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建索引
        c.execute('CREATE INDEX IF NOT EXISTS idx_pred_match ON prediction_records(match_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_pred_date ON prediction_records(match_date)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_result_match ON match_results(match_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_review_pred ON prediction_review(prediction_id)')

        conn.commit()
        conn.close()
        logger.info("预测追踪表初始化完成")

    def save_prediction(self, match_data: Dict, prediction: Dict, model_params: Dict = None) -> int:
        """
        保存预测记录

        Args:
            match_data: 比赛基础数据
            prediction: 预测结果
            model_params: 模型参数

        Returns:
            prediction_id
        """
        conn = self._get_conn()
        c = conn.cursor()

        c.execute('''
            INSERT INTO prediction_records (
                match_id, home_team, away_team, match_date, match_time, league, match_type,
                pred_home_prob, pred_draw_prob, pred_away_prob, pred_total_goals,
                pred_score_home, pred_score_away, pred_result, pred_over_under,
                fifa_home_rank, fifa_away_rank, fifa_rank_diff,
                elo_home, elo_away, elo_diff,
                form_home_rating, form_away_rating, form_diff,
                h2h_home_wins, h2h_draws, h2h_away_wins, h2h_total,
                is_friendly, home_advantage, motivation_home, motivation_away,
                injury_impact_home, injury_impact_away,
                news_sentiment_home, news_sentiment_away,
                model_version, model_params
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            match_data.get('match_id'),
            match_data.get('home_team'),
            match_data.get('away_team'),
            match_data.get('match_date'),
            match_data.get('match_time'),
            match_data.get('league'),
            match_data.get('match_type', 'friendly'),
            prediction.get('home_prob'),
            prediction.get('draw_prob'),
            prediction.get('away_prob'),
            prediction.get('total_goals'),
            prediction.get('score_home'),
            prediction.get('score_away'),
            prediction.get('result'),
            prediction.get('over_under'),
            match_data.get('fifa_home_rank'),
            match_data.get('fifa_away_rank'),
            match_data.get('fifa_rank_diff'),
            match_data.get('elo_home'),
            match_data.get('elo_away'),
            match_data.get('elo_diff'),
            match_data.get('form_home_rating'),
            match_data.get('form_away_rating'),
            match_data.get('form_diff'),
            match_data.get('h2h_home_wins'),
            match_data.get('h2h_draws'),
            match_data.get('h2h_away_wins'),
            match_data.get('h2h_total'),
            match_data.get('is_friendly', 1),
            match_data.get('home_advantage', 1),
            match_data.get('motivation_home'),
            match_data.get('motivation_away'),
            match_data.get('injury_impact_home'),
            match_data.get('injury_impact_away'),
            match_data.get('news_sentiment_home'),
            match_data.get('news_sentiment_away'),
            prediction.get('model_version', 'v1.0'),
            json.dumps(model_params, ensure_ascii=False) if model_params else None
        ))

        prediction_id = c.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"预测已记录: {match_data['home_team']} vs {match_data['away_team']} (ID={prediction_id})")
        return prediction_id

    def update_result(self, match_id: str, result_data: Dict) -> int:
        """
        更新比赛结果

        Args:
            match_id: 比赛ID
            result_data: 结果数据
        """
        conn = self._get_conn()
        c = conn.cursor()

        home_score = result_data.get('home_score')
        away_score = result_data.get('away_score')

        if home_score is None or away_score is None:
            conn.close()
            return 0

        # 确定结果
        if home_score > away_score:
            actual_result = 'home'
        elif home_score < away_score:
            actual_result = 'away'
        else:
            actual_result = 'draw'

        total_goals = home_score + away_score
        actual_over_under = 'over' if total_goals > 2.5 else 'under'

        c.execute('''
            INSERT OR REPLACE INTO match_results (
                match_id, home_team, away_team, match_date,
                actual_home_score, actual_away_score, actual_result,
                actual_total_goals, actual_over_under,
                home_score_ht, away_score_ht,
                possession_home, shots_home, shots_away,
                shots_on_target_home, shots_on_target_away,
                corners_home, corners_away
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            match_id,
            result_data.get('home_team'),
            result_data.get('away_team'),
            result_data.get('match_date'),
            home_score, away_score, actual_result,
            total_goals, actual_over_under,
            result_data.get('home_score_ht'),
            result_data.get('away_score_ht'),
            result_data.get('possession_home'),
            result_data.get('shots_home'),
            result_data.get('shots_away'),
            result_data.get('shots_on_target_home'),
            result_data.get('shots_on_target_away'),
            result_data.get('corners_home'),
            result_data.get('corners_away')
        ))

        conn.commit()
        conn.close()

        logger.info(f"结果已更新: {match_id} {home_score}-{away_score}")
        return 1

    def review_prediction(self, match_id: str) -> Dict:
        """
        复盘单场预测

        Returns:
            复盘评估结果
        """
        conn = self._get_conn()
        c = conn.cursor()

        # 获取预测
        c.execute('SELECT * FROM prediction_records WHERE match_id = ?', (match_id,))
        pred_row = c.fetchone()
        if not pred_row:
            conn.close()
            return {'error': '预测记录不存在'}

        prediction = dict(pred_row)

        # 获取结果
        c.execute('SELECT * FROM match_results WHERE match_id = ?', (match_id,))
        result_row = c.fetchone()
        if not result_row:
            conn.close()
            return {'error': '比赛结果尚未获取', 'status': 'pending'}

        result = dict(result_row)

        # 计算评估指标
        review = {
            'match_id': match_id,
            'prediction_id': prediction['id'],
            'home_team': prediction['home_team'],
            'away_team': prediction['away_team'],
            'predicted': {
                'home_prob': prediction['pred_home_prob'],
                'draw_prob': prediction['pred_draw_prob'],
                'away_prob': prediction['pred_away_prob'],
                'result': prediction['pred_result'],
                'score': f"{prediction['pred_score_home']}-{prediction['pred_score_away']}",
                'total_goals': prediction['pred_total_goals']
            },
            'actual': {
                'home_score': result['actual_home_score'],
                'away_score': result['actual_away_score'],
                'result': result['actual_result'],
                'total_goals': result['actual_total_goals']
            }
        }

        # 胜平负正确性
        review['result_correct'] = 1 if prediction['pred_result'] == result['actual_result'] else 0

        # 比分正确性
        pred_score = (prediction['pred_score_home'], prediction['pred_score_away'])
        actual_score = (result['actual_home_score'], result['actual_away_score'])
        review['score_correct'] = 1 if pred_score == actual_score else 0

        # 大小球正确性
        review['over_under_correct'] = 1 if prediction['pred_over_under'] == result['actual_over_under'] else 0

        # Brier Score (概率预测准确性)
        actual_probs = {'home': 0, 'draw': 0, 'away': 0}
        actual_probs[result['actual_result']] = 1
        brier = (
            (prediction['pred_home_prob'] - actual_probs['home']) ** 2 +
            (prediction['pred_draw_prob'] - actual_probs['draw']) ** 2 +
            (prediction['pred_away_prob'] - actual_probs['away']) ** 2
        ) / 3
        review['brier_score'] = brier

        # 概率误差
        review['prob_error_home'] = prediction['pred_home_prob'] - actual_probs['home']
        review['prob_error_draw'] = prediction['pred_draw_prob'] - actual_probs['draw']
        review['prob_error_away'] = prediction['pred_away_prob'] - actual_probs['away']

        # 进球误差
        review['goal_error'] = prediction['pred_total_goals'] - result['actual_total_goals']

        # 排名预测准确性
        rank_diff = prediction['fifa_rank_diff'] or 0
        if rank_diff < -30 and result['actual_result'] == 'home':
            review['rank_prediction'] = 'correct'  # 高排名主队赢
        elif rank_diff > 30 and result['actual_result'] == 'away':
            review['rank_prediction'] = 'correct'  # 高排名客队赢
        elif abs(rank_diff) <= 15 and result['actual_result'] == 'draw':
            review['rank_prediction'] = 'correct'  # 排名接近平局
        else:
            review['rank_prediction'] = 'incorrect'

        # 分析意外情况
        unexpected = []
        if result['actual_result'] != prediction['pred_result']:
            if abs(rank_diff) > 50:
                unexpected.append(f"排名差距{abs(rank_diff)}但结果相反")
            if prediction['is_friendly'] and result['actual_result'] == 'draw':
                unexpected.append("友谊赛平局符合预期")
            if result['actual_total_goals'] > 3:
                unexpected.append(f"进球数超预期({result['actual_total_goals']}球)")

        review['unexpected_events'] = unexpected

        # 保存复盘结果
        c.execute('''
            INSERT INTO prediction_review (
                prediction_id, match_id,
                result_correct, score_correct, over_under_correct,
                brier_score, log_loss,
                prob_error_home, prob_error_draw, prob_error_away,
                goal_error, rank_prediction,
                unexpected_events
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            prediction['id'], match_id,
            review['result_correct'], review['score_correct'], review['over_under_correct'],
            review['brier_score'], None,
            review['prob_error_home'], review['prob_error_draw'], review['prob_error_away'],
            review['goal_error'], review['rank_prediction'],
            json.dumps(unexpected, ensure_ascii=False)
        ))

        conn.commit()
        conn.close()

        return review

    def get_model_accuracy(self, days: int = 30, model_version: str = None) -> Dict:
        """
        获取模型准确性统计

        Args:
            days: 统计天数
            model_version: 模型版本
        """
        conn = self._get_conn()
        c = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        query = '''
            SELECT
                COUNT(*) as total,
                SUM(result_correct) as result_hits,
                SUM(score_correct) as score_hits,
                SUM(over_under_correct) as ou_hits,
                AVG(brier_score) as avg_brier,
                AVG(goal_error) as avg_goal_error
            FROM prediction_review r
            JOIN prediction_records p ON r.prediction_id = p.id
            WHERE p.match_date >= ?
        '''
        params = [since]

        if model_version:
            query += ' AND p.model_version = ?'
            params.append(model_version)

        c.execute(query, params)
        row = c.fetchone()

        if row and row['total'] > 0:
            accuracy = {
                'total_predictions': row['total'],
                'result_accuracy': row['result_hits'] / row['total'] * 100,
                'score_accuracy': row['score_hits'] / row['total'] * 100,
                'over_under_accuracy': row['ou_hits'] / row['total'] * 100,
                'avg_brier_score': row['avg_brier'],
                'avg_goal_error': row['avg_goal_error']
            }
        else:
            accuracy = {'total_predictions': 0}

        # 按比赛类型细分
        c.execute('''
            SELECT p.match_type,
                   COUNT(*) as total,
                   SUM(r.result_correct) as hits,
                   AVG(r.brier_score) as avg_brier
            FROM prediction_review r
            JOIN prediction_records p ON r.prediction_id = p.id
            WHERE p.match_date >= ?
            GROUP BY p.match_type
        ''', (since,))

        accuracy['by_match_type'] = {}
        for row in c.fetchall():
            accuracy['by_match_type'][row['match_type']] = {
                'total': row['total'],
                'accuracy': row['hits'] / row['total'] * 100 if row['total'] > 0 else 0,
                'avg_brier': row['avg_brier']
            }

        # 按排名差距细分
        c.execute('''
            SELECT
                CASE
                    WHEN fifa_rank_diff < -50 THEN 'home_strong'
                    WHEN fifa_rank_diff > 50 THEN 'away_strong'
                    WHEN ABS(fifa_rank_diff) <= 15 THEN 'even'
                    ELSE 'moderate_diff'
                END as rank_category,
                COUNT(*) as total,
                SUM(r.result_correct) as hits
            FROM prediction_review r
            JOIN prediction_records p ON r.prediction_id = p.id
            WHERE p.match_date >= ?
            GROUP BY rank_category
        ''', (since,))

        accuracy['by_rank_diff'] = {}
        for row in c.fetchall():
            accuracy['by_rank_diff'][row['rank_category']] = {
                'total': row['total'],
                'accuracy': row['hits'] / row['total'] * 100 if row['total'] > 0 else 0
            }

        conn.close()
        return accuracy

    def suggest_param_adjustments(self, min_samples: int = 10) -> List[Dict]:
        """
        基于复盘数据建议参数调整

        Args:
            min_samples: 最小样本数

        Returns:
            参数调整建议列表
        """
        conn = self._get_conn()
        c = conn.cursor()

        suggestions = []

        # 1. 检查友谊赛平局率
        c.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN r.result_correct = 0 AND p.pred_result != 'draw' AND r.actual_result = 'draw' THEN 1 ELSE 0 END) as missed_draws,
                AVG(r.brier_score) as avg_brier
            FROM prediction_review r
            JOIN prediction_records p ON r.prediction_id = p.id
            WHERE p.is_friendly = 1
        ''')

        row = c.fetchone()
        if row and row['total'] >= min_samples:
            missed_draw_rate = row['missed_draws'] / row['total']
            if missed_draw_rate > 0.3:
                suggestions.append({
                    'param': 'friendly_draw_boost',
                    'current_value': 0.30,
                    'suggested_value': 0.35 + missed_draw_rate * 0.1,
                    'reason': f"友谊赛平局漏判率{missed_draw_rate*100:.1f}%，需提高平局概率",
                    'sample_size': row['total']
                })

        # 2. 检查排名差距权重
        c.execute('''
            SELECT
                AVG(ABS(fifa_rank_diff)) as avg_rank_diff,
                AVG(ABS(r.prob_error_home)) as avg_home_error,
                AVG(ABS(r.prob_error_away)) as avg_away_error
            FROM prediction_review r
            JOIN prediction_records p ON r.prediction_id = p.id
            WHERE ABS(fifa_rank_diff) > 30
        ''')

        row = c.fetchone()
        if row and row['avg_home_error'] > 0.15:
            suggestions.append({
                'param': 'fifa_rank_weight',
                'current_value': 0.3,
                'suggested_value': 0.25,
                'reason': f"排名差距大时主胜概率误差{row['avg_home_error']*100:.1f}%，需降低权重",
                'sample_size': row['total'] if 'total' in row.keys() else 0
            })

        # 3. 检查状态因素权重
        c.execute('''
            SELECT
                AVG(p.form_diff) as avg_form_diff,
                AVG(r.goal_error) as avg_goal_error
            FROM prediction_review r
            JOIN prediction_records p ON r.prediction_id = p.id
        ''')

        row = c.fetchone()
        if row and abs(row['avg_goal_error']) > 0.5:
            suggestions.append({
                'param': 'form_weight',
                'current_value': 0.2,
                'suggested_value': 0.25 if row['avg_goal_error'] < 0 else 0.15,
                'reason': f"平均进球误差{row['avg_goal_error']:.1f}球，需调整状态权重",
                'sample_size': row['total'] if 'total' in row.keys() else 0
            })

        conn.close()
        return suggestions

    def auto_fetch_results(self, hours_after: int = 3):
        """
        自动获取已结束比赛的结果

        Args:
            hours_after: 比赛开始后多少小时获取结果
        """
        from fetchers.apifootball.get_data import get_match_detail, get_fixtures

        conn = self._get_conn()
        c = conn.cursor()

        # 查找需要更新结果的预测
        now = datetime.now()
        cutoff = (now - timedelta(hours=hours_after)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT p.match_id, p.home_team, p.away_team, p.match_date, p.match_time
            FROM prediction_records p
            WHERE p.match_date <= ?
            AND NOT EXISTS (
                SELECT 1 FROM match_results r WHERE r.match_id = p.match_id
            )
        ''', (cutoff,))

        pending = c.fetchall()
        conn.close()

        logger.info(f"待更新结果: {len(pending)}场")

        for row in pending:
            match_id = row['match_id']
            try:
                detail = get_match_detail(match_id)
                if detail and detail.get('status') in ['finished', 'FT', '90']:
                    self.update_result(match_id, {
                        'home_team': row['home_team'],
                        'away_team': row['away_team'],
                        'match_date': row['match_date'],
                        'home_score': detail.get('home_score'),
                        'away_score': detail.get('away_score'),
                        'home_score_ht': detail.get('home_score_ht'),
                        'away_score_ht': detail.get('away_score_ht')
                    })
                    # 自动复盘
                    self.review_prediction(match_id)
            except Exception as e:
                logger.error(f"获取结果失败 {match_id}: {e}")


class ModelOptimizer:
    """模型参数优化器"""

    def __init__(self, tracker: PredictionTracker):
        self.tracker = tracker

    def optimize(self, param_name: str, old_value: float, new_value: float,
                 reason: str, sample_size: int):
        """
        记录参数优化
        """
        conn = self.tracker._get_conn()
        c = conn.cursor()

        # 获取优化前准确率
        accuracy_before = self.tracker.get_model_accuracy(days=30)

        c.execute('''
            INSERT INTO model_params_history (
                model_version, param_name, old_value, new_value,
                change_reason, accuracy_before, sample_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            'v1.0', param_name, old_value, new_value,
            reason,
            accuracy_before.get('result_accuracy'),
            sample_size
        ))

        conn.commit()
        conn.close()

        logger.info(f"参数优化记录: {param_name} {old_value} -> {new_value}")

    def run_daily_review(self):
        """
        每日复盘流程
        """
        print("=" * 60)
        print("每日预测复盘")
        print("=" * 60)

        # 1. 获取缺失结果
        self.tracker.auto_fetch_results()

        # 2. 复盘待评估预测
        conn = self.tracker._get_conn()
        c = conn.cursor()

        c.execute('''
            SELECT p.match_id FROM prediction_records p
            WHERE NOT EXISTS (
                SELECT 1 FROM prediction_review r WHERE r.match_id = p.match_id
            )
            AND EXISTS (
                SELECT 1 FROM match_results m WHERE m.match_id = p.match_id
            )
        ''')

        pending_reviews = [row[0] for row in c.fetchall()]
        conn.close()

        print(f"\n待复盘预测: {len(pending_reviews)}场")

        for match_id in pending_reviews:
            review = self.tracker.review_prediction(match_id)
            if 'error' not in review:
                print(f"  {match_id}: 结果={review['result_correct']}, Brier={review['brier_score']:.3f}")

        # 3. 输出准确率统计
        accuracy = self.tracker.get_model_accuracy(days=30)
        print(f"\n近30日模型准确率:")
        print(f"  总预测: {accuracy['total_predictions']}场")
        print(f"  胜平负: {accuracy['result_accuracy']:.1f}%")
        print(f"  大小球: {accuracy['over_under_accuracy']:.1f}%")
        print(f"  Brier Score: {accuracy['avg_brier_score']:.3f}")

        # 4. 参数调整建议
        suggestions = self.tracker.suggest_param_adjustments(min_samples=5)
        if suggestions:
            print(f"\n参数调整建议:")
            for s in suggestions:
                print(f"  {s['param']}: {s['current_value']} -> {s['suggested_value']}")
                print(f"    原因: {s['reason']}")
                print(f"    样本: {s['sample_size']}场")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='预测复盘系统')
    parser.add_argument('--fetch', action='store_true', help='获取比赛结果')
    parser.add_argument('--review', type=str, help='复盘单场比赛')
    parser.add_argument('--accuracy', action='store_true', help='查看准确率')
    parser.add_argument('--suggest', action='store_true', help='参数调整建议')
    parser.add_argument('--daily', action='store_true', help='每日复盘流程')

    args = parser.parse_args()

    tracker = PredictionTracker()

    if args.fetch:
        tracker.auto_fetch_results()

    if args.review:
        review = tracker.review_prediction(args.review)
        print(json.dumps(review, ensure_ascii=False, indent=2))

    if args.accuracy:
        accuracy = tracker.get_model_accuracy(days=30)
        print(json.dumps(accuracy, ensure_ascii=False, indent=2))

    if args.suggest:
        suggestions = tracker.suggest_param_adjustments()
        print(json.dumps(suggestions, ensure_ascii=False, indent=2))

    if args.daily:
        optimizer = ModelOptimizer(tracker)
        optimizer.run_daily_review()

    if not any([args.fetch, args.review, args.accuracy, args.suggest, args.daily]):
        print("预测复盘系统")
        print("用法:")
        print("  python prediction_tracker.py --fetch          # 获取结果")
        print("  python prediction_tracker.py --review 763698  # 复盘单场")
        print("  python prediction_tracker.py --accuracy       # 查看准确率")
        print("  python prediction_tracker.py --suggest        # 参数建议")
        print("  python prediction_tracker.py --daily          # 每日复盘")