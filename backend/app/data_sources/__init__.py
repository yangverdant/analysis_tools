"""
数据源模块 - 统一接口管理所有足球数据源
支持API、爬虫、本地数据等多种数据源类型
"""

from .base import BaseDataSource, DataSourceType, DataCategory
from .manager import DataSourceManager

__all__ = [
    'BaseDataSource',
    'DataSourceType',
    'DataCategory',
    'DataSourceManager',
]
