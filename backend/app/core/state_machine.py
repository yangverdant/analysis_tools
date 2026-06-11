"""轻量日循环工作流引擎

9节点线性流程，条件边驱动路由。
SQLite持久化，断点可恢复。
"""

import json
import logging
from typing import Callable, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CycleState:
    """日循环状态"""
    date: str
    current_node: str = 'perceive'
    status: str = 'running'
    results: Dict = field(default_factory=dict)
    error: Optional[str] = None


class DailyCycleStateMachine:
    """日循环状态机 — 条件边驱动"""

    NODES = ['perceive', 'collect', 'intel', 'classify',
             'analyze', 'push', 'clv_update', 'validate', 'learn']

    TRANSITIONS = {
        'perceive': {'normal': 'collect', 'validate_yesterday': 'validate',
                     'circuit_break': 'collect', 'warmup': 'collect'},
        'collect': {'normal': 'intel'},
        'intel': {'normal': 'classify'},
        'classify': {'normal': 'analyze'},
        'analyze': {'normal': 'push'},
        'push': {'normal': 'clv_update'},
        'clv_update': {'normal': 'validate'},
        'validate': {'normal': 'learn'},
        'learn': {'normal': 'done'},
    }

    def __init__(self, node_handlers: Dict[str, Callable], cycle_dao):
        self.handlers = node_handlers
        self.cycle_dao = cycle_dao

    def run_node(self, state: CycleState, node: str) -> dict:
        handler = self.handlers.get(node)
        if not handler:
            raise ValueError(f"No handler for node: {node}")
        return handler(state)

    def get_next(self, current: str, result: dict) -> str:
        transition = self.TRANSITIONS.get(current, {})
        if isinstance(transition, dict):
            route = result.get('route', 'normal')
            next_node = transition.get(route)
            if next_node is None:
                # fallback to 'normal' if route not found
                next_node = transition.get('normal', 'done')
            return next_node
        elif isinstance(transition, str):
            return transition
        # If transition is a dict, use it
        return 'done'

    def run_cycle(self, state: CycleState, stop_at: str = None) -> CycleState:
        """运行日循环，直到stop_at或状态结束"""
        while state.status == 'running':
            try:
                result = self.run_node(state, state.current_node)
                state.results[state.current_node] = result

                next_node = self.get_next(state.current_node, result)

                if next_node.startswith('done'):
                    state.status = next_node
                    break

                state.current_node = next_node
                self._save_state(state)

                if stop_at and state.current_node == stop_at:
                    break

            except Exception as e:
                state.status = 'failed'
                state.error = str(e)
                self._save_state(state)
                logger.error(f"Cycle failed at {state.current_node}: {e}")
                break

        return state

    def _save_state(self, state: CycleState):
        """持久化状态"""
        try:
            self.cycle_dao.save({
                'date': state.date,
                'current_node': state.current_node,
                'status': state.status,
                'error_message': state.error,
            })
            # 保存各节点结果
            for node, result in state.results.items():
                self.cycle_dao.update_node_result(
                    state.date, node,
                    json.dumps(result, ensure_ascii=False, default=str)
                )
        except Exception as e:
            logger.debug(f"State save error: {e}")