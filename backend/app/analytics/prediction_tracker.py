"""
预测追踪器 — 闭环分析核心

负责：
1. 记录每次预测（含完整子分析器输出和权重）
2. 赛后验证（预测 vs 实际赛果）
3. 计算准确率指标
4. 调用 WeightOptimizer 自动优化
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class PredictionTracker:
    """预测追踪与验证"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── 1. 记录预测 ──────────────────────────────────────────

    def log_prediction(
        self,
        match_id: str,
        prediction: Dict,
        weights_used: Dict,
        model_version: str = 'v1'
    ) -> int:
        """
        记录一次完整预测，返回 log_id

        prediction: comprehensive analyzer 的完整输出
        weights_used: 本次使用的权重配置
        """
        conn = self.get_connection()
        try:
            fp = prediction.get('final_prediction', {})
            probs = fp.get('probabilities', {})
            expected = fp.get('expected_score', {})
            ou = fp.get('over_under_2_5', {})
            btts = fp.get('both_teams_to_score', {})
            bp = prediction.get('base_prediction', {})
            mls = fp.get('most_likely_scores', [])

            # 提取比赛信息
            cursor = conn.cursor()
            cursor.execute("SELECT match_date, league_id, season_id FROM matches WHERE match_id = ?", (match_id,))
            match_info = cursor.fetchone()

            log_id = cursor.execute('''
                INSERT OR REPLACE INTO prediction_logs (
                    match_id, home_team_id, away_team_id, league_id, season_id, match_date,
                    home_win_prob, draw_prob, away_win_prob,
                    predicted_result, confidence, confidence_level,
                    expected_home_goals, expected_away_goals,
                    most_likely_score,
                    over_2_5_prob, under_2_5_prob,
                    btts_yes_prob, btts_no_prob,
                    elo_output, poisson_output, h2h_output, form_output,
                    home_away_output, motivation_output, news_factors_output,
                    weights_used, adjustments,
                    model_version
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                match_id,
                prediction.get('home_team_id'),
                prediction.get('away_team_id'),
                match_info['league_id'] if match_info else None,
                match_info['season_id'] if match_info else None,
                match_info['match_date'] if match_info else prediction.get('match_date'),
                probs.get('home_win'),
                probs.get('draw'),
                probs.get('away_win'),
                fp.get('predicted_result'),
                fp.get('confidence'),
                fp.get('confidence_level'),
                expected.get('home'),
                expected.get('away'),
                mls[0].get('score') if mls else None,
                ou.get('over'),
                ou.get('under'),
                btts.get('yes'),
                btts.get('no'),
                json.dumps(bp.get('elo'), ensure_ascii=False) if bp.get('elo') else None,
                json.dumps(bp.get('poisson'), ensure_ascii=False) if bp.get('poisson') else None,
                json.dumps(prediction.get('h2h_analysis'), ensure_ascii=False),
                json.dumps(prediction.get('form_comparison'), ensure_ascii=False),
                json.dumps(prediction.get('home_away_analysis'), ensure_ascii=False),
                json.dumps(prediction.get('motivation_analysis'), ensure_ascii=False),
                json.dumps(prediction.get('news_factors_analysis'), ensure_ascii=False),
                json.dumps(weights_used, ensure_ascii=False),
                json.dumps(prediction.get('adjustments'), ensure_ascii=False),
                model_version
            )).lastrowid

            conn.commit()
            return log_id
        finally:
            conn.close()

    # ── 2. 赛后验证 ──────────────────────────────────────────

    def validate_predictions(self, match_ids: List[str] = None) -> Dict:
        """
        验证已结束比赛的预测

        对比预测和实际赛果，计算准确度指标
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            # 找出有预测但还没验证的已结束比赛
            if match_ids:
                placeholders = ','.join(['?'] * len(match_ids))
                cursor.execute(f'''
                    SELECT pl.*, m.home_goals, m.away_goals, m.status
                    FROM prediction_logs pl
                    JOIN matches m ON pl.match_id = m.match_id
                    LEFT JOIN prediction_results pr ON pl.match_id = pr.match_id
                    WHERE m.status = 'finished'
                    AND m.home_goals IS NOT NULL
                    AND pr.result_id IS NULL
                    AND pl.match_id IN ({placeholders})
                ''', match_ids)
            else:
                cursor.execute('''
                    SELECT pl.*, m.home_goals, m.away_goals, m.status
                    FROM prediction_logs pl
                    JOIN matches m ON pl.match_id = m.match_id
                    LEFT JOIN prediction_results pr ON pl.match_id = pr.match_id
                    WHERE m.status = 'finished'
                    AND m.home_goals IS NOT NULL
                    AND pr.result_id IS NULL
                ''')

            pending = cursor.fetchall()
            results = []

            for row in pending:
                validation = self._validate_single(cursor, dict(row))
                results.append(validation)

            conn.commit()

            return {
                'validated_count': len(results),
                'results': results
            }
        finally:
            conn.close()

    def _validate_single(self, cursor, log: Dict) -> Dict:
        """验证单条预测"""
        actual_home = log['home_goals']
        actual_away = log['away_goals']
        match_id = log['match_id']
        log_id = log['log_id']

        # 实际赛果
        if actual_home > actual_away:
            actual_result = 'home_win'
        elif actual_home < actual_away:
            actual_result = 'away_win'
        else:
            actual_result = 'draw'

        total_goals = actual_home + actual_away
        actual_over = 'yes' if total_goals > 2.5 else 'no'
        actual_btts = 'yes' if actual_home > 0 and actual_away > 0 else 'no'

        # 预测正确性
        result_correct = 1 if log['predicted_result'] == actual_result else 0
        predicted_ou = 'yes' if (log['over_2_5_prob'] or 0) > 0.5 else 'no'
        over_under_correct = 1 if predicted_ou == actual_over else 0
        predicted_btts = 'yes' if (log['btts_yes_prob'] or 0) > 0.5 else 'no'
        btts_correct = 1 if predicted_btts == actual_btts else 0

        # Brier Score（概率校准度）
        brier = self._calc_brier_score(
            log['home_win_prob'], log['draw_prob'], log['away_win_prob'],
            actual_result
        )

        # Log Loss
        log_loss = self._calc_log_loss(
            log['home_win_prob'], log['draw_prob'], log['away_win_prob'],
            actual_result
        )

        # 各维度贡献分析
        dimension_contribution = self._analyze_dimension_contribution(log, actual_result)

        cursor.execute('''
            INSERT OR REPLACE INTO prediction_results (
                log_id, match_id,
                actual_home_goals, actual_away_goals, actual_result,
                actual_over_2_5, actual_btts,
                result_correct, over_under_correct, btts_correct,
                brier_score, log_loss,
                dimension_contribution
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            log_id, match_id,
            actual_home, actual_away, actual_result,
            actual_over, actual_btts,
            result_correct, over_under_correct, btts_correct,
            brier, log_loss,
            json.dumps(dimension_contribution, ensure_ascii=False)
        ))

        return {
            'match_id': match_id,
            'predicted': log['predicted_result'],
            'actual': actual_result,
            'correct': bool(result_correct),
            'brier_score': brier,
            'log_loss': log_loss
        }

    # ── 3. 指标计算 ──────────────────────────────────────────

    def get_accuracy_metrics(self, model_version: str = None, days: int = 30) -> Dict:
        """获取预测准确率指标"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            version_filter = ''
            params = []
            if model_version:
                version_filter = 'AND pl.model_version = ?'
                params.append(model_version)

            if days:
                version_filter += ' AND pl.created_at >= datetime("now", ?)'
                params.append(f'-{days} days')

            # 总体准确率
            cursor.execute(f'''
                SELECT
                    COUNT(*) as total,
                    SUM(pr.result_correct) as correct,
                    SUM(pr.over_under_correct) as ou_correct,
                    SUM(pr.btts_correct) as btts_correct,
                    AVG(pr.brier_score) as avg_brier,
                    AVG(pr.log_loss) as avg_log_loss
                FROM prediction_results pr
                JOIN prediction_logs pl ON pr.log_id = pl.log_id
                WHERE 1=1 {version_filter}
            ''', params)

            row = cursor.fetchone()
            total = row['total'] or 0

            if total == 0:
                return {'total': 0, 'message': '暂无验证数据'}

            # 按置信度分组
            cursor.execute(f'''
                SELECT
                    pl.confidence_level,
                    COUNT(*) as total,
                    SUM(pr.result_correct) as correct,
                    AVG(pr.brier_score) as avg_brier
                FROM prediction_results pr
                JOIN prediction_logs pl ON pr.log_id = pl.log_id
                WHERE 1=1 {version_filter}
                GROUP BY pl.confidence_level
            ''', params)

            by_confidence = {}
            for r in cursor.fetchall():
                cl = r['confidence_level']
                by_confidence[cl] = {
                    'total': r['total'],
                    'correct': r['correct'] or 0,
                    'accuracy': round((r['correct'] or 0) / r['total'] * 100, 2)
                }

            # 按预测结果分组
            cursor.execute(f'''
                SELECT
                    pl.predicted_result,
                    COUNT(*) as total,
                    SUM(pr.result_correct) as correct
                FROM prediction_results pr
                JOIN prediction_logs pl ON pr.log_id = pl.log_id
                WHERE 1=1 {version_filter}
                GROUP BY pl.predicted_result
            ''', params)

            by_result = {}
            for r in cursor.fetchall():
                pr = r['predicted_result']
                by_result[pr] = {
                    'total': r['total'],
                    'correct': r['correct'] or 0,
                    'accuracy': round((r['correct'] or 0) / r['total'] * 100, 2)
                }

            # 近期趋势（最近7天 vs 之前）
            cursor.execute(f'''
                SELECT
                    DATE(pl.created_at) as date,
                    COUNT(*) as total,
                    SUM(pr.result_correct) as correct,
                    AVG(pr.brier_score) as avg_brier
                FROM prediction_results pr
                JOIN prediction_logs pl ON pr.log_id = pl.log_id
                WHERE 1=1 {version_filter}
                GROUP BY DATE(pl.created_at)
                ORDER BY date DESC
                LIMIT 30
            ''', params)

            daily_trend = []
            for r in cursor.fetchall():
                daily_trend.append({
                    'date': r['date'],
                    'total': r['total'],
                    'correct': r['correct'] or 0,
                    'accuracy': round((r['correct'] or 0) / r['total'] * 100, 2) if r['total'] else 0,
                    'avg_brier': round(r['avg_brier'] or 0, 4)
                })

            return {
                'total': total,
                'result_accuracy': round((row['correct'] or 0) / total * 100, 2),
                'over_under_accuracy': round((row['ou_correct'] or 0) / total * 100, 2),
                'btts_accuracy': round((row['btts_correct'] or 0) / total * 100, 2),
                'avg_brier_score': round(row['avg_brier'] or 0, 4),
                'avg_log_loss': round(row['avg_log_loss'] or 0, 4),
                'by_confidence': by_confidence,
                'by_result': by_result,
                'daily_trend': daily_trend
            }
        finally:
            conn.close()

    # ── 4. 维度贡献分析 ──────────────────────────────────────

    def _analyze_dimension_contribution(self, log: Dict, actual_result: str) -> Dict:
        """
        分析每个子分析器对最终预测的贡献

        通过对比子分析器的原始方向和最终预测的偏差来评估
        """
        contributions = {}

        # Elo 方向
        elo_raw = json.loads(log['elo_output']) if log.get('elo_output') else None
        if elo_raw:
            elo_pred = elo_raw.get('predictions', {})
            elo_dir = max(elo_pred, key=elo_pred.get) if elo_pred else None
            contributions['elo'] = {
                'direction': elo_dir,
                'aligned': elo_dir == actual_result
            }

        # Poisson 方向
        poisson_raw = json.loads(log['poisson_output']) if log.get('poisson_output') else None
        if poisson_raw:
            pois_pred = poisson_raw.get('probabilities', {})
            pois_dir = max(pois_pred, key=pois_pred.get) if pois_pred else None
            contributions['poisson'] = {
                'direction': pois_dir,
                'aligned': pois_dir == actual_result
            }

        # Form 方向
        form_raw = json.loads(log.get('form_output') or '{}')
        if form_raw:
            comp = form_raw.get('comparison', {})
            adv = comp.get('advantage')
            if adv == 'team1':
                form_dir = 'home_win'
            elif adv == 'team2':
                form_dir = 'away_win'
            else:
                form_dir = 'draw'
            contributions['form'] = {
                'direction': form_dir,
                'aligned': form_dir == actual_result
            }

        # H2H 方向
        h2h_raw = json.loads(log.get('h2h_output') or '{}')
        if h2h_raw:
            psy = h2h_raw.get('psychological_advantage', {})
            adv = psy.get('advantage')
            if adv == 'team1':
                h2h_dir = 'home_win'
            elif adv == 'team2':
                h2h_dir = 'away_win'
            else:
                h2h_dir = 'draw'
            contributions['h2h'] = {
                'direction': h2h_dir,
                'aligned': h2h_dir == actual_result
            }

        return contributions

    # ── 5. 辅助函数 ──────────────────────────────────────────

    @staticmethod
    def _calc_brier_score(home_p: float, draw_p: float, away_p: float, actual: str) -> float:
        """Brier Score: 越低越好，0=完美"""
        probs = {'home_win': home_p or 0, 'draw': draw_p or 0, 'away_win': away_p or 0}
        actuals = {'home_win': 0, 'draw': 0, 'away_win': 0}
        actuals[actual] = 1
        return sum((probs[k] - actuals[k]) ** 2 for k in probs)

    @staticmethod
    def _calc_log_loss(home_p: float, draw_p: float, away_p: float, actual: str) -> float:
        """Log Loss: 越低越好，0=完美"""
        import math
        probs = {'home_win': home_p or 0.01, 'draw': draw_p or 0.01, 'away_win': away_p or 0.01}
        p = max(probs[actual], 0.01)
        return -math.log(p)

    def get_pending_validations(self) -> List[Dict]:
        """获取待验证的预测列表（已结束但未验证）"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pl.match_id, pl.match_date, pl.predicted_result,
                       pl.confidence_level, pl.home_win_prob, pl.draw_prob, pl.away_win_prob,
                       m.home_goals, m.away_goals,
                       ht.name_en as home_name, at.name_en as away_name
                FROM prediction_logs pl
                JOIN matches m ON pl.match_id = m.match_id
                LEFT JOIN prediction_results pr ON pl.match_id = pr.match_id
                LEFT JOIN teams ht ON pl.home_team_id = ht.team_id
                LEFT JOIN teams at ON pl.away_team_id = at.team_id
                WHERE m.status = 'finished'
                AND m.home_goals IS NOT NULL
                AND pr.result_id IS NULL
                ORDER BY pl.match_date DESC
            ''')
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_model_versions(self) -> List[Dict]:
        """获取所有模型权重版本"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM model_weights ORDER BY created_at DESC')
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_active_weights(self) -> Dict:
        """获取当前激活的权重配置"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM model_weights WHERE is_active = 1 LIMIT 1')
            row = cursor.fetchone()
            return dict(row) if row else {
                'elo_weight': 0.20, 'poisson_weight': 0.25,
                'h2h_weight': 0.10, 'form_weight': 0.15,
                'home_away_weight': 0.10, 'motivation_weight': 0.10,
                'news_factors_weight': 0.10
            }
        finally:
            conn.close()
