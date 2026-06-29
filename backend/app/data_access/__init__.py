"""data_access — 统一数据访问层

拆分自 backend/app/lottery/dao/lottery_dao.py，按表职责分离。
"""

from .database import get_connection
from .match_dao import LotteryMatchDAO
from .odds_dao import LotteryOddsDAO
from .result_dao import ResultDAO
from .prediction_dao import PredictionDAO
from .validation_dao import ValidationDAO
from .health_dao import DataSourceHealthDAO
from .cycle_dao import CycleStateDAO
from .foundation_dao import FoundationDAO

__all__ = [
    'get_connection',
    'LotteryMatchDAO',
    'LotteryOddsDAO',
    'ResultDAO',
    'PredictionDAO',
    'ValidationDAO',
    'DataSourceHealthDAO',
    'CycleStateDAO',
    'FoundationDAO',
]
