"""
数据流水线模块
四层架构：分拣层 -> 采集层 -> 清洗层 -> 导入层
"""

from .tasks import TaskManager, TaskType, TaskStatus, Task, TaskPriority
from .router import PipelineRouter, RoutingResult, DataSource
from .collector import DataCollector, CollectResult, BaseCollector
from .cleaner import DataCleaner, CleanResult
from .loader import DataLoader, LoadResult
from .schema import (
    TABLES, get_table_def, get_column_names, get_field_map,
    get_all_tables_summary, API_SPORTS_FIELD_MAP, THESPORTSDB_FIELD_MAP
)
from .sources import (
    DATA_SOURCES, get_source_config, get_sources_for_task,
    get_best_source, check_rate_limit, update_usage,
    get_league_support, get_sources_for_league, get_all_supported_leagues,
    get_data_type_support, get_available_fields,
    DataSourceType, TierLimit, DataField, DataTypeSupport,
    LeagueSupport, DataSourceConfig
)
from .routes import router as pipeline_router

__all__ = [
    # 任务管理
    'TaskManager',
    'TaskType',
    'TaskStatus',
    'Task',
    'TaskPriority',

    # 分拣层
    'PipelineRouter',
    'RoutingResult',
    'DataSource',

    # 采集层
    'DataCollector',
    'CollectResult',
    'BaseCollector',

    # 清洗层
    'DataCleaner',
    'CleanResult',

    # 导入层
    'DataLoader',
    'LoadResult',

    # 数据库表结构
    'TABLES',
    'get_table_def',
    'get_column_names',
    'get_field_map',
    'get_all_tables_summary',
    'API_SPORTS_FIELD_MAP',
    'THESPORTSDB_FIELD_MAP',

    # 数据源配置
    'DATA_SOURCES',
    'get_source_config',
    'get_sources_for_task',
    'get_best_source',
    'check_rate_limit',
    'update_usage',
    'get_league_support',
    'get_sources_for_league',
    'get_all_supported_leagues',
    'get_data_type_support',
    'get_available_fields',
    'DataSourceType',
    'TierLimit',
    'DataField',
    'DataTypeSupport',
    'LeagueSupport',
    'DataSourceConfig',

    # API 路由
    'pipeline_router'
]