"""core — 日循环核心模块

入口: python -m backend.app.core.daily_runner --mode <mode>
节点: perceive → collect → intel → classify → analyze → push → clv_update → validate → learn
"""

from .daily_runner import run_mode
from .state_machine import DailyCycleStateMachine, CycleState