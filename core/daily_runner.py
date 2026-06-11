"""
日循环入口 — 独立运行，不依赖FastAPI

用法:
    python -m core.daily_runner --mode perceive
    python -m core.daily_runner --mode collect
    python -m core.daily_runner --mode classify
    python -m core.daily_runner --mode analyze
    python -m core.daily_runner --mode validate
    python -m core.daily_runner --mode full
"""

import argparse
import logging
import sys
import os
from datetime import date
from pathlib import Path

import yaml

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    """加载 config/config.yaml"""
    config_path = PROJECT_ROOT / 'config' / 'config.yaml'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def setup_logging(config: dict):
    """配置日志"""
    log_dir = PROJECT_ROOT / 'logs'
    log_dir.mkdir(exist_ok=True)

    log_level = logging.INFO
    log_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                log_dir / f'daily_{date.today().isoformat()}.log',
                encoding='utf-8',
            ),
        ],
    )


def get_db_path(config: dict) -> str:
    """从配置获取数据库路径"""
    rel = config.get('database', {}).get('path', 'data/football_v2.db')
    return str(PROJECT_ROOT / rel)


class DailyRunner:
    """日循环编排器 — 按时间线串联各模块"""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.db_path = get_db_path(self.config)
        self.logger = logging.getLogger('core.daily_runner')

        # 惰性初始化各模块
        self._perception = None
        self._collector = None
        self._classifier = None
        self._analyzer = None
        self._validator = None

    @property
    def perception(self):
        if self._perception is None:
            from .self_perception import SelfPerception
            self._perception = SelfPerception(self.db_path, self.config)
        return self._perception

    @property
    def collector(self):
        if self._collector is None:
            from .collector import Collector
            self._collector = Collector(self.db_path, self.config)
        return self._collector

    @property
    def classifier(self):
        if self._classifier is None:
            from .classifier import Classifier
            self._classifier = Classifier(self.db_path, self.config)
        return self._classifier

    @property
    def analyzer(self):
        if self._analyzer is None:
            from .analyzer import Analyzer
            self._analyzer = Analyzer(self.db_path, self.config)
        return self._analyzer

    @property
    def validator(self):
        if self._validator is None:
            from .validator import Validator
            self._validator = Validator(self.db_path, self.config)
        return self._validator

    # --- 各模式入口 ---

    def run_perceive(self) -> dict:
        """6:00 自感知"""
        self.logger.info('=== 6:00 自感知开始 ===')
        result = self.perception.run()
        self.logger.info('=== 自感知完成: %s ===', result.get('status', 'unknown'))
        return result

    def run_collect(self, match_date: date = None) -> dict:
        """7:00 采集编排"""
        if match_date is None:
            match_date = date.today()
        self.logger.info('=== 7:00 采集编排开始 (%s) ===', match_date)
        result = self.collector.run(match_date)
        self.logger.info('=== 采集完成: %d场比赛 ===', result.get('saved', 0))
        return result

    def run_classify(self, match_date: date = None) -> dict:
        """8:30 赛事分类"""
        if match_date is None:
            match_date = date.today()
        self.logger.info('=== 8:30 赛事分类开始 (%s) ===', match_date)
        result = self.classifier.run(match_date)
        self.logger.info('=== 分类完成: %d场 ===', result.get('classified', 0))
        return result

    def run_analyze(self, match_date: date = None) -> dict:
        """9:00 分析"""
        if match_date is None:
            match_date = date.today()
        self.logger.info('=== 9:00 分析开始 (%s) ===', match_date)
        result = self.analyzer.run(match_date)
        self.logger.info('=== 分析完成: %d场 ===', result.get('analyzed', 0))
        return result

    def run_validate(self, match_date: date = None) -> dict:
        """次日复盘"""
        if match_date is None:
            match_date = date.today()
        self.logger.info('=== 复盘验证开始 (%s) ===', match_date)
        result = self.validator.run(match_date)
        self.logger.info('=== 复盘完成: %d场 ===', result.get('validated', 0))
        return result

    def run_full(self, match_date: date = None) -> dict:
        """完整日循环"""
        if match_date is None:
            match_date = date.today()
        self.logger.info('====== 完整日循环开始 (%s) ======', match_date)

        results = {}

        # 6:00 自感知
        results['perceive'] = self.run_perceive()

        # 7:00 采集
        results['collect'] = self.run_collect(match_date)

        # 8:30 分类
        results['classify'] = self.run_classify(match_date)

        # 9:00 分析
        results['analyze'] = self.run_analyze(match_date)

        # 复盘 (用前一天)
        from datetime import timedelta
        results['validate'] = self.run_validate(match_date - timedelta(days=1))

        self.logger.info('====== 完整日循环结束 ======')
        return results


def main():
    parser = argparse.ArgumentParser(description='足球分析日循环')
    parser.add_argument(
        '--mode',
        choices=['perceive', 'collect', 'classify', 'analyze', 'validate', 'full'],
        required=True,
        help='运行模式',
    )
    parser.add_argument('--date', type=str, default=None, help='指定日期 YYYY-MM-DD')
    args = parser.parse_args()

    config = load_config()
    setup_logging(config)

    runner = DailyRunner(config)
    match_date = date.fromisoformat(args.date) if args.date else None

    mode_map = {
        'perceive': lambda: runner.run_perceive(),
        'collect': lambda: runner.run_collect(match_date),
        'classify': lambda: runner.run_classify(match_date),
        'analyze': lambda: runner.run_analyze(match_date),
        'validate': lambda: runner.run_validate(match_date),
        'full': lambda: runner.run_full(match_date),
    }

    result = mode_map[args.mode]()
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
