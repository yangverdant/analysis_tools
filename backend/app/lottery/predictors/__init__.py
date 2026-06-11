"""
预测模型模块

提供各玩法的预测模型，整合多个特征提取器的结果
"""

from .base import (
    BasePredictor,
    PredictionResult,
    PredictionType,
    FeatureContribution,
    PredictorRegistry
)

from .spf_predictor import SPFPredictor

__all__ = [
    'BasePredictor',
    'PredictionResult',
    'PredictionType',
    'FeatureContribution',
    'PredictorRegistry',
    'SPFPredictor'
]