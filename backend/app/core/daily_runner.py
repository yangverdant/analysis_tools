"""日循环入口 — 状态机驱动

用法:
    python -m backend.app.core.daily_runner --mode perceive
    python -m backend.app.core.daily_runner --mode morning
    python -m backend.app.core.daily_runner --mode full
"""

import argparse
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DB_PATH = os.environ.get('DB_PATH', str(PROJECT_ROOT / 'data' / 'football_v2.db'))

from .state_machine import DailyCycleStateMachine, CycleState
from .time_utils import today_beijing

logger = logging.getLogger(__name__)


def get_handlers(db_path: str = None):
    """注册所有节点处理器"""
    _db = db_path or DB_PATH

    from .perceive import perceive
    from .collect import collect
    from .intel import intel
    from .classify import classify
    from .analyze import analyze
    from .push import push
    from .clv_update import clv_update
    from .validate import validate
    from .learn import learn as _learn

    # learn函数签名不同: learn(db_path, agent, days, min_samples)
    def learn_adapter(state, db=_db):
        from .agent.client import AnalystAgent
        try:
            agent = AnalystAgent(db)
        except Exception as e:
            logger.warning('AnalystAgent实例化失败, segment发现跳过Agent确认: %s', e)
            agent = None
        result = _learn(db_path=db, agent=agent)
        return {
            'route': 'normal',
            'adjustments': result.adjustments,
            'circuit_breaks': len(result.circuit_breaks),
        }

    # 绑定db_path到处理器
    def _make_handler(func, db):
        def handler(state):
            return func(state, db)
        return handler

    return {
        'perceive': _make_handler(perceive, _db),
        'collect': _make_handler(collect, _db),
        'intel': _make_handler(intel, _db),
        'classify': _make_handler(classify, _db),
        'analyze': _make_handler(analyze, _db),
        'push': _make_handler(push, _db),
        'clv_update': _make_handler(clv_update, _db),
        'validate': _make_handler(validate, _db),
        'learn': learn_adapter,
    }


def auto_recover(db_path: str):
    """自动修复卡住的日循环状态

    规则:
    1. 过去日期的status='running' → 标记为'abandoned'
    2. 今天status='running'但updated_at超过2小时 → 从断点恢复
    3. 今天status='failed' → 从失败节点重试
    """
    import json
    today = today_beijing()

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. 过去卡住的 → abandoned
        cursor.execute("""
            UPDATE daily_cycle_state SET status = 'abandoned',
                error_message = 'auto_recovered: past date still running'
            WHERE date < ? AND status = 'running'
        """, (today,))
        abandoned = cursor.rowcount

        # 2. 今天卡住的(>2h) → 从断点恢复
        cursor.execute("""
            SELECT date, current_node, status, updated_at FROM daily_cycle_state
            WHERE date = ? AND status IN ('running', 'failed')
        """, (today,))
        stuck = cursor.fetchone()

        recovered_node = None
        if stuck:
            updated_at = stuck['updated_at']
            if updated_at:
                # 检查是否超过2小时
                from datetime import timedelta, timezone
                utc_plus8 = timezone(timedelta(hours=8))
                try:
                    last_update = datetime.strptime(str(updated_at), '%Y-%m-%d %H:%M:%S')
                    last_update = last_update.replace(tzinfo=utc_plus8)
                    elapsed = datetime.now(utc_plus8) - last_update
                    if elapsed.total_seconds() > 7200:  # 2h
                        cursor.execute("""
                            UPDATE daily_cycle_state SET status = 'recovered',
                                error_message = ?
                            WHERE date = ?
                        """, (f'auto_recovered: stuck for {elapsed}', today))
                        recovered_node = stuck['current_node']
                        logger.info('自动恢复: 日期=%s, 断点=%s, 卡住%.0f分钟',
                                    today, recovered_node, elapsed.total_seconds() / 60)
                except ValueError:
                    pass

        conn.commit()
        conn.close()

        if abandoned > 0:
            logger.info('自动恢复: %d个过去日期标记为abandoned', abandoned)

        return {
            'abandoned': abandoned,
            'recovered_node': recovered_node,
        }

    except Exception as e:
        logger.warning('自动恢复失败: %s', e)
        return {'abandoned': 0, 'recovered_node': None}


def run_mode(mode: str, db_path: str = None):
    """按模式运行日循环"""
    _db = db_path or DB_PATH

    # 自动恢复卡住的状态
    recovery = auto_recover(_db)

    from backend.app.data_access.cycle_dao import CycleStateDAO
    dao = CycleStateDAO(_db)

    today = today_beijing()

    # 如果有恢复的断点, 从断点继续
    # 但如果断点是perceive之后的节点且日期是昨天的, 说明昨天没跑完
    # 今天应该从collect重新开始(需要采集新比赛)
    if recovery.get('recovered_node') and mode in ('morning', 'full'):
        node = recovery['recovered_node']
        # 如果断点在perceive之后, 说明前一天的collect/analyze已完成
        # 但今天是新的一天, 需要重新从collect开始采集新比赛
        if node in ('learn', 'validate', 'clv_update', 'push', 'analyze', 'classify', 'intel'):
            logger.info('断点 %s 是前一天残留, 今日从collect重新开始', node)
            state = CycleState(date=today, current_node='collect')
        else:
            logger.info('从断点恢复: %s', node)
            state = CycleState(date=today, current_node=node)
    else:
        # 检查今天是否已有完成的状态
        existing = dao.load(today)
        if existing and existing.get('status') == 'done':
            logger.info('今日循环已完成, 跳过')
            print('今日循环已完成')
            return
        state = CycleState(date=today)

    handlers = get_handlers(_db)
    machine = DailyCycleStateMachine(handlers, dao)

    if mode == 'perceive':
        result = handlers['perceive'](state)
        print(f"自感知完成: {result}")
    elif mode == 'collect':
        state.current_node = 'collect'
        machine.run_cycle(state, stop_at='classify')
    elif mode == 'intel':
        state.current_node = 'intel'
        machine.run_cycle(state, stop_at='classify')
    elif mode == 'classify':
        state.current_node = 'classify'
        machine.run_cycle(state, stop_at='analyze')
    elif mode == 'analyze':
        state.current_node = 'analyze'
        machine.run_cycle(state, stop_at='push')
    elif mode == 'push':
        state.current_node = 'push'
        machine.run_cycle(state, stop_at='clv_update')
    elif mode == 'clv':
        state.current_node = 'clv_update'
        machine.run_cycle(state, stop_at='validate')
    elif mode == 'validate':
        state.current_node = 'validate'
        machine.run_cycle(state, stop_at='learn')
    elif mode == 'learn':
        state.current_node = 'learn'
        machine.run_cycle(state, stop_at=None)
    elif mode == 'morning':
        # 完整上午: perceive → collect → ... → push → clv_update
        machine.run_cycle(state)
    elif mode == 'full':
        machine.run_cycle(state)
    else:
        print(f"Unknown mode: {mode}")
        return

    print(f"状态: {state.status}, 当前节点: {state.current_node}")


def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    parser = argparse.ArgumentParser(description='足球分析日循环')
    parser.add_argument('--mode', default='perceive',
                        choices=['perceive', 'collect', 'intel', 'classify', 'analyze', 'push', 'clv', 'validate', 'learn', 'morning', 'full'])
    parser.add_argument('--db', default=None, help='数据库路径')
    args = parser.parse_args()

    run_mode(args.mode, args.db)


if __name__ == '__main__':
    main()