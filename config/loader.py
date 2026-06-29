"""
统一配置加载器
支持从 config.yaml 和 api_keys.yaml 加载配置
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# 配置文件路径
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
API_KEYS_FILE = CONFIG_DIR / "api_keys.yaml"
LEGACY_API_CONFIG = CONFIG_DIR / "api_config.json"


class Config:
    """统一配置管理类"""

    _instance: Optional["Config"] = None
    _config: Dict[str, Any] = {}
    _api_keys: Dict[str, Any] = {}

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        """加载所有配置文件"""
        # 加载主配置
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}

        # 加载API密钥
        if API_KEYS_FILE.exists():
            with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
                self._api_keys = yaml.safe_load(f) or {}

    def reload(self) -> None:
        """重新加载配置"""
        self._load()

    # === 数据库配置 ===
    @property
    def db_path(self) -> Path:
        """数据库路径(绝对路径)"""
        path = self._config.get("database", {}).get("path", "data/football_v2.db")
        expanded = Path(os.path.expandvars(str(path))).expanduser()
        if expanded.is_absolute():
            return expanded.resolve()
        return (PROJECT_ROOT / expanded).resolve()

    @property
    def db_backup_dir(self) -> Path:
        """数据库备份目录"""
        path = os.environ.get(
            "FOOTBALL_BACKUP_DIR",
            self._config.get("database", {}).get("backup_dir", "../football_backups/app_backups"),
        )
        expanded = Path(os.path.expandvars(str(path))).expanduser()
        if expanded.is_absolute():
            return expanded.resolve()
        return (PROJECT_ROOT / expanded).resolve()

    # === 调度器配置 ===
    @property
    def scheduler_timezone(self) -> str:
        return self._config.get("scheduler", {}).get("timezone", "Asia/Shanghai")

    @property
    def scheduler_jobs(self) -> Dict[str, str]:
        """返回所有调度任务的cron表达式"""
        return self._config.get("scheduler", {}).get("jobs", {})

    # === 数据源配置 ===
    def get_data_source(self, name: str) -> Dict[str, Any]:
        """获取指定数据源的配置"""
        sources = self._config.get("data_sources", {})
        source_config = sources.get(name, {})

        # 合并API密钥
        if name in self._api_keys:
            source_config.update(self._api_keys[name])

        return source_config

    def get_all_data_sources(self) -> Dict[str, Dict[str, Any]]:
        """获取所有数据源配置(含密钥)"""
        sources = self._config.get("data_sources", {})
        result = {}
        for name, cfg in sources.items():
            result[name] = cfg.copy()
            if name in self._api_keys:
                result[name].update(self._api_keys[name])
        return result

    # === RapidAPI配置 ===
    @property
    def rapidapi_key(self) -> Optional[str]:
        return self._api_keys.get("rapidapi", {}).get("key")

    def get_rapidapi_source(self, name: str) -> Dict[str, Any]:
        """获取RapidAPI数据源配置"""
        rapidapi = self._config.get("rapidapi", {}).get("apis", {})
        source = rapidapi.get(name, {})
        if self.rapidapi_key:
            source["api_key"] = self.rapidapi_key
        return source

    # === 模型配置 ===
    @property
    def model_version(self) -> str:
        return self._config.get("model", {}).get("version", "3.9.2")

    @property
    def model_config(self) -> Dict[str, Any]:
        return self._config.get("model", {})

    # === 路径配置 ===
    def get_path(self, name: str) -> Path:
        """获取指定路径(绝对路径)"""
        paths = self._config.get("paths", {})
        relative = paths.get(name, name)
        return PROJECT_ROOT / relative

    # === 原始配置访问 ===
    @property
    def raw(self) -> Dict[str, Any]:
        """返回原始配置字典"""
        return self._config

    @property
    def api_keys(self) -> Dict[str, Any]:
        """返回API密钥字典"""
        return self._api_keys

    # === 兼容旧代码 ===
    def get_api_key(self, source: str) -> Optional[str]:
        """获取指定数据源的API Key(兼容旧代码)"""
        keys = self._api_keys.get(source, {})
        return keys.get("api_key") or keys.get("api_token")

    def get_base_url(self, source: str) -> Optional[str]:
        """获取指定数据源的Base URL"""
        source_config = self._config.get("data_sources", {}).get(source, {})
        return source_config.get("base_url")


# 全局配置实例
config = Config()


# === 便捷函数 ===
def get_config() -> Config:
    """获取全局配置实例"""
    return config


def get_db_path() -> Path:
    """获取数据库路径"""
    return config.db_path


def get_api_key(source: str) -> Optional[str]:
    """获取API Key"""
    return config.get_api_key(source)


def get_data_source_config(source: str) -> Dict[str, Any]:
    """获取数据源完整配置(含密钥)"""
    return config.get_data_source(source)


# === 兼容旧api_config.json加载方式 ===
def load_api_config_legacy() -> Dict[str, Any]:
    """
    兼容旧的api_config.json加载方式
    返回扁平化的API配置字典
    """
    result = {}

    # 从新配置构建兼容格式
    for name, cfg in config.get_all_data_sources().items():
        result[name] = {
            "base_url": cfg.get("base_url"),
            "api_key": cfg.get("api_key"),
            "api_token": cfg.get("api_token"),
        }

    # 添加rapidapi
    if config.rapidapi_key:
        result["rapidapi"] = {"key": config.rapidapi_key}

    return result


if __name__ == "__main__":
    # 测试配置加载
    print("=== 配置测试 ===")
    print(f"数据库路径: {config.db_path}")
    print(f"时区: {config.scheduler_timezone}")
    print(f"调度任务: {config.scheduler_jobs}")
    print(f"模型版本: {config.model_version}")
    print(f"\n数据源列表: {list(config.get_all_data_sources().keys())}")
    print(f"\nSporttery配置: {config.get_data_source('sporttery')}")
    print(f"\nAPI Keys (已配置): {list(config.api_keys.keys())}")
