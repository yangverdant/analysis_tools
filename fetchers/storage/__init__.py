"""
统一数据串联层 — 存储模块

核心模块:
- schema: 表结构定义
- database: SQLite连接+建表
- crud: 增删改查操作

使用示例:
    from fetchers.storage import UnifiedStorage

    storage = UnifiedStorage()
    storage.upsert_match("2026-05-25|arsenal|chelsea", ...)
    match = storage.get_match("2026-05-25|arsenal|chelsea")
"""

from fetchers.storage.crud import UnifiedStorage
from fetchers.storage.database import get_db_path, init_database

__all__ = ['UnifiedStorage', 'get_db_path', 'init_database']