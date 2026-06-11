"""
6:00 自感知 — 日循环第一步

职责:
1. DB连接健康检查
2. 昨日未完成任务诊断
3. 数据源健康检查
4. 近期准确率自评
5. 生成告警
"""

import sqlite3
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SelfPerception:
    """6:00 自感知模块"""

    def __init__(self, db_path: str, config: dict = None):
        self.db_path = db_path
        self.config = config or {}
        self.issues: List[dict] = []
        self.warnings: List[dict] = []

    def run(self) -> dict:
        """执行自感知，返回诊断结果"""
        logger.info('自感知开始')

        checks = {
            'db_health': self._check_db_health(),
            'yesterday_incomplete': self._check_yesterday_incomplete(),
            'data_source_health': self._check_data_source_health(),
            'accuracy_self_eval': self._check_accuracy(),
        }

        # 汇总
        all_ok = all(c.get('ok', False) for c in checks.values())
        status = 'healthy' if all_ok and not self.issues else 'degraded'

        result = {
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'checks': checks,
            'issues': self.issues,
            'warnings': self.warnings,
        }

        if self.issues:
            logger.warning('自感知发现 %d 个问题', len(self.issues))
        if self.warnings:
            logger.info('自感知发现 %d 个警告', len(self.warnings))

        return result

    # --- 检查项 ---

    def _check_db_health(self) -> dict:
        """检查数据库连接和基本完整性"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 基本连接
            cursor.execute('SELECT 1')

            # 关键表存在性
            required_tables = [
                'matches', 'teams', 'leagues', 'standings',
                'lottery_matches', 'lottery_odds', 'lottery_predictions',
                'lottery_results', 'lottery_validation',
                'elo_ratings', 'data_source_health',
            ]
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing = {row[0] for row in cursor.fetchall()}
            missing = [t for t in required_tables if t not in existing]

            # 数据新鲜度: 最近一场比赛日期
            cursor.execute(
                "SELECT MAX(match_date) FROM matches"
            )
            row = cursor.fetchone()
            latest_match_date = row[0] if row else None

            conn.close()

            if missing:
                self.issues.append({
                    'type': 'db_missing_tables',
                    'detail': missing,
                    'severity': 'high',
                })

            return {
                'ok': not missing,
                'latest_match_date': latest_match_date,
                'missing_tables': missing,
            }

        except Exception as e:
            self.issues.append({
                'type': 'db_connection_failed',
                'detail': str(e),
                'severity': 'critical',
            })
            return {'ok': False, 'error': str(e)}

    def _check_yesterday_incomplete(self) -> dict:
        """检查昨日未完成的采集/分析任务"""
        yesterday = str(date.today() - timedelta(days=1))
        incomplete = []

        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 昨日比赛但无赔率
            cursor.execute("""
                SELECT COUNT(*) FROM lottery_matches
                WHERE match_date = ?
                AND lottery_match_id NOT IN (
                    SELECT DISTINCT lottery_match_id FROM lottery_odds
                )
            """, (yesterday,))
            no_odds = cursor.fetchone()[0]
            if no_odds > 0:
                incomplete.append({'task': 'sync_odds', 'count': no_odds})

            # 昨日比赛但无分析
            cursor.execute("""
                SELECT COUNT(*) FROM lottery_matches
                WHERE match_date = ?
                AND lottery_match_id NOT IN (
                    SELECT DISTINCT lottery_match_id FROM lottery_analysis_reports
                )
            """, (yesterday,))
            no_analysis = cursor.fetchone()[0]
            if no_analysis > 0:
                incomplete.append({'task': 'analyze', 'count': no_analysis})

            # 昨日已完赛但无验证
            cursor.execute("""
                SELECT COUNT(*) FROM lottery_matches lm
                JOIN lottery_results lr ON lm.lottery_match_id = lr.lottery_match_id
                WHERE lm.match_date = ?
                AND lm.lottery_match_id NOT IN (
                    SELECT DISTINCT lottery_match_id FROM lottery_validation
                )
            """, (yesterday,))
            no_validation = cursor.fetchone()[0]
            if no_validation > 0:
                incomplete.append({'task': 'validate', 'count': no_validation})

            conn.close()

            if incomplete:
                self.warnings.append({
                    'type': 'yesterday_incomplete',
                    'detail': incomplete,
                })

            return {
                'ok': not incomplete,
                'incomplete_tasks': incomplete,
            }

        except Exception as e:
            return {'ok': True, 'error': str(e)}

    def _check_data_source_health(self) -> dict:
        """检查数据源健康状态"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT source_name, status, last_success, success_rate
                FROM data_source_health
                ORDER BY source_name
            """)
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()

            unhealthy = [r for r in rows if r.get('status') != 'healthy']
            if unhealthy:
                self.warnings.append({
                    'type': 'unhealthy_sources',
                    'detail': [r['source_name'] for r in unhealthy],
                })

            return {
                'ok': not unhealthy,
                'sources': rows,
                'unhealthy_count': len(unhealthy),
            }

        except Exception as e:
            # data_source_health表可能不存在
            return {'ok': True, 'sources': [], 'note': str(e)}

    def _check_accuracy(self) -> dict:
        """近期准确率自评"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 最近30天spf准确率
            cursor.execute("""
                SELECT
                    play_type,
                    COUNT(*) as total,
                    SUM(is_correct) as correct,
                    AVG(brier_score) as avg_brier
                FROM lottery_validation
                WHERE validated_at >= date('now', '-30 days')
                GROUP BY play_type
            """)
            stats = [dict(row) for row in cursor.fetchall()]

            # 整体准确率
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(is_correct) as correct
                FROM lottery_validation
                WHERE validated_at >= date('now', '-30 days')
            """)
            row = cursor.fetchone()
            total = row['total'] if row else 0
            correct = row['correct'] if row else 0
            accuracy = round(correct / total * 100, 2) if total > 0 else None

            conn.close()

            # 准确率低于50%告警
            if accuracy is not None and accuracy < 50:
                self.warnings.append({
                    'type': 'low_accuracy',
                    'detail': f'30天准确率 {accuracy}% < 50%',
                })

            return {
                'ok': True,
                'accuracy_30d': accuracy,
                'total_validations': total,
                'by_play_type': stats,
            }

        except Exception as e:
            return {'ok': True, 'accuracy_30d': None, 'note': str(e)}
