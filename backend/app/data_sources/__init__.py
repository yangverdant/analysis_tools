"""
数据源模块 - 统一接口管理所有足球数据源
支持API、爬虫、本地数据等多种数据源类型

核心组件:
1. source_knowledge.py - 数据源能力知识库
2. source_registry.py - 数据源注册和字段映射
3. data_cleaner.py - 数据清洗和SQL生成
4. collection_service.py - 统一采集服务
5. intelligent_collector.py - 智能多源合并采集
6. data_completion.py - AI补充和查漏补缺
"""

from .base import BaseDataSource, DataSourceType, DataCategory
from .manager import DataSourceManager
from .source_registry import (
    DataSourceRegistry, SourceRegistryManager, registry_manager,
    FieldMapping, FieldType
)
from .data_cleaner import DataCleaner, DataTransformer, SQLGenerator
from .collection_service import (
    UnifiedCollectionService, CollectionRequest, CollectionResult,
    collection_service
)
from .source_knowledge import (
    knowledge_base, DataSourceCapability, LEAGUES,
    DataSourceKnowledgeBase
)
from .intelligent_collector import (
    IntelligentCollector, MatchQuery, MergedMatchData,
    DataCollectionAPI, collection_api
)
from .data_completion import (
    AIDataCompleter, MissingDataRequest, AICompletionResult,
    DataGapDetector, AutoSyncScheduler
)

__all__ = [
    # 基础类
    'BaseDataSource',
    'DataSourceType',
    'DataCategory',
    'DataSourceManager',

    # 注册和映射
    'DataSourceRegistry',
    'SourceRegistryManager',
    'registry_manager',
    'FieldMapping',
    'FieldType',

    # 清洗和SQL
    'DataCleaner',
    'DataTransformer',
    'SQLGenerator',

    # 采集服务
    'UnifiedCollectionService',
    'CollectionRequest',
    'CollectionResult',
    'collection_service',

    # 知识库
    'knowledge_base',
    'DataSourceCapability',
    'LEAGUES',
    'DataSourceKnowledgeBase',

    # 智能采集
    'IntelligentCollector',
    'MatchQuery',
    'MergedMatchData',
    'DataCollectionAPI',
    'collection_api',

    # AI补充
    'AIDataCompleter',
    'MissingDataRequest',
    'AICompletionResult',
    'DataGapDetector',
    'AutoSyncScheduler',
]
