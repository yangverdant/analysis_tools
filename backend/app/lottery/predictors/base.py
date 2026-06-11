"""
预测模型基类

定义预测模型的统一接口，用于整合多个特征提取器的结果，
生成最终的预测结果。

预测模型与特征提取器的区别:
- 特征提取器: 提取单一维度的特征 (如Poisson概率、Elo评分等)
- 预测模型: 整合多个特征，生成最终预测结果
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PredictionType(Enum):
    """预测类型"""
    SPF = "spf"          # 胜平负
    BF = "bf"           # 比分
    BQC = "bqc"         # 半全场
    RQSPF = "rqspf"     # 让球胜平负


@dataclass
class PredictionResult:
    """
    预测结果数据类

    Attributes:
        prediction_type: 预测类型
        predicted_result: 预测结果 (如: "home_win", "1:0", "33"等)
        predicted_prob: 预测概率 (0-1)
        confidence: 置信度 (0-1)
        confidence_level: 置信度等级 (high/medium/low)
        all_probabilities: 所有选项的概率分布
        feature_contributions: 各特征的贡献度
        value_bet: 是否为价值投注
        value: 价值百分比
        odds: 相关赔率
        raw_data: 原始数据
    """
    prediction_type: PredictionType
    predicted_result: str
    predicted_prob: float
    confidence: float
    confidence_level: str = "medium"
    all_probabilities: Dict[str, float] = field(default_factory=dict)
    feature_contributions: Dict[str, float] = field(default_factory=dict)
    value_bet: bool = False
    value: float = 0.0
    odds: Optional[float] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'prediction_type': self.prediction_type.value,
            'predicted_result': self.predicted_result,
            'predicted_prob': round(self.predicted_prob, 4),
            'confidence': round(self.confidence, 4),
            'confidence_level': self.confidence_level,
            'all_probabilities': {k: round(v, 4) for k, v in self.all_probabilities.items()},
            'feature_contributions': {k: round(v, 4) for k, v in self.feature_contributions.items()},
            'value_bet': self.value_bet,
            'value': round(self.value, 4),
            'odds': self.odds,
            'raw_data': self.raw_data
        }


@dataclass
class FeatureContribution:
    """
    特征贡献记录

    记录每个特征提取器对最终预测的贡献
    """
    feature_name: str
    feature_value: float
    weight: float
    contribution: float  # feature_value * weight
    confidence: float


class BasePredictor(ABC):
    """
    预测模型基类

    所有预测模型必须继承此类并实现 predict() 方法
    """

    def __init__(self, db_path: str, config: Dict = None):
        """
        初始化预测模型

        Args:
            db_path: 数据库路径
            config: 配置参数
        """
        self.db_path = db_path
        self.config = config or {}
        self._feature_weights = self._get_default_weights()
        self._initialized = True

    @property
    @abstractmethod
    def name(self) -> str:
        """返回模型名称"""
        pass

    @property
    @abstractmethod
    def prediction_type(self) -> PredictionType:
        """返回预测类型"""
        pass

    @abstractmethod
    def predict(self, context: Dict[str, Any]) -> PredictionResult:
        """
        执行预测

        Args:
            context: 预测上下文，包含:
                - home_team_id: 主队ID
                - away_team_id: 客队ID
                - match_id: 比赛ID (可选)
                - features: 已提取的特征 (可选，如未提供则自动提取)
                - odds: 赔率数据 (可选)

        Returns:
            PredictionResult: 预测结果
        """
        pass

    def _get_default_weights(self) -> Dict[str, float]:
        """
        获取默认特征权重

        子类可重写此方法提供不同的默认权重
        """
        return {}

    def update_weights(self, weights: Dict[str, float]) -> None:
        """
        更新特征权重

        Args:
            weights: 新的权重字典
        """
        self._feature_weights.update(weights)
        # 归一化权重
        total = sum(self._feature_weights.values())
        if total > 0:
            self._feature_weights = {
                k: v / total for k, v in self._feature_weights.items()
            }

    def get_weights(self) -> Dict[str, float]:
        """获取当前权重"""
        return self._feature_weights.copy()

    def _calculate_confidence_level(self, confidence: float) -> str:
        """
        根据置信度值计算置信度等级

        Args:
            confidence: 置信度值 (0-1)

        Returns:
            置信度等级 (high/medium/low)
        """
        if confidence >= 0.6:
            return "high"
        elif confidence >= 0.35:
            return "medium"
        else:
            return "low"

    def _check_value_bet(
        self,
        predicted_prob: float,
        odds: Optional[float],
        threshold: float = 0.05
    ) -> tuple:
        """
        检查是否为价值投注

        Args:
            predicted_prob: 预测概率
            odds: 赔率
            threshold: 价值阈值

        Returns:
            (is_value_bet, value)
        """
        if not odds or odds <= 1:
            return False, 0.0

        implied_prob = 1 / odds
        value = predicted_prob - implied_prob

        return value > threshold, value

    def _combine_features(
        self,
        features: Dict[str, Dict[str, float]],
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        组合多个特征的结果

        Args:
            features: 特征字典 {feature_name: {result: prob}}
            weights: 权重字典 (可选，默认使用 self._feature_weights)

        Returns:
            组合后的概率分布
        """
        if weights is None:
            weights = self._feature_weights

        # 初始化结果
        all_results = set()
        for feat_probs in features.values():
            all_results.update(feat_probs.keys())

        combined = {result: 0.0 for result in all_results}
        total_weight = 0.0

        for feature_name, feat_probs in features.items():
            weight = weights.get(feature_name, 0.0)
            if weight <= 0:
                continue

            total_weight += weight
            for result, prob in feat_probs.items():
                combined[result] += prob * weight

        # 归一化
        if total_weight > 0:
            combined = {k: v / total_weight for k, v in combined.items()}

        return combined

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}' type={self.prediction_type.value}>"


class PredictorRegistry:
    """
    预测模型注册表

    管理所有注册的预测模型
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._predictors = {}
            cls._instance._db_path = None
        return cls._instance

    def initialize(self, db_path: str):
        """初始化注册表"""
        self._db_path = db_path

    def register(self, predictor: BasePredictor) -> None:
        """注册预测模型"""
        self._predictors[predictor.name] = predictor
        logger.info(f"Registered predictor: {predictor.name}")

    def get(self, name: str) -> Optional[BasePredictor]:
        """获取预测模型"""
        return self._predictors.get(name)

    def get_by_type(self, prediction_type: PredictionType) -> List[BasePredictor]:
        """按类型获取预测模型"""
        return [
            p for p in self._predictors.values()
            if p.prediction_type == prediction_type
        ]

    def list_predictors(self) -> List[str]:
        """列出所有预测模型"""
        return list(self._predictors.keys())

    def predict_all(self, context: Dict[str, Any]) -> Dict[str, PredictionResult]:
        """
        使用所有注册的模型进行预测

        Args:
            context: 预测上下文

        Returns:
            {predictor_name: PredictionResult}
        """
        results = {}
        for name, predictor in self._predictors.items():
            try:
                results[name] = predictor.predict(context)
            except Exception as e:
                logger.error(f"Prediction failed for {name}: {e}")
        return results
