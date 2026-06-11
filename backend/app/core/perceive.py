"""
6:00 自感知 — 日循环第一步

职责:
1. DB连接健康检查
2. 昨日未完成任务诊断 → 路由到validate
3. 熔断检测 → 模型准确率<赔率基线 → circuit_break路由
4. 冷启动检测 → 热启动
5. 数据源健康检查
6. Agent策略选择(如果可用)
7. 输出DailyStatus写入daily_cycle_state
"""

import json
import logging
import sqlite3
from datetime import date, timedelta
from typing import Dict, List, Optional

from .time_utils import today_beijing, yesterday_beijing

logger = logging.getLogger(__name__)


def perceive(state, db_path: str, agent=None) -> dict:
    """执行自感知，返回结果+路由"""
    logger.info('=== 6:00 自感知 ===')

    checks = {}
    route = 'normal'

    # 0. oddsfe增量同步(最先执行，确保后续检查基于最新数据)
    sync_result = _sync_oddsfe_incremental(db_path)
    checks['oddsfe_sync'] = sync_result

    # 1. DB健康检查
    checks['db'] = _check_db(db_path)

    # 2. 昨日未完成 → 路由到validate
    incomplete = _check_yesterday_incomplete(db_path)
    checks['yesterday_incomplete'] = incomplete
    if incomplete:
        route = 'validate_yesterday'

    # 3. 熔断检测
    circuit = _check_circuit_breaker(db_path)
    checks['circuit_breaker'] = circuit
    if circuit.get('triggered'):
        route = 'circuit_break'

    # 4. 冷启动检测 → 执行热启动
    cold = _check_cold_start(db_path)
    checks['cold_start'] = cold
    if cold.get('is_cold'):
        warmup_result = _run_warmup(db_path)
        checks['warmup'] = warmup_result
        logger.info(f'热启动完成: mode={warmup_result.get("mode")}, '
                    f'accuracy={warmup_result.get("odds_accuracy", 0):.2%}')
        # 热启动后继续正常流程
        route = 'normal'

    # 5. 数据源健康
    checks['data_sources'] = _check_data_sources(db_path)

    # 6. Agent策略选择(如果可用且非冷启动)
    if route not in ('warmup', 'circuit_break'):
        agent_result = _agent_strategy_select(db_path, agent)
        if agent_result:
            checks['agent_strategy'] = agent_result

    # 7. 异常诊断(数据源不健康时)
    unhealthy = checks['data_sources'].get('unhealthy', 0)
    if unhealthy > 0:
        agent_diag = _agent_anomaly_diagnosis(db_path, agent, checks)
        if agent_diag:
            checks['agent_diagnosis'] = agent_diag

    logger.info('自感知完成: route=%s', route)

    return {
        'route': route,
        'checks': checks,
    }


def _check_db(db_path: str) -> dict:
    """检查数据库健康"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM matches")
        match_count = cursor.fetchone()[0]
        cursor.execute("SELECT MAX(match_date) FROM matches")
        latest = cursor.fetchone()[0]
        conn.close()
        return {'ok': True, 'matches': match_count, 'latest_date': latest}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def _check_yesterday_incomplete(db_path: str) -> list:
    """检查昨日未完成任务"""
    yesterday = yesterday_beijing()
    incomplete = []

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        # 昨日比赛但无赔率
        cursor.execute("""
            SELECT COUNT(*) FROM lottery_matches
            WHERE match_date = ? AND lottery_match_id NOT IN (
                SELECT DISTINCT lottery_match_id FROM lottery_odds
            )
        """, (yesterday,))
        no_odds = cursor.fetchone()[0]
        if no_odds > 0:
            incomplete.append({'task': 'sync_odds', 'count': no_odds})

        # 昨日已完赛但无验证
        cursor.execute("""
            SELECT COUNT(*) FROM lottery_matches lm
            JOIN lottery_results lr ON lm.lottery_match_id = lr.lottery_match_id
            WHERE lm.match_date = ? AND lm.lottery_match_id NOT IN (
                SELECT DISTINCT lottery_match_id FROM lottery_validation
            )
        """, (yesterday,))
        no_validation = cursor.fetchone()[0]
        if no_validation > 0:
            incomplete.append({'task': 'validate', 'count': no_validation})

        conn.close()
    except Exception as e:
        logger.debug(f"昨日检查失败: {e}")

    return incomplete


def _check_circuit_breaker(db_path: str) -> dict:
    """熔断检测: 模型准确率 < 赔率基线"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        # 最近30天模型vs赔率基线
        cursor.execute("""
            SELECT scene_type, model_accuracy, odds_baseline_accuracy, total_matches
            FROM model_accuracy
            WHERE calculated_at >= date('now', '-30 days')
            ORDER BY calculated_at DESC LIMIT 5
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {'triggered': False, 'note': 'no accuracy data'}

        # Only trigger if model < baseline with sufficient sample (min 10 matches)
        triggered = False
        for row in rows:
            scene, model_acc, baseline_acc, total = row[0], row[1], row[2], (row[3] or 0)
            if model_acc is None or baseline_acc is None:
                continue
            if total < 10:
                continue
            if model_acc < baseline_acc:
                triggered = True
                break

        return {
            'triggered': triggered,
            'scenes': [{'scene': r[0], 'model': r[1], 'baseline': r[2]} for r in rows],
        }

    except Exception:
        return {'triggered': False, 'note': 'table not available'}


def _check_cold_start(db_path: str) -> dict:
    """冷启动检测: 无历史预测→需要热启动"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM lottery_validation")
        validation_count = cursor.fetchone()[0]
        conn.close()

        is_cold = validation_count < 10  # 少于10条验证记录视为冷启动
        return {'is_cold': is_cold, 'validations': validation_count}
    except Exception:
        return {'is_cold': False}


def _check_data_sources(db_path: str) -> dict:
    """检查数据源健康"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT source_name, status, last_success FROM data_source_health")
        sources = [dict(row) for row in cursor.fetchall()]
        conn.close()
        unhealthy = [s for s in sources if s.get('status') not in ('healthy', 'unknown')]
        return {'total': len(sources), 'unhealthy': len(unhealthy), 'sources': sources}
    except Exception:
        return {'total': 0, 'unhealthy': 0}


def _agent_strategy_select(db_path: str, agent=None) -> Optional[dict]:
    """Agent策略选择 — 根据今日赛事+近期准确率推荐策略"""
    # 自动初始化Agent
    if agent is None:
        try:
            from backend.app.core.agent.client import create_agent
            agent = create_agent(db_path)
        except Exception:
            return None

    if not agent:
        return None

    try:
        # 今日赛事构成
        today = today_beijing()
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT league_name_cn, COUNT(*) as cnt
            FROM lottery_matches WHERE match_date = ?
            GROUP BY league_name_cn
        """, (today,))
        match_groups = [dict(r) for r in cursor.fetchall()]

        # 近期准确率
        cursor.execute("""
            SELECT
                COALESCE(scenario_type, 'unknown') as scene,
                COUNT(*) as total,
                SUM(is_correct) as correct,
                AVG(brier_score) as brier
            FROM lottery_validation
            WHERE validated_at >= datetime('now', '-30 days')
            GROUP BY scenario_type
        """)
        accuracy = [dict(r) for r in cursor.fetchall()]
        conn.close()

        if not match_groups:
            return None

        return agent.strategy_select(
            {'date': today, 'matches': match_groups},
            {'recent': accuracy}
        )
    except Exception as e:
        logger.debug(f'Agent策略选择失败: {e}')
        return None


def _agent_anomaly_diagnosis(db_path: str, agent=None, checks: dict = None) -> Optional[dict]:
    """Agent异常诊断 — 数据源不健康时"""
    if agent is None:
        try:
            from backend.app.core.agent.client import create_agent
            agent = create_agent(db_path)
        except Exception:
            return None

    if not agent:
        return None

    try:
        error_info = {
            'unhealthy_sources': checks.get('data_sources', {}).get('unhealthy', 0),
            'yesterday_incomplete': checks.get('yesterday_incomplete', []),
        }
        source_health = checks.get('data_sources', {})

        return agent.anomaly_diagnosis(error_info, source_health)
    except Exception as e:
        logger.debug(f'Agent异常诊断失败: {e}')
        return None


def _run_warmup(db_path: str) -> dict:
    """执行热启动 — 用oddsfe 229K历史数据校准"""
    try:
        from backend.app.core.warmup import run_warmup
        return run_warmup(db_path=db_path)
    except Exception as e:
        logger.error(f'热启动失败: {e}')
        return {'error': str(e), 'mode': 'default', 'odds_accuracy': 0}


def _sync_oddsfe_incremental(db_path: str) -> dict:
    """执行oddsfe增量同步 — 将oddsfe_merged.db最新数据同步到football_v2.db

    同步3种更新:
    1. 新比赛(oddsfe有新event_id) → INSERT
    2. 赛果更新(scheduled→finished) → UPDATE status+比分
    3. 赔率变化 → INSERT match_odds_normalized
    """
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(db_path).parent.parent
    oddsfe_path = str(Path(db_path).parent / 'oddsfe_merged.db')
    sync_script = str(project_root / 'scripts' / 'oddsfe_sync.py')

    if not Path(oddsfe_path).exists():
        logger.debug('oddsfe_merged.db不存在，跳过增量同步')
        return {'status': 'skipped', 'reason': 'no oddsfe db'}

    if not Path(sync_script).exists():
        logger.debug('oddsfe_sync.py不存在，跳过增量同步')
        return {'status': 'skipped', 'reason': 'no sync script'}

    try:
        result = subprocess.run(
            [sys.executable, sync_script,
             '--oddsfe', oddsfe_path,
             '--db', db_path,
             '--incremental', '--days', '5'],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            logger.info('oddsfe增量同步完成')
            return {'status': 'ok', 'returncode': result.returncode}
        else:
            logger.warning('oddsfe增量同步失败: %s', result.stderr[:200] if result.stderr else 'unknown')
            return {'status': 'error', 'returncode': result.returncode,
                    'error': result.stderr[:200] if result.stderr else ''}
    except subprocess.TimeoutExpired:
        logger.warning('oddsfe增量同步超时(5min)')
        return {'status': 'timeout'}
    except Exception as e:
        logger.warning('oddsfe增量同步异常: %s', e)
        return {'status': 'error', 'error': str(e)}