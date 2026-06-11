"""
特征提取器模块 - 热插拔设计

包含:
- FeatureExtractor: 基类
- ExtractionContext: 提取上下文
- ExtractionResult: 提取结果
- FeatureExtractorRegistry: 注册表
- SPFAnalyzer: 胜平负分析
- ScorePredictor: 比分预测
- BQCAnalyzer: 半全场分析
- HandicapAnalyzer: 让球分析
"""

from .base import (
    ExtractionContext,
    ExtractionResult,
    FeatureExtractor,
    DataDrivenExtractor,
    CalculationExtractor,
    ContextExtractor,
    MarketExtractor
)
from .registry import FeatureExtractorRegistry

# 数学分析器
from .math.spf_analyzer import SPFAnalyzer
from .math.score_predictor import ScorePredictor
from .math.bqc_analyzer import BQCAnalyzer
from .math.handicap_analyzer import HandicapAnalyzer

# 别名
BaseFeatureExtractor = FeatureExtractor

__all__ = [
    # 基类
    'BaseFeatureExtractor',
    'ExtractionContext',
    'ExtractionResult',
    'FeatureExtractor',
    'DataDrivenExtractor',
    'CalculationExtractor',
    'ContextExtractor',
    'MarketExtractor',
    # 注册表
    'FeatureExtractorRegistry',
    # 分析器
    'SPFAnalyzer',
    'ScorePredictor',
    'BQCAnalyzer',
    'HandicapAnalyzer'
]
