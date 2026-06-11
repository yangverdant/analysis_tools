"""
SQLite连接管理 + 数据库初始化

新数据库: data/unified_football.db
不覆盖原有 football_v2.db
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

from fetchers.storage.schema import SCHEMA_SQL

logger = logging.getLogger(__name__)

# 默认数据库路径
_DEFAULT_DB_PATH = None


def get_db_path() -> str:
    """获取数据库路径"""
    global _DEFAULT_DB_PATH
    if _DEFAULT_DB_PATH is None:
        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        _DEFAULT_DB_PATH = str(data_dir / "unified_football.db")
    return _DEFAULT_DB_PATH


def set_db_path(path: str):
    """设置数据库路径（用于测试）"""
    global _DEFAULT_DB_PATH
    _DEFAULT_DB_PATH = path


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """获取数据库连接"""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database(db_path: str = None) -> bool:
    """初始化数据库（建表）"""
    path = db_path or get_db_path()
    try:
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA_SQL)
        conn.close()
        logger.info(f"数据库初始化完成: {path}")
        return True
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return False


def get_table_stats(db_path: str = None) -> dict:
    """获取各表记录数"""
    path = db_path or get_db_path()
    conn = get_connection(path)
    stats = {}
    for table in ["matches", "match_data", "standings", "players",
                  "injuries", "news", "weather", "fetch_log"]:
        try:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
            stats[table] = row["cnt"]
        except Exception:
            stats[table] = 0
    conn.close()
    return stats